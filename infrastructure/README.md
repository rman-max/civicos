# Infrastructure boundary

`docker-compose.yml` is the local and initial deployment topology. It starts the web scaffold, API scaffold, PostgreSQL, and Qdrant; the autonomous discovery worker is enabled through the `discovery` profile.

The compose file is not a production secret store. Production deployment must provide secret values through the target environment’s secret mechanism, pin images by digest, and run tested PostgreSQL/object-storage backup procedures.

The API Compose service includes local defaults for the production control configuration, but production must use the OIDC, ingress, monitoring, backup, and recovery process in `../docs/production-operations.md` rather than deploy this file unchanged.
