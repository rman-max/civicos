# ADR 0001: Evidence-bound assistant responses

- Status: Accepted
- Date: 2026-07-24

## Context

CivicOS users need natural-language answers about local government activity. Civic records are incomplete, can contain conflicting statements, and may include prompt-injection text. A general-purpose model response without verifiable support is unsuitable for civic research.

## Decision

Use the existing tenant-scoped hybrid retrieval service as the only context source for the assistant. Ask an OpenAI-compatible model for structured claim drafts that reference retrieved evidence IDs. Validate those IDs server-side, render only claims with valid citations, and return an explicit insufficient-evidence result for absent or invalid grounding. Compute confidence from evidence coverage and diversity on the server.

## Consequences

The assistant never returns an uncited prose answer and does not silently fall back to model knowledge. It adds an approved answer-model runtime dependency and can decline useful questions when the corpus is sparse. Citation references are request-scoped rather than automatically persisted, which avoids retaining user questions by default but leaves notebook integration for a later feature.
