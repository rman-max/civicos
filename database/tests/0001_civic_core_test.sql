BEGIN;

SELECT set_config('app.organization_id', '10000000-0000-0000-0000-000000000001', true);
SELECT set_config('app.user_id', '20000000-0000-0000-0000-000000000001', true);

INSERT INTO core.users (id, external_subject, email, display_name)
VALUES (
  '20000000-0000-0000-0000-000000000001',
  'test-subject',
  'researcher@example.test',
  'Test Researcher'
);

INSERT INTO core.organizations (id, slug, name, organization_type)
VALUES (
  '10000000-0000-0000-0000-000000000001',
  'tenant-a',
  'Tenant A',
  'county'
);

INSERT INTO core.organization_memberships (organization_id, user_id, role_key)
VALUES (
  '10000000-0000-0000-0000-000000000001',
  '20000000-0000-0000-0000-000000000001',
  'tenant_admin'
);

INSERT INTO core.municipalities (id, organization_id, slug, name, municipality_type)
VALUES (
  '30000000-0000-0000-0000-000000000001',
  '10000000-0000-0000-0000-000000000001',
  'example-county',
  'Example County',
  'county'
);

INSERT INTO core.departments (id, organization_id, municipality_id, name, department_type)
VALUES (
  '40000000-0000-0000-0000-000000000001',
  '10000000-0000-0000-0000-000000000001',
  '30000000-0000-0000-0000-000000000001',
  'County Council',
  'legislative_body'
);

INSERT INTO civic.sources (id, organization_id, municipality_id, department_id, name, source_type, canonical_url)
VALUES (
  '50000000-0000-0000-0000-000000000001',
  '10000000-0000-0000-0000-000000000001',
  '30000000-0000-0000-0000-000000000001',
  '40000000-0000-0000-0000-000000000001',
  'Council records',
  'official_website',
  'https://records.example.test/council'
);

INSERT INTO civic.documents (id, organization_id, source_id, title, document_type, canonical_url)
VALUES (
  '60000000-0000-0000-0000-000000000001',
  '10000000-0000-0000-0000-000000000001',
  '50000000-0000-0000-0000-000000000001',
  'Regular meeting agenda',
  'agenda',
  'https://records.example.test/council/agenda-1'
);

INSERT INTO civic.document_versions (id, organization_id, document_id, version_number, content_hash, extracted_text)
VALUES (
  '70000000-0000-0000-0000-000000000001',
  '10000000-0000-0000-0000-000000000001',
  '60000000-0000-0000-0000-000000000001',
  1,
  'sha256:test',
  'Agenda text'
);

DO $$
BEGIN
  BEGIN
    UPDATE civic.document_versions
    SET extracted_text = 'Changed text'
    WHERE id = '70000000-0000-0000-0000-000000000001';
    RAISE EXCEPTION 'expected immutable document version update to fail';
  EXCEPTION
    WHEN SQLSTATE '55000' THEN NULL;
  END;
END;
$$;

SELECT set_config('app.organization_id', '10000000-0000-0000-0000-000000000002', true);

INSERT INTO core.organizations (id, slug, name, organization_type)
VALUES (
  '10000000-0000-0000-0000-000000000002',
  'tenant-b',
  'Tenant B',
  'county'
);

SELECT set_config('app.organization_id', '10000000-0000-0000-0000-000000000001', true);

DO $$
DECLARE
  visible_organization_count integer;
  visible_document_count integer;
BEGIN
  SELECT count(*) INTO visible_organization_count FROM core.organizations;
  SELECT count(*) INTO visible_document_count FROM civic.documents;

  IF visible_organization_count <> 1 THEN
    RAISE EXCEPTION 'RLS leaked organization rows: %', visible_organization_count;
  END IF;

  IF visible_document_count <> 1 THEN
    RAISE EXCEPTION 'expected exactly one visible tenant document: %', visible_document_count;
  END IF;
END;
$$;

ROLLBACK;

