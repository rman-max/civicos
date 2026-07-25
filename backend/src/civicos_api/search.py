from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import date, datetime
from enum import StrEnum
from typing import Any, Protocol
from uuid import UUID

import httpx
import psycopg
from psycopg.rows import dict_row


class SearchMode(StrEnum):
    KEYWORD = "keyword"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"


class SearchUnavailableError(RuntimeError):
    """Raised when a caller explicitly requests an unavailable semantic search dependency."""


class SemanticSearchError(RuntimeError):
    """Raised when an embedding or Qdrant operation fails."""


@dataclass(frozen=True)
class SearchFilters:
    start_date: date | None = None
    end_date: date | None = None
    department_ids: tuple[UUID, ...] = ()
    topic_ids: tuple[UUID, ...] = ()
    source_ids: tuple[UUID, ...] = ()
    municipality_ids: tuple[UUID, ...] = ()
    document_types: tuple[str, ...] = ()
    newest_first: bool = False


@dataclass(frozen=True)
class SearchHit:
    document_id: UUID
    document_version_id: UUID
    title: str
    document_type: str
    source_name: str | None
    canonical_url: str | None
    department_id: UUID | None
    published_at: date | None
    excerpt: str
    score: float
    match_kind: str
    ingested_at: datetime | None = None


@dataclass(frozen=True)
class SearchResponse:
    results: tuple[SearchHit, ...]
    semantic_available: bool


class SearchRepository(Protocol):
    async def keyword_search(
        self, *, organization_id: UUID, query: str, filters: SearchFilters, limit: int
    ) -> list[SearchHit]: ...

    async def documents_by_ids(
        self, *, organization_id: UUID, document_ids: tuple[UUID, ...], filters: SearchFilters
    ) -> list[SearchHit]: ...


class SemanticSearchClient(Protocol):
    async def search(
        self, *, organization_id: UUID, query: str, filters: SearchFilters, limit: int
    ) -> list[tuple[UUID, float]]: ...


class PostgresSearchRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url.replace("postgresql+psycopg://", "postgresql://", 1)

    async def keyword_search(
        self, *, organization_id: UUID, query: str, filters: SearchFilters, limit: int
    ) -> list[SearchHit]:
        clauses, parameters = self._filter_clauses(organization_id=organization_id, filters=filters)
        sql = f"""
            WITH terms AS (SELECT websearch_to_tsquery('english'::regconfig, %s) AS query),
            latest_versions AS (
              SELECT DISTINCT ON (organization_id, document_id)
                organization_id, document_id, id, extracted_text, search_vector, created_at
              FROM civic.document_versions
              WHERE organization_id = %s
              ORDER BY organization_id, document_id, version_number DESC
            )
            SELECT document.id AS document_id, version.id AS document_version_id, document.title,
              document.document_type, source.name AS source_name, document.canonical_url,
              document.department_id,
              document.published_at, version.created_at AS ingested_at,
              ts_headline('english'::regconfig, coalesce(version.extracted_text, ''), terms.query,
                'MaxFragments=2,MaxWords=18,MinWords=6') AS excerpt,
              ts_rank(document.search_vector, terms.query)
                + ts_rank(version.search_vector, terms.query) AS score
            FROM civic.documents AS document
            JOIN latest_versions AS version
              ON version.organization_id = document.organization_id
              AND version.document_id = document.id
            LEFT JOIN civic.sources AS source
              ON source.organization_id = document.organization_id
              AND source.id = document.source_id
            CROSS JOIN terms
            WHERE {" AND ".join(clauses)}
              AND (document.search_vector @@ terms.query OR version.search_vector @@ terms.query)
            ORDER BY {"document.published_at DESC NULLS LAST, score DESC" if filters.newest_first else "score DESC, document.published_at DESC NULLS LAST"},
              document.id
            LIMIT %s
        """
        rows = await self._fetchall(
            sql, (query, organization_id, *parameters, limit), organization_id
        )
        return [self._hit_from_row(row, match_kind="keyword") for row in rows]

    async def documents_by_ids(
        self, *, organization_id: UUID, document_ids: tuple[UUID, ...], filters: SearchFilters
    ) -> list[SearchHit]:
        if not document_ids:
            return []
        clauses, parameters = self._filter_clauses(organization_id=organization_id, filters=filters)
        sql = f"""
            WITH latest_versions AS (
              SELECT DISTINCT ON (organization_id, document_id)
                organization_id, document_id, id, extracted_text, created_at
              FROM civic.document_versions
              WHERE organization_id = %s
              ORDER BY organization_id, document_id, version_number DESC
            )
            SELECT document.id AS document_id, version.id AS document_version_id, document.title,
              document.document_type, source.name AS source_name, document.canonical_url,
              document.department_id,
              document.published_at, version.created_at AS ingested_at,
              left(coalesce(version.extracted_text, ''), 320) AS excerpt, 0::real AS score
            FROM civic.documents AS document
            JOIN latest_versions AS version
              ON version.organization_id = document.organization_id
              AND version.document_id = document.id
            LEFT JOIN civic.sources AS source
              ON source.organization_id = document.organization_id
              AND source.id = document.source_id
            WHERE {" AND ".join(clauses)}
              AND document.id = ANY(%s::uuid[])
            ORDER BY array_position(%s::uuid[], document.id)
        """
        rows = await self._fetchall(
            sql,
            (organization_id, *parameters, list(document_ids), list(document_ids)),
            organization_id,
        )
        return [self._hit_from_row(row, match_kind="semantic") for row in rows]

    def _filter_clauses(
        self, *, organization_id: UUID, filters: SearchFilters
    ) -> tuple[list[str], list[object]]:
        clauses = ["document.organization_id = %s"]
        parameters: list[object] = [organization_id]
        if filters.start_date is not None:
            clauses.append("document.published_at >= %s")
            parameters.append(filters.start_date)
        if filters.end_date is not None:
            clauses.append("document.published_at <= %s")
            parameters.append(filters.end_date)
        if filters.department_ids:
            clauses.append("document.department_id = ANY(%s::uuid[])")
            parameters.append(list(filters.department_ids))
        if filters.source_ids:
            clauses.append("document.source_id = ANY(%s::uuid[])")
            parameters.append(list(filters.source_ids))
        if filters.municipality_ids:
            clauses.append("source.municipality_id = ANY(%s::uuid[])")
            parameters.append(list(filters.municipality_ids))
        if filters.document_types:
            clauses.append("document.document_type = ANY(%s::text[])")
            parameters.append(list(filters.document_types))
        if filters.topic_ids:
            clauses.append(
                """EXISTS (
                  SELECT 1 FROM civic.topic_assignments AS assignment
                  WHERE assignment.organization_id = document.organization_id
                    AND assignment.document_id = document.id
                    AND assignment.topic_id = ANY(%s::uuid[])
                )"""
            )
            parameters.append(list(filters.topic_ids))
        return clauses, parameters

    async def _fetchall(
        self, sql: str, parameters: tuple[object, ...], organization_id: UUID
    ) -> list[dict[str, Any]]:
        async with await psycopg.AsyncConnection.connect(
            self._database_url, row_factory=dict_row
        ) as connection:
            async with connection.transaction():
                await connection.execute(
                    "SELECT set_config('app.organization_id', %s, true)", (str(organization_id),)
                )
                async with connection.cursor() as cursor:
                    await cursor.execute(sql, parameters)
                    return await cursor.fetchall()

    @staticmethod
    def _hit_from_row(row: dict[str, Any], *, match_kind: str) -> SearchHit:
        return SearchHit(
            document_id=UUID(str(row["document_id"])),
            document_version_id=UUID(str(row["document_version_id"])),
            title=str(row["title"]),
            document_type=str(row["document_type"]),
            source_name=str(row["source_name"]) if row["source_name"] else None,
            canonical_url=str(row["canonical_url"]) if row["canonical_url"] else None,
            department_id=UUID(str(row["department_id"])) if row["department_id"] else None,
            published_at=row["published_at"],
            ingested_at=row["ingested_at"],
            excerpt=str(row["excerpt"]),
            score=float(row["score"]),
            match_kind=match_kind,
        )


