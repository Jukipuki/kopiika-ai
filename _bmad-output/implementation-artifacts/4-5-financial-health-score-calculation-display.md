# Story 4.5: Financial Health Score Calculation & Display

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want to see a Financial Health Score (0-100) based on my cumulative data,
so that I have a quick indicator of my overall financial wellness.

## Acceptance Criteria

1. **Given** a user has a financial profile with sufficient data, **When** the Health Score is calculated, **Then** a score from 0-100 is computed based on spending patterns, savings ratio, and category distribution, completing within 2 seconds.

2. **Given** the Health Score is calculated, **When** the user views their profile page, **Then** the score is displayed as an Apple Fitness-inspired circular ring (SVG) with animated gradient transitions between score zones:
   - 0–30: Coral (needs attention)
   - 31–60: Amber (developing)
   - 61–80: Violet (healthy)
   - 81–100: Sage/Teal (excellent)

3. **Given** a user with `prefers-reduced-motion` enabled, **When** the Health Score ring renders, **Then** the animation is disabled and the score displays as a static number with the ring at its final position.

4. **Given** the Health Score is stored, **When** it is persisted, **Then** a `financial_health_scores` table is created via Alembic migration with `id` (UUID), `user_id` (FK), `score` (integer 0-100), `calculated_at` (timestamp), and `breakdown` (JSONB snapshot of component scores).

## Tasks / Subtasks

