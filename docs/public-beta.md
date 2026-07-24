# Public beta launch guide

## Purpose and scope

The CivicOS public beta is a municipal evaluation environment, not a launch of a legal record system. Its purpose is to help municipal staff and civic partners assess whether an evidence-first civic interface makes official information easier to find, understand, and verify.

The landing page explains the value proposition; `/demo` provides a guided, illustrative workflow; `/notebook` shows an example evidence trail. Every demo route displays a persistent notice that records are illustrative and CivicOS is not an official record system.

## Municipal showcase script

Use this five-minute path with a municipal evaluator:

1. Start at the landing page and frame the promise: a public question should lead to a visible official source, date, and context.
2. Open `/demo` and use the capital-priorities question to show a result excerpt, publisher, record type, and date.
3. Open the notebook example to show how a resident, journalist, or staff member can preserve an evidence trail instead of copying isolated links into a document.
4. Explain that the production architecture keeps public sources versioned and does not ask users to trust uncited AI output.
5. Invite feedback about priority sources, terminology, accessibility, correction workflows, and the questions residents most often ask.

Do not imply the demo has complete, current, or official source coverage. For a live municipal pilot, show source health, coverage limits, freshness targets, and official links before discussing AI answers.

## Feedback

The landing-page feedback form sends voluntary submissions to `POST /public/beta-feedback`. It accepts a category, message, optional contact email, and the page path. Do not ask visitors for sensitive personal information, case details, or public-record requests through this form.

Feedback is stored separately from civic research data. An operator should review new submissions at least weekly, acknowledge contacts only when they opted in, classify source/correction reports promptly, and remove or restrict inappropriate submissions under the published retention policy.

Grant the API role only the feedback function it needs:

```sql
GRANT EXECUTE ON FUNCTION core.submit_public_beta_feedback(text, text, citext, text) TO civicos_api;
GRANT EXECUTE ON FUNCTION core.record_public_beta_analytics_event(text, text, text) TO civicos_api;
```

## Privacy-conscious analytics

Analytics is first-party and disabled by default. Set `NEXT_PUBLIC_BETA_ANALYTICS_ENABLED=true` only for the deployed beta. The client records a fixed event name, route path without query parameters, and a fixed interface surface. It records no cookies, user IDs, session IDs, IP addresses, search queries, document text, feedback content, or URL parameters.

Review aggregate event counts only to understand whether evaluators reach the demo, examples, and feedback flow. Do not use analytics for individual profiling, rankings, advertising, or decisions about people or communities. Define a short retention period before enabling it and delete raw beta events afterward.

## Launch checklist

- Confirm all public demo copy labels data as illustrative and links to the feedback/privacy explanation.
- Set exact production CORS and allowed-host values, OIDC configuration, metrics token, and beta analytics flag through the secret/deployment system.
- Apply migrations through `0008_public_beta_feedback_and_analytics.up.sql` and grant only documented API function rights.
- Test feedback submission, anonymous analytics, 429 protection, a 503 database failure, and an accessibility pass of the landing and demo routes.
- Have a municipal source-policy owner and beta feedback owner named before inviting external participants.
- Publish the beta scope, source coverage statement, correction path, privacy/retention statement, and contact method.
- Establish weekly source-health, feedback, analytics, accessibility, and incident reviews for the beta period.

## Success signals

Prioritize evidence of verified understanding over engagement volume:

- evaluators can find an official source after completing the demo;
- municipal staff can explain coverage and correction limits accurately;
- feedback identifies concrete source gaps or high-value user questions;
- no privacy, attribution, or source-provenance issue is left without a named owner; and
- a partner agrees to a scoped live pilot with approved sources and operational ownership.
