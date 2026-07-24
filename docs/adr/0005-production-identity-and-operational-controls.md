# ADR 0005: Use OIDC and database-authoritative tenant membership

**Status:** Accepted  
**Date:** 2026-07-24

## Context

Early API routes accepted tenant and user identifiers from request headers. That is development scaffolding, not production authentication. CivicOS needs account administration without passwords or a proprietary identity-provider dependency.

## Decision

Production routes require RS256 OIDC bearer access tokens. The API validates issuer, audience, expiry, and JWKS signature, then resolves the token subject and tenant claim to an active PostgreSQL membership. The IdP authenticates people; CivicOS owns membership status and application roles.

Migration `0007` provides narrowly scoped security-definer functions for identity resolution and tenant-admin user management. It adds membership activation and prevents removal of the final tenant administrator. Verified identity replaces client-supplied tenant scope headers.

Structured logs, protected metrics, health endpoints, bounded request handling, HTTP security headers, backup tooling, and a provider-neutral operational runbook are part of the production baseline.

## Consequences

- CivicOS never stores passwords and supports self-hosted or managed OIDC providers.
- A valid token cannot access a tenant without an active CivicOS membership, allowing immediate application-level revocation.
- Only the provisioner has `BYPASSRLS`; the API has narrowly granted function execution rights.
- Development preserves the local header-based scaffold, while production startup refuses it.
- TLS, distributed rate limits, secret management, backup replication, image signing, and alert delivery remain deployment responsibilities documented in the runbook.
