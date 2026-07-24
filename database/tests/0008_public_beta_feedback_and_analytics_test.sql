BEGIN;

SELECT core.submit_public_beta_feedback(
  'idea',
  'Please add a clearer explanation of source coverage.',
  'beta@example.test',
  '/'
);
SELECT core.record_public_beta_analytics_event('beta_page_view', '/', 'landing');

DO $$
DECLARE
  feedback_count integer;
  event_count integer;
BEGIN
  SELECT count(*) INTO feedback_count FROM core.public_beta_feedback;
  SELECT count(*) INTO event_count FROM core.public_beta_analytics_events;
  IF feedback_count <> 1 OR event_count <> 1 THEN
    RAISE EXCEPTION 'expected one public-beta feedback record and one analytics event';
  END IF;
END;
$$;

ROLLBACK;
