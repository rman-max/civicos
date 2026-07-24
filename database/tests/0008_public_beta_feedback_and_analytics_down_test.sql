DO $$
BEGIN
  IF to_regclass('core.public_beta_feedback') IS NOT NULL
    OR to_regclass('core.public_beta_analytics_events') IS NOT NULL THEN
    RAISE EXCEPTION 'public beta migration rollback left a table behind';
  END IF;
END;
$$;
