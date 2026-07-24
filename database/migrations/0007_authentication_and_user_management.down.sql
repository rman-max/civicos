BEGIN;

DROP FUNCTION IF EXISTS core.update_organization_user(uuid, text, boolean);
DROP FUNCTION IF EXISTS core.provision_organization_user(text, citext, text, text);
DROP FUNCTION IF EXISTS core.list_organization_users();
DROP FUNCTION IF EXISTS core.require_current_organization_admin();
DROP FUNCTION IF EXISTS core.resolve_authenticated_principal(text, uuid);
DROP INDEX IF EXISTS core.organization_memberships_active_user_idx;
ALTER TABLE core.organization_memberships DROP COLUMN IF EXISTS is_active;

COMMIT;
