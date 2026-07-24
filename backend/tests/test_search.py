import asyncio
from datetime import date
from uuid import UUID

from civicos_api.search import (
    HybridSearchService,
    SearchFilters,
    SearchHit,
    SearchMode,
    SearchUnavailableError,
)

ORGANIZATION_ID = UUID("00000000-0000-0000-0000-000000000001")
DOCUMENT_ONE = UUID("00000000-0000-0000-0000-000000000010")
DOCUMENT_TWO = UUID("00000000-0000-0000-0000-000000000020")


def make_hit(document_id: UUID, score: float, match_kind: str = "keyword") -> SearchHit:
    return SearchHit(
        document_id=document_id,
        document_version_id=UUID("00000000-0000-0000-0000-000000000030"),
        title=f"Document {document_id}",
        document_type="report",
        source_name="Official records",
        canonical_url="https://example.test/record",
        department_id=None,
        published_at=date(2026, 1, 1),
        excerpt="Excerpt",
        score=score,
        match_kind=match_kind,
    )


class FakeRepository:
    async def keyword_search(self, **_: object) -> list[SearchHit]:
        return [make_hit(DOCUMENT_ONE, 0.9), make_hit(DOCUMENT_TWO, 0.4)]

    async def documents_by_ids(
        self, *, document_ids: tuple[UUID, ...], **_: object
    ) -> list[SearchHit]:
        return [make_hit(document_id, 0, "semantic") for document_id in document_ids]


class FakeSemanticClient:
    async def search(self, **_: object) -> list[tuple[UUID, float]]:
        return [(DOCUMENT_TWO, 0.95), (DOCUMENT_ONE, 0.80)]


def test_hybrid_search_fuses_keyword_and_semantic_results() -> None:
    service = HybridSearchService(repository=FakeRepository(), semantic_client=FakeSemanticClient())

    response = asyncio.run(
        service.search(
            organization_id=ORGANIZATION_ID,
            query="river restoration",
            filters=SearchFilters(),
            mode=SearchMode.HYBRID,
            limit=10,
        )
    )

    assert response.semantic_available
    assert [result.document_id for result in response.results] == [DOCUMENT_ONE, DOCUMENT_TWO]
    assert all(result.match_kind == "hybrid" for result in response.results)


def test_semantic_mode_requires_configured_semantic_client() -> None:
    service = HybridSearchService(repository=FakeRepository(), semantic_client=None)

    try:
        asyncio.run(
            service.search(
                organization_id=ORGANIZATION_ID,
                query="river restoration",
                filters=SearchFilters(),
                mode=SearchMode.SEMANTIC,
                limit=10,
            )
        )
    except SearchUnavailableError:
        return
    raise AssertionError("Expected semantic search to require a configured semantic client")
