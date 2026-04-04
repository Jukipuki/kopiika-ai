# Story 3.5: Teaching Feed Card UI & Progressive Disclosure

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want to view financial insights as cards with expandable education layers,
So that I can quickly scan headlines and dive deeper when interested.

## Acceptance Criteria

1. **Given** I am on the Teaching Feed screen, **When** insights are loaded, **Then** I see a card-based feed with each card showing: triage severity indicator (color + icon + text), headline fact, and key metric

2. **Given** I view an insight card, **When** I tap/click to expand it, **Then** the "why this matters" layer is revealed with a smooth animation

3. **Given** I have expanded the first layer, **When** I tap/click to expand further, **Then** the "deep-dive" education layer is revealed with progressive disclosure

4. **Given** I have expanded layers, **When** I tap/click to collapse, **Then** layers collapse smoothly back to the headline view

5. **Given** the Teaching Feed is rendered, **When** I inspect the UI, **Then** cards use shadcn/ui Card primitives, severity colors have icon+text fallback (not color alone), and all elements meet WCAG 2.1 AA compliance

6. **Given** the feed data is fetched, **When** TanStack Query manages the request, **Then** loading states show skeleton cards (shadcn/ui Skeleton) and errors are caught by the feature error boundary

## Tasks / Subtasks

