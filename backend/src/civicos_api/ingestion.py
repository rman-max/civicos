"""Founder-admin controls and read models for durable ingestion operations."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row


class IngestionControlError(RuntimeError):
    """Raised for a safe, user-actionable ingestion-control rejection."""


class PostgresIngestionRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url.replace("postgresql+psycopg://", "postgresql://", 1)

    async def enqueue(
        self, *, organization_id: UUID, user_id: UUID, source_id: UUID | None, cooldown_seconds: int
    ) -> dict[str, Any]:
        async with self._transaction(organization_id, user_id) as connection:
            cursor = await connection.execute(
                """SELECT requested_at FROM civic.ingestion_runs
                WHERE organization_id = %s AND request_kind = 'founder_refresh'
                ORDER BY requested_at DESC LIMIT 1""",
                (organization_id,),
            )
            last = await cursor.fetchone()
            if last and last["requested_at"] > datetime.now(last["requested_at"].tzinfo) - timedelta(
                seconds=cooldown_seconds
            ):
                raise IngestionControlError(
                    "A source refresh was requested recently. Please wait before trying again."
                )
            source_clause = "AND id = %s" if source_id else ""
            cursor = await connection.execute(
                f"SELECT id FROM civic.sources WHERE organization_id = %s AND is_active {source_clause} "
                "ORDER BY id",
                (organization_id, source_id) if source_id else (organization_id,),
            )
            source_rows = await cursor.fetchall()
            if not source_rows:
                raise IngestionControlError("No enabled connector matches this refresh request.")
            source_ids = [row["id"] for row in source_rows]
            cursor = await connection.execute(
                """SELECT source_id FROM civic.ingestion_run_sources
                WHERE organization_id = %s AND source_id = ANY(%s::uuid[])
                  AND status IN ('queued', 'running')""",
                (organization_id, source_ids),
            )
            if await cursor.fetchone():
                raise IngestionControlError(
                    "One or more requested sources are already being refreshed."
                )
            cursor = await connection.execute(
                """INSERT INTO civic.ingestion_runs
                (organization_id, requested_by_user_id, request_kind)
                VALUES (%s, %s, 'founder_refresh') RETURNING id""",
                (organization_id, user_id),
            )
            run = await cursor.fetchone()
            if run is None:
                raise IngestionControlError("Could not queue the source refresh.")
            run_id = UUID(str(run["id"]))
            await connection.execute(
                """INSERT INTO civic.ingestion_run_sources
                (ingestion_run_id, organization_id, source_id)
                SELECT %s, %s, unnest(%s::uuid[])""",
                (run_id, organization_id, source_ids),
            )
            await connection.execute(
                """UPDATE civic.discovery_jobs SET run_after = LEAST(run_after, now())
                WHERE organization_id = %s AND source_id = ANY(%s::uuid[])
                  AND (leased_until IS NULL OR leased_until < now())""",
                (organization_id, source_ids),
            )
            return await self._run_payload(connection, run_id)

    async def run(self, *, organization_id: UUID, user_id: UUID, run_id: UUID) -> dict[str, Any]:
        async with self._transaction(organization_id, user_id) as connection:
            return await self._run_payload(connection, run_id)

    async def status(
        self, *, organization_id: UUID, user_id: UUID, semantic_available: bool
    ) -> dict[str, Any]:
        async with self._transaction(organization_id, user_id) as connection:
            document_cursor = await connection.execute(
                """SELECT count(*) AS document_count, max(updated_at) AS last_corpus_update
                FROM civic.documents WHERE organization_id = %s""",
                (organization_id,),
            )
            documents = await document_cursor.fetchone()
            heartbeat_cursor = await connection.execute(
                "SELECT max(last_seen_at) AS worker_heartbeat FROM civic.worker_heartbeats"
            )
            heartbeat = await heartbeat_cursor.fetchone()
            connector_cursor = await connection.execute(
                """SELECT source.id, source.name, job.run_after AS next_expected_run,
                  latest.status AS last_status, latest.completed_at AS last_completed_at,
                  latest.error_message
                FROM civic.sources AS source
                LEFT JOIN civic.discovery_jobs AS job
                  ON job.organization_id = source.organization_id AND job.source_id = source.id
                LEFT JOIN LATERAL (
                  SELECT status, completed_at, error_message FROM civic.source_scan_runs
                  WHERE organization_id = source.organization_id AND source_id = source.id
                  ORDER BY started_at DESC LIMIT 1
                ) AS latest ON true
                WHERE source.organization_id = %s AND source.is_active ORDER BY source.name""",
                (organization_id,),
            )
            connectors = [dict(row) for row in await connector_cursor.fetchall()]
            return {
                "worker_heartbeat": heartbeat["worker_heartbeat"] if heartbeat else None,
                "last_scheduled_run": max(
                    (row["last_completed_at"] for row in connectors if row["last_completed_at"]),
                    default=None,
                ),
                "document_count": int(documents["document_count"] if documents else 0),
                "last_corpus_update": documents["last_corpus_update"] if documents else None,
                "failed_connector_count": sum(row["last_status"] == "failed" for row in connectors),
                "indexing_mode": "semantic" if semantic_available else "keyword",
                "connectors": connectors,
            }

    async def _run_payload(
        self, connection: psycopg.AsyncConnection[dict[str, Any]], run_id: UUID
    ) -> dict[str, Any]:
        cursor = await connection.execute(
            """SELECT id, status, request_kind, requested_at, started_at, completed_at,
            error_message
            FROM civic.ingestion_runs WHERE id = %s""", (run_id,)
        )
        run = await cursor.fetchone()
        if run is None:
            raise IngestionControlError("The ingestion run was not found.")
        cursor = await connection.execute(
            """SELECT source_id, status, pages_crawled, documents_discovered, documents_changed,
              documents_skipped, documents_indexed, error_message, started_at, completed_at
            FROM civic.ingestion_run_sources
            WHERE ingestion_run_id = %s ORDER BY source_id""",
            (run_id,),
        )
        return {**dict(run), "sources": [dict(row) for row in await cursor.fetchall()]}

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
                await connection.execute("SELECT set_config('app.user_id', %s, true)", (str(user_id),))
                yield connection
