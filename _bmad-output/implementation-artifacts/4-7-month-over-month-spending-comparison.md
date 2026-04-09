# Story 4.7: Month-over-Month Spending Comparison

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want to see how my spending changes month over month,
so that I can identify improving or worsening trends.

## Acceptance Criteria

1. **Given** a user has uploaded statements covering at least two different months, **When** the system compares the periods, **Then** month-over-month changes are calculated and displayed per category (e.g., "Groceries: +12% vs last month"), comparing the two most recent months.

2. **Given** month-over-month data is available, **When** it is displayed on the profile page, **Then** increases are shown with up-arrow indicators and decreases with down-arrow indicators, using color + icon + text (not color alone) to meet WCAG 2.1 AA accessibility standards.

3. **Given** a user has data for only one month, **When** they view the comparison section, **Then** they see a friendly message ("Upload another month to see spending trends") instead of empty charts.

## Tasks / Subtasks

- [x] Task 1: Add monthly spending service function (AC: #1)
  - [x] 1.1 In `backend/app/services/profile_service.py`, add `get_monthly_comparison(session: AsyncSession, user_id: UUID) -> dict | None` — queries `Transaction` table, groups expenses (amount < 0) by `EXTRACT(YEAR, MONTH)` from `date` field and `category`, returns per-category totals for the two most recent calendar months
  - [x] 1.2 Return structure: `{"current_month": "2026-03", "previous_month": "2026-02", "categories": [{"category": str, "current_amount": int, "previous_amount": int, "change_percent": float, "change_amount": int}], "total_current": int, "total_previous": int, "total_change_percent": float}`
  - [x] 1.3 Handle edge cases: category exists in only one month (treat missing as 0), uncategorized transactions (`category IS NULL`) grouped as `"uncategorized"`, return `None` if fewer than 2 distinct months exist
  - [x] 1.4 Sort categories by absolute `change_amount` descending (biggest movers first)
  - [x] 1.5 Amounts are kopiykas (integers, stored as negative for expenses) — return absolute values for display (positive kopiykas)

- [x] Task 2: Add monthly comparison API endpoint (AC: #1)
  - [x] 2.1 In `backend/app/api/v1/profile.py`, add `GET /api/v1/profile/monthly-comparison` endpoint
  - [x] 2.2 Response model: `MonthlyComparisonResponse` with Pydantic `alias_generator=to_camel` — fields: `currentMonth`, `previousMonth`, `categories` (list of `CategoryComparison`), `totalCurrent`, `totalPrevious`, `totalChangePercent`
  - [x] 2.3 Return `200` with data when 2+ months available; return `200` with `null` body when < 2 months (NOT 404 — absence of comparison data is not an error, frontend uses null to show encouraging message)
  - [x] 2.4 Auth: reuse `get_current_user` dependency, scope to `current_user.id`

- [x] Task 3: Create frontend types and hook (AC: #1)
  - [x] 3.1 In `frontend/src/features/profile/types.ts`, add `CategoryComparison` interface (`category: string`, `currentAmount: number`, `previousAmount: number`, `changePercent: number`, `changeAmount: number`) and `MonthlyComparison` interface (`currentMonth: string`, `previousMonth: string`, `categories: CategoryComparison[]`, `totalCurrent: number`, `totalPrevious: number`, `totalChangePercent: number`)
  - [x] 3.2 Create `frontend/src/features/profile/hooks/use-monthly-comparison.ts` — TanStack Query hook for `GET /api/v1/profile/monthly-comparison`, queryKey `["monthly-comparison"]`, staleTime 5 min, follow `use-profile.ts` pattern. Returns `null` when no comparison data available (do NOT treat as error)

- [x] Task 4: Create MonthlyComparison component (AC: #1, #2)
  - [x] 4.1 Create `frontend/src/features/profile/components/MonthlyComparison.tsx`
  - [x] 4.2 Render a card with title "Month-over-Month Spending" (i18n) showing `currentMonth` vs `previousMonth` as subtitle
  - [x] 4.3 For each category row: display category name, current month amount (hryvnias), change percentage with direction indicator
  - [x] 4.4 Direction indicators — accessible (color + icon + text, not color alone):
    - Increase (spending went up): red/coral text + up-arrow icon (`ArrowUp` or Unicode `↑`) + "+X%" text
    - Decrease (spending went down): green/sage text + down-arrow icon (`ArrowDown` or Unicode `↓`) + "-X%" text
    - No change: neutral/gray text + dash icon + "0%" text
  - [x] 4.5 Show total spending comparison row at bottom (bold/separated): total current vs total previous with overall change %
  - [x] 4.6 Format amounts using `Intl.NumberFormat` for hryvnia display (kopiykas ÷ 100), respect locale
  - [x] 4.7 Responsive: single-column list on mobile, no horizontal scroll needed

- [x] Task 5: Integrate into Profile Page (AC: #1, #2, #3)
  - [x] 5.1 In `ProfilePage.tsx`, add `MonthlyComparison` section after the Health Score trend section and before the existing Category Breakdown section
  - [x] 5.2 When comparison data is available (2+ months): show the MonthlyComparison component
  - [x] 5.3 When comparison data is `null` (< 2 months): show encouraging message "Upload another month to see spending trends" (i18n)
  - [x] 5.4 When comparison data is loading: show skeleton placeholder (rectangular skeleton matching section dimensions)
  - [x] 5.5 Wire up the `useMonthlyComparison` hook in ProfilePage

- [x] Task 6: Add i18n strings (AC: #1, #2, #3)
  - [x] 6.1 Add to `frontend/messages/en.json` under `profile.monthlyComparison`:
    - `title`: "Month-over-Month Spending"
    - `subtitle`: "{current} vs {previous}"
    - `noData`: "Upload another month to see spending trends"
    - `totalLabel`: "Total Spending"
    - `increase`: "increase"
    - `decrease`: "decrease"
    - `noChange`: "no change"
    - `uncategorized`: "Uncategorized"
  - [x] 6.2 Add equivalent Ukrainian translations to `frontend/messages/uk.json`

- [x] Task 7: Tests (AC: #1-#3)
  - [x] 7.1 Backend service test: add to `backend/tests/test_profile_service.py` — test `get_monthly_comparison()`: returns correct comparison for 2 months, returns None for 1 month, handles categories present in only one month (missing = 0), groups null category as "uncategorized", sorts by biggest movers, tenant isolation
  - [x] 7.2 Backend API test: add to `backend/tests/test_profile_api.py` — test `GET /api/v1/profile/monthly-comparison`: returns 200 with camelCase data, returns 200 with null for single month, returns 401 without auth
  - [x] 7.3 Frontend test: create `frontend/src/features/profile/__tests__/MonthlyComparison.test.tsx` — test renders category rows with correct arrows and percentages, test increase shows up-arrow in red, test decrease shows down-arrow in green, test total row renders, test accessible indicators (icon + text, not color alone), test currency formatting
  - [x] 7.4 Frontend test: update `frontend/src/features/profile/__tests__/ProfilePage.test.tsx` — add test that MonthlyComparison section appears with mock data, test encouraging message appears when comparison is null
  - [x] 7.5 Verify all existing tests still pass

## Dev Notes

### Scope Summary

**Full-stack story** with a new backend service function + API endpoint and a new frontend component. No new DB tables or migrations — comparison is computed on-the-fly from the existing `transactions` table. No charting library needed — this is a styled list with direction indicators.

### Architecture Compliance

**Database:**
- No schema changes — queries the existing `transactions` table directly
- `Transaction` model: `date` (datetime), `category` (Optional[str], max 50), `amount` (int, kopiykas — negative for expenses)
- Group by `EXTRACT(YEAR FROM date)`, `EXTRACT(MONTH FROM date)`, `category` using SQLAlchemy `func.extract()`
- Filter to expenses only: `Transaction.amount < 0`
- Scope to `Transaction.user_id == user_id` (tenant isolation)

**API:**
- New endpoint: `GET /api/v1/profile/monthly-comparison` (kebab-case, follows existing patterns like `/health-score/history`)
- Added to existing `backend/app/api/v1/profile.py` — no new router file
- Response JSON: camelCase via Pydantic `alias_generator=to_camel`
- Returns `200` with `null` for insufficient data (not 404 — same pattern as health score history returning empty array)
- Auth: reuse existing `get_current_user` dependency
- Money as integers (kopiykas) per architecture enforcement rule #4

**Backend patterns:**
- Add async `get_monthly_comparison()` to existing `backend/app/services/profile_service.py`
- Follow existing async query patterns from `health_score_service.py`
- Use `func.extract('year', Transaction.date)` and `func.extract('month', Transaction.date)` for grouping
- Use `func.abs(Transaction.amount)` to return positive kopiykas for display

**Frontend patterns:**
- New component in `frontend/src/features/profile/components/`
- New hook in `frontend/src/features/profile/hooks/`
- TanStack Query for data fetching (no raw `fetch`)
- i18n via next-intl (`useTranslations('profile.monthlyComparison')`)
- Tailwind CSS for styling — no custom CSS files
- Component naming: PascalCase (`MonthlyComparison.tsx`)
- Hook naming: kebab-case (`use-monthly-comparison.ts`)

### Library & Framework Requirements

- **No new dependencies** — backend or frontend
- **Currency formatting:** `Intl.NumberFormat` (built-in) — format kopiykas ÷ 100 as hryvnias. Use `style: 'currency', currency: 'UAH'` or manual `₴` prefix with number formatting
- **Date formatting:** `Intl.DateTimeFormat` with `{ year: 'numeric', month: 'long' }` for month labels (e.g., "March 2026" / "Березень 2026")
- **Percentage formatting:** Simple `Math.round()` or `toFixed(1)` — no library needed
- **Icons:** Use Unicode arrows (`↑` / `↓` / `–`) or inline SVG arrows — do NOT import an icon library. If shadcn/ui already provides arrow icons from lucide-react, those are acceptable since lucide-react is already a dependency
- **Backend:** No new dependencies. SQLAlchemy `func.extract()` is built-in

### File Structure Requirements

**New files:**
- `frontend/src/features/profile/components/MonthlyComparison.tsx` — comparison component
- `frontend/src/features/profile/hooks/use-monthly-comparison.ts` — TanStack Query hook
- `frontend/src/features/profile/__tests__/MonthlyComparison.test.tsx` — component tests

**Modified files:**
- `backend/app/services/profile_service.py` — add `get_monthly_comparison()` function
- `backend/app/api/v1/profile.py` — add `/monthly-comparison` endpoint + `MonthlyComparisonResponse` model
- `backend/tests/test_profile_service.py` — add monthly comparison service tests
- `backend/tests/test_profile_api.py` — add monthly comparison API tests
- `frontend/src/features/profile/types.ts` — add `CategoryComparison` and `MonthlyComparison` types
- `frontend/src/features/profile/components/ProfilePage.tsx` — integrate MonthlyComparison section
- `frontend/src/features/profile/__tests__/ProfilePage.test.tsx` — add comparison section assertions
- `frontend/messages/en.json` — add `profile.monthlyComparison.*` keys
- `frontend/messages/uk.json` — add Ukrainian translations

### Testing Requirements

**Backend service tests (add to `test_profile_service.py`):**
- `get_monthly_comparison()` with 2 months of transactions returns correct per-category comparison
- `get_monthly_comparison()` with 1 month returns `None`
- `get_monthly_comparison()` with 0 transactions returns `None`
- Category present in month A but not month B → previous_amount is 0, change is +100%
- Category present in month B but not month A → current_amount is 0, change is -100%
- `category IS NULL` transactions grouped under `"uncategorized"`
- Results sorted by absolute change_amount descending
- Only expenses (amount < 0) included — income transactions excluded
- Tenant isolation: only returns data for the requesting user

**Backend API tests (add to `test_profile_api.py`):**
- `GET /api/v1/profile/monthly-comparison` returns 200 with camelCase fields
- Returns 200 with `null` when < 2 months
- Returns 401 without auth token

**Frontend tests (`MonthlyComparison.test.tsx`):**
- Renders category rows with correct category names and amounts
- Increase category shows up-arrow + positive percentage in red/coral
- Decrease category shows down-arrow + negative percentage in green/sage
- Total row renders with overall change
- Accessible: direction conveyed by icon + text, not color alone
- Currency amounts formatted correctly (kopiykas → hryvnias)
- Empty/null data renders nothing (ProfilePage handles the empty state)

**Frontend integration tests (update `ProfilePage.test.tsx`):**
- MonthlyComparison section renders when comparison data is available
- Encouraging message renders when comparison data is `null`
- Loading skeleton renders while data is fetching

### Previous Story Intelligence

**From Story 4.6 (immediate predecessor):**
- SVG trend chart was pure SVG with no charting library — same "no external library" philosophy applies here
- `score-zones.ts` was extracted as shared utility — consider if any shared formatting utils are needed (probably not, this story is simpler)
- Test baseline after 4.6: 305 backend + 218 frontend tests (verify no regressions)
- Code review established: use `JSON` (not `JSONB`) in SQLModel definitions for SQLite test compatibility — relevant if adding any JSON fields (not needed for this story since we compute on-the-fly)

**From Story 4.4 (Financial Profile):**
- `FinancialProfile` model stores all-time aggregates only — `category_totals: dict[str, int]` is NOT per-month. Do NOT try to derive monthly data from the profile model — query `Transaction` table directly
- `profile_service.build_or_update_profile()` is sync (called from Celery pipeline) — the new `get_monthly_comparison()` must be async (called from API layer)
- `ProfileResponse` already uses `alias_generator=to_camel` — follow same pattern for `MonthlyComparisonResponse`

**From Story 4.5 (Health Score):**
- Established the pattern of separate Pydantic response models per endpoint
- `get_current_user` dependency injection pattern for auth

### Git Intelligence

**Recent commit patterns (Stories 4.1-4.6):**
- Commit message format: `Story X.Y: Title Description`
- Story 4.6 commit `db0b828` is the most recent — all health score infrastructure is in place
- Profile page currently has: HealthScoreRing, HealthScoreTrend, summary cards, period info, category breakdown list

### Key Implementation Details

**Monthly comparison service function:**
```python
# In profile_service.py — add alongside existing functions
from sqlalchemy import func, case

async def get_monthly_comparison(session: AsyncSession, user_id: UUID) -> dict | None:
    """Compare spending by category for the two most recent months."""
    # Step 1: Find distinct months with expenses
    month_query = (
        select(
            func.extract('year', Transaction.date).label('year'),
            func.extract('month', Transaction.date).label('month'),
        )
        .where(Transaction.user_id == user_id, Transaction.amount < 0)
        .group_by('year', 'month')
        .order_by(func.extract('year', Transaction.date).desc(),
                  func.extract('month', Transaction.date).desc())
        .limit(2)
    )
    months = (await session.exec(month_query)).all()
    if len(months) < 2:
        return None

    current_year, current_month = int(months[0].year), int(months[0].month)
    previous_year, previous_month = int(months[1].year), int(months[1].month)

    # Step 2: Get per-category totals for both months
    # Use func.coalesce(Transaction.category, 'uncategorized') for null categories
    # Use func.abs() to return positive kopiykas
    # Group by year, month, category
    # ... (standard SQLAlchemy GROUP BY query)
```

**API endpoint:**
```python
# In profile.py — add alongside existing get_profile()
@router.get("/profile/monthly-comparison")
async def get_monthly_comparison(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MonthlyComparisonResponse | None:
    result = await profile_service.get_monthly_comparison(session, current_user.id)
    if result is None:
        return None
    return MonthlyComparisonResponse(**result)
```

**Frontend component structure:**
```tsx
// MonthlyComparison.tsx — key rendering concept
function MonthlyComparison({ data }: { data: MonthlyComparison }) {
  const t = useTranslations('profile.monthlyComparison');

  return (
    <Card>
      <h3>{t('title')}</h3>
      <p className="text-sm text-muted-foreground">
        {t('subtitle', { current: formatMonth(data.currentMonth), previous: formatMonth(data.previousMonth) })}
      </p>
      <ul>
        {data.categories.map((cat) => (
          <li key={cat.category} className="flex justify-between items-center py-2">
            <span>{cat.category === 'uncategorized' ? t('uncategorized') : cat.category}</span>
            <span className="flex items-center gap-1">
              <span>{formatCurrency(cat.currentAmount)}</span>
              <ChangeIndicator changePercent={cat.changePercent} />
            </span>
          </li>
        ))}
      </ul>
      {/* Total row */}
    </Card>
  );
}

function ChangeIndicator({ changePercent }: { changePercent: number }) {
  if (changePercent > 0) return <span className="text-red-500">↑ +{changePercent}%</span>;
  if (changePercent < 0) return <span className="text-green-600">↓ {changePercent}%</span>;
  return <span className="text-gray-400">– 0%</span>;
}
```

### DO NOT

- Do NOT install any charting library — this is a styled list, not a chart
- Do NOT add a new database table or Alembic migration — compute from existing `transactions` table
- Do NOT modify the existing `FinancialProfile` model or `build_or_update_profile()` — monthly comparison is independent
- Do NOT add category spending breakdown — that's Story 4.8
- Do NOT paginate the monthly comparison — it's a fixed comparison of 2 months
- Do NOT include income transactions — this compares expenses only (amount < 0)
- Do NOT use `FinancialProfile.category_totals` for monthly data — it's all-time aggregate, not per-month. Query `Transaction` directly
- Do NOT use date-fns, moment, or any date library — use built-in `Intl.DateTimeFormat`
- Do NOT create a new router file — add endpoint to existing `profile.py`

### Project Structure Notes

- All new files align with established project structure (`features/profile/components/`, `features/profile/hooks/`)
- Backend additions extend existing `profile_service.py` and `profile.py` — no new files needed
- MonthlyComparison section integrates into existing `ProfilePage.tsx` between HealthScoreTrend and Category Breakdown
- No conflicts with existing code paths
- No new route needed — renders on existing `/profile` page

### References

- [Source: _bmad-output/planning-artifacts/epics.md#L1001-1019 — Story 4.7] — acceptance criteria, per-category comparison, arrow indicators, single-month message
- [Source: _bmad-output/planning-artifacts/architecture.md] — DB naming (snake_case), API naming (kebab-case URLs, camelCase JSON), frontend patterns (TanStack Query, feature folders), enforcement rules (money as kopiykas, UUID IDs, user_id scoping)
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md] — "Month-over-month comparison cards that show trajectory", Critical Success Moment 4 example copy
- [Source: backend/app/models/transaction.py] — Transaction model with `date`, `category`, `amount` fields
- [Source: backend/app/models/financial_profile.py] — FinancialProfile model (all-time aggregate only — do NOT use for monthly data)
- [Source: backend/app/services/profile_service.py] — existing `build_or_update_profile()` and `get_profile_for_user()` patterns
- [Source: backend/app/api/v1/profile.py] — existing `GET /api/v1/profile` endpoint and `ProfileResponse` model
- [Source: frontend/src/features/profile/components/ProfilePage.tsx] — current profile page structure (HealthScoreRing, HealthScoreTrend, summary cards, category breakdown)
- [Source: frontend/src/features/profile/hooks/use-profile.ts] — TanStack Query hook pattern to follow
- [Source: frontend/src/features/profile/types.ts] — existing FinancialProfile and HealthScore types
- [Source: _bmad-output/implementation-artifacts/4-6-health-score-history-trends.md] — previous story intelligence, test counts, file patterns

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- All 8 new backend tests pass (service + API)
- All 11 new frontend tests pass (MonthlyComparison component + ProfilePage integration)
- Full regression suites pass: backend + frontend

### Completion Notes List

- Implemented `get_monthly_comparison()` async service function in profile_service.py — queries Transaction table, groups expenses by year/month/category, compares two most recent months
- Added `GET /api/v1/profile/monthly-comparison` endpoint with camelCase Pydantic response models, returns 200 with null for insufficient data
- Created `MonthlyComparison.tsx` component with accessible direction indicators (color + icon + sr-only text)
- Integrated into ProfilePage between Health Score Trend and Category Breakdown sections
- Added i18n strings for both English and Ukrainian
- Comprehensive test coverage: 8 backend service tests, 3 API tests, 11 frontend component tests, 3 ProfilePage integration tests

### File List

**New files:**
- `frontend/src/features/profile/components/MonthlyComparison.tsx`
- `frontend/src/features/profile/hooks/use-monthly-comparison.ts`
- `frontend/src/features/profile/__tests__/MonthlyComparison.test.tsx`
- `frontend/src/features/profile/format.ts` — shared `formatCurrency` utility (extracted during review)

**Modified files:**
- `backend/app/services/profile_service.py` — added `get_monthly_comparison()` function
- `backend/app/api/v1/profile.py` — added `/monthly-comparison` endpoint + response models
- `backend/tests/test_profile_service.py` — added 9 monthly comparison service tests (incl. cross-year boundary)
- `backend/tests/test_profile_api.py` — added 3 monthly comparison API tests
- `frontend/src/features/profile/types.ts` — added `CategoryComparison` and `MonthlyComparison` interfaces
- `frontend/src/features/profile/components/ProfilePage.tsx` — integrated MonthlyComparison section + error state handling
- `frontend/src/features/profile/__tests__/ProfilePage.test.tsx` — added 4 comparison section tests (incl. error state)
- `frontend/src/features/profile/__tests__/MonthlyComparison.test.tsx` — added currency + subtitle formatting tests
- `frontend/messages/en.json` — added `profile.monthlyComparison.*` keys (incl. `loadFailed`)
- `frontend/messages/uk.json` — added Ukrainian translations (incl. `loadFailed`)

## Senior Developer Review (AI)

**Reviewed by:** Oleh on 2026-04-09
**Outcome:** Approved with fixes applied

**Findings (6 total: 2 HIGH, 2 MEDIUM, 2 LOW):**

1. **HIGH — Fixed:** Cross-year boundary SQL bug in `get_monthly_comparison()`. WHERE clause filtered year and month independently, which would leak data from wrong year-month combinations (e.g., Jan 2025 into a Dec 2025 vs Jan 2026 comparison). Fixed with paired OR conditions.
2. **HIGH — Fixed:** API error silently masked as "no data" in ProfilePage. `isError` from `useMonthlyComparison()` was never consumed — network failures showed encouraging "upload more" message instead of error. Added error state handling + `loadFailed` i18n key.
3. **MEDIUM — Fixed:** `formatCurrency` duplicated in MonthlyComparison.tsx and ProfilePage.tsx. Extracted to shared `format.ts` utility.
4. **MEDIUM — Fixed:** Missing test for currency formatting (kopiykas → hryvnias). Added test verifying amounts render as hryvnias, not raw kopiykas.
5. **LOW — Skipped:** Debug log inconsistency (says 8 backend tests, actually 11). Doc-only, no code impact.
6. **LOW — Fixed:** Missing test for subtitle month formatting. Added test verifying formatted month names render instead of raw ISO strings.

## Change Log

- 2026-04-09: Implemented Story 4.7 — Month-over-Month Spending Comparison. Added backend service function and API endpoint for comparing the two most recent months of spending by category. Created frontend MonthlyComparison component with accessible direction indicators (WCAG 2.1 AA). Integrated into ProfilePage with loading skeleton and encouraging message for single-month users. Added EN/UK i18n strings. Full test coverage across backend (11 new tests) and frontend (14 new tests).
- 2026-04-09: Code review — fixed 5 issues: cross-year boundary SQL bug, API error masking, formatCurrency duplication, added currency formatting test, added subtitle formatting test. All 24 backend + 25 frontend tests pass.
