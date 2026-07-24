-- CivicOS initial relational schema.
--
-- This migration is intentionally framework-neutral. Apply it with psql in one
-- transaction after provisioning PostgreSQL 17 or later. Application services
-- must set app.organization_id for every tenant-scoped transaction.

BEGIN;

CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS civic;
CREATE SCHEMA IF NOT EXISTS research;

CREATE FUNCTION core.current_organization_id()
RETURNS uuid
LANGUAGE sql
STABLE
AS $$
  SELECT NULLIF(current_setting('app.organization_id', true), '')::uuid;
$$;

CREATE FUNCTION core.current_user_id()
RETURNS uuid
LANGUAGE sql
STABLE
AS $$
  SELECT NULLIF(current_setting('app.user_id', true), '')::uuid;
$$;

CREATE FUNCTION core.touch_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

CREATE FUNCTION civic.prevent_immutable_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  RAISE EXCEPTION '% records are immutable', TG_TABLE_NAME
    USING ERRCODE = '55000';
END;
$$;

CREATE TABLE core.users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  external_subject text NOT NULL UNIQUE,
  email citext NOT NULL UNIQUE,
  display_name text NOT NULL CHECK (length(trim(display_name)) > 0),
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE core.organizations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug citext NOT NULL UNIQUE CHECK (length(trim(slug::text)) > 0),
  name text NOT NULL CHECK (length(trim(name)) > 0),
  organization_type text NOT NULL CHECK (length(trim(organization_type)) > 0),
  settings jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(settings) = 'object'),
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (id, slug)
);

CREATE TABLE core.organization_memberships (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
  user_id uuid NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
  role_key text NOT NULL CHECK (length(trim(role_key)) > 0),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, user_id)
);

CREATE TABLE core.municipalities (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
  parent_municipality_id uuid,
  slug citext NOT NULL CHECK (length(trim(slug::text)) > 0),
  name text NOT NULL CHECK (length(trim(name)) > 0),
  municipality_type text NOT NULL CHECK (length(trim(municipality_type)) > 0),
  jurisdiction_code text,
  geography jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(geography) = 'object'),
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, slug),
  CONSTRAINT municipalities_parent_same_organization
    FOREIGN KEY (organization_id, parent_municipality_id)
    REFERENCES core.municipalities (organization_id, id)
    ON DELETE RESTRICT
);

CREATE TABLE core.departments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
  municipality_id uuid NOT NULL,
  name text NOT NULL CHECK (length(trim(name)) > 0),
  department_type text NOT NULL CHECK (length(trim(department_type)) > 0),
  external_identifier text,
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, municipality_id, name),
  CONSTRAINT departments_municipality_same_organization
    FOREIGN KEY (organization_id, municipality_id)
    REFERENCES core.municipalities (organization_id, id)
    ON DELETE RESTRICT
);

CREATE TABLE civic.sources (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
  municipality_id uuid,
  department_id uuid,
  name text NOT NULL CHECK (length(trim(name)) > 0),
  source_type text NOT NULL CHECK (length(trim(source_type)) > 0),
  canonical_url text NOT NULL CHECK (length(trim(canonical_url)) > 0),
  acquisition_policy jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(acquisition_policy) = 'object'),
  licensing_note text,
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, canonical_url),
  CONSTRAINT sources_municipality_same_organization
    FOREIGN KEY (organization_id, municipality_id)
    REFERENCES core.municipalities (organization_id, id)
    ON DELETE RESTRICT,
  CONSTRAINT sources_department_same_organization
    FOREIGN KEY (organization_id, department_id)
    REFERENCES core.departments (organization_id, id)
    ON DELETE RESTRICT
);

CREATE TABLE civic.documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
  source_id uuid,
  municipality_id uuid,
  department_id uuid,
  title text NOT NULL CHECK (length(trim(title)) > 0),
  document_type text NOT NULL CHECK (length(trim(document_type)) > 0),
  canonical_url text,
  published_at timestamptz,
  first_observed_at timestamptz NOT NULL DEFAULT now(),
  visibility text NOT NULL DEFAULT 'public' CHECK (length(trim(visibility)) > 0),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id),
  CONSTRAINT documents_source_same_organization
    FOREIGN KEY (organization_id, source_id)
    REFERENCES civic.sources (organization_id, id)
    ON DELETE RESTRICT,
  CONSTRAINT documents_municipality_same_organization
    FOREIGN KEY (organization_id, municipality_id)
    REFERENCES core.municipalities (organization_id, id)
    ON DELETE RESTRICT,
  CONSTRAINT documents_department_same_organization
    FOREIGN KEY (organization_id, department_id)
    REFERENCES core.departments (organization_id, id)
    ON DELETE RESTRICT
);

