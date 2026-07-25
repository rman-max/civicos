# Railway ingestion worker

Create a second Railway service from this repository. Leave its root directory empty and set its Dockerfile path to `ingestion/Dockerfile`; the image includes the reviewed St. Joseph County seed at `/app/database/seeds/st_joseph_county_indiana.sql`.

Its persistent start command is:

```sh
python -m civicos_ingestion.worker --apply-seed
```

`--apply-seed` is idempotent: it inserts missing approved connectors and queues their first scans. The worker then claims PostgreSQL jobs with `FOR UPDATE SKIP LOCKED`; one leased source cannot be scanned by another worker. Completed sources are scheduled for their next scan after the interval stored in the connector seed (three hours). Failed sources receive capped exponential backoff while other sources continue.

## Required worker variables

Copy from the API service:

- `DATABASE_URL`
- `CIVICOS_BRIEFING_TIMEZONE=America/Indiana/Indianapolis`
- `CIVICOS_FOUNDER_BRIEF_MINIMUM_SCORE`
- `CIVICOS_FOUNDER_BRIEF_SECTION_LIMIT`

Set these object-storage variables. They are mandatory because CivicOS stores immutable raw public artifacts before creating their document-version provenance:

- `S3_BUCKET`
- `S3_ACCESS_KEY`
- `S3_SECRET_KEY`
- `S3_ENDPOINT_URL` only for a non-AWS S3-compatible provider; omit it for AWS S3.

Set `CIVICOS_DISCOVERY_POLL_SECONDS=60`. This is queue polling, not a scrape interval. The per-connector schedule is three hours.

`QDRANT_URL`, `QDRANT_API_KEY`, `QDRANT_COLLECTION`, `EMBEDDING_BASE_URL`, `EMBEDDING_MODEL`, and `EMBEDDING_API_KEY` are optional. When they are absent, document ingestion and PostgreSQL keyword search remain fully operational; no vector-index job is claimed.

## Initial backfill

Run this one-off Railway command from the worker service after its variables are set:

```sh
python -m civicos_ingestion.worker --apply-seed --once
```

It safely applies the seed then processes one five-source batch. Leave the persistent worker running to process the remaining queued sources. Confirm progress through `GET /v1/founder/ingestion/status` and `GET /v1/search?query=county&mode=keyword` while authenticated as the founder.

## Canonical civic-record backfill

After the API service deploys migrations `0013_canonical_civic_records` and `0014_canonical_backfill_run_state`, set this Railway worker variable and redeploy the worker:

```env
CIVICOS_CANONICAL_BACKFILL_ON_START=true
```

The locked persistent start command remains unchanged. The worker performs the backfill once per organization and extraction version, records durable completion state, then continues its normal scheduled scans. It is safe to leave the variable enabled; completed backfills are skipped after restarts.

If a worker shell is available, this equivalent one-off command remains supported:

```sh
python -m civicos_ingestion.worker --backfill-canonical
```

It makes no network calls and does not alter raw documents, artifacts, or raw versions. It rebuilds the deterministic canonical projection from existing immutable source text, creates field-level change events, and reports processed, created, rejected, and merged counts in worker logs. Default `GET /v1/search` returns this canonical projection; append `view=raw` only when auditing original source documents.

## Founder refresh

`POST /v1/founder/ingestion/runs` queues all enabled sources, or accepts `{ "source_id": "<uuid>" }` for one connector. It returns immediately with a durable run ID. `GET /v1/founder/ingestion/runs/{run_id}` reports every connector's progress and counts. Only tenant administrators can use these endpoints; the configured cooldown and the partial unique active-source index prevent overlapping refreshes.
