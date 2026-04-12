# Story 5.3: Financial Advice Disclaimer

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want to see a clear disclaimer that this product provides education and insights, not financial advice,
So that I understand the nature of the service.

## Acceptance Criteria

1. **Given** I am going through onboarding, **When** I reach the appropriate step, **Then** I see a financial advice disclaimer: "This product provides financial insights and education, not financial advice"
2. **Given** the Teaching Feed screen, **When** I view insight cards, **Then** a subtle but visible disclaimer is accessible (e.g., info icon or footer text) reminding users this is education, not advice
3. **Given** the disclaimer, **When** it is displayed, **Then** it is available in both Ukrainian and English matching the user's language preference

## Tasks / Subtasks

- [x] Task 1: Add disclaimer section to onboarding privacy screen (AC: #1, #3)
  - [x] 1.1 Add a "Financial Advice Disclaimer" section to `PrivacyExplanationScreen.tsx` — a new topic section below the existing four privacy topics, visually distinct (e.g., different icon or border color) to signal it is a legal notice, not a data-use explanation
  - [x] 1.2 Add i18n keys under `onboarding.privacy.disclaimer.*` namespace in `frontend/messages/en.json` and `frontend/messages/uk.json` (title + body keys)
  - [x] 1.3 Add i18n smoke tests for the new disclaimer keys (extend existing `consent-i18n.test.ts`)

- [x] Task 2: Add persistent disclaimer to Teaching Feed screen (AC: #2, #3)
  - [x] 2.1 Create `frontend/src/features/teaching-feed/components/FeedDisclaimer.tsx` — a subtle footer/info-bar component below the card stack with an info icon and short disclaimer text; tapping/clicking reveals full text via a Tooltip or expandable section
  - [x] 2.2 Integrate `FeedDisclaimer` into `FeedContainer.tsx` — render it below the `CardStackNavigator` (before the streaming indicator), visible whenever cards are present
  - [x] 2.3 Add i18n keys under `feed.disclaimer.*` namespace in both locale files (short text + full text)
  - [x] 2.4 Write component test for `FeedDisclaimer.tsx` — renders correctly, tooltip/expand interaction works, i18n keys resolve

- [x] Task 3: Tests & regression (AC: #1, #2, #3)
  - [x] 3.1 Update `PrivacyExplanationScreen.test.tsx` to assert the disclaimer section renders
  - [x] 3.2 Update `FeedContainer.test.tsx` to assert `FeedDisclaimer` renders when cards are present and does NOT render in empty/loading/error states
  - [x] 3.3 Run full frontend test suite — confirm green

## Dev Notes

### Architecture & Patterns

- **This is a frontend-only story.** No backend changes, no new API endpoints, no database migrations. The disclaimer is static UI content served via i18n, not a consent record. Story 5.2 already established the `consent_type` column with future types in mind — if a future requirement needs consent tracking for the disclaimer, it's a separate story.
- **Onboarding screen pattern:** `PrivacyExplanationScreen.tsx` already renders topic sections from an array of `{ titleKey, bodyKey }` objects. Add a new entry to this array for the disclaimer. Consider visually distinguishing it (e.g., a subtle border or info icon) since it serves a different purpose (legal notice vs. data explanation).
- **Teaching Feed pattern:** `FeedContainer.tsx` renders `CardStackNavigator` inside a `flex flex-col gap-4` container. The disclaimer should be a new sibling component below the card stack. Use shadcn/ui `Tooltip` or a collapsible section for the full text — keep the default view compact (one line + info icon).
- **i18n conventions:** Follow the established pattern: `namespace.section.key`. Use `onboarding.privacy.disclaimer.*` for onboarding and `feed.disclaimer.*` for the feed. Both `en.json` and `uk.json` must be updated in tandem.
- **Component naming:** `FeedDisclaimer.tsx` in `features/teaching-feed/components/` follows the feature-based folder structure.
- **Styling:** Use Tailwind utility classes with existing design tokens (`text-muted-foreground`, `text-foreground/60`, etc.). Do NOT introduce new colors or design tokens. Use `shadcn/ui` components (Tooltip, Button) where appropriate.

### Key Files to Touch

**New files:**
- `frontend/src/features/teaching-feed/components/FeedDisclaimer.tsx` — Feed disclaimer component
- `frontend/src/features/teaching-feed/__tests__/FeedDisclaimer.test.tsx` — Tests

**Modified files:**
- `frontend/src/features/onboarding/components/PrivacyExplanationScreen.tsx` — Add disclaimer topic section
- `frontend/src/features/teaching-feed/components/FeedContainer.tsx` — Integrate FeedDisclaimer
- `frontend/messages/en.json` — Add `onboarding.privacy.disclaimer.*` and `feed.disclaimer.*` keys
- `frontend/messages/uk.json` — Add matching Ukrainian translations
- `frontend/src/features/onboarding/__tests__/PrivacyExplanationScreen.test.tsx` — Assert disclaimer renders
- `frontend/src/features/onboarding/__tests__/consent-i18n.test.ts` — Add disclaimer keys to smoke test
- `frontend/src/features/teaching-feed/__tests__/FeedContainer.test.tsx` — Assert FeedDisclaimer integration

### Disclaimer Copy (English)

- **Onboarding section title:** "Financial Advice Disclaimer"
- **Onboarding section body:** "kōpiika provides financial insights and education based on your uploaded bank statements. This is not professional financial advice. Always consult a qualified financial advisor for decisions about investments, debt, or major financial commitments."
- **Feed short text:** "Educational insights only — not financial advice"
- **Feed full text (tooltip/expanded):** "kōpiika provides financial insights and education, not professional financial advice. Consult a qualified advisor for financial decisions."

### Disclaimer Copy (Ukrainian)

- **Onboarding section title:** "Застереження щодо фінансових порад"
- **Onboarding section body:** "kōpiika надає фінансові інсайти та освітній контент на основі ваших банківських виписок. Це не є професійною фінансовою порадою. Завжди консультуйтеся з кваліфікованим фінансовим радником щодо рішень про інвестиції, борги або великі фінансові зобов'язання."
- **Feed short text:** "Лише освітні інсайти — не фінансова порада"
- **Feed full text:** "kōpiika надає фінансові інсайти та освіту, а не професійні фінансові поради. Консультуйтеся з кваліфікованим радником щодо фінансових рішень."

### Previous Story Intelligence (5.2)

- **Detached ORM copy pattern** — not relevant here (no backend), but good to know for future stories.
- **Consent guard architecture** — `ConsentGuard` wraps all dashboard routes; onboarding routes are excluded. The disclaimer in onboarding is just additional UI content within the existing `PrivacyExplanationScreen`, no guard changes needed.
- **Testing patterns:** vitest + @testing-library/react, mock fetch + useRouter. Follow the same patterns for new component tests.
- **DashboardSkeleton** — shared loading component, not relevant to this story.
- **i18n key format:** hierarchical dot-separated keys, 14 keys added per namespace in Story 5.2. Follow same pattern.

### Git Intelligence

- Recent commits follow pattern: "Story X.Y: Title"
- Story 5.2 was the last commit — direct predecessor, same epic
- No in-progress work or conflicts expected

### Testing Standards

- **Component tests:** Co-located in `__tests__/` folders within feature directories
- **i18n smoke tests:** Key × locale matrix assertions (fail fast on missing translations)
- **Run commands:**
  - `cd frontend && pnpm test -- FeedDisclaimer` (new component)
  - `cd frontend && pnpm test -- PrivacyExplanation` (updated component)
  - `cd frontend && pnpm test -- consent-i18n` (updated smoke test)
  - `cd frontend && pnpm test -- FeedContainer` (integration)
  - `cd frontend && pnpm test` (full regression)

### Project Structure Notes

- Alignment with unified project structure: feature-based folders under `features/`, tests co-located in `__tests__/`
- No detected conflicts or variances

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 5, Story 5.3]
- [Source: _bmad-output/planning-artifacts/prd.md — FR36, Compliance & Regulatory section]
- [Source: _bmad-output/planning-artifacts/architecture.md — Consent Management, Frontend Structure]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md — Trust-first model, education product positioning]
- [Source: _bmad-output/implementation-artifacts/5-2-privacy-explanation-consent-during-onboarding.md — Previous story patterns, file list, i18n conventions]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

None — clean implementation, no debug issues encountered.

### Completion Notes List

- Added financial advice disclaimer section to onboarding privacy screen with amber border styling and legal icon to visually distinguish from data-use explanations
- Created FeedDisclaimer component with expandable info-bar pattern (no Tooltip component available in shadcn/ui, used state-based expand/collapse instead)
- Added i18n keys for both English and Ukrainian in both onboarding.privacy.disclaimer.* and feed.disclaimer.* namespaces
- Extended consent-i18n smoke tests (28→32 assertions) to cover new disclaimer keys
- Added 4 new FeedDisclaimer component tests and 4 new FeedContainer integration tests
- Full test suite: 31 files, 305 tests, all passing, zero regressions (6 new i18n smoke tests added during code review)

### Change Log

- 2026-04-12: Story 5.3 implemented — financial advice disclaimer added to onboarding and teaching feed
- 2026-04-12: Code review fixes — replaced inline SVG with lucide-react Info icon, replaced emoji with lucide-react Scale icon, i18n'd aria-label, added feed.disclaimer i18n smoke tests (6 new assertions), switched integration tests to data-testid selectors

### File List

**New files:**
- frontend/src/features/teaching-feed/components/FeedDisclaimer.tsx
- frontend/src/features/teaching-feed/__tests__/FeedDisclaimer.test.tsx

**Modified files:**
- frontend/src/features/onboarding/components/PrivacyExplanationScreen.tsx
- frontend/src/features/teaching-feed/components/FeedContainer.tsx
- frontend/messages/en.json
- frontend/messages/uk.json
- frontend/src/features/onboarding/__tests__/PrivacyExplanationScreen.test.tsx
- frontend/src/features/onboarding/__tests__/consent-i18n.test.ts
- frontend/src/features/teaching-feed/__tests__/FeedContainer.test.tsx
