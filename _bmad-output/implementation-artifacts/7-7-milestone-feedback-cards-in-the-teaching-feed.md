# Story 7.7: Milestone Feedback Cards in the Teaching Feed

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want to see occasional feedback cards at the end of my Teaching Feed at key milestones,
So that I can share how the product is working for me without it feeling like an interruption.

## Acceptance Criteria

1. **Given** I have completed my 3rd upload (one-time milestone) **When** I view the Teaching Feed **Then** a milestone feedback card appears at the end of the feed: "How's Kopiika working for you?" with 3 emoji faces (happy/neutral/sad) and an optional text field

2. **Given** my Financial Health Score has changed significantly (+/- 5 points since last check) **When** I view the Teaching Feed **Then** a milestone feedback card appears at the end: "Your score changed! Does this feel accurate?" with Yes/No options and optional text

3. **Given** a milestone feedback card **When** I interact with it **Then** it uses the same card component, swipe gestures, and visual design as education cards — no new UI pattern

4. **Given** I swipe away or dismiss a milestone feedback card **When** the dismissal is recorded **Then** that specific milestone card never appears again (tracked via `feedback_responses` table unique constraint on `user_id + feedback_card_type`)

5. **Given** a `feedback_responses` table created via Alembic migration **When** a response is stored **Then** it contains: `id` (UUID), `user_id` (FK → users), `feedback_card_type` (varchar: `'milestone_3rd_upload'` or `'health_score_change'`), `response_value` (varchar), `free_text` (nullable), `created_at`

6. **Given** the feedback card frequency cap logic **When** determining whether to show a feedback card **Then** max 1 feedback card per session and max 1 per month are enforced (per-session cap client-side; per-month cap via `created_at` check against `feedback_responses`)

7. **Given** the Health Score change milestone card **When** it checks for significant change **Then** it depends on Epic 4's `FinancialHealthScore` data — if fewer than 2 score records exist for the user, this trigger is skipped

## Tasks / Subtasks

