# Story 7.2: Thumbs Up/Down on Teaching Feed Cards

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want to rate any Teaching Feed card with thumbs up or thumbs down,
So that I can signal whether an insight was helpful.

## Acceptance Criteria

1. **Given** I am viewing a Teaching Feed card **When** the card has been visible for 2+ seconds **Then** two small, muted thumb icons (up/down) appear in the bottom-right corner of the card

2. **Given** I tap the thumbs-up or thumbs-down icon **When** the vote is registered **Then** the selected icon fills/highlights, I receive brief haptic feedback (mobile), and the vote is sent to `POST /api/v1/feedback/cards/{cardId}/vote` with `{"vote": "up"}` or `{"vote": "down"}` → 201 response with `{ "id": "uuid", "cardId": "uuid", "vote": "up", "createdAt": "..." }`

3. **Given** a `card_feedback` table is created via Alembic migration **When** a vote is stored **Then** it contains: `id` (UUID PK), `user_id` (FK → users.id), `card_id` (FK → insights.id), `card_type` (varchar 50), `vote` (varchar 10, CHECK IN ('up','down'), nullable), `reason_chip` (varchar 50, nullable), `free_text` (text, nullable), `feedback_source` (varchar 20, NOT NULL, default 'card_vote'), `issue_category` (varchar 30, nullable), `created_at` (timestamptz, default now()); with unique constraint on `(user_id, card_id, feedback_source)` preventing duplicate votes

4. **Given** I have previously voted on a card **When** I return to that card **Then** my vote state is visible (filled icon) loaded via `GET /api/v1/feedback/cards/{cardId}` → `{ "vote": "up", "reasonChip": null, "createdAt": "..." }` or 404 if no vote yet

5. **Given** I tap the opposite thumb icon on a card I already voted on **When** the update is processed **Then** my vote is changed (not duplicated) and the UI reflects the new state

6. **Given** the thumb icons render **When** a user interacts via keyboard **Then** they meet WCAG 2.1 AA: keyboard accessible (button elements), screen reader labeled (`aria-label="Rate this insight helpful"` / `aria-label="Rate this insight not helpful"`), `aria-pressed` reflects current vote state, visible focus indicators

## Tasks / Subtasks

