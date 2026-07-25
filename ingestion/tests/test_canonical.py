from datetime import date

from civicos_ingestion.canonical import canonical_signal_candidates, canonicalize_document
from civicos_ingestion.models import ExtractedDocument, ProcessingContext
from civicos_ingestion.processing import process_document
from civicos_ingestion.repository import PostgresDiscoveryRepository


def _draft(title: str, text: str):
    processed = process_document(
        ExtractedDocument(title=title, document_type="pdf", text=text, metadata={}),
        ProcessingContext(departments=(), topics=()),
    )
    return canonicalize_document(
        processed=processed,
        source_agency="St. Joseph County Planning Department",
        source_url="https://records.example.test/item",
        jurisdiction="St. Joseph County, Indiana",
    )


def test_planning_agenda_becomes_structured_agenda_items() -> None:
    draft = _draft(
        "Planning Commission Agenda",
        "Planning Commission Agenda\n1. Case PC-2026-17 — rezoning 123 Main Street\n2. Riverfront Development Plan",
    )

    assert draft.record_type == "planning_zoning_case"
    assert "PC-2026-17" in draft.case_numbers
    assert "123 Main Street" in draft.addresses
    assert draft.typed_payload["agenda_items"]
    assert any(item.field_name == "case_numbers" for item in draft.evidence)


def test_permit_yields_address_permit_number_and_project_value() -> None:
    draft = _draft(
        "Building Permit",
        "Building Permit No. BP-2026-441 filed for 456 Market Avenue. Project value: $250,000.",
    )

    assert draft.record_type == "permit"
    assert draft.permit_numbers == ("BP-2026-441",)
    assert draft.addresses == ("456 Market Avenue",)
    assert draft.money_amounts == ("$250,000",)
    assert draft.typed_payload["permit_numbers"] == ["BP-2026-441"]


def test_contract_yields_vendor_amount_and_award_status() -> None:
    draft = _draft(
        "Notice of Award",
        "Notice of award: The County awarded to Acme Construction Company a contract for $1,200,000.",
    )

    assert draft.record_type == "contract_award"
    assert "Acme Construction Company" in draft.organizations
    assert draft.money_amounts == ("$1,200,000",)
    assert draft.status == "approved"


def test_duplicate_source_documents_share_a_deterministic_deduplication_key() -> None:
    first = _draft("Permit", "Permit No. P-2026-10 issued for 100 River Road.")
    second = _draft("Permit", "Permit No. P-2026-10 issued for 100 River Road.")

    assert first.dedup_key == second.dedup_key


def test_changed_document_produces_field_level_change_event() -> None:
    before = _draft("RFP", "Request for proposals. Responses are due June 1, 2026.")
    after = _draft("RFP", "Request for proposals. Responses are due June 15, 2026.")

    changes = PostgresDiscoveryRepository._canonical_changes(
        draft=after, previous=PostgresDiscoveryRepository._canonical_snapshot(before)
    )

    assert any(change_type == "deadline_changed" and field == "deadlines" for change_type, field, _, _ in changes)


def test_canonical_intelligence_has_evidence_for_every_claim() -> None:
    draft = _draft(
        "Request for Proposals",
        "The County issued a request for proposals. Responses are due June 1, 2026. Budget is $500,000.",
    )
    signals = canonical_signal_candidates(draft, change_types=("new_record",))

    assert signals
    for signal in signals:
        assert signal.evidence_excerpt
        assert signal.evidence_start_offset >= 0
        assert signal.evidence_end_offset > signal.evidence_start_offset
