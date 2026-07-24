from datetime import date
from uuid import UUID

from civicos_ingestion.founder_intelligence import opportunity_score
from civicos_ingestion.models import (
    DepartmentCandidate,
    ExtractedDocument,
    GraphNodeCandidate,
    ProcessingContext,
    TopicCandidate,
)
from civicos_ingestion.processing import clean_text, process_document


def test_processing_enriches_cleaned_content_with_auditable_metadata() -> None:
    department_id = UUID("00000000-0000-0000-0000-000000000010")
    topic_id = UUID("00000000-0000-0000-0000-000000000011")
    document = ExtractedDocument(
        title="Planning Commission Agenda",
        document_type="pdf",
        text="Published: March 7, 2026\r\n\r\nPlanning Department agenda\t\n"
        "Mayor Jane Doe discussed infrastructure funding.",
        metadata={"pages": 1},
    )
    context = ProcessingContext(
        departments=(DepartmentCandidate(id=department_id, name="Planning Department"),),
        topics=(TopicCandidate(id=topic_id, name="infrastructure"),),
    )

    processed = process_document(document, context)

    assert processed.cleaned_text == (
        "Published: March 7, 2026\nPlanning Department agenda\nMayor Jane Doe discussed infrastructure funding."
    )
    assert processed.document_type == "meeting_agenda"
    assert processed.publication_date == date(2026, 3, 7)
    assert processed.department_id == department_id
    assert processed.topic_ids == (topic_id,)
    assert [(entity.entity_type, entity.canonical_name) for entity in processed.entities] == [
        ("organization", "Planning Department"),
        ("person", "Jane Doe"),
    ]
    assert processed.entities[1].official_title == "Mayor"
    assert processed.metadata["file_type"] == "pdf"
    assert processed.metadata["date_candidates"][0]["value"] == "2026-03-07"


def test_clean_text_removes_control_characters_without_losing_line_boundaries() -> None:
    assert clean_text("  One\x00\t two\r\n\r\nThree  ") == "One two\nThree"


def test_processing_discovers_evidence_backed_graph_relationships() -> None:
    document = ExtractedDocument(
        title="Project update",
        document_type="pdf",
        text=(
            "The Capital Improvement Plan is on the Board Meeting agenda at Civic Center. "
            "ORD-2026-1 appropriates the FY 2026 Budget, and Jane Doe will present it."
        ),
        metadata={},
    )
    context = ProcessingContext(
        departments=(),
        topics=(),
        graph_nodes=(
            GraphNodeCandidate(UUID("00000000-0000-0000-0000-000000000021"), "meeting", "Board Meeting"),
            GraphNodeCandidate(UUID("00000000-0000-0000-0000-000000000022"), "ordinance", "ORD-2026-1"),
            GraphNodeCandidate(UUID("00000000-0000-0000-0000-000000000023"), "budget", "FY 2026 Budget"),
            GraphNodeCandidate(UUID("00000000-0000-0000-0000-000000000024"), "project", "Capital Improvement Plan"),
            GraphNodeCandidate(UUID("00000000-0000-0000-0000-000000000025"), "official", "Jane Doe"),
            GraphNodeCandidate(UUID("00000000-0000-0000-0000-000000000026"), "location", "Civic Center"),
        ),
    )

    processed = process_document(document, context)

    assert [(relationship.object_type, relationship.predicate) for relationship in processed.relationships] == [
        ("meeting", "references_meeting"),
        ("ordinance", "references_ordinance"),
        ("budget", "references_budget"),
        ("project", "references_project"),
        ("official", "mentions_official"),
        ("location", "mentions_location"),
    ]
    assert all(relationship.confidence == 0.9 for relationship in processed.relationships)


def test_processing_detects_ranked_founder_signals_with_source_evidence() -> None:
    document = ExtractedDocument(
        title="Public Works RFP and Infrastructure Funding",
        document_type="pdf",
        text=(
            "The St. Joseph County Department of Public Works issued a request for proposals for a roadway "
            "infrastructure project. The capital improvement appropriation will fund the work."
        ),
        metadata={},
    )

    processed = process_document(document, ProcessingContext(departments=(), topics=()))

    signals = {signal.signal_type: signal for signal in processed.founder_signals}
    assert {"procurement", "infrastructure", "public_spending"} <= set(signals)
    assert signals["procurement"].evidence_excerpt
    assert signals["procurement"].evidence_start_offset >= 0
    assert "local contractors" in signals["procurement"].potential_customer_segments
    assert opportunity_score(signals["procurement"]) == 90
    assert processed.metadata["founder_signal_types"]
