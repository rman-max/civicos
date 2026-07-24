from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Protocol
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from civicos_ingestion.models import DailyBriefingJob

logger = logging.getLogger(__name__)


class BriefingRepository(Protocol):
    async def enqueue_for_date(self, briefing_date: date) -> int: ...

    async def claim_due_jobs(self, *, limit: int) -> list[DailyBriefingJob]: ...

    async def collect_content(
        self, *, job: DailyBriefingJob, near_term_days: int, lookahead_days: int, limit: int
    ) -> dict[str, Any]: ...

    async def complete_job(self, *, job: DailyBriefingJob, content: dict[str, Any]) -> None: ...

    async def fail_job(self, *, job: DailyBriefingJob, error: str) -> None: ...


class PostgresBriefingRepository:
    """Durable, tenant-scoped daily briefing jobs and extractive civic activity queries."""

    def __init__(self, database_url: str) -> None:
        self._database_url = database_url.replace("postgresql+psycopg://", "postgresql://", 1)

    async def enqueue_for_date(self, briefing_date: date) -> int:
        async with await self._connection() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute("SELECT civic.enqueue_daily_briefing_jobs(%s)", (briefing_date,))
                row = await cursor.fetchone()
        if row is None:
            raise RuntimeError("Could not enqueue daily briefing jobs")
        return int(row["enqueue_daily_briefing_jobs"])

    async def claim_due_jobs(self, *, limit: int) -> list[DailyBriefingJob]:
        async with await self._connection() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute("SELECT * FROM civic.claim_daily_briefing_jobs(%s)", (limit,))
                rows = await cursor.fetchall()
        return [
            DailyBriefingJob(
                id=row["job_id"],
                lease_token=row["lease_token"],
                organization_id=row["organization_id"],
                briefing_date=row["briefing_date"],
            )
            for row in rows
        ]

    async def collect_content(
        self, *, job: DailyBriefingJob, near_term_days: int, lookahead_days: int, limit: int
    ) -> dict[str, Any]:
        day_after = job.briefing_date + timedelta(days=1)
        near_term_end = job.briefing_date + timedelta(days=near_term_days)
        lookahead_end = job.briefing_date + timedelta(days=lookahead_days)
        async with await self._connection() as connection, connection.transaction():
            await self._set_organization(connection, job.organization_id)
            new_documents = await self._rows(
                connection,
                """
                SELECT document.id, document.title, document.document_type,
                  coalesce(document.canonical_url, source.canonical_url) AS source_url,
                  document.published_at::date AS published_at, document.first_observed_at
                FROM civic.documents AS document
                LEFT JOIN civic.sources AS source
                  ON source.organization_id = document.organization_id AND source.id = document.source_id
                WHERE document.organization_id = %s
                  AND document.first_observed_at >= %s AND document.first_observed_at < %s
                ORDER BY document.first_observed_at DESC, document.id
                LIMIT %s
                """,
                (job.organization_id, job.briefing_date, day_after, limit),
            )
            important_meetings = await self._rows(
                connection,
                """
                SELECT id, title, meeting_type, status, scheduled_start_at,
                  coalesce(external_url, '') AS source_url
                FROM civic.meetings
                WHERE organization_id = %s
                  AND scheduled_start_at >= %s AND scheduled_start_at < %s
                ORDER BY scheduled_start_at, id
                LIMIT %s
                """,
                (job.organization_id, job.briefing_date, near_term_end, limit),
            )
            policy_changes = await self._rows(
                connection,
                """
                SELECT id, ordinance_number, title, status, adopted_at, updated_at
                FROM civic.ordinances
                WHERE organization_id = %s AND updated_at >= %s AND updated_at < %s
                ORDER BY updated_at DESC, id
                LIMIT %s
                """,
                (job.organization_id, job.briefing_date, day_after, limit),
            )
            budget_changes = await self._rows(
                connection,
                """
                SELECT DISTINCT budget.id, budget.name, budget.fiscal_year, budget.status, budget.updated_at
                FROM civic.budgets AS budget
                LEFT JOIN civic.budget_lines AS line
                  ON line.organization_id = budget.organization_id AND line.budget_id = budget.id
                WHERE budget.organization_id = %s
                  AND (
                    (budget.updated_at >= %s AND budget.updated_at < %s)
                    OR (line.updated_at >= %s AND line.updated_at < %s)
                  )
                ORDER BY budget.updated_at DESC, budget.id
                LIMIT %s
                """,
                (
                    job.organization_id,
                    job.briefing_date,
                    day_after,
                    job.briefing_date,
                    day_after,
                    limit,
                ),
            )
            trending_topics = await self._rows(
                connection,
                """
                SELECT topic.id, topic.name, count(*) AS assignment_count
                FROM civic.topic_assignments AS assignment
                JOIN civic.topics AS topic
                  ON topic.organization_id = assignment.organization_id AND topic.id = assignment.topic_id
                WHERE assignment.organization_id = %s
                  AND assignment.created_at >= %s AND assignment.created_at < %s
                GROUP BY topic.id, topic.name
                ORDER BY assignment_count DESC, topic.name
                LIMIT %s
                """,
                (job.organization_id, job.briefing_date, day_after, limit),
            )
            upcoming_events = await self._rows(
                connection,
                """
                SELECT id, title, meeting_type, status, scheduled_start_at,
                  coalesce(external_url, '') AS source_url
                FROM civic.meetings
                WHERE organization_id = %s
                  AND scheduled_start_at >= %s AND scheduled_start_at < %s
                ORDER BY scheduled_start_at, id
                LIMIT %s
                """,
                (job.organization_id, near_term_end, lookahead_end, limit),
            )
        return {
            "briefing_date": job.briefing_date.isoformat(),
            "sections": {
                "new_documents": self._serialize_rows(new_documents),
                "important_meetings": self._serialize_rows(important_meetings),
                "policy_changes": self._serialize_rows(policy_changes),
                "budget_changes": self._serialize_rows(budget_changes),
                "trending_topics": self._serialize_rows(trending_topics),
                "upcoming_events": self._serialize_rows(upcoming_events),
            },
        }

    async def complete_job(self, *, job: DailyBriefingJob, content: dict[str, Any]) -> None:
        async with await self._connection() as connection, connection.transaction():
            await self._set_organization(connection, job.organization_id)
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    INSERT INTO research.daily_briefings (organization_id, briefing_date, content)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (organization_id, briefing_date)
                    DO UPDATE SET content = EXCLUDED.content, generated_at = now()
                    RETURNING id
                    """,
                    (job.organization_id, job.briefing_date, Jsonb(content)),
                )
                briefing = await cursor.fetchone()
                if briefing is None:
                    raise RuntimeError("Could not persist daily briefing")
                await cursor.execute(
                    """
                    INSERT INTO research.daily_briefing_deliveries (organization_id, briefing_id, subscription_id)
                    SELECT %s, %s, subscription.id
                    FROM research.briefing_subscriptions AS subscription
                    WHERE subscription.organization_id = %s AND subscription.is_active
                    ON CONFLICT (organization_id, briefing_id, subscription_id) DO NOTHING
                    """,
                    (job.organization_id, briefing["id"], job.organization_id),
                )
                await cursor.execute(
                    """
                    UPDATE civic.daily_briefing_jobs
                    SET status = 'completed', lease_token = NULL, leased_until = NULL, last_error = NULL
                    WHERE organization_id = %s AND id = %s AND lease_token = %s AND status = 'processing'
                    """,
                    (job.organization_id, job.id, job.lease_token),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("Daily briefing job lease was lost")

    async def fail_job(self, *, job: DailyBriefingJob, error: str) -> None:
        async with await self._connection() as connection, connection.transaction():
            await self._set_organization(connection, job.organization_id)
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    UPDATE civic.daily_briefing_jobs
                    SET status = 'failed', lease_token = NULL, leased_until = NULL, last_error = left(%s, 2000),
                      run_after = now() + make_interval(secs => LEAST(3600, power(2, attempt_count)::integer))
                    WHERE organization_id = %s AND id = %s AND lease_token = %s AND status = 'processing'
                    """,
                    (error, job.organization_id, job.id, job.lease_token),
                )

    async def _rows(
        self, connection: psycopg.AsyncConnection[dict[str, Any]], sql: str, parameters: tuple[object, ...]
    ) -> list[dict[str, Any]]:
        async with connection.cursor() as cursor:
            await cursor.execute(sql, parameters)
            return await cursor.fetchall()

    @staticmethod
    def _serialize_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {key: str(value) if isinstance(value, date | UUID) else value for key, value in row.items()} for row in rows
        ]

    @staticmethod
    async def _set_organization(connection: psycopg.AsyncConnection[dict[str, Any]], organization_id: object) -> None:
        await connection.execute("SELECT set_config('app.organization_id', %s, true)", (str(organization_id),))

    async def _connection(self) -> psycopg.AsyncConnection[dict[str, Any]]:
        return await psycopg.AsyncConnection.connect(self._database_url, row_factory=dict_row)


class DailyBriefingService:
    def __init__(
        self,
        *,
        repository: BriefingRepository,
        near_term_days: int,
        lookahead_days: int,
        section_limit: int,
    ) -> None:
        self._repository = repository
        self._near_term_days = near_term_days
        self._lookahead_days = lookahead_days
        self._section_limit = section_limit

    async def run_due_jobs(self, *, briefing_date: date, limit: int = 10) -> int:
        await self._repository.enqueue_for_date(briefing_date)
        jobs = await self._repository.claim_due_jobs(limit=limit)
        for job in jobs:
            try:
                content = await self._repository.collect_content(
                    job=job,
                    near_term_days=self._near_term_days,
                    lookahead_days=self._lookahead_days,
                    limit=self._section_limit,
                )
                await self._repository.complete_job(job=job, content=content)
            except Exception as error:
                logger.exception(
                    "Daily briefing generation failed", extra={"organization_id": str(job.organization_id)}
                )
                await self._repository.fail_job(job=job, error=str(error))
        return len(jobs)
