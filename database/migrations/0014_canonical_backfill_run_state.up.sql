BEGIN;

-- Allows a deployment-triggered backfill to be safe across worker restarts.
CREATE TABLE civic.canonical_backfill_runs (
  organization_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
  extraction_version text NOT NULL,
  status text NOT NULL CHECK (status IN ('running', 'completed', 'failed')),
  raw_documents_processed integer NOT NULL DEFAULT 0 CHECK (raw_documents_processed >= 0),
  canonical_records_created integer NOT NULL DEFAULT 0 CHECK (canonical_records_created >= 0),
  records_rejected integer NOT NULL DEFAULT 0 CHECK (records_rejected >= 0),
  duplicates_merged integer NOT NULL DEFAULT 0 CHECK (duplicates_merged >= 0),
  started_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz,
  error_message text,
  PRIMARY KEY (organization_id, extraction_version)
);

ALTER TABLE civic.canonical_backfill_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE civic.canonical_backfill_runs FORCE ROW LEVEL SECURITY;
CREATE POLICY canonical_backfill_runs_organization_isolation ON civic.canonical_backfill_runs
  FOR ALL USING (organization_id = core.current_organization_id())
  WITH CHECK (organization_id = core.current_organization_id());

COMMIT;
