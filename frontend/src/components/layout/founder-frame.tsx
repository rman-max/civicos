import type { ReactNode } from "react";

import Link from "next/link";

interface FounderFrameProps {
  children: ReactNode;
}

/** Private frame intentionally kept out of the public-beta navigation. */
export function FounderFrame({ children }: FounderFrameProps) {
  return (
    <div className="min-h-screen bg-canvas text-ink">
      <header className="border-b border-rule">
        <div className="mx-auto flex w-full max-w-7xl items-center justify-between px-5 py-5 sm:px-8 lg:px-12">
          <div>
            <Link className="font-serif text-xl font-semibold tracking-[-0.02em] text-ink no-underline" href="/founder">
              CivicOS
            </Link>
            <p className="mt-1 text-xs font-medium uppercase tracking-[0.14em] text-ink-muted">Founder Intelligence</p>
          </div>
          <span className="border border-rule-strong px-3 py-1 text-xs font-medium uppercase tracking-[0.12em] text-ink">
            Private workspace
          </span>
        </div>
      </header>
      {children}
    </div>
  );
}
