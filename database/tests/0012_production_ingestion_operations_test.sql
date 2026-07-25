BEGIN;

DO $$
BEGIN
  IF to_regclass('civic.ingestion_runs') IS NULL
     OR to_regclass('civic.ingestion_run_sources') IS NULL
     OR to_regclass('civic.worker_heartbeats') IS NULL THEN
    RAISE EXCEPTION 'production ingestion operation tables are missing';
  END IF;
END;
$$;

DO $$
DECLARE
  active_index_exists boolean;
BEGIN
  SELECT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname = 'civic' AND indexname = 'ingestion_run_sources_active_source_key'
  ) INTO active_index_exists;
  IF NOT active_index_exists THEN
    RAISE EXCEPTION 'active-source locking index is missing';
  END IF;
END;
$$;

ROLLBACK;
