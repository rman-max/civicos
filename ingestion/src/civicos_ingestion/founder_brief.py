"""Durable daily founder brief generation from ranked, source-linked opportunities."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Protocol
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from civicos_ingestion.models import FounderBriefJob

logger = logging.getLogger(__name__)


class FounderBriefRepository(Protocol):
    async def enqueue_for_date(self, briefing_date: date) -> int: ...

    async def claim_due_jobs(self, *, limit: int) -> list[FounderBriefJob]: ...

    async def collect_content(self, *, job: FounderBriefJob, minimum_score: int, limit: int) -> dict[str, Any]: ...

    async def complete_job(self, *, job: FounderBriefJob, content: dict[str, Any]) -> None: ...

    async def fail_job(self, *, job: FounderBriefJob, error: str) -> None: ...


class PostgresFounderBriefRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url.replace("postgresql+psycopg://", "postgresql://", 1)

    async def enqueue_for_date(self, briefing_date: date) -> int:
        async with await self._connection() as connection:
            cursor = await connection.execute("SELECT founder.enqueue_daily_brief_jobs(%s)", (briefing_date,))
            row = await cursor.fetchone()
        if row is None:
            raise RuntimeError("Could not enqueue founder brief jobs")
        return int(row["enqueue_daily_brief_jobs"])

    async def claim_due_jobs(self, *, limit: int) -> list[FounderBriefJob]:
        async with await self._connection() as connection:
            cursor = await connection.execute("SELECT * FROM founder.claim_daily_brief_jobs(%s)", (limit,))
            rows = await cursor.fetchall()
        return [
            FounderBriefJob(
                id=row["job_id"],
                lease_token=row["lease_token"],
                organization_id=row["organization_id"],
                briefing_date=row["briefing_date"],
            )
            for row in rows
        ]

    async def collect_content(
        self, *, job: FounderBriefJob, minimum_score: int, limit: int
    ) -> dict[str, Any]:
        day_after = job.briefing_date + timedelta(days=1)
        async with await self._connection() as connection, connection.transaction():
            await self._set_organization(connection, job.organization_id)
            cursor = await connection.execute(
                """
                SELECT opportunity.id, signal.signal_type, signal.title, opportunity.what_happened,
                  opportunity.why_it_matters, opportunity.where_money_may_be, opportunity.who_might_pay,
                  opportunity.action_to_take, opportunity.urgency, opportunity.score, signal.evidence,
                  signal.affected_organizations, signal.discovered_at
                FROM founder.opportunities AS opportunity
                JOIN founder.signals AS signal
                  ON signal.organization_id = opportunity.organization_id AND signal.id = opportunity.signal_id
                WHERE opportunity.organization_id = %s AND opportunity.status = 'open'
                  AND opportunity.score >= %s
                  AND signal.discovered_at >= %s AND signal.discovered_at < %s
                ORDER BY opportunity.score DESC, signal.discovered_at DESC
                LIMIT %s
                """,
                (job.organization_id, minimum_score, job.briefing_date, day_after, limit),
            )
            rows = await cursor.fetchall()
        opportunities = [self._serialize_row(row) for row in rows]
        return {
            "briefing_date": job.briefing_date.isoformat(),
            "question": "What changed in this jurisdiction that could create economic opportunity?",
            "high_value_opportunities": opportunities,
            "methodology": {
                "minimum_score": minimum_score,
                "selection": "Only new, active opportunities at or above the configured score threshold are included.",
                "caveat": (
                    "Commercial implications are hypotheses derived from cited civic records and "
                    "require founder review."
                ),
            },
        }

    async def complete_job(self, *, job: FounderBriefJob, content: dict[str, Any]) -> None:
        async with await self._connection() as connection, connection.transaction():
            await self._set_organization(connection, job.organization_id)
            await connection.execute(
                """
                INSERT INTO founder.daily_briefs (organization_id, briefing_date, content)
                VALUES (%s, %s, %s)
                ON CONFLICT (organization_id, briefing_date)
                DO UPDATE SET content = EXCLUDED.content, generated_at = now(), updated_at = now()
                """,
                (job.organization_id, job.briefing_date, Jsonb(content)),
            )
            cursor = await connection.execute(
                """
                UPDATE founder.daily_brief_jobs SET status = 'completed', lease_token = NULL, leased_until = NULL,
                  last_error = NULL
                WHERE organization_id = %s AND id = %s AND lease_token = %s AND status = 'processing'
                """,
                (job.organization_id, job.id, job.lease_token),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("Founder brief job lease was lost")

    async def fail_job(self, *, job: FounderBriefJob, error: str) -> None:
        async with await self._connection() as connection, connection.transaction():
            await self._set_organization(connection, job.organization_id)
            await connection.execute(
                """
                UPDATE founder.daily_brief_jobs SET status = 'failed', lease_token = NULL, leased_until = NULL,
                  last_error = left(%s, 2000),
                  run_after = now() + make_interval(secs => LEAST(3600, power(2, attempt_count)::integer))
                WHERE organization_id = %s AND id = %s AND lease_token = %s AND status = 'processing'
                """,
                (error, job.organization_id, job.id, job.lease_token),
            )

    @staticmethod
    def _serialize_row(row: dict[str, Any]) -> dict[str, Any]:
        return {
            key: value.isoformat() if isinstance(value, date) else value
            for key, value in row.items()
        }

    @staticmethod
    async def _set_organization(
        connection: psycopg.AsyncConnection[dict[str, Any]], organization_id: UUID
    ) -> None:
        await connection.execute("SELECT set_config('app.organization_id', %s, true)", (str(organization_id),))

    async def _connection(self) -> psycopg.AsyncConnection[dict[str, Any]]:
        return await psycopg.AsyncConnection.connect(self._database_url, row_factory=dict_row)


class FounderBriefService:
    def __init__(self, *, repository: FounderBriefRepository, minimum_score: int, section_limit: int) -> None:
        self._repository = repository
        self._minimum_score = minimum_score
        self._section_limit = section_limit

    async def run_due_jobs(self, *, briefing_date: date, limit: int = 10) -> int:
        await self._repository.enqueue_for_date(briefing_date)
        jobs = await self._repository.claim_due_jobs(limit=limit)
        for job in jobs:
            try:
                content = await self._repository.collect_content(
                    job=job, minimum_score=self._minimum_score, limit=self._section_limit
                )
                await self._repository.complete_job(job=job, content=content)
            except Exception as error:
                logger.exception("Founder brief generation failed", extra={"organization_id": str(job.organization_id)})
                await self._repository.fail_job(job=job, error=str(error))
        return len(jobs)
