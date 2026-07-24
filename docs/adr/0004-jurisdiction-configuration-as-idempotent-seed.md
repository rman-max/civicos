# ADR 0004: Configure jurisdictions as idempotent data seeds

**Status:** Accepted  
**Date:** 2026-07-24

## Context

CivicOS needs a first production jurisdiction without embedding St. Joseph County URLs, schedules, departments, or municipal boundaries in application code. The discovery worker already treats `civic.sources` as its sole input and creates a durable job when an active source is inserted.

## Decision

Store the St. Joseph County rollout as an idempotent SQL seed. It creates the tenant, municipalities, department assignments, and official source records, each with a source-specific acquisition policy, interval, page cap, and timeout. The seed inserts missing data but does not overwrite existing operator changes.

Extend acquisition policy with `allowed_path_prefixes`. The crawler validates absolute paths and applies the scope to its initial URL, discovered links, and final redirects. The previous domain-only behavior remains the default for existing sources through `['/']`.

## Consequences

- Jurisdiction-specific values remain auditable database configuration rather than application constants.
- Active seeded sources automatically enqueue work; enabling the discovery worker starts recurring ingestion without an application release.
- Path scoping protects relevant County connectors from drifting across an entire official host, while page caps remain a second safety boundary.
- Applying a seed requires the existing privileged provisioning role because the tenant does not yet exist. The API and worker remain without `BYPASSRLS`.
- Source coverage is intentionally conservative. New sites, APIs, authenticated portals, or changed source policies require explicit configuration and review.
