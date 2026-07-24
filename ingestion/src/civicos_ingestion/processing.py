from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import asdict
from datetime import date, datetime

from civicos_ingestion.founder_intelligence import detect_founder_signals
from civicos_ingestion.models import (
    DateCandidate,
    DepartmentCandidate,
    DiscoveredRelationship,
    EntityMention,
    ExtractedDocument,
    GraphNodeCandidate,
    ProcessedDocument,
    ProcessingContext,
    TopicCandidate,
)

PROCESSOR_VERSION = "deterministic-v1"
MAX_DATE_CANDIDATES = 25
MAX_ENTITY_MENTIONS = 100
MAX_GRAPH_RELATIONSHIPS = 100

GRAPH_PREDICATES = {
    "meeting": "references_meeting",
    "ordinance": "references_ordinance",
    "budget": "references_budget",
    "official": "mentions_official",
    "project": "references_project",
    "location": "mentions_location",
}

DOCUMENT_TYPE_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("meeting_agenda", ("agenda", "order of business")),
    ("meeting_minutes", ("minutes", "approved minutes")),
    ("ordinance", ("ordinance", "ord. no.")),
    ("resolution", ("resolution", "res. no.")),
    ("budget", ("budget", "appropriation", "fiscal year")),
    ("public_notice", ("public notice", "notice is hereby given")),
    ("report", ("annual report", "report")),
)

DATE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?P<value>\d{4}-\d{2}-\d{2})\b"),
    re.compile(r"\b(?P<value>\d{1,2}/\d{1,2}/\d{4})\b"),
    re.compile(
        r"\b(?P<value>(?:January|February|March|April|May|June|July|August|September|October|November|December)"
        r"\s+\d{1,2},\s+\d{4})\b",
        re.IGNORECASE,
    ),
)
PUBLICATION_PREFIX = re.compile(r"(?:published|posted|issued|date)\s*[:\-]?\s*$", re.IGNORECASE)
PERSON_PATTERN = re.compile(
    r"\b(?P<title>Mayor|Council(?:member|man|woman)?|Commissioner|Chair(?:person)?|Dr\.|Mr\.|Ms\.|Mrs\.)\s+"
    r"(?P<name>[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b"
)
ORGANIZATION_PATTERN = re.compile(
    r"\b(?P<name>(?:[A-Z][\w&.'-]*\s+){0,5}"
    r"(?:County|City|Town|Village|Department|Office|Board|Commission|Authority|University|School))\b"
)
OFFICIAL_TITLES = {"mayor", "councilmember", "councilman", "councilwoman", "commissioner", "chair", "chairperson"}


def clean_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).replace("\r\n", "\n").replace("\r", "\n")
    normalized = "".join(character for character in normalized if character == "\n" or character >= " ")
    lines = [re.sub(r"[\t ]+", " ", line).strip() for line in normalized.split("\n")]
    return "\n".join(line for line in lines if line)


def process_document(document: ExtractedDocument, context: ProcessingContext) -> ProcessedDocument:
    cleaned_text = clean_text(document.text)
    dates = extract_dates(cleaned_text)
    department = identify_department(cleaned_text, context.departments)
    topics = identify_topics(cleaned_text, context.topics)
    entities = extract_entities(cleaned_text)
    relationships = discover_relationships(cleaned_text, context.graph_nodes)
    founder_signals = detect_founder_signals(title=document.title, text=cleaned_text, entities=entities)
    document_type = classify_document_type(document.title, cleaned_text, document.document_type)
    publication_date = next((candidate.value for candidate in dates if candidate.is_publication_date), None)
    metadata = {
        "processor_version": PROCESSOR_VERSION,
        "file_type": document.document_type,
        "word_count": len(cleaned_text.split()),
        "character_count": len(cleaned_text),
        "date_candidates": [date_candidate_to_metadata(candidate) for candidate in dates],
        "department_match": department.name if department else None,
        "topic_matches": [topic.name for topic in topics],
        "entity_count": len(entities),
        "relationship_count": len(relationships),
        "founder_signal_types": [signal.signal_type for signal in founder_signals],
        "relationship_matches": [
            {
                "object_type": relationship.object_type,
                "object_id": str(relationship.object_id),
                "predicate": relationship.predicate,
                "mention_text": relationship.mention_text,
                "start_offset": relationship.start_offset,
                "end_offset": relationship.end_offset,
                "confidence": relationship.confidence,
            }
            for relationship in relationships
        ],
        "extraction": document.metadata,
    }
    return ProcessedDocument(
        title=document.title,
        document_type=document_type,
        cleaned_text=cleaned_text,
        publication_date=publication_date,
        department_id=department.id if department else None,
        topic_ids=tuple(topic.id for topic in topics),
        entities=tuple(entities),
        relationships=relationships,
        founder_signals=founder_signals,
        metadata=metadata,
    )


