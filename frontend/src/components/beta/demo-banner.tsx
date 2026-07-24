import Link from "next/link";

export function DemoBanner() {
  return (
    <div className="border-b border-rule bg-surface">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-2 px-5 py-3 text-sm sm:flex-row sm:items-center sm:justify-between sm:px-8 lg:px-12">
        <p className="text-ink-muted">
          <span className="font-medium text-ink">Public beta demo.</span> Illustrative records only — not an official record system.
        </p>
        <Link className="w-fit border-b border-ink pb-0.5 font-medium text-ink no-underline" href="/">
          About this beta
        </Link>
      </div>
    </div>
  );
}
