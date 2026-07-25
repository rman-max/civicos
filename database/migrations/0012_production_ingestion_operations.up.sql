BEGIN;

ALTER TABLE civic.source_scan_runs
  ADD COLUMN documents_skipped integer NOT NULL DEFAULT 0 CHECK (documents_skipped >= 0),
  ADD COLUMN documents_indexed integer NOT NULL DEFAULT 0 CHECK (documents_indexed >= 0);

CREATE TABLE civic.ingestion_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
  requested_by_user_id uuid REFERENCES core.users(id) ON DELETE SET NULL,
  request_kind text NOT NULL CHECK (request_kind IN ('scheduled', 'founder_refresh', 'backfill')),
  status text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'running', 'completed', 'failed')),
  requested_at timestamptz NOT NULL DEFAULT now(),
  started_at timestamptz,
  completed_at timestamptz,
  error_message text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id)
);

CREATE TABLE civic.ingestion_run_sources (
  ingestion_run_id uuid NOT NULL,
  organization_id uuid NOT NULL,
  source_id uuid NOT NULL,
  scan_run_id uuid,
  status text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'running', 'completed', 'failed')),
  started_at timestamptz,
  completed_at timestamptz,
  pages_crawled integer NOT NULL DEFAULT 0 CHECK (pages_crawled >= 0),
  documents_discovered integer NOT NULL DEFAULT 0 CHECK (documents_discovered >= 0),
  documents_changed integer NOT NULL DEFAULT 0 CHECK (documents_changed >= 0),
  documents_skipped integer NOT NULL DEFAULT 0 CHECK (documents_skipped >= 0),
  documents_indexed integer NOT NULL DEFAULT 0 CHECK (documents_indexed >= 0),
  error_message text,
  PRIMARY KEY (ingestion_run_id, source_id),
  CONSTRAINT ingestion_run_sources_run_fk FOREIGN KEY (organization_id, ingestion_run_id)
    REFERENCES civic.ingestion_runs (organization_id, id) ON DELETE CASCADE,
  CONSTRAINT ingestion_run_sources_source_fk FOREIGN KEY (organization_id, source_id)
    REFERENCES civic.sources (organization_id, id) ON DELETE CASCADE,
  CONSTRAINT ingestion_run_sources_scan_fk FOREIGN KEY (organization_id, scan_run_id)
    REFERENCES civic.source_scan_runs (organization_id, id) ON DELETE SET NULL
);

CREATE UNIQUE INDEX ingestion_run_sources_active_source_key
  ON civic.ingestion_run_sources (organization_id, source_id)
  WHERE status IN ('queued', 'running');
CREATE INDEX ingestion_runs_organization_requested_idx
  ON civic.ingestion_runs (organization_id, requested_at DESC);

CREATE TABLE civic.worker_heartbeats (
  worker_id text PRIMARY KEY,
  last_seen_at timestamptz NOT NULL DEFAULT now(),
  last_scheduled_poll_at timestamptz NOT NULL DEFAULT now(),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(metadata) = 'object')
);

CREATE TRIGGER ingestion_runs_set_updated_at BEFORE UPDATE ON civic.ingestion_runs
  FOR EACH ROW EXECUTE FUNCTION core.touch_updated_at();

ALTER TABLE civic.ingestion_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE civic.ingestion_runs FORCE ROW LEVEL SECURITY;
ALTER TABLE civic.ingestion_run_sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE civic.ingestion_run_sources FORCE ROW LEVEL SECURITY;

CREATE POLICY ingestion_runs_organization_isolation ON civic.ingestion_runs
  FOR ALL USING (organization_id = core.current_organization_id())
  WITH CHECK (organization_id = core.current_organization_id());
CREATE POLICY ingestion_run_sources_organization_isolation ON civic.ingestion_run_sources
  FOR ALL USING (organization_id = core.current_organization_id())
  WITH CHECK (organization_id = core.current_organization_id());

COMMIT;
