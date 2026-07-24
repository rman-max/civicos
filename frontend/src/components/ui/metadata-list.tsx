import type { ReactNode } from "react";

export interface MetadataItem {
  label: string;
  value: ReactNode;
}

interface MetadataListProps {
  items: MetadataItem[];
}

export function MetadataList({ items }: MetadataListProps) {
  return (
    <dl className="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-2">
      {items.map((item) => (
        <div className="flex justify-between gap-4 border-b border-rule py-2" key={item.label}>
          <dt className="text-ink-muted">{item.label}</dt>
          <dd className="text-right font-medium text-ink">{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}

