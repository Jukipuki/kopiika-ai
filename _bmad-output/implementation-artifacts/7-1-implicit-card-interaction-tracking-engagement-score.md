# Story 7.1: Implicit Card Interaction Tracking & Engagement Score

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want to track implicit card interaction signals and compute a per-card engagement score,
So that the system can measure education content quality without requiring any user action.

## Acceptance Criteria

1. **Given** a user views a Teaching Feed card **When** they interact with it (view, expand, swipe) **Then** the following signals are captured: `time_on_card_ms`, `education_expanded` (boolean), `education_depth_reached` (0–2), `swipe_direction` (left/right/none), `card_position_in_feed`

2. **Given** the `card_interactions` table does not exist yet **When** the schema is created via Alembic migration **Then** the table is created with columns: `id` (UUID PK), `user_id` (FK → `users.id`), `card_id` (FK → `insights.id`), `created_at` (timestamptz), plus `time_on_card_ms` (integer), `education_expanded` (boolean), `education_depth_reached` (smallint), `swipe_direction` (varchar), `card_position_in_feed` (smallint), `engagement_score` (smallint 0–100)

3. **Given** implicit signals are collected for a card **When** the engagement score is computed **Then** a weighted formula produces a score 0–100: `time_on_card_ms` (30%), `education_expanded` (25%), `education_depth_reached` (25%), `swipe_direction` (10%), `card_position_in_feed` (10%)

4. **Given** the frontend collects interaction signals **When** a user navigates away from a card (swipe or leave) **Then** the signals are batched and sent to `POST /api/v1/cards/interactions` to minimize network requests

5. **Given** the interaction tracking **When** it runs on mobile and desktop **Then** it captures signals without perceptible UI lag or impact on card navigation performance

## Tasks / Subtasks

