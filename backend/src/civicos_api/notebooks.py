from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Any, Protocol
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from civicos_api.assistant import (
    AnswerClaim,
    AnswerClient,
    AnswerGenerationUnavailableError,
    Evidence,
    InvalidAnswerDraftError,
)
from civicos_api.search import SearchHit


class ResearchAccessError(PermissionError):
    """Raised when a user is not an active member of the requested organization."""


class ResearchNotFoundError(LookupError):
    """Raised when an owned notebook or civic record is not visible to the caller."""


class NotebookGroundingError(ValueError):
    """Raised when a generated notebook summary cannot be tied to notebook evidence."""


@dataclass(frozen=True)
class Notebook:
    id: UUID
    title: str
    description: str | None
    visibility: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class NotebookEntry:
    id: UUID
    position: int
    entry_type: str
    title: str | None
    body_markdown: str | None
    structured_content: dict[str, Any]
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class SavedSearch:
    id: UUID
    title: str
    query_text: str
    filters: dict[str, Any]
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class SavedDocument:
    document_id: UUID
    document_version_id: UUID | None
    title: str
    document_type: str
    source_name: str | None
    source_url: str | None
    published_at: date | None
    note: str | None
    saved_at: datetime


@dataclass(frozen=True)
class SourceReference:
    citation_id: UUID
    notebook_entry_id: UUID
    document_id: UUID
    document_version_id: UUID
    title: str
    source_name: str | None
    source_url: str | None
    published_at: date | None
    excerpt: str | None
    locator: dict[str, Any]
    note: str | None


@dataclass(frozen=True)
class NotebookSnapshot:
    notebook: Notebook
    entries: tuple[NotebookEntry, ...]
    saved_searches: tuple[SavedSearch, ...]
    saved_documents: tuple[SavedDocument, ...]
    source_references: tuple[SourceReference, ...]


@dataclass(frozen=True)
class NotebookEvidence:
    document_id: UUID
    document_version_id: UUID
    title: str
    document_type: str
    source_name: str | None
    source_url: str | None
    published_at: date | None
    excerpt: str
    citation_id: UUID | None


class NotebookServiceRepository(Protocol):
    async def evidence(
        self, *, organization_id: UUID, user_id: UUID, notebook_id: UUID
    ) -> tuple[NotebookEvidence, ...]: ...

    async def add_generated_entry(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
        notebook_id: UUID,
        entry_type: str,
        title: str,
        body_markdown: str,
        structured_content: dict[str, Any],
        evidence: tuple[NotebookEvidence, ...],
    ) -> NotebookEntry: ...

    async def snapshot(
        self, *, organization_id: UUID, user_id: UUID, notebook_id: UUID
    ) -> NotebookSnapshot: ...


