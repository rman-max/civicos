BEGIN;

DO $$
DECLARE
  org_id uuid := '90000000-0000-0000-0000-000000000001';
  user_id uuid := '90000000-0000-0000-0000-000000000002';
  municipality_id uuid := '90000000-0000-0000-0000-000000000003';
  source_id uuid := '90000000-0000-0000-0000-000000000004';
  document_id uuid := '90000000-0000-0000-0000-000000000005';
  version_id uuid := '90000000-0000-0000-0000-000000000006';
  signal_id uuid;
  brief_jobs integer;
BEGIN
  INSERT INTO core.organizations (id, slug, name, organization_type)
  VALUES (org_id, 'founder-test', 'Founder Test', 'test');
  INSERT INTO core.users (id, external_subject, email, display_name)
  VALUES (user_id, 'founder-test-admin', 'founder-test@example.test', 'Founder Test');
  INSERT INTO core.organization_memberships (organization_id, user_id, role_key)
  VALUES (org_id, user_id, 'tenant_admin');
  INSERT INTO core.municipalities (id, organization_id, slug, name, municipality_type)
  VALUES (municipality_id, org_id, 'test', 'Test', 'county');
  INSERT INTO civic.sources (id, organization_id, municipality_id, name, source_type, canonical_url)
  VALUES (source_id, org_id, municipality_id, 'Test source', 'website', 'https://example.test/source');
  INSERT INTO civic.documents (id, organization_id, source_id, title, document_type, canonical_url)
  VALUES (document_id, org_id, source_id, 'Test RFP', 'public_notice', 'https://example.test/rfp');
  INSERT INTO civic.document_versions (id, organization_id, document_id, version_number, content_hash, extracted_text, extracted_metadata)
  VALUES (version_id, org_id, document_id, 1, 'test-hash', 'request for proposals', '{}');
  INSERT INTO founder.signals (
    organization_id, document_id, document_version_id, signal_type, title, summary, why_it_matters,
    economic_value_score, confidence_score, recency_score, urgency_score, evidence_strength_score,
    actionability_score, commercial_significance, evidence
  ) VALUES (
    org_id, document_id, version_id, 'procurement', 'Test procurement', 'RFP language detected', 'May create vendor demand',
    0.9, 0.8, 1.0, 0.9, 0.8, 0.9, 88, '[{"excerpt":"request for proposals"}]'
  ) RETURNING id INTO signal_id;
  INSERT INTO founder.opportunities (
    organization_id, signal_id, what_happened, why_it_matters, where_money_may_be, action_to_take, urgency, score
  ) VALUES (org_id, signal_id, 'RFP language detected', 'May create vendor demand', 'Vendor delivery', 'Read source', 'high', 88);

  PERFORM set_config('app.organization_id', org_id::text, true);
  PERFORM set_config('app.user_id', user_id::text, true);
  IF (SELECT count(*) FROM founder.list_opportunities(10)) <> 1 THEN
    RAISE EXCEPTION 'Founder opportunities must be available to tenant admins';
  END IF;
  IF (SELECT count(*) FROM founder.create_watchlist('industry', 'Construction', 'Construction', '{}')) <> 1 THEN
    RAISE EXCEPTION 'Founder watchlists must be creatable by tenant admins';
  END IF;

  SELECT founder.enqueue_daily_brief_jobs(CURRENT_DATE) INTO brief_jobs;
  IF brief_jobs < 1 THEN
    RAISE EXCEPTION 'Founder daily brief jobs must enqueue active organizations';
  END IF;
END;
$$;

ROLLBACK;
