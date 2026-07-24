import Link from "next/link";

export interface NavigationItem {
  href: string;
  label: string;
  current?: boolean;
}

interface NavigationListProps {
  items: NavigationItem[];
  label?: string;
}

export function NavigationList({ items, label = "Primary navigation" }: NavigationListProps) {
  return (
    <nav aria-label={label}>
      <ul className="flex flex-wrap items-center gap-1 text-sm">
        {items.map((item) => (
          <li key={item.href}>
            <Link
              aria-current={item.current ? "page" : undefined}
              className="inline-flex border-b border-transparent px-2 py-1 text-ink-muted no-underline transition-colors hover:border-ink hover:text-ink aria-[current=page]:border-ink aria-[current=page]:text-ink"
              href={item.href}
            >
              {item.label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
