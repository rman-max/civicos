BEGIN;

DROP TRIGGER IF EXISTS saved_searches_set_updated_at ON research.saved_searches;
DROP TABLE IF EXISTS research.notebook_documents;
DROP TABLE IF EXISTS research.saved_searches;

COMMIT;
