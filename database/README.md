# Database boundary

PostgreSQL is CivicOS’s authoritative transactional store. The initial schema is a portable raw-SQL migration in `migrations/0001_civic_core.up.sql`; its companion rollback is deliberately destructive and limited to approved development/recovery use.

See [schema.md](schema.md) for the tenant model, evidence lineage, table inventory, and safe migration procedure. Every future tenant-owned table must include an organization boundary, row-level-security coverage, and migration tests.
