import type { ReactNode } from "react";

import { SiteHeader } from "@/components/navigation/site-header";

interface AppFrameProps {
  children: ReactNode;
}

export function AppFrame({ children }: AppFrameProps) {
  return (
    <div className="min-h-screen bg-canvas text-ink">
      <SiteHeader />
      {children}
    </div>
  );
}

