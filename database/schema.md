# CivicOS PostgreSQL schema

## Scope and ownership

The schema is installed by ordered raw-SQL migrations. `0001_civic_core.up.sql` owns the core model; `0001_core_set_updated_at_compatibility.up.sql` establishes the trigger function required by the following migrations without changing an already-recorded initial migration; `0002_autonomous_discovery.up.sql` adds durable autonomous discovery; `0003_knowledge_graph.up.sql` adds the evidence-backed knowledge graph; `0004_hybrid_search.up.sql` adds hybrid search projections; `0005_research_notebooks.up.sql` adds saved searches and saved documents; `0006_daily_briefings.up.sql` adds daily briefings and in-app subscriptions; `0007_authentication_and_user_management.up.sql` adds active tenant memberships and OIDC identity-resolution functions; `0008_public_beta_feedback_and_analytics.up.sql` adds voluntary beta feedback with anonymous first-party events; and `0009_founder_intelligence.up.sql` adds private, evidence-bound commercial signals, opportunities, watchlist matches, and durable Founder Brief jobs. Raw SQL keeps the database boundary portable and does not couple the application to an ORM or migration runtime.

| PostgreSQL schema | Owns |
|---|---|
| `core` | users, organizations, active memberships, municipalities, departments, tenant helpers |
| `civic` | sources, discovery and vector-index jobs, versioned documents, meetings, ordinances, budgets, projects, locations, officials, graph relationships, entities, topics, citations |
| `research` | notebooks, notebook entries/citations, saved searches/documents, collections, daily briefings/subscriptions |
| `founder` | private commercial signals, ranked opportunities, watchlists/matches, and Founder Brief jobs |

## Tenant boundary

An organization is the top-level CivicOS tenant. A tenant can own a county, municipalities within it, and their government bodies. Every tenant-owned table has `organization_id`, a composite foreign key to related records that includes the same organization, and enforced PostgreSQL row-level security.

Before every tenant-scoped database transaction, the API or worker must set both values using transaction-local settings:

```sql
SET LOCAL app.organization_id = 'organization-uuid';
SET LOCAL app.user_id = 'user-uuid';
```

`core.current_organization_id()` is used by the RLS policies. A service role that provisions organizations or executes cross-tenant maintenance must be explicitly created with `BYPASSRLS`; ordinary API and worker roles must not have that privilege. The discovery worker claims cross-tenant work only through `civic.claim_discovery_jobs(integer)`, a narrowly scoped `SECURITY DEFINER` function. Its service role needs `EXECUTE` on that function, not `BYPASSRLS`.

## Evidence model

```text
source -> document -> document_version -> document_artifact
                                  -> citation -> notebook_citation
```

`civic.documents` is the logical public record. `civic.document_versions` is append-only and stores the representation retrieved at a point in time; `civic.document_artifacts` stores immutable object-storage metadata. Citations always target a document version and a structured locator, never a mutable URL alone.

The ingestion processor stores cleaned text and extraction/processing metadata on the immutable version. Its verified document classification, explicit publication date, and department match live on the logical document; topic assignments and entity mentions remain normalized relationship records. See `../docs/document-processing.md` for the processing contract and inference limits.

Meetings, ordinances, budgets, and projects relate to documents through explicit join tables. This prevents a brittle generic foreign key and permits a document to support several civic records.

The knowledge graph is a tenant-scoped PostgreSQL projection. `civic.knowledge_graph_edges` stores discovered, evidence-backed relationships; `civic.knowledge_graph_relationships` unifies them with structural relationships from normalized tables; and `civic.related_documents` exposes shared-node links across documents. See `../docs/knowledge-graph.md`.

Hybrid search uses generated PostgreSQL `tsvector` columns on documents and document versions, plus `civic.vector_index_jobs` for the rebuildable Qdrant projection. See `../docs/search.md`.

## Entity and topic model

`civic.entities` represents people and non-person entities using an `entity_type` value and organization-scoped identifiers. `civic.document_entity_mentions` preserves the observed name and optional source offsets instead of treating entity resolution as unreviewable truth.

