-- Rollback for 0001_civic_core.up.sql.
-- Destructive: only use in an empty development database or an approved recovery procedure.

BEGIN;

DROP SCHEMA IF EXISTS research CASCADE;
DROP SCHEMA IF EXISTS civic CASCADE;
DROP SCHEMA IF EXISTS core CASCADE;

COMMIT;

