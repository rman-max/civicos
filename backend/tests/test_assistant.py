import asyncio
from datetime import date
from uuid import UUID

from civicos_api.assistant import (
    AnswerClaim,
    AnswerStatus,
    AssistantPolicy,
    GroundedAnswerService,
    InvalidAnswerDraftError,
)
from civicos_api.search import SearchFilters, SearchHit, SearchResponse

ORGANIZATION_ID = UUID("00000000-0000-0000-0000-000000000001")
DOCUMENT_ONE = UUID("00000000-0000-0000-0000-000000000010")
DOCUMENT_TWO = UUID("00000000-0000-0000-0000-000000000020")


def make_hit(document_id: UUID, source_name: str) -> SearchHit:
    return SearchHit(
        document_id=document_id,
        document_version_id=UUID("00000000-0000-0000-0000-000000000030"),
        title=f"Document {document_id}",
        document_type="meeting_minutes",
        source_name=source_name,
        canonical_url=f"https://example.test/{document_id}",
        department_id=None,
        published_at=date(2026, 1, 1),
        excerpt="The county approved housing-related funding and directed staff to report back.",
        score=0.9,
        match_kind="hybrid",
    )


class FakeRetriever:
    def __init__(self, results: tuple[SearchHit, ...]) -> None:
        self._results = results

    async def search(self, **_: object) -> SearchResponse:
        return SearchResponse(results=self._results, semantic_available=True)


class FakeAnswerClient:
    def __init__(self, claims: tuple[AnswerClaim, ...]) -> None:
        self._claims = claims
        self.was_called = False

    async def generate_claims(self, **_: object) -> tuple[AnswerClaim, ...]:
        self.was_called = True
        return self._claims


class InvalidDraftClient:
    async def generate_claims(self, **_: object) -> tuple[AnswerClaim, ...]:
        raise InvalidAnswerDraftError("Malformed answer")


def make_policy() -> AssistantPolicy:
    return AssistantPolicy(
        retrieval_limit=8,
        max_claims=5,
        minimum_citations_per_claim=1,
        target_independent_sources=2,
        high_confidence_threshold=0.85,
        medium_confidence_threshold=0.6,
    )


def test_assistant_renders_only_claims_with_retrieved_citations() -> None:
    answer_client = FakeAnswerClient(
        (
            AnswerClaim(
                text="The county approved housing-related funding and requested a staff report.",
                citation_ids=("C1", "C2"),
            ),
        )
    )
    service = GroundedAnswerService(
        retriever=FakeRetriever(
            (make_hit(DOCUMENT_ONE, "County Council"), make_hit(DOCUMENT_TWO, "County Auditor"))
        ),
        answer_client=answer_client,
        policy=make_policy(),
    )

    response = asyncio.run(
        service.answer(
            organization_id=ORGANIZATION_ID,
            question="What has the county done about housing?",
            filters=SearchFilters(),
        )
    )

    assert response.status is AnswerStatus.ANSWERED
    assert response.answer.endswith("[C1] [C2]")
    assert [citation.citation_id for citation in response.citations] == ["C1", "C2"]
    assert response.confidence.score == 1.0


def test_assistant_declines_a_claim_with_an_unknown_citation() -> None:
    service = GroundedAnswerService(
        retriever=FakeRetriever((make_hit(DOCUMENT_ONE, "County Council"),)),
        answer_client=FakeAnswerClient(
            (AnswerClaim(text="An unsupported statement.", citation_ids=("C99",)),)
        ),
        policy=make_policy(),
    )

    response = asyncio.run(
        service.answer(
            organization_id=ORGANIZATION_ID,
            question="What happened?",
            filters=SearchFilters(),
        )
    )

    assert response.status is AnswerStatus.INSUFFICIENT_EVIDENCE
    assert not response.claims
    assert not response.citations


def test_assistant_declines_without_retrieved_evidence() -> None:
    answer_client = FakeAnswerClient(
        (AnswerClaim(text="Should not be used.", citation_ids=("C1",)),)
    )
    service = GroundedAnswerService(
        retriever=FakeRetriever(()), answer_client=answer_client, policy=make_policy()
    )

    response = asyncio.run(
        service.answer(
            organization_id=ORGANIZATION_ID,
            question="What happened?",
            filters=SearchFilters(),
        )
    )

    assert response.status is AnswerStatus.INSUFFICIENT_EVIDENCE
    assert not answer_client.was_called


def test_assistant_declines_an_invalid_provider_draft() -> None:
    service = GroundedAnswerService(
        retriever=FakeRetriever((make_hit(DOCUMENT_ONE, "County Council"),)),
        answer_client=InvalidDraftClient(),
        policy=make_policy(),
    )

    response = asyncio.run(
        service.answer(
            organization_id=ORGANIZATION_ID,
            question="What happened?",
            filters=SearchFilters(),
        )
    )

    assert response.status is AnswerStatus.INSUFFICIENT_EVIDENCE
    assert not response.claims