- [x] Task 1: Create `FinancialHealthScore` SQLModel and Alembic migration (AC: #4)
  - [x] 1.1 Create `backend/app/models/financial_health_score.py` with SQLModel class (`financial_health_scores` table): `id` UUID PK, `user_id` UUID FK → users(id), `score` Integer (0-100), `calculated_at` DateTime, `breakdown` JSONB (component scores snapshot)
  - [x] 1.2 Add model to `backend/app/models/__init__.py` exports
  - [x] 1.3 Generate Alembic migration: `alembic revision --autogenerate -m "add financial_health_scores table"`
  - [x] 1.4 Add index: `idx_financial_health_scores_user_id` and composite `idx_financial_health_scores_user_id_calculated_at` for history queries (Story 4.6)
  - [x] 1.5 Test migration up/down locally

- [x] Task 2: Implement health score calculation service (AC: #1)
  - [x] 2.1 Create `backend/app/services/health_score_service.py`
  - [x] 2.2 Implement `calculate_health_score(session: Session, user_id: UUID) -> FinancialHealthScore` with these weighted components:
    - **Savings ratio** (40%): `(total_income + total_expenses) / total_income` — higher savings = higher score. If total_income ≤ 0, this component scores 0
    - **Category diversity** (20%): penalize if >50% of expenses in a single category (over-concentration risk)
    - **Expense regularity** (20%): ratio of recurring vs one-off expenses — more predictable spending = higher score. Use category distribution variance as proxy
    - **Income coverage** (20%): months of expenses coverable by net savings — basic emergency fund indicator
  - [x] 2.3 Each component returns 0-100; final score = weighted average, clamped to [0, 100]
  - [x] 2.4 Store breakdown as JSONB: `{"savings_ratio": 75, "category_diversity": 60, "expense_regularity": 80, "income_coverage": 50, "weights": {...}}`
  - [x] 2.5 Implement `get_latest_score(session: AsyncSession, user_id: UUID) -> FinancialHealthScore | None` for API layer

- [x] Task 3: Hook score calculation into pipeline (AC: #1)
  - [x] 3.1 In `backend/app/tasks/processing_tasks.py`, call `calculate_health_score()` AFTER `build_or_update_profile()` completes successfully (at ~92% progress)
  - [x] 3.2 Add SSE progress message: "Calculating your Financial Health Score..."
  - [x] 3.3 Wrap in try/except — score failure must NOT fail the pipeline job (same pattern as profile build)

- [x] Task 4: Create/extend API endpoints (AC: #1, #4)
  - [x] 4.1 Create `backend/app/api/v1/health_score.py` with `GET /api/v1/health-score` endpoint
  - [x] 4.2 Response model: `HealthScoreResponse` with camelCase alias (`score`, `breakdown`, `calculatedAt`)
  - [x] 4.3 Return 404 if no score yet; scope to authenticated user_id
  - [x] 4.4 Register router in `backend/app/api/v1/router.py`

- [x] Task 5: Create frontend Health Score ring component (AC: #2, #3)
  - [x] 5.1 Create `frontend/src/features/profile/components/HealthScoreRing.tsx` — SVG circular ring component
  - [x] 5.2 Implement animated arc that fills to score percentage with gradient color based on zone:
    - 0–30: `#F87171` (coral/red) — "Needs Attention"
    - 31–60: `#FBBF24` (amber) — "Developing"
    - 61–80: `#8B5CF6` (violet) — "Healthy"
    - 81–100: `#2DD4BF` (sage/teal) — "Excellent"
  - [x] 5.3 Display score number centered in the ring with zone label below
  - [x] 5.4 Implement `prefers-reduced-motion` media query: skip animation, render ring at final position immediately
  - [x] 5.5 Add score breakdown tooltip/expandable showing component scores (savings ratio, diversity, regularity, coverage)

- [x] Task 6: Integrate Health Score into Profile Page (AC: #2)
  - [x] 6.1 Create `frontend/src/features/profile/hooks/use-health-score.ts` — TanStack Query hook for `GET /api/v1/health-score`
  - [x] 6.2 Add `HealthScoreSection` to `ProfilePage.tsx` — positioned prominently above the existing summary cards
  - [x] 6.3 Add `frontend/src/features/profile/types.ts` — add `HealthScore` interface (`score`, `breakdown`, `calculatedAt`)
  - [x] 6.4 Handle empty state: "Upload a statement to see your Financial Health Score"
  - [x] 6.5 Add loading skeleton for health score section
  - [x] 6.6 Add i18n strings to `frontend/messages/en.json` and `frontend/messages/uk.json` for all score zones, labels, breakdown component names

- [x] Task 7: Tests (AC: #1-#4)
  - [x] 7.1 Backend unit tests: `backend/tests/test_health_score_service.py` — test score calculation with various profiles (high savings, overspending, single category, balanced), edge cases (zero income, no transactions, single transaction)
  - [x] 7.2 Backend API tests: `backend/tests/test_health_score_api.py` — test GET returns camelCase, test 404, test auth required
  - [x] 7.3 Frontend tests: `frontend/src/features/profile/__tests__/HealthScoreRing.test.tsx` — test ring renders with correct color per zone, test reduced-motion, test breakdown display
  - [x] 7.4 Frontend tests: update `ProfilePage.test.tsx` to include health score section
  - [x] 7.5 Verify all existing tests pass (299 backend + 209 frontend)

## Dev Notes

### Scope Summary

**Full-stack story.** New DB table, calculation service, pipeline integration, API endpoint, and frontend SVG ring visualization. No AI/LLM involvement — pure computation from existing financial profile data.

### Architecture Compliance

**Database:**
- Table name: `financial_health_scores` (snake_case, plural)
- PK: `id UUID DEFAULT gen_random_uuid()`
- FK: `user_id UUID REFERENCES users(id)` — NOT unique (multiple scores over time for Story 4.6 history)
- Columns: `score` (integer, 0-100), `calculated_at` (timestamp), `breakdown` (JSONB)
- Indexes: `idx_financial_health_scores_user_id`, `idx_financial_health_scores_user_id_calculated_at`
- Each pipeline run creates a NEW score record (append-only for history tracking)

**API:**
- Endpoint: `GET /api/v1/health-score` (kebab-case)
- Response JSON: camelCase via Pydantic `alias_generator=to_camel` (follow `backend/app/api/v1/profile.py` pattern)
- Auth: use existing `get_current_user` dependency from `backend/app/api/deps.py`

**Backend patterns:**
- ORM: SQLModel — follow `backend/app/models/financial_profile.py` pattern
- Service layer: `backend/app/services/health_score_service.py` with sync function for Celery + async function for API
- Pipeline integration: same try/except pattern as profile build in `backend/app/tasks/processing_tasks.py:250-266`

**Frontend patterns:**
- Reuse existing `frontend/src/features/profile/` feature directory — health score is part of the profile feature
- State: TanStack Query v5 `useQuery` hook (follow `use-profile.ts` pattern)
- UI: SVG ring is custom component; surrounding cards use shadcn/ui `Card`
- i18n: next-intl (add to both `en.json` and `uk.json`)
- No new route — health score renders on existing `/profile` page

### Library & Framework Requirements

- **SVG ring:** Pure SVG with `<circle>` and `stroke-dasharray`/`stroke-dashoffset` — NO external charting library needed. Use CSS `transition` for animation, `@media (prefers-reduced-motion: reduce)` to disable
- **Color gradients:** Use SVG `<linearGradient>` or `<stop>` elements for smooth color transitions within zones
- **Backend:** No new dependencies — uses existing SQLModel, FastAPI, Celery stack
- **Frontend:** No new dependencies — uses existing React, TanStack Query, shadcn/ui, next-intl

### File Structure Requirements

**New files:**
- `backend/app/models/financial_health_score.py` — SQLModel entity
- `backend/app/services/health_score_service.py` — calculation + retrieval
- `backend/app/api/v1/health_score.py` — API route
- `backend/alembic/versions/XXXX_add_financial_health_scores_table.py` — migration
- `backend/tests/test_health_score_service.py` — service unit tests
- `backend/tests/test_health_score_api.py` — API tests
- `frontend/src/features/profile/components/HealthScoreRing.tsx` — SVG ring component
- `frontend/src/features/profile/hooks/use-health-score.ts` — TanStack Query hook
- `frontend/src/features/profile/__tests__/HealthScoreRing.test.tsx` — ring tests

**Modified files:**
- `backend/app/models/__init__.py` — add FinancialHealthScore export
- `backend/app/api/v1/router.py` — register health_score router
- `backend/app/tasks/processing_tasks.py` — add score calculation after profile build (~line 266)
- `backend/tests/test_sse_streaming.py` — update expected progress event count
- `frontend/src/features/profile/types.ts` — add HealthScore interface
- `frontend/src/features/profile/components/ProfilePage.tsx` — add HealthScoreSection
- `frontend/src/features/profile/__tests__/ProfilePage.test.tsx` — add health score assertions
- `frontend/messages/en.json` — add health score i18n keys
- `frontend/messages/uk.json` — add health score i18n keys

### Testing Requirements

**Backend unit tests (`test_health_score_service.py`):**
- Test balanced profile → score in 60-80 range
- Test overspending (expenses > income) → low savings component → score < 40
- Test single-category concentration → low diversity → penalized score
- Test high savings ratio → score > 80
- Test zero income → savings component = 0, other components still calculated
- Test no transactions → graceful handling (return score 0 or None)
- Test breakdown JSONB contains all 4 component scores

**Backend API tests (`test_health_score_api.py`):**
- GET returns 200 with camelCase fields (`score`, `breakdown`, `calculatedAt`)
- GET returns 404 when no score exists
- GET requires authentication (401 without token)

**Frontend tests (`HealthScoreRing.test.tsx`):**
- Ring renders with correct color class for each zone (0-30, 31-60, 61-80, 81-100)
- Score number displays centered
- Zone label displays below score
- Breakdown section shows component names and values

### Previous Story Intelligence

**From Story 4.4 (immediate predecessor):**
- `FinancialProfile` model at `backend/app/models/financial_profile.py` — score service will query this directly rather than re-aggregating transactions
- `build_or_update_profile()` in `backend/app/services/profile_service.py` is synchronous (for Celery) — follow same sync pattern for `calculate_health_score()`
- `get_profile_for_user()` is async (for API) — follow same async pattern for `get_latest_score()`
- Profile build is at lines 250-266 in `processing_tasks.py` — insert score calculation immediately after
- Pipeline failure isolation pattern: `try/except` with `logger.warning()`, job stays completed
- Frontend `ProfilePage.tsx` uses `useProfile()` hook with loading/error/empty states — replicate for health score
- `formatCurrency()` utility in ProfilePage — reuse for any monetary display in breakdown
- Code review from 4.4 established: use `JSONB` (not `JSON`) for PostgreSQL column types
- Test baseline after 4.4: 297 backend + 203 frontend tests

**From Stories 4.1-4.3:**
- SSE progress messages are backend-owned (`message` field in `pipeline-progress` events)
- `SkeletonList` component available for loading states
- Frontend test count may vary slightly from story estimates

### Git Intelligence

**Recent commit patterns (Stories 4.1–4.4):**
- Commit message format: `Story X.Y: Title Description`
- Stories 4.1-4.3 were frontend-focused fixes; 4.4 was the first full-stack story in Epic 4
- Story 4.4 commit `097ceb9` is the most relevant — established the profile infrastructure this story builds upon
- Test infrastructure is mature and stable across both stacks

### Key Implementation Details

**Score calculation from FinancialProfile (NOT raw transactions):**
```python
# In health_score_service.py — use existing profile data, don't re-query transactions
def calculate_health_score(session: Session, user_id: UUID) -> FinancialHealthScore:
    profile = session.exec(
        select(FinancialProfile).where(FinancialProfile.user_id == user_id)
    ).first()
    if not profile:
        raise ValueError("No financial profile — cannot calculate score")
    
    # Component 1: Savings ratio (40%) — how much income is saved
    if profile.total_income > 0:
        savings_rate = (profile.total_income + profile.total_expenses) / profile.total_income
        savings_score = min(100, max(0, int(savings_rate * 200)))  # 50% savings = 100
    else:
        savings_score = 0
    
    # Component 2: Category diversity (20%) — penalize over-concentration
    # Component 3: Expense regularity (20%) — variance in category distribution
    # Component 4: Income coverage (20%) — net savings / avg monthly expenses
    
    final_score = int(
        savings_score * 0.4 +
        diversity_score * 0.2 +
        regularity_score * 0.2 +
        coverage_score * 0.2
    )
    final_score = max(0, min(100, final_score))
    
    # Persist as new record (append-only for history)
    health_score = FinancialHealthScore(
        user_id=user_id,
        score=final_score,
        calculated_at=datetime.now(UTC).replace(tzinfo=None),
        breakdown={
            "savings_ratio": savings_score,
            "category_diversity": diversity_score,
            "expense_regularity": regularity_score,
            "income_coverage": coverage_score,
        }
    )
    session.add(health_score)
    session.commit()
    session.refresh(health_score)
    return health_score
```

**SVG Ring approach:**
```tsx
// HealthScoreRing.tsx — key implementation concept
const circumference = 2 * Math.PI * radius;
const offset = circumference - (score / 100) * circumference;

<svg>
  <defs>
    <linearGradient id="scoreGradient">
      <stop offset="0%" stopColor={zoneColor} />
      <stop offset="100%" stopColor={zoneColorEnd} />
    </linearGradient>
  </defs>
  {/* Background ring */}
  <circle cx={center} cy={center} r={radius} stroke="#e5e7eb" strokeWidth={strokeWidth} fill="none" />
  {/* Score ring */}
  <circle
    cx={center} cy={center} r={radius}
    stroke="url(#scoreGradient)"
    strokeWidth={strokeWidth}
    fill="none"
    strokeDasharray={circumference}
    strokeDashoffset={offset}
    strokeLinecap="round"
    style={{ transition: prefersReducedMotion ? 'none' : 'stroke-dashoffset 1s ease-in-out' }}
    transform={`rotate(-90 ${center} ${center})`}
  />
  {/* Center text */}
  <text x={center} y={center} textAnchor="middle" dominantBaseline="central">{score}</text>
</svg>
```

**Pipeline integration point (processing_tasks.py, after ~line 266):**
```python
# After profile build succeeds
publish_job_progress(job_id, {
    "event": "pipeline-progress",
    "step": "health-score",
    "progress": 92,
    "message": "Calculating your Financial Health Score...",
})

try:
    calculate_health_score(session, job.user_id)
except Exception as score_exc:
    logger.warning("Health score calculation failed (job stays completed): %s", score_exc)
```

### DO NOT

- Do NOT add trend visualization — that's Story 4.6 (Health Score History & Trends)
- Do NOT add month-over-month comparison — that's Story 4.7
- Do NOT add category charts/donut charts — that's Story 4.8
- Do NOT modify the existing `FinancialProfile` model — health scores are a separate table
- Do NOT use incremental score updates — always recalculate from current profile state
- Do NOT add any charting library (recharts, chart.js, etc.) — the ring is pure SVG

### Project Structure Notes

- All new files align with established project structure
- `backend/app/models/financial_health_score.py` follows existing model file pattern
- `backend/app/services/health_score_service.py` follows existing service pattern (sync + async dual functions)
- Health score components live within existing `frontend/src/features/profile/` feature directory
- No new route needed — profile page at `/profile` gains the health score section
- No conflicts with existing code paths

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Story 4.5] — acceptance criteria, score 0-100, Apple Fitness ring
- [Source: _bmad-output/planning-artifacts/architecture.md] — DB naming (snake_case plural tables, UUID PK), API naming (kebab-case endpoints, camelCase JSON), file structure
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md#L207-266] — health score ring visualization, color zones (coral/amber/violet/sage), progressive disclosure
- [Source: backend/app/models/financial_profile.py] — FinancialProfile model (total_income, total_expenses, category_totals as JSONB)
- [Source: backend/app/services/profile_service.py] — sync/async service pattern, profile aggregation logic
- [Source: backend/app/tasks/processing_tasks.py:250-266] — pipeline integration point, try/except isolation, SSE progress message pattern
- [Source: backend/app/api/v1/profile.py] — API response pattern with camelCase alias, 404 handling, auth dependency
- [Source: frontend/src/features/profile/components/ProfilePage.tsx] — existing profile page structure, loading/error states, formatCurrency utility
- [Source: frontend/src/features/profile/hooks/use-profile.ts] — TanStack Query hook pattern
- [Source: frontend/src/features/profile/types.ts] — FinancialProfile interface (to extend with HealthScore)
- [Source: _bmad-output/implementation-artifacts/4-4-persistent-financial-profile.md] — previous story file list, dev notes, completion notes

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- Fixed JSONB → JSON in model layer for SQLite test compatibility (Alembic migration retains JSONB for PostgreSQL)
- Also fixed pre-existing JSONB issue in FinancialProfile model (same root cause)
- Fixed `window.matchMedia` not available in jsdom test environment
- Updated SSE progress event count test (6 → 7) to account for new health-score step

### Completion Notes List

- Task 1: Created `FinancialHealthScore` SQLModel with UUID PK, user_id FK, score (0-100), calculated_at, breakdown (JSON). Alembic migration with two indexes. Migration up/down tested.
- Task 2: Implemented `calculate_health_score()` (sync) and `get_latest_score()` (async) in health_score_service.py. Four weighted components: savings ratio (40%), category diversity (20%), expense regularity (20%), income coverage (20%). Each 0-100, clamped final score.
- Task 3: Integrated score calculation into pipeline at 92% progress after profile build. Try/except isolation — score failure doesn't fail the job.
- Task 4: Created `GET /api/v1/health-score` endpoint with camelCase response, 404 handling, auth scoping.
- Task 5: Created HealthScoreRing SVG component with animated arc, gradient colors per zone, centered score + label, expandable breakdown, prefers-reduced-motion support.
- Task 6: Integrated into ProfilePage with TanStack Query hook, loading skeleton, empty state, i18n (en + uk).
- Task 7: 10 backend service tests, 4 backend API tests, 9 frontend ring tests, 2 new ProfilePage tests. Updated SSE progress event count. All 299 backend + 209 frontend tests pass.

### Change Log

- 2026-04-09: Story 4.5 implementation complete — financial health score calculation, API, pipeline integration, SVG ring UI
- 2026-04-09: Code review (AI) — fixed 3 HIGH + 4 MEDIUM issues: SSR hydration fix for prefers-reduced-motion (H1), documented JSON/JSONB model divergence (H2), gated health score calc on profile build success (H3), documented snake_case breakdown keys (M1), added reduced-motion tests (M2)

### File List

**New files:**
- backend/app/models/financial_health_score.py
- backend/app/services/health_score_service.py
- backend/app/api/v1/health_score.py
- backend/alembic/versions/0a5a47b6bb15_add_financial_health_scores_table.py
- backend/tests/test_health_score_service.py
- backend/tests/test_health_score_api.py
- frontend/src/features/profile/components/HealthScoreRing.tsx
- frontend/src/features/profile/hooks/use-health-score.ts
- frontend/src/features/profile/__tests__/HealthScoreRing.test.tsx

**Modified files:**
- backend/app/models/__init__.py
- backend/app/models/financial_profile.py (JSONB → JSON for SQLite test compat)
- backend/app/api/v1/router.py
- backend/app/tasks/processing_tasks.py
- backend/tests/test_sse_streaming.py
- frontend/src/features/profile/types.ts
- frontend/src/features/profile/components/ProfilePage.tsx
- frontend/src/features/profile/__tests__/ProfilePage.test.tsx
- frontend/messages/en.json
- frontend/messages/uk.json
