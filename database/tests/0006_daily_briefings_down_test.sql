DO $$
BEGIN
  IF to_regclass('research.daily_briefings') IS NOT NULL THEN
    RAISE EXCEPTION 'daily_briefings table remains after rollback';
  END IF;
  IF to_regclass('civic.daily_briefing_jobs') IS NOT NULL THEN
    RAISE EXCEPTION 'daily_briefing_jobs table remains after rollback';
  END IF;
END;
$$;
