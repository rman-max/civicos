import type { ComponentPropsWithoutRef } from "react";

import { cn } from "@/lib/cn";

export function Eyebrow({ className, ...props }: ComponentPropsWithoutRef<"p">) {
  return (
    <p
      className={cn("text-xs font-medium uppercase tracking-[0.16em] text-ink-muted", className)}
      {...props}
    />
  );
}

export function PageTitle({ className, ...props }: ComponentPropsWithoutRef<"h1">) {
  return (
    <h1
      className={cn("mt-4 font-serif text-5xl font-normal tracking-[-0.035em] text-ink sm:text-6xl", className)}
      {...props}
    />
  );
}

export function SectionHeading({ className, ...props }: ComponentPropsWithoutRef<"h2">) {
  return (
    <h2
      className={cn("border-b border-rule pb-3 font-serif text-2xl font-normal tracking-[-0.02em] text-ink", className)}
      {...props}
    />
  );
}

