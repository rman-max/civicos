# CivicOS design system

## Purpose

The CivicOS interface should feel like a well-edited public notebook: calm, direct, and easy to read for a long time. The system uses only black, white, and grey. Hierarchy comes from type, spacing, and rules—not color, gradients, shadows, or ornamental surfaces.

The front-end implementation lives in `frontend/src/components/`. Components use only React, Next.js, and Tailwind; the system adds no UI-library dependency.

## Foundations

### Colors

| Token | Value | Use |
|---|---|---|
| `canvas` | `#ffffff` | default page background |
| `surface` | `#f7f7f7` | restrained secondary surface |
| `ink` | `#171717` | primary text, rules, primary action |
| `ink-muted` | `#5c5c5c` | supporting text only |
| `rule` | `#dedede` | dividers and grouped boundaries |
| `rule-strong` | `#ababab` | controls and stronger separation |

Do not introduce semantic color, gradients, transparency effects, shadows, or color-only status meaning. Where a state needs distinction, pair clear text and structure with the neutral treatment.

### Typography

| Role | Family | Tailwind implementation | Use |
|---|---|---|---|
| Interface text | system sans | `font-sans` | navigation, labels, controls, metadata |
| Editorial text | system serif | `font-serif` | page titles, section headings, long-form record context |
| Eyebrow | system sans | `Eyebrow` | compact categorization, never body copy |
| Display title | system serif | `PageTitle` | one per page |
| Section heading | system serif | `SectionHeading` | content landmarks |
| Reading copy | system serif | `civicos-prose` | summaries and source context |

Use normal/medium weights only. Body text starts at 16px; reading text uses 18px with a generous line height. Avoid all-caps except short eyebrows. Do not use a display title for a simple label.

### Spacing and rules

- Use Tailwind’s 4px spacing scale. Default page padding is 20px, then 32px at `sm` and 48px at `lg`.
- Maintain a maximum 768px reading column with `ContentColumn`; wide tables and evidence grids may opt into `PageContainer`.
- Prefer a single 1px rule to separate related content. Use whitespace before adding another container.
- Keep interactive targets at least 40px tall. Do not rely on hover alone for meaning.

## Layout rules

1. Put content inside `AppFrame`, then `PageContainer`; use `ContentColumn` for reading-oriented pages.
2. Begin pages with an optional `Eyebrow`, exactly one `PageTitle`, and a concise summary when context is needed.
3. Use a `SectionHeading` for each major landmark. Avoid cards within cards.
4. Use `Card` only to create a direct grouping. It has no radius or shadow; use a surrounding rule/grid when separation is required.
5. Present evidence close to the claim it supports. Metadata should be quieter, but never hidden behind ambiguous icons.
6. Test at 320px, 768px, and wide desktop widths. Dense data may scroll horizontally only when a responsive reflow would lose meaning.

## Navigation patterns

### Primary navigation

`SiteHeader` uses the CivicOS wordmark and `NavigationList`. Navigation labels use plain nouns. The active destination receives both `aria-current="page"` and a visible bottom rule.

Keep primary navigation deliberately small. Add a new top-level destination only when it represents a sustained user goal, not a single action or data type.

### Context navigation

Use `Breadcrumbs` when a user needs to understand an item’s location in a record hierarchy. The final item is plain text with `aria-current="page"`; ancestors are links. Do not use breadcrumbs as a replacement for a page title.

### Actions

- `Button` `primary`: one highest-emphasis action per local context.
- `Button` `secondary`: related but lower-emphasis action.
- `Button` `quiet`: adjacent or utility action; it remains visibly interactive through text and focus treatment.

Write action labels as verbs: “Save search,” “View source,” “Export evidence.” Avoid vague labels such as “Submit” or “Click here.”

## Components

| Component | Responsibility | Accessibility behavior |
|---|---|---|
| `AppFrame` | application shell and standard header | establishes consistent page structure |
| `PageContainer` / `ContentColumn` | responsive outer and reading widths | semantic `main` landmark on `PageContainer` |
| `SiteHeader` / `NavigationList` | site identity and primary navigation | labeled `nav`, active item exposes `aria-current` |
| `Breadcrumbs` | hierarchy path | labeled `nav`, current item exposes `aria-current` |
| `Eyebrow`, `PageTitle`, `SectionHeading` | semantic editorial hierarchy | preserve native heading levels |
| `Button` | neutral action variants | native button, keyboard/focus/disabled behavior preserved |
| `TextInput` | labeled text entry with hint/error support | explicit label, `aria-describedby`, `aria-invalid` |
| `Card` | quiet content grouping | no implied interactivity; wrap with an appropriate element when needed |
| `Notice` | important contextual or system guidance | `aside` landmark; title is visible text |

### Component usage

```tsx
<TextInput
  id="search"
  label="Search civic records"
  hint="Use a body name, topic, or document title."
  placeholder="e.g., county council agenda"
/>

<Notice title="Source availability">
  This record is based on the latest published county agenda.
</Notice>
```

## Accessibility and content rules

- Use native semantic elements before custom behavior. New interactive patterns require keyboard behavior, focus management, and an accessibility test plan.
- Keep focus indicators visible. Never suppress browser focus without a clear replacement.
- Every input has a visible label; every icon-only control needs an accessible name.
- Do not encode urgency, completeness, or success by color. State must be readable in text.
- Use direct, neutral language. Clearly distinguish a CivicOS summary from quoted or linked official material.
- Keep source title, publisher/body, and relevant dates readable without hover or JavaScript.

## Change policy

Add a component only after confirming that an existing primitive cannot compose the need. Component changes that alter accessibility behavior, the visual tokens, or navigation patterns require a design-system documentation update and appropriate frontend checks.