- [x] Task 1: Backend — New `FeedbackResponse` model and Alembic migration (AC: #4, #5)
  - [x] 1.1 Create `backend/app/models/feedback_response.py` with `FeedbackResponse` SQLModel:
    - `id: UUID` (gen_random_uuid() default)
    - `user_id: UUID` (FK → users.id, ON DELETE CASCADE, indexed)
    - `feedback_card_type: str` (varchar 50, not null)
    - `response_value: str` (varchar 50, not null — stores emoji key, "yes", "no", or "dismissed")
    - `free_text: Optional[str]` (nullable)
    - `created_at: datetime` (server default = now())
    - Unique constraint on `(user_id, feedback_card_type)` — each card type shown at most once
  - [x] 1.2 Add `FeedbackResponse` to `backend/app/models/__init__.py` exports
  - [x] 1.3 Generate Alembic migration: `alembic revision --autogenerate -m "add_feedback_responses_table"` — verify it creates `feedback_responses` table, the unique constraint, and the `user_id` index
  - [x] 1.4 Apply migration: `alembic upgrade head` — applied successfully. Migration chain: `h4i5j6k7l8m9 → i5j6k7l8m9n0 (langgraph) → … → q3r4s5t6u7v8 (card_feedback) → r4s5t6u7v8w9 (feedback_responses)`. Required an incidental fix to `i5j6k7l8m9n0_add_langgraph_checkpoint_tables.py` (pre-existing): added `autocommit=True` to the psycopg connection since `PostgresSaver.setup()` runs `CREATE INDEX CONCURRENTLY` which cannot execute inside a transaction block. Verified via information_schema: `feedback_responses` table + `uq_feedback_response_user_type` unique constraint + `ix_feedback_response_user_id` index all present.

- [x] Task 2: Backend — Milestone feedback service (AC: #1, #2, #6, #7)
  - [x] 2.1 Create `backend/app/services/milestone_feedback_service.py`
  - [x] 2.2 `get_pending_milestone_cards(user_id: UUID, db: AsyncSession) -> list[dict]`:
    - Query `feedback_responses` for user — build a set of already-responded card types
    - Check 3rd upload trigger via `processing_jobs` (status = `completed`) — on this project uploads create a `ProcessingJob` row rather than a dedicated `upload_jobs` table
    - Check health score trigger via `FinancialHealthScore` ordered by `calculated_at desc limit 2`
    - Monthly frequency cap: any `feedback_responses` row within 30 days suppresses the card
    - Return list of `{"card_type": str, "variant": str}` dicts; at most 1 card (priority: `milestone_3rd_upload` > `health_score_change`)
  - [x] 2.3 `save_milestone_response(...) -> FeedbackResponse`: insert → on `IntegrityError` rollback + reload existing row → return detached snapshot (constructor-based, matches `feedback_service.py` pattern)

- [x] Task 3: Backend — Milestone feedback API endpoints (AC: #1, #2, #4, #5, #6)
  - [x] 3.1 Create `backend/app/api/v1/milestone_feedback.py` with router prefix `/milestone-feedback` (`/api/v1/milestone-feedback` once mounted under `v1_router`)
  - [x] 3.2 `MilestoneFeedbackCardOut` pydantic model with camelCase alias_generator
  - [x] 3.3 `MilestoneResponseIn` pydantic model with `card_type: Literal[…]` (422 on unknown), `response_value`, `free_text: Optional[str]`, camelCase alias_generator
  - [x] 3.4 `GET /api/v1/milestone-feedback/pending` — auth required, returns `{"cards": [...]}`
  - [x] 3.5 `POST /api/v1/milestone-feedback/respond` — auth required, validates card_type, returns `{"ok": true}`
  - [x] 3.6 Register router — added to `backend/app/api/v1/router.py` (project registers v1 routers there rather than directly in `main.py`)

- [x] Task 4: Backend — Tests (AC: #1, #2, #4, #5, #6, #7)
  - [x] 4.1 Create `backend/tests/test_milestone_feedback_api.py`
  - [x] 4.2 `TestGetPendingMilestoneCards`: all 7 listed scenarios + `test_requires_auth`
  - [x] 4.3 `TestPostMilestoneResponse`: all 4 listed scenarios + `test_requires_auth`

- [x] Task 5: Frontend — `MilestoneFeedbackCard.tsx` component (AC: #1, #2, #3)
  - [x] 5.1 Create `frontend/src/features/teaching-feed/components/MilestoneFeedbackCard.tsx`
  - [x] 5.2 Props: `cardType`, `onRespond`, `onDismiss`, `isSubmitting`
  - [x] 5.3 `emoji_rating` variant — 3 emoji buttons with `data-testid`s + textarea + Submit + Skip
  - [x] 5.4 `yes_no` variant — Yes/No buttons with `data-testid`s + textarea + Submit + Skip
  - [x] 5.5 Skip → `onDismiss()`; FeedContainer forwards as `submitResponse({ responseValue: "dismissed" })`
  - [x] 5.6 Reused existing `<Card>` / `<CardHeader>` / `<CardContent>` shell — no new CSS classes; severity badge omitted
  - [x] 5.7 Textarea is optional — can submit with only a selected value
  - [x] 5.8 Submit is disabled until a value is selected (`emoji-happy/neutral/sad` or `response-yes/no`)
  - [x] 5.9 Swipe-to-dismiss (AC #3): card wrapped in `motion.div` with `drag="x"`, matching `CardStackNavigator`'s 80px threshold and `dragElastic` tuning. Horizontal drag beyond the threshold calls `onDismiss()`; `useReducedMotion()` disables drag for accessibility, leaving the Skip button as the sole affordance.

- [x] Task 6: Frontend — `useMilestoneFeedback.ts` hook (AC: #4, #6)
  - [x] 6.1 Create `frontend/src/features/teaching-feed/hooks/use-milestone-feedback.ts`
  - [x] 6.2 `useQuery` for `GET /milestone-feedback/pending`, `staleTime: 0`, gated on `!!token`
  - [x] 6.3 Module-level `_milestoneSession.hasShownCard`; returns `null` when set
  - [x] 6.4 `useMutation` for POST `/respond`; on success: set flag + invalidate query
  - [x] 6.5 Exports `{ pendingCard, submitResponse, isPending }`

- [x] Task 7: Frontend — Integrate into `FeedContainer.tsx` (AC: #1, #2, #3)
  - [x] 7.1 Imported `useMilestoneFeedback` + `MilestoneFeedbackCard`
  - [x] 7.2 Milestone card renders after `<CardStackNavigator>` when `pendingCard && !isStreaming`
  - [x] 7.3 `onRespond` → `submitResponse({ cardType, responseValue, freeText })`
  - [x] 7.4 `onDismiss` → `submitResponse({ cardType, responseValue: "dismissed" })`
  - [x] 7.5 Milestone card rendered in `FeedContainer` after the stack; `CardStackNavigator.tsx` not modified

- [x] Task 8: Frontend — i18n (AC: #1, #2)
  - [x] 8.1 Added `feed.milestoneFeedback` keys to `frontend/messages/en.json` (keys nested under `feed` to match existing `reportIssue` / `followUpPanel` siblings — the story text referenced `teachingFeed.milestoneFeedback`, but this codebase uses `feed.*`)
  - [x] 8.2 Mirrored all keys in `frontend/messages/uk.json`

- [x] Task 9: Frontend — Tests (AC: #1–#7)
  - [x] 9.1 `MilestoneFeedbackCard.test.tsx` — 9 tests covering both variants, submit, skip, free-text, disabled state, swipe-dismiss-at-threshold, and no-dismiss-below-threshold
  - [x] 9.2 `use-milestone-feedback.test.tsx` — 5 tests covering fetch, empty state, session cap, POST body, and session-flag-set on success

## Dev Notes

### Architecture Overview

Story 7.7 adds a **Layer 3 feedback mechanism** — milestone-triggered cards appended to the end of the Teaching Feed. These are one-time, contextual prompts that appear at significant lifecycle events.

**Key architectural decisions:**
- **No mid-feed injection** — milestone card always at the tail (after swipeable card stack exhausted). This avoids touching `CardStackNavigator.tsx`.
- **"Never again" via DB unique constraint** — `(user_id, feedback_card_type)` unique on `feedback_responses` table. Once any response (including "dismissed") is stored, the card is permanently suppressed for that user. No fragile front-end flag.
- **Monthly frequency cap** — server-side: check `feedback_responses.created_at >= now() - 30 days` in `get_pending_milestone_cards`. Client-side session cap in module-level `_milestoneSession` flag (same pattern as `_sessionFlags` in `CardFeedbackBar.tsx`).
- **Health Score dependency** — if user has < 2 `FinancialHealthScore` rows, skip that trigger entirely. Epic 4 data is used read-only.

### Backend: New `feedback_responses` Table

**Model** (`backend/app/models/feedback_response.py`):
```python
class FeedbackResponse(SQLModel, table=True):
    __tablename__ = "feedback_responses"
    __table_args__ = (
        UniqueConstraint("user_id", "feedback_card_type", name="uq_feedback_response_user_type"),
        Index("ix_feedback_response_user_id", "user_id"),
    )
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", ondelete="CASCADE", nullable=False)
    feedback_card_type: str = Field(max_length=50, nullable=False)
    response_value: str = Field(max_length=50, nullable=False)
    free_text: Optional[str] = Field(default=None, nullable=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

The previous migration ID to chain from: `q3r4s5t6u7v8` (`add_card_feedback_table`). The new migration `down_revision` must reference `q3r4s5t6u7v8`.

### Backend: Upload Count Query

The 3rd upload trigger needs the upload jobs table. Use `ProcessingJob` model (check `backend/app/models/` — likely `processing_job.py` or `upload_job.py`). Query pattern:
```python
from sqlalchemy import select, func
count = await db.scalar(
    select(func.count()).where(
        ProcessingJob.user_id == user_id,
        ProcessingJob.status == "completed"
    )
)
```
If the model name or status field differs, adjust accordingly.

### Backend: Health Score Delta Query

```python
from sqlalchemy import select
scores = (await db.execute(
    select(FinancialHealthScore.score)
    .where(FinancialHealthScore.user_id == user_id)
    .order_by(FinancialHealthScore.calculated_at.desc())
    .limit(2)
)).scalars().all()

if len(scores) >= 2 and abs(scores[0] - scores[1]) >= 5:
    # trigger health_score_change card
```

### Backend: Detached Snapshot Pattern

Follow the pattern in `feedback_service.py:299-329` — after inserting, refresh the object and call `db.expunge()` to prevent `MissingGreenlet` errors when the session is closed before serialization:
```python
await db.refresh(response)
db.expunge(response)
return response
```

### Backend: Router Registration

In `backend/app/main.py`, follow existing pattern:
```python
from app.api.v1.milestone_feedback import router as milestone_feedback_router
app.include_router(milestone_feedback_router, prefix="/api/v1")
```

### Frontend: MilestoneFeedbackCard Visual Pattern

Do NOT create new CSS classes. Reuse the `InsightCard` outer shell pattern from `frontend/src/features/teaching-feed/components/InsightCard.tsx`. The card should visually look like a sibling of existing insight cards. Omit severity badge and `CardFeedbackBar`. Example outer shell:
```tsx
<div className="rounded-2xl shadow-md bg-white p-4 flex flex-col gap-3">
  <h3 className="text-lg font-semibold">{title}</h3>
  {/* emoji buttons OR yes/no buttons */}
  <textarea ... />
  <div className="flex justify-between">
    <button onClick={onSkip}>{t("skip")}</button>
    <button onClick={onSubmit} disabled={!selectedValue}>{t("submit")}</button>
  </div>
</div>
```

### Frontend: Session Cap Pattern

Mirror the `_sessionFlags` module-level object pattern from `CardFeedbackBar.tsx`:
```typescript
// Module-level — persists for browser tab lifetime
const _milestoneSession = { hasShownCard: false };

export function useMilestoneFeedback() {
  const { data } = useQuery(...);
  const rawCard = data?.cards?.[0] ?? null;
  const pendingCard = _milestoneSession.hasShownCard ? null : rawCard;
  // ...
}
```

After the card is shown (either responded or dismissed), set `_milestoneSession.hasShownCard = true`.

### Frontend: FeedContainer Integration Point

`FeedContainer.tsx` currently renders the card stack inside a `<div>`. The milestone card goes after the `<CardStackNavigator>` but only when the feed has loaded and the stack is empty (or when all cards have been swiped). If the feed still has cards, do not show the milestone card mid-session. A simple approach: render the milestone card below the card stack unconditionally when `pendingCard` is defined — the user reaches it naturally by swiping through all education cards.

### Frontend: camelCase ↔ snake_case

The backend uses `alias_generator = to_camel` (Pydantic setting). Verify in `feedback.py` — `CardVoteIn` uses this pattern. Mirror it in `MilestoneResponseIn` so the frontend sends `cardType`, `responseValue`, `freeText` in JSON and the backend model aliases them from snake_case fields.

### Project Structure Notes

```
backend/
├── app/models/
│   └── feedback_response.py         ← NEW: FeedbackResponse SQLModel
├── app/models/__init__.py            ← MODIFIED: export FeedbackResponse
├── app/services/
│   └── milestone_feedback_service.py ← NEW: get_pending + save_response
├── app/api/v1/
│   └── milestone_feedback.py         ← NEW: GET /pending + POST /respond
├── app/main.py                        ← MODIFIED: register milestone_feedback_router
├── alembic/versions/
│   └── <hash>_add_feedback_responses_table.py ← NEW: migration
tests/
└── test_milestone_feedback_api.py    ← NEW: 11 tests

frontend/src/features/teaching-feed/
├── components/
│   ├── MilestoneFeedbackCard.tsx     ← NEW: emoji_rating + yes_no variants
│   └── FeedContainer.tsx             ← MODIFIED: render milestone card at end
├── hooks/
│   └── use-milestone-feedback.ts     ← NEW: query + mutation + session cap
├── __tests__/
│   ├── MilestoneFeedbackCard.test.tsx ← NEW: 6 tests
│   └── use-milestone-feedback.test.tsx ← NEW: 5 tests

frontend/messages/
├── en.json                           ← MODIFIED: add milestoneFeedback keys (10)
└── uk.json                           ← MODIFIED: add milestoneFeedback keys (10)
```

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 7.7] — user story, all 7 acceptance criteria, `feedback_responses` table schema
- [Source: _bmad-output/planning-artifacts/epics.md#FR52] — "System can display milestone feedback cards at end of Teaching Feed after 3rd upload and after significant Health Score change"
- [Source: _bmad-output/planning-artifacts/epics.md#FR53] — "Milestone feedback cards use same card component and gestures as education cards"
- [Source: backend/app/models/feedback.py] — `CardFeedback` and `CardInteraction` model patterns (unique constraints, indices, field types)
- [Source: backend/app/models/financial_health_score.py:13-31] — `FinancialHealthScore` model fields for health score delta query
- [Source: backend/app/services/feedback_service.py:107-166] — upsert pattern with IntegrityError rollback to follow for `save_milestone_response`
- [Source: backend/app/services/feedback_service.py:299-329] — detached snapshot pattern (expunge after refresh)
- [Source: backend/app/api/v1/feedback.py:60-82] — `CardVoteIn/Out` camelCase alias_generator pattern for `MilestoneResponseIn`
- [Source: backend/alembic/versions/q3r4s5t6u7v8_add_card_feedback_table.py] — latest migration to chain `down_revision` from
- [Source: frontend/src/features/teaching-feed/components/InsightCard.tsx:23-74] — card outer shell CSS to reuse in `MilestoneFeedbackCard.tsx`
- [Source: frontend/src/features/teaching-feed/components/FeedContainer.tsx:34-148] — integration point for milestone card (after `<CardStackNavigator>`)
- [Source: frontend/src/features/teaching-feed/components/CardFeedbackBar.tsx] — `_sessionFlags` module-level session cap pattern to replicate in `useMilestoneFeedback.ts`
- [Source: frontend/src/features/teaching-feed/hooks/use-card-feedback.ts:32-131] — `useQuery` + `useMutation` pattern with auth token dependency and query invalidation
- [Source: _bmad-output/implementation-artifacts/7-6-occasional-thumbs-up-follow-up.md] — test baseline: backend 544 passing, frontend 456 passing (47 files)

## Dev Agent Record

### Agent Model Used

claude-opus-4-7

### Debug Log References

- Backend regression suite: `557 passed, 2 warnings in 172.39s` (`backend/ && python -m pytest`)
- New milestone tests: `13 passed in 1.27s` (`pytest tests/test_milestone_feedback_api.py`)
- Frontend full suite: `Test Files 49 passed (49), Tests 468 passed (468)` (`npm test -- --run`)
- New frontend tests: 7 (`MilestoneFeedbackCard.test.tsx`) + 5 (`use-milestone-feedback.test.tsx`) — all passing
- `alembic upgrade head` now runs clean end-to-end. An incidental fix to `i5j6k7l8m9n0_add_langgraph_checkpoint_tables.py` (pre-existing) was required: added `autocommit=True` to the psycopg `Connection.connect()` so that langgraph's internal `PostgresSaver.setup()` — which runs `CREATE INDEX CONCURRENTLY` — can execute outside a transaction. Safe because all statements in `PostgresSaver.MIGRATIONS` use `IF NOT EXISTS`.

### Completion Notes List

- Implemented all 9 tasks and all 7 acceptance criteria.
- Two deviations from story text, both documented inline above:
  1. Router registration: project pattern registers v1 routers in `backend/app/api/v1/router.py`, not directly in `backend/app/main.py`. Followed the project pattern.
  2. Upload-count query: the story mentions `upload_jobs`; the codebase uses `processing_jobs` (`ProcessingJob`). Used the correct existing model.
  3. i18n key namespace: story referenced `teachingFeed.milestoneFeedback`; the messages file uses top-level `feed.*` (sibling of `reportIssue`, `followUpPanel`). Kept consistent with existing pattern.
- FeedContainer tests required adding a `useMilestoneFeedback` mock to prevent the new `fetch` call from consuming queued `mockResolvedValueOnce` responses — 3 regressions fixed that way.
- Session cap: module-level `_milestoneSession.hasShownCard` flag persists for the browser tab (reset on page reload), same pattern as `_sessionFlags` in `CardFeedbackBar.tsx`.
- "Never again" guarantee: `(user_id, feedback_card_type)` unique constraint on `feedback_responses` — any response value (including `"dismissed"`) suppresses the card permanently. `IntegrityError` on duplicate insert is caught and returns the existing row (idempotent).
- Frequency cap: server-side check — any `feedback_responses` row `created_at >= now() - 30 days` suppresses all milestone cards (handles timezone-aware Postgres and naive SQLite).
- Backend lint (`ruff`) passes for all new files. Pre-existing ruff/eslint errors in unrelated files were not addressed.

### File List

**Backend (new)**
- `backend/app/models/feedback_response.py`
- `backend/app/services/milestone_feedback_service.py`
- `backend/app/api/v1/milestone_feedback.py`
- `backend/alembic/versions/r4s5t6u7v8w9_add_feedback_responses_table.py`
- `backend/tests/test_milestone_feedback_api.py`

**Backend (modified)**
- `backend/app/models/__init__.py` — export `FeedbackResponse`
- `backend/app/api/v1/router.py` — register `milestone_feedback_router`
- `backend/alembic/versions/i5j6k7l8m9n0_add_langgraph_checkpoint_tables.py` — add `autocommit=True` so `alembic upgrade head` can succeed (pre-existing bug — `PostgresSaver.setup()` runs `CREATE INDEX CONCURRENTLY`)

**Frontend (new)**
- `frontend/src/features/teaching-feed/components/MilestoneFeedbackCard.tsx`
- `frontend/src/features/teaching-feed/hooks/use-milestone-feedback.ts`
- `frontend/src/features/teaching-feed/__tests__/MilestoneFeedbackCard.test.tsx`
- `frontend/src/features/teaching-feed/__tests__/use-milestone-feedback.test.tsx`

**Frontend (modified)**
- `frontend/src/features/teaching-feed/components/FeedContainer.tsx` — wire up hook and render card after stack
- `frontend/src/features/teaching-feed/__tests__/FeedContainer.test.tsx` — mock `useMilestoneFeedback` hook
- `frontend/messages/en.json` — add `feed.milestoneFeedback` block
- `frontend/messages/uk.json` — add Ukrainian translations for `feed.milestoneFeedback`

**Repo**
- `VERSION` — bumped 1.12.0 → 1.13.0 (MINOR: new user-facing milestone feedback cards)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — updated `7-7-milestone-feedback-cards-in-the-teaching-feed: ready-for-dev → in-progress → review`
- `.gitignore` — added `*.db` / `*.db-journal` so stray SQLite files from local alembic runs stay untracked (code-review M3 fix)

### Change Log

- 2026-04-17 — Story 7.7 implemented end-to-end (backend model + migration + service + API + tests; frontend component + hook + i18n + integration + tests). All 7 ACs satisfied. Version bumped 1.12.0 → 1.13.0 per versioning policy (new user-facing feature).
- 2026-04-17 — Code-review fix (H1, AC #3): `MilestoneFeedbackCard` now wrapped in a `motion.div` with horizontal drag matching `CardStackNavigator`'s 80px threshold. Swiping the card past the threshold in either direction calls `onDismiss`. `useReducedMotion()` disables drag for users who prefer reduced motion. Added 2 frontend tests covering both threshold boundaries; full suite 470 passing.
- 2026-04-17 — Code-review fix (H2): added `Depends(get_rate_limiter)` + `check_feedback_rate_limit` to POST `/api/v1/milestone-feedback/respond`, matching the convention used across `feedback.py` endpoints. Existing tests already mock `get_rate_limiter`, so no test changes needed.
- 2026-04-17 — Code-review fix (M1): `FeedbackResponse.user_id` Field now declares `ondelete="CASCADE"`, aligning the SQLModel-generated schema (used in SQLite test fixtures) with the Alembic migration. No drift between `metadata.create_all` and the production Postgres DDL.
- 2026-04-17 — Code-review fix (M2): `test_idempotent_second_response` now verifies that after the duplicate "sad" POST the stored `response_value` is still "happy" — i.e. the first response wins. The original test only checked status codes.
- 2026-04-17 — Code-review fix (M3): added `*.db` and `*.db-journal` to `.gitignore`. The stray `test.db` created by local `alembic upgrade head` won't be accidentally committed in future `git add .` sweeps.
- 2026-04-17 — Code-review fix (L1): simplified `save_milestone_response` — on IntegrityError we rollback and let the first-writer-wins semantics stand. Removed the unused detached-snapshot construction (the API route only returns `{"ok": true}`). Signature now returns `None`.
- 2026-04-17 — Code-review fix (L2): removed the unused `ALLOWED_CARD_TYPES` frozenset; card-type validation lives on `MilestoneResponseIn.card_type: Literal[...]`.
- 2026-04-17 — Code-review fix (L4): auth tests now assert `status_code == 401` (was `in (401, 403)`), matching the actual behavior of `get_current_user_payload`.
