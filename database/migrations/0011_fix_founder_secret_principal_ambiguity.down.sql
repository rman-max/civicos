BEGIN;

-- The previous function body is intentionally not restored: it contains the
-- ambiguity this migration corrects. Dropping the temporary founder-secret
-- function is the safe rollback for a deployment that cannot use this mode.
DROP FUNCTION IF EXISTS core.ensure_founder_secret_principal(citext, text, text, citext, text);

COMMIT;