- [x] Task 1: Create `types.ts` — Teaching Feed TypeScript types (AC: #1, #2, #3)
  - [x] 1.1 Create `frontend/src/features/teaching-feed/types.ts` — define `InsightCard` interface matching the `GET /api/v1/insights` camelCase response: `id`, `uploadId`, `headline`, `keyMetric`, `whyItMatters`, `deepDive`, `severity` (union: `"high" | "medium" | "low"`), `category`, `createdAt`
  - [x] 1.2 Define `InsightListResponse` type: `{ items: InsightCard[]; total: number; nextCursor: string | null; hasMore: boolean }`
  - [x] 1.3 Define `SeverityLevel = "high" | "medium" | "low"` as a named type export

- [x] Task 2: Create `use-teaching-feed.ts` — TanStack Query hook (AC: #1, #6)
  - [x] 2.1 Create `frontend/src/features/teaching-feed/hooks/use-teaching-feed.ts`
  - [x] 2.2 Implement `useTeachingFeed()` hook using `useQuery` from `@tanstack/react-query` with `queryKey: ["teaching-feed"]`
  - [x] 2.3 Fetch from `GET ${API_URL}/api/v1/insights` (no cursor for initial load — cursor pagination is Story 3.7's SSE integration scope)
  - [x] 2.4 Pass `Authorization: Bearer ${session?.accessToken}` header using `useSession` from `next-auth/react`
  - [x] 2.5 Return `{ data: InsightCard[], isLoading, isError, error }` — flatten `items` from `InsightListResponse` for simplicity at this stage
  - [x] 2.6 Set `staleTime: 5 * 60 * 1000` (5 minutes) — insights don't change frequently between uploads

- [x] Task 3: Create `TriageBadge.tsx` — Severity indicator component (AC: #1, #5)
  - [x] 3.1 Create `frontend/src/features/teaching-feed/components/TriageBadge.tsx`
  - [x] 3.2 Accept `severity: SeverityLevel` prop
  - [x] 3.3 Render icon + text + color: high → red/`🔴`/`"High Priority"`, medium → yellow/`🟡`/`"Medium"`, low → green/`🟢`/`"Low"`
  - [x] 3.4 Use Tailwind classes for color (not color alone — always pair with icon AND text label per WCAG 2.1 AA: `aria-label` on the badge)
  - [x] 3.5 Color classes: high → `bg-red-100 text-red-800`, medium → `bg-yellow-100 text-yellow-800`, low → `bg-green-100 text-green-800`

- [x] Task 4: Create `EducationLayer.tsx` — Progressive disclosure panels (AC: #2, #3, #4)
  - [x] 4.1 Create `frontend/src/features/teaching-feed/components/EducationLayer.tsx`
  - [x] 4.2 Accept props: `whyItMatters: string`, `deepDive: string`, `isExpanded: boolean`, `expandLevel: 0 | 1 | 2`
  - [x] 4.3 Level 0 (collapsed): show nothing extra
  - [x] 4.4 Level 1 (first expansion): show `whyItMatters` with `"Why this matters"` heading — animate in using Tailwind `transition-all duration-300`
  - [x] 4.5 Level 2 (second expansion): show both `whyItMatters` AND `deepDive` with `"Deep dive"` heading
  - [x] 4.6 Use CSS `max-height` transition for smooth collapse/expand (Tailwind `max-h-0 overflow-hidden` → `max-h-96`)
  - [x] 4.7 Do NOT install Framer Motion — that is Story 3.6's dependency. Use Tailwind CSS transitions only.

- [x] Task 5: Create `InsightCard.tsx` — Base card component (AC: #1–#5)
  - [x] 5.1 Create `frontend/src/features/teaching-feed/components/InsightCard.tsx`
  - [x] 5.2 Use shadcn/ui `Card`, `CardHeader`, `CardContent` from `@/components/ui/card`
  - [x] 5.3 Accept `insight: InsightCard` prop
  - [x] 5.4 Internal state: `expandLevel: 0 | 1 | 2` (useState), starts at 0
  - [x] 5.5 Layout: `TriageBadge` in header, `headline` as `<h3>`, `keyMetric` styled as prominent metric, expand button (`"Learn more"` / `"Deep dive"` / `"Collapse"`)
  - [x] 5.6 Expand button logic: level 0 → click → level 1; level 1 → click `"Deep dive"` → level 2; level 2 → click `"Collapse"` → level 0
  - [x] 5.7 Render `EducationLayer` with current `expandLevel`
  - [x] 5.8 Button: use shadcn/ui `Button` variant `"ghost"` with `size="sm"` — text changes per level: `"Learn why →"` (level 0), `"Go deeper →"` (level 1), `"← Collapse"` (level 2)
  - [x] 5.9 Add `aria-expanded` attribute to button for accessibility

- [x] Task 6: Create `FeedContainer.tsx` — Feed list with skeleton loading (AC: #1, #6)
  - [x] 6.1 Create `frontend/src/features/teaching-feed/components/FeedContainer.tsx`
  - [x] 6.2 Use `useTeachingFeed()` hook internally
  - [x] 6.3 Loading state: render 3 skeleton cards using `Skeleton` from `@/components/ui/skeleton` — mimic card structure height (~120px)
  - [x] 6.4 Error state: render a simple error message card with retry button (use `queryClient.invalidateQueries(["teaching-feed"])` for retry)
  - [x] 6.5 Empty state (no insights): render a friendly empty state — `"No insights yet. Upload a bank statement to get started."` with link to `/upload`
  - [x] 6.6 Success: render a `<ul>` of `InsightCard` components, each wrapped in `<li>` with `key={insight.id}`
  - [x] 6.7 Use `gap-4 flex flex-col` layout for card list

- [x] Task 7: Create feed page and loading skeleton (AC: #1, #6)
  - [x] 7.1 Create `frontend/src/app/[locale]/(dashboard)/feed/page.tsx` — Server Component that renders `<FeedContainer />`
  - [x] 7.2 Add metadata: `export const metadata = { title: "Teaching Feed | Kopiika" }`
  - [x] 7.3 Create `frontend/src/app/[locale]/(dashboard)/feed/loading.tsx` — renders same 3 skeleton cards as `FeedContainer` loading state for Next.js streaming

- [x] Task 8: Tests (AC: #1–#6)
  - [x] 8.1 Create `frontend/src/features/teaching-feed/__tests__/InsightCard.test.tsx` — test: renders headline, keyMetric, TriageBadge; clicking expand reveals whyItMatters; clicking again reveals deepDive; clicking again collapses
  - [x] 8.2 Create `frontend/src/features/teaching-feed/__tests__/TriageBadge.test.tsx` — test: all three severity levels render correct text+icon; aria-label present
  - [x] 8.3 Create `frontend/src/features/teaching-feed/__tests__/use-teaching-feed.test.tsx` — test: loading state, success state with data, error state; verifies Authorization header is sent
  - [x] 8.4 Create `frontend/src/features/teaching-feed/__tests__/FeedContainer.test.tsx` — test: skeleton shown during loading; error message shown on failure; insight cards rendered on success; empty state shown when items is []
  - [x] 8.5 All 15 existing frontend test files continue passing (19 total test files, 137 tests pass)

## Dev Notes

### Architecture Overview

This story creates the entire `teaching-feed` feature folder from scratch. There is NO existing `frontend/src/features/teaching-feed/` directory — create it. The feed page (`/feed`) also does not exist yet — create it under the `(dashboard)` route group.

**Story 3.5 scope boundary:**
- ✅ Card rendering, progressive disclosure (CSS transitions), TanStack Query data fetch, skeleton loading, error/empty states
- ❌ Framer Motion card stack gestures (Story 3.6)
- ❌ SSE-based progressive card appearance (Story 3.7)
- ❌ Cursor pagination / infinite scroll (Story 3.7 scope)

### API Integration

**Endpoint:** `GET ${API_URL}/api/v1/insights`

**Request headers:**
```typescript
Authorization: Bearer ${session?.accessToken}
```

**Response shape (camelCase from Story 3.4):**
```typescript
{
  items: Array<{
    id: string;            // UUID
    uploadId: string | null;
    headline: string;
    keyMetric: string;
    whyItMatters: string;
    deepDive: string;
    severity: "high" | "medium" | "low";
    category: string;
    createdAt: string;     // ISO 8601 UTC e.g. "2026-04-04T12:00:00.000000Z"
  }>;
  total: number;
  nextCursor: string | null;
  hasMore: boolean;
}
```

Items are pre-sorted by severity (high → medium → low) by the backend — **do not re-sort on frontend**.

### API_URL Pattern (Follow Upload Feature)

```typescript
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
```

Mirror exactly how `features/upload/hooks/use-upload.ts` and `use-job-status.ts` access the API.

### Auth Pattern (Follow Upload Feature)

```typescript
import { useSession } from "next-auth/react";

const { data: session } = useSession();
// Then pass:
headers: { Authorization: `Bearer ${session?.accessToken}` }
```

Only call the hook when `session?.accessToken` is available. TanStack Query's `enabled: !!session?.accessToken` prevents fetching before auth is ready.

### TanStack Query v5 Pattern

The project uses `@tanstack/react-query` v5 (`^5.95.2`). In v5, `useQuery` API changed:
- ✅ `useQuery({ queryKey: [...], queryFn: async () => ... })` — correct v5 API
- ❌ `useQuery(["key"], fn)` — this is v4 API, will NOT work

```typescript
import { useQuery } from "@tanstack/react-query";

export function useTeachingFeed() {
  const { data: session } = useSession();

  return useQuery({
    queryKey: ["teaching-feed"],
    queryFn: async (): Promise<InsightCard[]> => {
      const res = await fetch(`${API_URL}/api/v1/insights`, {
        headers: { Authorization: `Bearer ${session?.accessToken}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: InsightListResponse = await res.json();
      return data.items;
    },
    enabled: !!session?.accessToken,
    staleTime: 5 * 60 * 1000,
  });
}
```

### shadcn/ui Components Available

The following are already installed (verified in `frontend/src/components/ui/`):
- `card.tsx` → imports: `Card`, `CardHeader`, `CardContent`, `CardTitle`, `CardDescription`, `CardFooter`
- `skeleton.tsx` → imports: `Skeleton`
- `button.tsx` → imports: `Button`

Do NOT install new shadcn/ui components for this story — use only these. `badge.tsx` is NOT installed; implement severity badge with plain Tailwind `<span>` inside `TriageBadge.tsx` (no extra install needed).

### Progressive Disclosure Animation (CSS Only — No Framer Motion)

Framer Motion is NOT installed (`package.json` has no `framer-motion` or `motion`). Story 3.6 will add it for card stack gestures. For Story 3.5, use Tailwind CSS transitions:

```tsx
// EducationLayer.tsx — max-height transition pattern
<div
  className={cn(
    "overflow-hidden transition-all duration-300 ease-in-out",
    expandLevel >= 1 ? "max-h-96 opacity-100" : "max-h-0 opacity-0"
  )}
>
  {/* whyItMatters content */}
</div>
<div
  className={cn(
    "overflow-hidden transition-all duration-300 ease-in-out",
    expandLevel >= 2 ? "max-h-96 opacity-100" : "max-h-0 opacity-0"
  )}
>
  {/* deepDive content */}
</div>
```

`tw-animate-css` is installed (`^1.4.0`) as a Tailwind plugin if you need additional animation utilities, but the max-height transition pattern above is sufficient.

### Severity Color + Icon + Text (WCAG 2.1 AA)

**Critical:** Never use color alone to convey severity (accessibility requirement from epics AC). Always use icon + text + color together:

```tsx
const SEVERITY_CONFIG = {
  high: {
    label: "High Priority",
    icon: "🔴",
    className: "bg-red-100 text-red-800",
    ariaLabel: "High priority insight",
  },
  medium: {
    label: "Medium",
    icon: "🟡",
    className: "bg-yellow-100 text-yellow-800",
    ariaLabel: "Medium priority insight",
  },
  low: {
    label: "Low",
    icon: "🟢",
    className: "bg-green-100 text-green-800",
    ariaLabel: "Low priority insight",
  },
} as const;
```

### File Structure to Create

```
frontend/src/
├── app/[locale]/(dashboard)/
│   └── feed/
│       ├── page.tsx          # NEW — Teaching Feed page (Server Component)
│       └── loading.tsx       # NEW — Next.js streaming skeleton
├── features/
│   └── teaching-feed/        # NEW — entire directory
│       ├── components/
│       │   ├── FeedContainer.tsx
│       │   ├── InsightCard.tsx
│       │   ├── EducationLayer.tsx
│       │   └── TriageBadge.tsx
│       ├── hooks/
│       │   └── use-teaching-feed.ts
│       ├── __tests__/
│       │   ├── InsightCard.test.tsx
│       │   ├── TriageBadge.test.tsx
│       │   ├── use-teaching-feed.test.tsx
│       │   └── FeedContainer.test.tsx
│       └── types.ts
```

### Dashboard Navigation — No Changes Needed

The existing `(dashboard)/layout.tsx` handles auth guard and navigation. The `/feed` route will appear automatically once `feed/page.tsx` is created. Check if Sidebar has a link to `/feed` — if not, add one (look at `frontend/src/components/layout/Sidebar.tsx`).

### Import Aliases

The project uses `@/` as the alias for `src/`:
- `@/components/ui/card` → `src/components/ui/card.tsx`
- `@/components/ui/skeleton` → `src/components/ui/skeleton.tsx`
- `@/components/ui/button` → `src/components/ui/button.tsx`
- `@/lib/utils` → `src/lib/utils.ts` (the `cn()` helper)

### Testing Pattern (Follow Upload Feature)

Tests use Vitest + React Testing Library (follow `features/upload/__tests__/` structure):

```typescript
// InsightCard.test.tsx pattern
import { render, screen, fireEvent } from "@testing-library/react";
import { InsightCard } from "../components/InsightCard";

const mockInsight = {
  id: "uuid-1",
  uploadId: null,
  headline: "You spent 30% more on food this month",
  keyMetric: "₴3,200",
  whyItMatters: "Food is your biggest variable expense.",
  deepDive: "Breaking down by category: restaurants 60%, groceries 40%.",
  severity: "high" as const,
  category: "food",
  createdAt: "2026-04-04T12:00:00.000000Z",
};

test("expands to whyItMatters on first click", () => {
  render(<InsightCard insight={mockInsight} />);
  fireEvent.click(screen.getByRole("button", { name: /learn why/i }));
  expect(screen.getByText(/food is your biggest variable expense/i)).toBeInTheDocument();
});
```

For `use-teaching-feed.test.tsx`, use `msw` (check if it's in devDependencies) or mock `fetch` directly as done in `use-upload.test.tsx`.

### Previous Story Intelligence (Story 3.4)

- The backend `GET /api/v1/insights` API is fully implemented and tested (14 tests passing)
- Response is camelCase: `whyItMatters`, `keyMetric`, `deepDive`, `nextCursor`, `hasMore` — match exactly in `types.ts`
- Items sorted by severity (high first) from backend — no frontend re-sort
- 257 backend tests total (243 base + 14 from 3.4); pre-existing `test_sse_streaming.py` issue is unrelated
- `insight.py` API router registered at `/api/v1/insights` via `router.py`

### Git Intelligence (Recent Commits)

- `21c01d3 3.4: Teaching Feed API & Data Model` — backend API complete
- `6b7eff7 Story 3.3: RAG Knowledge Base & Education Agent` — insight generation pipeline
- `014e7f2 Story 2.7: Multiple Statement Uploads & Cumulative History` — upload feature complete
- All frontend work to date is auth, upload, settings features — `teaching-feed` is a new feature domain

### Project Structure Notes

- Feature folder follows exact architecture.md pattern: `features/teaching-feed/components/`, `features/teaching-feed/hooks/`
- `"use client"` directive required on all components with hooks (`useSession`, `useState`, `useQuery`)
- Server Components: `feed/page.tsx` can be a Server Component that wraps `<FeedContainer />` (which is client)
- i18n: no `useTranslations` needed for this story — hardcode English strings directly. i18n of the Teaching Feed is not in scope for MVP.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 3.5, line 715] — acceptance criteria
- [Source: _bmad-output/planning-artifacts/architecture.md#Frontend Directory Structure, lines 775-790] — file locations
- [Source: _bmad-output/planning-artifacts/architecture.md#Component Library, line 327] — shadcn/ui v4
- [Source: _bmad-output/planning-artifacts/architecture.md#API Style, line 311] — REST, camelCase, cursor pagination
- [Source: _bmad-output/implementation-artifacts/3-4-teaching-feed-api-data-model.md] — API shape, test baseline, endpoint path
- [Source: frontend/src/features/upload/hooks/use-upload.ts] — API_URL, auth header pattern
- [Source: frontend/src/features/upload/hooks/use-job-status.ts] — useSession pattern
- [Source: frontend/src/lib/query/query-provider.tsx] — TanStack Query v5 setup

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

No issues encountered. All tasks implemented cleanly in a single pass.

### Completion Notes List

- Created entire `frontend/src/features/teaching-feed/` feature directory from scratch
- Implemented `types.ts` with `InsightCard`, `InsightListResponse`, and `SeverityLevel` types matching backend camelCase response exactly
- Implemented `useTeachingFeed()` hook with TanStack Query v5 API, `enabled: !!session?.accessToken` guard, and 5-minute staleTime
- Implemented `TriageBadge` with WCAG 2.1 AA compliant icon + text + color (never color alone), aria-label on badge element
- Implemented `EducationLayer` with CSS max-height Tailwind transitions only (no Framer Motion — Story 3.6 scope)
- Implemented `InsightCard` with 3-level progressive disclosure (0→1→2→0), aria-expanded on expand button, shadcn/ui Card + Button primitives
- Implemented `FeedContainer` with loading skeletons (3 cards), error state with retry via `invalidateQueries`, empty state with upload link, success list
- Created `/feed` route as Server Component wrapping `FeedContainer` (client boundary) with metadata
- Created `loading.tsx` for Next.js streaming with matching skeleton structure
- All 15 new tests pass; all 122 pre-existing tests pass (137 total, 19 test files, zero regressions)

### File List

- frontend/src/features/teaching-feed/types.ts (new)
- frontend/src/features/teaching-feed/hooks/use-teaching-feed.ts (new)
- frontend/src/features/teaching-feed/components/TriageBadge.tsx (new)
- frontend/src/features/teaching-feed/components/EducationLayer.tsx (new, review-fixed: added aria-hidden, role, id props)
- frontend/src/features/teaching-feed/components/InsightCard.tsx (new, review-fixed: added aria-controls, isExpanded prop pass)
- frontend/src/features/teaching-feed/components/FeedContainer.tsx (new, review-fixed: Link import, extracted SkeletonCard)
- frontend/src/features/teaching-feed/components/SkeletonCard.tsx (new — review: extracted shared skeleton)
- frontend/src/features/teaching-feed/__tests__/TriageBadge.test.tsx (new)
- frontend/src/features/teaching-feed/__tests__/InsightCard.test.tsx (new)
- frontend/src/features/teaching-feed/__tests__/use-teaching-feed.test.tsx (new)
- frontend/src/features/teaching-feed/__tests__/FeedContainer.test.tsx (new, review-fixed: updated Link mock)
- frontend/src/app/[locale]/(dashboard)/feed/page.tsx (new, review-fixed: generateMetadata with i18n)
- frontend/src/app/[locale]/(dashboard)/feed/loading.tsx (new, review-fixed: uses shared SkeletonCard)
- frontend/src/app/[locale]/(dashboard)/feed/error.tsx (new — review: Next.js error boundary)
- frontend/src/app/[locale]/(dashboard)/layout.tsx (modified — review: added feed nav link)
- frontend/messages/en.json (modified — review: added dashboard.feed and feed.title keys)
- frontend/messages/uk.json (modified — review: added dashboard.feed and feed.title keys)

## Change Log

| Date | Change |
|------|--------|
| 2026-04-04 | Story implemented — Teaching Feed card UI with progressive disclosure, TanStack Query data fetch, skeleton loading, error/empty states, WCAG 2.1 AA accessibility; 25 new tests added (137 total passing) |
| 2026-04-04 | Code review fixes — H1: Fixed Link import to use @/i18n/navigation; H2: Added feed nav link to dashboard layout with BookOpen icon; H3: Added error.tsx error boundary for feed route; H4: Added aria-hidden on collapsed EducationLayer sections + aria-controls on expand button; M1: Added isExpanded prop to EducationLayer; M2: Extracted SkeletonCard to shared component; M3: Switched to generateMetadata with i18n translations |
