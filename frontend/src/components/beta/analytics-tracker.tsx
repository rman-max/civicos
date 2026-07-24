"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";

type AnalyticsEventName =
  | "beta_page_view"
  | "demo_started"
  | "example_notebook_opened"
  | "feedback_opened"
  | "feedback_submitted";
type AnalyticsSurface = "landing" | "demo" | "notebook" | "feedback";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

function enabled() {
  return process.env.NEXT_PUBLIC_BETA_ANALYTICS_ENABLED === "true" && apiBaseUrl.length > 0;
}

export function trackBetaEvent(eventName: AnalyticsEventName, surface?: AnalyticsSurface) {
  if (!enabled() || typeof window === "undefined") {
    return;
  }

  const payload = JSON.stringify({ event_name: eventName, page_path: window.location.pathname, surface });
  void fetch(`${apiBaseUrl}/public/analytics/events`, {
    body: payload,
    headers: { "Content-Type": "application/json" },
    keepalive: true,
    method: "POST",
  });
}

interface AnalyticsTrackerProps {
  surface: AnalyticsSurface;
}

export function AnalyticsTracker({ surface }: AnalyticsTrackerProps) {
  const pathname = usePathname();

  useEffect(() => {
    trackBetaEvent("beta_page_view", surface);
  }, [pathname, surface]);

  return null;
}
