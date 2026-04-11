# Story 4.8: Category Spending Breakdown

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want to see my spending broken down by category from all my cumulative data,
So that I understand my spending distribution.

## Acceptance Criteria

1. **Given** a user has categorized transactions from one or more uploads, **When** they view the spending breakdown section, **Then** they see a visual breakdown of spending by category (donut chart with legend) with amounts in the user's local currency format.

2. **Given** the category breakdown, **When** it is displayed, **Then** categories are sorted by amount (highest first), amounts are displayed in hryvnias (converted from kopiykas), and the visualization meets WCAG 2.1 AA standards.

3. **Given** the spending breakdown on mobile, **When** the user views it, **Then** the layout is responsive, touch-friendly, and legible in portrait orientation.

4. **Given** the profile page components, **When** data is fetching, **Then** TanStack Query manages all requests with proper loading skeletons and error boundaries.

## Tasks / Subtasks

- [x] Task 1: Backend — Add dedicated category breakdown endpoint (AC: #1, #2)
  - [x] 1.1 Add `get_category_breakdown()` async function to `profile_service.py` — query `category_totals` from financial profile, compute percentages, sort by absolute amount descending
  - [x] 1.2 Add Pydantic response models (`CategoryBreakdownItem`, `CategoryBreakdownResponse`) to `profile.py` with `alias_generator=to_camel`
  - [x] 1.3 Add `GET /api/v1/profile/category-breakdown` endpoint returning sorted categories with amounts (positive kopiykas), percentages, and count; return `null` when no profile exists
  - [x] 1.4 Write backend service tests: breakdown with multiple categories, single category, empty profile, null categories → "uncategorized", percentage calculation, sort order, tenant isolation
  - [x] 1.5 Write backend API tests: 200 with camelCase fields, 200 with null for missing profile, 401 without auth

- [x] Task 2: Frontend — Create `CategoryBreakdown` component with donut chart (AC: #1, #2, #3)
  - [x] 2.1 Add `CategoryBreakdownItem` and `CategoryBreakdown` TypeScript interfaces to `types.ts`
  - [x] 2.2 Create `use-category-breakdown.ts` hook in `hooks/` — TanStack Query with queryKey `["category-breakdown"]`, staleTime 5 minutes
  - [x] 2.3 Create `CategoryBreakdown.tsx` in `components/` — SVG donut chart (no external library) with a sorted legend list showing category name, amount (hryvnias), and percentage
  - [x] 2.4 Implement accessible donut chart: distinct colors per category, `aria-label` on SVG, `role="img"`, `<title>` and `<desc>` elements, text labels alongside color (not color-only)
  - [x] 2.5 Add responsive layout: donut + legend side-by-side on desktop (sm+), stacked vertically on mobile

- [x] Task 3: Frontend — Integrate into ProfilePage and replace existing basic list (AC: #1, #4)
  - [x] 3.1 Replace the existing basic `categories` list block in `ProfilePage.tsx` (lines 194-218) with the new `CategoryBreakdown` component
  - [x] 3.2 Add loading skeleton state for the breakdown section
  - [x] 3.3 Add error state with `t("categoryBreakdown.loadFailed")` message
  - [x] 3.4 Add empty/no-data state with encouraging message

- [x] Task 4: i18n — Add translation keys (AC: #1)
  - [x] 4.1 Add `profile.categoryBreakdown.*` keys to `en.json` (`title`, `noData`, `loadFailed`, `uncategorized`, `percentOfTotal`)
  - [x] 4.2 Add matching Ukrainian translations to `uk.json`

- [x] Task 5: Frontend tests (AC: #1, #2, #3, #4)
  - [x] 5.1 Create `CategoryBreakdown.test.tsx` — renders donut SVG + legend, categories sorted by amount, amounts in hryvnias, percentage display, uncategorized label, accessible SVG attributes
  - [x] 5.2 Add ProfilePage integration tests — breakdown section renders when data available, loading skeleton, error state, empty/no-data state
  - [x] 5.3 Verify all existing ProfilePage tests still pass (no regressions from replacing the basic list)

## Dev Notes

### Scope Summary

- Full-stack story: new backend service function + API endpoint, new frontend component with SVG donut chart
- **No new database tables or migrations** — the `category_totals` JSONB field in `financial_profiles` already stores all-time per-category totals from `build_or_update_profile()`
- **No external charting library** — follow the established "custom SVG" philosophy from Stories 4.5 (HealthScoreRing) and 4.6 (HealthScoreTrend)
- **Replaces existing basic list** — ProfilePage.tsx lines 194-218 currently render a simple `<ul>` from `profile.categoryTotals`; this story upgrades it to a proper visual breakdown component

### Architecture Compliance

- **Database:** No schema changes. Data source is `FinancialProfile.category_totals` (JSONB dict mapping category name → kopiykas amount). Already populated by `build_or_update_profile()` in `profile_service.py`
- **API:** New endpoint `GET /api/v1/profile/category-breakdown` (kebab-case). Return `200` with `null` for missing profile (not 404) — follows monthly-comparison pattern
- **Backend patterns:** Async `get_category_breakdown()` in existing `profile_service.py`. Follows the async query pattern from `get_monthly_comparison()` and `get_profile_for_user()`
- **Frontend patterns:** New component in `features/profile/components/`. New hook in `features/profile/hooks/`. TanStack Query for data fetching. i18n via next-intl. Tailwind CSS. No custom CSS files
- **Naming:** Component `CategoryBreakdown.tsx` (PascalCase), hook `use-category-breakdown.ts` (kebab-case), service function `get_category_breakdown` (snake_case), endpoint `/category-breakdown` (kebab-case)
- **Currency:** All amounts stored as integer kopiykas. Display via `formatCurrency()` from `features/profile/format.ts` (shared utility extracted in Story 4.7)
- **JSON response:** `camelCase` via Pydantic `alias_generator=to_camel`

### Backend Implementation Notes

The `FinancialProfile.category_totals` field is a JSON dict like:
```json
{
  "groceries": -25000,
  "dining_out": -18500,
  "transport": -12000,
  "uncategorized": -5000,
  "salary": 150000
}
```

Key considerations:
- **Filter expenses only** — `category_totals` contains both income (positive) and expenses (negative). The breakdown should only show expense categories (negative amounts)
- **Convert to positive kopiykas** — use `abs()` for display amounts
- **Compute percentages** — each category's share of total expenses
- **Sort by absolute amount descending** — biggest spending categories first
- **Null category handling** — already mapped to `"uncategorized"` string by `build_or_update_profile()`
- **Alternative approach:** Could read directly from `category_totals` field on the existing profile rather than re-querying transactions. This is simpler and faster since the data is already materialized. If the endpoint chooses to use the existing `/profile` data, a separate endpoint may not be needed — the frontend component can derive the breakdown from the profile response. **Dev should decide the simplest correct approach.**

### Frontend Implementation Notes

**Donut Chart (SVG):**
- Use SVG `<circle>` elements with `stroke-dasharray` and `stroke-dashoffset` to create donut segments (same technique as HealthScoreRing)
- Each category gets a segment proportional to its percentage
- Center of donut can show total expenses amount
- Use a predefined color palette (8-10 distinct colors) — ensure sufficient contrast for WCAG AA
- `prefers-reduced-motion`: skip entrance animations

**Legend:**
- Rendered alongside (desktop) or below (mobile) the donut
- Each row: color swatch + category name + amount (hryvnias) + percentage
- Sorted by amount descending (matching donut segment order, clockwise from top)

**Accessibility:**
- SVG: `role="img"`, `aria-label` with summary text (e.g., "Spending breakdown: Groceries 26%, Dining 19%...")
- `<title>` and `<desc>` elements inside SVG
- Legend provides text representation of all data (not color-dependent)
- Color palette should have 3:1 minimum contrast ratio between adjacent segments

**Responsive:**
- `sm:` breakpoint: donut (left) + legend (right) side-by-side using `flex`
- Below `sm`: donut above, legend below (stacked)
- Donut size: ~160px diameter mobile, ~200px desktop

### Previous Story Intelligence (from Story 4.7)

- `formatCurrency()` is in `features/profile/format.ts` — reuse it, do not duplicate
- `use-monthly-comparison.ts` hook pattern: TanStack Query with `queryKey`, `staleTime: 5 * 60 * 1000`, type-safe return object — follow same pattern
- ProfilePage error handling pattern: `isError` must be consumed and displayed (bug found in 4.7 review — API errors were silently masked as "no data")
- Cross-year boundary SQL bug was found in 4.7 — not relevant to this story (no date filtering) but shows the value of thorough test cases
- Test count baseline after 4.7: all backend + frontend tests pass

### Git Intelligence (Recent Commits)

Last 5 commits are all Epic 4 stories (4.3-4.7). Patterns:
- Files modified: `profile_service.py`, `profile.py` (API), `ProfilePage.tsx`, `types.ts`, `en.json`, `uk.json`
- Test files: `test_profile_service.py`, `test_profile_api.py`, `ProfilePage.test.tsx`
- New components follow: `features/profile/components/{Component}.tsx` + `features/profile/__tests__/{Component}.test.tsx`
- New hooks follow: `features/profile/hooks/use-{name}.ts`
- No new dependencies added in recent stories

### Project Structure Notes

- Alignment with unified project structure: all files go in `features/profile/` subtree
- Backend service additions go in existing `profile_service.py`
- Backend API additions go in existing `profile.py` (router prefix `/profile`)
- Backend tests: `test_profile_service.py` and `test_profile_api.py`
- Frontend tests: co-located in `features/profile/__tests__/`

### References

- [Source: backend/app/services/profile_service.py] — `build_or_update_profile()` computes `category_totals`; `get_monthly_comparison()` for async service pattern
- [Source: backend/app/api/v1/profile.py] — existing profile + monthly-comparison endpoints; Pydantic response model pattern
- [Source: backend/app/models/financial_profile.py] — `category_totals: dict[str, Any]` JSONB field
- [Source: frontend/src/features/profile/components/ProfilePage.tsx#L194-L218] — existing basic category list to replace
- [Source: frontend/src/features/profile/components/HealthScoreRing.tsx] — SVG donut/ring pattern reference
- [Source: frontend/src/features/profile/format.ts] — shared `formatCurrency()` utility
- [Source: frontend/src/features/profile/types.ts] — existing type definitions
- [Source: frontend/src/features/profile/hooks/use-monthly-comparison.ts] — TanStack Query hook pattern reference
- [Source: _bmad-output/planning-artifacts/epics.md#Epic4-Story4.8] — Original story requirements
- [Source: _bmad-output/planning-artifacts/architecture.md] — Tech stack, API patterns, DB schemas
- [Source: frontend/AGENTS.md] — CRITICAL: Next.js 16.1 has breaking changes; dev MUST read `node_modules/next/dist/docs/` before writing code

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

None — clean implementation with no blocking issues.

### Completion Notes List

- **Task 1 (Backend):** Added `get_category_breakdown()` async function to `profile_service.py` that reads from materialized `category_totals` JSONB field, filters expenses only, computes percentages, sorts by amount desc. Added `CategoryBreakdownItem` and `CategoryBreakdownResponse` Pydantic models with camelCase aliases. Added `GET /api/v1/profile/category-breakdown` endpoint returning `null` for missing profile. 8 new service tests + 3 new API tests all pass.
- **Task 2 (Frontend Component):** Created `CategoryBreakdown.tsx` with custom SVG donut chart using `stroke-dasharray` segments (same technique as HealthScoreRing). Legend shows category name, amount (hryvnias via `formatCurrency`), and percentage. Accessible: `role="img"`, `aria-label`, `<title>`, `<desc>`, color swatches with text labels. Responsive: side-by-side on `sm+`, stacked on mobile.
- **Task 3 (Integration):** Replaced basic `<ul>` category list in ProfilePage.tsx (lines 194-218) with new `CategoryBreakdown` component. Added loading skeleton, error state, and empty/no-data state with encouraging message.
- **Task 4 (i18n):** Added `profile.categoryBreakdown.*` nested keys (title, noData, loadFailed, uncategorized, percentOfTotal, ariaLabel) to both `en.json` and `uk.json`. Migrated from flat string to nested structure.
- **Task 5 (Tests):** Created `CategoryBreakdown.test.tsx` with 9 tests (SVG rendering, accessibility, legend, currency formatting, percentages, empty state). Updated `ProfilePage.test.tsx` with mock for `useCategoryBreakdown` hook and 3 new integration tests (loading, error, empty states). All 56 frontend profile tests pass, 249 total frontend tests pass, 328 backend tests pass — zero regressions.

### Change Log

- 2026-04-09: Story 4.8 implementation complete — Category Spending Breakdown with SVG donut chart, backend endpoint, and comprehensive tests.
- 2026-04-09: Code review fixes applied — removed dead `count` field from API/types, removed dead `offset` variable and empty-state dead code from component, made donut chart responsive (160px mobile / 200px desktop), fixed i18n for "uncategorized" label (was showing raw English string to Ukrainian users).

### File List

**New files:**
- frontend/src/features/profile/components/CategoryBreakdown.tsx
- frontend/src/features/profile/hooks/use-category-breakdown.ts
- frontend/src/features/profile/__tests__/CategoryBreakdown.test.tsx

**Modified files:**
- backend/app/services/profile_service.py — added `get_category_breakdown()` function
- backend/app/api/v1/profile.py — added response models and `/category-breakdown` endpoint
- backend/tests/test_profile_service.py — added `TestGetCategoryBreakdown` test class (8 tests)
- backend/tests/test_profile_api.py — added `TestCategoryBreakdownEndpoint` test class (3 tests)
- frontend/src/features/profile/types.ts — added `CategoryBreakdownItem` and `CategoryBreakdown` interfaces
- frontend/src/features/profile/components/ProfilePage.tsx — replaced basic category list with new component + states
- frontend/src/features/profile/__tests__/ProfilePage.test.tsx — added breakdown hook mock + 3 integration tests
- frontend/messages/en.json — added `profile.categoryBreakdown.*` nested keys
- frontend/messages/uk.json — added matching Ukrainian translations
