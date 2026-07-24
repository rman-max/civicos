import { PageContainer } from "@/components/layout/page-container";
import { PageHeader } from "@/components/layout/page-header";
import { Card } from "@/components/ui/card";
import { SectionHeading } from "@/components/ui/typography";

const opportunities = [
  {
    score: 91,
    label: "Procurement signal",
    title: "County solicitation language appears in a public works agenda",
    changed: "New request-for-proposals language was detected in a newly published county record.",
    matters: "A vendor-selection process may be approaching; confirm the formal solicitation and deadline.",
    money: "Engineering, construction, and specialist supplier demand may follow.",
    buyers: "Local contractors · professional-services firms · specialty suppliers",
    action: "Open cited record → identify eligibility and the next procurement event.",
  },
  {
    score: 84,
    label: "Infrastructure signal",
    title: "Transportation project language added to planning materials",
    changed: "An infrastructure project reference was detected alongside funding and planning terms.",
    matters: "Early project activity can precede design, inspection, materials, and construction work.",
    money: "Design, utility, materials, and implementation services may be needed.",
    buyers: "Engineering firms · contractors · materials suppliers",
    action: "Confirm phase, funding status, and anticipated delivery method.",
  },
  {
    score: 76,
    label: "Land-use signal",
    title: "Rezoning language detected in a planning record",
    changed: "A land-use change indicator appeared in a newly observed civic document.",
    matters: "Entitlement activity can change what may be built or operated in an area.",
    money: "Property, design, compliance, and adjacent business services may be relevant.",
    buyers: "Property owners · real-estate professionals · land-use consultants",
    action: "Check the parcel, hearing date, and proposed use before outreach.",
  },
];

const watchlists = ["Construction & infrastructure", "South Bend development", "Planning Department", "Local government procurement"];

export default function FounderConsolePage() {
  return (
    <PageContainer className="py-12 sm:py-16">
      <PageHeader
        eyebrow="St. Joseph County, Indiana · Daily Founder Brief"
        title="Where the money may be"
        description="High-value changes in the civic record, ranked for commercial follow-up. Every item stays tied to its evidence."
      />

      <section className="mt-10 grid gap-px border border-rule bg-rule md:grid-cols-4" aria-label="Founder brief summary">
        {[
          ["What changed", "3", "high-value record changes"],
          ["Why it matters", "2", "time-sensitive paths to verify"],
          ["Where money may be", "4", "commercial segments to investigate"],
          ["Action to take", "Today", "review cited source records"],
        ].map(([label, value, detail]) => (
          <Card key={label}>
            <p className="text-sm text-ink-muted">{label}</p>
            <p className="mt-5 font-serif text-4xl tracking-[-0.03em]">{value}</p>
            <p className="mt-2 text-sm text-ink-muted">{detail}</p>
          </Card>
        ))}
      </section>

      <div className="mt-16 grid gap-12 lg:grid-cols-[minmax(0,1fr)_18rem]">
        <section aria-labelledby="opportunities-heading">
          <div className="flex items-end justify-between gap-4 border-b border-rule pb-4">
            <div>
              <SectionHeading id="opportunities-heading">Ranked opportunities</SectionHeading>
              <p className="mt-2 text-sm text-ink-muted">Only changes above the Founder Brief threshold appear here.</p>
            </div>
            <p className="text-sm text-ink-muted">Score / 100</p>
          </div>
          <div className="divide-y divide-rule">
            {opportunities.map((item) => (
              <article className="py-8" key={item.title}>
                <div className="flex gap-5">
                  <p className="w-12 shrink-0 pt-1 font-serif text-3xl tracking-[-0.03em]">{item.score}</p>
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-medium uppercase tracking-[0.12em] text-ink-muted">{item.label}</p>
                    <h2 className="mt-2 font-serif text-2xl leading-tight tracking-[-0.02em] sm:text-3xl">{item.title}</h2>
                    <dl className="mt-6 grid gap-5 text-sm leading-6 sm:grid-cols-2">
                      <div><dt className="font-medium">What changed</dt><dd className="mt-1 text-ink-muted">{item.changed}</dd></div>
                      <div><dt className="font-medium">Why it matters</dt><dd className="mt-1 text-ink-muted">{item.matters}</dd></div>
                      <div><dt className="font-medium">Where the money may be</dt><dd className="mt-1 text-ink-muted">{item.money}</dd></div>
                      <div><dt className="font-medium">Who might pay</dt><dd className="mt-1 text-ink-muted">{item.buyers}</dd></div>
                    </dl>
                    <p className="mt-6 border-l-2 border-ink pl-4 text-sm leading-6"><span className="font-medium">Action: </span>{item.action}</p>
                    <p className="mt-5 text-xs uppercase tracking-[0.1em] text-ink-muted">Evidence required · Source record and excerpt available in the private API</p>
                  </div>
                </div>
              </article>
            ))}
          </div>
        </section>

        <aside className="border-t border-rule pt-5 lg:border-t-0 lg:border-l lg:pl-8 lg:pt-0">
          <SectionHeading>Watchlists</SectionHeading>
          <p className="mt-3 text-sm leading-6 text-ink-muted">Continuous monitoring for the things most likely to create a commercial lead.</p>
          <ul className="mt-5 divide-y divide-rule border-y border-rule">
            {watchlists.map((watchlist) => <li className="py-4 text-sm" key={watchlist}>{watchlist}</li>)}
          </ul>
          <p className="mt-8 text-xs leading-5 text-ink-muted">Companies, industries, properties, geographic areas, departments, projects, and topics are supported.</p>
        </aside>
      </div>
    </PageContainer>
  );
}
