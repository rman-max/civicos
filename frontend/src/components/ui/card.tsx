import type { ComponentPropsWithoutRef } from "react";

import { cn } from "@/lib/cn";

export function Card({ className, ...props }: ComponentPropsWithoutRef<"div">) {
  return <div className={cn("bg-canvas p-6", className)} {...props} />;
}

