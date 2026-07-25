from __future__ import annotations

import argparse
import asyncio
import logging
import socket
from datetime import datetime
from zoneinfo import ZoneInfo

from civicos_ingestion.briefing import DailyBriefingService, PostgresBriefingRepository
from civicos_ingestion.bootstrap import apply_st_joseph_seed
from civicos_ingestion.config import Settings
from civicos_ingestion.crawler import CivicCrawler
from civicos_ingestion.founder_brief import FounderBriefService, PostgresFounderBriefRepository
from civicos_ingestion.repository import PostgresDiscoveryRepository
from civicos_ingestion.service import DiscoveryService
from civicos_ingestion.storage import S3ObjectStore
from civicos_ingestion.vector_index import (
    OpenAICompatibleEmbeddingClient,
    QdrantVectorIndexer,
    VectorIndexer,
)


def build_service(settings: Settings) -> DiscoveryService:
    return DiscoveryService(
        repository=PostgresDiscoveryRepository(settings.database_url),
        crawler=CivicCrawler(user_agent=settings.discovery_user_agent),
        object_store=S3ObjectStore(
            bucket=settings.s3_bucket,
            access_key=settings.s3_access_key,
            secret_key=settings.s3_secret_key,
            endpoint_url=settings.s3_endpoint_url,
        ),
        vector_indexer=build_vector_indexer(settings),
    )


def build_vector_indexer(settings: Settings) -> VectorIndexer | None:
    if not (settings.qdrant_url and settings.embedding_base_url and settings.embedding_model):
        return None
    return QdrantVectorIndexer(
        qdrant_url=settings.qdrant_url,
        collection=settings.qdrant_collection,
        api_key=settings.qdrant_api_key,
        embedding_client=OpenAICompatibleEmbeddingClient(
            base_url=settings.embedding_base_url,
            model=settings.embedding_model,
            api_key=settings.embedding_api_key,
            max_characters=settings.embedding_max_characters,
        ),
    )


def build_briefing_service(settings: Settings) -> DailyBriefingService:
    return DailyBriefingService(
        repository=PostgresBriefingRepository(settings.database_url),
        near_term_days=settings.briefing_near_term_days,
        lookahead_days=settings.briefing_lookahead_days,
        section_limit=settings.briefing_section_limit,
    )


def build_founder_brief_service(settings: Settings) -> FounderBriefService:
    return FounderBriefService(
        repository=PostgresFounderBriefRepository(settings.database_url),
        minimum_score=settings.founder_brief_minimum_score,
        section_limit=settings.founder_brief_section_limit,
    )


async def run_worker(*, once: bool, backfill_canonical: bool = False) -> None:
    settings = Settings()  # type: ignore[call-arg]
    service = build_service(settings)
    briefing_service = build_briefing_service(settings)
    founder_brief_service = build_founder_brief_service(settings)
    if backfill_canonical or settings.canonical_backfill_on_start:
        result = await service.backfill_canonical_records()
        logging.getLogger(__name__).info("Canonical backfill complete", extra=result)
        if backfill_canonical:
            return
    while True:
        await service.record_heartbeat(socket.gethostname())
        discovery_claimed = await service.run_due_jobs()
        briefing_claimed = await briefing_service.run_due_jobs(
            briefing_date=datetime.now(ZoneInfo(settings.briefing_timezone)).date()
        )
        founder_brief_claimed = await founder_brief_service.run_due_jobs(
            briefing_date=datetime.now(ZoneInfo(settings.briefing_timezone)).date()
        )
        if once:
            return
        await asyncio.sleep(
            0 if discovery_claimed or briefing_claimed or founder_brief_claimed else settings.discovery_poll_seconds
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the CivicOS autonomous discovery worker.")
    parser.add_argument("--once", action="store_true", help="Claim and run one batch, then exit.")
    parser.add_argument(
        "--apply-seed",
        action="store_true",
        help="Apply the idempotent St. Joseph County source seed first.",
    )
    parser.add_argument(
        "--backfill-canonical",
        action="store_true",
        help="Rebuild canonical civic records from immutable raw document versions, then exit.",
    )
    arguments = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    if arguments.apply_seed:
        settings = Settings()  # type: ignore[call-arg]
        apply_st_joseph_seed(settings.database_url)
    asyncio.run(run_worker(once=arguments.once, backfill_canonical=arguments.backfill_canonical))


if __name__ == "__main__":
    main()
