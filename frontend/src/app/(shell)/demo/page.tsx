import Link from "next/link";

import { AnalyticsTracker } from "@/components/beta/analytics-tracker";
import { LaunchLink } from "@/components/beta/launch-link";
import { PageContainer } from "@/components/layout/page-container";
import { Card } from "@/components/ui/card";
import { StatusLabel } from "@/components/ui/status-label";
import { exampleNotebooks, searchResults } from "@/lib/mock-data";

export default function DemoPage() {
  return (
    <PageContainer className="py-12 sm:py-16">
      <AnalyticsTracker surface="demo" />
      <header className="max-w-3xl border-b border-rule pb-10">
        <p className="text-xs font-medium uppercase tracking-[0.16em] text-ink-muted">Guided public beta demo</p>
        <h1 className="mt-5 font-serif text-5xl tracking-[-0.04em]">Follow one civic question from record to evidence.</h1>
        <p className="mt-6 font-serif text-2xl leading-9 text-ink-muted">This guided environment uses illustrative St. Joseph County records to show the intended CivicOS workflow. It does not represent live coverage or official information.</p>
      </header>

      <section className="mt-12 grid gap-10 lg:grid-cols-[14rem_minmax(0,1fr)]">
        <aside className="border-r border-rule pr-6">
          <p className="text-xs font-medium uppercase tracking-[0.14em] text-ink-muted">Demo path</p>
          <ol className="mt-5 space-y-4 text-sm">
            <li><span className="mr-3 text-ink-muted">01</span> Start with a question</li>
            <li><span className="mr-3 text-ink-muted">02</span> Inspect the record</li>
            <li><span className="mr-3 text-ink-muted">03</span> Save an evidence trail</li>
            <li><span className="mr-3 text-ink-muted">04</span> Share feedback</li>
          </ol>
        </aside>
        <div className="min-w-0">
          <section>
            <p className="text-xs font-medium uppercase tracking-[0.14em] text-ink-muted">01 · Start with a question</p>
            <blockquote className="mt-4 border-l-2 border-ink pl-5 font-serif text-3xl leading-tight">“What has been published about the county’s proposed capital priorities?”</blockquote>
            <p className="mt-5 max-w-2xl text-sm leading-6 text-ink-muted">CivicOS should make the source trail visible from the first result — not wait until a user has already accepted a summary.</p>
          </section>

          <section className="mt-14">
            <div className="flex items-baseline justify-between gap-4 border-b border-rule pb-3">
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-ink-muted">02 · Inspect the record</p>
              <Link className="text-sm font-medium text-ink" href="/search">Open demo search</Link>
            </div>
            <div className="divide-y divide-rule">
              {searchResults.slice(0, 2).map((result) => (
                <article className="py-6" key={result.title}>
                  <div className="flex flex-wrap items-center gap-2"><StatusLabel>{result.type}</StatusLabel><span className="text-sm text-ink-muted">{result.body}</span></div>
                  <h2 className="mt-3 font-serif text-3xl tracking-[-0.03em]">{result.title}</h2>
                  <p className="mt-3 max-w-2xl font-serif text-lg leading-8 text-ink-muted">{result.excerpt}</p>
                  <p className="mt-4 text-sm text-ink-muted">{result.source} · {result.date}</p>
                </article>
              ))}
            </div>
          </section>

          <section className="mt-14" id="notebooks">
            <p className="text-xs font-medium uppercase tracking-[0.14em] text-ink-muted">03 · Save an evidence trail</p>
            <div className="mt-5 grid gap-px border border-rule bg-rule md:grid-cols-3">
              {exampleNotebooks.map((notebook) => (
                <Card key={notebook.title}>
                  <p className="text-sm text-ink-muted">{notebook.evidence}</p>
                  <h2 className="mt-5 font-serif text-2xl tracking-[-0.02em]">{notebook.title}</h2>
                  <p className="mt-4 text-sm leading-6 text-ink-muted">{notebook.question}</p>
                </Card>
              ))}
            </div>
            <LaunchLink className="mt-6 inline-block border-b border-ink pb-1 text-sm font-medium text-ink no-underline" eventName="example_notebook_opened" href="/notebook" surface="demo">
              Open the budget notebook example
            </LaunchLink>
          </section>
        </div>
      </section>
    </PageContainer>
  );
}
