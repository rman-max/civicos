import type { ReactNode } from "react";

import { DemoBanner } from "@/components/beta/demo-banner";
import { AppFrame } from "@/components/layout/app-frame";

export default function ShellLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <AppFrame>
      <DemoBanner />
      {children}
    </AppFrame>
  );
}
