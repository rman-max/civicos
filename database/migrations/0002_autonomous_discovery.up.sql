BEGIN;

ALTER TABLE civic.sources
  ADD COLUMN scan_interval_seconds integer NOT NULL DEFAULT 21600
    CHECK (scan_interval_seconds >= 60),
  ADD COLUMN max_pages_per_scan integer NOT NULL DEFAULT 100
    CHECK (max_pages_per_scan BETWEEN 1 AND 10000),
  ADD COLUMN request_timeout_seconds integer NOT NULL DEFAULT 20
    CHECK (request_timeout_seconds BETWEEN 1 AND 120);

CREATE TABLE civic.source_scan_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL,
  source_id uuid NOT NULL,
  status text NOT NULL CHECK (status IN ('running', 'completed', 'failed')),
  started_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz,
  pages_crawled integer NOT NULL DEFAULT 0 CHECK (pages_crawled >= 0),
  documents_discovered integer NOT NULL DEFAULT 0 CHECK (documents_discovered >= 0),
  documents_changed integer NOT NULL DEFAULT 0 CHECK (documents_changed >= 0),
  error_message text,
  CONSTRAINT source_scan_runs_organization_id_id_key UNIQUE (organization_id, id),
  CONSTRAINT source_scan_runs_source_fk FOREIGN KEY (organization_id, source_id)
    REFERENCES civic.sources (organization_id, id) ON DELETE CASCADE
);

CREATE TABLE civic.discovery_jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL,
  source_id uuid NOT NULL,
  run_after timestamptz NOT NULL DEFAULT now(),
  lease_token uuid,
  leased_until timestamptz,
  attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
  last_error text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT discovery_jobs_organization_id_id_key UNIQUE (organization_id, id),
  CONSTRAINT discovery_jobs_source_key UNIQUE (organization_id, source_id),
  CONSTRAINT discovery_jobs_source_fk FOREIGN KEY (organization_id, source_id)
    REFERENCES civic.sources (organization_id, id) ON DELETE CASCADE,
  CONSTRAINT discovery_jobs_lease_pair_check CHECK (
    (lease_token IS NULL AND leased_until IS NULL)
    OR (lease_token IS NOT NULL AND leased_until IS NOT NULL)
  )
);

CREATE TABLE civic.source_observations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL,
  source_id uuid NOT NULL,
  scan_run_id uuid NOT NULL,
  document_id uuid,
  document_version_id uuid,
  source_url text NOT NULL,
  final_url text NOT NULL,
  http_status integer NOT NULL CHECK (http_status BETWEEN 100 AND 599),
  media_type text,
  content_hash text,
  etag text,
  last_modified text,
  observed_at timestamptz NOT NULL DEFAULT now(),
  error_message text,
  CONSTRAINT source_observations_organization_id_id_key UNIQUE (organization_id, id),
  CONSTRAINT source_observations_source_fk FOREIGN KEY (organization_id, source_id)
    REFERENCES civic.sources (organization_id, id) ON DELETE CASCADE,
  CONSTRAINT source_observations_scan_run_fk FOREIGN KEY (organization_id, scan_run_id)
    REFERENCES civic.source_scan_runs (organization_id, id) ON DELETE CASCADE,
  CONSTRAINT source_observations_document_fk FOREIGN KEY (organization_id, document_id)
    REFERENCES civic.documents (organization_id, id) ON DELETE SET NULL,
  CONSTRAINT source_observations_version_fk FOREIGN KEY (organization_id, document_version_id)
    REFERENCES civic.document_versions (organization_id, id) ON DELETE SET NULL
);

CREATE INDEX source_scan_runs_source_started_idx
  ON civic.source_scan_runs (organization_id, source_id, started_at DESC);
CREATE INDEX discovery_jobs_due_idx
  ON civic.discovery_jobs (run_after) WHERE leased_until IS NULL;