CREATE UNIQUE INDEX documents_canonical_url_per_organization
  ON civic.documents (organization_id, canonical_url)
  WHERE canonical_url IS NOT NULL;

CREATE TABLE civic.document_versions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
  document_id uuid NOT NULL,
  version_number integer NOT NULL CHECK (version_number > 0),
  content_hash text NOT NULL CHECK (length(trim(content_hash)) > 0),
  language_code text,
  extracted_text text,
  extracted_metadata jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(extracted_metadata) = 'object'),
  published_at timestamptz,
  retrieved_at timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, document_id, version_number),
  CONSTRAINT document_versions_document_same_organization
    FOREIGN KEY (organization_id, document_id)
    REFERENCES civic.documents (organization_id, id)
    ON DELETE RESTRICT
);

CREATE TABLE civic.document_artifacts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
  document_version_id uuid NOT NULL,
  storage_key text NOT NULL CHECK (length(trim(storage_key)) > 0),
  media_type text NOT NULL CHECK (length(trim(media_type)) > 0),
  byte_size bigint NOT NULL CHECK (byte_size >= 0),
  checksum text NOT NULL CHECK (length(trim(checksum)) > 0),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, document_version_id, checksum),
  CONSTRAINT document_artifacts_version_same_organization
    FOREIGN KEY (organization_id, document_version_id)
    REFERENCES civic.document_versions (organization_id, id)
    ON DELETE RESTRICT
);

CREATE TABLE civic.meetings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
  municipality_id uuid NOT NULL,
  department_id uuid,
  source_id uuid,
  title text NOT NULL CHECK (length(trim(title)) > 0),
  meeting_type text NOT NULL CHECK (length(trim(meeting_type)) > 0),
  status text NOT NULL CHECK (length(trim(status)) > 0),
  scheduled_start_at timestamptz NOT NULL,
  scheduled_end_at timestamptz,
  location_name text,
  location_details jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(location_details) = 'object'),
  external_url text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id),
  CONSTRAINT meetings_valid_schedule CHECK (
    scheduled_end_at IS NULL OR scheduled_end_at >= scheduled_start_at
  ),
  CONSTRAINT meetings_municipality_same_organization
    FOREIGN KEY (organization_id, municipality_id)
    REFERENCES core.municipalities (organization_id, id)
    ON DELETE RESTRICT,
  CONSTRAINT meetings_department_same_organization
    FOREIGN KEY (organization_id, department_id)
    REFERENCES core.departments (organization_id, id)
    ON DELETE RESTRICT,
  CONSTRAINT meetings_source_same_organization
    FOREIGN KEY (organization_id, source_id)
    REFERENCES civic.sources (organization_id, id)
    ON DELETE RESTRICT
);

CREATE TABLE civic.meeting_agenda_items (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
  meeting_id uuid NOT NULL,
  position integer NOT NULL CHECK (position > 0),
  title text NOT NULL CHECK (length(trim(title)) > 0),
  description text,
  outcome text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, meeting_id, position),
  CONSTRAINT agenda_items_meeting_same_organization
    FOREIGN KEY (organization_id, meeting_id)
    REFERENCES civic.meetings (organization_id, id)
    ON DELETE CASCADE
);

CREATE TABLE civic.meeting_documents (
  organization_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
  meeting_id uuid NOT NULL,
  document_id uuid NOT NULL,
  relation_type text NOT NULL CHECK (length(trim(relation_type)) > 0),
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (organization_id, meeting_id, document_id, relation_type),
  CONSTRAINT meeting_documents_meeting_same_organization
    FOREIGN KEY (organization_id, meeting_id)
    REFERENCES civic.meetings (organization_id, id)
    ON DELETE CASCADE,
  CONSTRAINT meeting_documents_document_same_organization
    FOREIGN KEY (organization_id, document_id)
    REFERENCES civic.documents (organization_id, id)
    ON DELETE RESTRICT
);

