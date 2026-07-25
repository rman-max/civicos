-- Initial, administrator-approved public sources for St. Joseph County, Indiana.
--
-- Prerequisites: migrations 0001 through 0006 and a privileged provisioning
-- role. This is intentionally an idempotent, non-destructive configuration seed.

BEGIN;

INSERT INTO core.organizations (slug, name, organization_type, settings)
VALUES (
  'st-joseph-county-indiana',
  'St. Joseph County, Indiana',
  'county',
  '{"default_timezone": "America/Indiana/Indianapolis", "country_code": "US", "state_code": "IN"}'::jsonb
)
ON CONFLICT (slug) DO NOTHING;

SELECT set_config(
  'app.organization_id',
  (SELECT id::text FROM core.organizations WHERE slug = 'st-joseph-county-indiana'),
  true
);

WITH organization AS (
  SELECT id FROM core.organizations WHERE slug = 'st-joseph-county-indiana'
), municipality_definitions (slug, name, municipality_type, jurisdiction_code, geography) AS (
  VALUES
    ('st-joseph-county', 'St. Joseph County', 'county', 'US-IN-18141',
      '{"country_code": "US", "state_code": "IN", "county_fips": "18141"}'::jsonb),
    ('south-bend', 'South Bend', 'city', NULL,
      '{"country_code": "US", "state_code": "IN"}'::jsonb),
    ('mishawaka', 'Mishawaka', 'city', NULL,
      '{"country_code": "US", "state_code": "IN"}'::jsonb)
)
INSERT INTO core.municipalities (
  organization_id, slug, name, municipality_type, jurisdiction_code, geography
)
SELECT organization.id, definition.slug, definition.name, definition.municipality_type,
  definition.jurisdiction_code, definition.geography
FROM organization
CROSS JOIN municipality_definitions AS definition
ON CONFLICT (organization_id, slug) DO NOTHING;

WITH organization AS (
  SELECT id FROM core.organizations WHERE slug = 'st-joseph-county-indiana'
), department_definitions (municipality_slug, name, department_type) AS (
  VALUES
    ('st-joseph-county', 'County Government', 'county_government'),
    ('st-joseph-county', 'Public Meetings', 'public_records'),
    ('st-joseph-county', 'County Council', 'legislative_body'),
    ('st-joseph-county', 'Board of Commissioners', 'executive_body'),
    ('st-joseph-county', 'Area Plan Commission', 'planning'),
    ('st-joseph-county', 'Assessor', 'assessor'),
    ('st-joseph-county', 'Recorder', 'recorder'),
    ('st-joseph-county', 'Health Department', 'public_health'),
    ('st-joseph-county', 'Election Board', 'elections'),
    ('south-bend', 'City of South Bend', 'municipal_government'),
    ('mishawaka', 'City of Mishawaka', 'municipal_government')
)
INSERT INTO core.departments (organization_id, municipality_id, name, department_type)
SELECT organization.id, municipality.id, definition.name, definition.department_type
FROM organization
JOIN department_definitions AS definition ON true
JOIN core.municipalities AS municipality
  ON municipality.organization_id = organization.id
  AND municipality.slug = definition.municipality_slug
ON CONFLICT (organization_id, municipality_id, name) DO NOTHING;

