import { PageContainer } from "@/components/layout/page-container";
import { PageHeader } from "@/components/layout/page-header";
import { Breadcrumbs } from "@/components/navigation/breadcrumbs";
import { StatusLabel } from "@/components/ui/status-label";
import { TextInput } from "@/components/ui/text-input";
import { SectionHeading } from "@/components/ui/typography";
import { searchResults } from "@/lib/mock-data";

export default function SearchPage() {
  return (
    <PageContainer className="py-12 sm:py-16">
      <Breadcrumbs items={[{ href: "/dashboard", label: "Dashboard" }, { label: "Search" }]} />
      <PageHeader
        className="mt-8"
        description="Search mock records across the St. Joseph County civic corpus. Every result will eventually retain its original source context."
        title="Search the record"
      />

      <section className="mt-8 max-w-3xl" aria-label="Search records">
        <TextInput
          defaultValue="county budget"
          hint="Try a body, topic, document title, or a phrase from a public record."
          id="record-search"
          label="Search civic records"
          placeholder="Search records"
          type="search"
        />
      </section>

      <div className="mt-14 grid gap-12 lg:grid-cols-[15rem_minmax(0,1fr)]">
        <aside className="border-t border-rule pt-5 lg:border-t-0 lg:border-r lg:pr-8 lg:pt-0" aria-labelledby="filters-heading">
          <SectionHeading id="filters-heading">Filter results</SectionHeading>
          <dl className="mt-5 space-y-5 text-sm">
            <div>
              <dt className="font-medium text-ink">Time range</dt>
              <dd className="mt-1 text-ink-muted">All available records</dd>
            </div>
            <div>
              <dt className="font-medium text-ink">Government body</dt>
              <dd className="mt-1 text-ink-muted">All bodies</dd>
            </div>
            <div>
              <dt className="font-medium text-ink">Record type</dt>
              <dd className="mt-1 text-ink-muted">All document types</dd>
            </div>
          </dl>
        </aside>

        <section aria-labelledby="results-heading">
          <div className="flex items-baseline justify-between gap-4 border-b border-rule pb-3">
            <SectionHeading className="border-0 pb-0" id="results-heading">Results</SectionHeading>
            <p className="text-sm text-ink-muted">3 mock records</p>
          </div>
          <div className="divide-y divide-rule">
            {searchResults.map((result) => (
              <article className="py-7" key={result.title}>
                <div className="flex flex-wrap items-center gap-2">
                  <StatusLabel>{result.type}</StatusLabel>
                  <p className="text-sm text-ink-muted">{result.body}</p>
                </div>
                <h2 className="mt-3 font-serif text-3xl tracking-[-0.025em] text-ink">{result.title}</h2>
                <p className="mt-3 max-w-3xl font-serif text-lg leading-8 text-ink-muted">{result.excerpt}</p>
                <div className="mt-4 flex flex-wrap gap-x-4 gap-y-1 text-sm text-ink-muted">
                  <span>{result.source}</span>
                  <time>{result.date}</time>
                </div>
              </article>
            ))}
          </div>
        </section>
      </div>
    </PageContainer>
  );
}