CREATE TABLE civic.ordinances (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
  municipality_id uuid NOT NULL,
  department_id uuid,
  ordinance_number text NOT NULL CHECK (length(trim(ordinance_number)) > 0),
  title text NOT NULL CHECK (length(trim(title)) > 0),
  status text NOT NULL CHECK (length(trim(status)) > 0),
  introduced_at timestamptz,
  adopted_at timestamptz,
  effective_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, ordinance_number),
  CONSTRAINT ordinances_municipality_same_organization
    FOREIGN KEY (organization_id, municipality_id)
    REFERENCES core.municipalities (organization_id, id)
    ON DELETE RESTRICT,
  CONSTRAINT ordinances_department_same_organization
    FOREIGN KEY (organization_id, department_id)
    REFERENCES core.departments (organization_id, id)
    ON DELETE RESTRICT
);

CREATE TABLE civic.ordinance_documents (
  organization_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
  ordinance_id uuid NOT NULL,
  document_id uuid NOT NULL,
  relation_type text NOT NULL CHECK (length(trim(relation_type)) > 0),
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (organization_id, ordinance_id, document_id, relation_type),
  CONSTRAINT ordinance_documents_ordinance_same_organization
    FOREIGN KEY (organization_id, ordinance_id)
    REFERENCES civic.ordinances (organization_id, id)
    ON DELETE CASCADE,
  CONSTRAINT ordinance_documents_document_same_organization
    FOREIGN KEY (organization_id, document_id)
    REFERENCES civic.documents (organization_id, id)
    ON DELETE RESTRICT
);

CREATE TABLE civic.budgets (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
  municipality_id uuid NOT NULL,
  department_id uuid,
  fiscal_year smallint NOT NULL CHECK (fiscal_year >= 1900),
  name text NOT NULL CHECK (length(trim(name)) > 0),
  status text NOT NULL CHECK (length(trim(status)) > 0),
  adopted_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id),
  UNIQUE NULLS NOT DISTINCT (organization_id, municipality_id, department_id, fiscal_year, name),
  CONSTRAINT budgets_municipality_same_organization
    FOREIGN KEY (organization_id, municipality_id)
    REFERENCES core.municipalities (organization_id, id)
    ON DELETE RESTRICT,
  CONSTRAINT budgets_department_same_organization
    FOREIGN KEY (organization_id, department_id)
    REFERENCES core.departments (organization_id, id)
    ON DELETE RESTRICT
);

CREATE TABLE civic.budget_lines (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
  budget_id uuid NOT NULL,
  parent_budget_line_id uuid,
  line_code text,
  name text NOT NULL CHECK (length(trim(name)) > 0),
  line_type text NOT NULL CHECK (length(trim(line_type)) > 0),
  amount numeric(18, 2) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id),
  CONSTRAINT budget_lines_budget_same_organization
    FOREIGN KEY (organization_id, budget_id)
    REFERENCES civic.budgets (organization_id, id)
    ON DELETE CASCADE,
  CONSTRAINT budget_lines_parent_same_organization
    FOREIGN KEY (organization_id, parent_budget_line_id)
    REFERENCES civic.budget_lines (organization_id, id)
    ON DELETE RESTRICT
);

CREATE TABLE civic.budget_documents (
  organization_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
  budget_id uuid NOT NULL,
  document_id uuid NOT NULL,
  relation_type text NOT NULL CHECK (length(trim(relation_type)) > 0),
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (organization_id, budget_id, document_id, relation_type),
  CONSTRAINT budget_documents_budget_same_organization
    FOREIGN KEY (organization_id, budget_id)
    REFERENCES civic.budgets (organization_id, id)
    ON DELETE CASCADE,
  CONSTRAINT budget_documents_document_same_organization
    FOREIGN KEY (organization_id, document_id)
    REFERENCES civic.documents (organization_id, id)
    ON DELETE RESTRICT
);

CREATE TABLE civic.projects (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
  municipality_id uuid NOT NULL,
  department_id uuid,
  name text NOT NULL CHECK (length(trim(name)) > 0),
  project_type text NOT NULL CHECK (length(trim(project_type)) > 0),
  status text NOT NULL CHECK (length(trim(status)) > 0),
  external_identifier text,
  start_date date,
  end_date date,
  description text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id),
  CONSTRAINT projects_valid_dates CHECK (end_date IS NULL OR start_date IS NULL OR end_date >= start_date),
  CONSTRAINT projects_municipality_same_organization
    FOREIGN KEY (organization_id, municipality_id)
    REFERENCES core.municipalities (organization_id, id)
    ON DELETE RESTRICT,
  CONSTRAINT projects_department_same_organization
    FOREIGN KEY (organization_id, department_id)
    REFERENCES core.departments (organization_id, id)
    ON DELETE RESTRICT
);

