BEGIN;

-- Founder Intelligence is deliberately separate from the public civic record.
-- Every conclusion below retains its document-version evidence and is scoped to
-- the organization that owns the civic data.
CREATE SCHEMA IF NOT EXISTS founder;

CREATE TABLE founder.signals (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
  document_id uuid NOT NULL,
  document_version_id uuid NOT NULL,
  signal_type text NOT NULL CHECK (signal_type IN (
    'procurement', 'development', 'zoning_land_use', 'public_spending', 'grant_funding',
    'infrastructure', 'business_regulation', 'unusual_change_indicator'
  )),
  title text NOT NULL CHECK (length(trim(title)) > 0),
  summary text NOT NULL CHECK (length(trim(summary)) > 0),
  why_it_matters text NOT NULL CHECK (length(trim(why_it_matters)) > 0),
  economic_value_score numeric(4,3) NOT NULL CHECK (economic_value_score BETWEEN 0 AND 1),
  confidence_score numeric(4,3) NOT NULL CHECK (confidence_score BETWEEN 0 AND 1),
  recency_score numeric(4,3) NOT NULL CHECK (recency_score BETWEEN 0 AND 1),
  urgency_score numeric(4,3) NOT NULL CHECK (urgency_score BETWEEN 0 AND 1),
  evidence_strength_score numeric(4,3) NOT NULL CHECK (evidence_strength_score BETWEEN 0 AND 1),
  actionability_score numeric(4,3) NOT NULL CHECK (actionability_score BETWEEN 0 AND 1),
  commercial_significance integer NOT NULL CHECK (commercial_significance BETWEEN 0 AND 100),
  affected_organizations jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(affected_organizations) = 'array'),
  potential_customer_segments jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(potential_customer_segments) = 'array'),
  evidence jsonb NOT NULL CHECK (jsonb_typeof(evidence) = 'array' AND jsonb_array_length(evidence) > 0),
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'dismissed', 'archived')),
  discovered_at timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, document_version_id, signal_type),
  CONSTRAINT founder_signals_document_same_organization
    FOREIGN KEY (organization_id, document_id) REFERENCES civic.documents (organization_id, id) ON DELETE RESTRICT,
  CONSTRAINT founder_signals_version_same_organization
    FOREIGN KEY (organization_id, document_version_id)
    REFERENCES civic.document_versions (organization_id, id) ON DELETE RESTRICT
);

CREATE TABLE founder.opportunities (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
  signal_id uuid NOT NULL,
  what_happened text NOT NULL CHECK (length(trim(what_happened)) > 0),
  why_it_matters text NOT NULL CHECK (length(trim(why_it_matters)) > 0),
  where_money_may_be text NOT NULL CHECK (length(trim(where_money_may_be)) > 0),
  who_might_pay jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(who_might_pay) = 'array'),
  action_to_take text NOT NULL CHECK (length(trim(action_to_take)) > 0),
  urgency text NOT NULL CHECK (urgency IN ('low', 'medium', 'high')),
  score integer NOT NULL CHECK (score BETWEEN 0 AND 100),
  status text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'dismissed', 'archived')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, signal_id),
  CONSTRAINT founder_opportunities_signal_same_organization
    FOREIGN KEY (organization_id, signal_id) REFERENCES founder.signals (organization_id, id) ON DELETE CASCADE
);

CREATE TABLE founder.watchlists (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
  owner_user_id uuid NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
  watch_type text NOT NULL CHECK (watch_type IN (
    'company', 'industry', 'property', 'geographic_area', 'government_department', 'project', 'topic'
  )),
  name text NOT NULL CHECK (length(trim(name)) > 0),
  normalized_term text NOT NULL CHECK (length(trim(normalized_term)) > 0),
  criteria jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(criteria) = 'object'),
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, owner_user_id, watch_type, normalized_term)
);

