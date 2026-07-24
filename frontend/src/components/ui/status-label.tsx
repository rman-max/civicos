import { cn } from "@/lib/cn";

type StatusLabelTone = "muted" | "strong";

interface StatusLabelProps {
  children: string;
  tone?: StatusLabelTone;
}

const toneClasses: Record<StatusLabelTone, string> = {
  muted: "border-rule-strong text-ink-muted",
  strong: "border-ink text-ink",
};

export function StatusLabel({ children, tone = "muted" }: StatusLabelProps) {
  return (
    <span className={cn("inline-flex border px-2 py-0.5 text-xs font-medium uppercase tracking-[0.1em]", toneClasses[tone])}>
      {children}
    </span>
  );
}

