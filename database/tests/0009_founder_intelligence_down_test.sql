DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'founder') THEN
    RAISE EXCEPTION 'Founder schema should not exist after rollback';
  END IF;
END;
$$;
