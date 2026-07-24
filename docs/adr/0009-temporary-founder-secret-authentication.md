# ADR 0009: Temporary founder-secret authentication

## Status

Accepted for the initial private production deployment.

## Decision

When `CIVICOS_AUTH_MODE=founder_secret`, CivicOS exposes one private login endpoint which exchanges a Railway-held secret for a short-lived signed bearer token. It creates or verifies exactly one configured `tenant_admin` founder membership in the pre-deploy process. The database remains the authority for active user and tenant membership on every authenticated request.

## Consequences

The mode has no anonymous API access, account registration, recovery flow, or user discovery. Its secret is server-only and must be at least 32 characters. It is a deliberate temporary mode, not a general authentication system. Migration to Clerk or Auth0 retains the same database identity and membership model: switch to `oidc` and configure issuer, audience, and JWKS values.
