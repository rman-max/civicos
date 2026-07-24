import Link from "next/link";

import { PageContainer } from "@/components/layout/page-container";
import { PageHeader } from "@/components/layout/page-header";
import { Breadcrumbs } from "@/components/navigation/breadcrumbs";
import { Button } from "@/components/ui/button";
import { StatusLabel } from "@/components/ui/status-label";
import { collections } from "@/lib/mock-data";

export default function CollectionsPage() {
  return (
    <PageContainer className="py-12 sm:py-16">
      <Breadcrumbs items={[{ href: "/dashboard", label: "Dashboard" }, { label: "Collections" }]} />
      <PageHeader
        action={<Button variant="secondary">New collection</Button>}
        className="mt-8"
        description="Curated groups of mock records keep an ongoing civic topic legible over time."
        title="Collections"
      />

      <section className="mt-10 divide-y divide-rule border-y border-rule" aria-label="Saved collections">
        {collections.map((collection) => (
          <article className="grid gap-5 py-7 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-start" key={collection.title}>
            <div>
              <StatusLabel>Collection</StatusLabel>
              <h2 className="mt-3 font-serif text-3xl tracking-[-0.025em] text-ink">{collection.title}</h2>
              <p className="mt-3 max-w-2xl text-base leading-7 text-ink-muted">{collection.description}</p>
            </div>
            <div className="text-left text-sm text-ink-muted sm:text-right">
              <p>{collection.items} mock records</p>
              <p className="mt-1">{collection.updated}</p>
              <Link className="mt-4 inline-block border-b border-ink pb-1 font-medium text-ink no-underline" href="/search">
                View records
              </Link>
            </div>
          </article>
        ))}
      </section>
    </PageContainer>
  );
}

