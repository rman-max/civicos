BEGIN;

CREATE TABLE research.briefing_subscriptions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
  user_id uuid NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
  delivery_channel text NOT NULL DEFAULT 'in_app' CHECK (delivery_channel IN ('in_app')),
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, user_id, delivery_channel)
);

CREATE TABLE civic.daily_briefing_jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
  briefing_date date NOT NULL,
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
  run_after timestamptz NOT NULL DEFAULT now(),
  lease_token uuid,
  leased_until timestamptz,
  attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
  last_error text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, briefing_date),
  CONSTRAINT daily_briefing_jobs_lease_pair_check CHECK (
    (lease_token IS NULL AND leased_until IS NULL)
    OR (lease_token IS NOT NULL AND leased_until IS NOT NULL)
  )
);

CREATE TABLE research.daily_briefings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
  briefing_date date NOT NULL,
  content jsonb NOT NULL CHECK (jsonb_typeof(content) = 'object'),
  generated_at timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, briefing_date)
);

CREATE TABLE research.daily_briefing_deliveries (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
  briefing_id uuid NOT NULL,
  subscription_id uuid NOT NULL,
  status text NOT NULL DEFAULT 'available' CHECK (status IN ('available', 'read')),
  delivered_at timestamptz NOT NULL DEFAULT now(),
  read_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, briefing_id, subscription_id),
  CONSTRAINT daily_briefing_deliveries_briefing_same_organization
    FOREIGN KEY (organization_id, briefing_id)
    REFERENCES research.daily_briefings (organization_id, id)
    ON DELETE CASCADE,
  CONSTRAINT daily_briefing_deliveries_subscription_same_organization
    FOREIGN KEY (organization_id, subscription_id)
    REFERENCES research.briefing_subscriptions (organization_id, id)
    ON DELETE CASCADE,
  CONSTRAINT daily_briefing_deliveries_read_after_delivery CHECK (
    read_at IS NULL OR read_at >= delivered_at
  )
);

CREATE INDEX daily_briefing_jobs_due_idx
  ON civic.daily_briefing_jobs (run_after) WHERE status IN ('pending', 'failed');
CREATE INDEX daily_briefing_jobs_lease_idx
  ON civic.daily_briefing_jobs (leased_until) WHERE status = 'processing';
CREATE INDEX briefing_subscriptions_active_idx
  ON research.briefing_subscriptions (organization_id, user_id) WHERE is_active;
CREATE INDEX daily_briefing_deliveries_by_subscription
  ON research.daily_briefing_deliveries (organization_id, subscription_id, delivered_at DESC);

CREATE TRIGGER briefing_subscriptions_set_updated_at
  BEFORE UPDATE ON research.briefing_subscriptions
  FOR EACH ROW EXECUTE FUNCTION core.touch_updated_at();
CREATE TRIGGER daily_briefing_jobs_set_updated_at
  BEFORE UPDATE ON civic.daily_briefing_jobs
  FOR EACH ROW EXECUTE FUNCTION core.touch_updated_at();
CREATE TRIGGER daily_briefings_set_updated_at
  BEFORE UPDATE ON research.daily_briefings
  FOR EACH ROW EXECUTE FUNCTION core.touch_updated_at();
CREATE TRIGGER daily_briefing_deliveries_set_updated_at
  BEFORE UPDATE ON research.daily_briefing_deliveries
  FOR EACH ROW EXECUTE FUNCTION core.touch_updated_at();

CREATE FUNCTION civic.enqueue_daily_briefing_jobs(target_date date)
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, civic, research
AS $$
DECLARE
  job_count integer;
BEGIN
  INSERT INTO civic.daily_briefing_jobs (organization_id, briefing_date)
  SELECT DISTINCT organization_id, target_date
  FROM research.briefing_subscriptions
  WHERE is_active
  ON CONFLICT (organization_id, briefing_date) DO NOTHING;
  GET DIAGNOSTICS job_count = ROW_COUNT;
  RETURN job_count;
END;
$$;

CREATE FUNCTION civic.claim_daily_briefing_jobs(job_limit integer)
RETURNS TABLE (job_id uuid, lease_token uuid, organization_id uuid, briefing_date date)
LANGUAGE sql
SECURITY DEFINER
SET search_path = pg_catalog, civic
AS $$
  WITH due AS (
    SELECT id
    FROM civic.daily_briefing_jobs
    WHERE run_after <= now()
      AND (status IN ('pending', 'failed') OR (status = 'processing' AND leased_until < now()))
    ORDER BY run_after, created_at
    FOR UPDATE SKIP LOCKED
    LIMIT GREATEST(1, LEAST(job_limit, 100))
  ), claimed AS (
    UPDATE civic.daily_briefing_jobs AS job
    SET status = 'processing', lease_token = gen_random_uuid(),
      leased_until = now() + interval '10 minutes', attempt_count = job.attempt_count + 1
    FROM due
    WHERE job.id = due.id
    RETURNING job.id, job.lease_token, job.organization_id, job.briefing_date
  )
  SELECT id, lease_token, organization_id, briefing_date FROM claimed;
$$;

REVOKE ALL ON FUNCTION civic.enqueue_daily_briefing_jobs(date) FROM PUBLIC;
REVOKE ALL ON FUNCTION civic.claim_daily_briefing_jobs(integer) FROM PUBLIC;

ALTER TABLE research.briefing_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE research.briefing_subscriptions FORCE ROW LEVEL SECURITY;
CREATE POLICY briefing_subscriptions_organization_tenant_isolation ON research.briefing_subscriptions
  USING (organization_id = core.current_organization_id())
  WITH CHECK (organization_id = core.current_organization_id());

ALTER TABLE civic.daily_briefing_jobs ENABLE ROW LEVEL SECURITY;
CREATE POLICY daily_briefing_jobs_organization_tenant_isolation ON civic.daily_briefing_jobs
  FOR ALL
  USING (organization_id = core.current_organization_id())
  WITH CHECK (organization_id = core.current_organization_id());

ALTER TABLE research.daily_briefings ENABLE ROW LEVEL SECURITY;
ALTER TABLE research.daily_briefings FORCE ROW LEVEL SECURITY;
CREATE POLICY daily_briefings_organization_tenant_isolation ON research.daily_briefings
  USING (organization_id = core.current_organization_id())
  WITH CHECK (organization_id = core.current_organization_id());

ALTER TABLE research.daily_briefing_deliveries ENABLE ROW LEVEL SECURITY;
ALTER TABLE research.daily_briefing_deliveries FORCE ROW LEVEL SECURITY;
CREATE POLICY daily_briefing_deliveries_organization_tenant_isolation ON research.daily_briefing_deliveries
  USING (organization_id = core.current_organization_id())
  WITH CHECK (organization_id = core.current_organization_id());

COMMENT ON TABLE research.daily_briefings IS 'Source-linked daily civic activity briefing generated once per tenant day.';
COMMENT ON TABLE research.briefing_subscriptions IS 'In-app daily briefing subscriptions; external delivery requires a separately approved provider.';

COMMIT;
