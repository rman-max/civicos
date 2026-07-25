# St. Joseph County, Indiana deployment configuration

## Scope

`database/seeds/st_joseph_county_indiana.sql` is CivicOS’s first jurisdiction configuration. It creates one St. Joseph County tenant, three municipalities, eleven department boundaries, and eleven official public-record connectors. It creates no user accounts and exposes no public crawl or upload endpoint.

The seed is idempotent and non-destructive: later runs insert only missing records. Operators retain control of any source they have paused or edited.

## Approved initial connectors

| Coverage | Official entry point | Interval | Page cap | Scope |
|---|---|---:|---:|---|
| County government | [St. Joseph County](https://www.sjcindiana.gov/) | 3 hours | 40 | County site |
| Public meetings | [Agenda Center](https://www.sjcindiana.gov/AgendaCenter) | 3 hours | 60 | Agenda, calendar, and document endpoints |
| County Council | [County Council Agenda Center](https://www.sjcindiana.gov/AgendaCenter/County-Council-4) | 3 hours | 30 | Council agenda and document endpoints |
| Commissioners | [Board of Commissioners Agenda Center](https://www.sjcindiana.gov/AgendaCenter/Board-of-Commissioners-5) | 3 hours | 30 | Commissioners agenda and document endpoints |
| Planning | [Planning meeting search](https://www.sjcindiana.gov/AgendaCenter/Search/?CIDs=10%2C2%2C15%2C&dateRange=&dateSelector=&endDate=&startDate=&term=) | 3 hours | 35 | Planning meeting results and documents |
| Assessor | [Data extract and search information](https://www.sjcindiana.gov/1443/Data-Extract-Search-Information) | 3 hours | 20 | Assessor information and documents |
| Recorder | [eRecordings](https://www.sjcindiana.gov/779/eRecordings) | 3 hours | 20 | Recorder information and documents |
| Health Department | [Meetings and agendas](https://www.in.gov/localhealth/stjosephcounty/meetings-and-agendas/) | 3 hours | 30 | County health path and its document endpoint |
| Elections | [Election Board Agenda Center](https://www.sjcindiana.gov/AgendaCenter/Election-Board-11) | 3 hours | 30 | Election Board agenda and document endpoints |
| South Bend | [News and public meetings](https://southbendin.gov/news-and-public-meetings/) | 3 hours | 35 | Public-meeting page and document uploads |
| Mishawaka | [Agendas and minutes](https://mishawaka.in.gov/government/agendas-minutes/) | 3 hours | 35 | Site, bounded by a page cap |

Each connector follows only its official host, uses HTTPS, honors `robots.txt`, rejects off-domain redirects and credentialed URLs, and has a 12 MB per-response limit. `allowed_path_prefixes` narrows County sources to their pertinent official record areas. The page caps make routine scans predictable even if an upstream site changes its navigation.

The Assessor and Recorder connectors intentionally begin at informational public endpoints. CivicOS does not bypass authentication, terms, rate limits, CAPTCHAs, or record-search interfaces; a later connector can be added only after its public access and collection policy are reviewed.

## Enabling autonomous ingestion

1. Apply migrations through `0008_public_beta_feedback_and_analytics.up.sql`.
2. Use the privileged provisioning role to apply the seed:

   ```sh
   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 \
     -f database/seeds/st_joseph_county_indiana.sql
   ```

3. Configure the artifact bucket and restricted ingestion role required by [autonomous discovery](autonomous-discovery.md).
4. Set the deployment briefing timezone to `America/Indiana/Indianapolis` when this is the only active jurisdiction.
5. Start the worker:

   ```sh
   docker compose --env-file .env -f infrastructure/docker-compose.yml \
     --profile discovery up --build
   ```

Inserting every active `civic.sources` record automatically enqueues a durable `civic.discovery_jobs` record. The worker leases due jobs safely across replicas, observes every successful fetch, creates a new document version only when the content hash changes, and schedules the next run from the source’s configured interval. No founder action is needed after this deployment step.

## First-run operations

Before treating the deployment as live, review its first completed scan run for each connector:

- confirm `robots.txt` access and expected source page counts;
- review source observations and failed jobs for site-specific adjustments;
- confirm that linked PDFs, DOCX files, and CSVs resolve inside the configured scope; and
- adjust a source record through the provisioning workflow rather than changing worker code.

Alert on failed scans, overdue discovery jobs, and unexpected page or document counts. Source availability and public-record policy remain operator responsibilities.
