import asyncio
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

import pytest

from civicos_api.assistant import AnswerClaim, Evidence
from civicos_api.notebooks import (
    NotebookEntry,
    NotebookEvidence,
    NotebookGroundingError,
    NotebookSnapshot,
    ResearchNotebookService,
)

ORGANIZATION_ID = UUID("00000000-0000-0000-0000-000000000001")
USER_ID = UUID("00000000-0000-0000-0000-000000000002")
NOTEBOOK_ID = UUID("00000000-0000-0000-0000-000000000003")
DOCUMENT_ONE = UUID("00000000-0000-0000-0000-000000000010")
DOCUMENT_TWO = UUID("00000000-0000-0000-0000-000000000020")


def make_evidence(document_id: UUID, published_at: date) -> NotebookEvidence:
    return NotebookEvidence(
        document_id=document_id,
        document_version_id=UUID("00000000-0000-0000-0000-000000000030"),
        title=f"Document {document_id}",
        document_type="report",
        source_name="Official records",
        source_url="https://example.test/record",
        published_at=published_at,
        excerpt="The record describes a documented civic action.",
        citation_id=None,
    )


class FakeRepository:
    def __init__(self, evidence: tuple[NotebookEvidence, ...]) -> None:
        self._evidence = evidence
        self.generated: list[dict[str, object]] = []

    async def evidence(self, **_: object) -> tuple[NotebookEvidence, ...]:
        return self._evidence

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
        self.generated.append(
            {
                "organization_id": organization_id,
                "user_id": user_id,
                "notebook_id": notebook_id,
                "entry_type": entry_type,
                "title": title,
                "body_markdown": body_markdown,
                "structured_content": structured_content,
                "evidence": evidence,
            }
        )
        now = datetime(2026, 1, 1, tzinfo=UTC)
        return NotebookEntry(
            id=UUID("00000000-0000-0000-0000-000000000040"),
            position=1,
            entry_type=entry_type,
            title=title,
            body_markdown=body_markdown,
            structured_content=structured_content,
            created_at=now,
            updated_at=now,
        )

    async def snapshot(
        self, *, organization_id: UUID, user_id: UUID, notebook_id: UUID
    ) -> NotebookSnapshot:
        del organization_id, user_id, notebook_id
        raise AssertionError("Snapshot is not used by these tests")


class FakeAnswerClient:
    def __init__(self, claims: tuple[AnswerClaim, ...]) -> None:
        self._claims = claims

    async def generate_claims(
        self, *, question: str, evidence: tuple[Evidence, ...], max_claims: int
    ) -> tuple[AnswerClaim, ...]:
        del question, evidence, max_claims
        return self._claims


def test_summary_keeps_only_the_evidence_it_cites() -> None:
    first = make_evidence(DOCUMENT_ONE, date(2025, 1, 1))
    second = make_evidence(DOCUMENT_TWO, date(2026, 1, 1))
    repository = FakeRepository((first, second))
    service = ResearchNotebookService(
        repository=repository,
        answer_client=FakeAnswerClient(
            (AnswerClaim(text="A supported finding.", citation_ids=("C2",)),)
        ),
        max_claims=5,
    )

    entry = asyncio.run(
        service.generate_summary(
            organization_id=ORGANIZATION_ID,
            user_id=USER_ID,
            notebook_id=NOTEBOOK_ID,
            focus=None,
        )
    )

    assert entry.entry_type == "summary"
    assert entry.body_markdown == "A supported finding. [C2]"
    assert repository.generated[0]["evidence"] == (second,)


def test_summary_rejects_a_citation_outside_notebook_evidence() -> None:
    repository = FakeRepository((make_evidence(DOCUMENT_ONE, date(2026, 1, 1)),))
    service = ResearchNotebookService(
        repository=repository,
        answer_client=FakeAnswerClient(
            (AnswerClaim(text="Unsupported finding.", citation_ids=("C9",)),)
        ),
        max_claims=5,
    )

    with pytest.raises(NotebookGroundingError):
        asyncio.run(
            service.generate_summary(
                organization_id=ORGANIZATION_ID,
                user_id=USER_ID,
                notebook_id=NOTEBOOK_ID,
                focus=None,
            )
        )


def test_timeline_sorts_saved_evidence_by_publication_date() -> None:
    first = make_evidence(DOCUMENT_ONE, date(2026, 2, 1))
    second = make_evidence(DOCUMENT_TWO, date(2025, 4, 1))
    repository = FakeRepository((first, second))
    service = ResearchNotebookService(repository=repository, answer_client=None, max_claims=5)

    entry = asyncio.run(
        service.create_timeline(
            organization_id=ORGANIZATION_ID,
            user_id=USER_ID,
            notebook_id=NOTEBOOK_ID,
        )
    )

    assert entry.entry_type == "timeline"
    assert entry.structured_content["events"][0]["document_id"] == str(DOCUMENT_TWO)
