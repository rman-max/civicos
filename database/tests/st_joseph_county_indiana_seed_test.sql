BEGIN;

SELECT set_config(
  'app.organization_id',
  (SELECT id::text FROM core.organizations WHERE slug = 'st-joseph-county-indiana'),
  true
);

DO $$
DECLARE
  municipality_count integer;
  department_count integer;
  source_count integer;
  discovery_job_count integer;
  out_of_scope_path_count integer;
BEGIN
  SELECT count(*) INTO municipality_count FROM core.municipalities;
  SELECT count(*) INTO department_count FROM core.departments;
  SELECT count(*) INTO source_count FROM civic.sources WHERE is_active;
  SELECT count(*) INTO discovery_job_count FROM civic.discovery_jobs;
  SELECT count(*) INTO out_of_scope_path_count
  FROM civic.sources
  WHERE NOT (acquisition_policy ? 'allowed_path_prefixes')
     OR acquisition_policy->'allowed_path_prefixes' = '[]'::jsonb;

  IF municipality_count <> 3 THEN
    RAISE EXCEPTION 'expected 3 municipalities, got %', municipality_count;
  END IF;
  IF department_count <> 11 THEN
    RAISE EXCEPTION 'expected 11 departments, got %', department_count;
  END IF;
  IF source_count <> 11 THEN
    RAISE EXCEPTION 'expected 11 active sources, got %', source_count;
  END IF;
  IF discovery_job_count <> source_count THEN
    RAISE EXCEPTION 'expected one discovery job per source, got % jobs for % sources', discovery_job_count, source_count;
  END IF;
  IF out_of_scope_path_count <> 0 THEN
    RAISE EXCEPTION 'every seeded source must have at least one allowed path prefix';
  END IF;
END;
$$;

ROLLBACK;
