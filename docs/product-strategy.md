# CivicOS Product Strategy

**Status:** Proposed  
**Initial market:** St. Joseph County, Indiana  
**Product type:** Open-source, evidence-first civic intelligence platform

## Product vision

CivicOS helps people understand what their local government is doing without requiring them to know which office published a document, where a meeting agenda lives, or how to interpret fragmented public records.

It continuously organizes official civic information into a searchable public record. A user can discover a decision, understand its context, follow its status over time, and inspect the original evidence. CivicOS does not replace the government’s record system or present itself as legally authoritative; it makes official information easier to find, compare, and understand.

### Product promise

For any answer CivicOS presents, a user can see:

- what it is based on;
- where the source came from;
- when the source was published or retrieved; and
- when the evidence is insufficient to support an answer.

### Strategic principles

1. **Trust before convenience.** Citations, dates, source status, and limitations are product requirements—not secondary metadata.
2. **Public value before engagement.** Prioritize finding and understanding civic records over addictive feeds, opaque rankings, or advertising-driven attention.
3. **One platform, local relevance.** A common platform must still preserve local government structure, terminology, geography, and source authority.
4. **Automation with accountable boundaries.** Automate recurring discovery and updates; retain visible policy, provenance, and exception handling.
5. **Open core and portable deployment.** Government and civic organizations should be able to inspect, self-host, and extend the system.

## Target users and personas

| Persona | Primary need | Current friction | CivicOS value |
|---|---|---|---|
| Citizen | Understand a local issue, meeting, service, or public decision | records are distributed across unfamiliar sites and formats | plain-language, cited answers; chronological context; direct source links |
| Journalist | Find timely, defensible leads and supporting records | manual monitoring and document search consume reporting time | change detection, source-traceable search, alerts, and exportable citations |
| Government employee | Publish information that residents can actually find; answer repeat questions | fragmented publishing tools and high public-record navigation burden | source-health visibility, searchable public archive, governed correction workflow |
| Nonprofit staff | Track policy, budgets, and public programs affecting a community | limited staff cannot follow every board and agency | topic/body alerts, evidence bundles, accessible historical context |
| Researcher | Build reproducible analysis of local civic activity | inconsistent formats, broken links, and unclear provenance | versioned source data, documented scope, stable evidence references, export paths |

## User journeys

### Citizen: understand a proposed local decision

1. A resident asks, “What is changing with the county’s proposed transit plan?”
2. CivicOS identifies the selected jurisdiction and retrieves current, relevant official sources.
3. The resident receives a concise summary with cited agenda items, plans, notices, and dates.
4. They open a cited record to review the original page/PDF section and related meeting timeline.
5. If the evidence is incomplete, CivicOS says so and offers the closest official records rather than speculating.

**Success moment:** the resident can explain what is proposed, by whom, and what happens next with source links they can verify.

### Journalist: monitor public action

1. A reporter follows county commissioners, planning, procurement, and a set of civic topics.
2. CivicOS detects a newly published agenda, contract, notice, or change to a source document.
3. The reporter receives a concise alert containing what changed, source links, and related prior records.
4. They search the historical record, inspect citations, and export an evidence bundle for reporting.
5. The reporter independently confirms information before publication.

**Success moment:** a trustworthy lead reaches the reporter before a routine manual sweep would have found it.

### Government employee: improve public discoverability

1. A communications or records employee connects approved official sources to the jurisdiction profile.
2. CivicOS monitors those sources and displays source health, freshness, and parsing exceptions.
3. A resident searches CivicOS and reaches the employee’s official source with context.
4. When a correction is needed, the employee follows a recorded correction/takedown workflow; the original provenance remains auditable.

**Success moment:** fewer navigation-only inquiries and fewer residents relying on unofficial summaries.

### Nonprofit: prepare for an advocacy or service decision

1. A nonprofit worker follows housing, public health, and transportation topics across multiple bodies.
2. CivicOS presents a timeline of upcoming meetings, recent notices, and relevant decisions.
3. The worker shares verified evidence with colleagues or community members.
4. They subscribe to future changes instead of repeatedly checking numerous government sites.

**Success moment:** a small team can participate in a civic process with the same factual footing as a well-resourced organization.

### Researcher: construct a reproducible civic dataset

1. A researcher filters records by government body, record type, time range, and geography.
2. They inspect source provenance, version timestamps, and extraction confidence.
3. They export permitted metadata/evidence references and document the query scope.
4. A later researcher can reproduce the result against the preserved source version or identify a superseding version.

**Success moment:** the research can be audited without treating an AI-generated narrative as data.

## Feature roadmap