CREATE INDEX discovery_jobs_lease_idx
  ON civic.discovery_jobs (leased_until) WHERE leased_until IS NOT NULL;
CREATE INDEX source_observations_source_url_idx
  ON civic.source_observations (organization_id, source_id, source_url, observed_at DESC);
CREATE INDEX source_observations_version_idx
  ON civic.source_observations (organization_id, document_version_id)
  WHERE document_version_id IS NOT NULL;

CREATE TRIGGER discovery_jobs_set_updated_at
  BEFORE UPDATE ON civic.discovery_jobs
  FOR EACH ROW EXECUTE FUNCTION core.set_updated_at();

CREATE FUNCTION civic.enqueue_discovery_job()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF NEW.is_active THEN
    INSERT INTO civic.discovery_jobs (organization_id, source_id, run_after)
    VALUES (NEW.organization_id, NEW.id, now())
    ON CONFLICT (organization_id, source_id)
    DO UPDATE SET run_after = LEAST(civic.discovery_jobs.run_after, EXCLUDED.run_after);
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER sources_enqueue_discovery_job
  AFTER INSERT OR UPDATE OF is_active, canonical_url, acquisition_policy ON civic.sources
  FOR EACH ROW EXECUTE FUNCTION civic.enqueue_discovery_job();

-- The worker receives cross-tenant work only through this narrowly scoped queue-claim
-- operation. All later reads and writes remain subject to organization RLS.
CREATE FUNCTION civic.claim_discovery_jobs(job_limit integer)
RETURNS TABLE (
  job_id uuid,
  lease_token uuid,
  source_id uuid,
  organization_id uuid,
  name text,
  canonical_url text,
  acquisition_policy jsonb,
  scan_interval_seconds integer,
  max_pages_per_scan integer,
  request_timeout_seconds integer
)
LANGUAGE sql
SECURITY DEFINER
SET search_path = pg_catalog, civic
AS $$
  WITH due AS (
    SELECT job.id
    FROM civic.discovery_jobs AS job
    JOIN civic.sources AS source
      ON source.id = job.source_id
      AND source.organization_id = job.organization_id
      AND source.is_active
    WHERE job.run_after <= now() AND (job.leased_until IS NULL OR job.leased_until < now())
    ORDER BY job.run_after, job.created_at
    FOR UPDATE OF job SKIP LOCKED
    LIMIT GREATEST(1, LEAST(job_limit, 100))
  )
  UPDATE civic.discovery_jobs AS job
  SET lease_token = gen_random_uuid(),
      leased_until = now() + interval '10 minutes',
      attempt_count = job.attempt_count + 1
  FROM due, civic.sources AS source
  WHERE job.id = due.id
    AND source.id = job.source_id
    AND source.organization_id = job.organization_id
  RETURNING job.id, job.lease_token, source.id, source.organization_id, source.name,
    source.canonical_url, source.acquisition_policy, source.scan_interval_seconds,
    source.max_pages_per_scan, source.request_timeout_seconds;
$$;

REVOKE ALL ON FUNCTION civic.claim_discovery_jobs(integer) FROM PUBLIC;

DO $$
DECLARE
  table_name text;
BEGIN
  FOREACH table_name IN ARRAY ARRAY[
    'source_scan_runs', 'discovery_jobs', 'source_observations'
  ] LOOP
    EXECUTE format('ALTER TABLE civic.%I ENABLE ROW LEVEL SECURITY', table_name);
    EXECUTE format(
      'CREATE POLICY %I ON civic.%I FOR ALL USING (organization_id = core.current_organization_id()) WITH CHECK (organization_id = core.current_organization_id())',
      table_name || '_organization_isolation', table_name
    );
  END LOOP;
END $$;

INSERT INTO civic.discovery_jobs (organization_id, source_id, run_after)
SELECT organization_id, id, now()
FROM civic.sources
WHERE is_active
ON CONFLICT (organization_id, source_id) DO NOTHING;

COMMIT;
