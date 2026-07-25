from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from civicos_ingestion.canonical import (
    CanonicalRecordDraft,
    EXTRACTION_VERSION,
    canonical_signal_candidates,
    canonicalize_document,
)
from civicos_ingestion.crawler import content_hash
from civicos_ingestion.founder_intelligence import opportunity_score
from civicos_ingestion.models import (
    DepartmentCandidate,
    DiscoveryJob,
    ExtractedDocument,
    FetchedResource,
    GraphNodeCandidate,
    PersistedDocument,
    ProcessedDocument,
    ProcessingContext,
    Source,
    TopicCandidate,
    VectorIndexJob,
)
from civicos_ingestion.processing import process_document


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

    async def backfill_canonical_records(self, *, limit: int | None = None) -> dict[str, int]: ...


@dataclass(frozen=True)
class CanonicalPersistence:
    record_id: UUID
    version_id: UUID
    change_ids: tuple[UUID, ...]
    change_types: tuple[str, ...]


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
                    jurisdiction = await self._source_jurisdiction(
                        cursor=cursor,
                        organization_id=source.organization_id,
                        source_id=source.id,
                    )
                    canonical_draft = canonicalize_document(
                        processed=processed,
                        source_agency=source.name,
                        source_url=resource.final_url,
                        jurisdiction=jurisdiction,
                    )
                    canonical = await self._persist_canonical_record(
                        cursor=cursor,
                        organization_id=source.organization_id,
                        raw_document_id=document_id,
                        raw_document_version_id=version_id,
                        source_id=source.id,
                        draft=canonical_draft,
                    )
                    await self._persist_founder_intelligence(
                        cursor=cursor,
                        organization_id=source.organization_id,
                        document_id=document_id,
                        document_version_id=version_id,
                        source_url=resource.final_url,
                        canonical_record_id=canonical.record_id,
                        canonical_change_id=canonical.change_ids[0] if canonical.change_ids else None,
                        candidates=canonical_signal_candidates(
                            canonical_draft,
                            change_types=canonical.change_types,
                        ),
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

    async def _source_jurisdiction(
        self,
        *,
        cursor: psycopg.AsyncCursor[dict[str, Any]],
        organization_id: UUID,
        source_id: UUID,
    ) -> str | None:
        await cursor.execute(
            """
            SELECT coalesce(municipality.name, organization.name) AS jurisdiction
            FROM civic.sources AS source
            JOIN core.organizations AS organization ON organization.id = source.organization_id
            LEFT JOIN core.municipalities AS municipality
              ON municipality.organization_id = source.organization_id AND municipality.id = source.municipality_id
            WHERE source.organization_id = %s AND source.id = %s
            """,
            (organization_id, source_id),
        )
        row = await cursor.fetchone()
        return str(row["jurisdiction"]) if row and row["jurisdiction"] else None

    async def _persist_canonical_record(
        self,
        *,
        cursor: psycopg.AsyncCursor[dict[str, Any]],
        organization_id: UUID,
        raw_document_id: UUID,
        raw_document_version_id: UUID,
        source_id: UUID | None,
        draft: CanonicalRecordDraft,
    ) -> CanonicalPersistence:
        """Version a canonical projection; raw versions and evidence are never mutated."""

        await cursor.execute(
            """
            SELECT record.id, record.current_version_id, version.snapshot
            FROM civic.canonical_records AS record
            LEFT JOIN civic.canonical_record_versions AS version
              ON version.organization_id = record.organization_id AND version.id = record.current_version_id
            WHERE record.organization_id = %s AND record.record_type = %s AND record.dedup_key = %s
            FOR UPDATE
            """,
            (organization_id, draft.record_type, draft.dedup_key),
        )
        previous = await cursor.fetchone()
        snapshot = self._canonical_snapshot(draft)
        await cursor.execute(
            """
            INSERT INTO civic.canonical_records (
              organization_id, raw_document_id, source_id, record_type, jurisdiction, source_agency, source_url,
              source_document_id, dedup_key, title, published_at, event_date, effective_date, summary, key_facts,
              entities, people, organizations, addresses, parcel_numbers, case_numbers, permit_numbers,
              project_names, money_amounts, deadlines, actions, decisions, status, topics, typed_payload,
              extraction_confidence, extraction_version, first_seen_at, last_seen_at
            ) VALUES (
              %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
              %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb,
              %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s, %s::jsonb, %s::jsonb, %s, %s, now(), now()
            ) ON CONFLICT (organization_id, record_type, dedup_key) DO UPDATE SET
              source_id = EXCLUDED.source_id, jurisdiction = EXCLUDED.jurisdiction,
              source_agency = EXCLUDED.source_agency, source_url = EXCLUDED.source_url,
              source_document_id = EXCLUDED.source_document_id, title = EXCLUDED.title,
              published_at = EXCLUDED.published_at, event_date = EXCLUDED.event_date,
              effective_date = EXCLUDED.effective_date, summary = EXCLUDED.summary, key_facts = EXCLUDED.key_facts,
              entities = EXCLUDED.entities, people = EXCLUDED.people, organizations = EXCLUDED.organizations,
              addresses = EXCLUDED.addresses, parcel_numbers = EXCLUDED.parcel_numbers, case_numbers = EXCLUDED.case_numbers,
              permit_numbers = EXCLUDED.permit_numbers, project_names = EXCLUDED.project_names,
              money_amounts = EXCLUDED.money_amounts, deadlines = EXCLUDED.deadlines, actions = EXCLUDED.actions,
              decisions = EXCLUDED.decisions, status = EXCLUDED.status, topics = EXCLUDED.topics,
              typed_payload = EXCLUDED.typed_payload, extraction_confidence = EXCLUDED.extraction_confidence,
              extraction_version = EXCLUDED.extraction_version, last_seen_at = now()
            RETURNING id
            """,
            (
                organization_id, raw_document_id, source_id, draft.record_type, draft.jurisdiction, draft.source_agency,
                draft.source_url, draft.source_document_id, draft.dedup_key, draft.title, draft.published_at,
                draft.event_date, draft.effective_date, draft.summary, Jsonb(list(draft.key_facts)),
                Jsonb(list(draft.entities)), Jsonb(list(draft.people)), Jsonb(list(draft.organizations)),
                Jsonb(list(draft.addresses)), Jsonb(list(draft.parcel_numbers)), Jsonb(list(draft.case_numbers)),
                Jsonb(list(draft.permit_numbers)), Jsonb(list(draft.project_names)), Jsonb(list(draft.money_amounts)),
                Jsonb(list(draft.deadlines)), Jsonb(list(draft.actions)), Jsonb(list(draft.decisions)), draft.status,
                Jsonb(list(draft.topics)), Jsonb(draft.typed_payload), draft.confidence, EXTRACTION_VERSION,
            ),
        )
        row = await cursor.fetchone()
        if row is None:
            raise RuntimeError("Could not persist canonical civic record")
        record_id = UUID(str(row["id"]))
        await cursor.execute(
            """
            INSERT INTO civic.canonical_record_versions (
              organization_id, canonical_record_id, raw_document_version_id, version_number, extraction_version, snapshot
            ) VALUES (
              %s, %s, %s,
              coalesce((SELECT max(version_number) + 1 FROM civic.canonical_record_versions
                WHERE organization_id = %s AND canonical_record_id = %s), 1),
              %s, %s::jsonb
            ) RETURNING id
            """,
            (organization_id, record_id, raw_document_version_id, organization_id, record_id, EXTRACTION_VERSION, Jsonb(snapshot)),
        )
        version_row = await cursor.fetchone()
        if version_row is None:
            raise RuntimeError("Could not version canonical civic record")
        canonical_version_id = UUID(str(version_row["id"]))
        await cursor.execute(
            """UPDATE civic.canonical_records SET current_version_id = %s, last_seen_at = now()
            WHERE organization_id = %s AND id = %s""",
            (canonical_version_id, organization_id, record_id),
        )
        for item in draft.evidence:
            await cursor.execute(
                """
                INSERT INTO civic.canonical_record_evidence (
                  organization_id, canonical_record_version_id, field_name, value, source_text, source_url,
                  start_offset, end_offset, page_reference, section_reference, confidence
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (organization_id, canonical_record_version_id, field_name, start_offset, end_offset)
                DO NOTHING
                """,
                (organization_id, canonical_version_id, item.field_name, item.value, item.source_text, draft.source_url,
                 item.start_offset, item.end_offset, item.page_reference, item.section_reference, item.confidence),
            )
        prior_snapshot = previous["snapshot"] if previous and previous["snapshot"] else None
        prior_version_id = UUID(str(previous["current_version_id"])) if previous and previous["current_version_id"] else None
        changes = self._canonical_changes(
            draft=draft,
            previous=prior_snapshot if isinstance(prior_snapshot, dict) else None,
        )
        change_ids: list[UUID] = []
        for change_type, field_name, before, after in changes:
            evidence = [
                item.payload() | {"source_url": draft.source_url}
                for item in draft.evidence
                if field_name == "record" or item.field_name == field_name
            ]
            await cursor.execute(
                """
                INSERT INTO civic.canonical_record_changes (
                  organization_id, canonical_record_id, from_version_id, to_version_id, change_type, field_name,
                  previous_value, current_value, evidence, confidence
                ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s)
                RETURNING id
                """,
                (organization_id, record_id, prior_version_id, canonical_version_id, change_type, field_name,
                 Jsonb(before) if before is not None else None, Jsonb(after) if after is not None else None,
                 Jsonb(evidence), draft.confidence),
            )
            change_row = await cursor.fetchone()
            if change_row:
                change_ids.append(UUID(str(change_row["id"])))
        return CanonicalPersistence(
            record_id=record_id,
            version_id=canonical_version_id,
            change_ids=tuple(change_ids),
            change_types=tuple(change[0] for change in changes),
        )

    @staticmethod
    def _canonical_snapshot(draft: CanonicalRecordDraft) -> dict[str, Any]:
        return {
            "record_type": draft.record_type, "title": draft.title, "published_at": draft.published_at.isoformat() if draft.published_at else None,
            "event_date": draft.event_date.isoformat() if draft.event_date else None,
            "effective_date": draft.effective_date.isoformat() if draft.effective_date else None,
            "summary": draft.summary, "key_facts": list(draft.key_facts), "entities": list(draft.entities),
            "people": list(draft.people), "organizations": list(draft.organizations), "addresses": list(draft.addresses),
            "parcel_numbers": list(draft.parcel_numbers), "case_numbers": list(draft.case_numbers),
            "permit_numbers": list(draft.permit_numbers), "project_names": list(draft.project_names),
            "money_amounts": list(draft.money_amounts), "deadlines": list(draft.deadlines), "actions": list(draft.actions),
            "decisions": list(draft.decisions), "status": draft.status, "topics": list(draft.topics),
            "typed_payload": draft.typed_payload,
        }

    @staticmethod
    def _canonical_changes(
        *, draft: CanonicalRecordDraft, previous: dict[str, Any] | None
    ) -> list[tuple[str, str, object | None, object | None]]:
        current = PostgresDiscoveryRepository._canonical_snapshot(draft)
        if previous is None:
            return [("new_record", "record", None, current)]
        changes: list[tuple[str, str, object | None, object | None]] = []
        for key, value in current.items():
            if previous.get(key) != value:
                change_type = "field_changed"
                if key == "deadlines":
                    change_type = "deadline_changed"
                elif key == "money_amounts" and draft.record_type in {"contract_award", "budget_financial_report"}:
                    change_type = "project_value_increased"
                elif key == "status" and draft.record_type == "planning_zoning_case" and value == "approved":
                    change_type = "zoning_approved"
                elif key == "status" and draft.record_type == "planning_zoning_case" and value == "denied":
                    change_type = "zoning_denied"
                elif key == "status" and draft.record_type == "contract_award" and value == "approved":
                    change_type = "contract_awarded"
                elif key == "status" and draft.record_type == "ordinance" and value == "approved":
                    change_type = "ordinance_adopted"
                changes.append((change_type, key, previous.get(key), value))
        return changes

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
        canonical_record_id: UUID,
        canonical_change_id: UUID | None,
        candidates: tuple[Any, ...],
    ) -> None:
        """Persist signals only after a canonical record and its change evidence exist."""

        for candidate in candidates:
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
                  evidence, canonical_record_id, canonical_change_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s, %s)
                ON CONFLICT (organization_id, document_version_id, signal_type) DO UPDATE SET
                  title = EXCLUDED.title, summary = EXCLUDED.summary, why_it_matters = EXCLUDED.why_it_matters,
                  economic_value_score = EXCLUDED.economic_value_score, confidence_score = EXCLUDED.confidence_score,
                  recency_score = EXCLUDED.recency_score, urgency_score = EXCLUDED.urgency_score,
                  evidence_strength_score = EXCLUDED.evidence_strength_score,
                  actionability_score = EXCLUDED.actionability_score,
                  commercial_significance = EXCLUDED.commercial_significance,
                  affected_organizations = EXCLUDED.affected_organizations,
                  potential_customer_segments = EXCLUDED.potential_customer_segments, evidence = EXCLUDED.evidence,
                  canonical_record_id = EXCLUDED.canonical_record_id,
                  canonical_change_id = EXCLUDED.canonical_change_id,
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
                    canonical_record_id,
                    canonical_change_id,
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
                document_text=f"{candidate.title} {candidate.summary}",
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

    async def backfill_canonical_records(self, *, limit: int | None = None) -> dict[str, int]:
        """Rebuild the projection from immutable raw versions without recrawling sources."""

        counts = {
            "raw_documents_processed": 0,
            "canonical_records_created": 0,
            "records_rejected": 0,
            "duplicates_merged": 0,
        }
        async with await self._connection() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute("SELECT id FROM core.organizations WHERE is_active ORDER BY id")
                organizations = await cursor.fetchall()
            for organization in organizations:
                organization_id = UUID(str(organization["id"]))
                async with connection.transaction():
                    await self._set_organization(connection, organization_id)
                    async with connection.cursor() as cursor:
                        await cursor.execute(
                            """SELECT status FROM civic.canonical_backfill_runs
                            WHERE organization_id = %s AND extraction_version = %s""",
                            (organization_id, EXTRACTION_VERSION),
                        )
                        existing_run = await cursor.fetchone()
                        if existing_run and existing_run["status"] == "completed":
                            continue
                        organization_counts = {
                            "raw_documents_processed": 0,
                            "canonical_records_created": 0,
                            "records_rejected": 0,
                            "duplicates_merged": 0,
                        }
                        await cursor.execute(
                            """INSERT INTO civic.canonical_backfill_runs (organization_id, extraction_version, status)
                            VALUES (%s, %s, 'running')
                            ON CONFLICT (organization_id, extraction_version) DO UPDATE SET
                              status = 'running', started_at = now(), completed_at = NULL, error_message = NULL""",
                            (organization_id, EXTRACTION_VERSION),
                        )
                        await cursor.execute(
                            """
                            SELECT DISTINCT ON (document.id) document.id AS document_id, version.id AS version_id,
                              document.title, document.document_type, document.canonical_url, version.extracted_text,
                              version.extracted_metadata, source.id AS source_id, source.name AS source_name,
                              source.canonical_url AS source_url,
                              coalesce(municipality.name, organization.name) AS jurisdiction
                            FROM civic.documents AS document
                            JOIN civic.document_versions AS version
                              ON version.organization_id = document.organization_id AND version.document_id = document.id
                            LEFT JOIN civic.sources AS source
                              ON source.organization_id = document.organization_id AND source.id = document.source_id
                            JOIN core.organizations AS organization ON organization.id = document.organization_id
                            LEFT JOIN core.municipalities AS municipality
                              ON municipality.organization_id = document.organization_id AND municipality.id = document.municipality_id
                            WHERE document.organization_id = %s AND coalesce(version.extracted_text, '') <> ''
                            ORDER BY document.id, version.version_number DESC
                            """ + (" LIMIT %s" if limit is not None else ""),
                            (organization_id, limit) if limit is not None else (organization_id,),
                        )
                        rows = await cursor.fetchall()
                        for row in rows:
                            try:
                                await cursor.execute("SAVEPOINT canonical_backfill_document")
                                organization_counts["raw_documents_processed"] += 1
                                await cursor.execute(
                                    """
                                    SELECT 1 FROM civic.canonical_record_versions
                                    WHERE organization_id = %s AND raw_document_version_id = %s LIMIT 1
                                    """,
                                    (organization_id, row["version_id"]),
                                )
                                if await cursor.fetchone():
                                    organization_counts["duplicates_merged"] += 1
                                    await cursor.execute("RELEASE SAVEPOINT canonical_backfill_document")
                                    continue
                                extracted = ExtractedDocument(
                                    title=str(row["title"]), document_type=str(row["document_type"]),
                                    text=str(row["extracted_text"]), metadata={},
                                )
                                processed = process_document(extracted, ProcessingContext(departments=(), topics=()))
                                source_url = str(row["canonical_url"] or row["source_url"] or "").strip()
                                if not source_url:
                                    raise ValueError("Raw document has no auditable source URL")
                                draft = canonicalize_document(
                                    processed=processed,
                                    source_agency=str(row["source_name"] or "Official public source"),
                                    source_url=source_url,
                                    jurisdiction=str(row["jurisdiction"]) if row["jurisdiction"] else None,
                                )
                                existed_before = False
                                await cursor.execute(
                                    """SELECT 1 FROM civic.canonical_records
                                    WHERE organization_id = %s AND record_type = %s AND dedup_key = %s""",
                                    (organization_id, draft.record_type, draft.dedup_key),
                                )
                                existed_before = await cursor.fetchone() is not None
                                await self._persist_canonical_record(
                                    cursor=cursor, organization_id=organization_id,
                                    raw_document_id=UUID(str(row["document_id"])),
                                    raw_document_version_id=UUID(str(row["version_id"])),
                                    source_id=UUID(str(row["source_id"])) if row["source_id"] else None,
                                    draft=draft,
                                )
                                if existed_before:
                                    organization_counts["duplicates_merged"] += 1
                                else:
                                    organization_counts["canonical_records_created"] += 1
                                await cursor.execute("RELEASE SAVEPOINT canonical_backfill_document")
                            except Exception:
                                await cursor.execute("ROLLBACK TO SAVEPOINT canonical_backfill_document")
                                logger.exception("Canonical backfill failed", extra={"document_id": str(row["document_id"])})
                                organization_counts["records_rejected"] += 1
                        status = "completed" if organization_counts["records_rejected"] == 0 else "failed"
                        await cursor.execute(
                            """UPDATE civic.canonical_backfill_runs SET status = %s, raw_documents_processed = %s,
                              canonical_records_created = %s, records_rejected = %s, duplicates_merged = %s,
                              completed_at = now(), error_message = %s
                            WHERE organization_id = %s AND extraction_version = %s""",
                            (
                                status, organization_counts["raw_documents_processed"],
                                organization_counts["canonical_records_created"], organization_counts["records_rejected"],
                                organization_counts["duplicates_merged"],
                                "One or more raw documents could not be canonicalized" if status == "failed" else None,
                                organization_id, EXTRACTION_VERSION,
                            ),
                        )
                        for key, value in organization_counts.items():
                            counts[key] += value
        return counts

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
