BEGIN;

DROP VIEW IF EXISTS civic.related_documents;
DROP VIEW IF EXISTS civic.knowledge_graph_relationships;
DROP TRIGGER IF EXISTS knowledge_graph_edges_validate_nodes ON civic.knowledge_graph_edges;
DROP FUNCTION IF EXISTS civic.validate_knowledge_graph_edge();
DROP FUNCTION IF EXISTS civic.knowledge_graph_node_exists(uuid, text, uuid);
DROP TABLE IF EXISTS civic.knowledge_graph_edges;
DROP TABLE IF EXISTS civic.document_location_mentions;
ALTER TABLE civic.projects DROP CONSTRAINT IF EXISTS projects_location_same_organization;
ALTER TABLE civic.projects DROP COLUMN IF EXISTS location_id;
ALTER TABLE civic.meetings DROP CONSTRAINT IF EXISTS meetings_location_same_organization;
ALTER TABLE civic.meetings DROP COLUMN IF EXISTS location_id;
DROP TABLE IF EXISTS civic.officials;
DROP TABLE IF EXISTS civic.locations;

COMMIT;
