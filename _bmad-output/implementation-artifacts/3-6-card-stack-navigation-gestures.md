# Story 3.6: Card Stack Navigation & Gestures

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want to navigate insights using swipe gestures on mobile and keyboard/click on desktop,
So that browsing feels natural and responsive on any device.

## Acceptance Criteria

1. **Given** I am on mobile viewing the Teaching Feed, **When** I swipe left or right on a card, **Then** I navigate between insight cards with physical-feeling spring animations (Framer Motion)

2. **Given** I am on desktop viewing the Teaching Feed, **When** I press left/right arrow keys or click navigation controls (prev/next buttons), **Then** I navigate between cards with smooth transitions

3. **Given** the card stack, **When** animations play, **Then** they respect the `prefers-reduced-motion` media query — reduced motion users see instant transitions (no animation)

4. **Given** the Teaching Feed on mobile, **When** I interact with cards, **Then** all touch targets are thumb-reachable (min 44×44px) and the layout is optimized for portrait orientation

## Tasks / Subtasks

- [x] Task 1: Install Framer Motion (AC: #1, #2)
  - [x] 1.1 Install `motion` package (Framer Motion v11+): `npm install motion` — use `motion` not legacy `framer-motion` (React 19 compatible, tree-shakeable, smaller bundle)
  - [x] 1.2 Verify install in `frontend/package.json` — expected version `^11.x.x`

- [x] Task 2: Create `CardStackNavigator.tsx` — core stack navigation component (AC: #1, #2, #3, #4)
  - [x] 2.1 Create `frontend/src/features/teaching-feed/components/CardStackNavigator.tsx`
  - [x] 2.2 Accept props: `cards: InsightCard[]`
  - [x] 2.3 Internal state: `currentIndex: number` (useState, starts at 0), `direction: 1 | -1` for animation direction
  - [x] 2.4 Read `prefers-reduced-motion` via `window.matchMedia("(prefers-reduced-motion: reduce)")` or the `useReducedMotion()` hook from `motion/react` — pass to AnimatePresence/motion.div
  - [x] 2.5 Use `AnimatePresence` from `motion/react` with `mode="wait"` to handle card enter/exit transitions
  - [x] 2.6 Wrap each `InsightCard` in `motion.div` with:
    - Enter: slide in from right (direction=1) or left (direction=-1), spring physics: `{ type: "spring", stiffness: 300, damping: 30 }`
    - Exit: slide out opposite direction, fade to opacity 0
    - Reduced motion fallback: `initial={{ opacity: 0 }}`, `animate={{ opacity: 1 }}`, `exit={{ opacity: 0 }}` (no x translation)
  - [x] 2.7 Swipe gesture (mobile): use `drag="x"` prop on `motion.div`, `dragConstraints={{ left: 0, right: 0 }}`, `dragElastic={0.7}` — on `onDragEnd`, check `offset.x` threshold (> 80px → prev card, < -80px → next card)
  - [x] 2.8 Keyboard navigation (desktop): attach `onKeyDown` handler at container level (`tabIndex={0}`): `ArrowLeft` → prev card, `ArrowRight` → next card. Focus the container on mount.
  - [x] 2.9 Navigation controls: render `<button>` prev/next with chevron icons (use Lucide React — already installed). Disable prev button at index 0, disable next button at last index.
  - [x] 2.10 Progress indicator: render `"X of Y"` counter below the card (e.g., `"3 of 7"`) — use `text-sm text-muted-foreground` styling
  - [x] 2.11 Touch targets: all navigation buttons min `h-11 w-11` (44px — shadcn/ui Button default with `size="icon"`)
  - [x] 2.12 Guard: if `cards.length === 0`, render nothing (parent `FeedContainer` already handles empty state)

- [x] Task 3: Update `FeedContainer.tsx` — replace list with stack navigator (AC: #1, #2, #4)
  - [x] 3.1 Remove the `<ul>` list of `InsightCard` components from the success render path
  - [x] 3.2 Replace with `<CardStackNavigator cards={data} />` import
  - [x] 3.3 Keep unchanged: loading skeleton, error state with retry, empty state with upload link
  - [x] 3.4 The `<ul>` / `<li>` structure is replaced — no need for `key={insight.id}` on list items anymore

- [x] Task 4: Tests (AC: #1–#4)
  - [x] 4.1 Create `frontend/src/features/teaching-feed/__tests__/CardStackNavigator.test.tsx`
  - [x] 4.2 Test: renders first card by default (shows card at index 0)
  - [x] 4.3 Test: "Next" button click advances to second card
  - [x] 4.4 Test: "Prev" button disabled at first card (index 0)
  - [x] 4.5 Test: "Next" button disabled at last card
  - [x] 4.6 Test: progress counter shows correct `"X of Y"` value
  - [x] 4.7 Test: keyboard `ArrowRight` navigates to next card (fire keydown event on container)
  - [x] 4.8 Test: keyboard `ArrowLeft` navigates to previous card
  - [x] 4.9 Mock `motion/react` — add to test setup: `vi.mock("motion/react", ...)` with identity wrapper components (AnimatePresence renders children, motion.div renders div) — see pattern below
  - [x] 4.10 Update `FeedContainer.test.tsx`: replace list-rendering assertions with stack navigator assertions (first card visible, not all cards at once)
  - [x] 4.11 All pre-existing tests continue passing

## Dev Notes

### Architecture Overview

**Story 3.6 scope:** Convert the flat scrollable list of insight cards into a swipeable card stack with Framer Motion spring animations.

**What changes:**
- `FeedContainer.tsx` — success path replaces `<ul>` list with `<CardStackNavigator>`
- New `CardStackNavigator.tsx` — contains all stack/gesture/keyboard/animation logic
- `InsightCard.tsx` — **no changes needed** (progressive disclosure still works per-card)

**What does NOT change:**
- `FeedContainer` loading/error/empty states (unchanged)
- `InsightCard` internal expand/collapse logic (unchanged)
- `useTeachingFeed` hook (unchanged)
- Backend API (unchanged)
- SSE integration (Story 3.7 scope)
- Cursor pagination / infinite scroll (Story 3.7 scope)

### Installing Framer Motion (React 19)

**CRITICAL:** Use the `motion` package (Framer Motion v11+), NOT the legacy `framer-motion` package.

```bash
cd frontend && npm install motion
```

**Why `motion` not `framer-motion`:** Framer Motion v11 was rebranded as `motion`. It is React 19 compatible, supports tree-shaking, and has a smaller bundle. The legacy `framer-motion` package still works but `motion` is the maintained path.

**Import paths in `motion` package:**
```typescript
import { motion, AnimatePresence, useReducedMotion } from "motion/react";
// NOT from "framer-motion"
```

**Next.js 16 + Turbopack compatibility:** The `motion` package is ESM-first and compatible with Turbopack. No special next.config.ts changes needed.

### Card Stack Animation Pattern

```tsx
import { motion, AnimatePresence, useReducedMotion } from "motion/react";

// Inside CardStackNavigator:
const prefersReducedMotion = useReducedMotion();

const variants = prefersReducedMotion
  ? {
      enter: { opacity: 0 },
      center: { opacity: 1 },
      exit: { opacity: 0 },
    }
  : {
      enter: (direction: number) => ({
        x: direction > 0 ? 300 : -300,
        opacity: 0,
      }),
      center: { x: 0, opacity: 1 },
      exit: (direction: number) => ({
        x: direction > 0 ? -300 : 300,
        opacity: 0,
      }),
    };

<AnimatePresence mode="wait" custom={direction}>
  <motion.div
    key={currentIndex}
    custom={direction}
    variants={variants}
    initial="enter"
    animate="center"
    exit="exit"
    transition={prefersReducedMotion ? { duration: 0 } : { type: "spring", stiffness: 300, damping: 30 }}
    drag={prefersReducedMotion ? false : "x"}
    dragConstraints={{ left: 0, right: 0 }}
    dragElastic={0.7}
    onDragEnd={(_, info) => {
      if (info.offset.x < -80) goNext();
      if (info.offset.x > 80) goPrev();
    }}
  >
    <InsightCard insight={cards[currentIndex]} />
  </motion.div>
</AnimatePresence>
```

### Keyboard Navigation Pattern

```tsx
<div
  ref={containerRef}
  tabIndex={0}
  onKeyDown={(e) => {
    if (e.key === "ArrowRight") goNext();
    if (e.key === "ArrowLeft") goPrev();
  }}
  className="outline-none"  // hide focus ring on container
  aria-label="Insight card stack"
  role="region"
>
```

Add `aria-live="polite"` announcement for screen readers:
```tsx
<span className="sr-only" aria-live="polite">
  Card {currentIndex + 1} of {cards.length}
</span>
```

### Navigation Controls Layout

```tsx
// Bottom navigation row
<div className="mt-4 flex items-center justify-between">
  <Button
    variant="outline"
    size="icon"
    onClick={goPrev}
    disabled={currentIndex === 0}
    aria-label="Previous insight"
  >
    <ChevronLeft className="h-4 w-4" />
  </Button>

  <span className="text-sm text-muted-foreground">
    {currentIndex + 1} of {cards.length}
  </span>

  <Button
    variant="outline"
    size="icon"
    onClick={goNext}
    disabled={currentIndex === cards.length - 1}
    aria-label="Next insight"
  >
    <ChevronRight className="h-4 w-4" />
  </Button>
</div>
```

Lucide React icons: `import { ChevronLeft, ChevronRight } from "lucide-react"` — Lucide is already installed (used in layout/sidebar).

### Mocking `motion/react` in Tests

Vitest cannot run real animations. Add this mock for all tests that use `CardStackNavigator`:

```typescript
// In test file or vitest.setup.ts
vi.mock("motion/react", () => ({
  motion: {
    div: ({ children, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
      <div {...props}>{children}</div>
    ),
  },
  AnimatePresence: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useReducedMotion: () => false,
}));
```

**Note:** If multiple test files need this, add to `vitest.setup.ts` globally. Check if `frontend/vitest.setup.ts` or `frontend/src/test/setup.ts` exists.

### `prefers-reduced-motion` — Accessibility Requirement

**WCAG 2.3.3 (Level AAA) / WCAG 2.1 (2.3.3):** Animations must be suppressible.

The `useReducedMotion()` hook from `motion/react` reads the `prefers-reduced-motion` CSS media query and returns `true` if the user has enabled the OS-level "Reduce Motion" setting.

When `prefersReducedMotion === true`:
- `x` translation animations: disabled (no slide-in/out)
- `drag` prop: set to `false` (swipe gestures disabled)
- Transitions: `{ duration: 0 }` (instant)
- Only opacity fade remains (1 → 0 → 1)

### Mobile Portrait Layout

The card occupies the full container width. The `CardStackNavigator` container should be:
```tsx
<div className="relative w-full touch-pan-y">
```

`touch-pan-y` allows vertical scrolling (if page is long) while horizontal drag is captured by Framer Motion.

On mobile, the card itself (`InsightCard`) is already full-width — no changes needed there.

### File Structure

```
frontend/src/features/teaching-feed/
├── components/
│   ├── CardStackNavigator.tsx    # NEW — stack navigation with Framer Motion
│   ├── FeedContainer.tsx         # MODIFIED — use CardStackNavigator in success path
│   ├── InsightCard.tsx           # unchanged
│   ├── EducationLayer.tsx        # unchanged
│   ├── TriageBadge.tsx           # unchanged
│   └── SkeletonCard.tsx          # unchanged
└── __tests__/
    ├── CardStackNavigator.test.tsx  # NEW
    ├── FeedContainer.test.tsx       # MODIFIED — update success-path assertions
    ├── InsightCard.test.tsx         # unchanged
    ├── TriageBadge.test.tsx         # unchanged
    └── use-teaching-feed.test.tsx   # unchanged
```

### Previous Story Intelligence (Story 3.5)

- `FeedContainer` renders a `<ul>` with one `InsightCard` per `<li>` — **replace success path only**
- `InsightCard` uses `expandLevel` state (0/1/2) for progressive disclosure — unchanged
- `EducationLayer` uses CSS `max-height` Tailwind transitions — unchanged
- `SkeletonCard` was extracted as a shared component — unchanged
- Dashboard layout's `/feed` nav link and `feed/page.tsx` already exist — no changes needed
- `tw-animate-css` (`^1.4.0`) is installed but not needed for this story (Framer Motion handles animations)
- Note from 3.5: `EducationLayer` uses `max-h-96` for expanded state — if a card expands while in the stack, the card grows in height and drag still works (Framer Motion wraps the full InsightCard)

**Story 3.5 test baseline:** 137 total tests passing (19 test files). Story 3.6 adds ~9 new tests + updates FeedContainer tests.

### Git Intelligence (Recent Commits)

- `2d4da52 Story 3.5: Teaching Feed Card UI & Progressive Disclosure` — the flat card list we're converting to a stack
- `21c01d3 3.4: Teaching Feed API & Data Model` — backend API complete, no changes needed
- All teaching-feed frontend code is in `frontend/src/features/teaching-feed/` (established in 3.5)

### Next.js 16 / React 19 Notes

**CRITICAL:** Read `node_modules/next/dist/docs/` before writing any Next.js-specific code. This version (16.2.1) has breaking changes. The `motion` package is a client-side animation library used only inside `"use client"` components — no server-side concerns.

`CardStackNavigator` must have `"use client"` directive (uses `useState`, `useReducedMotion`, event handlers, `motion` animations).

### Import Aliases

- `@/components/ui/button` → `src/components/ui/button.tsx` (`Button`)
- `@/i18n/navigation` → for `Link` if needed (not needed in this story)
- `@/lib/utils` → `src/lib/utils.ts` (`cn()` helper)
- `motion/react` → installed from `npm install motion`

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 3.6, line 747] — acceptance criteria
- [Source: _bmad-output/planning-artifacts/epics.md, line 166] — Card stack as primary navigation pattern
- [Source: _bmad-output/planning-artifacts/epics.md, line 168] — Framer Motion for card stack gestures specified
- [Source: _bmad-output/implementation-artifacts/3-5-teaching-feed-card-ui-progressive-disclosure.md#Dev Notes] — FeedContainer structure, test baseline (137 tests), tw-animate-css note
- [Source: _bmad-output/implementation-artifacts/3-5-teaching-feed-card-ui-progressive-disclosure.md#Task 4.7] — explicit note: "Do NOT install Framer Motion — that is Story 3.6's dependency"
- [Source: frontend/src/features/teaching-feed/components/FeedContainer.tsx] — current `<ul>` list to replace
- [Source: frontend/src/features/teaching-feed/components/InsightCard.tsx] — component to wrap in motion.div
- [Source: frontend/AGENTS.md] — CRITICAL: read Next.js docs before writing Next.js-specific code

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

None — implementation completed without errors.

### Completion Notes List

- Installed `motion` package v12.38.0 (Framer Motion v11+ rebranded; React 19 compatible, tree-shakeable).
- Created `CardStackNavigator.tsx`: `useReducedMotion()` hook controls animation variants and drag — reduced-motion users get instant opacity-only transitions with drag disabled; full-motion users get spring physics (stiffness 300, damping 30) with swipe thresholds at ±80px.
- `AnimatePresence mode="wait"` with `custom={direction}` ensures enter/exit variants are directionally aware.
- Keyboard navigation: `tabIndex={0}` container auto-focused on mount; ArrowLeft/ArrowRight handled via `onKeyDown`.
- Navigation buttons use `h-11 w-11` (44px touch target), Lucide `ChevronLeft`/`ChevronRight` icons.
- Screen-reader support: `aria-live="polite"` sr-only span announces card position on change.
- `FeedContainer.tsx`: success path replaced `<ul>/<li>` list with `<CardStackNavigator cards={data} />`. Loading, error, and empty states unchanged.
- Tests: 8 new tests in `CardStackNavigator.test.tsx`; `FeedContainer.test.tsx` updated to assert only first card visible in stack (not all). `motion/react` mocked in both test files via `vi.mock`.
- Full regression: **145 tests passing** (20 test files). Baseline was 137 tests.

### Code Review Fixes (AI — claude-opus-4-6, 2026-04-04)

- **[H1] Added 3 drag/swipe gesture tests** — `capturedDragEnd` mock pattern tests swipe-left-to-next, swipe-right-to-prev, and below-threshold-no-nav (AC #1).
- **[H2] Added reduced motion test** — `mockReducedMotion = true` verifies card renders and button navigation works in reduced-motion mode (AC #3).
- **[M1] Added `currentIndex` clamping `useEffect`** — resets index when `cards` array shrinks, preventing `undefined` card access.
- **[M2] Added `e.preventDefault()` to keyboard handler** — prevents ArrowLeft/ArrowRight from triggering browser scroll alongside card navigation.
- **[L1] Replaced brittle motion mock** — prop-by-prop stripping replaced with HTML-safe allowlist filter in both test files.
- **[L2] Added `preventScroll: true` to auto-focus** — prevents scroll jump when container receives focus on mount.
- Full regression: **149 tests passing** (20 test files). +4 new tests from review fixes.

### File List

- `frontend/package.json` (modified — added `motion ^12.38.0`)
- `frontend/package-lock.json` (modified — updated lockfile)
- `frontend/src/features/teaching-feed/components/CardStackNavigator.tsx` (new)
- `frontend/src/features/teaching-feed/components/FeedContainer.tsx` (modified)
- `frontend/src/features/teaching-feed/__tests__/CardStackNavigator.test.tsx` (new)
- `frontend/src/features/teaching-feed/__tests__/FeedContainer.test.tsx` (modified)
