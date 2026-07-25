-- Resolve and provision the temporary founder-only identity without requiring a
-- client-supplied tenant scope before authentication has completed.

BEGIN;

CREATE FUNCTION core.ensure_founder_secret_principal(
  founder_organization_slug citext,
  founder_organization_name text,
  founder_external_subject text,
  founder_email citext,
  founder_display_name text
)
RETURNS TABLE (user_id uuid, organization_id uuid, role_key text)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, core
AS $$
DECLARE
  resolved_organization_id uuid;
  resolved_user_id uuid;
BEGIN
  IF length(trim(founder_organization_slug::text)) = 0
    OR length(trim(founder_organization_name)) = 0
    OR length(trim(founder_external_subject)) = 0
    OR length(trim(founder_email::text)) = 0
    OR length(trim(founder_display_name)) = 0 THEN
    RAISE EXCEPTION 'Founder identity attributes must not be empty' USING ERRCODE = '22023';
  END IF;

  INSERT INTO core.organizations (slug, name, organization_type, settings)
  VALUES (
    founder_organization_slug,
    founder_organization_name,
    'county',
    '{"country_code": "US", "state_code": "IN"}'::jsonb
  )
  ON CONFLICT (slug) DO NOTHING;

  SELECT organization.id INTO resolved_organization_id
  FROM core.organizations AS organization
  WHERE organization.slug = founder_organization_slug
    AND organization.name = founder_organization_name
    AND organization.is_active;
  IF resolved_organization_id IS NULL THEN
    RAISE EXCEPTION 'Configured founder organization is missing, inactive, or does not match'
      USING ERRCODE = '23505';
  END IF;

  INSERT INTO core.users (external_subject, email, display_name)
  VALUES (founder_external_subject, founder_email, founder_display_name)
  ON CONFLICT (external_subject) DO NOTHING;

  SELECT member.id INTO resolved_user_id
  FROM core.users AS member
  WHERE member.external_subject = founder_external_subject
    AND member.email = founder_email
    AND member.display_name = founder_display_name
    AND member.is_active;
  IF resolved_user_id IS NULL THEN
    RAISE EXCEPTION 'Configured founder user is missing, inactive, or does not match'
      USING ERRCODE = '23505';
  END IF;

  INSERT INTO core.organization_memberships (organization_id, user_id, role_key, is_active)
  VALUES (resolved_organization_id, resolved_user_id, 'tenant_admin', true)
  ON CONFLICT (organization_id, user_id)
  DO UPDATE SET role_key = 'tenant_admin', is_active = true;

  RETURN QUERY
  SELECT resolved_user_id, resolved_organization_id, 'tenant_admin'::text;
END;
$$;

REVOKE ALL ON FUNCTION core.ensure_founder_secret_principal(citext, text, text, citext, text)
  FROM PUBLIC;

COMMENT ON FUNCTION core.ensure_founder_secret_principal(citext, text, text, citext, text)
  IS 'Provision and resolve the one temporary founder-secret identity after secret verification.';

COMMIT;
