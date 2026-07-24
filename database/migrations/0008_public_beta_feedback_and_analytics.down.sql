BEGIN;

DROP FUNCTION IF EXISTS core.record_public_beta_analytics_event(text, text, text);
DROP FUNCTION IF EXISTS core.submit_public_beta_feedback(text, text, citext, text);
DROP TABLE IF EXISTS core.public_beta_analytics_events;
DROP TABLE IF EXISTS core.public_beta_feedback;

COMMIT;
