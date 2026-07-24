# CivicOS repository structure

## Purpose

This repository is a deliberately small monorepo. It separates deployable boundaries now so that future features do not couple the resident-facing web application, public API, long-running ingestion work, model access, and persistence concerns.

No directory may import another directory’s implementation by filesystem path. Shared contracts, when needed, must be introduced deliberately with an ADR and a versioned package or generated API client.

## Directory map

| Path | Responsibility | Current state |
|---|---|---|
| `frontend/` | Next.js App Router UI; accessibility, presentation, and typed API client only | runnable scaffold |
| `backend/` | FastAPI public/operator API; OIDC authentication, authorization, and request orchestration | production-hardened API baseline |
| `ingestion/` | policy-bound source discovery, retrieval, extraction, versioning, and durable job workers | runnable autonomous discovery worker |
| `ai/` | provider adapters, embedding/inference policy, and model audit metadata | reserved; no implementation |
| `database/` | migrations, schema documentation, jurisdiction seeds, and migration/seed checks | PostgreSQL schema through daily briefings; St. Joseph County configuration seed |
| `infrastructure/` | local/initial Compose topology and deployment documentation | Compose baseline |
| `docs/` | decisions, runbooks, governance, contributor documentation | repository guide |
| `outputs/` | user-facing planning artifacts created during architecture work | architecture proposal |

## Dependency direction

```text
frontend  -> backend API contract
backend   -> database contracts, ai interfaces
ingestion -> database contracts, ai interfaces, object storage
ai        -> approved model providers only
database  -> PostgreSQL migrations and metadata
infrastructure -> deploys boundaries; owns no domain logic
```

The `frontend` never connects to PostgreSQL, Qdrant, object storage, or a model provider. The API never performs long-running ingestion work. Qdrant remains a rebuildable projection, not an authority for permissions or source content.

## Configuration

`.env.example` is the complete local configuration contract. Copy it to `.env` for local use; `.env` is ignored by Git. `CIVICOS_API_CORS_ORIGINS` is a JSON array because the API validates it as a list. Values containing secrets must never be prefixed with `NEXT_PUBLIC_`, included in browser bundles, logged, committed, or copied into issues.

Each service reads only the variables it owns. New variables require a documented default or a fail-fast required setting, an `.env.example` entry, and documentation of whether they are confidential.

## Local commands

```sh
# Install JavaScript dependencies and create the committed lockfile.
corepack enable
pnpm install

# Web checks
pnpm frontend:lint
pnpm frontend:typecheck
pnpm frontend:build

# API checks
cd backend
python3.12 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
ruff check .
mypy src tests
pytest

# Discovery worker checks
cd ../ingestion
python3.12 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
ruff check .
mypy src tests
pytest

# Containers
docker compose --env-file .env -f infrastructure/docker-compose.yml up --build
```

## CI/CD

GitHub Actions runs frontend lint/type/build, backend lint/type/test, discovery-worker lint/type/test, clean PostgreSQL migrations/tests, a twice-applied St. Joseph County seed idempotency check, and a Docker Compose configuration validation on pull requests and the default branch. The release workflow is intentionally not created: publishing images or deploying infrastructure requires approval of hosting, image registry, secret management, and environment promotion policy.

See `docs/production-operations.md` for production deployment, security, monitoring, backup, and recovery responsibilities.

`pnpm-lock.yaml` is committed and CI enforces immutable JavaScript installs. Python dependencies are exact-pinned in each Python package's `pyproject.toml` until a reviewed lockfile strategy is introduced.

## Architectural decisions

Record cross-cutting decisions in `docs/adr/` using the template below. Do not change tenancy, hosting, model egress, source policy, database authority, or authentication design without an approved ADR and user approval where required.

### ADR template

```md
# ADR-NNN: Short title

**Status:** Proposed | Accepted | Superseded

## Context

## Decision

## Consequences

## Alternatives considered
```