- [x] Task 1: Backend — Add `CardFeedback` model to `backend/app/models/feedback.py` (AC: #3)
  - [x] 1.1 Append `CardFeedback` SQLModel class to existing `backend/app/models/feedback.py`; reuse `_utcnow()` already defined there
  - [x] 1.2 Fields: `id` (UUID PK, gen uuid4), `user_id` (UUID FK → users.id, NOT NULL, index=True), `card_id` (UUID FK → insights.id, NOT NULL, index=True), `card_type` (str, max_length=50, NOT NULL), `vote` (Optional[str], max_length=10, nullable), `reason_chip` (Optional[str], max_length=50, nullable), `free_text` (Optional[str], nullable), `feedback_source` (str, max_length=20, NOT NULL, default="card_vote"), `issue_category` (Optional[str], max_length=30, nullable), `created_at` (datetime, default=_utcnow, sa_type=DateTime(timezone=True))
  - [x] 1.3 Register `CardFeedback` in `backend/app/models/__init__.py`

- [x] Task 2: Backend — Alembic migration for `card_feedback` table (AC: #3)
  - [x] 2.1 Create `backend/alembic/versions/q3r4s5t6u7v8_add_card_feedback_table.py` following exact pattern of `p2q3r4s5t6u7_add_card_interactions_table.py`
  - [x] 2.2 Use `op.create_table()` with all columns; use `sa.CheckConstraint("vote IN ('up', 'down')", name="ck_card_feedback_vote")` for the vote column
  - [x] 2.3 Create indexes: `idx_card_feedback_user_id`, `idx_card_feedback_card_id`, `idx_card_feedback_card_type_vote` (on card_type + vote for aggregation)
  - [x] 2.4 Create unique constraint: `uq_card_feedback_user_card_source` on `(user_id, card_id, feedback_source)` via `op.create_index(..., unique=True)` or `UniqueConstraint`
  - [x] 2.5 Include `downgrade()` with `op.drop_table("card_feedback")`

- [x] Task 3: Backend — Feedback service functions (AC: #2, #4, #5)
  - [x] 3.1 Add `submit_card_vote(card_id: UUID, user_id: UUID, vote: str, card_type: str, session: AsyncSession) -> CardFeedback` to `feedback_service.py`
  - [x] 3.2 Implement upsert logic: try `INSERT ... ON CONFLICT (user_id, card_id, feedback_source) DO UPDATE SET vote = excluded.vote` using SQLAlchemy `insert().on_conflict_do_update()` — this handles both first-vote and vote-change atomically
  - [x] 3.3 Add `get_card_feedback(card_id: UUID, user_id: UUID, feedback_source: str, session: AsyncSession) -> CardFeedback | None` — SELECT where user_id + card_id + feedback_source match
  - [x] 3.4 `feedback_source` is always `"card_vote"` for this story; keep as parameter for future reuse by Story 7.3 (issue reports)

- [x] Task 4: Backend — New `/feedback` router and endpoints (AC: #2, #4)
  - [x] 4.1 Add a second router `feedback_vote_router = APIRouter(prefix="/feedback", tags=["feedback"])` in `backend/app/api/v1/feedback.py` (alongside existing `router = APIRouter(prefix="/cards", ...)`)
  - [x] 4.2 Define Pydantic schemas: `CardVoteIn(BaseModel)` with `vote: Literal["up", "down"]`; `CardVoteOut(BaseModel)` with `id: UUID`, `card_id: UUID`, `vote: str`, `created_at: datetime`; `CardFeedbackResponse(BaseModel)` with `vote: str | None`, `reason_chip: str | None`, `created_at: datetime`
  - [x] 4.3 Implement `POST /feedback/cards/{card_id}/vote` → calls `feedback_service.submit_card_vote()`, returns 201 with `CardVoteOut`; apply `rate_limiter.check_feedback_rate_limit()` (reuse existing)
  - [x] 4.4 Implement `GET /feedback/cards/{card_id}` → calls `feedback_service.get_card_feedback()`; returns 200 with `CardFeedbackResponse` if found, 404 if not
  - [x] 4.5 Register `feedback_vote_router` in `backend/app/api/v1/router.py`

- [x] Task 5: Frontend — `use-card-feedback.ts` hook (AC: #2, #4, #5)
  - [x] 5.1 Create `frontend/src/features/teaching-feed/hooks/use-card-feedback.ts`
  - [x] 5.2 `useCardFeedback(cardId: string)` — uses `useSession()` for auth; returns `{ vote, submitVote, isPending }` (card_type is derived server-side, not passed by client)
  - [x] 5.3 Use `useQuery({ queryKey: ["card-feedback", cardId], queryFn: ... })` to fetch persisted state via `GET /api/v1/feedback/cards/{cardId}`; handle 404 as `null` vote (not an error); `enabled: !!session?.accessToken && !!cardId`; `staleTime: 5 * 60 * 1000`
  - [x] 5.4 Use `useMutation({ mutationFn: ... })` to POST vote; on success call `queryClient.invalidateQueries({ queryKey: ["card-feedback", cardId] })`; on error: silent (no user-visible error for telemetry-like feedback)
  - [x] 5.5 Optimistic update pattern: in `onMutate`, snapshot previous query data and update cache immediately (prevents flicker); in `onError`, rollback to snapshot

- [x] Task 6: Frontend — `CardFeedbackBar.tsx` component (AC: #1, #2, #5, #6)
  - [x] 6.1 Create `frontend/src/features/teaching-feed/components/CardFeedbackBar.tsx`
  - [x] 6.2 Accept props: `cardId: string`, `cardType: string`
  - [x] 6.3 Implement 2-second appearance delay: `const [visible, setVisible] = useState(false)` + `useEffect(() => { const t = setTimeout(() => setVisible(true), 2000); return () => clearTimeout(t); }, [])` — return null or invisible placeholder until `visible`
  - [x] 6.4 Wire to `useCardFeedback(cardId)`; render two icon buttons: thumbs-up (ThumbsUp from lucide-react) and thumbs-down (ThumbsDown); filled/colored when active (`vote === "up"` / `vote === "down"`)
  - [x] 6.5 On click: call `submitVote("up")` or `submitVote("down")`; if already selected → no-op (prevent redundant requests); if opposite selected → allow (triggers vote change via upsert)
  - [x] 6.6 Haptic: `if ("vibrate" in navigator) navigator.vibrate(10)` on icon click (graceful degradation)
  - [x] 6.7 WCAG: `<button aria-label="Rate this insight helpful" aria-pressed={vote === "up"}>` and `<button aria-label="Rate this insight not helpful" aria-pressed={vote === "down"}>` — use `<Button>` from shadcn/ui for built-in focus ring; `disabled={isPending}` during request
  - [x] 6.8 Style: `className="flex gap-2"` placed at bottom-right; icons muted (`text-muted-foreground`) when unset, accent color (`text-primary` or `fill-current`) when active

- [x] Task 7: Frontend — Integrate `CardFeedbackBar` into `InsightCard.tsx` (AC: #1)
  - [x] 7.1 Import `CardFeedbackBar` in `InsightCard.tsx`
  - [x] 7.2 Derive `cardType` from `insight.category` (available on `InsightCardType`); pass as `cardType={insight.category}`
  - [x] 7.3 Render `<CardFeedbackBar cardId={insight.id} cardType={insight.category} />` inside `<CardContent>`, after the expand button, aligned to the bottom-right

- [x] Task 8: Tests (AC: #1–#6)
  - [x] 8.1 Backend unit: `backend/tests/test_feedback_service.py` (existing file) — add tests for `submit_card_vote` (new vote → 201, vote change → updates row not duplicates, upsert idempotency) and `get_card_feedback` (found vs not found)
  - [x] 8.2 Backend API: `backend/tests/test_feedback_vote_api.py` — test `POST /api/v1/feedback/cards/{cardId}/vote`: returns 201, rejects invalid vote values, requires auth; test `GET /api/v1/feedback/cards/{cardId}`: returns vote when present, 404 when absent, requires auth
  - [x] 8.3 Frontend: `frontend/src/features/teaching-feed/__tests__/use-card-feedback.test.ts` — mock fetch; test query fetches on mount, mutation calls POST, optimistic update and rollback on error
  - [x] 8.4 Frontend: `frontend/src/features/teaching-feed/__tests__/CardFeedbackBar.test.tsx` — use `vi.useFakeTimers()` to advance 2s and verify icons appear; test click → mutation fires; test aria-pressed reflects vote state; mock `useCardFeedback`
  - [x] 8.5 All pre-existing backend and frontend tests continue passing; `InsightCard.test.tsx` may need `useCardFeedback` mock added

## Dev Notes

### Critical Architecture Context

Story 7.2 implements **Layer 1 — Explicit Card Feedback** of the 4-layer feedback system. Layer 0 (`card_interactions`) was implemented in Story 7.1 and is live. This story must not touch Layer 0 infrastructure.

**Two separate routers in `feedback.py`:**
- **Existing** (Story 7.1): `router = APIRouter(prefix="/cards", tags=["feedback"])` → `POST /api/v1/cards/interactions`
- **New** (Story 7.2): `feedback_vote_router = APIRouter(prefix="/feedback", tags=["feedback"])` → `POST /api/v1/feedback/cards/{cardId}/vote` + `GET /api/v1/feedback/cards/{cardId}`

Both routers live in the same `backend/app/api/v1/feedback.py` file; both are registered separately in `router.py`.

### Backend: CardFeedback Model

Append to the **existing** `backend/app/models/feedback.py` (do NOT create a new file):

```python
from sqlalchemy import CheckConstraint, DateTime, UniqueConstraint

class CardFeedback(SQLModel, table=True):
    __tablename__ = "card_feedback"
    __table_args__ = (
        CheckConstraint("vote IN ('up', 'down')", name="ck_card_feedback_vote"),
        UniqueConstraint("user_id", "card_id", "feedback_source", name="uq_card_feedback_user_card_source"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", nullable=False, index=True)
    card_id: uuid.UUID = Field(foreign_key="insights.id", nullable=False, index=True)
    card_type: str = Field(max_length=50)
    vote: Optional[str] = Field(default=None, max_length=10)
    reason_chip: Optional[str] = Field(default=None, max_length=50)
    free_text: Optional[str] = Field(default=None)
    feedback_source: str = Field(default="card_vote", max_length=20)
    issue_category: Optional[str] = Field(default=None, max_length=30)
    created_at: datetime = Field(default_factory=_utcnow, sa_type=DateTime(timezone=True))
```

Note: `_utcnow` is already defined in `feedback.py` from Story 7.1. Import `CheckConstraint, UniqueConstraint, DateTime` from `sqlalchemy`.

### Backend: Migration

**File:** `backend/alembic/versions/q3r4s5t6u7v8_add_card_feedback_table.py`

Follow exact pattern of `p2q3r4s5t6u7_add_card_interactions_table.py`. Key details:
- `revision = "q3r4s5t6u7v8"`, `down_revision = "p2q3r4s5t6u7"`
- Use `op.create_table("card_feedback", ...)` with `sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False, primary_key=True)`
- `card_type` column: `sa.Column("card_type", sa.String(50), nullable=False)`
- `vote` column: `sa.Column("vote", sa.String(10), nullable=True)` + `sa.CheckConstraint("vote IN ('up', 'down')", name="ck_card_feedback_vote")`
- `feedback_source`: `sa.Column("feedback_source", sa.String(20), nullable=False, server_default="card_vote")`
- `created_at`: `sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)`
- Indexes after table creation: `op.create_index("idx_card_feedback_user_id", "card_feedback", ["user_id"])`, `op.create_index("idx_card_feedback_card_id", "card_feedback", ["card_id"])`, `op.create_index("idx_card_feedback_card_type_vote", "card_feedback", ["card_type", "vote"])`
- Unique index: `op.create_index("uq_card_feedback_user_card_source", "card_feedback", ["user_id", "card_id", "feedback_source"], unique=True)`

### Backend: Upsert Logic

The `submit_card_vote` function uses a dialect-agnostic SELECT-then-INSERT/UPDATE with `IntegrityError` fallback, because `pg_insert().on_conflict_do_update()` is not available under the SQLite test engine. The unique constraint on `(user_id, card_id, feedback_source)` provides the race-safety net: concurrent first-vote inserts are caught, the losing request rolls back and re-loads the winner's row to update its vote.

```python
from sqlalchemy.exc import IntegrityError

existing_stmt = select(CardFeedback).where(...)
existing = (await session.exec(existing_stmt)).one_or_none()
if existing is not None:
    existing.vote = vote
    record = existing
    await session.flush()
else:
    record = CardFeedback(...)
    session.add(record)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        winner = (await session.exec(existing_stmt)).one_or_none()
        if winner is None:
            raise
        winner.vote = vote
        record = winner
        await session.flush()
```

See the actual implementation in `backend/app/services/feedback_service.py:submit_card_vote`.

### Backend: Router Addition

In `backend/app/api/v1/feedback.py`, after the existing `router` definition and `record_card_interactions` endpoint, add:

```python
feedback_vote_router = APIRouter(prefix="/feedback", tags=["feedback"])

class CardVoteIn(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    vote: Literal["up", "down"]

class CardVoteOut(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    id: uuid.UUID
    card_id: uuid.UUID
    vote: str
    created_at: datetime

class CardFeedbackResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    vote: str | None
    reason_chip: str | None
    created_at: datetime

@feedback_vote_router.post("/cards/{card_id}/vote", status_code=status.HTTP_201_CREATED, response_model=CardVoteOut)
async def submit_vote(...) -> CardVoteOut:
    ...

@feedback_vote_router.get("/cards/{card_id}", response_model=CardFeedbackResponse)
async def get_card_feedback(...) -> CardFeedbackResponse:
    # raises HTTPException(404) if not found
    ...
```

In `router.py`, add:
```python
from app.api.v1.feedback import feedback_vote_router as feedback_vote_router
v1_router.include_router(feedback_vote_router)
```

Note: `card_type` is not provided by the client — derive it server-side by querying the `insights` table for the card's `category` field, OR accept it from the client as a body field. **Simplest approach:** add `card_type: str` to `CardVoteIn` — the frontend sends `insight.category`. This avoids a DB join in the endpoint.

### Frontend: API URL Pattern

Follow `use-teaching-feed.ts` pattern:
```typescript
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
```

Auth header: `Authorization: Bearer ${session?.accessToken}` — same pattern used in `use-card-interactions.ts` and `use-teaching-feed.ts`.

### Frontend: Hook Design (`use-card-feedback.ts`)

```typescript
"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSession } from "next-auth/react";

export type VoteValue = "up" | "down";

export interface CardFeedbackState {
  vote: VoteValue | null;
  reasonChip: string | null;
  createdAt: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function useCardFeedback(cardId: string, cardType: string) {
  const { data: session } = useSession();
  const queryClient = useQueryClient();
  const token = session?.accessToken;
  const queryKey = ["card-feedback", cardId];

  const { data } = useQuery({
    queryKey,
    queryFn: async () => {
      const res = await fetch(`${API_URL}/api/v1/feedback/cards/${cardId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.status === 404) return null;
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json() as Promise<CardFeedbackState>;
    },
    enabled: !!token && !!cardId,
    staleTime: 5 * 60 * 1000,
  });

  const mutation = useMutation({
    mutationFn: async (vote: VoteValue) => {
      const res = await fetch(`${API_URL}/api/v1/feedback/cards/${cardId}/vote`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ vote, cardType }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
    onMutate: async (newVote) => {
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData<CardFeedbackState | null>(queryKey);
      queryClient.setQueryData(queryKey, (old: CardFeedbackState | null) =>
        old ? { ...old, vote: newVote } : { vote: newVote, reasonChip: null, createdAt: new Date().toISOString() }
      );
      return { previous };
    },
    onError: (_err, _vote, context) => {
      queryClient.setQueryData(queryKey, context?.previous);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey });
    },
  });

  return {
    vote: data?.vote ?? null,
    submitVote: mutation.mutate,
    isPending: mutation.isPending,
  };
}
```

### Frontend: 2-Second Delay Implementation

The 2-second delay in `CardFeedbackBar` must reset on card change. Since `CardFeedbackBar` is mounted fresh per-card (inside `AnimatePresence` in `CardStackNavigator`), the `useEffect` always fires on mount and the 2-second clock starts fresh. No special handling needed — React lifecycle does this automatically.

```typescript
const [visible, setVisible] = useState(false);
useEffect(() => {
  const t = setTimeout(() => setVisible(true), 2000);
  return () => clearTimeout(t);
}, []); // empty deps → runs once on mount per card
```

### Frontend: Icon Styling

Use `lucide-react` icons (already used by `CardStackNavigator`):
```tsx
import { ThumbsUp, ThumbsDown } from "lucide-react";

// Active state: fill the icon
<ThumbsUp className={cn("h-4 w-4", vote === "up" ? "fill-primary text-primary" : "text-muted-foreground")} />
```

### Previous Story Intelligence (Story 7.1 — Implicit Card Interaction Tracking)

**Critical learnings from Story 7.1 implementation (2026-04-16/17):**

1. **SQLModel + SA types:** Use `sa_type=SmallInteger` for `smallint` columns; for `DateTime(timezone=True)`, import from `sqlalchemy` and use `sa_type=DateTime(timezone=True)`. Pattern is established in `feedback.py`.

2. **Test isolation — MissingGreenlet:** When testing async SQLAlchemy services, capture `.id` fields into local variables BEFORE calling the service (e.g., `card_a_id = card_a.id`). Services may commit mid-test, expiring object state.

3. **Router registration:** Add to `router.py` `include_router` calls. The `v1_router` has `prefix="/api/v1"` so the registered router just needs its own sub-prefix (e.g., `/feedback`).

4. **Frontend test mocking:** New hooks that call `useSession()` require `vi.mock("next-auth/react")` in test files. Tests for `InsightCard.test.tsx` and `CardFeedbackBar.test.tsx` must include this mock.

5. **TanStack Query in tests:** Wrap components under test in `<QueryClientProvider client={new QueryClient()}>`. Follow pattern in `use-teaching-feed.test.tsx`.

6. **`__table_args__` for constraints:** SQLModel supports `__table_args__` as a tuple of SA constructs + optional dict. This is the right place for `CheckConstraint` and `UniqueConstraint`.

7. **Audit trail:** `AUDIT_PATH_RESOURCE_MAP` in the compliance middleware does NOT need updating — feedback votes are behavioral data, not GDPR-regulated financial data access. Same decision as Story 7.1 for `card_interactions`.

8. **Rate limiter:** `check_feedback_rate_limit` (60 req/min per user) already exists in `rate_limiter.py` from Story 7.1. Reuse it on the new vote endpoint.

9. **Test baseline:** Backend 509 passing, Frontend 397 passing before this story starts.

### Git Intelligence

- Latest commit `d758ea5` (Story 7.1) created: `feedback.py` (model, migration, service, API, tests). Story 7.2 extends all four of these files.
- Pattern for Alembic migrations: `revision` uses hex-suffix naming; `down_revision` points to the immediately preceding migration.
- Pattern for FastAPI deps: `Depends(get_current_user_id)` → `uuid.UUID`, `Depends(get_db)` → `AsyncSession`, `Depends(get_rate_limiter)` → `RateLimiter`.
- Pattern for `async def` test functions with `AsyncClient(app=app, base_url="http://test")`: established in `test_feedback_api.py`.

### Project Structure Notes

```
backend/
├── app/
│   ├── models/
│   │   └── feedback.py                     ← MODIFIED: add CardFeedback class
│   ├── services/
│   │   └── feedback_service.py             ← MODIFIED: add submit_card_vote(), get_card_feedback()
│   ├── api/v1/
│   │   ├── feedback.py                     ← MODIFIED: add feedback_vote_router + 2 new endpoints
│   │   └── router.py                       ← MODIFIED: include feedback_vote_router
│   └── models/__init__.py                  ← MODIFIED: register CardFeedback
├── alembic/versions/
│   └── q3r4s5t6u7v8_add_card_feedback_table.py  ← NEW
└── tests/
    ├── test_feedback_service.py            ← MODIFIED: add vote/get tests
    └── test_feedback_vote_api.py           ← NEW

frontend/src/features/teaching-feed/
├── hooks/
│   └── use-card-feedback.ts               ← NEW
├── components/
│   ├── CardFeedbackBar.tsx                ← NEW
│   └── InsightCard.tsx                    ← MODIFIED: add CardFeedbackBar
└── __tests__/
    ├── CardFeedbackBar.test.tsx           ← NEW
    ├── use-card-feedback.test.ts          ← NEW
    └── InsightCard.test.tsx               ← MODIFIED: mock useCardFeedback
```

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 7.2] — acceptance criteria, user story statement, vote endpoint URLs
- [Source: _bmad-output/planning-artifacts/architecture.md#Line 311] — Layer 1 card_feedback table schema (columns, constraints, indexes)
- [Source: _bmad-output/planning-artifacts/architecture.md#Line 766] — POST /feedback/cards/{cardId}/vote and GET /feedback/cards/{cardId} API specs
- [Source: _bmad-output/planning-artifacts/architecture.md#Line 1004] — CardFeedbackBar.tsx and use-card-feedback.ts in component/hook map
- [Source: _bmad-output/planning-artifacts/architecture.md#Line 1318] — Layer 1 frontend→backend mapping
- [Source: _bmad-output/implementation-artifacts/7-1-implicit-card-interaction-tracking-engagement-score.md] — existing feedback.py model/service/API patterns, test patterns, MissingGreenlet fix
- [Source: backend/app/models/feedback.py] — CardInteraction model pattern; _utcnow() to reuse
- [Source: backend/app/services/feedback_service.py] — existing service structure to extend
- [Source: backend/app/api/v1/feedback.py] — existing router; add second router here
- [Source: backend/alembic/versions/p2q3r4s5t6u7_add_card_interactions_table.py] — migration pattern to follow exactly
- [Source: frontend/src/features/teaching-feed/hooks/use-teaching-feed.ts] — TanStack Query + auth pattern
- [Source: frontend/src/features/teaching-feed/hooks/use-card-interactions.ts] — useSession() + API_URL pattern
- [Source: frontend/src/features/teaching-feed/components/InsightCard.tsx] — component to modify; cardType = insight.category
- [Source: frontend/src/features/teaching-feed/components/CardStackNavigator.tsx] — AnimatePresence remounts per card; lucide-react import pattern

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context)

### Debug Log References

- MissingGreenlet on post-commit attribute access: fixed by creating detached CardFeedback snapshots before commit (same pattern as Story 7.1)
- pg_insert (PostgreSQL dialect) incompatible with SQLite test engine: replaced with dialect-agnostic SELECT-then-INSERT/UPDATE pattern, unique constraint provides safety net
- CardStackNavigator.test.tsx and FeedContainer.test.tsx needed useCardFeedback mock after CardFeedbackBar integration into InsightCard

### Completion Notes List

- ✅ Task 1: Added CardFeedback SQLModel class with CheckConstraint and UniqueConstraint to existing feedback.py; registered in models/__init__.py
- ✅ Task 2: Created Alembic migration q3r4s5t6u7v8 with all columns, indexes (user_id, card_id, card_type+vote), and unique constraint (user_id, card_id, feedback_source)
- ✅ Task 3: Implemented submit_card_vote (dialect-agnostic upsert with IntegrityError retry) and get_card_feedback in feedback_service.py; both return detached snapshots to avoid MissingGreenlet
- ✅ Task 4: Added feedback_vote_router with POST /feedback/cards/{card_id}/vote (201/404) and GET /feedback/cards/{card_id} (200/404); registered in router.py; card_type derived server-side from the insight's category (body is `{"vote": "up"}` per AC #2)
- ✅ Task 5: Created use-card-feedback.ts hook with useQuery (404→null), useMutation, optimistic updates with rollback
- ✅ Task 6: Created CardFeedbackBar.tsx with 2-second appearance delay, ThumbsUp/ThumbsDown icons, haptic feedback, WCAG AA compliance (aria-label, aria-pressed, focus ring, disabled during pending)
- ✅ Task 7: Integrated CardFeedbackBar into InsightCard.tsx after expand button (cardId only — cardType removed in code review)
- ✅ Task 8: Backend tests (5 service + 7 API — race-condition + unknown-card + rate-limit-429 coverage added in review), 12 frontend tests (4 hook + 8 component); updated InsightCard, CardStackNavigator, FeedContainer tests with useCardFeedback mock; 522 backend + 409 frontend tests pass
- ✅ Version bump: 1.7.0 → 1.8.0 (MINOR — new user-facing feature)

### Code Review (2026-04-17)

Adversarial review found 1 HIGH, 3 MEDIUM, 6 LOW. All HIGH/MEDIUM fixed automatically; LOW items resolved inline or promoted to tech-debt register.

**Fixed:**
- H1: Removed `card_type` from `CardVoteIn` body; endpoint now derives it by querying `Insight` → 404 if card not found. Restores the architecture/AC-documented body contract of `{"vote": "up"}`. Dropped `cardType` parameter from `useCardFeedback`, `CardFeedbackBar`, and `InsightCard` integration.
- M1: Added `IntegrityError` catch + rollback + re-fetch-and-update path to `submit_card_vote`, so concurrent first-vote races no longer surface as 500. Snapshot now includes all `CardFeedback` fields.
- M2: Migration switched from `op.create_index(..., unique=True)` to `sa.UniqueConstraint` in `create_table`, matching the SQLModel `__table_args__` so Alembic autogenerate won't flag drift.
- M3: Fixed stale `mock_rate.check_rate_limit` reference in `vote_client` fixture. Added `test_submit_vote_rate_limited` (asserts 429 and that `check_feedback_rate_limit` was awaited with the user_id) and `test_submit_vote_unknown_card_returns_404`.

**Resolved inline:**
- L1: Dev Notes "Backend: Upsert Logic" example updated to the actual SELECT-then-INSERT/UPDATE + IntegrityError pattern.
- L2: Task 5.2 text clarified that `card_type` is derived server-side.
- L4: `submit_card_vote` snapshot was extended to include `reason_chip`, `free_text`, `issue_category` (incidental to the M1 rewrite).

**Promoted to tech-debt register:**
- L3 → [TD-017](../../docs/tech-debt.md#td-017) — `card_feedback.created_at` is frozen on vote flip; add `updated_at` column and expose `updatedAt`.
- L5 → [TD-018](../../docs/tech-debt.md#td-018) — No concurrency test for the `IntegrityError` retry path added in M1. Requires Postgres testcontainer.
- L6 → [TD-019](../../docs/tech-debt.md#td-019) — GET `/feedback/cards/{cardId}` is not rate-limited. Add a read-tier limiter.

### File List

**New files:**
- backend/alembic/versions/q3r4s5t6u7v8_add_card_feedback_table.py
- backend/tests/test_feedback_vote_api.py
- frontend/src/features/teaching-feed/hooks/use-card-feedback.ts
- frontend/src/features/teaching-feed/components/CardFeedbackBar.tsx
- frontend/src/features/teaching-feed/__tests__/use-card-feedback.test.ts
- frontend/src/features/teaching-feed/__tests__/CardFeedbackBar.test.tsx

**Modified files:**
- backend/app/models/feedback.py
- backend/app/models/__init__.py
- backend/app/services/feedback_service.py
- backend/app/api/v1/feedback.py
- backend/app/api/v1/router.py
- backend/tests/test_feedback_service.py
- frontend/src/features/teaching-feed/components/InsightCard.tsx
- frontend/src/features/teaching-feed/__tests__/InsightCard.test.tsx
- frontend/src/features/teaching-feed/__tests__/CardStackNavigator.test.tsx
- frontend/src/features/teaching-feed/__tests__/FeedContainer.test.tsx
- VERSION
- _bmad-output/implementation-artifacts/sprint-status.yaml

## Change Log

- Implemented Story 7.2: Thumbs up/down explicit feedback on Teaching Feed cards (Layer 1 of 4-layer feedback system)
- Added card_feedback table via Alembic migration with vote check constraint and user+card+source unique constraint
- Added POST /api/v1/feedback/cards/{cardId}/vote and GET /api/v1/feedback/cards/{cardId} endpoints
- Added CardFeedbackBar component with 2-second delayed appearance, WCAG AA accessibility, and haptic feedback
- Version bumped from 1.7.0 to 1.8.0 per story completion (Date: 2026-04-17)
- Code review (2026-04-17): restored `{"vote": ...}`-only body contract by deriving card_type server-side; added IntegrityError retry to vote upsert; migration now uses UniqueConstraint instead of a unique index; added 429 and unknown-card test coverage; 3 LOW findings promoted to TD-017/018/019. Status: done.
