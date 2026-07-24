BEGIN;

SELECT set_config('app.organization_id', '17000000-0000-0000-0000-000000000001', true);
SELECT set_config('app.user_id', '27000000-0000-0000-0000-000000000001', true);

INSERT INTO core.users (id, external_subject, email, display_name)
VALUES (
  '27000000-0000-0000-0000-000000000001',
  'oidc-admin',
  'admin@example.test',
  'Tenant Admin'
);

INSERT INTO core.organizations (id, slug, name, organization_type)
VALUES (
  '17000000-0000-0000-0000-000000000001',
  'authentication-tenant',
  'Authentication Tenant',
  'county'
);

INSERT INTO core.organization_memberships (organization_id, user_id, role_key)
VALUES (
  '17000000-0000-0000-0000-000000000001',
  '27000000-0000-0000-0000-000000000001',
  'tenant_admin'
);

DO $$
DECLARE
  resolved_user_id uuid;
  user_count integer;
BEGIN
  SELECT user_id INTO resolved_user_id
  FROM core.resolve_authenticated_principal(
    'oidc-admin',
    '17000000-0000-0000-0000-000000000001'
  );
  IF resolved_user_id <> '27000000-0000-0000-0000-000000000001' THEN
    RAISE EXCEPTION 'OIDC principal did not resolve to the active tenant administrator';
  END IF;

  PERFORM core.provision_organization_user(
    'oidc-researcher',
    'researcher@example.test',
    'Civic Researcher',
    'researcher'
  );

  SELECT count(*) INTO user_count FROM core.list_organization_users();
  IF user_count <> 2 THEN
    RAISE EXCEPTION 'expected two tenant users, got %', user_count;
  END IF;

  BEGIN
    PERFORM core.update_organization_user(
      '27000000-0000-0000-0000-000000000001',
      'tenant_admin',
      false
    );
    RAISE EXCEPTION 'expected final tenant administrator deactivation to fail';
  EXCEPTION
    WHEN check_violation THEN NULL;
  END;
END;
$$;

ROLLBACK;
