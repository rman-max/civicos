BEGIN;

CREATE TABLE civic.locations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
  municipality_id uuid,
  name text NOT NULL CHECK (length(trim(name)) > 0),
  location_type text NOT NULL DEFAULT 'place' CHECK (length(trim(location_type)) > 0),
  address text,
  latitude numeric(9, 6),
  longitude numeric(9, 6),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(metadata) = 'object'),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id),
  UNIQUE NULLS NOT DISTINCT (organization_id, municipality_id, name, address),
  CONSTRAINT locations_municipality_same_organization
    FOREIGN KEY (organization_id, municipality_id)
    REFERENCES core.municipalities (organization_id, id)
    ON DELETE RESTRICT,
  CONSTRAINT locations_valid_latitude CHECK (latitude IS NULL OR latitude BETWEEN -90 AND 90),
  CONSTRAINT locations_valid_longitude CHECK (longitude IS NULL OR longitude BETWEEN -180 AND 180)
);

CREATE TABLE civic.officials (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
  entity_id uuid NOT NULL,
  municipality_id uuid,
  department_id uuid,
  title text NOT NULL CHECK (length(trim(title)) > 0),
  starts_on date,
  ends_on date,
  is_active boolean NOT NULL DEFAULT true,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(metadata) = 'object'),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, id),
  UNIQUE NULLS NOT DISTINCT (organization_id, entity_id, department_id, title, starts_on),
  CONSTRAINT officials_entity_same_organization
    FOREIGN KEY (organization_id, entity_id)
    REFERENCES civic.entities (organization_id, id)
    ON DELETE RESTRICT,
  CONSTRAINT officials_municipality_same_organization
    FOREIGN KEY (organization_id, municipality_id)
    REFERENCES core.municipalities (organization_id, id)
    ON DELETE RESTRICT,
  CONSTRAINT officials_department_same_organization
    FOREIGN KEY (organization_id, department_id)
    REFERENCES core.departments (organization_id, id)
    ON DELETE RESTRICT,
  CONSTRAINT officials_valid_dates CHECK (ends_on IS NULL OR starts_on IS NULL OR ends_on >= starts_on)
);

ALTER TABLE civic.meetings
  ADD COLUMN location_id uuid,
  ADD CONSTRAINT meetings_location_same_organization
    FOREIGN KEY (organization_id, location_id)
    REFERENCES civic.locations (organization_id, id)
    ON DELETE RESTRICT;

ALTER TABLE civic.projects
  ADD COLUMN location_id uuid,
  ADD CONSTRAINT projects_location_same_organization
    FOREIGN KEY (organization_id, location_id)
    REFERENCES civic.locations (organization_id, id)
    ON DELETE RESTRICT;

CREATE TABLE civic.document_location_mentions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
  document_version_id uuid NOT NULL,
  location_id uuid NOT NULL,
  mention_text text NOT NULL CHECK (length(trim(mention_text)) > 0),
  start_offset integer NOT NULL CHECK (start_offset >= 0),
  end_offset integer NOT NULL CHECK (end_offset >= start_offset),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (organization_id, document_version_id, location_id, start_offset, end_offset),
  CONSTRAINT document_location_mentions_version_same_organization
    FOREIGN KEY (organization_id, document_version_id)
    REFERENCES civic.document_versions (organization_id, id)
    ON DELETE RESTRICT,
  CONSTRAINT document_location_mentions_location_same_organization
    FOREIGN KEY (organization_id, location_id)
    REFERENCES civic.locations (organization_id, id)
    ON DELETE RESTRICT
);

CREATE TABLE civic.knowledge_graph_edges (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
  subject_type text NOT NULL CHECK (subject_type IN (
    'document', 'meeting', 'ordinance', 'budget', 'department', 'official', 'topic', 'project', 'location'
  )),
  subject_id uuid NOT NULL,
  predicate text NOT NULL CHECK (length(trim(predicate)) > 0),
  object_type text NOT NULL CHECK (object_type IN (
    'document', 'meeting', 'ordinance', 'budget', 'department', 'official', 'topic', 'project', 'location'
  )),
  object_id uuid NOT NULL,
  evidence_document_version_id uuid,
  evidence_start_offset integer CHECK (evidence_start_offset IS NULL OR evidence_start_offset >= 0),
  evidence_end_offset integer CHECK (evidence_end_offset IS NULL OR evidence_end_offset >= evidence_start_offset),
  discovery_method text NOT NULL CHECK (length(trim(discovery_method)) > 0),
  confidence numeric(4, 3) NOT NULL DEFAULT 1.000 CHECK (confidence >= 0 AND confidence <= 1),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(metadata) = 'object'),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE NULLS NOT DISTINCT (
    organization_id, subject_type, subject_id, predicate, object_type, object_id, evidence_document_version_id
  ),
  CONSTRAINT knowledge_graph_edges_not_self_referential CHECK (
    subject_type <> object_type OR subject_id <> object_id
  ),
  CONSTRAINT knowledge_graph_edges_evidence_same_organization
    FOREIGN KEY (organization_id, evidence_document_version_id)
    REFERENCES civic.document_versions (organization_id, id)
    ON DELETE RESTRICT
);

