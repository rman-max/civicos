BEGIN;

DO $$
DECLARE
  first_user_id uuid;
  first_organization_id uuid;
  second_user_id uuid;
  second_organization_id uuid;
BEGIN
  SELECT principal.user_id, principal.organization_id
  INTO first_user_id, first_organization_id
  FROM core.ensure_founder_secret_principal(
    'founder-secret-test',
    'Founder Secret Test',
    'founder-secret-test-subject',
    'founder-secret-test@example.test',
    'Founder Secret Test'
  ) AS principal;

  SELECT principal.user_id, principal.organization_id
  INTO second_user_id, second_organization_id
  FROM core.ensure_founder_secret_principal(
    'founder-secret-test',
    'Founder Secret Test',
    'founder-secret-test-subject',
    'founder-secret-test@example.test',
    'Founder Secret Test'
  ) AS principal;

  IF first_user_id IS NULL OR first_organization_id IS NULL THEN
    RAISE EXCEPTION 'founder-secret principal was not provisioned';
  END IF;
  IF first_user_id <> second_user_id OR first_organization_id <> second_organization_id THEN
    RAISE EXCEPTION 'founder-secret provisioning must be idempotent';
  END IF;
  IF NOT EXISTS (
    SELECT 1
    FROM core.organization_memberships AS membership
    WHERE membership.organization_id = first_organization_id
      AND membership.user_id = first_user_id
      AND membership.role_key = 'tenant_admin'
      AND membership.is_active
  ) THEN
    RAISE EXCEPTION 'founder-secret principal must have an active tenant-admin membership';
  END IF;
END;
$$;

ROLLBACK;
