BEGIN;

DO $$
DECLARE
  required_function regprocedure;
BEGIN
  FOREACH required_function IN ARRAY ARRAY[
    'core.touch_updated_at()'::regprocedure,
    'core.set_updated_at()'::regprocedure,
    'civic.enqueue_discovery_job()'::regprocedure,
    'civic.enqueue_vector_index_job()'::regprocedure,
    'civic.validate_knowledge_graph_edge()'::regprocedure,
    'core.require_current_organization_admin()'::regprocedure,
    'core.ensure_founder_secret_principal(citext, text, text, citext, text)'::regprocedure
  ]
  LOOP
    IF required_function IS NULL THEN
      RAISE EXCEPTION 'required migration function is missing';
    END IF;
  END LOOP;
END;
$$;

DO $$
BEGIN
  IF to_regclass('civic.canonical_records') IS NULL
    OR to_regclass('civic.canonical_record_versions') IS NULL
    OR to_regclass('civic.canonical_record_evidence') IS NULL
    OR to_regclass('civic.canonical_record_changes') IS NULL
    OR to_regclass('civic.canonical_backfill_runs') IS NULL THEN
    RAISE EXCEPTION 'canonical civic-record migration is incomplete';
  END IF;
END;
$$;

DO $$
DECLARE
  unresolved_trigger_count integer;
BEGIN
  SELECT count(*)
  INTO unresolved_trigger_count
  FROM pg_trigger AS trigger
  LEFT JOIN pg_proc AS trigger_function ON trigger_function.oid = trigger.tgfoid
  WHERE NOT trigger.tgisinternal
    AND trigger_function.oid IS NULL;

  IF unresolved_trigger_count <> 0 THEN
    RAISE EXCEPTION 'one or more non-internal triggers have no function';
  END IF;
END;
$$;

ROLLBACK;