`civic.topics` supports a hierarchy. `civic.topic_assignments` permits one topic to relate to one typed target per row. Its one-target check and composite foreign keys retain referential integrity while allowing a topic to classify documents, meetings, ordinances, budgets, projects, entities, or departments.

## Core tables

| Domain | Tables |
|---|---|
| Organizations and municipalities | `core.organizations`, `core.municipalities`, `core.departments` |
| Users | `core.users`, `core.organization_memberships` |
| Sources and documents | `civic.sources`, `civic.documents`, `civic.document_versions`, `civic.document_artifacts` |
| Autonomous discovery | `civic.discovery_jobs`, `civic.source_scan_runs`, `civic.source_observations` |
| Hybrid search | generated document/version search vectors, `civic.vector_index_jobs` |
| Meetings | `civic.meetings`, `civic.meeting_agenda_items`, `civic.meeting_documents` |
| Ordinances | `civic.ordinances`, `civic.ordinance_documents` |
| Budgets | `civic.budgets`, `civic.budget_lines`, `civic.budget_documents` |
| Projects | `civic.projects`, `civic.project_documents` |
| Locations, officials, and graph | `civic.locations`, `civic.officials`, `civic.document_location_mentions`, `civic.knowledge_graph_edges`, `civic.knowledge_graph_relationships`, `civic.related_documents` |
| People/entities and topics | `civic.entities`, `civic.document_entity_mentions`, `civic.topics`, `civic.topic_assignments` |
| Citations and research | `civic.citations`, `research.notebooks`, `research.notebook_entries`, `research.notebook_citations`, `research.saved_searches`, `research.notebook_documents`, `research.daily_briefings`, `research.briefing_subscriptions`, `research.daily_briefing_deliveries`, `research.collections`, `research.collection_documents` |
| Founder intelligence | `founder.signals`, `founder.opportunities`, `founder.watchlists`, `founder.watchlist_matches`, `founder.daily_briefs`, `founder.daily_brief_jobs` |

## Applying migrations

Migrations are ordered by their numeric prefix and must be applied in order. Always back up a production database and use `ON_ERROR_STOP` before applying one.

The provisioning role must be permitted to install the `citext` and `pgcrypto` extensions used by the initial migration. Application roles do not need extension-install privileges.

```sh
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f database/migrations/0001_civic_core.up.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f database/migrations/0001_core_set_updated_at_compatibility.up.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f database/migrations/0002_autonomous_discovery.up.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f database/migrations/0003_knowledge_graph.up.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f database/migrations/0004_hybrid_search.up.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f database/migrations/0005_research_notebooks.up.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f database/migrations/0006_daily_briefings.up.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f database/migrations/0007_authentication_and_user_management.up.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f database/migrations/0008_public_beta_feedback_and_analytics.up.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f database/migrations/0009_founder_intelligence.up.sql
```

Jurisdiction configuration is applied separately from schema migration. For the initial County deployment, use the privileged provisioning role to run `database/seeds/st_joseph_county_indiana.sql`; it adds approved municipalities, departments, sources, and their discovery jobs without changing existing configuration. See `../docs/st-joseph-county-indiana.md`.

The paired `down.sql` file is intentionally destructive and is only appropriate for an empty development database or an approved recovery procedure.

GitHub Actions applies the migrations to a clean PostgreSQL instance and verifies document-version immutability, tenant RLS isolation, discovery job scheduling, and the idempotence of the St. Joseph County seed with matching SQL tests.

## Schema rules

- Never update or delete a `document_version` or `document_artifact`; add a newer version instead.
- Use structured metadata fields only for source-specific or evolving attributes. Do not place core relationships in JSONB.
- Add tenant-scoped foreign keys as `(organization_id, record_id)` pairs. A UUID alone is insufficient for tenant isolation.
- Add a migration and a documentation update for every new persisted domain concept.
- Add a database integration test for RLS, constraints, migration upgrade, and migration rollback before adding application writes.
