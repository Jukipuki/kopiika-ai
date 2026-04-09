# Story 4.4: Persistent Financial Profile

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want the system to build and maintain a financial profile from all my uploaded statements,
so that I have a comprehensive view of my financial situation.

## Acceptance Criteria

1. **Given** a user has uploaded one or more statements, **When** the pipeline completes processing, **Then** a financial profile is created or updated, aggregating data across all uploads (via `financial_profiles` table with user_id FK, total_income, total_expenses, category_totals JSON, period_start, period_end, updated_at).

2. **Given** a user uploads a new statement, **When** the new transactions are processed, **Then** the financial profile is recalculated to include the new data without losing previous aggregations.

3. **Given** the financial profile API endpoint `GET /api/v1/profile`, **When** an authenticated user requests their profile, **Then** they receive aggregated financial data scoped to their user_id with camelCase JSON serialization.

## Tasks / Subtasks

- [x] Task 1: Create `FinancialProfile` SQLModel and Alembic migration (AC: #1)
  - [x] 1.1 Create `backend/app/models/financial_profile.py` with SQLModel class (`financial_profiles` table)
  - [x] 1.2 Add model to `backend/app/models/__init__.py` exports
  - [x] 1.3 Generate Alembic migration: `alembic revision --autogenerate -m "add financial_profiles table"`
  - [x] 1.4 Test migration up/down locally

- [x] Task 2: Create `ProfileService` with aggregation logic (AC: #1, #2)
  - [x] 2.1 Create `backend/app/services/profile_service.py`
  - [x] 2.2 Implement `build_or_update_profile(session, user_id)` — query ALL user transactions, compute totals
  - [x] 2.3 Aggregation: sum positive amounts → total_income, sum negative amounts → total_expenses, group by category → category_totals JSON, min/max date → period_start/period_end
  - [x] 2.4 Upsert logic: create if no profile exists, update if one does (always recalculate from all transactions)

- [x] Task 3: Hook profile aggregation into pipeline completion (AC: #1, #2)
  - [x] 3.1 In `backend/app/tasks/processing_tasks.py`, call `build_or_update_profile()` after categorization completes (before marking job as "completed")
  - [x] 3.2 Add SSE progress message: "Building your financial profile..."
  - [x] 3.3 Handle profile build failure gracefully (log warning, don't fail the job)

- [x] Task 4: Create `GET /api/v1/profile` endpoint (AC: #3)
  - [x] 4.1 Create `backend/app/api/v1/profile.py` with router
  - [x] 4.2 Register router in `backend/app/api/v1/router.py`
  - [x] 4.3 Return 200 with profile data (camelCase via Pydantic alias), or 404 if no profile yet
  - [x] 4.4 Scope query to authenticated user_id (use existing `get_current_user` dependency)

- [x] Task 5: Create frontend profile page (AC: #3)
  - [x] 5.1 Create `frontend/src/features/profile/` feature directory with components/, hooks/, types.ts
  - [x] 5.2 Create `useProfile` hook using TanStack Query (`useQuery` with key `["profile"]`)
  - [x] 5.3 Create `ProfilePage` component showing: total income, total expenses, net balance, category breakdown (simple list for now — charts deferred to Story 4.8)
  - [x] 5.4 Create `frontend/src/app/(dashboard)/profile/page.tsx` route
  - [x] 5.5 Add navigation link to profile page in the header/sidebar
  - [x] 5.6 Display amounts in hryvnias (convert from kopiykas: `amount / 100`), format with `Intl.NumberFormat('uk-UA', { style: 'currency', currency: 'UAH' })`
  - [x] 5.7 Add i18n strings to `frontend/messages/en.json` and `frontend/messages/uk.json`

- [x] Task 6: Tests (AC: #1-#3)
  - [x] 6.1 Backend unit tests: `backend/tests/test_profile_service.py` — test aggregation with multiple uploads, empty transactions, mixed categories
  - [x] 6.2 Backend API tests: `backend/tests/test_profile_api.py` — test GET /api/v1/profile returns camelCase, test 404 when no profile, test auth required
  - [x] 6.3 Frontend tests: `frontend/src/features/profile/__tests__/ProfilePage.test.tsx` — test data display, loading state, empty state
  - [x] 6.4 Verify all existing tests pass (285 backend + 198 frontend)

## Dev Notes

### Scope Summary

**Full-stack story.** New DB table, service layer, API endpoint, and frontend page. No AI/LLM involvement — pure data aggregation from existing categorized transactions.

### Architecture Compliance

**Database:**
- Table name: `financial_profiles` (snake_case, plural)
- PK: `id UUID DEFAULT gen_random_uuid()`
- FK: `user_id UUID REFERENCES users(id)` with unique constraint (one profile per user)
- Columns: `total_income` (integer, kopiykas), `total_expenses` (integer, kopiykas), `category_totals` (JSONB), `period_start` (timestamp), `period_end` (timestamp), `created_at`, `updated_at`
- Index: `idx_financial_profiles_user_id`
- Amounts stored as **integer kopiykas** (same as `transactions.amount` — e.g., 15050 = 150.50 UAH)

**API:**
- Endpoint: `GET /api/v1/profile` (kebab-case, REST convention)
- Response JSON: camelCase fields via Pydantic `alias_generator=to_camel` (existing pattern — see `backend/app/api/v1/insights.py` for reference)
- Auth: use existing `get_current_user` dependency from `backend/app/api/deps.py`

**Backend patterns:**
- ORM: SQLModel (SQLAlchemy + Pydantic) — follow existing models in `backend/app/models/`
- Service layer: business logic in `backend/app/services/profile_service.py`, thin route handler in `backend/app/api/v1/profile.py`
- Sync DB sessions in Celery tasks: use `get_sync_session()` from `backend/app/core/database.py` (see `processing_tasks.py` for pattern)

**Frontend patterns:**
- Feature folder: `frontend/src/features/profile/` (follow teaching-feed pattern)
- State: TanStack Query v5 `useQuery` hook
- UI: shadcn/ui components (Card, etc.)
- i18n: next-intl (add to both `en.json` and `uk.json`)
- Routing: `frontend/src/app/(dashboard)/profile/page.tsx`

### Key Implementation Details

**Aggregation approach — always recalculate from ALL transactions:**
```python
# In profile_service.py
def build_or_update_profile(session: Session, user_id: UUID) -> FinancialProfile:
    transactions = session.exec(
        select(Transaction).where(Transaction.user_id == user_id)
    ).all()
    
    total_income = sum(t.amount for t in transactions if t.amount > 0)
    total_expenses = sum(t.amount for t in transactions if t.amount < 0)
    
    category_totals = {}
    for t in transactions:
        cat = t.category or "uncategorized"
        category_totals[cat] = category_totals.get(cat, 0) + t.amount
    
    # Upsert
    profile = session.exec(
        select(FinancialProfile).where(FinancialProfile.user_id == user_id)
    ).first()
    if not profile:
        profile = FinancialProfile(user_id=user_id)
    
    profile.total_income = total_income
    profile.total_expenses = total_expenses
    profile.category_totals = category_totals
    profile.period_start = min(t.date for t in transactions) if transactions else None
    profile.period_end = max(t.date for t in transactions) if transactions else None
    profile.updated_at = datetime.now(UTC).replace(tzinfo=None)
    
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile
```

**Pipeline integration point in `processing_tasks.py`:**
- Insert profile build call at line ~248, AFTER categorization results are committed, BEFORE marking job as "completed"
- Wrap in try/except so profile failure doesn't fail the job
- Add progress message at ~90% progress

**Frontend currency formatting:**
- All amounts are stored as integer kopiykas
- Convert: `amount / 100` for display
- Format: `new Intl.NumberFormat(locale === 'uk' ? 'uk-UA' : 'en-US', { style: 'currency', currency: 'UAH' }).format(amount / 100)`

### DO NOT

- Do NOT create charts/visualizations — that's Story 4.8 (Category Spending Breakdown)
- Do NOT calculate health score — that's Story 4.5
- Do NOT add trend tracking — that's Story 4.6
- Do NOT add month-over-month comparison — that's Story 4.7
- Do NOT use incremental aggregation — always recalculate from all transactions (simpler, safer, data volume is small for MVP)

### Previous Story Intelligence

**From Story 4.3 (previous):**
- `wasStreamingRef` pattern for scoping state transitions — may be relevant if profile page needs SSE awareness
- `SkeletonList` component extracted — reuse for profile loading states
- Frontend test count is now 193 (not 184 as originally planned)
- Code review established: extract shared components rather than duplicate JSX

**From Story 4.1:**
- SSE progress messages are now backend-owned (message field in pipeline-progress events) — follow same pattern for profile build progress message

**Git patterns from recent commits:**
- Stories 4.1-4.3 were frontend-heavy fixes. Story 4.4 is the first full-stack story in Epic 4
- Existing test infrastructure is mature: vitest + @testing-library/react (frontend), pytest (backend)

### Project Structure Notes

- New files align with established project structure
- `backend/app/models/financial_profile.py` follows existing model file pattern
- `backend/app/services/profile_service.py` follows existing service pattern
- `frontend/src/features/profile/` follows feature folder convention
- No conflicts with existing code paths

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Story 4.4] — acceptance criteria
- [Source: _bmad-output/planning-artifacts/architecture.md#L476-498] — naming conventions (DB, API, code)
- [Source: _bmad-output/planning-artifacts/architecture.md#L554-612] — backend structure pattern
- [Source: _bmad-output/planning-artifacts/architecture.md#L518-552] — frontend structure pattern
- [Source: backend/app/models/transaction.py] — transaction model (amount as integer kopiykas, category field)
- [Source: backend/app/tasks/processing_tasks.py] — pipeline task (integration point for profile build)
- [Source: backend/app/api/v1/router.py] — API router registration pattern
- [Source: backend/app/models/__init__.py] — model exports pattern

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

None — clean implementation with no debug issues.

### Completion Notes List

- Task 1: Created `FinancialProfile` SQLModel with UUID PK, user_id FK (unique), integer kopiykas amounts, JSONB category_totals, period timestamps. Alembic migration tested up/down successfully.
- Task 2: Created `profile_service.py` with sync `build_or_update_profile()` (for Celery) and async `get_profile_for_user()` (for API). Full recalculation from all transactions on every call.
- Task 3: Hooked profile build into processing pipeline at 90% progress, after categorization/education and before job completion. Wrapped in try/except so failures don't fail the job. Updated SSE test to account for new progress event.
- Task 4: Created `GET /api/v1/profile` endpoint with camelCase response (Pydantic alias_generator), 404 when no profile, scoped to authenticated user_id.
- Task 5: Created full frontend feature: `useProfile` hook (TanStack Query), `ProfilePage` component with summary cards (income/expenses/net), category breakdown list, loading skeleton, empty state, and error state. Added profile nav link to dashboard header. Added i18n strings in both English and Ukrainian.
- Task 6: 12 backend tests (7 service + 5 API) and 5 frontend tests all pass. Full regression: 285 backend + 198 frontend = 483 total tests passing.

### Change Log

- 2026-04-08: Implemented Story 4.4 — Persistent Financial Profile (full-stack: DB model, service, pipeline integration, API endpoint, frontend page with i18n)
- 2026-04-08: Code review fixes — H1: skip retries on 404 in useProfile; H2: invalidate profile cache on job-complete; M1: JSON→JSONB for category_totals; M2: show expenses as positive in UI; M3: remove false UTC "Z" suffix from period timestamps

### File List

**New files:**
- backend/app/models/financial_profile.py
- backend/app/services/profile_service.py
- backend/app/api/v1/profile.py
- backend/alembic/versions/c3d4e5f6a7b8_add_financial_profiles_table.py
- backend/tests/test_profile_service.py
- backend/tests/test_profile_api.py
- frontend/src/features/profile/types.ts
- frontend/src/features/profile/hooks/use-profile.ts
- frontend/src/features/profile/components/ProfilePage.tsx
- frontend/src/features/profile/__tests__/ProfilePage.test.tsx
- frontend/src/app/[locale]/(dashboard)/profile/page.tsx

**Modified files:**
- backend/app/models/__init__.py
- backend/app/api/v1/router.py
- backend/app/tasks/processing_tasks.py
- backend/tests/test_sse_streaming.py
- frontend/src/app/[locale]/(dashboard)/layout.tsx
- frontend/messages/en.json
- frontend/messages/uk.json
- frontend/src/features/teaching-feed/hooks/use-feed-sse.ts (review fix: profile cache invalidation)
- frontend/src/features/teaching-feed/__tests__/use-feed-sse.test.ts (review fix: updated assertion)
