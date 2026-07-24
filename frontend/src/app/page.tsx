import Link from "next/link";

import { AnalyticsTracker } from "@/components/beta/analytics-tracker";
import { FeedbackForm } from "@/components/beta/feedback-form";
import { LaunchLink } from "@/components/beta/launch-link";
import { Card } from "@/components/ui/card";
import { exampleNotebooks } from "@/lib/mock-data";

const municipalBenefits = [
  ["Make the record findable", "Bring approved public sources into one evidence-first public experience."],
  ["Show the work behind an answer", "Keep source links, dates, and document context visible at every step."],
  ["Reduce routine navigation burden", "Help residents arrive at the right official record before they call or file a request."],
];

export default function HomePage() {
  return (
    <main>
      <AnalyticsTracker surface="landing" />
      <header className="border-b border-rule">
        <div className="mx-auto flex w-full max-w-7xl items-center justify-between px-5 py-5 sm:px-8 lg:px-12">
          <Link className="font-serif text-xl font-semibold tracking-[-0.02em] text-ink no-underline" href="/">
            CivicOS
          </Link>
          <a className="border-b border-ink pb-0.5 text-sm font-medium text-ink no-underline" href="#feedback">
            Join the beta
          </a>
        </div>
      </header>

      <section className="mx-auto grid w-full max-w-7xl gap-12 px-5 py-20 sm:px-8 sm:py-28 lg:grid-cols-[minmax(0,1fr)_20rem] lg:px-12">
        <div className="max-w-4xl">
          <p className="text-xs font-medium uppercase tracking-[0.16em] text-ink-muted">Public beta · St. Joseph County, Indiana</p>
          <h1 className="mt-7 font-serif text-5xl leading-[1.03] tracking-[-0.04em] text-ink sm:text-7xl">
            Make local government easier to understand.
          </h1>
          <p className="mt-8 max-w-2xl font-serif text-2xl leading-9 text-ink-muted">
            CivicOS turns fragmented public records into a calm, source-first civic research experience — without asking people to trust a black box.
          </p>
          <div className="mt-10 flex flex-wrap gap-3">
            <LaunchLink
              className="border border-ink bg-ink px-5 py-3 text-sm font-medium text-canvas no-underline hover:opacity-90"
              eventName="demo_started"
              href="/demo"
              surface="landing"
            >
              Explore the demo
            </LaunchLink>
            <a className="border border-rule-strong px-5 py-3 text-sm font-medium text-ink no-underline hover:border-ink" href="#how-it-helps">
              See the municipal value
            </a>
          </div>
        </div>
        <aside className="border-t border-rule pt-6 lg:border-t-0 lg:border-l lg:pl-8 lg:pt-0">
          <p className="text-xs font-medium uppercase tracking-[0.16em] text-ink-muted">Built for public trust</p>
          <dl className="mt-5 divide-y divide-rule border-y border-rule">
            <div className="py-4">
              <dt className="text-sm text-ink-muted">Every result</dt>
              <dd className="mt-1 font-serif text-xl">Points to an official source</dd>
            </div>
            <div className="py-4">
              <dt className="text-sm text-ink-muted">Every summary</dt>
              <dd className="mt-1 font-serif text-xl">Shows its supporting evidence</dd>
            </div>
            <div className="py-4">
              <dt className="text-sm text-ink-muted">Every beta screen</dt>
              <dd className="mt-1 font-serif text-xl">Clearly marks illustrative data</dd>
            </div>
          </dl>
        </aside>
      </section>

      <section className="border-y border-rule bg-surface" id="how-it-helps">
        <div className="mx-auto w-full max-w-7xl px-5 py-20 sm:px-8 lg:px-12">
          <p className="text-xs font-medium uppercase tracking-[0.16em] text-ink-muted">For municipalities and civic partners</p>
          <div className="mt-6 grid gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
            <h2 className="font-serif text-4xl leading-tight tracking-[-0.03em]">A better path from a public question to an official record.</h2>
            <div className="grid gap-px border border-rule bg-rule sm:grid-cols-3">
              {municipalBenefits.map(([title, description], index) => (
                <Card key={title}>
                  <p className="text-sm text-ink-muted">0{index + 1}</p>
                  <h3 className="mt-8 font-serif text-2xl tracking-[-0.02em]">{title}</h3>
                  <p className="mt-4 text-sm leading-6 text-ink-muted">{description}</p>
                </Card>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto w-full max-w-7xl px-5 py-20 sm:px-8 lg:px-12">
        <div className="flex flex-col justify-between gap-6 border-b border-rule pb-7 sm:flex-row sm:items-end">
          <div>
            <p className="text-xs font-medium uppercase tracking-[0.16em] text-ink-muted">Example research notebooks</p>
            <h2 className="mt-4 font-serif text-4xl tracking-[-0.03em]">Show the question, evidence, and trail.</h2>
          </div>
          <LaunchLink className="border-b border-ink pb-1 text-sm font-medium text-ink no-underline" eventName="example_notebook_opened" href="/demo#notebooks" surface="landing">
            View all examples
          </LaunchLink>
        </div>
        <div className="mt-8 grid gap-px border border-rule bg-rule lg:grid-cols-3">
          {exampleNotebooks.map((notebook) => (
            <Card key={notebook.title}>
              <p className="text-xs font-medium uppercase tracking-[0.14em] text-ink-muted">{notebook.trail}</p>
              <h3 className="mt-5 font-serif text-3xl tracking-[-0.03em]">{notebook.title}</h3>
              <p className="mt-4 text-sm leading-6 text-ink-muted">{notebook.description}</p>
              <p className="mt-8 border-t border-rule pt-4 text-sm text-ink-muted">{notebook.evidence}</p>
            </Card>
          ))}
        </div>
      </section>

      <section className="border-t border-rule" id="feedback">
        <div className="mx-auto grid w-full max-w-7xl gap-12 px-5 py-20 sm:px-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] lg:px-12">
          <div>
            <p className="text-xs font-medium uppercase tracking-[0.16em] text-ink-muted">Shape the public beta</p>
            <h2 className="mt-4 font-serif text-4xl leading-tight tracking-[-0.03em]">What would make CivicOS useful in your municipality?</h2>
            <p className="mt-5 max-w-xl text-base leading-7 text-ink-muted">We are looking for practical feedback from residents, journalists, nonprofit teams, researchers, and local government staff. The demo is illustrative; feedback helps us decide what to validate next.</p>
          </div>
          <div className="border-t border-rule pt-8 lg:border-t-0 lg:border-l lg:pl-10 lg:pt-0">
            <FeedbackForm />
          </div>
        </div>
      </section>

      <footer className="border-t border-rule bg-surface">
        <div className="mx-auto flex w-full max-w-7xl flex-col gap-3 px-5 py-7 text-sm text-ink-muted sm:flex-row sm:items-center sm:justify-between sm:px-8 lg:px-12">
          <p>CivicOS public beta · Evidence-first civic intelligence.</p>
          <p>Illustrative demo data. Not an official record system.</p>
        </div>
      </footer>
    </main>
  );
}
