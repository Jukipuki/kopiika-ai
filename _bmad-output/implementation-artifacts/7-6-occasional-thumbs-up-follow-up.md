# Story 7.6: Occasional Thumbs-Up Follow-Up

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want to occasionally tell the system what made a card useful,
So that the system learns what works without asking me every time.

## Acceptance Criteria

1. **Given** I tap thumbs-up on a Teaching Feed card **When** the system determines this is the 1-in-10 trigger occurrence **Then** a compact slide-up panel appears with 3 preset chips: "Learned something", "Actionable", "Well explained"

2. **Given** the follow-up panel appears on thumbs-up **When** I tap a chip or dismiss **Then** it behaves identically to the thumbs-down panel: chip selection sent via PATCH `/api/v1/feedback/{feedbackId}`, auto-dismiss after 1s, dismissible without action (tap-outside or Escape)

3. **Given** the 1-in-10 trigger logic **When** it determines whether to show the follow-up **Then** the probability is computed client-side (`Math.random() < 0.1`) so no server round-trip is needed

4. **Given** the follow-up panel **When** it renders for thumbs-up **Then** it uses the same `FollowUpPanel.tsx` component as the thumbs-down follow-up panel but with different chip labels

## Tasks / Subtasks

- [x] Task 1: Backend — Extend `ReasonChipIn` to accept thumbs-up chip values (AC: #2)
  - [x] 1.1 In `backend/app/api/v1/feedback.py`, update `ReasonChipIn.reason_chip` `Literal` to add three new values:
    ```python
    reason_chip: Literal[
        "not_relevant", "already_knew", "seems_incorrect", "hard_to_understand",
        "learned_something", "actionable", "well_explained",
    ]
    ```
  - [x] 1.2 No DB migration needed — `reason_chip VARCHAR(50)` column already exists and all new values fit within 50 chars

- [x] Task 2: Backend — Tests for new chip values (AC: #2)
  - [x] 2.1 In `backend/tests/test_feedback_vote_api.py`, inside `TestPatchReasonChipEndpoint`, add:
    - `test_patch_thumbs_up_chip_learned_something`: POST vote (up), PATCH with `{"reasonChip": "learned_something"}` → 200, `data["reasonChip"] == "learned_something"`
    - `test_patch_thumbs_up_chip_actionable`: POST vote (up), PATCH with `{"reasonChip": "actionable"}` → 200
    - `test_patch_thumbs_up_chip_well_explained`: POST vote (up), PATCH with `{"reasonChip": "well_explained"}` → 200
    - The existing `test_patch_reason_chip_rejects_invalid_chip` still covers the 422 case for unknown values

- [x] Task 3: Frontend — Extend `ReasonChip` type (AC: #2)
  - [x] 3.1 In `frontend/src/features/teaching-feed/hooks/use-card-feedback.ts`, extend the `ReasonChip` type with `"learned_something"`, `"actionable"`, `"well_explained"`

- [x] Task 4: Frontend — Update `FollowUpPanel.tsx` to accept a `variant` prop (AC: #4)
  - [x] 4.1 In `frontend/src/features/teaching-feed/components/FollowUpPanel.tsx`: added `variant` prop, `THUMBS_UP_CHIPS` array, renamed `CHIPS` → `THUMBS_DOWN_CHIPS`, variant-aware `chips` and `titleKey` selection

- [x] Task 5: Frontend — Update `CardFeedbackBar.tsx` to trigger on thumbs-up (AC: #1, #3)
  - [x] 5.1 In `frontend/src/features/teaching-feed/components/CardFeedbackBar.tsx`: added `followUpVariant` state, timer-clear on new vote, thumbs-up 1-in-10 trigger, variant-aware `useEffect` session-flag guard, `variant` prop passed to `<FollowUpPanel>`

- [x] Task 6: Frontend — i18n (AC: #1, #4)
  - [x] 6.1 In `frontend/messages/en.json`: added `thumbsUpTitle`, `learnedSomething`, `actionable`, `wellExplained` keys
  - [x] 6.2 In `frontend/messages/uk.json`: added Ukrainian equivalents

- [x] Task 7: Frontend — Tests (AC: #1–#4)
  - [x] 7.1 Updated `frontend/src/features/teaching-feed/__tests__/FollowUpPanel.test.tsx`: 4 new tests for thumbs-up variant (11 total)
  - [x] 7.2 Updated `frontend/src/features/teaching-feed/__tests__/CardFeedbackBar.test.tsx`: updated mock to pass `variant` prop, 4 new thumbs-up trigger tests (24 total)

## Dev Notes

### Architecture Overview

Story 7.6 is **Layer 2 feedback for thumbs-up** — the occasional follow-up panel that mirrors Story 7.5's thumbs-down panel. It is purely additive:
- **No DB migration** — `reason_chip VARCHAR(50)` column exists, all new values fit within 50 chars
- **No new backend model** — only the `Literal` union in `ReasonChipIn` is expanded
- **No new component** — `FollowUpPanel.tsx` is extended with a `variant` prop

### Backend: Literal Extension

`ReasonChipIn.reason_chip` current `Literal` (Story 7.5):
```python
Literal["not_relevant", "already_knew", "seems_incorrect", "hard_to_understand"]
```

Add three values (Story 7.6):
```python
Literal[
    "not_relevant", "already_knew", "seems_incorrect", "hard_to_understand",
    "learned_something", "actionable", "well_explained",
]
```

The `feedback_service.update_reason_chip()` function takes `reason_chip: str` — no service-layer changes needed. The `reason_chip VARCHAR(50)` column has no DB-level constraint on valid values; validation is purely at the API layer via Pydantic `Literal`.

### Frontend: FollowUpPanel Variant Architecture

The current `CHIPS` constant (renamed `THUMBS_DOWN_CHIPS`) lives at module level in `FollowUpPanel.tsx`. Add a second `THUMBS_UP_CHIPS` array and select based on the `variant` prop:

```typescript
const THUMBS_DOWN_CHIPS: ReadonlyArray<{ value: ReasonChip; key: string }> = [
  { value: "not_relevant", key: "chip.notRelevant" },
  { value: "already_knew", key: "chip.alreadyKnew" },
  { value: "seems_incorrect", key: "chip.seemsIncorrect" },
  { value: "hard_to_understand", key: "chip.hardToUnderstand" },
];

const THUMBS_UP_CHIPS: ReadonlyArray<{ value: ReasonChip; key: string }> = [
  { value: "learned_something", key: "chip.learnedSomething" },
  { value: "actionable", key: "chip.actionable" },
  { value: "well_explained", key: "chip.wellExplained" },
];
```

Inside the component body:
```typescript
const chips = variant === "thumbs_up" ? THUMBS_UP_CHIPS : THUMBS_DOWN_CHIPS;
const titleKey = variant === "thumbs_up" ? "thumbsUpTitle" : "title";
```

The `selected` state uses `ReasonChip | null` — already updated in Task 3 to include thumbs-up chip values, so TypeScript will accept them without any cast.

### Frontend: CardFeedbackBar Trigger Logic

Current state (Story 7.5 post-code-review): The `followUpPending` + `feedbackId` effect guards thumbs-down with `_sessionFlags.hasShownFollowUp`. Thumbs-up has no session cap (it's purely probabilistic):

```typescript
// handleVote additions
if (value === "up" && Math.random() < 0.1) {
  followUpTimerRef.current = setTimeout(() => {
    setFollowUpVariant("thumbs_up");
    setFollowUpPending(true);
  }, 300);
}
```

The existing effect needs `followUpVariant` in its dependency array and must skip the `_sessionFlags` check for thumbs-up:

```typescript
useEffect(() => {
  if (!followUpPending) return;
  if (!feedbackId) return;
  if (followUpVariant === "thumbs_down") {
    if (_sessionFlags.hasShownFollowUp) {
      setFollowUpPending(false);
      return;
    }
    _sessionFlags.hasShownFollowUp = true;
  }
  setShowFollowUp(true);
  setFollowUpPending(false);
}, [followUpPending, feedbackId, followUpVariant]);
```

**Important**: `followUpVariant` must be initialized with a valid default (e.g. `"thumbs_down"`) since it's used in JSX before any vote is cast. The default doesn't matter in practice because `showFollowUp` starts `false`.

### Frontend: Timer Race Condition — Thumbs-Up vs Thumbs-Down

If a user taps thumbs-down then quickly thumbs-up (or vice versa), two `setTimeout` calls can race. The existing `followUpTimerRef` already clears on unmount but does NOT clear when a second vote fires. Add a `clearTimeout` at the top of `handleVote` before starting a new timer:

```typescript
const handleVote = (value: "up" | "down") => {
  if (vote === value) return;
  // Clear any pending follow-up timer from a prior vote
  if (followUpTimerRef.current !== null) {
    clearTimeout(followUpTimerRef.current);
    followUpTimerRef.current = null;
  }
  setFollowUpPending(false);
  ...
```

This prevents a stale thumbs-down timer from firing after the user switched to thumbs-up.

### Frontend: Testing Math.random

Use `vi.spyOn(Math, "random")` to control randomness in tests:

```typescript
// Force trigger (< 0.1)
vi.spyOn(Math, "random").mockReturnValue(0.05);

// Prevent trigger (>= 0.1)
vi.spyOn(Math, "random").mockReturnValue(0.5);
```

Restore in `afterEach` with `vi.restoreAllMocks()` (already called in Story 7.5 afterEach).

### Frontend: Test Baseline

As of Story 7.5 code-review fixes: backend 541 passing, frontend 443 passing.

### Project Structure Notes

```
backend/
└── app/api/v1/
    └── feedback.py              ← MODIFIED: expand ReasonChipIn Literal (3 new values)
    tests/
    └── test_feedback_vote_api.py ← MODIFIED: add 3 thumbs-up chip tests in TestPatchReasonChipEndpoint

frontend/src/features/teaching-feed/
├── hooks/
│   └── use-card-feedback.ts     ← MODIFIED: extend ReasonChip type (3 new values)
├── components/
│   ├── FollowUpPanel.tsx         ← MODIFIED: add variant prop, THUMBS_UP_CHIPS, thumbsUpTitle key
│   └── CardFeedbackBar.tsx       ← MODIFIED: followUpVariant state, thumbs-up trigger, timer clear
├── __tests__/
│   ├── FollowUpPanel.test.tsx    ← MODIFIED: add thumbs-up variant tests (4 new tests)
│   └── CardFeedbackBar.test.tsx  ← MODIFIED: add thumbs-up trigger tests (4 new tests)
└── (no new files)

frontend/messages/
├── en.json                       ← MODIFIED: add thumbsUpTitle + 3 thumbs-up chip keys
└── uk.json                       ← MODIFIED: add thumbsUpTitle + 3 thumbs-up chip keys
```

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 7.6] — user story, acceptance criteria, chip labels, 1-in-10 trigger requirement
- [Source: _bmad-output/planning-artifacts/epics.md#FR51] — "On thumbs-up, system presents an optional follow-up (triggered 1 in 10 occurrences)"
- [Source: frontend/src/features/teaching-feed/components/FollowUpPanel.tsx] — current component structure; CHIPS array, variant prop pattern to add
- [Source: frontend/src/features/teaching-feed/components/CardFeedbackBar.tsx] — `_sessionFlags`, `followUpPending`/`followUpTimerRef` pattern, `handleVote` logic to extend
- [Source: frontend/src/features/teaching-feed/hooks/use-card-feedback.ts] — `ReasonChip` type definition to extend (line 9–13), `submitReasonChip` mutation
- [Source: backend/app/api/v1/feedback.py:120-126] — `ReasonChipIn` with current `Literal` values to expand
- [Source: _bmad-output/implementation-artifacts/7-5-thumbs-down-follow-up-panel-with-reason-chips.md] — timer race note (H1 fix), inline panel pattern (H2 fix), test baselines, snapshot pattern, `_sessionFlags` reset in `afterEach`

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

No blockers or debug sessions required. All tasks implemented cleanly on first pass.

### Completion Notes List

- Extended `ReasonChipIn.reason_chip` Literal in `feedback.py` with 3 thumbs-up values; no DB migration needed (VARCHAR(50) column has no DB-level constraint)
- Added 3 backend tests in `TestPatchReasonChipEndpoint`; backend suite: 541 → 544 passing
- Extended `ReasonChip` TypeScript union type in `use-card-feedback.ts` with 3 new values
- Refactored `FollowUpPanel.tsx`: renamed `CHIPS` → `THUMBS_DOWN_CHIPS`, added `THUMBS_UP_CHIPS`, added `variant` prop with variant-aware chip selection and title key
- Extended `CardFeedbackBar.tsx`: added `followUpVariant` state, added timer-clear at top of `handleVote` to prevent race conditions, added thumbs-up 1-in-10 trigger (`Math.random() < 0.1`), updated `useEffect` to skip session-flag guard for thumbs-up variant
- Added `thumbsUpTitle` and 3 new chip keys to both `en.json` and `uk.json`
- Added 4 new `FollowUpPanel` tests (thumbs-up variant, regression guard, chip call, title key); FollowUpPanel suite: 7 → 11
- Updated `CardFeedbackBar` mock to pass `variant` prop through testid; updated existing tests to use `follow-up-panel-thumbs_down` testid; added 4 new thumbs-up tests; suite: 20 → 24
- Frontend suite: 443 → 451 passing; all regressions clean
- Version bumped 1.11.0 → 1.12.0 (new user-facing feature → MINOR)

### File List

- `backend/app/api/v1/feedback.py`
- `backend/tests/test_feedback_vote_api.py`
- `frontend/src/features/teaching-feed/hooks/use-card-feedback.ts`
- `frontend/src/features/teaching-feed/components/FollowUpPanel.tsx`
- `frontend/src/features/teaching-feed/components/CardFeedbackBar.tsx`
- `frontend/messages/en.json`
- `frontend/messages/uk.json`
- `frontend/src/features/teaching-feed/__tests__/FollowUpPanel.test.tsx`
- `frontend/src/features/teaching-feed/__tests__/CardFeedbackBar.test.tsx`
- `VERSION`

### Change Log

- 2026-04-17: Story 7.6 implemented — thumbs-up occasional follow-up panel via `FollowUpPanel` variant prop, 1-in-10 client-side trigger, 3 new chip values in backend Literal and frontend type, i18n for EN and UK
- 2026-04-17: Version bumped from 1.11.0 to 1.12.0 per story completion
- 2026-04-17: Senior Developer code review (AI) — 4 MEDIUM findings fixed (test coverage for thumbs-up dismissal paths, rapid-switch race test, end-to-end thumbs-up chip test, i18n key rename `title` → `thumbsDownTitle` for variant symmetry); 2 LOW findings promoted to [TD-024](../../docs/tech-debt.md) and [TD-025](../../docs/tech-debt.md); 1 LOW kept story-local (misleading test name). Frontend suite 451 → 456 passing.

## Senior Developer Review (AI)

**Reviewer:** Oleh
**Date:** 2026-04-17
**Outcome:** Approve — all ACs implemented; all HIGH/MEDIUM findings fixed in-review.

### Findings

| ID | Severity | Title | Disposition |
|----|---|---|---|
| M1 | MEDIUM | Missing tap-outside / Escape / auto-dismiss tests for thumbs-up variant (AC #2 "identical behavior") | Fixed — 3 new tests in [FollowUpPanel.test.tsx](../../frontend/src/features/teaching-feed/__tests__/FollowUpPanel.test.tsx) |
| M2 | MEDIUM | No test for rapid vote switch within 300ms (the exact race the `clearTimeout` in `handleVote` prevents) | Fixed — new test `"clears pending timer when user switches vote within 300ms"` in [CardFeedbackBar.test.tsx](../../frontend/src/features/teaching-feed/__tests__/CardFeedbackBar.test.tsx) |
| M3 | MEDIUM | Mock `FollowUpPanel` hardcoded `"not_relevant"` for all variants — no integration proof that thumbs-up chips reach `submitReasonChip` | Fixed — mock is now variant-aware; new test `"forwards thumbs-up chip selection to submitReasonChip"` asserts `"actionable"` reaches the mutation |
| M4 | MEDIUM | i18n key asymmetry: `title` (thumbs-down) vs `thumbsUpTitle` (thumbs-up); future variants would inherit the drift | Fixed — renamed to `thumbsDownTitle` + `thumbsUpTitle` in [en.json](../../frontend/messages/en.json), [uk.json](../../frontend/messages/uk.json), [FollowUpPanel.tsx](../../frontend/src/features/teaching-feed/components/FollowUpPanel.tsx), and the test file |
| L1 | LOW | Magic number `0.1` in [CardFeedbackBar.tsx:92](../../frontend/src/features/teaching-feed/components/CardFeedbackBar.tsx#L92) — extract `THUMBS_UP_FOLLOW_UP_PROBABILITY` | Promoted → [TD-024](../../docs/tech-debt.md). Thumbs-up follow-up probability is an inline literal, not a named constant |
| L2 | LOW | `_sessionFlags` mutable module object read in `useEffect` but not in deps | Promoted → [TD-025](../../docs/tech-debt.md). `_sessionFlags` module-level object read inside useEffect without being in deps |
| L3 | LOW | Misleading test name `"does NOT render thumbs-down FollowUpPanel on thumbs-up"` at [CardFeedbackBar.test.tsx:289](../../frontend/src/features/teaching-feed/__tests__/CardFeedbackBar.test.tsx#L289) — actually tests the `Math.random() >= 0.1` branch | Kept story-local (trivial rename any future reader can fix in passing) |

### Git vs Story File List

No discrepancies. All 10 files in the story's File List match `git diff --name-only`. VERSION bump 1.11.0 → 1.12.0 matches story intent. Story file itself is untracked (expected for a newly-created story).

### Test Baselines After Review

- Backend: 544 passing (unchanged — backend not touched by review fixes).
- Frontend: 456 passing, 47 test files (was 451 pre-review; +5 tests from M1, M2, M3 fixes).
