# Production operations

## Deployment boundary

Deploy PostgreSQL, S3-compatible storage, Qdrant, and an OIDC provider as independently managed services. Docker Compose is a local/initial topology, not a production orchestrator or secret store. Terminate TLS and enforce network policy at ingress; only the frontend and selected API routes should be internet-facing.

Production requires `CIVICOS_ENVIRONMENT=production`, `CIVICOS_AUTH_MODE=oidc`, non-wildcard `CIVICOS_ALLOWED_HOSTS`, explicit CORS origins, and a confidential `CIVICOS_METRICS_TOKEN`. Startup rejects incomplete OIDC or production monitoring configuration.

## Authentication and user management

The API validates RS256 OIDC bearer tokens against the configured issuer, audience, and JWKS. Tokens require `sub`, `exp`, `iat`, and a UUID tenant claim named by `CIVICOS_AUTH_ORGANIZATION_CLAIM` (default `organization_id`). The token subject must also resolve to an active CivicOS user and active PostgreSQL membership for that tenant.

The API strips client-provided tenant/user headers and internally replaces them with the verified identity. `tenant_admin` users manage existing IdP identities through `/v1/users`, assigning `tenant_admin`, `researcher`, or `government_staff` roles and deactivating tenant memberships. CivicOS never stores passwords or creates IdP accounts. Keep at least two active administrators; the database rejects removal of the final administrator.

The migration provisioner must own the security-definer functions and have `BYPASSRLS`. Grant the API role only required function execution rights and normal tenant-table permissions; never grant it `BYPASSRLS`.

```sql
GRANT EXECUTE ON FUNCTION core.resolve_authenticated_principal(text, uuid) TO civicos_api;
GRANT EXECUTE ON FUNCTION core.list_organization_users() TO civicos_api;
GRANT EXECUTE ON FUNCTION core.provision_organization_user(text, citext, text, text) TO civicos_api;
GRANT EXECUTE ON FUNCTION core.update_organization_user(uuid, text, boolean) TO civicos_api;
```

The frontend currently uses mock data. Connect an approved OIDC authorization-code-with-PKCE client only after callback URLs, session storage, and renewal behavior are reviewed. Do not expose client secrets or database credentials in `NEXT_PUBLIC_*` variables.

## Deployment procedure

1. Build immutable frontend, API, and ingestion images in CI; scan and sign them in the registry.
2. Put database, OIDC, metrics, and object-storage settings in the deployment secret manager.
3. Apply migrations `0001`–`0008` with `psql -v ON_ERROR_STOP=1`; apply the St. Joseph County seed with the provisioner account.
4. Deploy at least two API replicas behind TLS ingress. Restrict `/readyz` to the platform health checker.
5. Expose `/metrics` only to the monitoring network with `Authorization: Bearer $CIVICOS_METRICS_TOKEN`.
6. Start discovery only after scoped database and object-storage permissions are verified; review its initial source-health results before public launch.
7. Test OIDC login, tenant isolation, ingestion, backup restore, and rollback in staging before promotion.

## Monitoring, logging, and error handling

The API writes JSON logs containing request ID, method, route, status, and latency. It does not log authorization tokens, request bodies, or database URLs. Centralize logs with restricted access and a defined retention policy.

`/metrics` exposes request counts and recent latency summaries. Alert on sustained 5xx responses, readiness failures, high 429 rates, latency regressions, discovery backlog, failed scans, object-store errors, and backup failures. `/healthz` is liveness; `/readyz` verifies PostgreSQL connectivity.

Unhandled errors produce generic problem responses with a request ID, not stack traces or SQL errors. The in-process rate limit is burst protection only; enforce a distributed rate and body-size limit at ingress for every public replica.

## Security and performance controls

- Use TLS 1.2+ everywhere; keep PostgreSQL, Qdrant, and object storage on private networks.
- Pin images by digest, run non-root read-only containers, set CPU/memory limits, and patch base images regularly.
- Supply exact allowed hosts and CORS origins. The API sends HSTS in production, no-sniff, frame, referrer, permissions-policy, CSP, and no-store headers.
- Rotate IdP, database, storage, and metrics credentials through the secret manager. Disable a CivicOS membership and revoke the IdP session when an identity is compromised.
- Use managed PostgreSQL connection pooling, bounded API workers, and horizontal API replicas. Gzip and bounded query limits are enabled; review query plans before raising search limits.
- Track database connection use, slow queries, cache hit ratio, storage, vector-index lag, queue age, and object-store throughput. Scale ingestion independently.

## Backups and recovery

PostgreSQL is authoritative. Take encrypted off-site logical backups daily and maintain point-in-time recovery/WAL archives for the required recovery-point objective. Enable object-store versioning and lifecycle policy for raw artifacts. Qdrant can be rebuilt from PostgreSQL and artifacts, though periodic snapshots reduce recovery time.

`infrastructure/scripts/backup-postgres.sh` writes a PostgreSQL custom-format dump, verifies the archive index, and writes a SHA-256 manifest. Run it from a restricted backup job with `DATABASE_URL` and `BACKUP_DIRECTORY`; replicate the output to immutable encrypted storage. It never deletes backups.

Quarterly, restore the newest backup into an isolated database and verify tenant RLS plus source/document/version counts. This command overwrites the target database, so run it only against an explicitly designated recovery target:

```sh
pg_restore --clean --if-exists --no-owner --dbname="$RECOVERY_DATABASE_URL" \
  /secure-backups/civicos-postgres-YYYYMMDDTHHMMSSZ.dump
```
