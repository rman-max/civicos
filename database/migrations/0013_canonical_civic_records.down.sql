BEGIN;
CREATE OR REPLACE FUNCTION founder.list_opportunities(maximum_rows integer)
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
CREATE OR REPLACE FUNCTION founder.list_signals(maximum_rows integer)
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
ALTER TABLE founder.signals DROP CONSTRAINT IF EXISTS founder_signals_canonical_change_fk;
ALTER TABLE founder.signals DROP CONSTRAINT IF EXISTS founder_signals_canonical_record_fk;
ALTER TABLE founder.signals DROP COLUMN IF EXISTS canonical_change_id;
ALTER TABLE founder.signals DROP COLUMN IF EXISTS canonical_record_id;
DROP TABLE IF EXISTS civic.canonical_record_changes;
DROP TABLE IF EXISTS civic.canonical_record_evidence;
ALTER TABLE civic.canonical_records DROP CONSTRAINT IF EXISTS canonical_records_current_version_fk;
ALTER TABLE civic.canonical_records DROP COLUMN IF EXISTS current_version_id;
DROP TABLE IF EXISTS civic.canonical_record_versions;
DROP TABLE IF EXISTS civic.canonical_records;
DROP FUNCTION IF EXISTS civic.set_canonical_record_search_vector();
COMMIT;
