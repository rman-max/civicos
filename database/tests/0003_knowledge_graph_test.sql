BEGIN;

SELECT set_config('app.organization_id', '12000000-0000-0000-0000-000000000001', true);

INSERT INTO core.organizations (id, slug, name, organization_type)
VALUES ('12000000-0000-0000-0000-000000000001', 'graph-tenant', 'Graph Tenant', 'county');

INSERT INTO core.municipalities (id, organization_id, slug, name, municipality_type)
VALUES (
  '32000000-0000-0000-0000-000000000001',
  '12000000-0000-0000-0000-000000000001',
  'graph-county',
  'Graph County',
  'county'
);

INSERT INTO core.departments (id, organization_id, municipality_id, name, department_type)
VALUES (
  '42000000-0000-0000-0000-000000000001',
  '12000000-0000-0000-0000-000000000001',
  '32000000-0000-0000-0000-000000000001',
  'Planning Department',
  'department'
);

INSERT INTO civic.locations (id, organization_id, municipality_id, name)
VALUES (
  '82000000-0000-0000-0000-000000000001',
  '12000000-0000-0000-0000-000000000001',
  '32000000-0000-0000-0000-000000000001',
  'Civic Center'
);

INSERT INTO civic.entities (id, organization_id, entity_type, canonical_name)
VALUES (
  '72000000-0000-0000-0000-000000000001',
  '12000000-0000-0000-0000-000000000001',
  'person',
  'Jane Doe'
);

INSERT INTO civic.officials (id, organization_id, entity_id, department_id, title)
VALUES (
  '92000000-0000-0000-0000-000000000001',
  '12000000-0000-0000-0000-000000000001',
  '72000000-0000-0000-0000-000000000001',
  '42000000-0000-0000-0000-000000000001',
  'Director'
);

INSERT INTO civic.documents (id, organization_id, department_id, title, document_type, canonical_url)
VALUES
  (
    '62000000-0000-0000-0000-000000000001',
    '12000000-0000-0000-0000-000000000001',
    '42000000-0000-0000-0000-000000000001',
    'Project update',
    'report',
    'https://example.test/project-update'
  ),
  (
    '62000000-0000-0000-0000-000000000002',
    '12000000-0000-0000-0000-000000000001',
    '42000000-0000-0000-0000-000000000001',
    'Project agenda',
    'meeting_agenda',
    'https://example.test/project-agenda'
  );

INSERT INTO civic.document_versions (id, organization_id, document_id, version_number, content_hash)
VALUES (
  '73000000-0000-0000-0000-000000000001',
  '12000000-0000-0000-0000-000000000001',
  '62000000-0000-0000-0000-000000000001',
  1,
  'sha256:graph'
);

INSERT INTO civic.document_location_mentions (
  organization_id, document_version_id, location_id, mention_text, start_offset, end_offset
)
VALUES (
  '12000000-0000-0000-0000-000000000001',
  '73000000-0000-0000-0000-000000000001',
  '82000000-0000-0000-0000-000000000001',
  'Civic Center',
  0,
  12
);

INSERT INTO civic.knowledge_graph_edges (
  organization_id, subject_type, subject_id, predicate, object_type, object_id,
  evidence_document_version_id, evidence_start_offset, evidence_end_offset, discovery_method, confidence
)
VALUES (
  '12000000-0000-0000-0000-000000000001',
  'document',
  '62000000-0000-0000-0000-000000000001',
  'mentions_official',
  'official',
  '92000000-0000-0000-0000-000000000001',
  '73000000-0000-0000-0000-000000000001',
  0,
  8,
  'test',
  0.900
);

INSERT INTO civic.topics (id, organization_id, name)
VALUES ('52000000-0000-0000-0000-000000000001', '12000000-0000-0000-0000-000000000001', 'infrastructure');

INSERT INTO civic.topic_assignments (organization_id, topic_id, document_id)
VALUES
  ('12000000-0000-0000-0000-000000000001', '52000000-0000-0000-0000-000000000001', '62000000-0000-0000-0000-000000000001'),
  ('12000000-0000-0000-0000-000000000001', '52000000-0000-0000-0000-000000000001', '62000000-0000-0000-0000-000000000002');

DO $$
DECLARE
  graph_edge_count integer;
  related_document_count integer;
BEGIN
  SELECT count(*) INTO graph_edge_count
  FROM civic.knowledge_graph_relationships
  WHERE subject_type = 'document'
    AND subject_id = '62000000-0000-0000-0000-000000000001'
    AND object_type = 'official'
    AND object_id = '92000000-0000-0000-0000-000000000001';

  IF graph_edge_count <> 1 THEN
    RAISE EXCEPTION 'expected evidence-backed official edge, got %', graph_edge_count;
  END IF;

  SELECT count(*) INTO related_document_count
  FROM civic.related_documents
  WHERE document_id = '62000000-0000-0000-0000-000000000001'
    AND related_document_id = '62000000-0000-0000-0000-000000000002'
    AND shared_node_type = 'topic';

  IF related_document_count <> 1 THEN
    RAISE EXCEPTION 'expected one topic-based related document, got %', related_document_count;
  END IF;
END;
$$;

ROLLBACK;
