BEGIN;

CREATE TABLE research.saved_searches (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
  owner_user_id uuid NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
  notebook_id uuid NOT NULL,
  title text NOT NULL CHECK (length(trim(title)) > 0),
  query_text text NOT NULL CHECK (length(trim(query_text)) > 0),
  filters jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(filters) = 'object'),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id),
  CONSTRAINT saved_searches_notebook_same_organization
    FOREIGN KEY (organization_id, notebook_id)
    REFERENCES research.notebooks (organization_id, id)
    ON DELETE CASCADE
);

CREATE TABLE research.notebook_documents (
  organization_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
  notebook_id uuid NOT NULL,
  document_id uuid NOT NULL,
  saved_by_user_id uuid NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
  note text,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (organization_id, notebook_id, document_id),
  CONSTRAINT notebook_documents_notebook_same_organization
    FOREIGN KEY (organization_id, notebook_id)
    REFERENCES research.notebooks (organization_id, id)
    ON DELETE CASCADE,
  CONSTRAINT notebook_documents_document_same_organization
    FOREIGN KEY (organization_id, document_id)
    REFERENCES civic.documents (organization_id, id)
    ON DELETE RESTRICT
);

CREATE INDEX saved_searches_by_notebook
  ON research.saved_searches (organization_id, notebook_id, updated_at DESC);
CREATE INDEX notebook_documents_by_notebook
  ON research.notebook_documents (organization_id, notebook_id, created_at DESC);

CREATE TRIGGER saved_searches_set_updated_at
  BEFORE UPDATE ON research.saved_searches
  FOR EACH ROW EXECUTE FUNCTION core.touch_updated_at();

ALTER TABLE research.saved_searches ENABLE ROW LEVEL SECURITY;
ALTER TABLE research.saved_searches FORCE ROW LEVEL SECURITY;
CREATE POLICY saved_searches_organization_tenant_isolation ON research.saved_searches
  USING (organization_id = core.current_organization_id())
  WITH CHECK (organization_id = core.current_organization_id());

ALTER TABLE research.notebook_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE research.notebook_documents FORCE ROW LEVEL SECURITY;
CREATE POLICY notebook_documents_organization_tenant_isolation ON research.notebook_documents
  USING (organization_id = core.current_organization_id())
  WITH CHECK (organization_id = core.current_organization_id());

COMMENT ON TABLE research.saved_searches IS 'Reusable tenant-scoped search queries saved to one research notebook.';
COMMENT ON TABLE research.notebook_documents IS 'Logical civic documents deliberately retained in one research notebook.';

COMMIT;