class OpenAICompatibleSemanticSearchClient:
    def __init__(
        self,
        *,
        embedding_base_url: str,
        embedding_model: str,
        embedding_api_key: str | None,
        qdrant_url: str,
        qdrant_collection: str,
        qdrant_api_key: str | None,
    ) -> None:
        self._embedding_base_url = embedding_base_url.rstrip("/")
        self._embedding_model = embedding_model
        self._embedding_api_key = embedding_api_key
        self._qdrant_url = qdrant_url.rstrip("/")
        self._qdrant_collection = qdrant_collection
        self._qdrant_api_key = qdrant_api_key

    async def search(
        self, *, organization_id: UUID, query: str, filters: SearchFilters, limit: int
    ) -> list[tuple[UUID, float]]:
        try:
            vector = await self._embed(query)
            payload_filter = self._qdrant_filter(organization_id=organization_id, filters=filters)
            headers = {"api-key": self._qdrant_api_key} if self._qdrant_api_key else {}
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{self._qdrant_url}/collections/{self._qdrant_collection}/points/query",
                    headers=headers,
                    json={
                        "query": vector,
                        "limit": limit,
                        "filter": payload_filter,
                        "with_payload": False,
                    },
                )
            response.raise_for_status()
            points = response.json().get("result", {}).get("points", [])
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            raise SemanticSearchError("Semantic search backend is unavailable") from error
        return [(UUID(str(point["id"])), float(point["score"])) for point in points]

    async def _embed(self, query: str) -> list[float]:
        headers = (
            {"Authorization": f"Bearer {self._embedding_api_key}"}
            if self._embedding_api_key
            else {}
        )
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self._embedding_base_url}/embeddings",
                headers=headers,
                json={"model": self._embedding_model, "input": query},
            )
        response.raise_for_status()
        embedding = response.json()["data"][0]["embedding"]
        if not isinstance(embedding, list) or not all(
            isinstance(value, int | float) for value in embedding
        ):
            raise ValueError("Embedding provider returned an invalid vector")
        return [float(value) for value in embedding]

    @staticmethod
    def _qdrant_filter(*, organization_id: UUID, filters: SearchFilters) -> dict[str, object]:
        conditions: list[dict[str, object]] = [
            {"key": "organization_id", "match": {"value": str(organization_id)}}
        ]
        if filters.department_ids:
            conditions.append(
                {
                    "key": "department_id",
                    "match": {"any": [str(value) for value in filters.department_ids]},
                }
            )
        if filters.source_ids:
            conditions.append(
                {"key": "source_id", "match": {"any": [str(value) for value in filters.source_ids]}}
            )
        if filters.topic_ids:
            conditions.append(
                {"key": "topic_ids", "match": {"any": [str(value) for value in filters.topic_ids]}}
            )
        if filters.start_date or filters.end_date:
            date_range: dict[str, str] = {}
            if filters.start_date:
                date_range["gte"] = filters.start_date.isoformat()
            if filters.end_date:
                date_range["lte"] = filters.end_date.isoformat()
            conditions.append({"key": "published_at", "range": date_range})
        return {"must": conditions}


class HybridSearchService:
    def __init__(
        self, *, repository: SearchRepository, semantic_client: SemanticSearchClient | None
    ) -> None:
        self._repository = repository
        self._semantic_client = semantic_client

    async def search(
        self,
        *,
        organization_id: UUID,
        query: str,
        filters: SearchFilters,
        mode: SearchMode,
        limit: int,
    ) -> SearchResponse:
        keyword_results: list[SearchHit] = []
        semantic_results: list[SearchHit] = []
        if mode in {SearchMode.KEYWORD, SearchMode.HYBRID}:
            keyword_results = await self._repository.keyword_search(
                organization_id=organization_id, query=query, filters=filters, limit=limit
            )
        semantic_available = self._semantic_client is not None
        if mode in {SearchMode.SEMANTIC, SearchMode.HYBRID} and self._semantic_client is not None:
            try:
                semantic_candidates = await self._semantic_client.search(
                    organization_id=organization_id, query=query, filters=filters, limit=limit * 3
                )
                semantic_scores = dict(semantic_candidates)
                semantic_results = await self._repository.documents_by_ids(
                    organization_id=organization_id,
                    document_ids=tuple(document_id for document_id, _ in semantic_candidates),
                    filters=filters,
                )
                semantic_results = [
                    replace(hit, score=semantic_scores[hit.document_id]) for hit in semantic_results
                ]
            except SemanticSearchError:
                if mode is SearchMode.SEMANTIC:
                    raise SearchUnavailableError("Semantic search backend is unavailable") from None
                semantic_available = False
        elif mode is SearchMode.SEMANTIC:
            raise SearchUnavailableError("Semantic search is not configured")

        if mode is SearchMode.KEYWORD:
            return SearchResponse(
                results=tuple(keyword_results), semantic_available=semantic_available
            )
        if mode is SearchMode.SEMANTIC:
            return SearchResponse(results=tuple(semantic_results[:limit]), semantic_available=True)
        results = self._fuse(keyword_results, semantic_results, limit=limit)
        if filters.newest_first:
            results.sort(key=lambda hit: hit.published_at or date.min, reverse=True)
        return SearchResponse(
            results=tuple(results),
            semantic_available=semantic_available,
        )

    @staticmethod
    def _fuse(
        keyword_results: list[SearchHit], semantic_results: list[SearchHit], *, limit: int
    ) -> list[SearchHit]:
        fused_scores: defaultdict[UUID, float] = defaultdict(float)
        hits: dict[UUID, SearchHit] = {}
        for rank, hit in enumerate(keyword_results, start=1):
            fused_scores[hit.document_id] += 1 / (60 + rank)
            hits[hit.document_id] = hit
        for rank, hit in enumerate(semantic_results, start=1):
            fused_scores[hit.document_id] += 1 / (60 + rank)
            hits.setdefault(hit.document_id, hit)
        return [
            replace(hits[document_id], score=score, match_kind="hybrid")
            for document_id, score in sorted(
                fused_scores.items(), key=lambda item: item[1], reverse=True
            )[:limit]
        ]
