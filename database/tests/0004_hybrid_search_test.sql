BEGIN;

SELECT set_config('app.organization_id', '13000000-0000-0000-0000-000000000001', true);

INSERT INTO core.organizations (id, slug, name, organization_type)
VALUES ('13000000-0000-0000-0000-000000000001', 'search-tenant', 'Search Tenant', 'county');

INSERT INTO civic.documents (id, organization_id, title, document_type, canonical_url, published_at)
VALUES (
  '63000000-0000-0000-0000-000000000001',
  '13000000-0000-0000-0000-000000000001',
  'River restoration update',
  'report',
  'https://example.test/river-restoration',
  '2026-01-15'
);

INSERT INTO civic.document_versions (id, organization_id, document_id, version_number, content_hash, extracted_text)
VALUES (
  '73000000-0000-0000-0000-000000000002',
  '13000000-0000-0000-0000-000000000001',
  '63000000-0000-0000-0000-000000000001',
  1,
  'sha256:search',
  'The restoration project improves river water quality.'
);

DO $$
DECLARE
  indexed_job_count integer;
  keyword_match_count integer;
BEGIN
  SELECT count(*) INTO indexed_job_count
  FROM civic.vector_index_jobs
  WHERE document_version_id = '73000000-0000-0000-0000-000000000002'
    AND status = 'pending';

  IF indexed_job_count <> 1 THEN
    RAISE EXCEPTION 'expected one pending vector index job, got %', indexed_job_count;
  END IF;

  SELECT count(*) INTO keyword_match_count
  FROM civic.documents AS document
  JOIN civic.document_versions AS version
    ON version.organization_id = document.organization_id AND version.document_id = document.id
  WHERE document.search_vector @@ websearch_to_tsquery('english', 'river restoration')
     OR version.search_vector @@ websearch_to_tsquery('english', 'river restoration');

  IF keyword_match_count <> 1 THEN
    RAISE EXCEPTION 'expected PostgreSQL keyword match, got %', keyword_match_count;
  END IF;
END;
$$;

UPDATE civic.vector_index_jobs
SET status = 'completed', indexed_at = now()
WHERE document_version_id = '73000000-0000-0000-0000-000000000002';

INSERT INTO civic.topics (id, organization_id, slug, name)
VALUES (
  '83000000-0000-0000-0000-000000000003',
  '13000000-0000-0000-0000-000000000001',
  'water-quality',
  'Water quality'
);

INSERT INTO civic.topic_assignments (organization_id, document_id, topic_id)
VALUES (
  '13000000-0000-0000-0000-000000000001',
  '63000000-0000-0000-0000-000000000001',
  '83000000-0000-0000-0000-000000000003'
);

DO $$
DECLARE
  requeued_job_count integer;
BEGIN
  SELECT count(*) INTO requeued_job_count
  FROM civic.vector_index_jobs
  WHERE document_version_id = '73000000-0000-0000-0000-000000000002'
    AND status = 'pending';

  IF requeued_job_count <> 1 THEN
    RAISE EXCEPTION 'expected one requeued vector index job, got %', requeued_job_count;
  END IF;
END;
$$;

ROLLBACK;