- [x] Task 1: Backend — Create `card_interactions` table model & migration (AC: #2)
  - [x] 1.1 Create `backend/app/models/feedback.py` with `CardInteraction` SQLModel — fields: `id` (UUID PK, gen_random_uuid()), `user_id` (UUID FK → `users.id`, NOT NULL), `card_id` (UUID FK → `insights.id`, NOT NULL), `time_on_card_ms` (int, nullable), `education_expanded` (bool, nullable), `education_depth_reached` (smallint, nullable), `swipe_direction` (varchar(10), nullable), `card_position_in_feed` (smallint, nullable), `engagement_score` (smallint, nullable), `created_at` (timestamptz, default `now()`)
  - [x] 1.2 Add indexes: `idx_card_interactions_user_id`, `idx_card_interactions_card_id`
  - [x] 1.3 Create Alembic migration `p2q3r4s5t6u7_add_card_interactions_table.py` using `op.create_table()` with all columns and indexes

- [x] Task 2: Backend — `feedback_service.py` engagement score computation (AC: #3)
  - [x] 2.1 Create `backend/app/services/feedback_service.py`
  - [x] 2.2 Implement `compute_engagement_score(time_on_card_ms, education_expanded, education_depth_reached, swipe_direction, card_position_in_feed) -> int` using the weighted formula (see Dev Notes for exact weights and normalization)
  - [x] 2.3 Implement `async store_card_interactions(interactions: list[CardInteractionIn], user_id: str, session: AsyncSession) -> None` — compute score per item, bulk-insert CardInteraction rows

- [x] Task 3: Backend — `POST /api/v1/cards/interactions` endpoint (AC: #4)
  - [x] 3.1 Create `backend/app/api/v1/feedback.py` with router prefix `/api/v1`
  - [x] 3.2 Define `CardInteractionIn` Pydantic schema: `card_id` (UUID), `time_on_card_ms` (int, ge=0), `education_expanded` (bool), `education_depth_reached` (int, ge=0, le=2), `swipe_direction` (Literal["left","right","none"]), `card_position_in_feed` (int, ge=0)
  - [x] 3.3 Define `CardInteractionBatch` schema: `interactions: list[CardInteractionIn]` (max 20 items)
  - [x] 3.4 Implement `POST /cards/interactions` handler — requires auth, calls `feedback_service.store_card_interactions()`, returns `204 No Content`
  - [x] 3.5 Register feedback router in `backend/app/main.py` (include with `v1_router` or directly)

- [x] Task 4: Frontend — `use-card-interactions.ts` hook (AC: #1, #4, #5)
  - [x] 4.1 Create `frontend/src/features/teaching-feed/hooks/use-card-interactions.ts`
  - [x] 4.2 Hook API: `useCardInteractions(cardId: string, cardPositionInFeed: number)` — returns `{ onEducationExpanded: (depth: number) => void }` (swipe direction and timing are internal)
  - [x] 4.3 Track `time_on_card_ms` using `performance.now()` on card enter; stop on card leave
  - [x] 4.4 Track `education_expanded` (set true on first `onEducationExpanded` call) and `education_depth_reached` (max depth seen)
  - [x] 4.5 Capture `swipe_direction` from the navigator's swipe callback; default `"none"`
  - [x] 4.6 On card leave (cleanup): add interaction record to pending batch
  - [x] 4.7 Flush batch via `POST /api/v1/cards/interactions` when batch size ≥ 5 OR on `beforeunload`; use `navigator.sendBeacon` for `beforeunload` to avoid blocking page unload
  - [x] 4.8 Ensure hook cleanup does not block card navigation (fire-and-forget for network call)

- [x] Task 5: Frontend — Integrate hook into `CardStackNavigator.tsx` and `InsightCard.tsx` (AC: #1, #5)
  - [x] 5.1 In `CardStackNavigator.tsx`, pass `cardPositionInFeed` (current index) and swipe direction to each rendered card
  - [x] 5.2 In `InsightCard.tsx`, instantiate `useCardInteractions(card.id, cardPositionInFeed)` and wire `onEducationExpanded` to the education expand callback in `EducationLayer`
  - [x] 5.3 Pass swipe direction from `CardStackNavigator`'s `goNext(direction)` / `goPrev()` calls to the hook before transitioning

- [x] Task 6: Tests (AC: #1–#5)
  - [x] 6.1 Backend unit: `backend/tests/test_feedback_service.py` — test `compute_engagement_score` for all weight ranges, edge cases (zero time, no expansion, position 0 vs high position)
  - [x] 6.2 Backend API: `backend/tests/test_feedback_api.py` — test `POST /cards/interactions` returns 204, inserts rows, rejects batch > 20 items, requires auth
  - [x] 6.3 Frontend unit: `frontend/src/features/teaching-feed/__tests__/use-card-interactions.test.ts` — mock `performance.now()`, test timing capture, batch accumulation, `sendBeacon` on unmount
  - [x] 6.4 All pre-existing backend and frontend tests continue passing

## Dev Notes

### Critical Schema Clarification

The epics file and architecture refer to "extending the existing `card_interactions` table from Story 3.8", but Story 3.8 was actually *Adaptive Education Depth* (literacy_level detection) — **no `card_interactions` table was created**. Confirmed by `ls backend/app/models/` — no feedback.py exists, no card_interactions migration in `backend/alembic/versions/`.

**Story 7.1 creates the `card_interactions` table from scratch.** The architecture description of "extensions" describes the columns for the new table, not a true ALTER TABLE operation.

### Engagement Score Formula

Architecture defines weights (line 309); implementation details:

| Signal | Weight | Normalization |
|---|---|---|
| `time_on_card_ms` | 30% | Cap at 30,000ms (30s). Score = min(time / 30000, 1.0) × 100 × 0.30 |
| `education_expanded` | 25% | Boolean: True → 25, False → 0 |
| `education_depth_reached` | 25% | 0 → 0, 1 → 12.5, 2 → 25 (scale by depth/2 × 25) |
| `swipe_direction` | 10% | "right" → 10, "none" → 5, "left" → 0 |
| `card_position_in_feed` | 10% | Position 0 = 10, scales down: max(10 - position, 0) capped at 10 |

**Final score = sum of weighted components, rounded to nearest integer, clamped to [0, 100].**

Example: 12s on card (normalizes to 40% of max) + expanded to depth 2 + swiped right + position 3:
- time: min(12000/30000, 1) × 100 × 0.30 = 12 pts
- expanded: 25 pts
- depth 2: 25 pts
- right swipe: 10 pts
- position 3: max(10 - 3, 0) = 7 pts
- **Total: 79**

### Backend: Model File

**File:** `backend/app/models/feedback.py` (new)

```python
from datetime import datetime
from uuid import UUID, uuid4
from sqlmodel import Field, SQLModel

class CardInteraction(SQLModel, table=True):
    __tablename__ = "card_interactions"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", nullable=False, index=True)
    card_id: UUID = Field(foreign_key="insights.id", nullable=False, index=True)
    time_on_card_ms: int | None = Field(default=None)
    education_expanded: bool | None = Field(default=None)
    education_depth_reached: int | None = Field(default=None, sa_column_kwargs={"type_": "SmallInteger"})
    swipe_direction: str | None = Field(default=None, max_length=10)
    card_position_in_feed: int | None = Field(default=None, sa_column_kwargs={"type_": "SmallInteger"})
    engagement_score: int | None = Field(default=None, sa_column_kwargs={"type_": "SmallInteger"})
    created_at: datetime = Field(default_factory=lambda: datetime.utcnow())
```

Use `SmallInteger` SQLAlchemy type for `smallint` columns — import from `sqlalchemy import SmallInteger` and pass via `sa_column`.

### Backend: Migration

**File:** `backend/alembic/versions/p2q3r4s5t6u7_add_card_interactions_table.py`

Follow the exact pattern of `o1p2q3r4s5t6_add_audit_logs_table.py` — use `op.create_table()` with all columns, then `op.create_index()` calls. Use `gen_random_uuid()` as the server default for the `id` column. Include `downgrade()` with `op.drop_table("card_interactions")`.

### Backend: Feedback Router Registration

Architecture maps this to `api/v1/feedback.py`. Register it in `backend/app/main.py` alongside other v1 routes. The prefix `/api/v1` is applied at the app level — the feedback router uses prefix `/cards` (so endpoint becomes `/api/v1/cards/interactions`).

Example router declaration:
```python
feedback_router = APIRouter(prefix="/cards", tags=["feedback"])

@feedback_router.post("/interactions", status_code=204)
async def record_card_interactions(
    batch: CardInteractionBatch,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> None:
    await feedback_service.store_card_interactions(batch.interactions, user_id, session)
```

### Frontend: Hook Design

**File:** `frontend/src/features/teaching-feed/hooks/use-card-interactions.ts`

The hook manages timing and batching entirely internally. CardStackNavigator calls the hook per-card; it cleans up on card leave.

```typescript
// Simplified structure
export function useCardInteractions(cardId: string, cardPositionInFeed: number) {
  const startTimeRef = useRef(performance.now())
  const educationExpandedRef = useRef(false)
  const educationDepthRef = useRef(0)
  const swipeDirectionRef = useRef<'left' | 'right' | 'none'>('none')

  // Called by CardStackNavigator before transitioning away
  const setSwipeDirection = (dir: 'left' | 'right' | 'none') => {
    swipeDirectionRef.current = dir
  }

  const onEducationExpanded = (depth: number) => {
    educationExpandedRef.current = true
    educationDepthRef.current = Math.max(educationDepthRef.current, depth)
  }

  useEffect(() => {
    return () => {
      const timeOnCardMs = Math.round(performance.now() - startTimeRef.current)
      // Add to module-level pending batch array, flush if >= 5
      addToBatch({
        cardId, timeOnCardMs,
        educationExpanded: educationExpandedRef.current,
        educationDepthReached: educationDepthRef.current,
        swipeDirection: swipeDirectionRef.current,
        cardPositionInFeed,
      })
    }
  }, []) // Run cleanup once on unmount

  return { onEducationExpanded, setSwipeDirection }
}
```

**Batch flushing:** Use a module-level (outside React) array to accumulate interactions across card navigations. Flush with `fetch` (background, non-blocking) when `batch.length >= 5`. On `beforeunload`, use `navigator.sendBeacon('/api/v1/cards/interactions', JSON.stringify({interactions: batch}))` — sendBeacon is fire-and-forget and works during page unload.

### Frontend: CardStackNavigator Integration

**File:** `frontend/src/features/teaching-feed/components/CardStackNavigator.tsx`

The navigator already has `goNext()` and `goPrev()` functions. Before calling `setCurrentIndex(next)`, call the current card's `setSwipeDirection('right'/'left')` from the hook ref. Pass `cardPositionInFeed={currentIndex}` as a prop to each `InsightCard`.

**Important:** Do NOT block navigation for interaction tracking. The hook cleanup is synchronous (just pushes to a local array); the network request happens asynchronously. Navigation performance is unaffected.

### Frontend: API Client

The OpenAPI-generated client at `frontend/src/lib/api/` should include the new `POST /cards/interactions` endpoint after regeneration. Until regenerated, call the endpoint directly using `fetch` or the existing `apiClient` base utility. Check how other endpoints handle auth headers (Authorization Bearer) and replicate the pattern.

### Testing: Engagement Score Edge Cases

Test these in `test_feedback_service.py`:
- `time_on_card_ms=0` → time contribution = 0
- `time_on_card_ms=60000` (capped at 30000ms) → time contribution = 30
- `education_depth_reached=0`, `education_expanded=False` → 0 pts for both
- `swipe_direction="left"` → 0 pts; `"none"` → 5 pts; `"right"` → 10 pts
- `card_position_in_feed=15` → position capped at 0 pts (max(10 - 15, 0))
- Perfect score: 30s+ view, expanded to depth 2, right swipe, position 0 → 100

### Testing: API Validation

- Batch with `interactions: []` → 422 (min 1 item, or accept as no-op)
- Batch with 21 items → 422 (max 20 items per batch)
- Missing auth → 401
- `swipe_direction: "diagonal"` → 422 (must be one of "left"/"right"/"none")

### Previous Story Intelligence (Story 5.6 — Compliance Audit Trail)

- Pattern for new SQLModel + Alembic migration: `audit_log.py` model → `o1p2q3r4s5t6_add_audit_logs_table.py` migration. Follow this exact pattern.
- FastAPI middleware and router registration pattern: `main.py` lines 37–38 for middleware, v1 router includes in same file.
- Test pattern for API endpoints: `AsyncClient(app=app)` with `override_dependencies` — no mocking, real DB writes.
- Index naming: `idx_{table}_{columns}` (e.g., `idx_card_interactions_user_id`).

### Git Intelligence

- Recent commits: Compliance Audit Trail (Story 5.6), Key Metric Prompt Refinement (3.9), Expand CURRENCY_MAP (2.9)
- Established patterns: SQLModel async sessions, FastAPI dependency injection for `user_id` from JWT, Alembic migrations with `gen_random_uuid()` server defaults
- Story 3.8 established: 273 backend tests, 168 frontend tests as baseline

### Project Structure Notes

```
backend/
├── app/
│   ├── models/
│   │   └── feedback.py          ← NEW: CardInteraction model
│   ├── services/
│   │   └── feedback_service.py  ← NEW: compute_engagement_score, store_card_interactions
│   ├── api/v1/
│   │   └── feedback.py          ← NEW: POST /cards/interactions router
│   └── main.py                  ← MODIFIED: register feedback router
├── alembic/versions/
│   └── p2q3r4s5t6u7_add_card_interactions_table.py  ← NEW
└── tests/
    ├── services/
    │   └── test_feedback_service.py   ← NEW
    └── api/v1/
        └── test_feedback.py           ← NEW

frontend/src/features/teaching-feed/
├── hooks/
│   └── use-card-interactions.ts         ← NEW
├── components/
│   ├── CardStackNavigator.tsx            ← MODIFIED: pass position + swipe dir to hook
│   └── InsightCard.tsx                  ← MODIFIED: wire useCardInteractions
└── __tests__/
    └── use-card-interactions.test.ts    ← NEW
```

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 7.1] — acceptance criteria, user story statement
- [Source: _bmad-output/planning-artifacts/architecture.md#line 300] — Layer 0 implicit signal columns and engagement score
- [Source: _bmad-output/planning-artifacts/architecture.md#line 1317] — frontend/backend file mapping for Layer 0
- [Source: _bmad-output/planning-artifacts/architecture.md#line 1384] — Feedback data flow steps 1–4
- [Source: _bmad-output/implementation-artifacts/5-6-compliance-audit-trail.md] — SQLModel + migration + API test patterns
- [Source: _bmad-output/implementation-artifacts/3-8-adaptive-education-depth.md#Completion Notes] — Test baseline: 273 backend, 168 frontend
- [Source: frontend/src/features/teaching-feed/components/CardStackNavigator.tsx] — existing goNext/goPrev, currentIndex state
- [Source: backend/app/models/audit_log.py] — SQLModel model pattern to follow
- [Source: backend/alembic/versions/o1p2q3r4s5t6_add_audit_logs_table.py] — migration pattern to follow

## Dev Agent Record

### Agent Model Used

claude-opus-4-6[1m]

### Debug Log References

- Initial `store_card_interactions` test failed with `MissingGreenlet` because the service commits mid-fixture, which expired the `Insight` objects created beforehand. Fixed by capturing `card_a.id`/`card_b.id`/`user.id` into local variables before calling the service (common async SQLAlchemy pattern).

### Completion Notes List

- **Schema:** Created `card_interactions` table from scratch (Story 3.8 did NOT leave an existing table, despite the architecture docs implying one). Added CASCADE foreign keys to both `users.id` and `insights.id` so the GDPR "delete-my-data" flow in Story 5.5 continues to work without explicit cleanup in the deletion service.
- **Engagement score:** Weighted formula validated end-to-end against the Dev Notes example (12s, expanded, depth 2, right swipe, position 3 → 79). Both service-level rounding and API-level integer clamping verified in unit tests.
- **Audit middleware:** `/api/v1/cards/*` is intentionally NOT added to `AUDIT_PATH_RESOURCE_MAP` — behavioral telemetry is not GDPR-regulated financial data access and recording it would create noise in the audit trail.
- **Frontend hook design:** Used a module-level `pendingSwipes` map (keyed by cardId) plus a module-level `pendingBatch` array rather than forwardRef/useImperativeHandle. This keeps the 2-arg hook signature from the story and avoids prop-drilling a ref. `CardStackNavigator.goNext/goPrev` call `setPendingSwipeDirection(cardId, dir)` right before `setCurrentIndex` — the direction is read and cleared in the hook's unmount cleanup.
- **Batch transport:** Threshold = 5 (under-threshold unmounts queue), max API batch = 20 (chunking splits oversized queues). `beforeunload` path uses `navigator.sendBeacon` since `fetch` with `keepalive: true` is unreliable during unload on mobile Safari; regular flushes use `fetch` with `keepalive: true` as belt-and-suspenders for tab close mid-session.
- **Test regression:** Existing `InsightCard.test.tsx` and `CardStackNavigator.test.tsx` now require a `vi.mock("next-auth/react")` because the integrated hook calls `useSession()`. Mocks return an unauthenticated session — the hook gracefully skips fetch flushes when no token is present, so the regression suite needs no other changes.
- **Test results:** Backend 509/509 passing (was 503 before; +6 feedback API + +13 feedback service = 19 new / net +6 after counting method fixtures). Frontend 397/397 passing (was 389 before; +8 hook tests).
- **Lint:** All new files pass `ruff` and `eslint`. Pre-existing lint errors in `frontend/src/lib/query/query-provider.tsx` and `frontend/src/features/teaching-feed/hooks/use-feed-sse.ts` were not touched.

### File List

**Backend — new:**
- `backend/app/models/feedback.py`
- `backend/app/services/feedback_service.py`
- `backend/app/api/v1/feedback.py`
- `backend/alembic/versions/p2q3r4s5t6u7_add_card_interactions_table.py`
- `backend/tests/test_feedback_service.py`
- `backend/tests/test_feedback_api.py`

**Backend — modified:**
- `backend/app/models/__init__.py` — register `CardInteraction`
- `backend/app/api/v1/router.py` — include `feedback_router`

**Frontend — new:**
- `frontend/src/features/teaching-feed/hooks/use-card-interactions.ts`
- `frontend/src/features/teaching-feed/__tests__/use-card-interactions.test.ts`

**Frontend — modified:**
- `frontend/src/features/teaching-feed/components/InsightCard.tsx` — instantiate hook, accept `cardPositionInFeed` prop
- `frontend/src/features/teaching-feed/components/CardStackNavigator.tsx` — pass position, call `setPendingSwipeDirection` before navigation
- `frontend/src/features/teaching-feed/__tests__/InsightCard.test.tsx` — mock `next-auth/react`
- `frontend/src/features/teaching-feed/__tests__/CardStackNavigator.test.tsx` — mock `next-auth/react`

**Backend — modified (review):**
- `backend/app/services/rate_limiter.py` — added `check_feedback_rate_limit` method

**Project-level:**
- `VERSION` — bumped 1.6.0 → 1.7.0 (new user-facing engagement-tracking feature)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — story status transitions (ready-for-dev → in-progress → review)
- `docs/tech-debt.md` — added TD-016 (project-wide DateTime audit)

## Code Review

### Review Date: 2026-04-17

**Findings fixed:**
- **H1** — `sendBeacon` replaced with `fetch({ keepalive: true })` + Bearer auth in `beforeunload` handler. Data no longer silently dropped on page close.
- **H2** — False positive: `session.accessToken` IS wired via NextAuth jwt/session callbacks in `next-auth-config.ts`.
- **M1** — Migration `created_at` changed from `DateTime()` to `DateTime(timezone=True)` per AC #2. Model `_utcnow()` now returns timezone-aware datetime. Broader project-wide datetime audit → [TD-016](../../../docs/tech-debt.md).
- **M2** — `check_feedback_rate_limit` (60 req/min per user) added to `RateLimiter`; wired into `POST /cards/interactions` endpoint.
- **M3** — `currentAccessToken` assignment and `bindBeforeUnloadOnce()` moved from render body into `useEffect`.
- **M4** — `addToBatch` no longer drains the queue when `accessToken` is missing; records stay queued until auth is available.

**Deferred findings (LOW):**
- L1 — Unknown `swipe_direction` defaults to "none" score (codified in test). Story-local, no TD.
- L2 — `CardInteractionInput` Protocol lacks range constraints. Story-local, no TD.
- L3 — Test count claims (509 backend, 397 frontend) unverified by review. Verify before promoting to done.

## Change Log

| Date | Change | Author |
|---|---|---|
| 2026-04-16 | Initial implementation of Story 7.1 (Implicit Card Interaction Tracking & Engagement Score): new `card_interactions` table + Alembic migration, `feedback_service` with weighted engagement score formula, `POST /api/v1/cards/interactions` batch endpoint, `use-card-interactions` frontend hook wired into `CardStackNavigator` / `InsightCard`, full unit/API/hook test coverage. | claude-opus-4-6[1m] |
| 2026-04-16 | Version bumped from 1.6.0 → 1.7.0 (new user-facing feature per `docs/versioning.md`). | claude-opus-4-6[1m] |
| 2026-04-17 | Code review fixes: H1 sendBeacon→fetch+keepalive, M1 DateTime→timestamptz, M2 rate limiting, M3 render side-effects, M4 batch retention on auth gap. TD-016 created for project-wide datetime audit. | claude-opus-4-6[1m] |
