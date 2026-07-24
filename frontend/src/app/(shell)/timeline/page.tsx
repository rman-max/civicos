import { PageContainer } from "@/components/layout/page-container";
import { PageHeader } from "@/components/layout/page-header";
import { Breadcrumbs } from "@/components/navigation/breadcrumbs";
import { StatusLabel } from "@/components/ui/status-label";
import { SectionHeading } from "@/components/ui/typography";
import { timelineItems } from "@/lib/mock-data";

export default function TimelinePage() {
  return (
    <PageContainer className="py-12 sm:py-16">
      <Breadcrumbs items={[{ href: "/dashboard", label: "Dashboard" }, { label: "Timeline" }]} />
      <PageHeader
        className="mt-8"
        description="A chronological view of mock publishing activity and upcoming public meetings."
        title="Civic timeline"
      />

      <section className="mt-12 max-w-4xl" aria-labelledby="timeline-heading">
        <SectionHeading id="timeline-heading">This week</SectionHeading>
        <ol className="relative mt-6 border-l border-rule">
          {timelineItems.map((item) => (
            <li className="relative pl-8 pb-10 last:pb-0" key={item.title}>
              <span aria-hidden="true" className="absolute -left-[5px] top-1.5 size-2.5 border border-ink bg-canvas" />
              <div className="flex flex-wrap items-center gap-2">
                <StatusLabel tone={item.type === "Upcoming" ? "strong" : "muted"}>{item.type}</StatusLabel>
                <time className="text-sm text-ink-muted">{item.date}</time>
              </div>
              <h2 className="mt-3 font-serif text-3xl tracking-[-0.025em] text-ink">{item.title}</h2>
              <p className="mt-2 text-sm text-ink-muted">{item.body}</p>
              <p className="mt-3 max-w-2xl text-base leading-7 text-ink-muted">{item.description}</p>
            </li>
          ))}
        </ol>
      </section>
    </PageContainer>
  );
}
