import Link from "next/link";

import { PageContainer } from "@/components/layout/page-container";
import { PageHeader } from "@/components/layout/page-header";
import { Card } from "@/components/ui/card";
import { SectionHeading } from "@/components/ui/typography";
import { dashboardMetrics, recentActivity } from "@/lib/mock-data";

export default function DashboardPage() {
  return (
    <PageContainer className="py-12 sm:py-16">
      <PageHeader
        description="A concise view of the county record, recent publishing activity, and the research work waiting for you."
        eyebrow="St. Joseph County, Indiana"
        title="Good morning"
      />

      <section className="mt-10" aria-label="CivicOS overview">
        <div className="grid gap-px border border-rule bg-rule sm:grid-cols-2 lg:grid-cols-4">
          {dashboardMetrics.map((metric) => (
            <Card key={metric.label}>
              <p className="text-sm text-ink-muted">{metric.label}</p>
              <p className="mt-5 font-serif text-4xl tracking-[-0.03em] text-ink">{metric.value}</p>
            </Card>
          ))}
        </div>
      </section>

      <div className="mt-16 grid gap-12 lg:grid-cols-[minmax(0,1fr)_19rem]">
        <section aria-labelledby="recent-activity-heading">
          <SectionHeading id="recent-activity-heading">Recent activity</SectionHeading>
          <div className="divide-y divide-rule">
            {recentActivity.map((item) => (
              <article className="py-6" key={item.title}>
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <p className="text-sm text-ink-muted">{item.type} · {item.body}</p>
                    <h3 className="mt-1 font-serif text-2xl tracking-[-0.02em] text-ink">{item.title}</h3>
                    <p className="mt-2 max-w-2xl text-sm leading-6 text-ink-muted">{item.description}</p>
                  </div>
                  <time className="shrink-0 text-sm text-ink-muted">{item.date}</time>
                </div>
              </article>
            ))}
          </div>
        </section>

        <aside className="border-t border-rule pt-5 lg:border-t-0 lg:border-l lg:pl-8 lg:pt-0" aria-labelledby="next-steps-heading">
          <SectionHeading id="next-steps-heading">Continue work</SectionHeading>
          <div className="mt-5 text-sm leading-6">
            <p className="text-ink-muted">Search newly published records or return to a saved research thread.</p>
            <div className="mt-5 flex flex-col items-start gap-4">
              <Link className="border-b border-ink pb-1 font-medium text-ink no-underline" href="/search">
                Search the record
              </Link>
              <Link className="border-b border-ink pb-1 font-medium text-ink no-underline" href="/notebook">
                Open research notebook
              </Link>
            </div>
          </div>
        </aside>
      </div>
    </PageContainer>
  );
}