CREATE TABLE founder.daily_briefs (
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

CREATE TABLE founder.watchlist_matches (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
  watchlist_id uuid NOT NULL,
  signal_id uuid NOT NULL,
  matched_term text NOT NULL CHECK (length(trim(matched_term)) > 0),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, watchlist_id, signal_id),
  CONSTRAINT founder_watchlist_matches_watchlist_same_organization
    FOREIGN KEY (organization_id, watchlist_id) REFERENCES founder.watchlists (organization_id, id) ON DELETE CASCADE,
  CONSTRAINT founder_watchlist_matches_signal_same_organization
    FOREIGN KEY (organization_id, signal_id) REFERENCES founder.signals (organization_id, id) ON DELETE CASCADE
);

CREATE TABLE founder.daily_brief_jobs (
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
  CONSTRAINT founder_daily_brief_jobs_lease_pair_check CHECK (
    (lease_token IS NULL AND leased_until IS NULL) OR (lease_token IS NOT NULL AND leased_until IS NOT NULL)
  )
);

CREATE INDEX founder_signals_rank_idx ON founder.signals (organization_id, status, commercial_significance DESC, discovered_at DESC);
CREATE INDEX founder_opportunities_rank_idx ON founder.opportunities (organization_id, status, score DESC, updated_at DESC);
CREATE INDEX founder_daily_brief_jobs_due_idx ON founder.daily_brief_jobs (run_after) WHERE status IN ('pending', 'failed');
CREATE INDEX founder_watchlist_matches_watchlist_idx
  ON founder.watchlist_matches (organization_id, watchlist_id, created_at DESC);

CREATE TRIGGER founder_signals_set_updated_at BEFORE UPDATE ON founder.signals
  FOR EACH ROW EXECUTE FUNCTION core.touch_updated_at();
CREATE TRIGGER founder_opportunities_set_updated_at BEFORE UPDATE ON founder.opportunities
  FOR EACH ROW EXECUTE FUNCTION core.touch_updated_at();
CREATE TRIGGER founder_watchlists_set_updated_at BEFORE UPDATE ON founder.watchlists
  FOR EACH ROW EXECUTE FUNCTION core.touch_updated_at();
CREATE TRIGGER founder_daily_briefs_set_updated_at BEFORE UPDATE ON founder.daily_briefs
  FOR EACH ROW EXECUTE FUNCTION core.touch_updated_at();
CREATE TRIGGER founder_daily_brief_jobs_set_updated_at BEFORE UPDATE ON founder.daily_brief_jobs
  FOR EACH ROW EXECUTE FUNCTION core.touch_updated_at();

CREATE FUNCTION founder.enqueue_daily_brief_jobs(target_date date)
RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, founder, core
AS $$
DECLARE job_count integer;
BEGIN
  INSERT INTO founder.daily_brief_jobs (organization_id, briefing_date)
  SELECT id, target_date FROM core.organizations WHERE is_active
  ON CONFLICT (organization_id, briefing_date) DO NOTHING;
  GET DIAGNOSTICS job_count = ROW_COUNT;
  RETURN job_count;
END;
$$;

CREATE FUNCTION founder.claim_daily_brief_jobs(job_limit integer)
RETURNS TABLE (job_id uuid, lease_token uuid, organization_id uuid, briefing_date date)
LANGUAGE sql SECURITY DEFINER
SET search_path = pg_catalog, founder
AS $$
  WITH due AS (
    SELECT id FROM founder.daily_brief_jobs
    WHERE run_after <= now()
      AND (status IN ('pending', 'failed') OR (status = 'processing' AND leased_until < now()))
    ORDER BY run_after, created_at FOR UPDATE SKIP LOCKED
    LIMIT GREATEST(1, LEAST(job_limit, 100))
  ), claimed AS (
    UPDATE founder.daily_brief_jobs AS job
    SET status = 'processing', lease_token = gen_random_uuid(), leased_until = now() + interval '10 minutes',
      attempt_count = job.attempt_count + 1
    FROM due WHERE job.id = due.id
    RETURNING job.id, job.lease_token, job.organization_id, job.briefing_date
  ) SELECT id, lease_token, organization_id, briefing_date FROM claimed;
$$;

