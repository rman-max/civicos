# AI boundary

CivicOS uses provider-neutral OpenAI-compatible endpoints for embeddings and grounded answer generation. The API service owns request-time retrieval, citation validation, and model access; the ingestion worker owns offline document embeddings.

The grounded assistant is disabled until `LLM_BASE_URL` and `LLM_MODEL` are configured. Credentials remain service-only configuration. No model endpoint, prompt, or API key is exposed through `NEXT_PUBLIC_*` values.

See `docs/assistant.md` for the grounding contract and deployment requirements.
