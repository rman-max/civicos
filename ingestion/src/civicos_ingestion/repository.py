from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from civicos_ingestion.crawler import content_hash
from civicos_ingestion.founder_intelligence import opportunity_score
from civicos_ingestion.models import (
    DepartmentCandidate,
    DiscoveryJob,
    FetchedResource,
    GraphNodeCandidate,
    PersistedDocument,
    ProcessedDocument,
    ProcessingContext,
    Source,
    TopicCandidate,
    VectorIndexJob,
)


class DiscoveryRepository(Protocol):
    async def claim_due_jobs(self, *, limit: int) -> list[DiscoveryJob]: ...

    async def start_scan(self, job: DiscoveryJob) -> UUID: ...

    async def get_processing_context(self, job: DiscoveryJob) -> ProcessingContext: ...

    async def persist_resource(
        self,
        *,
        job: DiscoveryJob,
        scan_run_id: UUID,
        resource: FetchedResource,
        processed: ProcessedDocument,
        storage_key: str,
    ) -> PersistedDocument: ...

    async def complete_job(
        self,
        *,
        job: DiscoveryJob,
        scan_run_id: UUID,
        pages_crawled: int,
        documents_discovered: int,
        documents_changed: int,
        documents_skipped: int,
        documents_indexed: int,
    ) -> None: ...

    async def fail_job(self, *, job: DiscoveryJob, scan_run_id: UUID | None, error: str) -> None: ...

    async def heartbeat(self, worker_id: str) -> None: ...

    async def claim_vector_index_jobs(self, *, limit: int) -> list[VectorIndexJob]: ...

    async def complete_vector_index_job(self, job: VectorIndexJob) -> None: ...

    async def fail_vector_index_job(self, *, job: VectorIndexJob, error: str) -> None: ...


