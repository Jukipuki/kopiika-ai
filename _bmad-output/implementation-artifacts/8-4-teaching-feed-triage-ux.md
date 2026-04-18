# Story 8.4: Teaching Feed Triage UX

Status: done

## Story

As a **user**,
I want insight cards to display a clear visual severity indicator,
So that I can immediately understand the urgency of each insight without reading its full content.

## Acceptance Criteria

1. **Given** an insight card with `severity = "critical"` **When** it renders in the Teaching Feed **Then** a `TriageBadge.tsx` component displays a red badge with a warning icon and "Critical" text label; the card also has a subtle red left-border accent to reinforce urgency at a glance.

2. **Given** an insight card with `severity = "warning"` **When** it renders **Then** the `TriageBadge` displays an amber/yellow badge with a caution icon and "Warning" text label.

3. **Given** an insight card with `severity = "info"` **When** it renders **Then** the `TriageBadge` displays a teal/green badge with an info icon and "Info" text label (badge may be omitted for low-severity cards — implementation decision).

4. **Given** a user who cannot distinguish red, yellow, and green by colour **When** they view the Teaching Feed **Then** severity is conveyed through both the icon shape AND the text label ("Critical", "Warning", "Info") — not colour alone (NFR21 colour independence compliance).

5. **Given** a screen reader user navigating the Teaching Feed **When** their focus enters a severity badge **Then** it announces as "Severity: Critical", "Severity: Warning", or "Severity: Informational" via `aria-label` on the badge element (NFR20 screen reader compatibility).

6. **Given** the Teaching Feed is loaded after a completed pipeline **When** the card list renders **Then** critical-severity cards appear at the top, followed by warning, followed by info — consistent with the server-side sort order introduced in Story 8.3 (no frontend work needed — already done server-side).

7. **Given** a user with `prefers-reduced-motion` enabled **When** the Teaching Feed renders **Then** the severity badges display as static elements — no pulse, glow, or attention animation is applied.

## Tasks / Subtasks

- [x] Task 1: Update `SeverityLevel` type in `types.ts` (AC: all)
  - [x] 1.1 In `frontend/src/features/teaching-feed/types.ts`, update `SeverityLevel` to:
    ```typescript
    export type SeverityLevel = "critical" | "warning" | "info" | "high" | "medium" | "low";
    ```
    The `high/medium/low` variants remain for backward compatibility — pre-8.3 rows in the DB still carry these values and the API returns them as-is. The TriageBadge must handle both sets.

