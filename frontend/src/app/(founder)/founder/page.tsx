import { redirect } from "next/navigation";

interface FounderConsolePageProps {
  searchParams: Promise<{ returnTo?: string | string[] }>;
}

export default async function FounderConsolePage({ searchParams }: FounderConsolePageProps) {
  const { returnTo } = await searchParams;
  const safeReturnTo = typeof returnTo === "string" && returnTo.startsWith("/") && !returnTo.startsWith("//")
    ? `?returnTo=${encodeURIComponent(returnTo)}`
    : "";
  redirect(`/dashboard${safeReturnTo}`);
}
