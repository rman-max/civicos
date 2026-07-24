BEGIN;

DROP FUNCTION IF EXISTS founder.latest_daily_brief();
DROP FUNCTION IF EXISTS founder.create_watchlist(text, text, text, jsonb);
DROP FUNCTION IF EXISTS founder.list_watchlists();
DROP FUNCTION IF EXISTS founder.list_opportunities(integer);
DROP FUNCTION IF EXISTS founder.list_signals(integer);
DROP FUNCTION IF EXISTS founder.claim_daily_brief_jobs(integer);
DROP FUNCTION IF EXISTS founder.enqueue_daily_brief_jobs(date);
DROP TABLE IF EXISTS founder.daily_brief_jobs;
DROP TABLE IF EXISTS founder.daily_briefs;
DROP TABLE IF EXISTS founder.watchlist_matches;
DROP TABLE IF EXISTS founder.watchlists;
DROP TABLE IF EXISTS founder.opportunities;
DROP TABLE IF EXISTS founder.signals;
DROP SCHEMA IF EXISTS founder;

COMMIT;
