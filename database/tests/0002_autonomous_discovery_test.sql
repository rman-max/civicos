BEGIN;

SELECT set_config('app.organization_id', '11000000-0000-0000-0000-000000000001', true);

INSERT INTO core.organizations (id, slug, name, organization_type)
VALUES (
  '11000000-0000-0000-0000-000000000001',
  'discovery-tenant',
  'Discovery Tenant',
  'county'
);

INSERT INTO civic.sources (id, organization_id, name, source_type, canonical_url, acquisition_policy)
VALUES (
  '51000000-0000-0000-0000-000000000001',
  '11000000-0000-0000-0000-000000000001',
  'Official records',
  'official_website',
  'https://records.example.test/',
  '{"allowed_domains": ["records.example.test"], "respect_robots": true}'::jsonb
);

DO $$
DECLARE
  job_count integer;
  claimed_count integer;
BEGIN
  SELECT count(*) INTO job_count
  FROM civic.discovery_jobs
  WHERE source_id = '51000000-0000-0000-0000-000000000001';

  IF job_count <> 1 THEN
    RAISE EXCEPTION 'expected one discovery job, got %', job_count;
  END IF;

  SELECT count(*) INTO claimed_count FROM civic.claim_discovery_jobs(1);
  IF claimed_count <> 1 THEN
    RAISE EXCEPTION 'expected one claimed discovery job, got %', claimed_count;
  END IF;
END;
$$;

ROLLBACK;
