BEGIN;

DROP FUNCTION IF EXISTS civic.claim_daily_briefing_jobs(integer);
DROP FUNCTION IF EXISTS civic.enqueue_daily_briefing_jobs(date);
DROP TRIGGER IF EXISTS daily_briefing_deliveries_set_updated_at ON research.daily_briefing_deliveries;
DROP TRIGGER IF EXISTS daily_briefings_set_updated_at ON research.daily_briefings;
DROP TRIGGER IF EXISTS daily_briefing_jobs_set_updated_at ON civic.daily_briefing_jobs;
DROP TRIGGER IF EXISTS briefing_subscriptions_set_updated_at ON research.briefing_subscriptions;
DROP TABLE IF EXISTS research.daily_briefing_deliveries;
DROP TABLE IF EXISTS research.daily_briefings;
DROP TABLE IF EXISTS civic.daily_briefing_jobs;
DROP TABLE IF EXISTS research.briefing_subscriptions;

COMMIT;
