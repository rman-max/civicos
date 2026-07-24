# ADR 0003: Use extractive, source-linked daily briefings

- Status: Accepted
- Date: 2026-07-24

## Context

CivicOS needs a low-maintenance daily digest that helps users follow publishing activity and upcoming government events. A generated prose summary can incorrectly infer policy changes or hide the primary source record.

## Decision

Generate one durable briefing per subscribed organization day from bounded PostgreSQL queries over normalized civic data. Store structured sections and direct record links, use the existing autonomous worker and leased job pattern, and deliver the result in-app. Do not use a language model to create the digest. Email and other external channels are deferred until an approved provider and consent model exist.

## Consequences

The first briefing is explainable, repeatable, and inexpensive to operate. It may be less polished than a natural-language newsletter, but it does not manufacture civic conclusions. Additional delivery channels can consume the same stored briefing and delivery abstraction later.
