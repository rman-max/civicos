"""Deterministic, evidence-bound projection of raw civic documents.

Raw document versions are the system of record.  This module creates a
replaceable civic-record projection from a version without inventing facts.
Every non-empty field has an evidence span in the raw extracted text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from typing import Any

from civicos_ingestion.models import FounderSignalCandidate, ProcessedDocument

EXTRACTION_VERSION = "canonical-deterministic-v1"

RECORD_TYPES = {
    "agenda",
    "meeting_minutes",
    "ordinance",
    "resolution",
    "permit",
    "planning_zoning_case",
    "procurement_rfp",
    "contract_award",
    "budget_financial_report",
    "property_parcel_record",
    "public_notice",
    "newsletter",
    "general_webpage",
    "unknown",
}

MONEY_PATTERN = re.compile(r"\$(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{2})?")
ADDRESS_PATTERN = re.compile(
    r"(?<![A-Za-z0-9-])\d{1,6}\s+[A-Za-z0-9.'-]+(?:\s+[A-Za-z0-9.'-]+){0,4}\s+"
    r"(?:Street|St\.?|Avenue|Ave\.?|Road|Rd\.?|Drive|Dr\.?|Lane|Ln\.?|Court|Ct\.?|Boulevard|Blvd\.?|Way|Place|Pl\.?)\b",
    re.IGNORECASE,
)
PARCEL_PATTERN = re.compile(r"\b(?:parcel|tax\s+parcel|parcel\s*(?:no\.?|number)?)[\s:#-]*([0-9]{2,}(?:[-.]\d{2,})+)\b", re.I)
CASE_PATTERN = re.compile(r"\b(?:case|petition|docket)\s*(?:no\.?|number)?\s*[:#-]?\s*([A-Z]{1,5}(?:[- ]?\d+){1,3})\b", re.I)
PERMIT_PATTERN = re.compile(r"\b(?:permit)\s*(?:no\.?|number)?\s*[:#-]?\s*([A-Z]{0,5}(?:[- ]?\d+){1,3})\b", re.I)
ORDINANCE_PATTERN = re.compile(r"\b(?:ordinance|ord\.)\s*(?:no\.?|number)?\s*[:#-]?\s*([A-Z]{0,5}(?:[- ]?\d+){1,3})\b", re.I)
RESOLUTION_PATTERN = re.compile(r"\b(?:resolution|res\.)\s*(?:no\.?|number)?\s*[:#-]?\s*([A-Z]{0,5}(?:[- ]?\d+){1,3})\b", re.I)
DEADLINE_PATTERN = re.compile(
    r"\b(?:due|deadline|responses? (?:are )?due|bids? (?:are )?due|submit(?:ted)? by)\b[^.\n]{0,100}",
    re.I,
)
ACTION_PATTERN = re.compile(
    r"\b(?:approved|denied|adopted|introduced|awarded|issued|filed|scheduled|hearing|opened)\b[^.\n]{0,140}",
    re.I,
)
AGENDA_ITEM_PATTERN = re.compile(r"(?:^|\n)\s*(?:\d+[.)]|[A-Z][.)])\s+([^\n]{4,240})")


@dataclass(frozen=True)
class EvidenceSpan:
    field_name: str
    value: str
    source_text: str
    start_offset: int
    end_offset: int
    confidence: float
    section_reference: str | None = None
    page_reference: str | None = None

    def payload(self) -> dict[str, Any]:
        return {
            "field_name": self.field_name,
            "value": self.value,
            "source_text": self.source_text,
            "start_offset": self.start_offset,
            "end_offset": self.end_offset,
            "confidence": self.confidence,
            "section_reference": self.section_reference,
            "page_reference": self.page_reference,
        }


@dataclass(frozen=True)
class CanonicalRecordDraft:
    record_type: str
    title: str
    jurisdiction: str | None
    source_agency: str
    source_url: str
    source_document_id: str
    published_at: date | None
    event_date: date | None
    effective_date: date | None
    summary: str
    key_facts: tuple[str, ...]
    entities: tuple[str, ...]
    people: tuple[str, ...]
    organizations: tuple[str, ...]
    addresses: tuple[str, ...]
    parcel_numbers: tuple[str, ...]
    case_numbers: tuple[str, ...]
    permit_numbers: tuple[str, ...]
    project_names: tuple[str, ...]
    money_amounts: tuple[str, ...]
    deadlines: tuple[str, ...]
    actions: tuple[str, ...]
    decisions: tuple[str, ...]
    status: str | None
    topics: tuple[str, ...]
    typed_payload: dict[str, Any]
    evidence: tuple[EvidenceSpan, ...]
    confidence: float
    dedup_key: str


def classify_record_type(title: str, text: str, fallback: str) -> str:
    haystack = f"{title}\n{text[:16000]}".casefold()
    rules: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("procurement_rfp", ("request for proposals", "request for proposal", "rfp", "rfq", "invitation to bid")),
        ("contract_award", ("contract awarded", "notice of award", "award of contract", "awarded to")),
        ("planning_zoning_case", ("zoning", "planning commission", "board of zoning", "land use", "rezoning", "site plan")),
        ("permit", ("building permit", "permit number", "permit no.")),
        ("property_parcel_record", ("parcel", "property transfer", "assessor", "recorder")),
        ("meeting_minutes", ("meeting minutes", "approved minutes", "minutes of the")),
        ("agenda", ("agenda", "order of business")),
        ("ordinance", ("ordinance", "ord. no.")),
        ("resolution", ("resolution", "res. no.")),
        ("budget_financial_report", ("budget", "appropriation", "financial report", "fiscal year")),
        ("public_notice", ("public notice", "notice is hereby given")),
        ("newsletter", ("newsletter", "newsletters", "from the mayor")),
    )
    for record_type, phrases in rules:
        if any(phrase in haystack for phrase in phrases):
            return record_type
    if fallback in {"html", "pdf", "docx", "csv"}:
        return "general_webpage" if fallback == "html" else "unknown"
    return fallback if fallback in RECORD_TYPES else "unknown"


def canonicalize_document(
    *,
    processed: ProcessedDocument,
    source_agency: str,
    source_url: str,
    jurisdiction: str | None,
) -> CanonicalRecordDraft:
    """Create a conservative canonical projection from deterministic matches only."""

    text = processed.cleaned_text
    record_type = classify_record_type(processed.title, text, processed.document_type)
    evidence: list[EvidenceSpan] = []
    facts: list[str] = []

    def values(pattern: re.Pattern[str], field: str, *, group: int = 0) -> tuple[str, ...]:
        result: list[str] = []
        for match in pattern.finditer(text):
            value = match.group(group).strip()
            if value not in result:
                result.append(value)
                evidence.append(EvidenceSpan(field, value, match.group(0).strip(), match.start(), match.end(), 0.94))
        return tuple(result)

    addresses = values(ADDRESS_PATTERN, "addresses")
    parcel_numbers = values(PARCEL_PATTERN, "parcel_numbers", group=1)
    case_numbers = values(CASE_PATTERN, "case_numbers", group=1)
    permit_numbers = values(PERMIT_PATTERN, "permit_numbers", group=1)
    money_amounts = values(MONEY_PATTERN, "money_amounts")
    deadlines = values(DEADLINE_PATTERN, "deadlines")
    actions = values(ACTION_PATTERN, "actions")
    decisions = tuple(value for value in actions if re.search(r"\b(?:approved|denied|adopted|awarded)\b", value, re.I))
    for value in decisions:
        action = next(item for item in evidence if item.value == value)
        evidence.append(EvidenceSpan("decisions", value, action.source_text, action.start_offset, action.end_offset, 0.92))

    title_match = text.find(processed.title)
    if title_match >= 0:
        evidence.append(EvidenceSpan("title", processed.title, processed.title, title_match, title_match + len(processed.title), 0.99))
    summary = _summary(text)
    summary_offset = text.find(summary)
    if summary and summary_offset >= 0:
        evidence.append(EvidenceSpan("summary", summary, summary, summary_offset, summary_offset + len(summary), 0.75))
    if processed.publication_date is not None:
        date_evidence = next(
            (item for item in processed.metadata.get("date_candidates", []) if item.get("value") == processed.publication_date.isoformat()),
            None,
        )
        if date_evidence:
            evidence.append(
                EvidenceSpan(
                    "published_at", processed.publication_date.isoformat(), str(date_evidence["source_text"]),
                    int(date_evidence["start_offset"]), int(date_evidence["end_offset"]), 0.9,
                )
            )

    entities = _unique(entity.canonical_name for entity in processed.entities)
    people = _unique(entity.canonical_name for entity in processed.entities if entity.entity_type == "person")
    organizations = _unique(entity.canonical_name for entity in processed.entities if entity.entity_type == "organization")
    project_names = _projects(text, evidence)
    agenda_items = _agenda_items(text, evidence) if record_type in {"agenda", "planning_zoning_case"} else ()
    status = _status(record_type, actions)
    typed_payload = _typed_payload(
        record_type=record_type,
        agenda_items=agenda_items,
        addresses=addresses,
        permit_numbers=permit_numbers,
        case_numbers=case_numbers,
        money_amounts=money_amounts,
        organizations=organizations,
        actions=actions,
        decisions=decisions,
        deadlines=deadlines,
        parcel_numbers=parcel_numbers,
        project_names=project_names,
    )
    facts.extend([*permit_numbers, *case_numbers, *money_amounts, *deadlines, *decisions])
    dedup_material = "|".join(
        [record_type, source_url, *(permit_numbers or case_numbers or parcel_numbers or (processed.title,))]
    )
    return CanonicalRecordDraft(
        record_type=record_type,
        title=processed.title,
        jurisdiction=jurisdiction,
        source_agency=source_agency,
        source_url=source_url,
        source_document_id=source_url,
        published_at=processed.publication_date,
        event_date=_first_nonpublication_date(processed),
        effective_date=None,
        summary=summary,
        key_facts=_unique(facts),
        entities=entities,
        people=people,
        organizations=organizations,
        addresses=addresses,
        parcel_numbers=parcel_numbers,
        case_numbers=case_numbers,
        permit_numbers=permit_numbers,
        project_names=project_names,
        money_amounts=money_amounts,
        deadlines=deadlines,
        actions=actions,
        decisions=decisions,
        status=status,
        topics=tuple(str(topic) for topic in processed.metadata.get("topic_matches", [])),
        typed_payload=typed_payload,
        evidence=tuple(evidence),
        confidence=_confidence(record_type, evidence),
        dedup_key=sha256(dedup_material.casefold().encode()).hexdigest(),
    )


def _summary(text: str) -> str:
    sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
    for sentence in sentences:
        normalized = " ".join(sentence.split())
        if len(normalized) >= 35 and not normalized.casefold().startswith(("home", "skip to", "cookie")):
            return normalized[:600]
    return " ".join(text.split())[:600]


def _projects(text: str, evidence: list[EvidenceSpan]) -> tuple[str, ...]:
    pattern = re.compile(r"\b([A-Z][\w&.'-]*(?:\s+[A-Z][\w&.'-]*){1,6}\s+(?:Project|Development|Plan))\b")
    values: list[str] = []
    for match in pattern.finditer(text):
        value = match.group(1)
        if value not in values:
            values.append(value)
            evidence.append(EvidenceSpan("project_names", value, value, match.start(), match.end(), 0.82))
    return tuple(values)


def _agenda_items(text: str, evidence: list[EvidenceSpan]) -> tuple[str, ...]:
    items: list[str] = []
    for match in AGENDA_ITEM_PATTERN.finditer(text):
        value = match.group(1).strip()
        if value not in items:
            items.append(value)
            evidence.append(EvidenceSpan("agenda_items", value, match.group(0).strip(), match.start(1), match.end(1), 0.9))
    return tuple(items)


def _typed_payload(**values: Any) -> dict[str, Any]:
    record_type = values.pop("record_type")
    payloads = {
        "permit": ("permit_numbers", "addresses", "project_names", "money_amounts"),
        "planning_zoning_case": ("case_numbers", "addresses", "project_names", "agenda_items", "actions", "decisions"),
        "procurement_rfp": ("deadlines", "money_amounts", "organizations", "project_names"),
        "contract_award": ("organizations", "money_amounts", "actions", "decisions"),
        "agenda": ("agenda_items", "actions", "deadlines"),
        "ordinance": ("case_numbers", "actions", "decisions"),
        "resolution": ("case_numbers", "actions", "decisions"),
        "property_parcel_record": ("parcel_numbers", "addresses", "organizations"),
        "budget_financial_report": ("money_amounts", "project_names", "actions"),
    }
    return {field: list(values[field]) for field in payloads.get(record_type, ())}


def _status(record_type: str, actions: tuple[str, ...]) -> str | None:
    text = " ".join(actions).casefold()
    for label, words in (("approved", ("approved", "adopted", "awarded")), ("denied", ("denied",)), ("scheduled", ("scheduled", "hearing")), ("filed", ("filed",)), ("issued", ("issued",))):
        if any(word in text for word in words):
            return label
    if record_type == "procurement_rfp":
        return "open"
    return None


def _first_nonpublication_date(processed: ProcessedDocument) -> date | None:
    for candidate in processed.metadata.get("date_candidates", []):
        if not candidate.get("is_publication_date"):
            try:
                return date.fromisoformat(str(candidate["value"]))
            except (KeyError, ValueError):
                continue
    return None


def _confidence(record_type: str, evidence: list[EvidenceSpan]) -> float:
    if record_type == "unknown":
        return 0.45
    return min(0.98, 0.62 + min(len(evidence), 9) * 0.035)


def _unique(values: Any) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = str(value).strip()
        if normalized and normalized.casefold() not in seen:
            seen.add(normalized.casefold())
            result.append(normalized)
    return tuple(result)


def parse_money_amount(value: str) -> Decimal | None:
    """A helper for callers that need numeric values without silently coercing malformed text."""
    try:
        return Decimal(value.replace("$", "").replace(",", ""))
    except (InvalidOperation, ValueError):
        return None


def canonical_signal_candidates(
    draft: CanonicalRecordDraft, *, change_types: tuple[str, ...]
) -> tuple[FounderSignalCandidate, ...]:
    """Create commercial signals from a canonical type/change, never from raw blobs.

    The text and offsets supplied to Founder Intelligence come from the canonical
    record's evidence list, which itself points to the immutable raw version.
    """

    if not change_types:
        return ()
    mappings = {
        "procurement_rfp": ("procurement", "local contractors", "Review the solicitation and prepare a qualified response."),
        "contract_award": ("procurement", "suppliers and subcontractors", "Identify awarded vendors and adjacent subcontracting needs."),
        "permit": ("development", "construction and professional services", "Review the permit and contact the project team with a relevant offer."),
        "planning_zoning_case": ("zoning_land_use", "developers and land-use professionals", "Review the case record before the next public decision point."),
        "budget_financial_report": ("public_spending", "public-sector vendors", "Review funded line items for near-term procurement or partnership needs."),
    }
    mapping = mappings.get(draft.record_type)
    if mapping is None:
        return ()
    signal_type, segment, action = mapping
    if draft.record_type == "planning_zoning_case" and "zoning_approved" in change_types:
        signal_type = "zoning_land_use"
    evidence = next(
        (item for item in draft.evidence if item.field_name in {"actions", "money_amounts", "permit_numbers", "case_numbers", "summary"}),
        None,
    )
    if evidence is None:
        return ()
    detail = draft.money_amounts[0] if draft.money_amounts else draft.status or draft.record_type.replace("_", " ")
    summary = f"{draft.title}: {detail}."
    return (
        FounderSignalCandidate(
            signal_type=signal_type,
            title=draft.title,
            summary=summary,
            why_it_matters=f"A verified {draft.record_type.replace('_', ' ')} may create a near-term commercial opening.",
            where_money_may_be=f"{segment.capitalize()} may need services related to this civic action.",
            economic_value_score=0.8 if draft.money_amounts else 0.65,
            confidence_score=draft.confidence,
            recency_score=0.8,
            urgency_score=0.8 if draft.deadlines else 0.6,
            evidence_strength_score=evidence.confidence,
            actionability_score=0.75,
            affected_organizations=draft.organizations or (draft.source_agency,),
            potential_customer_segments=(segment,),
            action_to_take=action,
            evidence_excerpt=evidence.source_text,
            evidence_start_offset=evidence.start_offset,
            evidence_end_offset=evidence.end_offset,
        ),
    )
