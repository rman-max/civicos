# Autonomous discovery worker

This worker discovers documents only from active, administrator-configured `civic.sources` records. It has no upload endpoint and does not accept arbitrary URLs from the public API.

For every scheduled source scan, it:

- follows only HTTP(S) links within the configured government domain allowlist;
- respects `robots.txt` by default, uses bounded page counts and byte limits, and records the final source URL;
- supports HTML, PDF, DOCX, and CSV resources;
- calculates a SHA-256 content hash and appends an immutable `document_version` only when content changes;
- cleans extracted text and enriches a new version with dates, generic document classification, tenant departments/topics, and conservative entity mentions;
- evaluates the new version for deterministic, evidence-bound Founder Intelligence signals and matches active private watchlists;
- retains raw artifacts in S3-compatible object storage and a source observation for each successful fetch; and
- schedules the next run in PostgreSQL, with leases for safe concurrent workers and exponential retry after a failure.

The worker needs an internal database service account capable of processing all organizations. In production, provision a narrowly scoped service role and S3 write access only to the configured artifact bucket. Do not expose those credentials to the frontend or API process.

Founder Brief generation shares the worker loop and durable job/lease pattern. It generates only extractive, high-scoring opportunities; its score threshold and bounded section size are configured with `CIVICOS_FOUNDER_BRIEF_MINIMUM_SCORE` and `CIVICOS_FOUNDER_BRIEF_SECTION_LIMIT`.