The roadmap follows evidence and operational reliability before broad AI capability. Dates are intentionally not assigned until hosting, source scope, and staffing decisions are approved.

| Horizon | Product capability | User value | Dependencies |
|---|---|---|---|
| Foundation | jurisdiction profile, source registry, provenance, source health, secure operator access | trustworthy corpus and governed operations | approved source inventory and policy owner |
| MVP | public search, document/meeting timeline, cited answer experience, current-source links, no-answer behavior | citizens and journalists can find and verify local information | P0 St. Joseph County source connectors and evaluation set |
| Post-MVP 1 | subscriptions/alerts, saved topics, change summaries, evidence bundles, public feedback/correction path | repeat monitoring for journalists, nonprofits, and government staff | reliable change detection and notification policy |
| Post-MVP 2 | structured civic records for agendas, meetings, notices, budgets, contracts, and policies | comparison and analysis across sources | taxonomy, entity resolution, quality-review workflow |
| Expansion | self-service jurisdiction onboarding, connector SDK, role-based operator workspace, data exports | repeatable multi-county adoption | tenant isolation and onboarding runbook |
| Network | cross-jurisdiction comparison, regional/state context, partner ecosystem | researchers and regional organizations can study patterns responsibly | standardized taxonomy, normalization, consent/data-governance framework |

### Public beta showcase

The public beta is a bounded municipal evaluation experience: a landing page, guided illustrative demo, example research notebooks, voluntary feedback, and anonymous first-party aggregate analytics. It is not a claim of live source completeness or an official record portal. See `public-beta.md` for launch scope, privacy boundaries, and the municipal showcase script.

### Features explicitly deferred from the MVP

- Automated government action, filing, lobbying, or communications.
- Predictive scoring of officials, agencies, communities, or policy outcomes.
- Social feeds, comments, or unmoderated user-generated content.
- Cross-county comparisons before data coverage and taxonomy are demonstrably comparable.
- Paid features that hide primary civic records or citations from the public.

## MVP definition

The MVP is a public, read-only St. Joseph County civic intelligence experience supported by an operator workflow—not a complete county data warehouse.

### In scope

- A curated P0 inventory of approved official sources: county/board meetings, notices/public records, and selected financial sources.
- Automated polling, immutable source versioning, extraction, classification, and searchable indexing for that inventory.
- Public keyword and semantic search constrained to the St. Joseph County jurisdiction.
- A simple, notebook-inspired interface that displays source title, publisher/body, publication/retrieval dates, direct links, and relevant excerpts.
- Cited summaries for questions where evidence passes validation; a transparent no-answer state otherwise.
- An operator console or operational interface for source health, failures, approved sources, and correction/exceptions.
- Baseline accessibility, security, source provenance, audit logs, backup/restore validation, and documentation.

### MVP acceptance criteria

1. Every searchable public result resolves to one or more approved official source versions.
2. Every generated answer has valid citations, or the interface explicitly refuses to synthesize an unsupported answer.
3. A source update produces a new version without overwriting the earlier version.
4. The P0 source inventory meets an agreed freshness target and displays stale status when it cannot.
5. A trained municipal operator can resolve routine source failures using documented runbooks without founder intervention.
6. Evaluation questions from all target user groups meet agreed retrieval, citation-correctness, and accessibility thresholds.

## Success metrics

Metrics are instruments for public value and system trust. They should be segmented by jurisdiction, source type, and user role; they must not expose individual search histories or personal data.

| Dimension | Metric | MVP target-setting approach |
|---|---|---|
| Coverage | percentage of approved P0 sources healthy and indexed | agree source inventory and freshness SLO per source class before launch |
| Freshness | age of last successful observation and of latest searchable version | measure against declared source cadence, not a universal timer |
| Retrieval quality | evidence recall@k on a human-curated evaluation set | establish baseline, then set a release threshold per record type |
| Answer trust | citation precision; supported-claim rate; unsupported-answer rate | require near-zero unsupported public claims; evaluate continuously |
| Transparency | percentage of result views with accessible source/provenance links | target complete coverage for public results |
| User effectiveness | task completion rate and time-to-verified-source by persona | compare moderated usability tests against existing public-site workflows |
| Operational autonomy | routine exceptions resolved without founder involvement; mean time to recover source failures | define monthly operational-review target after pilot |
| Equity/accessibility | keyboard task completion, screen-reader testing, mobile usability, language coverage readiness | make WCAG conformance testing a release gate |
| Adoption | returning users, saved searches/alerts, partner usage | use aggregate, privacy-preserving measurement; never optimize for time-on-site alone |

### North-star measure

**Verified civic understanding:** the proportion of tested users who can correctly answer a local civic question and open the supporting official source after using CivicOS. This is measured through consented usability research, not inferred from clicks alone.

