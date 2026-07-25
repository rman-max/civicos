BEGIN;

DROP FUNCTION IF EXISTS core.ensure_founder_secret_principal(citext, text, text, citext, text);

COMMIT;
