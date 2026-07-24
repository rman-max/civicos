"""Deterministic, evidence-bound founder intelligence detection.

This module intentionally identifies *signals*, not contract awards, financial
outcomes, or specific buyers. Commercial significance is a transparent ranking
heuristic; the source excerpt remains the authority for every result.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from civicos_ingestion.models import EntityMention, FounderSignalCandidate

SCORE_WEIGHTS = {
    "economic_value": 0.30,
    "confidence": 0.20,
    "recency": 0.15,
    "urgency": 0.15,
    "evidence_strength": 0.10,
    "actionability": 0.10,
}
MAX_SIGNALS_PER_DOCUMENT = 8
MAX_EXCERPT_CHARACTERS = 480


@dataclass(frozen=True)
class SignalRule:
    signal_type: str
    phrases: tuple[str, ...]
    why_it_matters: str
    where_money_may_be: str
    customer_segments: tuple[str, ...]
    action_to_take: str
    economic_value: float
    urgency: float
    actionability: float


SIGNAL_RULES: tuple[SignalRule, ...] = (
    SignalRule(
        "procurement",
        (
            "request for proposals",
            "request for qualifications",
            "rfp",
            "rfq",
            "invitation to bid",
            "bid opening",
            "procurement",
        ),
        "A government purchasing process may create a near-term vendor or advisory need.",
        "A bid, professional-services engagement, or related supplier demand may follow.",
        ("local contractors", "professional services firms", "specialty suppliers"),
        "Read the solicitation and calendar; identify eligibility, deadlines, and incumbent context.", 0.88, 0.92, 0.94,
    ),
    SignalRule(
        "development",
        (
            "development agreement",
            "site plan",
            "redevelopment",
            "subdivision",
            "economic development",
            "construction plan",
        ),
        "A proposed or advancing development can create demand before work reaches the market.",
        "Planning, construction, utilities, and adjacent business services may be needed.",
        ("developers", "construction firms", "engineering and design firms"),
        "Confirm project stage, decision dates, and named applicants before outreach.", 0.84, 0.72, 0.78,
    ),
    SignalRule(
        "zoning_land_use", ("rezoning", "zoning", "land use", "variance", "special use", "planned unit development"),
        "A land-use action can change what may be built, operated, or financed in an area.",
        "Entitlement, property, design, and compliance services may be relevant.",
        ("property owners", "real-estate professionals", "land-use consultants"),
        "Check the parcel, hearing date, and proposed use; validate the applicable zoning record.", 0.76, 0.68, 0.74,
    ),
    SignalRule(
        "public_spending",
        (
            "appropriation",
            "capital improvement",
            "not to exceed",
            "change order",
            "budget amendment",
            "additional funding",
        ),
        "A spending decision may indicate a funded initiative or a material change in scope.",
        "Approved funding can precede purchasing, subcontracting, or implementation work.",
        ("government vendors", "construction firms", "financial and advisory firms"),
        "Locate the amount, funding source, and next procurement or approval step.", 0.82, 0.75, 0.82,
    ),
    SignalRule(
        "grant_funding",
        ("grant award", "grant funding", "notice of funding", "federal grant", "state grant", "grant application"),
        "Grant activity can create funded programs, compliance work, or future implementation demand.",
        "Funded recipients may need delivery partners, reporting support, or specialized services.",
        ("nonprofits", "grant consultants", "implementation vendors"),
        "Verify award status, recipient, amount, allowable uses, and procurement requirements.", 0.74, 0.70, 0.76,
    ),
    SignalRule(
        "infrastructure",
        ("infrastructure", "roadway", "bridge", "water main", "sewer", "utility improvement", "transportation project"),
        "Infrastructure activity can unlock a long chain of engineering, construction, and supplier demand.",
        "Design, construction, materials, inspection, and nearby development activity may follow.",
        ("engineering firms", "contractors", "materials suppliers"),
        "Establish the phase, funding status, delivery method, and anticipated procurement path.", 0.90, 0.78, 0.86,
    ),
    SignalRule(
        "business_regulation",
        (
            "license requirement",
            "permit requirement",
            "business regulation",
            "compliance requirement",
            "fee schedule",
            "ordinance amendment",
        ),
        "A regulatory change may create compliance work or alter operating conditions for businesses.",
        "Affected firms may need legal, compliance, operational, or communications support.",
        ("regulated businesses", "legal and compliance firms", "trade associations"),
        "Confirm the effective date, affected business types, and enforcement or guidance details.", 0.62, 0.65, 0.70,
    ),
    SignalRule(
        "unusual_change_indicator", ("emergency", "sole source", "waiver", "change order", "amendment", "unexpected"),
        "This language can indicate a material exception or change that merits founder review.",
        "The record may reveal an emerging need, a changed scope, or a time-sensitive follow-up.",
        ("specialized vendors", "risk and compliance advisers", "local service providers"),
        "Review the underlying record and surrounding approvals before treating it as an opportunity.",
        0.48,
        0.55,
        0.58,
    ),
)


def opportunity_score(candidate: FounderSignalCandidate) -> int:
    """Calculate the documented 0–100 weighted commercial-opportunity score."""

    weighted = (
        SCORE_WEIGHTS["economic_value"] * candidate.economic_value_score
        + SCORE_WEIGHTS["confidence"] * candidate.confidence_score
        + SCORE_WEIGHTS["recency"] * candidate.recency_score
        + SCORE_WEIGHTS["urgency"] * candidate.urgency_score
        + SCORE_WEIGHTS["evidence_strength"] * candidate.evidence_strength_score
        + SCORE_WEIGHTS["actionability"] * candidate.actionability_score
    )
    return round(100 * weighted)


def detect_founder_signals(
    *, title: str, text: str, entities: tuple[EntityMention, ...]
) -> tuple[FounderSignalCandidate, ...]:
    searchable = f"{title}\n{text}"
    affected_organizations = tuple(
        dict.fromkeys(entity.canonical_name for entity in entities if entity.entity_type == "organization")
    )[:6]
    candidates: list[FounderSignalCandidate] = []
    for rule in SIGNAL_RULES:
        matches = [match for phrase in rule.phrases if (match := _phrase_match(searchable, phrase)) is not None]
        if not matches:
            continue
        first_match = matches[0]
        evidence_start = max(0, first_match.start() - 160)
        evidence_end = min(len(searchable), first_match.end() + 320)
        excerpt = " ".join(searchable[evidence_start:evidence_end].split())[:MAX_EXCERPT_CHARACTERS]
        keyword_count = min(len(matches), 3)
        confidence = min(0.95, 0.62 + keyword_count * 0.11)
        evidence_strength = min(0.95, 0.58 + keyword_count * 0.12)
        candidates.append(
            FounderSignalCandidate(
                signal_type=rule.signal_type,
                title=f"{_humanize(rule.signal_type)}: {title}",
                summary=f"Detected {rule.signal_type.replace('_', ' ')} language in a newly observed civic record.",
                why_it_matters=rule.why_it_matters,
                where_money_may_be=rule.where_money_may_be,
                economic_value_score=rule.economic_value,
                confidence_score=confidence,
                recency_score=1.0,
                urgency_score=rule.urgency,
                evidence_strength_score=evidence_strength,
                actionability_score=rule.actionability,
                affected_organizations=affected_organizations,
                potential_customer_segments=rule.customer_segments,
                action_to_take=rule.action_to_take,
                evidence_excerpt=excerpt,
                evidence_start_offset=evidence_start,
                evidence_end_offset=evidence_end,
            )
        )
    return tuple(sorted(candidates, key=opportunity_score, reverse=True)[:MAX_SIGNALS_PER_DOCUMENT])


def _phrase_match(text: str, phrase: str) -> re.Match[str] | None:
    return re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text, re.IGNORECASE)


def _humanize(value: str) -> str:
    return value.replace("_", " ").title()
