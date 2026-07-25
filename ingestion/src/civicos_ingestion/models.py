from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class Source:
    id: UUID
    organization_id: UUID
    name: str
    canonical_url: str
    acquisition_policy: dict[str, Any]
    scan_interval_seconds: int
    max_pages_per_scan: int
    request_timeout_seconds: int


@dataclass(frozen=True)
class DiscoveryJob:
    id: UUID
    source: Source
    lease_token: UUID


@dataclass(frozen=True)
class FetchedResource:
    source_url: str
    final_url: str
    status_code: int
    media_type: str
    body: bytes
    etag: str | None
    last_modified: str | None


@dataclass(frozen=True)
class ExtractedDocument:
    title: str
    document_type: str
    text: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class DepartmentCandidate:
    id: UUID
    name: str


@dataclass(frozen=True)
class TopicCandidate:
    id: UUID
    name: str


@dataclass(frozen=True)
class GraphNodeCandidate:
    id: UUID
    node_type: str
    name: str


@dataclass(frozen=True)
class ProcessingContext:
    departments: tuple[DepartmentCandidate, ...]
    topics: tuple[TopicCandidate, ...]
    graph_nodes: tuple[GraphNodeCandidate, ...] = ()


@dataclass(frozen=True)
class DateCandidate:
    value: date
    source_text: str
    start_offset: int
    end_offset: int
    is_publication_date: bool


@dataclass(frozen=True)
class EntityMention:
    canonical_name: str
    entity_type: str
    official_title: str | None
    mention_text: str
    start_offset: int
    end_offset: int


@dataclass(frozen=True)
class DiscoveredRelationship:
    object_type: str
    object_id: UUID
    predicate: str
    mention_text: str
    start_offset: int
    end_offset: int
    confidence: float


@dataclass(frozen=True)
class FounderSignalCandidate:
    """An evidence-bound commercial signal detected from one document version."""

    signal_type: str
    title: str
    summary: str
    why_it_matters: str
    where_money_may_be: str
    economic_value_score: float
    confidence_score: float
    recency_score: float
    urgency_score: float
    evidence_strength_score: float
    actionability_score: float
    affected_organizations: tuple[str, ...]
    potential_customer_segments: tuple[str, ...]
    action_to_take: str
    evidence_excerpt: str
    evidence_start_offset: int
    evidence_end_offset: int


@dataclass(frozen=True)
class ProcessedDocument:
    title: str
    document_type: str
    cleaned_text: str
    publication_date: date | None
    department_id: UUID | None
    topic_ids: tuple[UUID, ...]
    entities: tuple[EntityMention, ...]
    relationships: tuple[DiscoveredRelationship, ...]
    founder_signals: tuple[FounderSignalCandidate, ...]
    metadata: dict[str, Any]


@dataclass(frozen=True)
class PersistedDocument:
    document_id: UUID
    version_id: UUID | None
    changed: bool


@dataclass(frozen=True)
class VectorIndexJob:
    id: UUID
    lease_token: UUID
    organization_id: UUID
    document_id: UUID
    document_version_id: UUID
    title: str
    document_type: str
    source_id: UUID | None
    department_id: UUID | None
    published_at: date | None
    extracted_text: str
    topic_ids: tuple[UUID, ...]


@dataclass(frozen=True)
class DailyBriefingJob:
    id: UUID
    lease_token: UUID
    organization_id: UUID
    briefing_date: date


@dataclass(frozen=True)
class FounderBriefJob:
    id: UUID
    lease_token: UUID
    organization_id: UUID
    briefing_date: date


@dataclass
class ScanSummary:
    pages_crawled: int = 0
    documents_discovered: int = 0
    documents_changed: int = 0
    documents_skipped: int = 0
    documents_indexed: int = 0
    observed_at: datetime = field(default_factory=datetime.now)
