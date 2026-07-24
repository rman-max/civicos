import asyncio
from datetime import date
from uuid import UUID

from civicos_ingestion.briefing import DailyBriefingService
from civicos_ingestion.models import DailyBriefingJob

ORGANIZATION_ID = UUID("00000000-0000-0000-0000-000000000001")
JOB_ID = UUID("00000000-0000-0000-0000-000000000002")
LEASE_TOKEN = UUID("00000000-0000-0000-0000-000000000003")
BRIEFING_DATE = date(2026, 7, 24)


class FakeBriefingRepository:
    def __init__(self) -> None:
        self.enqueued_for: date | None = None
        self.completed_content: dict[str, object] | None = None
        self.failed_error: str | None = None

    async def enqueue_for_date(self, briefing_date: date) -> int:
        self.enqueued_for = briefing_date
        return 1

    async def claim_due_jobs(self, *, limit: int) -> list[DailyBriefingJob]:
        assert limit == 10
        return [
            DailyBriefingJob(
                id=JOB_ID,
                lease_token=LEASE_TOKEN,
                organization_id=ORGANIZATION_ID,
                briefing_date=BRIEFING_DATE,
            )
        ]

    async def collect_content(self, **_: object) -> dict[str, object]:
        return {"briefing_date": BRIEFING_DATE.isoformat(), "sections": {"new_documents": []}}

    async def complete_job(self, *, job: DailyBriefingJob, content: dict[str, object]) -> None:
        assert job.id == JOB_ID
        self.completed_content = content

    async def fail_job(self, *, job: DailyBriefingJob, error: str) -> None:
        assert job.id == JOB_ID
        self.failed_error = error


class FailingBriefingRepository(FakeBriefingRepository):
    async def collect_content(self, **_: object) -> dict[str, object]:
        raise RuntimeError("database query failed")


def test_daily_briefing_service_enqueues_and_completes_due_work() -> None:
    repository = FakeBriefingRepository()
    service = DailyBriefingService(repository=repository, near_term_days=7, lookahead_days=14, section_limit=10)

    claimed = asyncio.run(service.run_due_jobs(briefing_date=BRIEFING_DATE))

    assert claimed == 1
    assert repository.enqueued_for == BRIEFING_DATE
    assert repository.completed_content == {
        "briefing_date": "2026-07-24",
        "sections": {"new_documents": []},
    }
    assert repository.failed_error is None


def test_daily_briefing_service_retries_failed_generation() -> None:
    repository = FailingBriefingRepository()
    service = DailyBriefingService(repository=repository, near_term_days=7, lookahead_days=14, section_limit=10)

    claimed = asyncio.run(service.run_due_jobs(briefing_date=BRIEFING_DATE))

    assert claimed == 1
    assert repository.completed_content is None
    assert repository.failed_error == "database query failed"
