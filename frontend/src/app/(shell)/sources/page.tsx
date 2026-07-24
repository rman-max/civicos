import { PageContainer } from "@/components/layout/page-container";
import { PageHeader } from "@/components/layout/page-header";
import { Breadcrumbs } from "@/components/navigation/breadcrumbs";
import { Notice } from "@/components/ui/notice";
import { StatusLabel } from "@/components/ui/status-label";
import { sources } from "@/lib/mock-data";

export default function SourcesPage() {
  return (
    <PageContainer className="py-12 sm:py-16">
      <Breadcrumbs items={[{ href: "/dashboard", label: "Dashboard" }, { label: "Sources" }]} />
      <PageHeader
        className="mt-8"
        description="Source health is part of civic trust. This mock inventory makes freshness, coverage, and exceptions visible."
        title="Sources"
      />

      <Notice className="mt-8" title="Mock source inventory">
        These entries demonstrate the source health interface. No source is currently connected or being collected.
      </Notice>

      <section className="mt-10 overflow-x-auto" aria-label="Source inventory">
        <table className="w-full min-w-[48rem] border-collapse text-left text-sm">
          <thead className="border-y border-rule text-xs uppercase tracking-[0.12em] text-ink-muted">
            <tr>
              <th className="px-3 py-4 font-medium">Source</th>
              <th className="px-3 py-4 font-medium">Coverage</th>
              <th className="px-3 py-4 font-medium">Last checked</th>
              <th className="px-3 py-4 font-medium">Records</th>
              <th className="px-3 py-4 font-medium">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-rule">
            {sources.map((source) => (
              <tr className="align-top" key={source.name}>
                <td className="px-3 py-5">
                  <p className="font-medium text-ink">{source.name}</p>
                  <p className="mt-1 text-ink-muted">{source.type}</p>
                </td>
                <td className="px-3 py-5 leading-6 text-ink-muted">{source.coverage}</td>
                <td className="px-3 py-5 text-ink-muted">{source.lastChecked}</td>
                <td className="px-3 py-5 text-ink-muted">{source.records}</td>
                <td className="px-3 py-5">
                  <StatusLabel tone={source.status === "Current" ? "muted" : "strong"}>{source.status}</StatusLabel>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </PageContainer>
  );
}