CREATE FUNCTION founder.list_opportunities(maximum_rows integer)
RETURNS TABLE (
  opportunity_id uuid, signal_id uuid, signal_type text, title text, what_happened text, why_it_matters text,
  where_money_may_be text, who_might_pay jsonb, action_to_take text, urgency text, score integer,
  evidence jsonb, affected_organizations jsonb, source_url text, document_title text, discovered_at timestamptz
)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, founder, core, civic
AS $$
BEGIN
  PERFORM core.require_current_organization_admin();
  RETURN QUERY
  SELECT opportunity.id, signal.id, signal.signal_type, signal.title, opportunity.what_happened,
    opportunity.why_it_matters, opportunity.where_money_may_be, opportunity.who_might_pay,
    opportunity.action_to_take, opportunity.urgency, opportunity.score, signal.evidence,
    signal.affected_organizations, document.canonical_url, document.title, signal.discovered_at
  FROM founder.opportunities AS opportunity
  JOIN founder.signals AS signal ON signal.organization_id = opportunity.organization_id AND signal.id = opportunity.signal_id
  JOIN civic.documents AS document ON document.organization_id = signal.organization_id AND document.id = signal.document_id
  WHERE opportunity.organization_id = core.current_organization_id() AND opportunity.status = 'open'
  ORDER BY opportunity.score DESC, signal.discovered_at DESC
  LIMIT GREATEST(1, LEAST(maximum_rows, 100));
END;
$$;

CREATE FUNCTION founder.list_signals(maximum_rows integer)
RETURNS TABLE (
  id uuid, signal_type text, title text, summary text, why_it_matters text, commercial_significance integer,
  confidence_score numeric, evidence jsonb, affected_organizations jsonb, potential_customer_segments jsonb,
  source_url text, discovered_at timestamptz
)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, founder, core, civic
AS $$
BEGIN
  PERFORM core.require_current_organization_admin();
  RETURN QUERY
  SELECT signal.id, signal.signal_type, signal.title, signal.summary, signal.why_it_matters,
    signal.commercial_significance, signal.confidence_score, signal.evidence, signal.affected_organizations,
    signal.potential_customer_segments, document.canonical_url, signal.discovered_at
  FROM founder.signals AS signal
  JOIN civic.documents AS document ON document.organization_id = signal.organization_id AND document.id = signal.document_id
  WHERE signal.organization_id = core.current_organization_id() AND signal.status = 'active'
  ORDER BY signal.commercial_significance DESC, signal.discovered_at DESC
  LIMIT GREATEST(1, LEAST(maximum_rows, 100));
END;
$$;

CREATE FUNCTION founder.list_watchlists()
RETURNS TABLE (
  id uuid, watch_type text, name text, normalized_term text, criteria jsonb, is_active boolean,
  match_count bigint, latest_match_at timestamptz, created_at timestamptz
)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, founder, core
AS $$
BEGIN
  PERFORM core.require_current_organization_admin();
  RETURN QUERY SELECT watchlist.id, watchlist.watch_type, watchlist.name, watchlist.normalized_term,
    watchlist.criteria, watchlist.is_active, count(watch_match.id), max(watch_match.created_at), watchlist.created_at
  FROM founder.watchlists AS watchlist
  LEFT JOIN founder.watchlist_matches AS watch_match
    ON watch_match.organization_id = watchlist.organization_id AND watch_match.watchlist_id = watchlist.id
  WHERE watchlist.organization_id = core.current_organization_id()
  GROUP BY watchlist.id
  ORDER BY watchlist.is_active DESC, max(watch_match.created_at) DESC NULLS LAST, watchlist.created_at DESC;
END;
$$;