class PostgresNotebookRepository:
    """Persistence for user-owned research notebooks and source-version citations."""

    def __init__(self, database_url: str) -> None:
        self._database_url = database_url.replace("postgresql+psycopg://", "postgresql://", 1)

    async def create_notebook(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
        title: str,
        description: str | None,
        visibility: str,
    ) -> Notebook:
        async with self._transaction(organization_id, user_id) as connection:
            cursor = await connection.execute(
                """
                INSERT INTO research.notebooks (organization_id, owner_user_id, title, description, visibility)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, title, description, visibility, created_at, updated_at
                """,
                (organization_id, user_id, title, description, visibility),
            )
            return self._notebook_from_row(await self._one(cursor, "Could not create notebook"))

    async def list_notebooks(self, *, organization_id: UUID, user_id: UUID) -> list[Notebook]:
        async with self._transaction(organization_id, user_id) as connection:
            cursor = await connection.execute(
                """
                SELECT id, title, description, visibility, created_at, updated_at
                FROM research.notebooks
                WHERE organization_id = %s AND owner_user_id = %s
                ORDER BY updated_at DESC, id
                """,
                (organization_id, user_id),
            )
            return [self._notebook_from_row(row) for row in await cursor.fetchall()]

    async def snapshot(
        self, *, organization_id: UUID, user_id: UUID, notebook_id: UUID
    ) -> NotebookSnapshot:
        async with self._transaction(organization_id, user_id) as connection:
            notebook = await self._owned_notebook(connection, organization_id, user_id, notebook_id)
            entries_cursor = await connection.execute(
                """
                SELECT id, position, entry_type, title, body_markdown, structured_content, created_at, updated_at
                FROM research.notebook_entries
                WHERE organization_id = %s AND notebook_id = %s
                ORDER BY position, id
                """,
                (organization_id, notebook_id),
            )
            searches_cursor = await connection.execute(
                """
                SELECT id, title, query_text, filters, created_at, updated_at
                FROM research.saved_searches
                WHERE organization_id = %s AND notebook_id = %s
                ORDER BY updated_at DESC, id
                """,
                (organization_id, notebook_id),
            )
            documents_cursor = await connection.execute(
                """
                WITH latest_versions AS (
                  SELECT DISTINCT ON (organization_id, document_id)
                    organization_id, document_id, id
                  FROM civic.document_versions
                  WHERE organization_id = %s
                  ORDER BY organization_id, document_id, version_number DESC
                )
                SELECT document.id AS document_id, version.id AS document_version_id, document.title,
                  document.document_type, source.name AS source_name,
                  coalesce(document.canonical_url, source.canonical_url) AS source_url,
                  document.published_at::date AS published_at, saved.note, saved.created_at AS saved_at
                FROM research.notebook_documents AS saved
                JOIN civic.documents AS document
                  ON document.organization_id = saved.organization_id AND document.id = saved.document_id
                LEFT JOIN latest_versions AS version
                  ON version.organization_id = document.organization_id AND version.document_id = document.id
                LEFT JOIN civic.sources AS source
                  ON source.organization_id = document.organization_id AND source.id = document.source_id
                WHERE saved.organization_id = %s AND saved.notebook_id = %s
                ORDER BY saved.created_at DESC, document.id
                """,
                (organization_id, organization_id, notebook_id),
            )
            references_cursor = await connection.execute(
                """
                SELECT citation.id AS citation_id, relation.notebook_entry_id, document.id AS document_id,
                  version.id AS document_version_id, document.title, source.name AS source_name,
                  coalesce(document.canonical_url, source.canonical_url) AS source_url,
                  document.published_at::date AS published_at, citation.excerpt, citation.locator, relation.note
                FROM research.notebook_citations AS relation
                JOIN civic.citations AS citation
                  ON citation.organization_id = relation.organization_id AND citation.id = relation.citation_id
                JOIN civic.document_versions AS version
                  ON version.organization_id = citation.organization_id AND version.id = citation.document_version_id
                JOIN civic.documents AS document
                  ON document.organization_id = version.organization_id AND document.id = version.document_id
                LEFT JOIN civic.sources AS source
                  ON source.organization_id = document.organization_id AND source.id = document.source_id
                WHERE relation.organization_id = %s
                  AND relation.notebook_entry_id IN (
                    SELECT id FROM research.notebook_entries
                    WHERE organization_id = %s AND notebook_id = %s
                  )
                ORDER BY relation.notebook_entry_id, citation.created_at, citation.id
                """,
                (organization_id, organization_id, notebook_id),
            )
            return NotebookSnapshot(
                notebook=notebook,
                entries=tuple(self._entry_from_row(row) for row in await entries_cursor.fetchall()),
                saved_searches=tuple(
                    self._search_from_row(row) for row in await searches_cursor.fetchall()
                ),
                saved_documents=tuple(
                    self._document_from_row(row) for row in await documents_cursor.fetchall()
                ),
                source_references=tuple(
                    self._reference_from_row(row) for row in await references_cursor.fetchall()
                ),
            )

    async def save_search(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
        notebook_id: UUID,
        title: str,
        query_text: str,
        filters: dict[str, Any],
    ) -> SavedSearch:
        async with self._transaction(organization_id, user_id) as connection:
            await self._owned_notebook(connection, organization_id, user_id, notebook_id)
            cursor = await connection.execute(
                """
                INSERT INTO research.saved_searches
                  (organization_id, owner_user_id, notebook_id, title, query_text, filters)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id, title, query_text, filters, created_at, updated_at
                """,
                (organization_id, user_id, notebook_id, title, query_text, Jsonb(filters)),
            )
            return self._search_from_row(await self._one(cursor, "Could not save search"))

    async def save_document(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
        notebook_id: UUID,
        document_id: UUID,
        note: str | None,
    ) -> SavedDocument:
        async with self._transaction(organization_id, user_id) as connection:
            await self._owned_notebook(connection, organization_id, user_id, notebook_id)
            document_cursor = await connection.execute(
                "SELECT id FROM civic.documents WHERE organization_id = %s AND id = %s",
                (organization_id, document_id),
            )
            await self._one(document_cursor, "Document was not found")
            await connection.execute(
                """
                INSERT INTO research.notebook_documents
                  (organization_id, notebook_id, document_id, saved_by_user_id, note)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (organization_id, notebook_id, document_id)
                DO UPDATE SET note = EXCLUDED.note, saved_by_user_id = EXCLUDED.saved_by_user_id
                """,
                (organization_id, notebook_id, document_id, user_id, note),
            )
            return await self._saved_document(connection, organization_id, notebook_id, document_id)

    async def add_note(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
        notebook_id: UUID,
        title: str | None,
        body_markdown: str,
    ) -> NotebookEntry:
        async with self._transaction(organization_id, user_id) as connection:
            await self._owned_notebook(connection, organization_id, user_id, notebook_id, lock=True)
            return await self._insert_entry(
                connection,
                organization_id=organization_id,
                user_id=user_id,
                notebook_id=notebook_id,
                entry_type="note",
                title=title,
                body_markdown=body_markdown,
                structured_content={},
            )

    async def add_highlight(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
        notebook_id: UUID,
        document_version_id: UUID,
        excerpt: str,
        start_offset: int | None,
        end_offset: int | None,
        note: str | None,
    ) -> NotebookEntry:
        async with self._transaction(organization_id, user_id) as connection:
            await self._owned_notebook(connection, organization_id, user_id, notebook_id, lock=True)
            version_cursor = await connection.execute(
                """
                SELECT version.id, version.document_id
                FROM civic.document_versions AS version
                WHERE version.organization_id = %s AND version.id = %s
                """,
                (organization_id, document_version_id),
            )
            version = await self._one(version_cursor, "Document version was not found")
            citation_cursor = await connection.execute(
                """
                INSERT INTO civic.citations
                  (organization_id, document_version_id, citation_kind, locator, excerpt, start_offset, end_offset, created_by_user_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    organization_id,
                    document_version_id,
                    "highlight",
                    Jsonb({"document_id": str(version["document_id"])}),
                    excerpt,
                    start_offset,
                    end_offset,
                    user_id,
                ),
            )
            citation = await self._one(citation_cursor, "Could not create highlight citation")
            entry = await self._insert_entry(
                connection,
                organization_id=organization_id,
                user_id=user_id,
                notebook_id=notebook_id,
                entry_type="highlight",
                title="Highlight",
                body_markdown=note,
                structured_content={
                    "document_version_id": str(document_version_id),
                    "excerpt": excerpt,
                },
            )
            await connection.execute(
                """
                INSERT INTO research.notebook_citations (organization_id, notebook_entry_id, citation_id, note)
                VALUES (%s, %s, %s, %s)
                """,
                (organization_id, entry.id, citation["id"], note),
            )
            return entry

    async def evidence(
        self, *, organization_id: UUID, user_id: UUID, notebook_id: UUID
    ) -> tuple[NotebookEvidence, ...]:
        async with self._transaction(organization_id, user_id) as connection:
            await self._owned_notebook(connection, organization_id, user_id, notebook_id)
            cursor = await connection.execute(
                """
                WITH latest_versions AS (
                  SELECT DISTINCT ON (organization_id, document_id)
                    organization_id, document_id, id, extracted_text
                  FROM civic.document_versions
                  WHERE organization_id = %s
                  ORDER BY organization_id, document_id, version_number DESC
                ), evidence AS (
                  SELECT document.id AS document_id, version.id AS document_version_id, document.title,
                    document.document_type, source.name AS source_name,
                    coalesce(document.canonical_url, source.canonical_url) AS source_url,
                    document.published_at::date AS published_at,
                    left(coalesce(version.extracted_text, ''), 900) AS excerpt,
                    NULL::uuid AS citation_id
                  FROM research.notebook_documents AS saved
                  JOIN civic.documents AS document
                    ON document.organization_id = saved.organization_id AND document.id = saved.document_id
                  JOIN latest_versions AS version
                    ON version.organization_id = document.organization_id AND version.document_id = document.id
                  LEFT JOIN civic.sources AS source
                    ON source.organization_id = document.organization_id AND source.id = document.source_id
                  WHERE saved.organization_id = %s AND saved.notebook_id = %s
                  UNION ALL
                  SELECT document.id, version.id, document.title, document.document_type, source.name,
                    coalesce(document.canonical_url, source.canonical_url), document.published_at::date,
                    coalesce(citation.excerpt, left(coalesce(version.extracted_text, ''), 900)), citation.id
                  FROM research.notebook_citations AS relation
                  JOIN civic.citations AS citation
                    ON citation.organization_id = relation.organization_id AND citation.id = relation.citation_id
                  JOIN civic.document_versions AS version
                    ON version.organization_id = citation.organization_id AND version.id = citation.document_version_id
                  JOIN civic.documents AS document
                    ON document.organization_id = version.organization_id AND document.id = version.document_id
                  LEFT JOIN civic.sources AS source
                    ON source.organization_id = document.organization_id AND source.id = document.source_id
                  WHERE relation.organization_id = %s
                    AND relation.notebook_entry_id IN (
                      SELECT id FROM research.notebook_entries
                      WHERE organization_id = %s AND notebook_id = %s
                    )
                )
                SELECT * FROM evidence WHERE length(trim(excerpt)) > 0
                """,
                (
                    organization_id,
                    organization_id,
                    notebook_id,
                    organization_id,
                    organization_id,
                    notebook_id,
                ),
            )
            seen: set[tuple[UUID, UUID, UUID | None, str]] = set()
            result: list[NotebookEvidence] = []
            for row in await cursor.fetchall():
                evidence = self._evidence_from_row(row)
                key = (
                    evidence.document_id,
                    evidence.document_version_id,
                    evidence.citation_id,
                    evidence.excerpt,
                )
                if key not in seen:
                    seen.add(key)
                    result.append(evidence)
            return tuple(result)

    async def add_generated_entry(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
        notebook_id: UUID,
        entry_type: str,
        title: str,
        body_markdown: str,
        structured_content: dict[str, Any],
        evidence: tuple[NotebookEvidence, ...],
    ) -> NotebookEntry:
        async with self._transaction(organization_id, user_id) as connection:
            await self._owned_notebook(connection, organization_id, user_id, notebook_id, lock=True)
            entry = await self._insert_entry(
                connection,
                organization_id=organization_id,
                user_id=user_id,
                notebook_id=notebook_id,
                entry_type=entry_type,
                title=title,
                body_markdown=body_markdown,
                structured_content=structured_content,
            )
            for item in evidence:
                citation_id = item.citation_id or await self._create_reference_citation(
                    connection, organization_id=organization_id, user_id=user_id, evidence=item
                )
                await connection.execute(
                    """
                    INSERT INTO research.notebook_citations (organization_id, notebook_entry_id, citation_id)
                    VALUES (%s, %s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (organization_id, entry.id, citation_id),
                )
            return entry

    async def _saved_document(
        self,
        connection: psycopg.AsyncConnection[dict[str, Any]],
        organization_id: UUID,
        notebook_id: UUID,
        document_id: UUID,
    ) -> SavedDocument:
        cursor = await connection.execute(
            """
            WITH latest_versions AS (
              SELECT DISTINCT ON (organization_id, document_id) organization_id, document_id, id
              FROM civic.document_versions
              WHERE organization_id = %s
              ORDER BY organization_id, document_id, version_number DESC
            )
            SELECT document.id AS document_id, version.id AS document_version_id, document.title,
              document.document_type, source.name AS source_name,
              coalesce(document.canonical_url, source.canonical_url) AS source_url,
              document.published_at::date AS published_at, saved.note, saved.created_at AS saved_at
            FROM research.notebook_documents AS saved
            JOIN civic.documents AS document
              ON document.organization_id = saved.organization_id AND document.id = saved.document_id
            LEFT JOIN latest_versions AS version
              ON version.organization_id = document.organization_id AND version.document_id = document.id
            LEFT JOIN civic.sources AS source
              ON source.organization_id = document.organization_id AND source.id = document.source_id
            WHERE saved.organization_id = %s AND saved.notebook_id = %s AND saved.document_id = %s
            """,
            (organization_id, organization_id, notebook_id, document_id),
        )
        return self._document_from_row(await self._one(cursor, "Saved document was not found"))

    async def _insert_entry(
        self,
        connection: psycopg.AsyncConnection[dict[str, Any]],
        *,
        organization_id: UUID,
        user_id: UUID,
        notebook_id: UUID,
        entry_type: str,
        title: str | None,
        body_markdown: str | None,
        structured_content: dict[str, Any],
    ) -> NotebookEntry:
        position_cursor = await connection.execute(
            """
            SELECT coalesce(max(position), 0) + 1 AS position
            FROM research.notebook_entries
            WHERE organization_id = %s AND notebook_id = %s
            """,
            (organization_id, notebook_id),
        )
        position = int(
            (await self._one(position_cursor, "Could not determine entry position"))["position"]
        )
        entry_cursor = await connection.execute(
            """
            INSERT INTO research.notebook_entries
              (organization_id, notebook_id, position, entry_type, title, body_markdown, structured_content, created_by_user_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, position, entry_type, title, body_markdown, structured_content, created_at, updated_at
            """,
            (
                organization_id,
                notebook_id,
                position,
                entry_type,
                title,
                body_markdown,
                Jsonb(structured_content),
                user_id,
            ),
        )
        return self._entry_from_row(
            await self._one(entry_cursor, "Could not create notebook entry")
        )

    async def _create_reference_citation(
        self,
        connection: psycopg.AsyncConnection[dict[str, Any]],
        *,
        organization_id: UUID,
        user_id: UUID,
        evidence: NotebookEvidence,
    ) -> UUID:
        cursor = await connection.execute(
            """
            INSERT INTO civic.citations
              (organization_id, document_version_id, citation_kind, locator, excerpt, created_by_user_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                organization_id,
                evidence.document_version_id,
                "notebook_reference",
                Jsonb({"generated_from": "research_notebook"}),
                evidence.excerpt,
                user_id,
            ),
        )
        return UUID(str((await self._one(cursor, "Could not create source reference"))["id"]))

    async def _owned_notebook(
        self,
        connection: psycopg.AsyncConnection[dict[str, Any]],
        organization_id: UUID,
        user_id: UUID,
        notebook_id: UUID,
        *,
        lock: bool = False,
    ) -> Notebook:
        cursor = await connection.execute(
            f"""
            SELECT id, title, description, visibility, created_at, updated_at
            FROM research.notebooks
            WHERE organization_id = %s AND owner_user_id = %s AND id = %s
            {"FOR UPDATE" if lock else ""}
            """,
            (organization_id, user_id, notebook_id),
        )
        return self._notebook_from_row(await self._one(cursor, "Notebook was not found"))

    @asynccontextmanager
    async def _transaction(
        self, organization_id: UUID, user_id: UUID
    ) -> AsyncIterator[psycopg.AsyncConnection[dict[str, Any]]]:
        async with await psycopg.AsyncConnection.connect(
            self._database_url, row_factory=dict_row
        ) as connection:
            async with connection.transaction():
                await connection.execute(
                    "SELECT set_config('app.organization_id', %s, true)", (str(organization_id),)
                )
                await connection.execute(
                    "SELECT set_config('app.user_id', %s, true)", (str(user_id),)
                )
                membership_cursor = await connection.execute(
                    """
                    SELECT 1
                    FROM core.organization_memberships AS membership
                    JOIN core.users AS member ON member.id = membership.user_id
                    WHERE membership.organization_id = %s AND membership.user_id = %s AND member.is_active
                    """,
                    (organization_id, user_id),
                )
                if await membership_cursor.fetchone() is None:
                    raise ResearchAccessError("User is not an active organization member")
                yield connection

    @staticmethod
    async def _one(cursor: psycopg.AsyncCursor[dict[str, Any]], message: str) -> dict[str, Any]:
        row = await cursor.fetchone()
        if row is None:
            raise ResearchNotFoundError(message)
        return row

    @staticmethod
    def _notebook_from_row(row: dict[str, Any]) -> Notebook:
        return Notebook(
            id=UUID(str(row["id"])),
            title=str(row["title"]),
            description=str(row["description"]) if row["description"] else None,
            visibility=str(row["visibility"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _entry_from_row(row: dict[str, Any]) -> NotebookEntry:
        return NotebookEntry(
            id=UUID(str(row["id"])),
            position=int(row["position"]),
            entry_type=str(row["entry_type"]),
            title=str(row["title"]) if row["title"] else None,
            body_markdown=str(row["body_markdown"]) if row["body_markdown"] else None,
            structured_content=dict(row["structured_content"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _search_from_row(row: dict[str, Any]) -> SavedSearch:
        return SavedSearch(
            id=UUID(str(row["id"])),
            title=str(row["title"]),
            query_text=str(row["query_text"]),
            filters=dict(row["filters"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _document_from_row(row: dict[str, Any]) -> SavedDocument:
        return SavedDocument(
            document_id=UUID(str(row["document_id"])),
            document_version_id=UUID(str(row["document_version_id"]))
            if row["document_version_id"]
            else None,
            title=str(row["title"]),
            document_type=str(row["document_type"]),
            source_name=str(row["source_name"]) if row["source_name"] else None,
            source_url=str(row["source_url"]) if row["source_url"] else None,
            published_at=row["published_at"],
            note=str(row["note"]) if row["note"] else None,
            saved_at=row["saved_at"],
        )

    @staticmethod
    def _reference_from_row(row: dict[str, Any]) -> SourceReference:
        return SourceReference(
            citation_id=UUID(str(row["citation_id"])),
            notebook_entry_id=UUID(str(row["notebook_entry_id"])),
            document_id=UUID(str(row["document_id"])),
            document_version_id=UUID(str(row["document_version_id"])),
            title=str(row["title"]),
            source_name=str(row["source_name"]) if row["source_name"] else None,
            source_url=str(row["source_url"]) if row["source_url"] else None,
            published_at=row["published_at"],
            excerpt=str(row["excerpt"]) if row["excerpt"] else None,
            locator=dict(row["locator"]),
            note=str(row["note"]) if row["note"] else None,
        )

    @staticmethod
    def _evidence_from_row(row: dict[str, Any]) -> NotebookEvidence:
        return NotebookEvidence(
            document_id=UUID(str(row["document_id"])),
            document_version_id=UUID(str(row["document_version_id"])),
            title=str(row["title"]),
            document_type=str(row["document_type"]),
            source_name=str(row["source_name"]) if row["source_name"] else None,
            source_url=str(row["source_url"]) if row["source_url"] else None,
            published_at=row["published_at"],
            excerpt=str(row["excerpt"]),
            citation_id=UUID(str(row["citation_id"])) if row["citation_id"] else None,
        )


class ResearchNotebookService:
    """Notebook-specific synthesis, timeline construction, and export rendering."""

    def __init__(
        self,
        *,
        repository: NotebookServiceRepository,
        answer_client: AnswerClient | None,
        max_claims: int,
    ) -> None:
        self._repository = repository
        self._answer_client = answer_client
        self._max_claims = max_claims

    async def generate_summary(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
        notebook_id: UUID,
        focus: str | None,
    ) -> NotebookEntry:
        if self._answer_client is None:
            raise AnswerGenerationUnavailableError("Grounded assistant is not configured")
        evidence = await self._repository.evidence(
            organization_id=organization_id, user_id=user_id, notebook_id=notebook_id
        )
        if not evidence:
            raise NotebookGroundingError(
                "The notebook has no document-grounded evidence to summarize"
            )
        prompt_evidence = tuple(
            Evidence(
                citation_id=f"C{index}",
                hit=SearchHit(
                    document_id=item.document_id,
                    document_version_id=item.document_version_id,
                    title=item.title,
                    document_type=item.document_type,
                    source_name=item.source_name,
                    canonical_url=item.source_url,
                    department_id=None,
                    published_at=item.published_at,
                    excerpt=item.excerpt,
                    score=0.0,
                    match_kind="notebook",
                ),
            )
            for index, item in enumerate(evidence, start=1)
        )
        question = (
            "Summarize the saved notebook evidence using only directly supported civic facts."
        )
        if focus:
            question = f"{question} Focus on: {focus}"
        try:
            claims = await self._answer_client.generate_claims(
                question=question, evidence=prompt_evidence, max_claims=self._max_claims
            )
        except InvalidAnswerDraftError as error:
            raise NotebookGroundingError(
                "The summary provider returned an invalid citation draft"
            ) from error
        used_evidence = self._claims_evidence(claims, evidence)
        body = "\n\n".join(
            f"{claim.text} {' '.join(f'[{citation_id}]' for citation_id in claim.citation_ids)}"
            for claim in claims
        )
        return await self._repository.add_generated_entry(
            organization_id=organization_id,
            user_id=user_id,
            notebook_id=notebook_id,
            entry_type="summary",
            title="Generated summary",
            body_markdown=body,
            structured_content={"generation": "grounded_assistant", "focus": focus},
            evidence=used_evidence,
        )

    async def create_timeline(
        self, *, organization_id: UUID, user_id: UUID, notebook_id: UUID
    ) -> NotebookEntry:
        evidence = await self._repository.evidence(
            organization_id=organization_id, user_id=user_id, notebook_id=notebook_id
        )
        dated = tuple(item for item in evidence if item.published_at is not None)
        if not dated:
            raise NotebookGroundingError(
                "The notebook has no dated document evidence for a timeline"
            )
        unique: dict[UUID, NotebookEvidence] = {}
        for item in dated:
            unique.setdefault(item.document_id, item)
        timeline = tuple(sorted(unique.values(), key=lambda item: (item.published_at, item.title)))
        events = [
            {
                "date": item.published_at.isoformat() if item.published_at else None,
                "title": item.title,
                "document_id": str(item.document_id),
                "document_version_id": str(item.document_version_id),
            }
            for item in timeline
        ]
        body = "\n".join(
            f"- {item.published_at.isoformat()}: {item.title}"
            for item in timeline
            if item.published_at
        )
        return await self._repository.add_generated_entry(
            organization_id=organization_id,
            user_id=user_id,
            notebook_id=notebook_id,
            entry_type="timeline",
            title="Evidence timeline",
            body_markdown=body,
            structured_content={"events": events},
            evidence=timeline,
        )

    async def export(
        self, *, organization_id: UUID, user_id: UUID, notebook_id: UUID, format: str
    ) -> tuple[str, str]:
        snapshot = await self._repository.snapshot(
            organization_id=organization_id, user_id=user_id, notebook_id=notebook_id
        )
        if format == "json":
            return "application/json", json.dumps(
                self._snapshot_payload(snapshot), indent=2, default=str
            )
        return "text/markdown; charset=utf-8", self._markdown(snapshot)

    def _claims_evidence(
        self, claims: tuple[AnswerClaim, ...], evidence: tuple[NotebookEvidence, ...]
    ) -> tuple[NotebookEvidence, ...]:
        if not claims or len(claims) > self._max_claims:
            raise NotebookGroundingError("The generated summary did not contain valid cited claims")
        evidence_by_id = {f"C{index}": item for index, item in enumerate(evidence, start=1)}
        used: list[NotebookEvidence] = []
        seen: set[str] = set()
        for claim in claims:
            if not claim.text.strip() or not claim.citation_ids:
                raise NotebookGroundingError("The generated summary included an uncited claim")
            for citation_id in claim.citation_ids:
                item = evidence_by_id.get(citation_id)
                if item is None:
                    raise NotebookGroundingError(
                        "The generated summary cited evidence outside this notebook"
                    )
                if citation_id not in seen:
                    seen.add(citation_id)
                    used.append(item)
        return tuple(used)

    @staticmethod
    def _snapshot_payload(snapshot: NotebookSnapshot) -> dict[str, Any]:
        return {
            "notebook": asdict(snapshot.notebook),
            "entries": [asdict(entry) for entry in snapshot.entries],
            "saved_searches": [asdict(search) for search in snapshot.saved_searches],
            "saved_documents": [asdict(document) for document in snapshot.saved_documents],
            "source_references": [asdict(reference) for reference in snapshot.source_references],
        }

    @staticmethod
    def _markdown(snapshot: NotebookSnapshot) -> str:
        lines = [f"# {snapshot.notebook.title}", ""]
        if snapshot.notebook.description:
            lines.extend([snapshot.notebook.description, ""])
        lines.extend(["## Saved searches", ""])
        for search in snapshot.saved_searches:
            lines.append(f"- **{search.title}** — `{search.query_text}`")
        lines.extend(["", "## Saved documents", ""])
        for document in snapshot.saved_documents:
            source = document.source_url or "Source URL unavailable"
            lines.append(f"- [{document.title}]({source})")
        lines.extend(["", "## Notes and research", ""])
        for entry in snapshot.entries:
            lines.append(f"### {entry.title or entry.entry_type.title()}")
            if entry.body_markdown:
                lines.extend([entry.body_markdown, ""])
        lines.extend(["## Source references", ""])
        for reference in snapshot.source_references:
            source = reference.source_url or "Source URL unavailable"
            lines.append(f"- [{reference.title}]({source}) — citation `{reference.citation_id}`")
            if reference.excerpt:
                lines.append(f"  - {reference.excerpt}")
        return "\n".join(lines).rstrip() + "\n"
