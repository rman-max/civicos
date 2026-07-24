# ADR 0007: Founder intelligence is evidence-bound and deterministic first

**Status:** Accepted

## Context

CivicOS needs a private founder workspace that turns continuously ingested public civic records into commercially useful leads. The product must be useful without a founder manually collecting records, but must not invent contract awards, commercial outcomes, or target-customer claims.

## Decision

Create a separate `founder` PostgreSQL schema with version-linked signals, opportunities, watchlists, and durable daily-brief jobs. Detect the initial signal taxonomy deterministically at document-version persistence. Persist source URL, excerpt, offsets, signal factors, and a documented weighted score. Generate the Founder Brief extractively from newly discovered opportunities above an environment-configured threshold.

Expose this data only via authenticated `/v1/founder` endpoints that require a `tenant_admin` membership both at the API edge and in PostgreSQL security-definer functions. Keep its route out of public-beta navigation.

## Consequences

- Commercial leads are explainable, idempotent, and auditable against immutable source versions.
- Ranking policy can improve independently of civic ingestion and retrieval.
- Early taxonomy coverage is intentionally heuristic rather than an opaque market-prediction model.
- Watchlists are stored now; proactive matching notifications remain a separately scoped delivery feature.
