BEGIN;

DROP FUNCTION IF EXISTS civic.claim_vector_index_jobs(integer);
DROP TRIGGER IF EXISTS topic_assignments_enqueue_vector_reindex ON civic.topic_assignments;
DROP TRIGGER IF EXISTS documents_enqueue_vector_reindex ON civic.documents;
DROP FUNCTION IF EXISTS civic.enqueue_document_vector_reindex();
DROP TRIGGER IF EXISTS document_versions_enqueue_vector_index_job ON civic.document_versions;
DROP FUNCTION IF EXISTS civic.enqueue_vector_index_job();
DROP TABLE IF EXISTS civic.vector_index_jobs;
DROP INDEX IF EXISTS civic.document_versions_search_vector_idx;
DROP INDEX IF EXISTS civic.documents_search_vector_idx;
ALTER TABLE civic.document_versions DROP COLUMN IF EXISTS search_vector;
ALTER TABLE civic.documents DROP COLUMN IF EXISTS search_vector;

COMMIT;
