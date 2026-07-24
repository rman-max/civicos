# Civic jurisdiction seeds

Seed files establish a tenant, its municipalities, departments, and approved public sources. They are configuration, not schema migrations: apply them only after all database migrations (currently through `0008`) and only with the privileged tenant-provisioning account described in `docs/autonomous-discovery.md`.

Each seed is safe to run again. It inserts missing records and deliberately leaves existing records unchanged, including any connector an operator has paused or edited.

Applying a source creates its durable discovery job automatically. Start the `discovery` Compose profile after applying a seed to begin autonomous ingestion.

```sh
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 \
  -f database/seeds/st_joseph_county_indiana.sql
```

Use a provisioning role with `BYPASSRLS` for this operation. Do not grant that privilege to the API or ingestion worker roles.