class PostgresDiscoveryRepository:
    """PostgreSQL adapter. The worker identity is an internal, non-public service account."""

    def __init__(self, database_url: str) -> None:
        self._database_url = database_url.replace("postgresql+psycopg://", "postgresql://", 1)

    async def claim_due_jobs(self, *, limit: int) -> list[DiscoveryJob]:
        async with await self._connection() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute("SELECT * FROM civic.claim_discovery_jobs(%s)", (limit,))
                rows = await cursor.fetchall()
        return [self._job_from_row(row) for row in rows]

    async def start_scan(self, job: DiscoveryJob) -> UUID:
        async with await self._connection() as connection, connection.transaction():
            await self._set_organization(connection, job.source.organization_id)
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    INSERT INTO civic.source_scan_runs (organization_id, source_id, status)
                    VALUES (%s, %s, 'running') RETURNING id
                    """,
                    (job.source.organization_id, job.source.id),
                )
                row = await cursor.fetchone()
                if row is None:
                    raise RuntimeError("Could not create a source scan run")
                await cursor.execute(
                    """UPDATE civic.ingestion_run_sources SET status = 'running', started_at = now(), scan_run_id = %s
                    WHERE organization_id = %s AND source_id = %s AND status = 'queued'""",
                    (row["id"], job.source.organization_id, job.source.id),
                )
                await cursor.execute(
                    """UPDATE civic.ingestion_runs AS run SET status = 'running', started_at = COALESCE(started_at, now())
                    WHERE run.organization_id = %s AND run.status = 'queued' AND EXISTS (
                      SELECT 1 FROM civic.ingestion_run_sources source
                      WHERE source.ingestion_run_id = run.id AND source.source_id = %s AND source.status = 'running'
                    )""",
                    (job.source.organization_id, job.source.id),
                )
        return UUID(str(row["id"]))

    async def get_processing_context(self, job: DiscoveryJob) -> ProcessingContext:
        async with await self._connection() as connection, connection.transaction():
            await self._set_organization(connection, job.source.organization_id)
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    SELECT id, name FROM core.departments
                    WHERE organization_id = %s AND is_active
                    ORDER BY name
                    """,
                    (job.source.organization_id,),
                )
                department_rows = await cursor.fetchall()
                await cursor.execute(
                    """
                    SELECT id, name FROM civic.topics
                    WHERE organization_id = %s AND is_active
                    ORDER BY name
                    """,
                    (job.source.organization_id,),
                )
                topic_rows = await cursor.fetchall()
                await cursor.execute(
                    """
                    SELECT id, node_type, name
                    FROM (
                      SELECT id, 'meeting'::text AS node_type, title AS name
                      FROM civic.meetings WHERE organization_id = %s
                      UNION ALL
                      SELECT id, 'ordinance'::text, ordinance_number FROM civic.ordinances
                      WHERE organization_id = %s
                      UNION ALL
                      SELECT id, 'ordinance'::text, title FROM civic.ordinances
                      WHERE organization_id = %s
                      UNION ALL
                      SELECT id, 'budget'::text, name FROM civic.budgets WHERE organization_id = %s
                      UNION ALL
                      SELECT id, 'project'::text, name FROM civic.projects WHERE organization_id = %s
                      UNION ALL
                      SELECT official.id, 'official'::text, entity.canonical_name
                      FROM civic.officials AS official
                      JOIN civic.entities AS entity
                        ON entity.organization_id = official.organization_id AND entity.id = official.entity_id
                      WHERE official.organization_id = %s AND official.is_active
                      UNION ALL
                      SELECT id, 'location'::text, name FROM civic.locations WHERE organization_id = %s
                    ) AS graph_nodes
                    WHERE length(trim(name)) >= 3
                    ORDER BY node_type, name
                    """,
                    (job.source.organization_id,) * 7,
                )
                graph_node_rows = await cursor.fetchall()
        return ProcessingContext(
            departments=tuple(
                DepartmentCandidate(id=UUID(str(row["id"])), name=str(row["name"])) for row in department_rows
            ),
            topics=tuple(TopicCandidate(id=UUID(str(row["id"])), name=str(row["name"])) for row in topic_rows),
            graph_nodes=tuple(
                GraphNodeCandidate(id=UUID(str(row["id"])), node_type=str(row["node_type"]), name=str(row["name"]))
                for row in graph_node_rows
            ),
        )

    async def persist_resource(
        self,
        *,
        job: DiscoveryJob,
        scan_run_id: UUID,
        resource: FetchedResource,
        processed: ProcessedDocument,
        storage_key: str,
    ) -> PersistedDocument:
        source = job.source
        checksum = content_hash(resource.body)
        async with await self._connection() as connection, connection.transaction():
            await self._set_organization(connection, source.organization_id)
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    INSERT INTO civic.documents (
                      organization_id, source_id, department_id, title, document_type, canonical_url, published_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (organization_id, canonical_url) WHERE canonical_url IS NOT NULL
                    DO UPDATE SET title = EXCLUDED.title, document_type = EXCLUDED.document_type,
                      source_id = EXCLUDED.source_id,
                      department_id = COALESCE(EXCLUDED.department_id, civic.documents.department_id),
                      published_at = COALESCE(EXCLUDED.published_at, civic.documents.published_at),
                      updated_at = now()
                    RETURNING id
                    """,
                    (
                        source.organization_id,
                        source.id,
                        processed.department_id,
                        processed.title,
                        processed.document_type,
                        resource.final_url,
                        processed.publication_date,
                    ),
                )
                document_row = await cursor.fetchone()
                if document_row is None:
                    raise RuntimeError("Could not resolve a discovered document")
                document_id = UUID(str(document_row["id"]))
                await cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (str(document_id),))
                await cursor.execute(
                    """
                    SELECT id, content_hash FROM civic.document_versions
                    WHERE organization_id = %s AND document_id = %s
                    ORDER BY version_number DESC LIMIT 1
                    """,
                    (source.organization_id, document_id),
                )
                latest_version = await cursor.fetchone()
                version_id: UUID | None = None
                changed = latest_version is None or latest_version["content_hash"] != checksum
                if changed:
                    await cursor.execute(
                        """
                        INSERT INTO civic.document_versions (
                          organization_id, document_id, version_number, content_hash, extracted_text,
                          extracted_metadata
                        ) VALUES (
                          %s, %s,
                          COALESCE((SELECT max(version_number) + 1 FROM civic.document_versions
                            WHERE organization_id = %s AND document_id = %s), 1),
                          %s, %s, %s::jsonb
                        ) RETURNING id
                        """,
                        (
                            source.organization_id,
                            document_id,
                            source.organization_id,
                            document_id,
                            checksum,
                            processed.cleaned_text,
                            Jsonb(processed.metadata),
                        ),
                    )
                    version_row = await cursor.fetchone()
                    if version_row is None:
                        raise RuntimeError("Could not create a document version")
                    version_id = UUID(str(version_row["id"]))
                    await cursor.execute(
                        """
                        INSERT INTO civic.document_artifacts (
                          organization_id, document_version_id, storage_key, media_type, byte_size, checksum
                        ) VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            source.organization_id,
                            version_id,
                            storage_key,
                            resource.media_type,
                            len(resource.body),
                            checksum,
                        ),
                    )
                    await self._persist_entities(
                        cursor=cursor,
                        organization_id=source.organization_id,
                        document_id=document_id,
                        document_version_id=version_id,
                        processed=processed,
                    )
                    await self._persist_topics(
                        cursor=cursor,
                        organization_id=source.organization_id,
                        document_id=document_id,
                        processed=processed,
                    )
                    await self._persist_graph_relationships(
                        cursor=cursor,
                        organization_id=source.organization_id,
                        document_id=document_id,
                        document_version_id=version_id,
                        processed=processed,
                    )
                    await self._persist_founder_intelligence(
                        cursor=cursor,
                        organization_id=source.organization_id,
                        document_id=document_id,
                        document_version_id=version_id,
                        source_url=resource.final_url,
                        processed=processed,
                    )
                else:
                    if latest_version is None:
                        raise RuntimeError("Latest document version disappeared during persistence")
                    version_id = UUID(str(latest_version["id"]))
                await cursor.execute(
                    """
                    INSERT INTO civic.source_observations (
                      organization_id, source_id, scan_run_id, document_id, document_version_id,
                      source_url, final_url, http_status, media_type, content_hash, etag, last_modified
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        source.organization_id,
                        source.id,
                        scan_run_id,
                        document_id,
                        version_id,
                        resource.source_url,
                        resource.final_url,
                        resource.status_code,
                        resource.media_type,
                        checksum,
                        resource.etag,
                        resource.last_modified,
                    ),
                )
        return PersistedDocument(document_id=document_id, version_id=version_id if changed else None, changed=changed)

    async def _persist_entities(
        self,
        *,
        cursor: psycopg.AsyncCursor[dict[str, Any]],
        organization_id: UUID,
        document_id: UUID,
        document_version_id: UUID,
        processed: ProcessedDocument,
    ) -> None:
        for entity in processed.entities:
            await cursor.execute(
                """
                INSERT INTO civic.entities (organization_id, entity_type, canonical_name)
                VALUES (%s, %s, %s)
                ON CONFLICT (organization_id, entity_type, canonical_name)
                DO UPDATE SET updated_at = now()
                RETURNING id
                """,
                (organization_id, entity.entity_type, entity.canonical_name),
            )
            entity_row = await cursor.fetchone()
            if entity_row is None:
                raise RuntimeError("Could not resolve extracted entity")
            entity_id = UUID(str(entity_row["id"]))
            await cursor.execute(
                """
                INSERT INTO civic.document_entity_mentions (
                  organization_id, document_version_id, entity_id, mention_text, start_offset, end_offset
                ) VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    organization_id,
                    document_version_id,
                    entity_id,
                    entity.mention_text,
                    entity.start_offset,
                    entity.end_offset,
                ),
            )
            if entity.official_title is not None:
                await self._persist_inferred_official(
                    cursor=cursor,
                    organization_id=organization_id,
                    document_id=document_id,
                    document_version_id=document_version_id,
                    entity_id=entity_id,
                    title=entity.official_title,
                    mention_text=entity.mention_text,
                    start_offset=entity.start_offset,
                    end_offset=entity.end_offset,
                )

    async def _persist_inferred_official(
        self,
        *,
        cursor: psycopg.AsyncCursor[dict[str, Any]],
        organization_id: UUID,
        document_id: UUID,
        document_version_id: UUID,
        entity_id: UUID,
        title: str,
        mention_text: str,
        start_offset: int,
        end_offset: int,
    ) -> None:
        await cursor.execute(
            """
            INSERT INTO civic.officials (organization_id, entity_id, title, metadata)
            VALUES (%s, %s, %s, %s::jsonb)
            ON CONFLICT (organization_id, entity_id, department_id, title, starts_on)
            DO UPDATE SET is_active = true, updated_at = now()
            RETURNING id
            """,
            (organization_id, entity_id, title, Jsonb({"discovery_method": "deterministic"})),
        )
        official_row = await cursor.fetchone()
        if official_row is None:
            raise RuntimeError("Could not resolve inferred official")
        await cursor.execute(
            """
            INSERT INTO civic.knowledge_graph_edges (
              organization_id, subject_type, subject_id, predicate, object_type, object_id,
              evidence_document_version_id, evidence_start_offset, evidence_end_offset,
              discovery_method, confidence, metadata
            ) VALUES (%s, 'document', %s, 'mentions_official', 'official', %s, %s, %s, %s,
              'deterministic', 0.800, %s::jsonb)
            ON CONFLICT DO NOTHING
            """,
            (
                organization_id,
                document_id,
                UUID(str(official_row["id"])),
                document_version_id,
                start_offset,
                end_offset,
                Jsonb({"mention_text": mention_text, "title": title}),
            ),
        )

    async def _persist_topics(
        self,
        *,
        cursor: psycopg.AsyncCursor[dict[str, Any]],
        organization_id: UUID,
        document_id: UUID,
        processed: ProcessedDocument,
    ) -> None:
        for topic_id in processed.topic_ids:
            await cursor.execute(
                """
                INSERT INTO civic.topic_assignments (organization_id, topic_id, document_id)
                SELECT %s, %s, %s
                WHERE NOT EXISTS (
                  SELECT 1 FROM civic.topic_assignments
                  WHERE organization_id = %s AND topic_id = %s AND document_id = %s
                )
                """,
                (organization_id, topic_id, document_id, organization_id, topic_id, document_id),
            )

    async def _persist_graph_relationships(
        self,
        *,
        cursor: psycopg.AsyncCursor[dict[str, Any]],
        organization_id: UUID,
        document_id: UUID,
        document_version_id: UUID,
        processed: ProcessedDocument,
    ) -> None:
        for relationship in processed.relationships:
            await cursor.execute(
                """
                INSERT INTO civic.knowledge_graph_edges (
                  organization_id, subject_type, subject_id, predicate, object_type, object_id,
                  evidence_document_version_id, evidence_start_offset, evidence_end_offset,
                  discovery_method, confidence, metadata
                ) VALUES (%s, 'document', %s, %s, %s, %s, %s, %s, %s, 'deterministic', %s, %s::jsonb)
                ON CONFLICT DO NOTHING
                """,
                (
                    organization_id,
                    document_id,
                    relationship.predicate,
                    relationship.object_type,
                    relationship.object_id,
                    document_version_id,
                    relationship.start_offset,
                    relationship.end_offset,
                    relationship.confidence,
                    Jsonb({"mention_text": relationship.mention_text}),
                ),
            )
            if relationship.object_type == "location":
                await cursor.execute(
                    """
                    INSERT INTO civic.document_location_mentions (
                      organization_id, document_version_id, location_id, mention_text, start_offset, end_offset
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (
                        organization_id,
                        document_version_id,
                        relationship.object_id,
                        relationship.mention_text,
                        relationship.start_offset,
                        relationship.end_offset,
                    ),
                )

    async def _persist_founder_intelligence(
        self,
        *,
        cursor: psycopg.AsyncCursor[dict[str, Any]],
        organization_id: UUID,
        document_id: UUID,
        document_version_id: UUID,
        source_url: str,
        processed: ProcessedDocument,
    ) -> None:
        """Persist deterministic signal candidates and their founder-ready views atomically."""

        for candidate in processed.founder_signals:
            evidence = [
                {
                    "document_id": str(document_id),
                    "document_version_id": str(document_version_id),
                    "source_url": source_url,
                    "excerpt": candidate.evidence_excerpt,
                    "start_offset": candidate.evidence_start_offset,
                    "end_offset": candidate.evidence_end_offset,
                }
            ]
            score = opportunity_score(candidate)
            await cursor.execute(
                """
                INSERT INTO founder.signals (
                  organization_id, document_id, document_version_id, signal_type, title, summary, why_it_matters,
                  economic_value_score, confidence_score, recency_score, urgency_score, evidence_strength_score,
                  actionability_score, commercial_significance, affected_organizations, potential_customer_segments,
                  evidence
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb)
                ON CONFLICT (organization_id, document_version_id, signal_type) DO UPDATE SET
                  title = EXCLUDED.title, summary = EXCLUDED.summary, why_it_matters = EXCLUDED.why_it_matters,
                  economic_value_score = EXCLUDED.economic_value_score, confidence_score = EXCLUDED.confidence_score,
                  recency_score = EXCLUDED.recency_score, urgency_score = EXCLUDED.urgency_score,
                  evidence_strength_score = EXCLUDED.evidence_strength_score,
                  actionability_score = EXCLUDED.actionability_score,
                  commercial_significance = EXCLUDED.commercial_significance,
                  affected_organizations = EXCLUDED.affected_organizations,
                  potential_customer_segments = EXCLUDED.potential_customer_segments, evidence = EXCLUDED.evidence,
                  status = 'active', updated_at = now()
                RETURNING id
                """,
                (
                    organization_id,
                    document_id,
                    document_version_id,
                    candidate.signal_type,
                    candidate.title,
                    candidate.summary,
                    candidate.why_it_matters,
                    candidate.economic_value_score,
                    candidate.confidence_score,
                    candidate.recency_score,
                    candidate.urgency_score,
                    candidate.evidence_strength_score,
                    candidate.actionability_score,
                    score,
                    Jsonb(list(candidate.affected_organizations)),
                    Jsonb(list(candidate.potential_customer_segments)),
                    Jsonb(evidence),
                ),
            )
            signal_row = await cursor.fetchone()
            if signal_row is None:
                raise RuntimeError("Could not persist founder intelligence signal")
            urgency = (
                "high" if candidate.urgency_score >= 0.8 else "medium" if candidate.urgency_score >= 0.6 else "low"
            )
            await cursor.execute(
                """
                INSERT INTO founder.opportunities (
                  organization_id, signal_id, what_happened, why_it_matters, where_money_may_be, who_might_pay,
                  action_to_take, urgency, score
                ) VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s)
                ON CONFLICT (organization_id, signal_id) DO UPDATE SET
                  what_happened = EXCLUDED.what_happened, why_it_matters = EXCLUDED.why_it_matters,
                  where_money_may_be = EXCLUDED.where_money_may_be, who_might_pay = EXCLUDED.who_might_pay,
                  action_to_take = EXCLUDED.action_to_take, urgency = EXCLUDED.urgency, score = EXCLUDED.score,
                  status = 'open', updated_at = now()
                """,
                (
                    organization_id,
                    UUID(str(signal_row["id"])),
                    candidate.summary,
                    candidate.why_it_matters,
                    candidate.where_money_may_be,
                    Jsonb(list(candidate.potential_customer_segments)),
                    candidate.action_to_take,
                    urgency,
                    score,
                ),
            )
            await self._persist_watchlist_matches(
                cursor=cursor,
                organization_id=organization_id,
                signal_id=UUID(str(signal_row["id"])),
                document_text=processed.cleaned_text,
            )

    async def _persist_watchlist_matches(
        self,
        *,
        cursor: psycopg.AsyncCursor[dict[str, Any]],
        organization_id: UUID,
        signal_id: UUID,
        document_text: str,
    ) -> None:
        """Match active watchlist terms as every new signal is persisted."""

        await cursor.execute(
            """
            INSERT INTO founder.watchlist_matches (organization_id, watchlist_id, signal_id, matched_term)
            SELECT %s, watchlist.id, %s, watchlist.normalized_term
            FROM founder.watchlists AS watchlist
            WHERE watchlist.organization_id = %s AND watchlist.is_active
              AND position(watchlist.normalized_term IN lower(%s)) > 0
            ON CONFLICT (organization_id, watchlist_id, signal_id) DO NOTHING
            """,
            (organization_id, signal_id, organization_id, document_text),
        )

    async def complete_job(
        self,
        *,
        job: DiscoveryJob,
        scan_run_id: UUID,
        pages_crawled: int,
        documents_discovered: int,
        documents_changed: int,
        documents_skipped: int,
        documents_indexed: int,
    ) -> None:
        async with await self._connection() as connection, connection.transaction():
            await self._set_organization(connection, job.source.organization_id)
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """UPDATE civic.source_scan_runs SET status = 'completed', completed_at = now(),
                    pages_crawled = %s, documents_discovered = %s, documents_changed = %s,
                    documents_skipped = %s, documents_indexed = %s
                    WHERE id = %s AND organization_id = %s""",
                    (pages_crawled, documents_discovered, documents_changed, documents_skipped,
                     documents_indexed, scan_run_id, job.source.organization_id),
                )
                await cursor.execute(
                    """UPDATE civic.ingestion_run_sources SET status = 'completed', completed_at = now(),
                    pages_crawled = %s, documents_discovered = %s, documents_changed = %s,
                    documents_skipped = %s, documents_indexed = %s
                    WHERE organization_id = %s AND source_id = %s AND scan_run_id = %s AND status = 'running'""",
                    (pages_crawled, documents_discovered, documents_changed, documents_skipped,
                     documents_indexed, job.source.organization_id, job.source.id, scan_run_id),
                )
                await self._complete_ingestion_runs(cursor, job.source.organization_id)
                await cursor.execute(
                    """UPDATE civic.discovery_jobs SET run_after = now() + make_interval(secs => %s),
                    lease_token = NULL, leased_until = NULL, last_error = NULL
                    WHERE id = %s AND organization_id = %s AND lease_token = %s""",
                    (job.source.scan_interval_seconds, job.id, job.source.organization_id, job.lease_token),
                )

    async def fail_job(self, *, job: DiscoveryJob, scan_run_id: UUID | None, error: str) -> None:
        async with await self._connection() as connection, connection.transaction():
            await self._set_organization(connection, job.source.organization_id)
            async with connection.cursor() as cursor:
                if scan_run_id is not None:
                    await cursor.execute(
                        """UPDATE civic.source_scan_runs SET status = 'failed', completed_at = now(),
                        error_message = %s WHERE id = %s AND organization_id = %s""",
                        (error[:4000], scan_run_id, job.source.organization_id),
                    )
                    await cursor.execute(
                        """UPDATE civic.ingestion_run_sources SET status = 'failed', completed_at = now(), error_message = %s
                        WHERE organization_id = %s AND source_id = %s AND scan_run_id = %s AND status = 'running'""",
                        (error[:4000], job.source.organization_id, job.source.id, scan_run_id),
                    )
                    await self._complete_ingestion_runs(cursor, job.source.organization_id)
                await cursor.execute(
                    """UPDATE civic.discovery_jobs SET run_after = now() + interval '60 seconds' *
                    LEAST(60, power(2, attempt_count)), lease_token = NULL, leased_until = NULL,
                    last_error = %s WHERE id = %s AND organization_id = %s AND lease_token = %s""",
                    (error[:4000], job.id, job.source.organization_id, job.lease_token),
                )

    async def heartbeat(self, worker_id: str) -> None:
        async with await self._connection() as connection:
            await connection.execute(
                """INSERT INTO civic.worker_heartbeats (worker_id, last_seen_at, last_scheduled_poll_at)
                VALUES (%s, now(), now())
                ON CONFLICT (worker_id) DO UPDATE SET last_seen_at = now(), last_scheduled_poll_at = now()""",
                (worker_id,),
            )

    async def _complete_ingestion_runs(
        self, cursor: psycopg.AsyncCursor[dict[str, Any]], organization_id: UUID
    ) -> None:
        await cursor.execute(
            """UPDATE civic.ingestion_runs AS run SET status = CASE
                  WHEN EXISTS (SELECT 1 FROM civic.ingestion_run_sources source
                    WHERE source.ingestion_run_id = run.id AND source.status = 'completed') THEN 'completed'
                  ELSE 'failed' END,
                completed_at = now()
              WHERE run.organization_id = %s AND run.status IN ('queued', 'running')
                AND NOT EXISTS (SELECT 1 FROM civic.ingestion_run_sources source
                  WHERE source.ingestion_run_id = run.id AND source.status IN ('queued', 'running'))""",
            (organization_id,),
        )

    async def claim_vector_index_jobs(self, *, limit: int) -> list[VectorIndexJob]:
        async with await self._connection() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute("SELECT * FROM civic.claim_vector_index_jobs(%s)", (limit,))
                rows = await cursor.fetchall()
        return [self._vector_index_job_from_row(row) for row in rows]

    async def complete_vector_index_job(self, job: VectorIndexJob) -> None:
        async with await self._connection() as connection, connection.transaction():
            await self._set_organization(connection, job.organization_id)
            await connection.execute(
                """
                UPDATE civic.vector_index_jobs
                SET status = 'completed', indexed_at = now(), lease_token = NULL, leased_until = NULL, last_error = NULL
                WHERE id = %s AND organization_id = %s AND lease_token = %s
                """,
                (job.id, job.organization_id, job.lease_token),
            )

    async def fail_vector_index_job(self, *, job: VectorIndexJob, error: str) -> None:
        async with await self._connection() as connection, connection.transaction():
            await self._set_organization(connection, job.organization_id)
            await connection.execute(
                """
                UPDATE civic.vector_index_jobs
                SET status = 'failed', run_after = now() + interval '60 seconds' * LEAST(60, power(2, attempt_count)),
                  lease_token = NULL, leased_until = NULL, last_error = %s
                WHERE id = %s AND organization_id = %s AND lease_token = %s
                """,
                (error[:4000], job.id, job.organization_id, job.lease_token),
            )

    async def _connection(self) -> psycopg.AsyncConnection[dict[str, Any]]:
        return await psycopg.AsyncConnection.connect(self._database_url, row_factory=dict_row)

    async def _set_organization(
        self, connection: psycopg.AsyncConnection[dict[str, Any]], organization_id: UUID
    ) -> None:
        await connection.execute("SELECT set_config('app.organization_id', %s, true)", (str(organization_id),))

    @staticmethod
    def _job_from_row(row: dict[str, Any]) -> DiscoveryJob:
        source = Source(
            id=UUID(str(row["source_id"])),
            organization_id=UUID(str(row["organization_id"])),
            name=str(row["name"]),
            canonical_url=str(row["canonical_url"]),
            acquisition_policy=dict(row["acquisition_policy"]),
            scan_interval_seconds=int(row["scan_interval_seconds"]),
            max_pages_per_scan=int(row["max_pages_per_scan"]),
            request_timeout_seconds=int(row["request_timeout_seconds"]),
        )
        return DiscoveryJob(id=UUID(str(row["job_id"])), source=source, lease_token=UUID(str(row["lease_token"])))

    @staticmethod
    def _vector_index_job_from_row(row: dict[str, Any]) -> VectorIndexJob:
        raw_topic_ids = row["topic_ids"] or []
        return VectorIndexJob(
            id=UUID(str(row["job_id"])),
            lease_token=UUID(str(row["lease_token"])),
            organization_id=UUID(str(row["organization_id"])),
            document_id=UUID(str(row["document_id"])),
            document_version_id=UUID(str(row["document_version_id"])),
            title=str(row["title"]),
            document_type=str(row["document_type"]),
            source_id=UUID(str(row["source_id"])) if row["source_id"] else None,
            department_id=UUID(str(row["department_id"])) if row["department_id"] else None,
            published_at=row["published_at"],
            extracted_text=str(row["extracted_text"] or ""),
            topic_ids=tuple(UUID(str(topic_id)) for topic_id in raw_topic_ids),
        )
