import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

interface NoticeProps {
  children: ReactNode;
  className?: string;
  title?: string;
}

export function Notice({ children, className, title }: NoticeProps) {
  return (
    <aside className={cn("border-l-2 border-ink bg-surface px-5 py-4", className)}>
      {title ? <p className="text-sm font-medium text-ink">{title}</p> : null}
      <div className={cn("text-sm leading-6 text-ink-muted", title && "mt-1")}>{children}</div>
    </aside>
  );
}

