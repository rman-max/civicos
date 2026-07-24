-- Compatibility prerequisite for migrations 0002 through 0004.
--
-- The early autonomous-discovery, graph, and hybrid-search migrations reference
-- core.set_updated_at(). Keep this separately versioned rather than mutating
-- 0001_civic_core so databases that already recorded 0001 remain upgrade-safe.

BEGIN;

CREATE FUNCTION core.set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

COMMIT;
