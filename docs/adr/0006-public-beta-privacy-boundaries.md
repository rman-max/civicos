# ADR 0006: Keep public-beta feedback and analytics minimal and separate

**Status:** Accepted  
**Date:** 2026-07-24

## Context

The public beta needs a way to learn whether municipal evaluators reach the demo and to collect voluntary improvement feedback. Conventional third-party analytics and session tracking conflict with CivicOS’s public-trust posture and can create unnecessary surveillance of civic research behavior.

## Decision

Use first-party, anonymous event records with a fixed event taxonomy, route path without query parameters, and a fixed interface surface. Do not store cookies, user IDs, session IDs, IP addresses, searches, document contents, or feedback text in analytics. Keep feedback as a separate voluntary store with an optional contact email.

The public beta is backed by explicit `POST /public/...` endpoints rather than authenticated civic-record routes. They are rate-limited and use narrow security-definer functions. Analytics remains disabled unless the deployment explicitly enables it.

## Consequences

- Product learning is limited to aggregate beta flow, which is intentional.
- Operators must define retention and review ownership before activation.
- The demo can be shown publicly without representing illustrative records as live, official coverage.
- A later live pilot may add consented, purpose-limited measurement only through a separate review and ADR.
