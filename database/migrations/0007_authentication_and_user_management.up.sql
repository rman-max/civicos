BEGIN;

ALTER TABLE core.organization_memberships
  ADD COLUMN is_active boolean NOT NULL DEFAULT true;

CREATE INDEX organization_memberships_active_user_idx
  ON core.organization_memberships (organization_id, user_id)
  WHERE is_active;

CREATE FUNCTION core.resolve_authenticated_principal(
  authenticated_subject text,
  requested_organization_id uuid
)
RETURNS TABLE (user_id uuid, organization_id uuid, role_key text)
LANGUAGE sql
SECURITY DEFINER
SET search_path = pg_catalog, core
AS $$
  SELECT member.id, membership.organization_id, membership.role_key
  FROM core.users AS member
  JOIN core.organization_memberships AS membership
    ON membership.user_id = member.id
  WHERE member.external_subject = authenticated_subject
    AND member.is_active
    AND membership.is_active
    AND membership.organization_id = requested_organization_id;
$$;

CREATE FUNCTION core.require_current_organization_admin()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, core
AS $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM core.organization_memberships AS membership
    JOIN core.users AS member ON member.id = membership.user_id
    WHERE membership.organization_id = core.current_organization_id()
      AND membership.user_id = core.current_user_id()
      AND membership.role_key = 'tenant_admin'
      AND membership.is_active
      AND member.is_active
  ) THEN
    RAISE EXCEPTION 'Tenant administrator role is required' USING ERRCODE = '42501';
  END IF;
END;
$$;

CREATE FUNCTION core.list_organization_users()
RETURNS TABLE (
  user_id uuid,
  external_subject text,
  email citext,
  display_name text,
  role_key text,
  is_active boolean,
  created_at timestamptz,
  updated_at timestamptz
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, core
AS $$
BEGIN
  PERFORM core.require_current_organization_admin();
  RETURN QUERY
  SELECT member.id, member.external_subject, member.email, member.display_name,
    membership.role_key, membership.is_active, membership.created_at, membership.updated_at
  FROM core.organization_memberships AS membership
  JOIN core.users AS member ON member.id = membership.user_id
  WHERE membership.organization_id = core.current_organization_id()
  ORDER BY member.display_name, member.id;
END;
$$;

CREATE FUNCTION core.provision_organization_user(
  new_external_subject text,
  new_email citext,
  new_display_name text,
  new_role_key text
)
RETURNS TABLE (
  user_id uuid,
  external_subject text,
  email citext,
  display_name text,
  role_key text,
  is_active boolean,
  created_at timestamptz,
  updated_at timestamptz
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, core
AS $$
DECLARE
  target_user_id uuid;
BEGIN
  PERFORM core.require_current_organization_admin();

  INSERT INTO core.users (external_subject, email, display_name)
  VALUES (new_external_subject, new_email, new_display_name)
  ON CONFLICT (external_subject) DO NOTHING;

  SELECT member.id INTO target_user_id
  FROM core.users AS member
  WHERE member.external_subject = new_external_subject;

  IF target_user_id IS NULL THEN
    RAISE EXCEPTION 'Could not resolve provisioned user';
  END IF;

  IF EXISTS (
    SELECT 1
    FROM core.users AS member
    WHERE member.id = target_user_id
      AND (member.email <> new_email OR member.display_name <> new_display_name)
  ) THEN
    RAISE EXCEPTION 'Existing user identity attributes do not match the requested values'
      USING ERRCODE = '23505';
  END IF;

  INSERT INTO core.organization_memberships (organization_id, user_id, role_key, is_active)
  VALUES (core.current_organization_id(), target_user_id, new_role_key, true)
  ON CONFLICT (organization_id, user_id)
  DO UPDATE SET role_key = EXCLUDED.role_key, is_active = true;

  RETURN QUERY
  SELECT member.id, member.external_subject, member.email, member.display_name,
    membership.role_key, membership.is_active, membership.created_at, membership.updated_at
  FROM core.users AS member
  JOIN core.organization_memberships AS membership ON membership.user_id = member.id
  WHERE member.id = target_user_id
    AND membership.organization_id = core.current_organization_id();
END;
$$;

CREATE FUNCTION core.update_organization_user(
  target_user_id uuid,
  target_role_key text,
  target_is_active boolean
)
RETURNS TABLE (
  user_id uuid,
  external_subject text,
  email citext,
  display_name text,
  role_key text,
  is_active boolean,
  created_at timestamptz,
  updated_at timestamptz
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, core
AS $$
BEGIN
  PERFORM core.require_current_organization_admin();

  IF NOT target_is_active AND EXISTS (
    SELECT 1
    FROM core.organization_memberships AS membership
    WHERE membership.organization_id = core.current_organization_id()
      AND membership.user_id = target_user_id
      AND membership.role_key = 'tenant_admin'
      AND membership.is_active
  ) AND NOT EXISTS (
    SELECT 1
    FROM core.organization_memberships AS membership
    WHERE membership.organization_id = core.current_organization_id()
      AND membership.user_id <> target_user_id
      AND membership.role_key = 'tenant_admin'
      AND membership.is_active
  ) THEN
    RAISE EXCEPTION 'Cannot deactivate the final tenant administrator' USING ERRCODE = '23514';
  END IF;

  UPDATE core.organization_memberships
  SET role_key = target_role_key, is_active = target_is_active
  WHERE organization_id = core.current_organization_id()
    AND user_id = target_user_id;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'Organization user was not found' USING ERRCODE = 'P0002';
  END IF;

  RETURN QUERY
  SELECT member.id, member.external_subject, member.email, member.display_name,
    membership.role_key, membership.is_active, membership.created_at, membership.updated_at
  FROM core.users AS member
  JOIN core.organization_memberships AS membership ON membership.user_id = member.id
  WHERE member.id = target_user_id
    AND membership.organization_id = core.current_organization_id();
END;
$$;

REVOKE ALL ON FUNCTION core.resolve_authenticated_principal(text, uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION core.require_current_organization_admin() FROM PUBLIC;
REVOKE ALL ON FUNCTION core.list_organization_users() FROM PUBLIC;
REVOKE ALL ON FUNCTION core.provision_organization_user(text, citext, text, text) FROM PUBLIC;
REVOKE ALL ON FUNCTION core.update_organization_user(uuid, text, boolean) FROM PUBLIC;

COMMENT ON FUNCTION core.resolve_authenticated_principal(text, uuid)
  IS 'Resolves a verified OIDC subject to an active tenant membership.';
COMMENT ON FUNCTION core.provision_organization_user(text, citext, text, text)
  IS 'Tenant-admin-only membership provisioning; external identity remains owned by the IdP.';

COMMIT;
