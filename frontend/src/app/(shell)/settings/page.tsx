import { PageContainer } from "@/components/layout/page-container";
import { PageHeader } from "@/components/layout/page-header";
import { Breadcrumbs } from "@/components/navigation/breadcrumbs";
import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
import { TextInput } from "@/components/ui/text-input";
import { SectionHeading } from "@/components/ui/typography";

export default function SettingsPage() {
  return (
    <PageContainer className="py-12 sm:py-16">
      <Breadcrumbs items={[{ href: "/dashboard", label: "Dashboard" }, { label: "Settings" }]} />
      <PageHeader
        className="mt-8"
        description="Mock controls for personal research preferences and jurisdiction context. Changes are not persisted."
        title="Settings"
      />

      <div className="mt-10 grid gap-12 lg:grid-cols-[minmax(0,1fr)_19rem]">
        <div className="space-y-12">
          <section aria-labelledby="profile-heading">
            <SectionHeading id="profile-heading">Profile</SectionHeading>
            <div className="mt-6 grid gap-6 sm:grid-cols-2">
              <TextInput defaultValue="CivicOS researcher" id="display-name" label="Display name" />
              <TextInput defaultValue="researcher@example.org" id="email" label="Email address" type="email" />
            </div>
          </section>

          <section aria-labelledby="research-heading">
            <SectionHeading id="research-heading">Research preferences</SectionHeading>
            <div className="mt-6 space-y-6">
              <TextInput
                defaultValue="St. Joseph County, Indiana"
                hint="The initial jurisdiction shown in this mock shell."
                id="jurisdiction"
                label="Default jurisdiction"
              />
              <fieldset className="border-y border-rule py-5">
                <legend className="text-sm font-medium text-ink">Update cadence</legend>
                <label className="mt-3 flex items-start gap-3 text-sm leading-6 text-ink-muted">
                  <input className="mt-1 size-4 accent-black" defaultChecked type="checkbox" />
                  Include newly published records in the dashboard overview.
                </label>
              </fieldset>
              <Button>Save mock preferences</Button>
            </div>
          </section>
        </div>

        <aside className="border-t border-rule pt-6 lg:border-t-0 lg:border-l lg:pl-8 lg:pt-0">
          <Notice title="No account data yet">
            Authentication and persisted preferences are intentionally outside this frontend-shell milestone.
          </Notice>
        </aside>
      </div>
    </PageContainer>
  );
}

