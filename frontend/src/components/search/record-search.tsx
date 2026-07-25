"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState, useSyncExternalStore } from "react";

import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
import { StatusLabel } from "@/components/ui/status-label";
import { TextInput } from "@/components/ui/text-input";
import { founderAccessTokenStorageKey } from "@/lib/founder-session";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

interface SearchResult {
  document_id: string;
  document_version_id: string;
  title: string;
  document_type: string;
  source_name: string | null;
  canonical_url: string | null;
  published_at: string | null;
  excerpt: string;
  match_kind: string;
  canonical_record_id: string | null;
  jurisdiction: string | null;
  summary: string | null;
  entities: string[];
  addresses: string[];
  money_amounts: string[];
  deadlines: string[];
  status: string | null;
  evidence: Array<{ source_text: string; source_url: string; confidence: number; page_reference: string | null; section_reference: string | null }>;
}

interface SearchResponse {
  results: SearchResult[];
  semantic_available: boolean;
}

interface IngestionStatus {
  document_count: number;
  last_corpus_update: string | null;
  failed_connector_count: number;
  indexing_mode: string;
}

type SearchState = "signed-out" | "idle" | "loading" | "ready" | "failure";

function subscribeToFounderSession(callback: () => void): () => void {
  window.addEventListener("storage", callback);
  return () => window.removeEventListener("storage", callback);
}

function hasFounderSession(): boolean {
  return window.sessionStorage.getItem(founderAccessTokenStorageKey) !== null;
}

function formatDate(value: string | null): string {
  if (!value) return "Publication date unavailable";
  return new Intl.DateTimeFormat("en-US", { dateStyle: "medium" }).format(
    new Date(`${value}T00:00:00`),
  );
}