CREATE UNIQUE INDEX projects_external_identifier_per_organization
  ON civic.projects (organization_id, external_identifier)
  WHERE external_identifier IS NOT NULL;

CREATE TABLE civic.project_documents (
  organization_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
  project_id uuid NOT NULL,
  document_id uuid NOT NULL,
  relation_type text NOT NULL CHECK (length(trim(relation_type)) > 0),
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (organization_id, project_id, document_id, relation_type),
  CONSTRAINT project_documents_project_same_organization
    FOREIGN KEY (organization_id, project_id)
    REFERENCES civic.projects (organization_id, id)
    ON DELETE CASCADE,
  CONSTRAINT project_documents_document_same_organization
    FOREIGN KEY (organization_id, document_id)
    REFERENCES civic.documents (organization_id, id)
    ON DELETE RESTRICT
);

CREATE TABLE civic.entities (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
  municipality_id uuid,
  entity_type text NOT NULL CHECK (length(trim(entity_type)) > 0),
  canonical_name text NOT NULL CHECK (length(trim(canonical_name)) > 0),
  description text,
  identifiers jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(identifiers) = 'object'),
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, entity_type, canonical_name),
  CONSTRAINT entities_municipality_same_organization
    FOREIGN KEY (organization_id, municipality_id)
    REFERENCES core.municipalities (organization_id, id)
    ON DELETE RESTRICT
);

CREATE TABLE civic.document_entity_mentions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
  document_version_id uuid NOT NULL,
  entity_id uuid NOT NULL,
  mention_text text NOT NULL CHECK (length(trim(mention_text)) > 0),
  start_offset integer CHECK (start_offset IS NULL OR start_offset >= 0),
  end_offset integer CHECK (end_offset IS NULL OR end_offset >= 0),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id),
  CONSTRAINT entity_mentions_valid_offsets CHECK (
    end_offset IS NULL OR start_offset IS NULL OR end_offset >= start_offset
  ),
  CONSTRAINT entity_mentions_version_same_organization
    FOREIGN KEY (organization_id, document_version_id)
    REFERENCES civic.document_versions (organization_id, id)
    ON DELETE RESTRICT,
  CONSTRAINT entity_mentions_entity_same_organization
    FOREIGN KEY (organization_id, entity_id)
    REFERENCES civic.entities (organization_id, id)
    ON DELETE RESTRICT
);

CREATE TABLE civic.topics (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
  parent_topic_id uuid,
  name text NOT NULL CHECK (length(trim(name)) > 0),
  description text,
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, parent_topic_id, name),
  CONSTRAINT topics_parent_same_organization
    FOREIGN KEY (organization_id, parent_topic_id)
    REFERENCES civic.topics (organization_id, id)
    ON DELETE RESTRICT
);

CREATE TABLE civic.topic_assignments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
  topic_id uuid NOT NULL,
  document_id uuid,
  meeting_id uuid,
  ordinance_id uuid,
  budget_id uuid,
  project_id uuid,
  entity_id uuid,
  department_id uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id),
  CONSTRAINT topic_assignments_one_target CHECK (
    num_nonnulls(document_id, meeting_id, ordinance_id, budget_id, project_id, entity_id, department_id) = 1
  ),
  CONSTRAINT topic_assignments_topic_same_organization
    FOREIGN KEY (organization_id, topic_id)
    REFERENCES civic.topics (organization_id, id)
    ON DELETE CASCADE,
  CONSTRAINT topic_assignments_document_same_organization
    FOREIGN KEY (organization_id, document_id)
    REFERENCES civic.documents (organization_id, id)
    ON DELETE CASCADE,
  CONSTRAINT topic_assignments_meeting_same_organization
    FOREIGN KEY (organization_id, meeting_id)
    REFERENCES civic.meetings (organization_id, id)
    ON DELETE CASCADE,
  CONSTRAINT topic_assignments_ordinance_same_organization
    FOREIGN KEY (organization_id, ordinance_id)
    REFERENCES civic.ordinances (organization_id, id)
    ON DELETE CASCADE,
  CONSTRAINT topic_assignments_budget_same_organization
    FOREIGN KEY (organization_id, budget_id)
    REFERENCES civic.budgets (organization_id, id)
    ON DELETE CASCADE,
  CONSTRAINT topic_assignments_project_same_organization
    FOREIGN KEY (organization_id, project_id)
    REFERENCES civic.projects (organization_id, id)
    ON DELETE CASCADE,
  CONSTRAINT topic_assignments_entity_same_organization
    FOREIGN KEY (organization_id, entity_id)
    REFERENCES civic.entities (organization_id, id)
    ON DELETE CASCADE,
  CONSTRAINT topic_assignments_department_same_organization
    FOREIGN KEY (organization_id, department_id)
    REFERENCES core.departments (organization_id, id)
    ON DELETE CASCADE
);

