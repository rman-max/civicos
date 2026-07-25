"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { NavigationList, type NavigationItem } from "@/components/navigation/navigation-list";

const primaryNavigation: NavigationItem[] = [
  { href: "/search", label: "Search" },
  { href: "/dashboard", label: "Dashboard" },
  { href: "/briefing", label: "Briefing" },
  { href: "/notebook", label: "Notebook" },
  { href: "/collections", label: "Collections" },
  { href: "/timeline", label: "Timeline" },
  { href: "/sources", label: "Sources" },
  { href: "/settings", label: "Settings" },
  { href: "/demo", label: "Demo" },
];

export function SiteHeader() {
  const pathname = usePathname();
  const items = primaryNavigation.map((item) => ({ ...item, current: item.href === pathname }));

  return (
    <header className="border-b border-rule">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-4 px-5 py-5 sm:flex-row sm:items-center sm:justify-between sm:px-8 lg:px-12">
        <Link
          className="font-serif text-xl font-semibold tracking-[-0.02em] text-ink no-underline"
          href="/"
        >
          CivicOS
        </Link>
        <NavigationList items={items} />
      </div>
    </header>
  );
}
