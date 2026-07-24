# Research notebooks

## Purpose

Research Notebooks provide a durable, evidence-first workspace for civic inquiry. A notebook retains a researcher’s question, saved searches, logical documents, highlighted passages, notes, grounded summaries, timelines, and source references in one exportable record.

## Data model

`research.notebooks` and `research.notebook_entries` hold the notebook and its ordered working record. Migration `0005_research_notebooks.up.sql` adds two explicit relationships:

- `research.saved_searches` stores the search text and structured filter set that produced a line of inquiry.
- `research.notebook_documents` retains a logical civic document, resolving to its newest version for display while all highlights and generated references cite an immutable document version.

Highlights create `civic.citations` with optional source offsets and connect the citation to a notebook entry. Notes, summaries, and timelines are typed notebook entries. Generated summaries and timelines attach source-version citations to their entries before they are exported.

## API

Production research routes require a verified OIDC bearer token. The API resolves the authenticated subject to an active CivicOS membership, injects the trusted organization/user scope, sets both PostgreSQL RLS settings, and only accesses notebooks owned by that user. Browsers cannot choose those identifiers. The named headers remain development-only compatibility scaffolding and are rejected by production configuration.

| Route | Purpose |
|---|---|
| `GET`, `POST /v1/research/notebooks` | List or create a personal notebook. |
| `GET /v1/research/notebooks/{id}` | Read the complete notebook, including source references. |
| `POST .../{id}/saved-searches` | Save a query and its filters. |
| `POST .../{id}/documents` | Save a logical civic document and optional researcher note. |
| `POST .../{id}/notes` | Append a Markdown research note. |
| `POST .../{id}/highlights` | Save a quoted passage with optional offsets and note. |
| `POST .../{id}/summaries` | Produce a citation-bound summary from notebook evidence. |
| `POST .../{id}/timelines` | Create a deterministic timeline from dated notebook evidence. |
| `GET .../{id}/export?format=markdown|json` | Export the notebook with source references. |

## Grounding and export behavior

Notebook summaries use the same OpenAI-compatible structured-claim contract as the CivicOS assistant. The model receives only saved notebook evidence, and any empty, malformed, uncited, or out-of-notebook claim is rejected. Provider failures return HTTP 503. Timeline generation does not infer events: it orders dated saved evidence and records the supporting document IDs.

Exports are generated on demand as Markdown or JSON. They include the saved-search trail, saved documents, notes, generated entries, citation IDs, document versions, excerpts, and canonical source URLs where available. CivicOS does not automatically publish or share a notebook.

## Frontend boundary

The notebook page currently demonstrates the intended evidence-desk UX with mock content. It intentionally does not call these endpoints until the authentication feature can supply trusted user and organization identity to a server-side client boundary.