CREATE FUNCTION founder.create_watchlist(target_watch_type text, target_name text, target_term text, target_criteria jsonb)
RETURNS TABLE (
  id uuid, watch_type text, name text, normalized_term text, criteria jsonb, is_active boolean,
  match_count bigint, latest_match_at timestamptz, created_at timestamptz
)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, founder, core
AS $$
BEGIN
  PERFORM core.require_current_organization_admin();
  INSERT INTO founder.watchlists (organization_id, owner_user_id, watch_type, name, normalized_term, criteria)
  VALUES (core.current_organization_id(), core.current_user_id(), target_watch_type, target_name,
    lower(trim(target_term)), coalesce(target_criteria, '{}'::jsonb))
  ON CONFLICT (organization_id, owner_user_id, watch_type, normalized_term)
  DO UPDATE SET name = EXCLUDED.name, criteria = EXCLUDED.criteria, is_active = true
  RETURNING founder.watchlists.id, founder.watchlists.watch_type, founder.watchlists.name,
    founder.watchlists.normalized_term, founder.watchlists.criteria, founder.watchlists.is_active,
    0::bigint, NULL::timestamptz, founder.watchlists.created_at
  INTO id, watch_type, name, normalized_term, criteria, is_active, match_count, latest_match_at, created_at;
  RETURN NEXT;
END;
$$;

CREATE FUNCTION founder.latest_daily_brief()
RETURNS TABLE (id uuid, briefing_date date, content jsonb, generated_at timestamptz)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, founder, core
AS $$
BEGIN
  PERFORM core.require_current_organization_admin();
  RETURN QUERY SELECT brief.id, brief.briefing_date, brief.content, brief.generated_at
  FROM founder.daily_briefs AS brief
  WHERE brief.organization_id = core.current_organization_id()
  ORDER BY brief.briefing_date DESC LIMIT 1;
END;
$$;

REVOKE ALL ON ALL TABLES IN SCHEMA founder FROM PUBLIC;
REVOKE ALL ON FUNCTION founder.enqueue_daily_brief_jobs(date) FROM PUBLIC;
REVOKE ALL ON FUNCTION founder.claim_daily_brief_jobs(integer) FROM PUBLIC;
REVOKE ALL ON FUNCTION founder.list_opportunities(integer) FROM PUBLIC;
REVOKE ALL ON FUNCTION founder.list_signals(integer) FROM PUBLIC;
REVOKE ALL ON FUNCTION founder.list_watchlists() FROM PUBLIC;
REVOKE ALL ON FUNCTION founder.create_watchlist(text, text, text, jsonb) FROM PUBLIC;
REVOKE ALL ON FUNCTION founder.latest_daily_brief() FROM PUBLIC;

ALTER TABLE founder.signals ENABLE ROW LEVEL SECURITY;
ALTER TABLE founder.opportunities ENABLE ROW LEVEL SECURITY;
ALTER TABLE founder.watchlists ENABLE ROW LEVEL SECURITY;
ALTER TABLE founder.daily_briefs ENABLE ROW LEVEL SECURITY;
ALTER TABLE founder.daily_brief_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE founder.watchlist_matches ENABLE ROW LEVEL SECURITY;
CREATE POLICY founder_signals_organization_isolation ON founder.signals
  USING (organization_id = core.current_organization_id()) WITH CHECK (organization_id = core.current_organization_id());
CREATE POLICY founder_opportunities_organization_isolation ON founder.opportunities
  USING (organization_id = core.current_organization_id()) WITH CHECK (organization_id = core.current_organization_id());
CREATE POLICY founder_watchlists_organization_isolation ON founder.watchlists
  USING (organization_id = core.current_organization_id()) WITH CHECK (organization_id = core.current_organization_id());
CREATE POLICY founder_daily_briefs_organization_isolation ON founder.daily_briefs
  USING (organization_id = core.current_organization_id()) WITH CHECK (organization_id = core.current_organization_id());
CREATE POLICY founder_daily_brief_jobs_organization_isolation ON founder.daily_brief_jobs
  USING (organization_id = core.current_organization_id()) WITH CHECK (organization_id = core.current_organization_id());
CREATE POLICY founder_watchlist_matches_organization_isolation ON founder.watchlist_matches
  USING (organization_id = core.current_organization_id()) WITH CHECK (organization_id = core.current_organization_id());

COMMENT ON SCHEMA founder IS 'Private, evidence-bound commercial intelligence derived from civic records.';
COMMENT ON TABLE founder.signals IS 'Deterministic detection output. A signal is not a claim of contract award, market size, or commercial outcome.';
COMMENT ON TABLE founder.opportunities IS 'Founder-facing interpretation of a signal, preserving score inputs and document evidence.';

COMMIT;
