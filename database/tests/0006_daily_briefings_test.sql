BEGIN;

SELECT set_config('app.organization_id', '16000000-0000-0000-0000-000000000001', true);
SELECT set_config('app.user_id', '26000000-0000-0000-0000-000000000001', true);

INSERT INTO core.users (id, external_subject, email, display_name)
VALUES (
  '26000000-0000-0000-0000-000000000001',
  'briefing-subscriber',
  'briefing-subscriber@example.test',
  'Briefing Subscriber'
);

INSERT INTO core.organizations (id, slug, name, organization_type)
VALUES (
  '16000000-0000-0000-0000-000000000001',
  'briefing-tenant',
  'Briefing Tenant',
  'county'
);

INSERT INTO core.organization_memberships (organization_id, user_id, role_key)
VALUES (
  '16000000-0000-0000-0000-000000000001',
  '26000000-0000-0000-0000-000000000001',
  'researcher'
);

INSERT INTO research.briefing_subscriptions (organization_id, user_id)
VALUES (
  '16000000-0000-0000-0000-000000000001',
  '26000000-0000-0000-0000-000000000001'
);

SELECT civic.enqueue_daily_briefing_jobs('2026-07-24');

DO $$
DECLARE
  queued_job_count integer;
BEGIN
  SELECT count(*) INTO queued_job_count
  FROM civic.daily_briefing_jobs
  WHERE briefing_date = '2026-07-24' AND status = 'pending';

  IF queued_job_count <> 1 THEN
    RAISE EXCEPTION 'expected one queued daily briefing job, got %', queued_job_count;
  END IF;
END;
$$;

ROLLBACK;
