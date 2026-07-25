import { PageContainer } from "@/components/layout/page-container";
import { PageHeader } from "@/components/layout/page-header";
import { Breadcrumbs } from "@/components/navigation/breadcrumbs";
import { RecordSearch } from "@/components/search/record-search";

export default function SearchPage() {
  return (
    <PageContainer className="py-12 sm:py-16">
      <Breadcrumbs items={[{ href: "/dashboard", label: "Dashboard" }, { label: "Search" }]} />
      <PageHeader
        className="mt-8"
        description="Search the live St. Joseph County civic corpus. Every result retains its original public-source context."
        title="Search the record"
      />
      <RecordSearch />
    </PageContainer>
  );
}