export function RecordSearch() {
  const signedIn = useSyncExternalStore(subscribeToFounderSession, hasFounderSession, () => false);
  const [state, setState] = useState<SearchState>("idle");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [semanticAvailable, setSemanticAvailable] = useState(true);
  const [error, setError] = useState<string>();
  const [ingestionStatus, setIngestionStatus] = useState<IngestionStatus>();
  const [refreshing, setRefreshing] = useState(false);
  const [rawSources, setRawSources] = useState(false);

  useEffect(() => {
    if (!signedIn || !apiBaseUrl) return;
    const token = window.sessionStorage.getItem(founderAccessTokenStorageKey);
    if (!token) return;
    void fetch(`${apiBaseUrl}/v1/founder/ingestion/status`, {
      headers: { Authorization: `Bearer ${token}` },
    }).then(async (response) => {
      if (response.ok) setIngestionStatus((await response.json()) as IngestionStatus);
    });
  }, [signedIn]);

  async function refreshSources() {
    const token = window.sessionStorage.getItem(founderAccessTokenStorageKey);
    if (!token || !apiBaseUrl) return;
    setRefreshing(true);
    setError(undefined);
    try {
      const response = await fetch(`${apiBaseUrl}/v1/founder/ingestion/runs`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: "{}",
      });
      if (!response.ok) throw new Error("A refresh is already running or sources are unavailable.");
      setError("Refresh queued. The civic record will update as connectors finish.");
    } catch (refreshError) {
      setError(refreshError instanceof Error ? refreshError.message : "Could not refresh sources.");
    } finally {
      setRefreshing(false);
    }
  }

  async function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalizedQuery = query.trim();
    if (normalizedQuery.length < 2) {
      setError("Enter at least two characters to search the civic record.");
      return;
    }
    if (!apiBaseUrl) {
      setError("The CivicOS API has not been configured.");
      setState("failure");
      return;
    }
    const token = window.sessionStorage.getItem(founderAccessTokenStorageKey);
    if (!token) {
      setState("signed-out");
      return;
    }

    setState("loading");
    setError(undefined);
    try {
      const response = await fetch(
        `${apiBaseUrl}/v1/search?${new URLSearchParams({
          query: normalizedQuery,
          mode: "hybrid",
          limit: "20",
          view: rawSources ? "raw" : "canonical",
        })}`,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      if (response.status === 401) {
        window.sessionStorage.removeItem(founderAccessTokenStorageKey);
        setState("signed-out");
        return;
      }
      if (!response.ok) {
        throw new Error("CivicOS could not search the record. Please try again shortly.");
      }
      const payload = (await response.json()) as SearchResponse;
      setResults(payload.results);
      setSemanticAvailable(payload.semantic_available);
      setState("ready");
    } catch (searchError) {
      setError(searchError instanceof Error ? searchError.message : "CivicOS could not search the record.");
      setState("failure");
    }
  }

  if (!signedIn || state === "signed-out") {
    return (
      <Notice className="mt-8" title="Private search access required">
        Sign in once to Founder Intelligence. You will return to search automatically. {" "}
        <Link className="font-medium text-ink underline" href="/dashboard?returnTo=/search">Open Dashboard</Link>
      </Notice>
    );
  }

  return (
    <>
      <section className="mt-8 flex flex-wrap items-end justify-between gap-4 border-y border-rule py-4" aria-label="Corpus freshness">
        <div className="text-sm text-ink-muted">
          <p><span className="font-medium text-ink">{ingestionStatus?.document_count ?? "—"}</span> searchable documents · {ingestionStatus?.indexing_mode ?? "keyword"} indexing</p>
          <p className="mt-1">Last corpus update: {ingestionStatus?.last_corpus_update ? new Date(ingestionStatus.last_corpus_update).toLocaleString() : "not yet ingested"}{ingestionStatus?.failed_connector_count ? ` · ${ingestionStatus.failed_connector_count} connector failures` : ""}</p>
        </div>
        <Button disabled={refreshing} onClick={refreshSources} variant="secondary">{refreshing ? "Queueing refresh…" : "Refresh sources"}</Button>
      </section>
      <form className="mt-8 max-w-3xl" onSubmit={submitSearch} aria-label="Search records">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end">
          <TextInput
            className="flex-1"
            hint="Search a document title, phrase, or topic. Results always link to the original public record."
            id="record-search"
            label="Search civic records"
            onChange={(event) => setQuery(event.target.value)}
            placeholder="For example: housing, county budget, or zoning"
            type="search"
            value={query}
          />
          <Button className="shrink-0" disabled={state === "loading"} type="submit">
            {state === "loading" ? "Searching…" : "Search"}
          </Button>
        </div>
        <label className="mt-4 flex items-center gap-2 text-sm text-ink-muted">
          <input checked={rawSources} onChange={(event) => setRawSources(event.target.checked)} type="checkbox" />
          Show raw source documents instead of canonical civic records
        </label>
      </form>

      {error ? <Notice className="mt-8" title="Search unavailable">{error}</Notice> : null}

      {state === "ready" ? (
        <section className="mt-14" aria-labelledby="results-heading">
          <div className="flex flex-wrap items-baseline justify-between gap-4 border-b border-rule pb-3">
            <h2 className="font-serif text-3xl tracking-[-0.025em] text-ink" id="results-heading">Results</h2>
            <p className="text-sm text-ink-muted">{results.length} {results.length === 1 ? "record" : "records"}</p>
          </div>
          {!semanticAvailable ? (
            <Notice className="mt-6" title="Keyword search is active">
              Semantic search is not configured yet. These results come from the searchable civic record.
            </Notice>
          ) : null}
          {results.length === 0 ? (
            <Notice className="mt-8" title="No matching records">
              Try a broader term, or check back after the next source scan completes.
            </Notice>
          ) : (
            <div className="divide-y divide-rule">
              {results.map((result) => (
                <article className="py-7" key={result.document_version_id}>
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusLabel>{result.document_type.replaceAll("_", " ")}</StatusLabel>
                    <p className="text-sm text-ink-muted">{result.match_kind} match</p>
                  </div>
                  <h3 className="mt-3 font-serif text-3xl tracking-[-0.025em] text-ink">{result.title}</h3>
                  <p className="mt-3 max-w-3xl font-serif text-lg leading-8 text-ink-muted">{result.summary ?? result.excerpt}</p>
                  <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-ink-muted">
                    <span>{result.source_name ?? "Official public source"}</span>
                    <time>{formatDate(result.published_at)}</time>
                    {result.jurisdiction ? <span>{result.jurisdiction}</span> : null}
                    {result.status ? <span>Status: {result.status}</span> : null}
                    {result.money_amounts[0] ? <span>{result.money_amounts[0]}</span> : null}
                    {result.deadlines[0] ? <span>Deadline: {result.deadlines[0]}</span> : null}
                    {result.canonical_url ? (
                      <a className="font-medium text-ink underline" href={result.canonical_url} rel="noreferrer" target="_blank">Open original source</a>
                    ) : null}
                  </div>
                  {result.entities.length || result.addresses.length || result.evidence.length ? (
                    <div className="mt-3 text-sm text-ink-muted">
                      {result.entities.length ? <p>Entities: {result.entities.join(", ")}</p> : null}
                      {result.addresses.length ? <p>Location: {result.addresses.join(", ")}</p> : null}
                      {result.evidence[0] ? <p className="mt-1">Evidence: “{result.evidence[0].source_text}”</p> : null}
                    </div>
                  ) : null}
                </article>
              ))}
            </div>
          )}
        </section>
      ) : null}
    </>
  );
}
