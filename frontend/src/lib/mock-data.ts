export interface ActivityItem {
  body: string;
  date: string;
  description: string;
  title: string;
  type: string;
}

export interface CivicRecord {
  body: string;
  date: string;
  excerpt: string;
  source: string;
  title: string;
  type: string;
}

export interface Collection {
  description: string;
  items: number;
  title: string;
  updated: string;
}

export interface Source {
  coverage: string;
  lastChecked: string;
  name: string;
  records: string;
  status: "Current" | "Needs review";
  type: string;
}

export interface ExampleNotebook {
  description: string;
  evidence: string;
  question: string;
  title: string;
  trail: string;
}

export const exampleNotebooks: ExampleNotebook[] = [
  {
    description: "Follow budget materials from departmental requests to a public hearing agenda.",
    evidence: "2 saved records · 1 highlight",
    question: "How are proposed capital priorities described in the county’s current budget materials?",
    title: "County budget research",
    trail: "County Council · County Auditor",
  },
  {
    description: "Connect planning case materials, public notices, and meeting dates around a development question.",
    evidence: "3 saved records · 2 highlights",
    question: "What has been published about the Northside corridor planning case?",
    title: "Northside corridor planning",
    trail: "Area Plan Commission · Public notices",
  },
  {
    description: "Trace a health-board question from an agenda packet to related public information.",
    evidence: "2 saved records · 1 open question",
    question: "Which public health issues are scheduled for the next board discussion?",
    title: "Community health watch",
    trail: "Health Department · Board of Health",
  },
];

export const dashboardMetrics = [
  { label: "Active sources", value: "24" },
  { label: "New records", value: "18" },
  { label: "Upcoming meetings", value: "6" },
  { label: "Saved research", value: "3" },
];

export const recentActivity: ActivityItem[] = [
  {
    body: "County Council",
    date: "Today, 9:12 AM",
    description: "Agenda packet published for the next regular meeting.",
    title: "Regular meeting agenda",
    type: "Meeting",
  },
  {
    body: "Area Plan Commission",
    date: "Yesterday",
    description: "New supporting documents were added to a zoning request.",
    title: "Zoning case: Northside corridor",
    type: "Planning",
  },
  {
    body: "County Auditor",
    date: "Jul 21",
    description: "The current budget summary was updated with a revised table.",
    title: "2027 budget working summary",
    type: "Finance",
  },
];

export const searchResults: CivicRecord[] = [
  {
    body: "County Council",
    date: "Jul 23, 2026",
    excerpt: "The agenda includes a first reading on the proposed capital improvement plan and a public hearing schedule.",
    source: "County Council agenda packet",
    title: "Regular meeting agenda — July 28",
    type: "Meeting",
  },
  {
    body: "County Auditor",
    date: "Jul 21, 2026",
    excerpt: "This working summary reflects departmental requests received through the most recent reporting period.",
    source: "Budget working papers",
    title: "2027 budget working summary",
    type: "Finance",
  },
  {
    body: "Board of Commissioners",
    date: "Jul 18, 2026",
    excerpt: "A notice of public meeting was posted with materials related to roadway maintenance and procurement.",
    source: "Commissioners notice board",
    title: "Public notice and meeting materials",
    type: "Notice",
  },
];

export const collections: Collection[] = [
  {
    description: "Agendas, notices, and related plans for movement across the county.",
    items: 28,
    title: "Transportation and infrastructure",
    updated: "Updated today",
  },
  {
    description: "Budget materials, public hearings, and departmental working documents.",
    items: 16,
    title: "2027 county budget",
    updated: "Updated Jul 21",
  },
  {
    description: "Planning cases, public notices, and supporting documents for the Northside corridor.",
    items: 11,
    title: "Northside corridor planning",
    updated: "Updated Jul 18",
  },
];

export const timelineItems: ActivityItem[] = [
  {
    body: "County Council",
    date: "Jul 28 · 6:00 PM",
    description: "Regular meeting; agenda packet is available for review.",
    title: "County Council regular meeting",
    type: "Upcoming",
  },
  {
    body: "Board of Commissioners",
    date: "Jul 24 · 9:00 AM",
    description: "Public meeting regarding roadway maintenance and procurement materials.",
    title: "Commissioners public meeting",
    type: "Upcoming",
  },
  {
    body: "Area Plan Commission",
    date: "Jul 22",
    description: "Supporting materials added to the Northside corridor case record.",
    title: "Zoning case materials updated",
    type: "Published",
  },
  {
    body: "County Auditor",
    date: "Jul 21",
    description: "Revised working summary added to the fiscal-year record.",
    title: "Budget working summary published",
    type: "Published",
  },
];

export const sources: Source[] = [
  {
    coverage: "Agendas, minutes, packets",
    lastChecked: "8 minutes ago",
    name: "County Council",
    records: "342 records",
    status: "Current",
    type: "Official website",
  },
  {
    coverage: "Notices, agendas, resolutions",
    lastChecked: "16 minutes ago",
    name: "Board of Commissioners",
    records: "527 records",
    status: "Current",
    type: "Official website",
  },
  {
    coverage: "Planning cases and documents",
    lastChecked: "2 hours ago",
    name: "Area Plan Commission",
    records: "185 records",
    status: "Needs review",
    type: "Public records portal",
  },
  {
    coverage: "Budget and financial records",
    lastChecked: "Yesterday",
    name: "Indiana Gateway",
    records: "93 records",
    status: "Current",
    type: "State data portal",
  },
];
