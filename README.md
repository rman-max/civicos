# CivicOS

CivicOS is an open-source civic intelligence platform, beginning with St. Joseph County, Indiana and designed to scale to any municipality.

This repository contains the platform foundation and an autonomous, policy-bound discovery worker. Its first jurisdiction configuration is an idempotent seed for St. Joseph County, Indiana; all jurisdiction-specific values remain in database configuration rather than application code.

## Prerequisites

- Node.js 22 or later with Corepack enabled
- Python 3.12 or later
- Docker Engine with Docker Compose v2

## Quick start

1. Copy `.env.example` to `.env` and replace development passwords before any shared deployment.
2. Run `docker compose --env-file .env -f infrastructure/docker-compose.yml up --build`.
3. Visit `http://localhost:3000` for the web scaffold and `http://localhost:8000/healthz` for API health.

Qdrant is included in the default Compose topology. Configure the OpenAI-compatible embedding endpoint before semantic indexing is enabled:

```sh
docker compose --env-file .env -f infrastructure/docker-compose.yml up --build
```

The `discovery` profile runs the autonomous ingestion worker. Configure an S3-compatible artifact store and provision the database role described in `docs/autonomous-discovery.md` before enabling it:

```sh
docker compose --env-file .env -f infrastructure/docker-compose.yml --profile discovery up --build
```

## Repository guide

See [docs/repository-structure.md](docs/repository-structure.md) for ownership boundaries, local development instructions, configuration rules, and CI/CD behavior. Product vision and rollout strategy are in [docs/product-strategy.md](docs/product-strategy.md); ingestion enrichment, graph, hybrid retrieval, grounded-assistant, research-notebook, and daily-briefing behavior are documented in [docs/document-processing.md](docs/document-processing.md), [docs/knowledge-graph.md](docs/knowledge-graph.md), [docs/search.md](docs/search.md), [docs/assistant.md](docs/assistant.md), [docs/research-notebooks.md](docs/research-notebooks.md), and [docs/daily-briefings.md](docs/daily-briefings.md). The proposed system design is retained in [outputs/civicos-architecture.md](outputs/civicos-architecture.md).

To configure the first deployment after applying migrations, follow [docs/st-joseph-county-indiana.md](docs/st-joseph-county-indiana.md). This creates only approved public-source connectors and their recurring discovery jobs; it does not create user accounts or bypass source access controls.

Production deployment, OIDC authentication, monitoring, backup, recovery, and security requirements are in [docs/production-operations.md](docs/production-operations.md).

The municipal-facing public beta, its illustrative demo, feedback, and privacy-preserving analytics are documented in [docs/public-beta.md](docs/public-beta.md). The private, evidence-bound Founder Intelligence Console is documented in [docs/founder-intelligence.md](docs/founder-intelligence.md).

## Development conventions

- Keep each pull request to one feature or infrastructure concern.
- Keep civic jurisdiction data in configuration and database records, never application constants.
- Run the relevant lint, type, test, and container-build checks before review.
- Add or amend an ADR in `docs/adr/` when a change affects architecture, security, data governance, or an external dependency.
