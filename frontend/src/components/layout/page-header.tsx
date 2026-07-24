import type { ReactNode } from "react";

import { Eyebrow, PageTitle } from "@/components/ui/typography";
import { cn } from "@/lib/cn";

interface PageHeaderProps {
  action?: ReactNode;
  className?: string;
  description?: string;
  eyebrow?: string;
  title: string;
}

export function PageHeader({ action, className, description, eyebrow, title }: PageHeaderProps) {
  return (
    <header className={cn("border-b border-rule pb-8", className)}>
      <div className="flex flex-col gap-6 sm:flex-row sm:items-end sm:justify-between">
        <div>
          {eyebrow ? <Eyebrow>{eyebrow}</Eyebrow> : null}
          <PageTitle>{title}</PageTitle>
          {description ? <p className="mt-4 max-w-2xl text-base leading-7 text-ink-muted">{description}</p> : null}
        </div>
        {action ? <div className="shrink-0">{action}</div> : null}
      </div>
    </header>
  );
}

