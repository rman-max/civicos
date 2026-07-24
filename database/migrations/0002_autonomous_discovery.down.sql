BEGIN;

DROP FUNCTION IF EXISTS civic.claim_discovery_jobs(integer);
DROP TRIGGER IF EXISTS sources_enqueue_discovery_job ON civic.sources;
DROP FUNCTION IF EXISTS civic.enqueue_discovery_job();
DROP TABLE IF EXISTS civic.source_observations;
DROP TABLE IF EXISTS civic.discovery_jobs;
DROP TABLE IF EXISTS civic.source_scan_runs;

ALTER TABLE civic.sources
  DROP COLUMN IF EXISTS request_timeout_seconds,
  DROP COLUMN IF EXISTS max_pages_per_scan,
  DROP COLUMN IF EXISTS scan_interval_seconds;

COMMIT;