CREATE INDEX document_location_mentions_location_idx
  ON civic.document_location_mentions (organization_id, location_id, document_version_id);
CREATE INDEX knowledge_graph_edges_subject_idx
  ON civic.knowledge_graph_edges (organization_id, subject_type, subject_id);
CREATE INDEX knowledge_graph_edges_object_idx
  ON civic.knowledge_graph_edges (organization_id, object_type, object_id);
CREATE INDEX knowledge_graph_edges_evidence_idx
  ON civic.knowledge_graph_edges (organization_id, evidence_document_version_id)
  WHERE evidence_document_version_id IS NOT NULL;

CREATE TRIGGER locations_set_updated_at
  BEFORE UPDATE ON civic.locations
  FOR EACH ROW EXECUTE FUNCTION core.set_updated_at();
CREATE TRIGGER officials_set_updated_at
  BEFORE UPDATE ON civic.officials
  FOR EACH ROW EXECUTE FUNCTION core.set_updated_at();

CREATE FUNCTION civic.knowledge_graph_node_exists(
  node_organization_id uuid,
  node_type text,
  node_id uuid
)
RETURNS boolean
LANGUAGE plpgsql
STABLE
SET search_path = pg_catalog, core, civic
AS $$
BEGIN
  CASE node_type
    WHEN 'document' THEN
      RETURN EXISTS (SELECT 1 FROM civic.documents WHERE organization_id = node_organization_id AND id = node_id);
    WHEN 'meeting' THEN
      RETURN EXISTS (SELECT 1 FROM civic.meetings WHERE organization_id = node_organization_id AND id = node_id);
    WHEN 'ordinance' THEN
      RETURN EXISTS (SELECT 1 FROM civic.ordinances WHERE organization_id = node_organization_id AND id = node_id);
    WHEN 'budget' THEN
      RETURN EXISTS (SELECT 1 FROM civic.budgets WHERE organization_id = node_organization_id AND id = node_id);
    WHEN 'department' THEN
      RETURN EXISTS (SELECT 1 FROM core.departments WHERE organization_id = node_organization_id AND id = node_id);
    WHEN 'official' THEN
      RETURN EXISTS (SELECT 1 FROM civic.officials WHERE organization_id = node_organization_id AND id = node_id);
    WHEN 'topic' THEN
      RETURN EXISTS (SELECT 1 FROM civic.topics WHERE organization_id = node_organization_id AND id = node_id);
    WHEN 'project' THEN
      RETURN EXISTS (SELECT 1 FROM civic.projects WHERE organization_id = node_organization_id AND id = node_id);
    WHEN 'location' THEN
      RETURN EXISTS (SELECT 1 FROM civic.locations WHERE organization_id = node_organization_id AND id = node_id);
    ELSE
      RETURN false;
  END CASE;
END;
$$;

CREATE FUNCTION civic.validate_knowledge_graph_edge()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF NOT civic.knowledge_graph_node_exists(NEW.organization_id, NEW.subject_type, NEW.subject_id) THEN
    RAISE EXCEPTION 'knowledge graph subject does not exist in organization';
  END IF;
  IF NOT civic.knowledge_graph_node_exists(NEW.organization_id, NEW.object_type, NEW.object_id) THEN
    RAISE EXCEPTION 'knowledge graph object does not exist in organization';
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER knowledge_graph_edges_validate_nodes
  BEFORE INSERT OR UPDATE OF organization_id, subject_type, subject_id, object_type, object_id
  ON civic.knowledge_graph_edges
  FOR EACH ROW EXECUTE FUNCTION civic.validate_knowledge_graph_edge();

DO $$
DECLARE
  table_name text;
BEGIN
  FOREACH table_name IN ARRAY ARRAY[
    'locations', 'officials', 'document_location_mentions', 'knowledge_graph_edges'
  ] LOOP
    EXECUTE format('ALTER TABLE civic.%I ENABLE ROW LEVEL SECURITY', table_name);
    EXECUTE format(
      'CREATE POLICY %I ON civic.%I FOR ALL USING (organization_id = core.current_organization_id()) WITH CHECK (organization_id = core.current_organization_id())',
      table_name || '_organization_isolation', table_name
    );
  END LOOP;
END $$;