CREATE TABLE civic.citations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
  document_version_id uuid NOT NULL,
  citation_kind text NOT NULL CHECK (length(trim(citation_kind)) > 0),
  locator jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(locator) = 'object'),
  excerpt text,
  start_offset integer CHECK (start_offset IS NULL OR start_offset >= 0),
  end_offset integer CHECK (end_offset IS NULL OR end_offset >= 0),
  created_by_user_id uuid REFERENCES core.users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id),
  CONSTRAINT citations_valid_offsets CHECK (
    end_offset IS NULL OR start_offset IS NULL OR end_offset >= start_offset
  ),
  CONSTRAINT citations_version_same_organization
    FOREIGN KEY (organization_id, document_version_id)
    REFERENCES civic.document_versions (organization_id, id)
    ON DELETE RESTRICT
);

CREATE TABLE research.notebooks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
  owner_user_id uuid NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
  title text NOT NULL CHECK (length(trim(title)) > 0),
  description text,
  visibility text NOT NULL DEFAULT 'private' CHECK (length(trim(visibility)) > 0),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id)
);

CREATE TABLE research.notebook_entries (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
  notebook_id uuid NOT NULL,
  position integer NOT NULL CHECK (position > 0),
  entry_type text NOT NULL CHECK (length(trim(entry_type)) > 0),
  title text,
  body_markdown text,
  structured_content jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(structured_content) = 'object'),
  created_by_user_id uuid REFERENCES core.users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id),
  UNIQUE (organization_id, notebook_id, position),
  CONSTRAINT notebook_entries_notebook_same_organization
    FOREIGN KEY (organization_id, notebook_id)
    REFERENCES research.notebooks (organization_id, id)
    ON DELETE CASCADE
);

CREATE TABLE research.notebook_citations (
  organization_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
  notebook_entry_id uuid NOT NULL,
  citation_id uuid NOT NULL,
  note text,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (organization_id, notebook_entry_id, citation_id),
  CONSTRAINT notebook_citations_entry_same_organization
    FOREIGN KEY (organization_id, notebook_entry_id)
    REFERENCES research.notebook_entries (organization_id, id)
    ON DELETE CASCADE,
  CONSTRAINT notebook_citations_citation_same_organization
    FOREIGN KEY (organization_id, citation_id)
    REFERENCES civic.citations (organization_id, id)
    ON DELETE RESTRICT
);

CREATE TABLE research.collections (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
  owner_user_id uuid NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
  title text NOT NULL CHECK (length(trim(title)) > 0),
  description text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id)
);

CREATE TABLE research.collection_documents (
  organization_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
  collection_id uuid NOT NULL,
  document_id uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (organization_id, collection_id, document_id),
  CONSTRAINT collection_documents_collection_same_organization
    FOREIGN KEY (organization_id, collection_id)
    REFERENCES research.collections (organization_id, id)
    ON DELETE CASCADE,
  CONSTRAINT collection_documents_document_same_organization
    FOREIGN KEY (organization_id, document_id)
    REFERENCES civic.documents (organization_id, id)
    ON DELETE RESTRICT
);

CREATE INDEX documents_search_context
  ON civic.documents (organization_id, municipality_id, department_id, document_type, published_at DESC);
CREATE INDEX document_versions_by_document
  ON civic.document_versions (organization_id, document_id, version_number DESC);
CREATE INDEX meetings_by_schedule
  ON civic.meetings (organization_id, municipality_id, scheduled_start_at DESC);
CREATE INDEX ordinances_by_status
  ON civic.ordinances (organization_id, municipality_id, status, adopted_at DESC);
CREATE INDEX budgets_by_fiscal_year
  ON civic.budgets (organization_id, municipality_id, fiscal_year DESC);
CREATE INDEX projects_by_status
  ON civic.projects (organization_id, municipality_id, status);
CREATE INDEX entities_by_name
  ON civic.entities (organization_id, canonical_name);
CREATE INDEX topic_assignments_by_topic
  ON civic.topic_assignments (organization_id, topic_id);
