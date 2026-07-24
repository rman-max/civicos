import type { ComponentPropsWithoutRef } from "react";

import { cn } from "@/lib/cn";

export function PageContainer({ className, ...props }: ComponentPropsWithoutRef<"main">) {
  return (
    <main className={cn("mx-auto w-full max-w-7xl px-5 sm:px-8 lg:px-12", className)} {...props} />
  );
}

export function ContentColumn({ className, ...props }: ComponentPropsWithoutRef<"div">) {
  return <div className={cn("max-w-3xl", className)} {...props} />;
}

