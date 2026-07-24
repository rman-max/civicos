import type { ReactNode } from "react";

import { FounderFrame } from "@/components/layout/founder-frame";

export default function FounderLayout({ children }: Readonly<{ children: ReactNode }>) {
  return <FounderFrame>{children}</FounderFrame>;
}