CREATE VIEW civic.knowledge_graph_relationships
WITH (security_invoker = true)
AS
  SELECT subject_type, subject_id, predicate, object_type, object_id,
    evidence_document_version_id, evidence_start_offset, evidence_end_offset,
    discovery_method, confidence, metadata, created_at
  FROM civic.knowledge_graph_edges
  UNION ALL
  SELECT 'document', document_id, relation_type, 'meeting', meeting_id,
    NULL::uuid, NULL::integer, NULL::integer, 'structural', 1.000::numeric, '{}'::jsonb, created_at
  FROM civic.meeting_documents
  UNION ALL
  SELECT 'document', document_id, relation_type, 'ordinance', ordinance_id,
    NULL::uuid, NULL::integer, NULL::integer, 'structural', 1.000::numeric, '{}'::jsonb, created_at
  FROM civic.ordinance_documents
  UNION ALL
  SELECT 'document', document_id, relation_type, 'budget', budget_id,
    NULL::uuid, NULL::integer, NULL::integer, 'structural', 1.000::numeric, '{}'::jsonb, created_at
  FROM civic.budget_documents
  UNION ALL
  SELECT 'document', document_id, relation_type, 'project', project_id,
    NULL::uuid, NULL::integer, NULL::integer, 'structural', 1.000::numeric, '{}'::jsonb, created_at
  FROM civic.project_documents
  UNION ALL
  SELECT 'document', id, 'owned_by_department', 'department', department_id,
    NULL::uuid, NULL::integer, NULL::integer, 'structural', 1.000::numeric, '{}'::jsonb, created_at
  FROM civic.documents WHERE department_id IS NOT NULL
  UNION ALL
  SELECT 'document', document_id, 'about_topic', 'topic', topic_id,
    NULL::uuid, NULL::integer, NULL::integer, 'structural', 1.000::numeric, '{}'::jsonb, created_at
  FROM civic.topic_assignments WHERE document_id IS NOT NULL
  UNION ALL
  SELECT 'document', document_version.document_id, 'mentions_official', 'official', official.id,
    mention.document_version_id, mention.start_offset, mention.end_offset,
    'structural', 1.000::numeric, jsonb_build_object('mention_text', mention.mention_text), mention.created_at
  FROM civic.document_entity_mentions AS mention
  JOIN civic.document_versions AS document_version
    ON document_version.organization_id = mention.organization_id
    AND document_version.id = mention.document_version_id
  JOIN civic.officials AS official
    ON official.organization_id = mention.organization_id
    AND official.entity_id = mention.entity_id
  UNION ALL
  SELECT 'document', document_version.document_id, 'mentions_location', 'location', location_mention.location_id,
    location_mention.document_version_id, location_mention.start_offset, location_mention.end_offset,
    'structural', 1.000::numeric, jsonb_build_object('mention_text', location_mention.mention_text), location_mention.created_at
  FROM civic.document_location_mentions AS location_mention
  JOIN civic.document_versions AS document_version
    ON document_version.organization_id = location_mention.organization_id
    AND document_version.id = location_mention.document_version_id
  UNION ALL
  SELECT 'meeting', id, 'organized_by_department', 'department', department_id,
    NULL::uuid, NULL::integer, NULL::integer, 'structural', 1.000::numeric, '{}'::jsonb, created_at
  FROM civic.meetings WHERE department_id IS NOT NULL
  UNION ALL
  SELECT 'meeting', id, 'held_at', 'location', location_id,
    NULL::uuid, NULL::integer, NULL::integer, 'structural', 1.000::numeric, '{}'::jsonb, created_at
  FROM civic.meetings WHERE location_id IS NOT NULL
  UNION ALL
  SELECT 'ordinance', id, 'owned_by_department', 'department', department_id,
    NULL::uuid, NULL::integer, NULL::integer, 'structural', 1.000::numeric, '{}'::jsonb, created_at
  FROM civic.ordinances WHERE department_id IS NOT NULL
  UNION ALL
  SELECT 'budget', id, 'owned_by_department', 'department', department_id,
    NULL::uuid, NULL::integer, NULL::integer, 'structural', 1.000::numeric, '{}'::jsonb, created_at
  FROM civic.budgets WHERE department_id IS NOT NULL
  UNION ALL
  SELECT 'project', id, 'owned_by_department', 'department', department_id,
    NULL::uuid, NULL::integer, NULL::integer, 'structural', 1.000::numeric, '{}'::jsonb, created_at
  FROM civic.projects WHERE department_id IS NOT NULL
  UNION ALL
  SELECT 'project', id, 'located_at', 'location', location_id,
    NULL::uuid, NULL::integer, NULL::integer, 'structural', 1.000::numeric, '{}'::jsonb, created_at
  FROM civic.projects WHERE location_id IS NOT NULL
  UNION ALL
  SELECT 'official', id, 'serves_department', 'department', department_id,
    NULL::uuid, NULL::integer, NULL::integer, 'structural', 1.000::numeric, '{}'::jsonb, created_at
  FROM civic.officials WHERE department_id IS NOT NULL;

CREATE VIEW civic.related_documents
WITH (security_invoker = true)
AS
  SELECT DISTINCT left_edge.subject_id AS document_id,
    right_edge.subject_id AS related_document_id,
    left_edge.object_type AS shared_node_type,
    left_edge.object_id AS shared_node_id,
    left_edge.predicate AS relation_type
  FROM civic.knowledge_graph_relationships AS left_edge
  JOIN civic.knowledge_graph_relationships AS right_edge
    ON right_edge.subject_type = 'document'
    AND right_edge.subject_id <> left_edge.subject_id
    AND right_edge.object_type = left_edge.object_type
    AND right_edge.object_id = left_edge.object_id
  WHERE left_edge.subject_type = 'document';

COMMIT;
