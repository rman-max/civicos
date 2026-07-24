BEGIN;

SELECT set_config('app.organization_id', '15000000-0000-0000-0000-000000000001', true);
SELECT set_config('app.user_id', '25000000-0000-0000-0000-000000000001', true);

INSERT INTO core.users (id, external_subject, email, display_name)
VALUES (
  '25000000-0000-0000-0000-000000000001',
  'notebook-researcher',
  'notebook-researcher@example.test',
  'Notebook Researcher'
);

INSERT INTO core.organizations (id, slug, name, organization_type)
VALUES (
  '15000000-0000-0000-0000-000000000001',
  'notebook-tenant',
  'Notebook Tenant',
  'county'
);

INSERT INTO core.organization_memberships (organization_id, user_id, role_key)
VALUES (
  '15000000-0000-0000-0000-000000000001',
  '25000000-0000-0000-0000-000000000001',
  'researcher'
);

INSERT INTO core.municipalities (id, organization_id, slug, name, municipality_type)
VALUES (
  '35000000-0000-0000-0000-000000000001',
  '15000000-0000-0000-0000-000000000001',
  'notebook-county',
  'Notebook County',
  'county'
);

INSERT INTO civic.sources (id, organization_id, municipality_id, name, source_type, canonical_url)
VALUES (
  '55000000-0000-0000-0000-000000000001',
  '15000000-0000-0000-0000-000000000001',
  '35000000-0000-0000-0000-000000000001',
  'Notebook records',
  'official_website',
  'https://example.test/notebook'
);

INSERT INTO civic.documents (id, organization_id, source_id, title, document_type, canonical_url)
VALUES (
  '65000000-0000-0000-0000-000000000001',
  '15000000-0000-0000-0000-000000000001',
  '55000000-0000-0000-0000-000000000001',
  'Notebook evidence',
  'report',
  'https://example.test/notebook/evidence'
);

INSERT INTO civic.document_versions (id, organization_id, document_id, version_number, content_hash, extracted_text)
VALUES (
  '75000000-0000-0000-0000-000000000001',
  '15000000-0000-0000-0000-000000000001',
  '65000000-0000-0000-0000-000000000001',
  1,
  'sha256:notebook',
  'Notebook evidence text'
);

INSERT INTO research.notebooks (id, organization_id, owner_user_id, title)
VALUES (
  '85000000-0000-0000-0000-000000000001',
  '15000000-0000-0000-0000-000000000001',
  '25000000-0000-0000-0000-000000000001',
  'Housing inquiry'
);

INSERT INTO research.saved_searches
  (organization_id, owner_user_id, notebook_id, title, query_text, filters)
VALUES (
  '15000000-0000-0000-0000-000000000001',
  '25000000-0000-0000-0000-000000000001',
  '85000000-0000-0000-0000-000000000001',
  'Housing search',
  'housing',
  '{"topic_ids": []}'::jsonb
);

INSERT INTO research.notebook_documents
  (organization_id, notebook_id, document_id, saved_by_user_id, note)
VALUES (
  '15000000-0000-0000-0000-000000000001',
  '85000000-0000-0000-0000-000000000001',
  '65000000-0000-0000-0000-000000000001',
  '25000000-0000-0000-0000-000000000001',
  'Review this source'
);

DO $$
DECLARE
  saved_search_count integer;
  saved_document_count integer;
BEGIN
  SELECT count(*) INTO saved_search_count FROM research.saved_searches;
  SELECT count(*) INTO saved_document_count FROM research.notebook_documents;

  IF saved_search_count <> 1 THEN
    RAISE EXCEPTION 'expected one saved search, got %', saved_search_count;
  END IF;
  IF saved_document_count <> 1 THEN
    RAISE EXCEPTION 'expected one saved document, got %', saved_document_count;
  END IF;
END;
$$;

ROLLBACK;
