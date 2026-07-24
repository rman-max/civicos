"use client";

import Link from "next/link";
import type { ComponentProps } from "react";

import { trackBetaEvent } from "@/components/beta/analytics-tracker";

interface LaunchLinkProps extends ComponentProps<typeof Link> {
  eventName: "demo_started" | "example_notebook_opened" | "feedback_opened";
  surface: "landing" | "demo" | "notebook" | "feedback";
}

export function LaunchLink({ eventName, onClick, surface, ...props }: LaunchLinkProps) {
  return (
    <Link
      {...props}
      onClick={(event) => {
        trackBetaEvent(eventName, surface);
        onClick?.(event);
      }}
    />
  );
}
