# Story 7.5: Thumbs-Down Follow-Up Panel with Reason Chips

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want to quickly tell the system why I thumbs-downed a card,
So that my feedback is categorized for better education quality improvement.

## Acceptance Criteria

1. **Given** I tap thumbs-down on a Teaching Feed card **When** 300ms has elapsed after my tap **Then** a compact slide-up panel appears below the card (not a modal) with 4 preset reason chips: "Not relevant to me", "Already knew this", "Seems incorrect", "Hard to understand"

2. **Given** the follow-up panel is visible **When** I tap a reason chip **Then** the chip selection is sent via `PATCH /api/v1/feedback/{feedbackId}` with `{"reasonChip": "not_relevant"}`, the panel auto-dismisses after 1 second, and no further interaction is required

3. **Given** the follow-up panel is visible **When** I tap outside the panel or swipe it down **Then** it dismisses without recording a reason (the thumbs-down vote still stands)

4. **Given** I thumbs-down multiple cards in the same session **When** the follow-up panel trigger logic runs **Then** the panel appears only on the first thumbs-down of the session to prevent repetition

5. **Given** the reason chips **When** they are displayed **Then** they are available in both Ukrainian and English, compact enough for mobile, and keyboard accessible

## Tasks / Subtasks

- [x] Task 1: Backend — Add `update_reason_chip` service function (AC: #2)
  - [x] 1.1 In `backend/app/services/feedback_service.py`, add `update_reason_chip(feedback_id, user_id, reason_chip, session)` that:
    - Queries `CardFeedback` by `id=feedback_id` AND `user_id=user_id` (ownership check in query)
    - Returns `None` if no row found (caller returns 404)
    - Updates `record.reason_chip = reason_chip`, calls `await session.flush()`
    - Returns a detached snapshot (same pattern as `submit_card_vote`) before `await session.commit()`

- [x] Task 2: Backend — Add PATCH endpoint (AC: #2)
  - [x] 2.1 In `backend/app/api/v1/feedback.py`, add Pydantic schemas:
    - `ReasonChipIn(BaseModel)` with `model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)` and `reason_chip: Literal["not_relevant", "already_knew", "seems_incorrect", "hard_to_understand"]`
    - `ReasonChipOut(BaseModel)` with same config and `id: uuid.UUID`, `reason_chip: str`
  - [x] 2.2 Add endpoint to `feedback_vote_router`:
    ```python
    @feedback_vote_router.patch("/{feedback_id}", response_model=ReasonChipOut)
    async def update_reason_chip(
        feedback_id: uuid.UUID,
        body: ReasonChipIn,
        user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
        session: Annotated[SQLModelAsyncSession, Depends(get_db)],
    ) -> ReasonChipOut:
    ```
    - Calls `feedback_service.update_reason_chip(...)`, raises `HTTP_404_NOT_FOUND` if `None`
    - Returns `ReasonChipOut(id=record.id, reason_chip=record.reason_chip)`
    - No rate limiter needed (PATCH is a follow-up to an already rate-limited POST)

- [x] Task 3: Backend — Tests (AC: #2)
  - [x] 3.1 In `backend/tests/test_feedback_vote_api.py`, add class `TestPatchReasonChipEndpoint`:
    - `test_patch_reason_chip_returns_200`: create user + insight, POST vote (down), capture feedback `id` from response, then PATCH with `{"reasonChip": "not_relevant"}`, assert 200, `data["reasonChip"] == "not_relevant"`, `data["id"] == feedback_id`
    - `test_patch_reason_chip_returns_404_when_absent`: PATCH with random UUID → 404
    - `test_patch_reason_chip_rejects_invalid_chip`: PATCH with `{"reasonChip": "wrong_chip"}` → 422
    - `test_patch_reason_chip_requires_auth`: no auth → 401/403
    - `test_patch_reason_chip_cannot_access_other_users_record`: two users, user A submits vote, user B tries to PATCH user A's feedback_id → 404 (ownership check via query filter)

- [x] Task 4: Frontend — Extend `use-card-feedback.ts` to expose feedbackId (AC: #2)
  - [x] 4.1 In `frontend/src/features/teaching-feed/hooks/use-card-feedback.ts`:
    - Add `feedbackId: string | null` state (initialized to `null`)
    - In `mutation.onSuccess`, extract `response.id` and call `setFeedbackId(response.id)` — the mutation already returns the full `CardVoteOut` JSON
    - Export `feedbackId` from the hook return value
    - Add `submitReasonChip` mutation: `PATCH ${API_URL}/api/v1/feedback/${feedbackId}` with `{ reasonChip: chip }`
      - `onSuccess`: calls `queryClient.invalidateQueries({ queryKey })` (so `reasonChip` is refreshed on the GET)
      - Only callable when `feedbackId != null`
    - Export `submitReasonChip` and `isReasonChipPending` from the hook

- [x] Task 5: Frontend — Create `FollowUpPanel.tsx` (AC: #1, #2, #3, #5)
  - [x] 5.1 Create `frontend/src/features/teaching-feed/components/FollowUpPanel.tsx`:
    - Props: `feedbackId: string`, `onDismiss: () => void`, `onChipSelect?: (chip: string) => void`
    - Uses `useTranslations("feed.followUpPanel")` for all labels
    - Renders 4 chip buttons (e.g., `<Button variant="outline" size="sm">`) with values:
      - `"not_relevant"` → `t("chip.notRelevant")`
      - `"already_knew"` → `t("chip.alreadyKnew")`
      - `"seems_incorrect"` → `t("chip.seemsIncorrect")`
      - `"hard_to_understand"` → `t("chip.hardToUnderstand")`
    - On chip click: calls `onChipSelect(chip)`, then after 1000ms calls `onDismiss()`
    - Has a dismiss button or backdrop click handler that calls `onDismiss()` immediately without recording
    - Slide-up animation: use CSS `translate-y` or a simple Tailwind `animate-slide-up`
    - Panel is `role="dialog"` with `aria-label={t("title")}` for accessibility (AC: #5)
    - Each chip button is keyboard focusable (standard `<Button>` already handles this)

- [x] Task 6: Frontend — Update `CardFeedbackBar.tsx` (AC: #1, #4)
  - [x] 6.1 In `frontend/src/features/teaching-feed/components/CardFeedbackBar.tsx`:
    - Add module-level `let hasShownFollowUpThisSession = false` (resets on page reload — satisfies "per session" AC)
    - Update `useCardFeedback` destructuring to include `feedbackId`, `submitReasonChip`
    - Add `showFollowUp: boolean` state, initialized to `false`
    - In `handleVote`, when `value === "down"` AND `hasShownFollowUpThisSession === false`:
      - Start a 300ms `setTimeout` → `setShowFollowUp(true)` and `hasShownFollowUpThisSession = true`
    - Render `{showFollowUp && feedbackId && <FollowUpPanel feedbackId={feedbackId} onDismiss={() => setShowFollowUp(false)} onChipSelect={submitReasonChip} />}` below the button row
    - Import `FollowUpPanel` from `./FollowUpPanel`

- [x] Task 7: Frontend — i18n (AC: #5)
  - [x] 7.1 Add to `frontend/messages/en.json` under `feed.followUpPanel`:
    ```json
    "followUpPanel": {
      "title": "Why wasn't this helpful?",
      "chip": {
        "notRelevant": "Not relevant to me",
        "alreadyKnew": "Already knew this",
        "seemsIncorrect": "Seems incorrect",
        "hardToUnderstand": "Hard to understand"
      }
    }
    ```
  - [x] 7.2 Add Ukrainian equivalents to `frontend/messages/uk.json` under `feed.followUpPanel`:
    ```json
    "followUpPanel": {
      "title": "Чому це не було корисним?",
      "chip": {
        "notRelevant": "Не актуально для мене",
        "alreadyKnew": "Я це вже знав",
        "seemsIncorrect": "Здається некоректним",
        "hardToUnderstand": "Важко зрозуміти"
      }
    }
    ```

- [x] Task 8: Frontend — Tests (AC: #1–#5)
  - [x] 8.1 Create `frontend/src/features/teaching-feed/__tests__/FollowUpPanel.test.tsx`:
    - Mock `useTranslations` (same `vi.mock("next-intl", ...)` pattern as `CardFeedbackBar.test.tsx`)
    - `test renders 4 chip buttons`: renders `<FollowUpPanel feedbackId="abc" onDismiss={vi.fn()} />` — assert all 4 chip labels present
    - `test calls onChipSelect and auto-dismisses after 1s`: click a chip, assert `onChipSelect` called with `"not_relevant"`, advance timers by 1000ms, assert `onDismiss` called
    - `test dismiss button calls onDismiss without onChipSelect`: click the dismiss/backdrop element — assert `onDismiss` called and `onChipSelect` NOT called
    - `test is keyboard accessible`: chips can be activated with Enter/Space (fireEvent.keyDown or role="button")

  - [x] 8.2 In `frontend/src/features/teaching-feed/__tests__/CardFeedbackBar.test.tsx`:
    - Add mock for `FollowUpPanel`: `vi.mock("../components/FollowUpPanel", () => ({ FollowUpPanel: ({ onDismiss }: { feedbackId: string; onDismiss: () => void; onChipSelect: (c: string) => void }) => <div data-testid="follow-up-panel"><button onClick={onDismiss}>dismiss-panel</button></div> }))`
    - Update `mockUseCardFeedback` to return `feedbackId: "feedback-uuid-123"` in all `beforeEach` setups
    - `test follow-up panel does not show immediately after thumbs-down`: click thumbs-down, assert no `follow-up-panel` in DOM before 300ms
    - `test follow-up panel shows 300ms after thumbs-down`: click thumbs-down, advance timers 300ms, assert `follow-up-panel` in DOM
    - `test follow-up panel does NOT show on thumbs-up`: click thumbs-up, advance timers 300ms, assert no `follow-up-panel`
    - `test follow-up panel shows only on first thumbs-down of session`: second thumbs-down on a different `cardId` should not show panel (reset `hasShownFollowUpThisSession` in `afterEach` by re-importing or using a factory)
    - `test dismissing panel hides it`: show panel (advance timers), click `dismiss-panel`, assert `follow-up-panel` gone

## Dev Notes

### Critical Context

Story 7.5 is **Layer 2 feedback** — the follow-up panel that appears after a thumbs-down vote. It is purely additive:
- **No new DB migration** — `reason_chip VARCHAR(50)` column already exists in `card_feedback` table (added in Story 7.2 migration `q3r4s5t6u7v8_add_card_feedback_table.py`)
- **No new model** — only the service function and API endpoint are added on the backend
- `GET /api/v1/feedback/cards/{cardId}` already returns `reasonChip` in `CardFeedbackResponse` — the UI can restore persisted chip state if needed (but the AC doesn't require it for this story)

### Backend: PATCH Endpoint URL

`feedback_vote_router` has `prefix="/feedback"` and is mounted at `v1_router` with prefix `/api/v1`. So:
- Full URL: `PATCH /api/v1/feedback/{feedbackId}`
- This matches the architecture spec and the epics AC exactly

### Backend: Ownership Pattern

The service function MUST filter by both `id=feedback_id` AND `user_id=user_id` in a single query — do NOT query by ID alone and then check ownership in Python. This prevents leaking the existence of other users' feedback IDs:

```python
async def update_reason_chip(
    feedback_id: uuid.UUID,
    user_id: uuid.UUID,
    reason_chip: str,
    session: SQLModelAsyncSession,
) -> Optional[CardFeedback]:
    existing = (
        await session.exec(
            select(CardFeedback).where(
                CardFeedback.id == feedback_id,
                CardFeedback.user_id == user_id,
            )
        )
    ).one_or_none()
    if existing is None:
        return None
    existing.reason_chip = reason_chip
    await session.flush()
    # Snapshot before commit to prevent MissingGreenlet
    snapshot = CardFeedback(
        id=existing.id,
        user_id=existing.user_id,
        card_id=existing.card_id,
        card_type=existing.card_type,
        vote=existing.vote,
        reason_chip=existing.reason_chip,
        free_text=existing.free_text,
        feedback_source=existing.feedback_source,
        issue_category=existing.issue_category,
        created_at=existing.created_at,
    )
    await session.commit()
    return snapshot
```

### Backend: Reason Chip Values

Valid values for `reason_chip` (enforced via `Literal` in `ReasonChipIn`):
- `"not_relevant"` → "Not relevant to me"
- `"already_knew"` → "Already knew this"
- `"seems_incorrect"` → "Seems incorrect"
- `"hard_to_understand"` → "Hard to understand"

Architecture spec (`reason_chip VARCHAR(50)`) — all values fit within 50 chars.

### Frontend: feedbackId Flow

The `POST /api/v1/feedback/cards/{cardId}/vote` response returns:
```json
{ "id": "uuid", "cardId": "uuid", "vote": "down", "createdAt": "..." }
```

The `id` here is the `CardFeedback.id` — this is the `feedbackId` needed for the PATCH. Currently `use-card-feedback.ts` doesn't expose it; extend the hook:

```typescript
const [feedbackId, setFeedbackId] = useState<string | null>(null);

// In mutation.onSuccess (replace the current invalidateQueries-only handler):
onSuccess: (responseData) => {
  setFeedbackId(responseData.id);  // responseData is CardVoteOut
  queryClient.invalidateQueries({ queryKey });
},
```

The mutation already returns the parsed JSON (see `return res.json()` in `mutationFn`). No additional typing needed beyond capturing the `.id` field.

### Frontend: Session-Level Tracking

The AC says "panel appears only on the first thumbs-down of the session". Implement as a **module-level variable** in `CardFeedbackBar.tsx` (or a shared module if preferred):

```typescript
// At module top-level (outside component) — resets on page reload
let hasShownFollowUpThisSession = false;
```

This is correct: `false` on fresh page load, set to `true` on first panel display. Multiple card instances share this flag because they all import the same module.

**Important:** In tests, you must reset this flag between test cases. Since it's module-level, the cleanest approach is to `vi.resetModules()` between tests that test the session-limit behavior, or expose a test-only reset. Alternatively, import the flag via a resetable module. Simplest for tests: refactor the check to a mutable object that can be reset in `afterEach`:

```typescript
// module-level (barrel to allow test reset)
export const _sessionFlags = { hasShownFollowUp: false };
```

Then use `_sessionFlags.hasShownFollowUp` in the component and reset it in tests with `import { _sessionFlags } from "../components/CardFeedbackBar"; ... afterEach(() => { _sessionFlags.hasShownFollowUp = false; })`.

### Frontend: FollowUpPanel Slide-Up Animation

Keep animation simple — no animation library needed. Use Tailwind utilities:

```tsx
<div className="fixed bottom-0 left-0 right-0 bg-background border-t rounded-t-xl p-4 shadow-lg animate-in slide-in-from-bottom duration-200">
```

`animate-in` and `slide-in-from-bottom` are available via `tailwindcss-animate` (already used in the project — `ReportIssueForm` uses similar patterns). This is "not a modal" per the AC — it's a bottom-anchored panel.

### Frontend: FollowUpPanel Dismiss on Backdrop Click

The panel is not a modal, so there's no built-in backdrop. For tap-outside dismissal, add a transparent overlay behind the panel:

```tsx
<>
  {/* backdrop */}
  <div className="fixed inset-0 z-40" onClick={onDismiss} aria-hidden="true" />
  {/* panel */}
  <div className="fixed bottom-0 left-0 right-0 z-50 ...">...</div>
</>
```

This matches the "tap outside dismisses without recording" AC.

### Frontend: Auto-Dismiss Timing

After chip selection:
1. Immediately update UI to show chip as selected (optimistic)
2. Fire PATCH request
3. After 1000ms, call `onDismiss()` — use `setTimeout(onDismiss, 1000)`

Do NOT wait for the PATCH response before starting the 1-second timer. If the PATCH fails, the panel will have already dismissed; the vote still stands (the AC only requires the chip to be sent, not confirmed). This matches the UX intent of "no further interaction required".

### Frontend: Test Reset for Session Flag

If you use the `_sessionFlags` export approach, the `afterEach` in `CardFeedbackBar.test.tsx` should include:

```typescript
import { _sessionFlags } from "../components/CardFeedbackBar";
// ...
afterEach(() => {
  _sessionFlags.hasShownFollowUp = false;
  vi.useRealTimers();
  vi.restoreAllMocks();
});
```

### Project Structure Notes

```
backend/
├── app/
│   ├── api/v1/
│   │   └── feedback.py         ← MODIFIED: add ReasonChipIn, ReasonChipOut schemas; add PATCH /{feedbackId}
│   └── services/
│       └── feedback_service.py ← MODIFIED: add update_reason_chip()
└── tests/
    └── test_feedback_vote_api.py  ← MODIFIED: add TestPatchReasonChipEndpoint class

frontend/src/features/teaching-feed/
├── hooks/
│   └── use-card-feedback.ts    ← MODIFIED: expose feedbackId + submitReasonChip
├── components/
│   ├── CardFeedbackBar.tsx     ← MODIFIED: add FollowUpPanel trigger logic (300ms, session flag)
│   └── FollowUpPanel.tsx       ← NEW: slide-up chip panel
├── __tests__/
│   ├── CardFeedbackBar.test.tsx  ← MODIFIED: add follow-up panel tests
│   └── FollowUpPanel.test.tsx    ← NEW: chip panel tests
└── messages/
    ├── en.json                 ← MODIFIED: add feed.followUpPanel keys
    └── uk.json                 ← MODIFIED: add feed.followUpPanel keys
```

### Previous Story Intelligence (Stories 7.1–7.4)

1. **Snapshot before commit:** Service functions MUST capture all field values before `session.commit()` to prevent `MissingGreenlet` error. `update_reason_chip` must follow the same snapshot pattern as `submit_card_vote` and `submit_issue_report`.

2. **Test isolation:** Capture `.id` (and any FK fields) into local variables BEFORE `session.commit()`. Post-commit attributes expire in SQLAlchemy async sessions.

3. **Frontend timer tests:** Use `vi.useFakeTimers()` in `beforeEach` and `vi.useRealTimers()` in `afterEach`. Wrap timer advances in `act(...)` — `act(() => { vi.advanceTimersByTime(300); })`.

4. **Frontend test mocking:** `vi.mock("next-intl", () => ({ useTranslations: () => (key: string) => key }))` returns keys as-is. New i18n keys will be returned as their key paths by the mock (e.g., `"chip.notRelevant"` is returned as `"chip.notRelevant"`).

5. **Test baseline as of Story 7.4:** backend 535 passing, frontend 428 passing.

6. **CardFeedback import path:** `from app.models.feedback import CardFeedback` — correct path for both service and test imports.

7. **No audit trail needed.** Feedback endpoints (votes, chips, reports) are NOT in `AUDIT_PATH_RESOURCE_MAP` per Stories 7.1–7.4 precedent.

### Git Intelligence (Recent Commits)

- `cbfefd6` (Story 7.4): Extended data-summary endpoint with feedbackSummary, added feedback deletion to account deletion service. Did NOT touch `feedback.py` or `feedback_service.py` (the vote/report layer).
- `8f5b7a0` (Story 7.3): Added `ReportIssueForm.tsx`, `use-issue-report.ts`, POST `/cards/{id}/report` endpoint. Last story to touch `CardFeedbackBar.tsx` before this one.
- `13ebcd9` (Story 7.2): Added `CardFeedbackBar.tsx`, `use-card-feedback.ts`, POST `/cards/{id}/vote`, GET `/cards/{id}`. Established all patterns used by this story.

This story's changes are in the **same files** as Story 7.2 + new `FollowUpPanel.tsx`. Review 7.2 story file for additional context on the test fixtures and import patterns.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 7.5] — full acceptance criteria and user story
- [Source: _bmad-output/planning-artifacts/architecture.md#Feedback Data Model] — `reason_chip VARCHAR(50)` column on `card_feedback`; `PATCH /api/v1/feedback/{feedbackId}` endpoint spec; `FollowUpPanel.tsx` path; Layer 2 feature description
- [Source: _bmad-output/planning-artifacts/architecture.md#User Feedback — Layer 2 (FR50-FR51)] — `FollowUpPanel.tsx` in components folder, Layer 2 behavior
- [Source: backend/app/api/v1/feedback.py] — existing schemas and route patterns; `feedback_vote_router` prefix `/feedback`; `Literal` typing pattern for validated string inputs
- [Source: backend/app/services/feedback_service.py] — snapshot pattern for all service functions; SELECT-then-update pattern; `get_card_feedback` as model for ownership-filtered queries
- [Source: backend/app/models/feedback.py] — `CardFeedback` model; `reason_chip: Optional[str] = Field(default=None, max_length=50)`
- [Source: backend/alembic/versions/q3r4s5t6u7v8_add_card_feedback_table.py] — confirms `reason_chip` column already exists (no migration needed)
- [Source: backend/tests/test_feedback_vote_api.py] — test fixture pattern (`vote_engine`, `vote_session`, `vote_client`), `_create_user`/`_create_insight` helpers, auth override pattern, class-based test organization
- [Source: frontend/src/features/teaching-feed/hooks/use-card-feedback.ts] — mutation return type (CardVoteOut JSON), optimistic update pattern, queryKey pattern
- [Source: frontend/src/features/teaching-feed/components/CardFeedbackBar.tsx] — component structure, useCardFeedback usage, `vi.useFakeTimers` pattern in tests
- [Source: frontend/src/features/teaching-feed/__tests__/CardFeedbackBar.test.tsx] — mock setup for `useCardFeedback`, `vi.mock("next-intl")`, `vi.mock("../components/ReportIssueForm")`, `vi.useFakeTimers` + `act` pattern
- [Source: _bmad-output/implementation-artifacts/7-4-feedback-data-privacy-integration.md] — test baselines (535 BE, 428 FE), snapshot pattern learnings, MissingGreenlet prevention

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (1M context)

### Debug Log References

None — all tests passed on first run.

### Completion Notes List

- Backend: added `update_reason_chip` service function in `backend/app/services/feedback_service.py` using the ownership-filtered SELECT pattern (filters by `id=feedback_id` AND `user_id=user_id`) and returns a detached snapshot before `await session.commit()` to avoid `MissingGreenlet` on closed sessions — same pattern as `submit_card_vote`.
- Backend: added `ReasonChipIn`/`ReasonChipOut` schemas and `PATCH /api/v1/feedback/{feedback_id}` endpoint to `feedback_vote_router` in `backend/app/api/v1/feedback.py`. Raises `HTTP_404_NOT_FOUND` when ownership check fails. No rate limiter (Layer 2 follow-up to an already rate-limited POST).
- Frontend: extended `useCardFeedback` hook to capture `id` from the vote-mutation response and expose it as `feedbackId`, plus a `submitReasonChip` mutation that `PATCH`es `/api/v1/feedback/{feedbackId}` and invalidates the feedback query on success.
- Frontend: new `FollowUpPanel.tsx` renders 4 reason chips with tailwindcss-animate `slide-in-from-bottom`, uses `role="dialog"` + `aria-label`, dismisses on backdrop click without recording, and auto-dismisses 1000ms after a chip click. Selecting a second chip is a no-op.
- Frontend: `CardFeedbackBar.tsx` now triggers the panel 300ms after a thumbs-down vote, but only on the first thumbs-down of the session — enforced via a module-level `_sessionFlags` object (exported for test reset). Panel is only rendered when `feedbackId` is already available.
- i18n: added `feed.followUpPanel` keys (title + 4 chip labels) to both `en.json` and `uk.json`.
- Tests: 5 new backend tests (`TestPatchReasonChipEndpoint`) and 5 new frontend tests (`FollowUpPanel`) + 7 new follow-up-panel tests in `CardFeedbackBar.test.tsx`. Backend suite: 540 passing (prev 535 → +5). Frontend suite: 440 passing (prev 428 → +12).
- Version bumped 1.10.0 → 1.11.0 (MINOR — new user-facing feature per `docs/versioning.md`).

### File List

- `backend/app/services/feedback_service.py` — added `update_reason_chip` service function
- `backend/app/api/v1/feedback.py` — added `ReasonChipIn`/`ReasonChipOut` schemas and `PATCH /feedback/{feedback_id}` endpoint
- `backend/tests/test_feedback_vote_api.py` — added `TestPatchReasonChipEndpoint` class (5 tests)
- `frontend/src/features/teaching-feed/hooks/use-card-feedback.ts` — added `feedbackId` state and `submitReasonChip` mutation
- `frontend/src/features/teaching-feed/components/FollowUpPanel.tsx` — new slide-up reason-chip panel
- `frontend/src/features/teaching-feed/components/CardFeedbackBar.tsx` — wired up panel trigger with 300ms delay and session-level guard (`_sessionFlags`)
- `frontend/src/features/teaching-feed/__tests__/FollowUpPanel.test.tsx` — new test file (5 tests)
- `frontend/src/features/teaching-feed/__tests__/CardFeedbackBar.test.tsx` — added follow-up-panel tests, mocked `FollowUpPanel`, and `_sessionFlags` reset in `afterEach`
- `frontend/messages/en.json` — added `feed.followUpPanel` keys
- `frontend/messages/uk.json` — added `feed.followUpPanel` keys
- `VERSION` — bumped 1.10.0 → 1.11.0
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — story status transitions
- `_bmad-output/implementation-artifacts/7-5-thumbs-down-follow-up-panel-with-reason-chips.md` — tasks checked, story Status set to review, Dev Agent Record filled

## Code Review (2026-04-17)

Adversarial review found 2 HIGH, 4 MEDIUM, 4 LOW. All HIGH and MEDIUM fixed in the same pass:

- **H1 FIXED — Session-flag race** [CardFeedbackBar.tsx:55-80](../../../frontend/src/features/teaching-feed/components/CardFeedbackBar.tsx#L55-L80): The flag was set in `handleVote` before the panel actually rendered. If the vote POST was still in flight at 300ms (→ `feedbackId` null → panel's render gate fails), the session flag was already burned and future thumbs-downs were suppressed forever. Fix: introduce `followUpPending` state; the 300ms timer now sets it, and an effect promotes it to `showFollowUp=true` AND consumes the flag **only when `feedbackId` is actually available**. New regression test `defers session flag until feedbackId is known (H1 race fix)`.
- **H2 FIXED — Panel was effectively modal** [FollowUpPanel.tsx](../../../frontend/src/features/teaching-feed/components/FollowUpPanel.tsx): The old implementation had a `fixed inset-0` click-catcher backdrop + `role="dialog"` + `fixed bottom-0` panel — i.e. a modal, directly contradicting AC#1 ("not a modal"). Fix: panel now renders inline beneath the card (`mt-2 rounded-lg border bg-background`); no backdrop. Outside-tap dismissal comes from a document-level `pointerdown` capture listener that checks `panelRef.contains(target)`.
- **M1 FIXED — Missing Escape + focus management**: Added a document-level `keydown` listener for `Escape` → `onDismiss()` (AC#5 keyboard a11y), and `autoFocus` on the first chip so keyboard users land inside the panel immediately. New tests `dismisses when Escape is pressed` and `auto-focuses the first chip on mount`.
- **M2 FIXED — `id` missing from GET /cards/{cardId} response** [feedback.py:75-81](../../../backend/app/api/v1/feedback.py#L75-L81), [use-card-feedback.ts](../../../frontend/src/features/teaching-feed/hooks/use-card-feedback.ts): `CardFeedbackResponse` now includes `id: uuid.UUID`. Hook derives `feedbackId = postedFeedbackId ?? data?.id ?? null` so that after a page reload, an existing vote can still feed the PATCH flow. Backend GET-feedback test asserts the new `id` field.
- **M3 FIXED — PATCH endpoint had no rate limit** [feedback.py:134-153](../../../backend/app/api/v1/feedback.py#L134-L153): Added `rate_limiter` dependency and `check_feedback_rate_limit(str(user_id))` call. New backend test `test_patch_reason_chip_rate_limited` asserts 429 path.
- **M4 FIXED by H2 — clickable `<div>` backdrop with no keyboard handler**: backdrop is gone entirely; no more lint-violating click-only element.

### LOW — remaining (considered but not fixed)

- **L1 resolved by H2** — `feedbackId` prop removed from FollowUpPanel interface (no longer needed; PATCH is fired by parent via `onChipSelect`).
- **L2 resolved** — `reasonChipMutation` now typed `Promise<ReasonChipResponse>`.
- **L3 — `isReasonChipPending` exposed from hook but unused by any consumer.** Not wired (would disable chips mid-flight); kept for possible future use.
- **L4 — `aria-pressed` on one-shot chip buttons is semantically fuzzy**; real fix would be `role="radiogroup"` / `aria-selected`. Minor; not worth refactoring the shadcn Button for this.
- **AC#3 swipe-down gap** → [TD-023](../../docs/tech-debt.md). `FollowUpPanel` is missing swipe-down dismissal; tap-outside + Escape cover the other AC#3 intents.

## Change Log

- 2026-04-17 — Implemented Story 7.5: thumbs-down follow-up panel with 4 reason chips (Layer 2 feedback). Backend PATCH `/api/v1/feedback/{feedback_id}` with ownership-filtered update. Frontend `FollowUpPanel` triggered 300ms after first thumbs-down of the session. Full EN/UK i18n. 5 BE + 12 FE new tests, all green.
- 2026-04-17 — Version bumped from 1.10.0 to 1.11.0 per story completion (MINOR: new user-facing feature).
- 2026-04-17 — Code review fixes: H1 (session-flag race), H2 (panel was modal, now inline), M1 (Escape + autofocus), M2 (id in GET response + hook hydration), M3 (rate-limit PATCH), M4 (backdrop removed). Tests: backend 541 (+1), frontend 443 (+3).
