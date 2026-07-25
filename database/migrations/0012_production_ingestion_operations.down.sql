BEGIN;
DROP TABLE IF EXISTS civic.worker_heartbeats;
DROP TABLE IF EXISTS civic.ingestion_run_sources;
DROP TABLE IF EXISTS civic.ingestion_runs;
ALTER TABLE civic.source_scan_runs
  DROP COLUMN IF EXISTS documents_indexed,
  DROP COLUMN IF EXISTS documents_skipped;
COMMIT;
