# ADR 0002: Preserve source versions in research notebooks

- Status: Accepted
- Date: 2026-07-24

## Context

Researchers need to retain searches, documents, annotations, summaries, and timelines without losing the public records that support their work. Civic documents can receive new versions, so a notebook cannot treat a mutable URL or current document text as sufficient evidence.

## Decision

Use existing `research.notebooks`, ordered `research.notebook_entries`, and `civic.citations` as the notebook foundation. Add first-class saved-search and saved-document tables. Store highlights and generated references as citations to immutable `document_versions`; store notes, summaries, and timelines as typed entries. Generate summaries only from notebook evidence and reject model drafts that cannot be tied to that evidence. Generate timelines deterministically from dated evidence.

## Consequences

Exports remain reproducible and source-traceable even when a logical document receives a new version. The model cannot use outside context for a notebook summary. Saved documents resolve to their newest version for convenient display, while annotations retain their original version. The feature requires authenticated user scope before a browser can call its API safely.
