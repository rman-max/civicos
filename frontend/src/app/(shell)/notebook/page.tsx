import { PageContainer } from "@/components/layout/page-container";
import { PageHeader } from "@/components/layout/page-header";
import { Breadcrumbs } from "@/components/navigation/breadcrumbs";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { MetadataList } from "@/components/ui/metadata-list";
import { Notice } from "@/components/ui/notice";
import { StatusLabel } from "@/components/ui/status-label";
import { SectionHeading } from "@/components/ui/typography";

const notebookSections = ["Question", "Evidence desk", "Working notes", "Timeline"];

const evidenceItems = [
  {
    date: "Jul 23, 2026",
    excerpt:
      "The agenda includes a first reading on the proposed capital improvement plan and a public hearing schedule.",
    source: "County Council agenda packet",
    title: "Regular meeting agenda — July 28",
    type: "Meeting",
  },
  {
    date: "Jul 21, 2026",
    excerpt:
      "This working summary reflects departmental requests received through the most recent reporting period.",
    source: "Budget working papers",
    title: "2027 budget working summary",
    type: "Finance",
  },
];

export default function NotebookPage() {
  return (
    <PageContainer className="py-12 sm:py-16">
      <Breadcrumbs items={[{ href: "/dashboard", label: "Dashboard" }, { label: "Research notebook" }]} />
      <PageHeader
        action={
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary">Export research</Button>
            <Button>New note</Button>
          </div>
        }
        className="mt-8"
        description="A calm, source-first workspace for following a question from search result to evidence-backed finding."
        eyebrow="Research workspace"
        title="County budget research"
      />

      <Notice className="mt-8" title="Illustrative notebook">
        This public-beta notebook demonstrates the intended research flow with illustrative records. It is not a live civic record or a saved personal workspace.
      </Notice>

      <div className="mt-10 grid gap-10 lg:grid-cols-[12rem_minmax(0,1fr)_18rem]">
        <aside className="border-r border-rule pr-6" aria-label="Notebook outline">
          <p className="text-xs font-medium uppercase tracking-[0.14em] text-ink-muted">Notebook</p>
          <ol className="mt-4 space-y-1 text-sm">
            {notebookSections.map((section, index) => (
              <li key={section}>
                <a
                  className="flex gap-3 border-l border-transparent px-3 py-2 text-ink-muted no-underline hover:border-ink hover:text-ink"
                  href={`#${section.toLowerCase().replace(" ", "-")}`}
                >
                  <span>0{index + 1}</span>
                  {section}
                </a>
              </li>
            ))}
          </ol>

          <div className="mt-10 border-t border-rule pt-5">
            <p className="text-xs font-medium uppercase tracking-[0.14em] text-ink-muted">Notebook tools</p>
            <div className="mt-4 grid gap-2">
              <Button className="justify-start" variant="quiet">Generate summary</Button>
              <Button className="justify-start" variant="quiet">Create timeline</Button>
              <Button className="justify-start" variant="quiet">Save search</Button>
            </div>
          </div>
        </aside>

        <article className="min-w-0">
          <section id="question">
            <SectionHeading>Question</SectionHeading>
            <p className="civicos-prose mt-6">How do the published budget materials describe the county’s proposed capital priorities for the next fiscal year?</p>
          </section>

          <section className="mt-14" id="evidence-desk">
            <div className="flex flex-wrap items-baseline justify-between gap-3 border-b border-rule pb-3">
              <SectionHeading className="border-0 pb-0">Evidence desk</SectionHeading>
              <p className="text-sm text-ink-muted">2 saved records · 1 highlighted passage</p>
            </div>
            <div className="mt-6 space-y-5">
              {evidenceItems.map((item) => (
                <Card className="border border-rule p-5" key={item.title}>
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusLabel>{item.type}</StatusLabel>
                    <p className="text-sm text-ink-muted">{item.source}</p>
                  </div>
                  <h3 className="mt-3 font-serif text-2xl tracking-[-0.02em] text-ink">{item.title}</h3>
                  <blockquote className="mt-4 border-l-2 border-ink pl-4 font-serif text-lg leading-8 text-ink">
                    {item.excerpt}
                  </blockquote>
                  <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-sm text-ink-muted">
                    <time>{item.date}</time>
                    <Button className="min-h-8 px-3 py-1" variant="quiet">Open source</Button>
                  </div>
                </Card>
              ))}
            </div>
          </section>

          <section className="mt-14" id="working-notes">
            <SectionHeading>Working notes</SectionHeading>
            <div className="mt-6 divide-y divide-rule border-y border-rule">
              <div className="py-6">
                <p className="text-xs font-medium uppercase tracking-[0.14em] text-ink-muted">Observation</p>
                <p className="civicos-prose mt-3">The materials frame capital work through departmental requests, maintenance priorities, and a public hearing schedule.</p>
              </div>
              <div className="py-6">
                <p className="text-xs font-medium uppercase tracking-[0.14em] text-ink-muted">Open thread</p>
                <p className="civicos-prose mt-3">Compare the council packet with the auditor’s working summary before characterizing any priority as final.</p>
              </div>
            </div>
          </section>

          <section className="mt-14" id="timeline">
            <SectionHeading>Timeline</SectionHeading>
            <ol className="mt-6 border-l border-rule pl-5">
              <li className="relative pb-7 text-sm">
                <span className="absolute -left-[1.58rem] top-1 size-2 border border-ink bg-canvas" />
                <time className="text-ink-muted">Jul 21, 2026</time>
                <p className="mt-1 font-medium text-ink">Budget working summary published</p>
              </li>
              <li className="relative text-sm">
                <span className="absolute -left-[1.58rem] top-1 size-2 border border-ink bg-ink" />
                <time className="text-ink-muted">Jul 23, 2026</time>
                <p className="mt-1 font-medium text-ink">Council agenda packet added to the notebook</p>
              </li>
            </ol>
          </section>
        </article>

        <aside className="border-t border-rule pt-6 lg:border-t-0 lg:border-l lg:pl-7 lg:pt-0">
          <SectionHeading>Research trail</SectionHeading>
          <div className="mt-5">
            <MetadataList
              items={[
                { label: "Owner", value: "Research team" },
                { label: "Last updated", value: "Today" },
                { label: "Saved records", value: "2" },
                { label: "Citations", value: "1" },
              ]}
            />
          </div>

          <section className="mt-10 border-t border-rule pt-6" aria-labelledby="saved-searches-heading">
            <p className="text-xs font-medium uppercase tracking-[0.14em] text-ink-muted" id="saved-searches-heading">Saved searches</p>
            <div className="mt-4 space-y-4">
              <div>
                <p className="font-medium text-ink">County budget</p>
                <p className="mt-1 font-mono text-xs text-ink-muted">county budget</p>
              </div>
              <div>
                <p className="font-medium text-ink">Capital priorities</p>
                <p className="mt-1 font-mono text-xs text-ink-muted">capital improvement</p>
              </div>
            </div>
          </section>

          <section className="mt-10 border-t border-rule pt-6" aria-labelledby="source-trail-heading">
            <p className="text-xs font-medium uppercase tracking-[0.14em] text-ink-muted" id="source-trail-heading">Source trail</p>
            <p className="mt-4 text-sm leading-6 text-ink-muted">Every saved passage retains its document version and original public source for export or later review.</p>
          </section>
        </aside>
      </div>
    </PageContainer>
  );
}