def classify_document_type(title: str, text: str, fallback: str) -> str:
    searchable = f"{title}\n{text[:12000]}".casefold()
    best_type = fallback
    best_score = 0
    for document_type, phrases in DOCUMENT_TYPE_RULES:
        score = sum(searchable.count(phrase) for phrase in phrases)
        if score > best_score:
            best_type = document_type
            best_score = score
    return best_type


def extract_dates(text: str) -> tuple[DateCandidate, ...]:
    candidates: list[DateCandidate] = []
    seen: set[tuple[date, int]] = set()
    for pattern in DATE_PATTERNS:
        for match in pattern.finditer(text):
            parsed = parse_date(match.group("value"))
            if parsed is None or (parsed, match.start()) in seen:
                continue
            prefix = text[max(0, match.start() - 32) : match.start()]
            candidates.append(
                DateCandidate(
                    value=parsed,
                    source_text=match.group("value"),
                    start_offset=match.start(),
                    end_offset=match.end(),
                    is_publication_date=bool(PUBLICATION_PREFIX.search(prefix)),
                )
            )
            seen.add((parsed, match.start()))
            if len(candidates) >= MAX_DATE_CANDIDATES:
                return tuple(candidates)
    return tuple(sorted(candidates, key=lambda candidate: candidate.start_offset))


def parse_date(value: str) -> date | None:
    for date_format in ("%Y-%m-%d", "%m/%d/%Y", "%B %d, %Y"):
        try:
            return datetime.strptime(value, date_format).date()
        except ValueError:
            continue
    return None


def identify_department(text: str, departments: Iterable[DepartmentCandidate]) -> DepartmentCandidate | None:
    matches = [department for department in departments if phrase_occurs(text, department.name)]
    return max(matches, key=lambda department: len(department.name), default=None)


def identify_topics(text: str, topics: Iterable[TopicCandidate]) -> tuple[TopicCandidate, ...]:
    return tuple(topic for topic in topics if phrase_occurs(text, topic.name))


def discover_relationships(text: str, graph_nodes: Iterable[GraphNodeCandidate]) -> tuple[DiscoveredRelationship, ...]:
    relationships: list[DiscoveredRelationship] = []
    seen: set[tuple[str, object]] = set()
    for node in graph_nodes:
        predicate = GRAPH_PREDICATES.get(node.node_type)
        if predicate is None:
            continue
        match = phrase_match(text, node.name)
        if match is None or (node.node_type, node.id) in seen:
            continue
        relationships.append(
            DiscoveredRelationship(
                object_type=node.node_type,
                object_id=node.id,
                predicate=predicate,
                mention_text=match.group(),
                start_offset=match.start(),
                end_offset=match.end(),
                confidence=0.900,
            )
        )
        seen.add((node.node_type, node.id))
        if len(relationships) >= MAX_GRAPH_RELATIONSHIPS:
            break
    return tuple(relationships)


def phrase_occurs(text: str, phrase: str) -> bool:
    return phrase_match(text, phrase) is not None


def phrase_match(text: str, phrase: str) -> re.Match[str] | None:
    normalized_phrase = clean_text(phrase)
    if not normalized_phrase:
        return None
    return re.search(rf"(?<!\w){re.escape(normalized_phrase)}(?!\w)", text, re.IGNORECASE)


def extract_entities(text: str) -> tuple[EntityMention, ...]:
    matches: list[EntityMention] = []
    seen: set[tuple[str, str, int]] = set()
    for pattern, entity_type in ((PERSON_PATTERN, "person"), (ORGANIZATION_PATTERN, "organization")):
        for match in pattern.finditer(text):
            name = match.group("name").strip()
            key = (entity_type, name.casefold(), match.start("name"))
            if key in seen:
                continue
            matches.append(
                EntityMention(
                    canonical_name=name,
                    entity_type=entity_type,
                    official_title=official_title_for(match.groupdict().get("title")),
                    mention_text=name,
                    start_offset=match.start("name"),
                    end_offset=match.end("name"),
                )
            )
            seen.add(key)
            if len(matches) >= MAX_ENTITY_MENTIONS:
                return tuple(matches)
    return tuple(sorted(matches, key=lambda entity: entity.start_offset))


def official_title_for(title: str | None) -> str | None:
    if title is None:
        return None
    normalized_title = title.rstrip(".")
    return normalized_title if normalized_title.casefold() in OFFICIAL_TITLES else None


def date_candidate_to_metadata(candidate: DateCandidate) -> dict[str, object]:
    return asdict(candidate) | {"value": candidate.value.isoformat()}