## Monetization model

CivicOS should preserve free public access to primary-source discovery, citations, and basic search. Revenue should pay for reliable operation and expansion without creating a paywall around civic facts.

### Recommended model: open-source public core + hosted operations

| Offering | Buyer | Includes | Guardrail |
|---|---|---|---|
| Self-hosted open-source core | governments, universities, civic technologists | source code, deployment docs, core public search/citation capabilities | use an OSI-approved license; do not restrict public record access |
| Managed CivicOS | counties, municipalities, regional consortia | hosting, updates, backups, source monitoring, security operations, support | pricing is based on operational scope, not residents’ access to records |
| Implementation services | government/consortium partners | source inventory, connector configuration, migration, training, accessibility review | fixed, transparent statement of work; no proprietary lock-in |
| Research and nonprofit plans | universities, newsrooms, nonprofits | managed workspace, permitted exports, support, multi-jurisdiction analysis | discounted or grant-supported; no reduced evidence quality |
| Ecosystem support | foundations and civic funders | sponsored jurisdictions, public-interest connectors, independent evaluations | sponsors have no control over source rankings or conclusions |

### Pricing principles

- Price hosted service by source count/complexity, storage, ingestion volume, support tier, and optional GPU capacity—not by opaque AI queries alone.
- Publish an implementation checklist so buyers can compare managed hosting with self-hosting fairly.
- Keep export formats, source provenance, and tenant data portable; provide documented offboarding and data-return procedures.
- Do not sell personal data, individual search behavior, or preferential public-result placement.

## Multi-county expansion strategy

Expansion is a product and governance discipline, not merely a database-tenant operation. Each county must receive a separate jurisdiction configuration, source policy, data-quality baseline, and accountable local owner.

### Expansion sequence

1. **Prove the St. Joseph County operating model.** Establish P0 coverage, operator runbooks, source-health SLOs, citation evaluation, and a correction process.
2. **Choose a comparable pilot county.** Prefer a nearby or similarly structured Indiana county with willing records/communications partners and a manageable source inventory.
3. **Make onboarding repeatable.** Deliver a source-policy worksheet, jurisdiction configuration package, adapter test fixtures, evaluation corpus, and operator training.
4. **Expand by source patterns, not one-off scraping.** Turn repeated official platforms (agenda systems, CMSs, open-data portals) into configured adapters with contract tests.
5. **Build an Indiana network.** Add state-context sources once, while preserving county-level tenant isolation and local ownership.
6. **Expand across states only after governance generalization.** Add state-specific public-records, retention, procurement, accessibility, and election/meeting practices as explicit policy modules.

### County onboarding criteria

- An accountable source-policy owner and operator team are named.
- Official domains, systems, terms, contact paths, and rate limits are inventoried.
- Data classification, redaction, correction, and retention policies are approved.
- The source inventory has a measurable coverage plan and an evaluation set representing local user questions.
- Hosting, identity, support, and funding commitments are in place for at least the pilot period.

### Scaling guardrails

- Enforce row-level tenant isolation and test it before activating any new jurisdiction.
- Do not compare jurisdictions as though their data were equivalent until coverage, time range, definitions, and source reliability are disclosed.
- Preserve local labels and governance bodies; map to a shared taxonomy without erasing local meaning.
- Never auto-enable cross-county data sharing or external-model egress solely because a new tenant is added.
- Treat connector health and public-record provenance as release-blocking, not operational afterthoughts.

## Key risks and product responses

| Risk | Response |
|---|---|
| Incomplete or changing public sources | display coverage/freshness, retain provenance, use exception queues, and never imply completeness |
| AI-generated misinformation | evidence-required answers, claim/citation validation, no-answer fallback, ongoing evaluation |
| Uneven county capability | tiered onboarding, reusable adapters, shared managed operations, transparent coverage indicators |
| Public-data privacy concerns | data classification, redaction policy, correction workflow, restricted processing routes |
| Vendor or funding dependency | open-source core, portable deployment, documented exports, diversified managed/foundation/research revenue |
| Perceived political bias | source-first presentation, transparent scope/methodology, auditable corrections, no opaque ranking of officials or viewpoints |

## Decisions required before product execution

1. Confirm which St. Joseph County source classes constitute the P0 MVP inventory.
2. Name the public-sector or partner role that owns source policy and correction decisions.
3. Approve the initial hosting and local-versus-external model-evaluation policy.
4. Select the business form and open-source license strategy before accepting paid implementation or hosted customers.
5. Define consent and privacy rules for user feedback, analytics, and journalist/nonprofit alert subscriptions.
