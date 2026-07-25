BEGIN;

-- Raw civic.documents and civic.document_versions remain immutable source evidence.
-- These tables are a versioned, replaceable civic-record projection of that evidence.
CREATE TABLE civic.canonical_records (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
  raw_document_id uuid NOT NULL,
  source_id uuid,
  record_type text NOT NULL CHECK (record_type IN (
    'agenda', 'meeting_minutes', 'ordinance', 'resolution', 'permit', 'planning_zoning_case',
    'procurement_rfp', 'contract_award', 'budget_financial_report', 'property_parcel_record',
    'public_notice', 'newsletter', 'general_webpage', 'unknown'
  )),
  jurisdiction text,
  source_agency text NOT NULL,
  source_url text NOT NULL,
  source_document_id text NOT NULL,
  dedup_key text NOT NULL,
  title text NOT NULL,
  published_at date,
  event_date date,
  effective_date date,
  summary text NOT NULL,
  key_facts jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(key_facts) = 'array'),
  entities jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(entities) = 'array'),
  people jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(people) = 'array'),
  organizations jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(organizations) = 'array'),
  addresses jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(addresses) = 'array'),
  parcel_numbers jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(parcel_numbers) = 'array'),
  case_numbers jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(case_numbers) = 'array'),
  permit_numbers jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(permit_numbers) = 'array'),
  project_names jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(project_names) = 'array'),
  money_amounts jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(money_amounts) = 'array'),
  deadlines jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(deadlines) = 'array'),
  actions jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(actions) = 'array'),
  decisions jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(decisions) = 'array'),
  status text,
  topics jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(topics) = 'array'),
  typed_payload jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(typed_payload) = 'object'),
  extraction_confidence numeric(4,3) NOT NULL CHECK (extraction_confidence BETWEEN 0 AND 1),
  extraction_version text NOT NULL,
  first_seen_at timestamptz NOT NULL DEFAULT now(),
  last_seen_at timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  search_vector tsvector NOT NULL DEFAULT ''::tsvector,
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, raw_document_id, record_type),
  UNIQUE (organization_id, record_type, dedup_key),
  CONSTRAINT canonical_records_raw_document_fk
    FOREIGN KEY (organization_id, raw_document_id)
    REFERENCES civic.documents (organization_id, id) ON DELETE RESTRICT,
  CONSTRAINT canonical_records_source_fk
    FOREIGN KEY (organization_id, source_id)
    REFERENCES civic.sources (organization_id, id) ON DELETE SET NULL
);

CREATE TABLE civic.canonical_record_versions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL,
  canonical_record_id uuid NOT NULL,
  raw_document_version_id uuid NOT NULL,
  version_number integer NOT NULL CHECK (version_number > 0),
  extraction_version text NOT NULL,
  snapshot jsonb NOT NULL CHECK (jsonb_typeof(snapshot) = 'object'),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, canonical_record_id, version_number),
  UNIQUE (organization_id, raw_document_version_id, canonical_record_id),
  CONSTRAINT canonical_record_versions_record_fk
    FOREIGN KEY (organization_id, canonical_record_id)
    REFERENCES civic.canonical_records (organization_id, id) ON DELETE CASCADE,
  CONSTRAINT canonical_record_versions_raw_version_fk
    FOREIGN KEY (organization_id, raw_document_version_id)
    REFERENCES civic.document_versions (organization_id, id) ON DELETE RESTRICT
);

ALTER TABLE civic.canonical_records
  ADD COLUMN current_version_id uuid,
  ADD CONSTRAINT canonical_records_current_version_fk
    FOREIGN KEY (organization_id, current_version_id)
    REFERENCES civic.canonical_record_versions (organization_id, id) ON DELETE SET NULL;

CREATE TABLE civic.canonical_record_evidence (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL,
  canonical_record_version_id uuid NOT NULL,
  field_name text NOT NULL,
  value text NOT NULL,
  source_text text NOT NULL,
  source_url text NOT NULL,
  start_offset integer NOT NULL CHECK (start_offset >= 0),
  end_offset integer NOT NULL CHECK (end_offset >= start_offset),
  page_reference text,
  section_reference text,
  confidence numeric(4,3) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, canonical_record_version_id, field_name, start_offset, end_offset),
  CONSTRAINT canonical_record_evidence_version_fk
    FOREIGN KEY (organization_id, canonical_record_version_id)
    REFERENCES civic.canonical_record_versions (organization_id, id) ON DELETE CASCADE
);

