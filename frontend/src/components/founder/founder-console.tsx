"use client";

import { useEffect, useState } from "react";
import type { FormEvent } from "react";

import { PageContainer } from "@/components/layout/page-container";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Notice } from "@/components/ui/notice";
import { TextInput } from "@/components/ui/text-input";
import { SectionHeading } from "@/components/ui/typography";
import { founderAccessTokenStorageKey } from "@/lib/founder-session";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

interface Opportunity {
  id: string;
  title: string;
  signal_type: string;
  score: number;
  what_happened: string;
  why_it_matters: string;
  where_money_may_be: string;
  who_might_pay: string[];
  action_to_take: string;
  source_url: string | null;
  discovered_at: string;
}

interface Watchlist {
  id: string;
  name: string;
  watch_type: string;
  match_count: number;
  latest_match_at: string | null;
}

interface FounderBrief {
  briefing_date: string;
  generated_at: string;
}

type ConsoleState = "checking" | "signed-out" | "loading" | "ready" | "failure";

async function request<T>(path: string, token: string): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    throw new Error(response.status === 401 ? "Your session has expired." : "CivicOS data is unavailable.");
  }
  return response.json() as Promise<T>;
}

export function FounderConsole() {
  const [state, setState] = useState<ConsoleState>("checking");
  const [secret, setSecret] = useState("");
  const [error, setError] = useState<string>();
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [watchlists, setWatchlists] = useState<Watchlist[]>([]);
  const [brief, setBrief] = useState<FounderBrief>();

  useEffect(() => {
    async function restoreSession() {
      const token = window.sessionStorage.getItem(founderAccessTokenStorageKey);
      if (!token) {
        setState("signed-out");
        return;
      }
      await load(token);
    }
    void restoreSession();
  }, []);

  async function load(token: string) {
    if (!apiBaseUrl) {
      setError("The Founder Console API has not been configured.");
      setState("failure");
      return;
    }
    setState("loading");
    setError(undefined);
    try {
      const [loadedOpportunities, loadedWatchlists, loadedBrief] = await Promise.all([
        request<Opportunity[]>("/v1/founder/opportunities", token),
        request<Watchlist[]>("/v1/founder/watchlists", token),
        request<FounderBrief>("/v1/founder/brief", token).catch(() => undefined),
      ]);
      setOpportunities(loadedOpportunities);
      setWatchlists(loadedWatchlists);
      setBrief(loadedBrief);
      setState("ready");
    } catch (loadError) {
      window.sessionStorage.removeItem(founderAccessTokenStorageKey);
      setError(loadError instanceof Error ? loadError.message : "CivicOS data is unavailable.");
      setState("signed-out");
    }
  }

  async function submitLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!apiBaseUrl) {
      setError("The Founder Console API has not been configured.");
      return;
    }
    setState("loading");
    setError(undefined);
    try {
      const response = await fetch(`${apiBaseUrl}/auth/founder/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ secret }),
      });
      if (!response.ok) {
        throw new Error("The founder secret was not accepted.");
      }
      const result = (await response.json()) as { access_token: string };
      window.sessionStorage.setItem(founderAccessTokenStorageKey, result.access_token);
      setSecret("");
      await load(result.access_token);
    } catch (loginError) {
      setError(loginError instanceof Error ? loginError.message : "Founder login failed.");
      setState("signed-out");
    }
  }

  function signOut() {
    window.sessionStorage.removeItem(founderAccessTokenStorageKey);
    setOpportunities([]);
    setWatchlists([]);
    setBrief(undefined);
    setState("signed-out");
  }

  if (state === "checking" || state === "loading") {
    return <FounderStatus title="Opening Founder Intelligence" message="Verifying secure access and loading evidence-bound civic data." />;
  }

  if (state === "signed-out") {
    return (
      <PageContainer className="max-w-xl py-16 sm:py-24">
        <PageHeader
          eyebrow="Founder Intelligence"
          title="Private access"
          description="Enter the private founder secret configured for this CivicOS deployment."
        />
        <form className="mt-10 space-y-6 border border-rule p-6 sm:p-8" onSubmit={submitLogin}>
          <TextInput
            autoComplete="current-password"
            id="founder-secret"
            label="Founder secret"
            onChange={(event) => setSecret(event.target.value)}
            required
            type="password"
            value={secret}
          />
          {error ? <Notice title="Access unavailable">{error}</Notice> : null}
          <Button className="w-full" type="submit">Open Founder Intelligence</Button>
        </form>
      </PageContainer>
    );
  }

  if (state === "failure") {
    return <FounderStatus title="Founder Intelligence is unavailable" message={error ?? "Try again shortly."} />;
  }

  return (
    <PageContainer className="py-12 sm:py-16">
      <div className="flex items-start justify-between gap-6">
        <PageHeader
          eyebrow="St. Joseph County, Indiana · Daily Founder Brief"
          title="Where the money may be"
          description="High-value changes in the civic record, ranked for commercial follow-up. Every item stays tied to its evidence."
        />
        <Button className="shrink-0" onClick={signOut} variant="quiet">Sign out</Button>
      </div>

      <section className="mt-10 grid gap-px border border-rule bg-rule md:grid-cols-4" aria-label="Founder brief summary">
        <Metric label="What changed" value={String(opportunities.length)} detail="ranked commercial opportunities" />
        <Metric label="Why it matters" value={brief ? "Today" : "Pending"} detail={brief ? `brief for ${brief.briefing_date}` : "brief generation awaits evidence"} />
        <Metric label="Where money may be" value={String(new Set(opportunities.flatMap((item) => item.who_might_pay)).size)} detail="potential customer segments" />
        <Metric label="Action to take" value={opportunities.length ? "Review" : "Monitor"} detail="open evidence before outreach" />
      </section>

      <div className="mt-16 grid gap-12 lg:grid-cols-[minmax(0,1fr)_18rem]">
        <section aria-labelledby="opportunities-heading">
          <div className="flex items-end justify-between gap-4 border-b border-rule pb-4">
            <div>
              <SectionHeading id="opportunities-heading">Ranked opportunities</SectionHeading>
              <p className="mt-2 text-sm text-ink-muted">Only evidence-bound changes above the Founder Brief threshold appear here.</p>
            </div>
            <p className="text-sm text-ink-muted">Score / 100</p>
          </div>
          {opportunities.length === 0 ? (
            <Notice className="mt-8" title="No high-value opportunities yet">CivicOS will add opportunities automatically when active source records yield evidence that meets the threshold.</Notice>
          ) : (
            <div className="divide-y divide-rule">
              {opportunities.map((item) => (
                <article className="py-8" key={item.id}>
                  <div className="flex gap-5">
                    <p className="w-12 shrink-0 pt-1 font-serif text-3xl tracking-[-0.03em]">{item.score}</p>
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-medium uppercase tracking-[0.12em] text-ink-muted">{item.signal_type}</p>
                      <h2 className="mt-2 font-serif text-2xl leading-tight tracking-[-0.02em] sm:text-3xl">{item.title}</h2>
                      <dl className="mt-6 grid gap-5 text-sm leading-6 sm:grid-cols-2">
                        <Detail label="What changed" value={item.what_happened} />
                        <Detail label="Why it matters" value={item.why_it_matters} />
                        <Detail label="Where the money may be" value={item.where_money_may_be} />
                        <Detail label="Who might pay" value={item.who_might_pay.join(" · ")} />
                      </dl>
                      <p className="mt-6 border-l-2 border-ink pl-4 text-sm leading-6"><span className="font-medium">Action: </span>{item.action_to_take}</p>
                      {item.source_url ? <a className="mt-5 inline-block text-xs font-medium uppercase tracking-[0.1em] text-ink underline" href={item.source_url} rel="noreferrer" target="_blank">Open original public source</a> : null}
                    </div>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>

        <aside className="border-t border-rule pt-5 lg:border-t-0 lg:border-l lg:pl-8 lg:pt-0">
          <SectionHeading>Watchlists</SectionHeading>
          <p className="mt-3 text-sm leading-6 text-ink-muted">Continuous monitoring for the things most likely to create a commercial lead.</p>
          {watchlists.length === 0 ? <p className="mt-5 text-sm leading-6 text-ink-muted">No watchlists yet.</p> : <ul className="mt-5 divide-y divide-rule border-y border-rule">{watchlists.map((watchlist) => <li className="py-4 text-sm" key={watchlist.id}><span className="block font-medium">{watchlist.name}</span><span className="mt-1 block text-ink-muted">{watchlist.match_count} matches · {watchlist.watch_type}</span></li>)}</ul>}
        </aside>
      </div>
    </PageContainer>
  );
}

function FounderStatus({ message, title }: { message: string; title: string }) {
  return <PageContainer className="max-w-xl py-16 sm:py-24"><PageHeader eyebrow="Founder Intelligence" title={title} description={message} /></PageContainer>;
}

function Metric({ detail, label, value }: { detail: string; label: string; value: string }) {
  return <Card><p className="text-sm text-ink-muted">{label}</p><p className="mt-5 font-serif text-4xl tracking-[-0.03em]">{value}</p><p className="mt-2 text-sm text-ink-muted">{detail}</p></Card>;
}

function Detail({ label, value }: { label: string; value: string }) {
  return <div><dt className="font-medium">{label}</dt><dd className="mt-1 text-ink-muted">{value}</dd></div>;
}
