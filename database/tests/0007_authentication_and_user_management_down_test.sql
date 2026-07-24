DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'core'
      AND table_name = 'organization_memberships'
      AND column_name = 'is_active'
  ) THEN
    RAISE EXCEPTION 'authentication migration rollback left is_active behind';
  END IF;
END;
$$;
