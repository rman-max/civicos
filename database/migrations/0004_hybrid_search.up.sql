BEGIN;

ALTER TABLE civic.documents
  ADD COLUMN search_vector tsvector GENERATED ALWAYS AS (
    to_tsvector('english'::regconfig, coalesce(title, '') || ' ' || coalesce(document_type, ''))
  ) STORED;

ALTER TABLE civic.document_versions
  ADD COLUMN search_vector tsvector GENERATED ALWAYS AS (
    to_tsvector('english'::regconfig, coalesce(extracted_text, ''))
  ) STORED;

CREATE INDEX documents_search_vector_idx ON civic.documents USING gin (search_vector);
CREATE INDEX document_versions_search_vector_idx ON civic.document_versions USING gin (search_vector);

CREATE TABLE civic.vector_index_jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL,
  document_version_id uuid NOT NULL,
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
  run_after timestamptz NOT NULL DEFAULT now(),
  lease_token uuid,
  leased_until timestamptz,
  attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
  last_error text,
  indexed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, document_version_id),
  CONSTRAINT vector_index_jobs_organization_id_id_key UNIQUE (organization_id, id),
  CONSTRAINT vector_index_jobs_version_same_organization
    FOREIGN KEY (organization_id, document_version_id)
    REFERENCES civic.document_versions (organization_id, id)
    ON DELETE CASCADE,
  CONSTRAINT vector_index_jobs_lease_pair_check CHECK (
    (lease_token IS NULL AND leased_until IS NULL)
    OR (lease_token IS NOT NULL AND leased_until IS NOT NULL)
  )
);

CREATE INDEX vector_index_jobs_due_idx
  ON civic.vector_index_jobs (run_after) WHERE status IN ('pending', 'failed');
CREATE INDEX vector_index_jobs_lease_idx
  ON civic.vector_index_jobs (leased_until) WHERE status = 'processing';

CREATE TRIGGER vector_index_jobs_set_updated_at
  BEFORE UPDATE ON civic.vector_index_jobs
  FOR EACH ROW EXECUTE FUNCTION core.set_updated_at();

CREATE FUNCTION civic.enqueue_vector_index_job()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  INSERT INTO civic.vector_index_jobs (organization_id, document_version_id)
  VALUES (NEW.organization_id, NEW.id)
  ON CONFLICT (organization_id, document_version_id) DO NOTHING;
  RETURN NEW;
END;
$$;

CREATE TRIGGER document_versions_enqueue_vector_index_job
  AFTER INSERT ON civic.document_versions
  FOR EACH ROW EXECUTE FUNCTION civic.enqueue_vector_index_job();

CREATE FUNCTION civic.enqueue_document_vector_reindex()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  target_organization_id uuid;
  target_document_id uuid;
BEGIN
  IF TG_TABLE_NAME = 'documents' THEN
    target_organization_id := NEW.organization_id;
    target_document_id := NEW.id;
  ELSIF TG_OP = 'DELETE' THEN
    target_organization_id := OLD.organization_id;
    target_document_id := OLD.document_id;
  ELSE
    target_organization_id := NEW.organization_id;
    target_document_id := NEW.document_id;
  END IF;

  INSERT INTO civic.vector_index_jobs (organization_id, document_version_id)
  SELECT target_organization_id, id
  FROM civic.document_versions
  WHERE organization_id = target_organization_id
    AND document_id = target_document_id
  ORDER BY version_number DESC
  LIMIT 1
  ON CONFLICT (organization_id, document_version_id)
  DO UPDATE SET
    status = 'pending',
    run_after = now(),
    lease_token = NULL,
    leased_until = NULL,
    last_error = NULL;

  IF TG_OP = 'DELETE' THEN
    RETURN OLD;
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER documents_enqueue_vector_reindex
  AFTER UPDATE OF source_id, department_id, published_at, title, document_type ON civic.documents
  FOR EACH ROW EXECUTE FUNCTION civic.enqueue_document_vector_reindex();

CREATE TRIGGER topic_assignments_enqueue_vector_reindex
  AFTER INSERT OR UPDATE OR DELETE ON civic.topic_assignments
  FOR EACH ROW EXECUTE FUNCTION civic.enqueue_document_vector_reindex();

CREATE FUNCTION civic.claim_vector_index_jobs(job_limit integer)
RETURNS TABLE (
  job_id uuid,
  lease_token uuid,
  organization_id uuid,
  document_id uuid,
  document_version_id uuid,
  title text,
  document_type text,
  source_id uuid,
  department_id uuid,
  published_at date,
  extracted_text text,
  topic_ids uuid[]
)
LANGUAGE sql
SECURITY DEFINER
SET search_path = pg_catalog, civic
AS $$
  WITH due AS (
    SELECT id
    FROM civic.vector_index_jobs
    WHERE run_after <= now()
      AND (status IN ('pending', 'failed') OR (status = 'processing' AND leased_until < now()))
    ORDER BY run_after, created_at
    FOR UPDATE SKIP LOCKED
    LIMIT GREATEST(1, LEAST(job_limit, 100))
  ), claimed AS (
    UPDATE civic.vector_index_jobs AS job
    SET status = 'processing', lease_token = gen_random_uuid(), leased_until = now() + interval '10 minutes',
      attempt_count = job.attempt_count + 1
    FROM due
    WHERE job.id = due.id
    RETURNING job.id, job.lease_token, job.organization_id, job.document_version_id
  )
  SELECT claimed.id, claimed.lease_token, claimed.organization_id, document.id, version.id,
    document.title, document.document_type, document.source_id, document.department_id, document.published_at,
    version.extracted_text,
    COALESCE(topic_assignment.topic_ids, ARRAY[]::uuid[])
  FROM claimed
  JOIN civic.document_versions AS version
    ON version.organization_id = claimed.organization_id AND version.id = claimed.document_version_id
  JOIN civic.documents AS document
    ON document.organization_id = version.organization_id AND document.id = version.document_id
  LEFT JOIN LATERAL (
    SELECT array_agg(topic_id ORDER BY topic_id) AS topic_ids
    FROM civic.topic_assignments
    WHERE organization_id = document.organization_id AND document_id = document.id
  ) AS topic_assignment ON true;
$$;

REVOKE ALL ON FUNCTION civic.claim_vector_index_jobs(integer) FROM PUBLIC;

ALTER TABLE civic.vector_index_jobs ENABLE ROW LEVEL SECURITY;
CREATE POLICY vector_index_jobs_organization_isolation ON civic.vector_index_jobs
  FOR ALL
  USING (organization_id = core.current_organization_id())
  WITH CHECK (organization_id = core.current_organization_id());

INSERT INTO civic.vector_index_jobs (organization_id, document_version_id)
SELECT organization_id, id
FROM (
  SELECT DISTINCT ON (organization_id, document_id) organization_id, id
  FROM civic.document_versions
  ORDER BY organization_id, document_id, version_number DESC
) AS latest_version
ON CONFLICT (organization_id, document_version_id) DO NOTHING;

COMMIT;