CREATE TABLE civic.canonical_record_changes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL,
  canonical_record_id uuid NOT NULL,
  from_version_id uuid,
  to_version_id uuid NOT NULL,
  change_type text NOT NULL CHECK (change_type IN (
    'new_record', 'field_changed', 'new_permit_filed', 'hearing_scheduled', 'contract_awarded',
    'project_value_increased', 'zoning_approved', 'zoning_denied', 'deadline_changed',
    'property_transferred', 'ordinance_introduced', 'ordinance_adopted'
  )),
  field_name text,
  previous_value jsonb,
  current_value jsonb,
  evidence jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(evidence) = 'array'),
  confidence numeric(4,3) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  detected_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id),
  CONSTRAINT canonical_record_changes_record_fk
    FOREIGN KEY (organization_id, canonical_record_id)
    REFERENCES civic.canonical_records (organization_id, id) ON DELETE CASCADE,
  CONSTRAINT canonical_record_changes_from_version_fk
    FOREIGN KEY (organization_id, from_version_id)
    REFERENCES civic.canonical_record_versions (organization_id, id) ON DELETE SET NULL,
  CONSTRAINT canonical_record_changes_to_version_fk
    FOREIGN KEY (organization_id, to_version_id)
    REFERENCES civic.canonical_record_versions (organization_id, id) ON DELETE CASCADE
);

CREATE INDEX canonical_records_search_idx ON civic.canonical_records USING gin (search_vector);
CREATE INDEX canonical_records_type_date_idx
  ON civic.canonical_records (organization_id, record_type, published_at DESC NULLS LAST);
CREATE INDEX canonical_record_changes_record_detected_idx
  ON civic.canonical_record_changes (organization_id, canonical_record_id, detected_at DESC);

CREATE FUNCTION civic.set_canonical_record_search_vector()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  NEW.search_vector := to_tsvector('english', concat_ws(' ', NEW.title, NEW.summary,
    NEW.key_facts::text, NEW.entities::text, NEW.organizations::text, NEW.addresses::text,
    NEW.project_names::text, NEW.money_amounts::text, NEW.status));
  RETURN NEW;
END;
$$;

CREATE TRIGGER canonical_records_set_search_vector
  BEFORE INSERT OR UPDATE OF title, summary, key_facts, entities, organizations, addresses,
    project_names, money_amounts, status ON civic.canonical_records
  FOR EACH ROW EXECUTE FUNCTION civic.set_canonical_record_search_vector();
CREATE TRIGGER canonical_records_set_updated_at BEFORE UPDATE ON civic.canonical_records
  FOR EACH ROW EXECUTE FUNCTION core.touch_updated_at();

ALTER TABLE founder.signals ADD COLUMN canonical_record_id uuid;
ALTER TABLE founder.signals ADD COLUMN canonical_change_id uuid;
ALTER TABLE founder.signals
  ADD CONSTRAINT founder_signals_canonical_record_fk
  FOREIGN KEY (organization_id, canonical_record_id)
  REFERENCES civic.canonical_records (organization_id, id) ON DELETE RESTRICT;
ALTER TABLE founder.signals
  ADD CONSTRAINT founder_signals_canonical_change_fk
  FOREIGN KEY (organization_id, canonical_change_id)
  REFERENCES civic.canonical_record_changes (organization_id, id) ON DELETE SET NULL;
CREATE INDEX founder_signals_canonical_record_idx
  ON founder.signals (organization_id, canonical_record_id, discovered_at DESC)
  WHERE canonical_record_id IS NOT NULL;

-- Existing raw-only signals are retained for audit but are not eligible for the
-- Founder console. New opportunities must originate from a canonical record.
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
    signal.affected_organizations, record.source_url, record.title, signal.discovered_at
  FROM founder.opportunities AS opportunity
  JOIN founder.signals AS signal ON signal.organization_id = opportunity.organization_id AND signal.id = opportunity.signal_id
  JOIN civic.canonical_records AS record
    ON record.organization_id = signal.organization_id AND record.id = signal.canonical_record_id
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
    signal.potential_customer_segments, record.source_url, signal.discovered_at
  FROM founder.signals AS signal
  JOIN civic.canonical_records AS record
    ON record.organization_id = signal.organization_id AND record.id = signal.canonical_record_id
  WHERE signal.organization_id = core.current_organization_id() AND signal.status = 'active'
  ORDER BY signal.commercial_significance DESC, signal.discovered_at DESC
  LIMIT GREATEST(1, LEAST(maximum_rows, 100));
END;
$$;

DO $$
DECLARE table_name text;
BEGIN
  FOREACH table_name IN ARRAY ARRAY[
    'canonical_records', 'canonical_record_versions', 'canonical_record_evidence', 'canonical_record_changes'
  ] LOOP
    EXECUTE format('ALTER TABLE civic.%I ENABLE ROW LEVEL SECURITY', table_name);
    EXECUTE format('ALTER TABLE civic.%I FORCE ROW LEVEL SECURITY', table_name);
    EXECUTE format(
      'CREATE POLICY %I ON civic.%I FOR ALL USING (organization_id = core.current_organization_id()) WITH CHECK (organization_id = core.current_organization_id())',
      table_name || '_organization_isolation', table_name
    );
  END LOOP;
END $$;

COMMIT;
