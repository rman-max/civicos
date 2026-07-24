DO $$
BEGIN
  IF to_regclass('research.saved_searches') IS NOT NULL THEN
    RAISE EXCEPTION 'saved_searches table remains after rollback';
  END IF;
  IF to_regclass('research.notebook_documents') IS NOT NULL THEN
    RAISE EXCEPTION 'notebook_documents table remains after rollback';
  END IF;
END;
$$;