WITH organization AS (
  SELECT id FROM core.organizations WHERE slug = 'st-joseph-county-indiana'
), connector_definitions (
  municipality_slug,
  department_name,
  name,
  canonical_url,
  acquisition_policy,
  scan_interval_seconds,
  max_pages_per_scan,
  request_timeout_seconds
) AS (
  VALUES
    (
      'st-joseph-county', 'County Government', 'St. Joseph County Government',
      'https://www.sjcindiana.gov/',
      '{"respect_robots": true, "allowed_path_prefixes": ["/"], "max_content_bytes": 12000000}'::jsonb,
      10800, 40, 20
    ),
    (
      'st-joseph-county', 'Public Meetings', 'St. Joseph County Public Meetings',
      'https://www.sjcindiana.gov/AgendaCenter',
      '{"respect_robots": true, "allowed_path_prefixes": ["/AgendaCenter", "/Calendar.aspx", "/DocumentCenter"], "max_content_bytes": 12000000}'::jsonb,
      10800, 60, 20
    ),
    (
      'st-joseph-county', 'County Council', 'St. Joseph County Council',
      'https://www.sjcindiana.gov/AgendaCenter/County-Council-4',
      '{"respect_robots": true, "allowed_path_prefixes": ["/AgendaCenter/County-Council-4", "/AgendaCenter/ViewFile", "/DocumentCenter"], "max_content_bytes": 12000000}'::jsonb,
      10800, 30, 20
    ),
    (
      'st-joseph-county', 'Board of Commissioners', 'St. Joseph County Commissioners',
      'https://www.sjcindiana.gov/AgendaCenter/Board-of-Commissioners-5',
      '{"respect_robots": true, "allowed_path_prefixes": ["/AgendaCenter/Board-of-Commissioners-5", "/AgendaCenter/ViewFile", "/DocumentCenter"], "max_content_bytes": 12000000}'::jsonb,
      10800, 30, 20
    ),
    (
      'st-joseph-county', 'Area Plan Commission', 'St. Joseph County Planning Meetings',
      'https://www.sjcindiana.gov/AgendaCenter/Search/?CIDs=10%2C2%2C15%2C&dateRange=&dateSelector=&endDate=&startDate=&term=',
      '{"respect_robots": true, "allowed_path_prefixes": ["/AgendaCenter/Search", "/AgendaCenter/ViewFile", "/DocumentCenter"], "max_content_bytes": 12000000}'::jsonb,
      10800, 35, 20
    ),
    (
      'st-joseph-county', 'Assessor', 'St. Joseph County Assessor Data Information',
      'https://www.sjcindiana.gov/1443/Data-Extract-Search-Information',
      '{"respect_robots": true, "allowed_path_prefixes": ["/1443/Data-Extract-Search-Information", "/DocumentCenter"], "max_content_bytes": 12000000}'::jsonb,
      10800, 20, 20
    ),
    (
      'st-joseph-county', 'Recorder', 'St. Joseph County Recorder eRecordings',
      'https://www.sjcindiana.gov/779/eRecordings',
      '{"respect_robots": true, "allowed_path_prefixes": ["/779/eRecordings", "/DocumentCenter"], "max_content_bytes": 12000000}'::jsonb,
      10800, 20, 20
    ),
    (
      'st-joseph-county', 'Health Department', 'St. Joseph County Health Department Meetings',
      'https://www.in.gov/localhealth/stjosephcounty/meetings-and-agendas/',
      '{"respect_robots": true, "allowed_path_prefixes": ["/localhealth/stjosephcounty", "/localhealth/files"], "max_content_bytes": 12000000}'::jsonb,
      10800, 30, 20
    ),
    (
      'st-joseph-county', 'Election Board', 'St. Joseph County Election Board',
      'https://www.sjcindiana.gov/AgendaCenter/Election-Board-11',
      '{"respect_robots": true, "allowed_path_prefixes": ["/AgendaCenter/Election-Board-11", "/AgendaCenter/ViewFile", "/DocumentCenter"], "max_content_bytes": 12000000}'::jsonb,
      10800, 30, 20
    ),
    (
      'south-bend', 'City of South Bend', 'South Bend News and Public Meetings',
      'https://southbendin.gov/news-and-public-meetings/',
      '{"respect_robots": true, "allowed_path_prefixes": ["/news-and-public-meetings", "/wp-content/uploads"], "max_content_bytes": 12000000}'::jsonb,
      10800, 35, 20
    ),
    (
      'mishawaka', 'City of Mishawaka', 'Mishawaka Agendas and Minutes',
      'https://mishawaka.in.gov/government/agendas-minutes/',
      '{"respect_robots": true, "allowed_path_prefixes": ["/"], "max_content_bytes": 12000000}'::jsonb,
      10800, 35, 20
    )
), resolved_connectors AS (
  SELECT organization.id AS organization_id, municipality.id AS municipality_id,
    department.id AS department_id, connector.name, connector.canonical_url,
    connector.acquisition_policy, connector.scan_interval_seconds,
    connector.max_pages_per_scan, connector.request_timeout_seconds
  FROM organization
  JOIN connector_definitions AS connector ON true
  JOIN core.municipalities AS municipality
    ON municipality.organization_id = organization.id
    AND municipality.slug = connector.municipality_slug
  JOIN core.departments AS department
    ON department.organization_id = organization.id
    AND department.municipality_id = municipality.id
    AND department.name = connector.department_name
)
INSERT INTO civic.sources (
  organization_id,
  municipality_id,
  department_id,
  name,
  source_type,
  canonical_url,
  acquisition_policy,
  licensing_note,
  scan_interval_seconds,
  max_pages_per_scan,
  request_timeout_seconds
)
SELECT organization_id, municipality_id, department_id, name, 'official_website', canonical_url,
  acquisition_policy, 'Public government record; retain source URL and version provenance.',
  scan_interval_seconds, max_pages_per_scan, request_timeout_seconds
FROM resolved_connectors
ON CONFLICT (organization_id, canonical_url) DO NOTHING;

COMMIT;
