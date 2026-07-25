# Canonical civic records

## Decision

CivicOS treats crawled pages, files, and extracted text as immutable raw evidence. A separate, versioned canonical-record projection makes those sources usable for civic intelligence without replacing or rewriting them.

## Layers

1. `civic.documents`, `civic.document_versions`, `civic.document_artifacts`, and `civic.source_observations` preserve source URL, agency, fetch timing, publication metadata, raw text, content hashes, artifacts, and connector provenance.
2. `civic.canonical_records` presents the current civic interpretation: controlled type, jurisdiction, agency, dates, facts, entities, locations, identifiers, money, deadlines, actions, status, topics, and typed payload.
3. `civic.canonical_record_versions` snapshots each projection against its immutable raw document version. `civic.canonical_record_evidence` stores exact source spans for every extracted fact. `civic.canonical_record_changes` records field-level changes.

No canonical field is accepted without source text and a source URL. The deterministic extractor is intentionally conservative; ambiguous material stays `unknown` or `general_webpage` until a source-specific parser or an evidence-bound model extractor is added.

## Extraction policy

The first implementation uses deterministic type rules and patterns for identifiers, addresses, money, deadlines, actions, decisions, entities, and agenda-like items. It records offsets into the source text and uses a versioned extraction label (`canonical-deterministic-v1`). Model-based extraction is an optional future stage: it must return the same evidence contract and cannot overwrite raw material or ungrounded fields.

## Deduplication and change detection

Records have a tenant-scoped deterministic natural key derived from record type, source URL, and a civic identifier when one exists. Repeated scans do not duplicate raw versions or canonical records. Changed raw content creates a new raw version and canonical snapshot; the projection compares structured fields and creates explicit field-level changes. New canonical records generate `new_record` events.

Founder signals are produced only after a canonical record and change event exist. Their evidence is tied to the canonical evidence span, which links back to the original public source.
