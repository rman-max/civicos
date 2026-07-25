from __future__ import annotations

import logging

from civicos_ingestion.crawler import CivicCrawler, content_hash
from civicos_ingestion.extractors import extract_document
from civicos_ingestion.models import DiscoveryJob, ScanSummary
from civicos_ingestion.processing import process_document
from civicos_ingestion.repository import DiscoveryRepository
from civicos_ingestion.storage import ObjectStore
from civicos_ingestion.vector_index import VectorIndexer

logger = logging.getLogger(__name__)


class DiscoveryService:
    def __init__(
        self,
        *,
        repository: DiscoveryRepository,
        crawler: CivicCrawler,
        object_store: ObjectStore,
        vector_indexer: VectorIndexer | None = None,
    ) -> None:
        self._repository = repository
        self._crawler = crawler
        self._object_store = object_store
        self._vector_indexer = vector_indexer

    async def run_due_jobs(self, *, limit: int = 5) -> int:
        jobs = await self._repository.claim_due_jobs(limit=limit)
        for job in jobs:
            await self._run_job(job)
        await self.run_due_vector_index_jobs(limit=limit)
        return len(jobs)

    async def record_heartbeat(self, worker_id: str) -> None:
        """Record liveness without exposing the worker through the public API."""

        await self._repository.heartbeat(worker_id)

    async def backfill_canonical_records(self) -> dict[str, int]:
        """Reprocess raw evidence into canonical records without network access."""

        return await self._repository.backfill_canonical_records()

    async def run_due_vector_index_jobs(self, *, limit: int = 5) -> int:
        if self._vector_indexer is None:
            return 0
        jobs = await self._repository.claim_vector_index_jobs(limit=limit)
        for job in jobs:
            try:
                await self._vector_indexer.index(job)
                await self._repository.complete_vector_index_job(job)
            except Exception as error:
                logger.exception("Vector indexing failed", extra={"document_version_id": str(job.document_version_id)})
                await self._repository.fail_vector_index_job(job=job, error=str(error))
        return len(jobs)

    async def _run_job(self, job: DiscoveryJob) -> None:
        scan_run_id = None
        try:
            scan_run_id = await self._repository.start_scan(job)
            result = await self._crawler.crawl(job.source)
            processing_context = await self._repository.get_processing_context(job)
            summary = ScanSummary(pages_crawled=result.pages_crawled)
            for resource in result.resources:
                try:
                    extracted = extract_document(
                        media_type=resource.media_type,
                        url=resource.final_url,
                        body=resource.body,
                    )
                    processed = process_document(extracted, processing_context)
                    checksum = content_hash(resource.body)
                    storage_key = await self._object_store.put(
                        checksum=checksum, media_type=resource.media_type, body=resource.body
                    )
                    persisted = await self._repository.persist_resource(
                        job=job,
                        scan_run_id=scan_run_id,
                        resource=resource,
                        processed=processed,
                        storage_key=storage_key,
                    )
                    summary.documents_discovered += 1
                    summary.documents_changed += int(persisted.changed)
                    summary.documents_skipped += int(not persisted.changed)
                    # PostgreSQL generated FTS vectors make every changed version searchable immediately.
                    summary.documents_indexed += int(persisted.changed)
                except Exception:
                    # An extraction failure is isolated to its document; the next public record still proceeds.
                    logger.exception("Document processing failed", extra={"source_url": resource.final_url})
            await self._repository.complete_job(
                job=job,
                scan_run_id=scan_run_id,
                pages_crawled=summary.pages_crawled,
                documents_discovered=summary.documents_discovered,
                documents_changed=summary.documents_changed,
                documents_skipped=summary.documents_skipped,
                documents_indexed=summary.documents_indexed,
            )
        except Exception as error:
            logger.exception("Discovery scan failed", extra={"source_id": str(job.source.id)})
            await self._repository.fail_job(job=job, scan_run_id=scan_run_id, error=str(error))