CREATE INDEX citations_by_document_version
  ON civic.citations (organization_id, document_version_id);
CREATE INDEX notebooks_by_owner
  ON research.notebooks (organization_id, owner_user_id, updated_at DESC);

DO $$
DECLARE
  target_table regclass;
BEGIN
  FOREACH target_table IN ARRAY ARRAY[
    'core.users'::regclass,
    'core.organizations'::regclass,
    'core.organization_memberships'::regclass,
    'core.municipalities'::regclass,
    'core.departments'::regclass,
    'civic.sources'::regclass,
    'civic.documents'::regclass,
    'civic.meetings'::regclass,
    'civic.meeting_agenda_items'::regclass,
    'civic.ordinances'::regclass,
    'civic.budgets'::regclass,
    'civic.budget_lines'::regclass,
    'civic.projects'::regclass,
    'civic.entities'::regclass,
    'civic.topics'::regclass,
    'civic.citations'::regclass,
    'research.notebooks'::regclass,
    'research.notebook_entries'::regclass,
    'research.collections'::regclass
  ]
  LOOP
    EXECUTE format(
      'CREATE TRIGGER set_updated_at BEFORE UPDATE ON %s FOR EACH ROW EXECUTE FUNCTION core.touch_updated_at()',
      target_table
    );
  END LOOP;
END;
$$;

CREATE TRIGGER document_versions_are_immutable
  BEFORE UPDATE OR DELETE ON civic.document_versions
  FOR EACH ROW EXECUTE FUNCTION civic.prevent_immutable_mutation();

CREATE TRIGGER document_artifacts_are_immutable
  BEFORE UPDATE OR DELETE ON civic.document_artifacts
  FOR EACH ROW EXECUTE FUNCTION civic.prevent_immutable_mutation();

ALTER TABLE core.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.users FORCE ROW LEVEL SECURITY;
CREATE POLICY users_self_access ON core.users
  USING (id = core.current_user_id())
  WITH CHECK (id = core.current_user_id());

ALTER TABLE core.organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE core.organizations FORCE ROW LEVEL SECURITY;
CREATE POLICY organizations_tenant_isolation ON core.organizations
  USING (id = core.current_organization_id())
  WITH CHECK (id = core.current_organization_id());

DO $$
DECLARE
  target_table regclass;
BEGIN
  FOREACH target_table IN ARRAY ARRAY[
    'core.organization_memberships'::regclass,
    'core.municipalities'::regclass,
    'core.departments'::regclass,
    'civic.sources'::regclass,
    'civic.documents'::regclass,
    'civic.document_versions'::regclass,
    'civic.document_artifacts'::regclass,
    'civic.meetings'::regclass,
    'civic.meeting_agenda_items'::regclass,
    'civic.meeting_documents'::regclass,
    'civic.ordinances'::regclass,
    'civic.ordinance_documents'::regclass,
    'civic.budgets'::regclass,
    'civic.budget_lines'::regclass,
    'civic.budget_documents'::regclass,
    'civic.projects'::regclass,
    'civic.project_documents'::regclass,
    'civic.entities'::regclass,
    'civic.document_entity_mentions'::regclass,
    'civic.topics'::regclass,
    'civic.topic_assignments'::regclass,
    'civic.citations'::regclass,
    'research.notebooks'::regclass,
    'research.notebook_entries'::regclass,
    'research.notebook_citations'::regclass,
    'research.collections'::regclass,
    'research.collection_documents'::regclass
  ]
  LOOP
    EXECUTE format('ALTER TABLE %s ENABLE ROW LEVEL SECURITY', target_table);
    EXECUTE format('ALTER TABLE %s FORCE ROW LEVEL SECURITY', target_table);
    EXECUTE format(
      'CREATE POLICY organization_tenant_isolation ON %s USING (organization_id = core.current_organization_id()) WITH CHECK (organization_id = core.current_organization_id())',
      target_table
    );
  END LOOP;
END;
$$;

COMMENT ON SCHEMA core IS 'Identity, tenant, municipality, and department boundary.';
COMMENT ON SCHEMA civic IS 'Provenance-first civic records and their relationships.';
COMMENT ON SCHEMA research IS 'User research workspaces over cited civic evidence.';
COMMENT ON TABLE civic.document_versions IS 'Append-only source representations. Reprocessing creates a new row.';
COMMENT ON TABLE civic.citations IS 'Evidence locators tied to one immutable document version.';

COMMIT;