- [x] Task 2: Rewrite `TriageBadge.tsx` for new severity values (AC: #1–#5, #7)
  - [x] 2.1 Replace the emoji icons with lucide-react icons — `AlertTriangle` for critical, `AlertCircle` for warning, `Info` for info. Lucide is already a project dependency (used in `CardStackNavigator.tsx`).
  - [x] 2.2 Update `SEVERITY_CONFIG` to the new values. Use distinct icon shapes (not just colours) so colour-blind users can distinguish severities by shape + text:
    ```typescript
    const SEVERITY_CONFIG: Record<SeverityLevel, SeverityConfig> = {
      critical: {
        label: "Critical",
        Icon: AlertTriangle,
        className: "bg-red-100 text-red-800",
        ariaLabel: "Severity: Critical",
      },
      warning: {
        label: "Warning",
        Icon: AlertCircle,
        className: "bg-amber-100 text-amber-800",
        ariaLabel: "Severity: Warning",
      },
      info: {
        label: "Info",
        Icon: Info,
        className: "bg-teal-100 text-teal-800",
        ariaLabel: "Severity: Informational",
      },
      // Backward compat aliases for pre-8.3 rows
      high:   { label: "Critical", Icon: AlertTriangle, className: "bg-red-100 text-red-800",   ariaLabel: "Severity: Critical" },
      medium: { label: "Warning",  Icon: AlertCircle,   className: "bg-amber-100 text-amber-800", ariaLabel: "Severity: Warning" },
      low:    { label: "Info",     Icon: Info,          className: "bg-teal-100 text-teal-800",  ariaLabel: "Severity: Informational" },
    };
    ```
  - [x] 2.3 Render the badge with the lucide icon at `size={12}` (or `h-3 w-3`) using `aria-hidden="true"` on the icon (the outer `aria-label` on the span conveys meaning to screen readers). Badge is a static `<span>` — no animations. This satisfies AC #7 by default (no motion to suppress).
  - [x] 2.4 The component signature stays the same: `TriageBadge({ severity: SeverityLevel })`. No `useReducedMotion` needed since the badge is already static.

- [x] Task 3: Add red left-border accent on critical cards in `InsightCard.tsx` (AC: #1)
  - [x] 3.1 In `frontend/src/features/teaching-feed/components/InsightCard.tsx`, add a conditional `className` to the `Card` element:
    ```tsx
    <Card className={insight.severity === "critical" || insight.severity === "high" ? "border-l-4 border-l-red-500" : undefined}>
    ```
    The `high` alias is included for backward compat. The shadcn `Card` uses `cn()` to merge className, so this works cleanly. The `ring-1 ring-foreground/10` (box-shadow based) coexists with `border-l-4` (physical border) — they occupy different CSS layers. `overflow-hidden` clips child content, not the card's own border.

- [x] Task 4: Add red left-border accent on critical cards in `SubscriptionAlertCard.tsx` (AC: #1)
  - [x] 4.1 Same change as Task 3 in `frontend/src/features/teaching-feed/components/SubscriptionAlertCard.tsx`:
    ```tsx
    <Card className={insight.severity === "critical" || insight.severity === "high" ? "border-l-4 border-l-red-500" : undefined}>
    ```

- [x] Task 5: Update `TriageBadge.test.tsx` (AC: #1–#5)
  - [x] 5.1 Replace old severity tests (`high/medium/low`) with new tests for `critical/warning/info`:
    - Test: `critical` → renders "Critical" text and `AlertTriangle` icon (check via `aria-label="Severity: Critical"` on badge, text "Critical" in DOM).
    - Test: `warning` → renders "Warning" text, `aria-label="Severity: Warning"`.
    - Test: `info` → renders "Info" text, `aria-label="Severity: Informational"`.
    - Test: backward compat `high` → same output as `critical` (aria-label + text).
    - Test: backward compat `medium` → same output as `warning`.
    - Test: backward compat `low` → same output as `info`.
  - [x] 5.2 Icon shape test: assert that the `AlertTriangle` icon is present for `critical` (use `data-testid` or check by accessible role if lucide renders with `role="img"`, otherwise just assert the aria-label approach is sufficient since the icon is `aria-hidden`).

- [x] Task 6: Update `InsightCard.test.tsx` (AC: #1, #4, #5)
  - [x] 6.1 Update `mockInsight.severity` from `"high"` to `"critical"` to match the new canonical value.
  - [x] 6.2 Update the TriageBadge aria-label assertion from `"High priority insight"` to `"Severity: Critical"` (line 64 in current file).
  - [x] 6.3 Add test: card with `severity = "critical"` renders with `border-l-4` class on the card element.
  - [x] 6.4 Add test: card with `severity = "warning"` does NOT render with `border-l-4` class.

- [x] Task 7: Update `SubscriptionAlertCard.test.tsx` (AC: #1, #5)
  - [x] 7.1 Check existing tests — update any mock `severity` values from old to new canonical values, and update any `aria-label` assertions to match new format `"Severity: ..."`.

- [x] Task 8: Version bump (AC: new user-facing feature = MINOR)
  - [x] 8.1 Update `VERSION` file: `1.17.0` → `1.18.0`.

## Dev Notes

### Scope: Frontend-Only Story

This is a pure frontend story. All backend work (severity scoring, DB storage, API sort order) was completed in Stories 8.1–8.3. The Teaching Feed API already returns `severity: "critical" | "warning" | "info"` for post-8.3 cards. Pre-8.3 rows still carry `"high" | "medium" | "low"` — backward compat aliases in both `SeverityLevel` type and `TriageBadge` SEVERITY_CONFIG are required.

### TriageBadge Already Exists

`TriageBadge.tsx` is NOT a new file — it already exists at `frontend/src/features/teaching-feed/components/TriageBadge.tsx` and is already imported by both `InsightCard.tsx` and `SubscriptionAlertCard.tsx`. This story rewrites it in-place.

### Icon Library: lucide-react

Project already uses lucide-react (see `CardStackNavigator.tsx` importing `ChevronLeft`, `ChevronRight`). Import the three icons at the top of `TriageBadge.tsx`:
```typescript
import { AlertTriangle, AlertCircle, Info } from "lucide-react";
```

Icon shapes chosen to be distinguishable by shape (not just colour):
- `AlertTriangle` (triangle) — universally recognized as danger/critical
- `AlertCircle` (circle with !) — recognized as caution/warning  
- `Info` (i) — recognized as informational

### Left-Border: CSS Compatibility with shadcn Card

The shadcn `Card` uses `ring-1 ring-foreground/10` (implemented as `box-shadow`). Adding `border-l-4 border-l-red-500` via `className` prop works correctly:
- `box-shadow` (ring) and physical `border` occupy different CSS stacking layers and render simultaneously.
- `overflow-hidden` clips child content overflow, NOT the element's own border edge.
- The `cn()` utility in `card.tsx` merges className cleanly.
- Left border only on `critical` (and backward-compat `high`) — not on `warning` or `info`.

### prefers-reduced-motion

The badge is a plain static `<span>` — no animations exist to suppress. If a future enhancement adds a pulse animation to critical badges, it must be wrapped in a `@media (prefers-reduced-motion: no-preference)` guard or use `useReducedMotion()` from `motion/react` (already available in the project). Do NOT add any `animate-*` Tailwind classes or CSS animations in this story — the AC explicitly prohibits it.

### Card Sort Order (AC #6): No Work Needed

Server-side sort by `critical → warning → info` was implemented in Story 8.3 (`insight_service.py` `severity_order` CASE expression). The `CardStackNavigator` renders cards in the order returned by the API. No frontend sort logic is required.

### Project Structure Notes

- All changes stay within `frontend/src/features/teaching-feed/`
- No new files created — only edits to existing files
- Next.js 16.1 specific: see `frontend/AGENTS.md` before writing any Next.js-specific code
- Do NOT read node_modules to understand APIs — use type inference and existing patterns

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 8.4] — Acceptance criteria source
- [Source: frontend/src/features/teaching-feed/types.ts](frontend/src/features/teaching-feed/types.ts) — SeverityLevel type to update
- [Source: frontend/src/features/teaching-feed/components/TriageBadge.tsx](frontend/src/features/teaching-feed/components/TriageBadge.tsx) — Component to rewrite
- [Source: frontend/src/features/teaching-feed/components/InsightCard.tsx](frontend/src/features/teaching-feed/components/InsightCard.tsx) — Add conditional border-l-4 to Card
- [Source: frontend/src/features/teaching-feed/components/SubscriptionAlertCard.tsx](frontend/src/features/teaching-feed/components/SubscriptionAlertCard.tsx) — Same border-l-4 treatment
- [Source: frontend/src/features/teaching-feed/__tests__/TriageBadge.test.tsx](frontend/src/features/teaching-feed/__tests__/TriageBadge.test.tsx) — Test file to rewrite
- [Source: frontend/src/features/teaching-feed/__tests__/InsightCard.test.tsx](frontend/src/features/teaching-feed/__tests__/InsightCard.test.tsx) — Update mock severity + aria-label + border tests
- [Source: frontend/src/features/teaching-feed/components/CardStackNavigator.tsx](frontend/src/features/teaching-feed/components/CardStackNavigator.tsx) — lucide-react + useReducedMotion usage pattern
- [Source: frontend/src/components/ui/card.tsx](frontend/src/components/ui/card.tsx) — Card className passthrough via cn()
- [Source: _bmad-output/implementation-artifacts/8-3-triage-agent-severity-scoring.md] — Previous story: severity values now critical/warning/info, backward compat high/medium/low in DB

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

No debug issues encountered. All 481 tests passed on first run.

### Completion Notes List

- Updated `SeverityLevel` type to include `"critical" | "warning" | "info"` alongside backward-compat `"high" | "medium" | "low"`
- Rewrote `TriageBadge.tsx` using lucide-react icons (AlertTriangle/AlertCircle/Info) — shapes are distinguishable without colour, satisfying colour-blind AC #4
- All six severity values handled: new canonical values + backward-compat aliases mapping to same output
- Added `border-l-4 border-l-red-500` conditional on critical/high severity in both `InsightCard` and `SubscriptionAlertCard`
- All 28 new tests pass; full 481-test suite green; no regressions
- Pre-existing TypeScript errors in 4 unrelated files were not introduced by this story
- Version bumped 1.17.0 → 1.18.0 (MINOR: new user-facing UI feature)

### File List

- frontend/src/features/teaching-feed/types.ts
- frontend/src/features/teaching-feed/components/TriageBadge.tsx
- frontend/src/features/teaching-feed/components/InsightCard.tsx
- frontend/src/features/teaching-feed/components/SubscriptionAlertCard.tsx
- frontend/src/features/teaching-feed/__tests__/TriageBadge.test.tsx
- frontend/src/features/teaching-feed/__tests__/InsightCard.test.tsx
- frontend/src/features/teaching-feed/__tests__/SubscriptionAlertCard.test.tsx
- VERSION
- _bmad-output/implementation-artifacts/8-4-teaching-feed-triage-ux.md
- _bmad-output/implementation-artifacts/sprint-status.yaml

## Code Review (2026-04-18)

Adversarial review found 1 HIGH, 3 MEDIUM, 3 LOW. HIGH + MEDIUM fixed in-place; LOW handled as noted.

**Fixed:**
- **H1** — SubscriptionAlertCard had no `border-l-4` test for AC #1. Added three tests (`critical` + backward-compat `high` render border; `warning` does not). [SubscriptionAlertCard.test.tsx](../../frontend/src/features/teaching-feed/__tests__/SubscriptionAlertCard.test.tsx)
- **M1** — Added backward-compat `high` severity border test to InsightCard suite so the `|| "high"` fallback is locked in. [InsightCard.test.tsx](../../frontend/src/features/teaching-feed/__tests__/InsightCard.test.tsx)
- **M2** — Extracted `isCriticalSeverity(severity)` helper to [types.ts](../../frontend/src/features/teaching-feed/types.ts); both card components now delegate instead of duplicating the `"critical" || "high"` expression.
- **M3** — Replaced narrow inline `React.ComponentType<...>` with `LucideIcon` from `lucide-react`. Accurate typing for lucide props (className, color, strokeWidth). [TriageBadge.tsx](../../frontend/src/features/teaching-feed/components/TriageBadge.tsx)

**Deferred (story-local):**
- **L1** — `SEVERITY_CONFIG[severity]` has no runtime fallback. Guarded by TypeScript; backend is controlled so drift risk is low. Revisit if API ever starts returning unexpected severity values.
- **L2** — `SEVERITY_CONFIG` duplicates config for backward-compat aliases (`high → critical`, etc.). Pure maintainability nit; only bites if severity vocab changes a third time.

**Withdrawn:**
- **L3** — Info visual label "Info" vs aria-label "Severity: Informational" → withdrawn on review: intentional per AC #5. Added an inline comment at [TriageBadge.tsx:27](../../frontend/src/features/teaching-feed/components/TriageBadge.tsx#L27) to prevent a future "fix".

## Change Log

- 2026-04-18: Story 8.4 implemented — Teaching Feed Triage UX with lucide-react severity badges, red left-border accents on critical cards, backward compat aliases, full a11y (aria-label, icon-shape + text). Version bumped from 1.17.0 to 1.18.0.
- 2026-04-18: Code review complete — fixed H1 (missing SubscriptionAlertCard border test), M1 (missing `high` severity border test), M2 (extracted `isCriticalSeverity` helper), M3 (switched to `LucideIcon` type). L1/L2 kept story-local, L3 withdrawn. 34 tests pass (was 28), status → done.
