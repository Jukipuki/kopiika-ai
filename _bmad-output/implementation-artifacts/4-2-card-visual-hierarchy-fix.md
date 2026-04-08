# Story 4.2: Card Visual Hierarchy Fix

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->
<!-- Source: Epic 3 Retrospective — High Action Item #2 -->

## Story

As a **user**,
I want the Teaching Feed card headline to be visually dominant over the key metric,
so that I understand the context before seeing the number.

## Acceptance Criteria

1. **Given** an insight card with both a headline and a key metric, **When** the card renders in `InsightCard.tsx`, **Then** the headline is styled as the primary element (larger font size, bold weight) and the key metric is styled as supporting (smaller font size, secondary color, regular/medium weight).

2. **Given** the Education Agent generates a key metric, **When** the metric value is produced, **Then** it is concise — a short number with minimal context (e.g., "₴4,200", "₴6,800 on groceries") and never a compound expression like "₴87,582.04 (25.9% of total) vs. ₴213,238.50 finance allocation".

3. **Given** the updated card styling, **When** viewed on mobile (320px+) and desktop, **Then** the visual hierarchy is consistent — headline reads first, metric supports it.

4. **Given** the updated card styling, **When** tested against WCAG 2.1 AA contrast requirements, **Then** both headline and key metric text meet minimum contrast ratios (4.5:1 for normal text, 3:1 for large text).

## Tasks / Subtasks

- [x] Task 1: Update `InsightCard.tsx` headline and key metric styling (AC: #1, #3)
  - [x] 1.1 Change headline `<h3>` from `text-base font-semibold` to `text-lg font-bold leading-snug` (make it visually dominant)
  - [x] 1.2 Change key metric `<p>` from `text-2xl font-bold text-primary` to `text-base font-medium text-muted-foreground` (make it supporting)
  - [x] 1.3 Verify visual hierarchy: headline should be the first thing the eye lands on

- [x] Task 2: Refine Education Agent prompt for concise key metrics (AC: #2)
  - [x] 2.1 In `backend/app/agents/education/prompts.py`, update all 4 prompt templates
  - [x] 2.2 Change `key_metric` description from `"The key number (e.g., '₴4,200 on food this month')"` to `"A short metric, max 30 chars (e.g., '₴4,200 on food'). No compound expressions or percentages with comparisons."`
  - [x] 2.3 Apply equivalent change to Ukrainian prompts: `"Коротке число, макс 30 символів (наприклад, '₴4 200 на їжу'). Без складних виразів чи порівнянь."`

- [x] Task 3: Tests (AC: #1–#4)
  - [x] 3.1 Update `InsightCard` test: verify headline renders with `text-lg font-bold` classes
  - [x] 3.2 Update `InsightCard` test: verify key metric renders with `text-base font-medium text-muted-foreground` classes
  - [x] 3.3 Verify all existing 273 backend + 184 frontend tests continue to pass

## Dev Notes

### Scope Summary

**Frontend + backend prompt change.** CSS class swap on `InsightCard.tsx` to fix visual hierarchy, and prompt refinement in Education Agent to produce concise key metrics.

### Current State Analysis

**The problem:** In `InsightCard.tsx` (lines 38-39):
- Headline: `text-base font-semibold leading-snug` — small, semibold
- Key metric: `text-2xl font-bold text-primary` — large, bold, blue

The key metric visually dominates. Users' eyes land on the number before understanding what it means. The retro noted: "headline in small text, key metric in large blue bold text — semantically backwards."

Additionally, some LLM-generated key metrics are too verbose (e.g., "₴87,582.04 (25.9% of total) vs. ₴213,238.50 finance allocation"). The prompt in `prompts.py` gives a good example but no explicit length constraint.

### Files to Change

- `frontend/src/features/teaching-feed/components/InsightCard.tsx` — swap headline/metric styles (lines 38-39)
- `backend/app/agents/education/prompts.py` — add max-length constraint to key_metric in all 4 prompt templates (lines 22, 49, 76, 103)
- `frontend/src/features/teaching-feed/__tests__/InsightCard.test.tsx` — update class assertions

### Architecture Compliance

- No new components or API changes
- Follows existing Tailwind CSS patterns and shadcn/ui Card component
- Prompt changes are backward-compatible — existing cards in DB keep their key_metric values; only new cards will be more concise

### Previous Story Intelligence

From Story 3.5 (Teaching Feed Card UI): `InsightCard` was originally built with progressive disclosure. The current styling was a design decision that the retro identified as problematic after seeing real LLM output.

### Testing Notes

- Frontend tests use `vitest` + `@testing-library/react`
- Test baseline: **273 backend tests**, **184 frontend tests**
- InsightCard tests check rendered content — update class name assertions for the style swap

### Project Structure Notes

- Frontend change in `frontend/src/features/teaching-feed/components/InsightCard.tsx`
- Backend change in `backend/app/agents/education/prompts.py`
- No cross-feature impact

### References

- [Source: frontend/src/features/teaching-feed/components/InsightCard.tsx#L38-39] — current headline/metric styling
- [Source: backend/app/agents/education/prompts.py#L22,49,76,103] — key_metric prompt descriptions
- [Source: _bmad-output/implementation-artifacts/epic-3-retro-2026-04-07.md#Challenge 5] — card visual hierarchy issue
- [Source: _bmad-output/implementation-artifacts/epic-3-retro-2026-04-07.md#Challenge 7] — key metric content quality

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

None — implementation was straightforward with no blockers.

### Completion Notes List

- Swapped `InsightCard.tsx` headline from `text-base font-semibold` → `text-lg font-bold leading-snug` and key metric from `text-2xl font-bold text-primary` → `truncate text-base font-medium text-muted-foreground`. Visual hierarchy is now correct: headline dominates, metric supports. Added `truncate` as CSS safety net for overflow.
- Updated all 4 Education Agent prompt templates in `prompts.py` (2 English + 2 Ukrainian) to enforce a 30-char max on `key_metric` and forbid compound expressions.
- Added 2 new class-assertion tests to `InsightCard.test.tsx` (subtasks 3.1, 3.2) as regression guards for the hierarchy fix.
- WCAG 2.1 AA contrast verified: `text-muted-foreground` on card background passes in both light mode (oklch(0.556 0 0) ≈ #737373 on white → 4.74:1) and dark mode (#9CA3AF on #181B23 → 6.78:1). Threshold: 4.5:1 for normal text.

### File List

- frontend/src/features/teaching-feed/components/InsightCard.tsx
- backend/app/agents/education/prompts.py
- frontend/src/features/teaching-feed/__tests__/InsightCard.test.tsx

## Known Limitations

- **Key metric length is prompt-advisory only.** The 30-char max in Education Agent prompts is a soft constraint — no backend truncation or validation. LLMs may still produce verbose metrics. Accepted risk: truncation could produce meaningless output. Revisit after testing with live data to assess actual metric length distribution.

## Change Log

- 2026-04-08: Story 4.2 implemented — fixed card visual hierarchy (headline dominant, metric supporting) and tightened Education Agent key_metric prompt to max 30 chars across all 4 templates.
- 2026-04-08: Code review fixes — added CSS `truncate` overflow guard on key metric, verified WCAG AA contrast (4.74:1 light / 6.78:1 dark), documented known limitation on soft prompt length constraint.
