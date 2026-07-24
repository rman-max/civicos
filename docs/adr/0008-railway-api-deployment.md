# 0008: Railway API deployments use repository-root Docker builds and tracked pre-deploy migrations

## Status

Accepted

## Context

The Railway API service needs the backend package and the canonical SQL migrations. A
`/backend` build root excludes `/database/migrations`, which prevents a safe pre-deploy
migration step. Reapplying raw SQL files without a ledger is also unsafe because most
forward migrations are intentionally non-idempotent.

## Decision

The Railway API service uses the repository root as its build context and
`backend/Dockerfile` as its Dockerfile. The image includes the canonical migration files.
`python -m civicos_api.migrations` runs as Railway's pre-deploy command. It records each
applied migration filename and SHA-256 checksum in `public.civicos_schema_migrations`,
applies only unapplied files, and refuses to continue if a recorded migration changes.

The API image starts with Railway's injected `PORT`; it falls back to `8000` only for
local container use. Railway checks `/readyz`, which verifies PostgreSQL connectivity,
before accepting a deployment.

## Consequences

The Railway service root must be the repository root, with config-as-code explicitly set
to `/backend/railway.toml`. Database migrations are atomic within their existing SQL
transactions and block an unsafe API rollout if they fail. The migration ledger is an
operational record, not tenant-owned civic data.
