from datetime import date
from uuid import UUID

from civicos_ingestion.models import VectorIndexJob
from civicos_ingestion.vector_index import QdrantVectorIndexer


def test_qdrant_payload_contains_all_search_filters() -> None:
    job = VectorIndexJob(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        lease_token=UUID("00000000-0000-0000-0000-000000000002"),
        organization_id=UUID("00000000-0000-0000-0000-000000000003"),
        document_id=UUID("00000000-0000-0000-0000-000000000004"),
        document_version_id=UUID("00000000-0000-0000-0000-000000000005"),
        title="River restoration update",
        document_type="report",
        source_id=UUID("00000000-0000-0000-0000-000000000006"),
        department_id=UUID("00000000-0000-0000-0000-000000000007"),
        published_at=date(2026, 1, 15),
        extracted_text="River restoration details",
        topic_ids=(UUID("00000000-0000-0000-0000-000000000008"),),
    )

    payload = QdrantVectorIndexer._payload(job)

    assert payload == {
        "organization_id": "00000000-0000-0000-0000-000000000003",
        "document_id": "00000000-0000-0000-0000-000000000004",
        "document_version_id": "00000000-0000-0000-0000-000000000005",
        "source_id": "00000000-0000-0000-0000-000000000006",
        "department_id": "00000000-0000-0000-0000-000000000007",
        "topic_ids": ["00000000-0000-0000-0000-000000000008"],
        "document_type": "report",
        "published_at": "2026-01-15",
    }
