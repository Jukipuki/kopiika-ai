# Story 4.6: Health Score History & Trends

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want to see how my Financial Health Score changes over time,
so that I can track my financial progress.

## Acceptance Criteria

1. **Given** a user has multiple Health Score records (from multiple uploads over time), **When** they view the Health Score section, **Then** a trend visualization shows score history with dates, rendered as a responsive SVG line/area chart below the existing HealthScoreRing.

2. **Given** the trend data, **When** it is displayed, **Then** the visualization is responsive on mobile and desktop, using accessible colors with text/icon fallbacks, and the chart respects `prefers-reduced-motion` for any entry animations.

3. **Given** a user with only one upload, **When** they view Health Score history, **Then** they see their current score with a message encouraging more uploads to see trends ("Upload more months to track your progress").

## Tasks / Subtasks

- [x] Task 1: Add history query to health score service (AC: #1)
  - [x] 1.1 In `backend/app/services/health_score_service.py`, add `get_score_history(session: AsyncSession, user_id: UUID) -> list[FinancialHealthScore]` — query all scores for user ordered by `calculated_at ASC` (leverages existing composite index `idx_financial_health_scores_user_id_calculated_at`)
  - [x] 1.2 Return full list (no pagination needed — scores grow at rate of ~1 per upload, will be small)

- [x] Task 2: Add history API endpoint (AC: #1)
  - [x] 2.1 In `backend/app/api/v1/health_score.py`, add `GET /api/v1/health-score/history` endpoint
  - [x] 2.2 Response model: `HealthScoreHistoryResponse` — list of `{ score, calculatedAt, breakdown }` items (camelCase via alias_generator, same pattern as existing `HealthScoreResponse`)
  - [x] 2.3 Return empty list `[]` if no scores exist (NOT 404 — empty array is valid)
  - [x] 2.4 Scope to authenticated user_id (reuse `get_current_user` dependency)

- [x] Task 3: Create frontend trend chart component (AC: #1, #2)
  - [x] 3.1 Create `frontend/src/features/profile/components/HealthScoreTrend.tsx` — pure SVG line/area chart
  - [x] 3.2 X-axis: dates (formatted with `Intl.DateTimeFormat` per locale); Y-axis: score 0-100
  - [x] 3.3 Plot score points connected by a smooth line with subtle area fill below
  - [x] 3.4 Color the line/area using the zone color of the LATEST score (coral/amber/violet/sage — reuse zone color logic from `HealthScoreRing.tsx`)
  - [x] 3.5 Show data points as small circles; on hover/tap show tooltip with exact score + date
  - [x] 3.6 Chart must be responsive: use `viewBox` + `width="100%"` SVG pattern, minimum height ~120px
  - [x] 3.7 Implement `prefers-reduced-motion`: skip any line-draw animation, render chart immediately
  - [x] 3.8 Accessible: add `role="img"` with `aria-label` describing the trend (e.g., "Health score trend: 45 on Mar 1, 62 on Apr 1")

- [x] Task 4: Create history hook and types (AC: #1)
  - [x] 4.1 Create `frontend/src/features/profile/hooks/use-health-score-history.ts` — TanStack Query hook for `GET /api/v1/health-score/history` (follow `use-health-score.ts` pattern, staleTime 5 min)
  - [x] 4.2 In `frontend/src/features/profile/types.ts`, add `HealthScoreHistoryItem` interface (same fields as `HealthScore`) and `HealthScoreHistory` as array type

- [x] Task 5: Integrate trend into Profile Page (AC: #1, #2, #3)
  - [x] 5.1 In `ProfilePage.tsx`, add `HealthScoreTrend` below the existing `HealthScoreRing` section
  - [x] 5.2 Show trend chart only when history has 2+ data points
  - [x] 5.3 When history has exactly 1 data point, show encouraging message: "Upload more months to track your progress" (i18n)
  - [x] 5.4 When history is empty (no score yet), show nothing (the existing empty state in HealthScoreRing handles this)
  - [x] 5.5 Add loading skeleton for trend section (simple rectangular skeleton matching chart dimensions)

- [x] Task 6: Add i18n strings (AC: #1, #3)
  - [x] 6.1 Add to `frontend/messages/en.json`: `profile.healthScore.trendTitle` ("Score History"), `profile.healthScore.trendEmpty` ("Upload more months to track your progress"), `profile.healthScore.trendLabel` ("Health score trend")
  - [x] 6.2 Add equivalent Ukrainian translations to `frontend/messages/uk.json`

- [x] Task 7: Tests (AC: #1-#3)
  - [x] 7.1 Backend service test: `backend/tests/test_health_score_service.py` — add test for `get_score_history()`: returns scores ordered by date, returns empty list for new user
  - [x] 7.2 Backend API test: `backend/tests/test_health_score_api.py` — add tests for `GET /api/v1/health-score/history`: returns list, returns empty array when no scores, requires auth
  - [x] 7.3 Frontend test: `frontend/src/features/profile/__tests__/HealthScoreTrend.test.tsx` — test chart renders SVG with correct number of data points, test single-point shows encouraging message, test empty state renders nothing, test accessible aria-label
  - [x] 7.4 Frontend test: update `ProfilePage.test.tsx` — add test that trend section appears with mock history data
  - [x] 7.5 Verify all existing tests still pass

## Dev Notes

### Scope Summary

**Primarily frontend story** with a small backend addition (history endpoint + service method). No new DB tables or migrations — the existing `financial_health_scores` table already stores append-only history records with a composite index optimized for this query. The trend chart is a pure SVG component — NO charting libraries.

### Architecture Compliance

**Database:**
- No schema changes — existing `financial_health_scores` table with composite index `idx_financial_health_scores_user_id_calculated_at` already supports efficient history queries
- Each pipeline run creates a new score record (append-only design from Story 4.5)

**API:**
- New endpoint: `GET /api/v1/health-score/history` (kebab-case, follows existing pattern)
- Returns array (not paginated — score records grow slowly, ~1 per upload)
- Response JSON: camelCase via Pydantic `alias_generator=to_camel`
- Auth: reuse existing `get_current_user` dependency

**Backend patterns:**
- Add async `get_score_history()` to existing `backend/app/services/health_score_service.py` — follow `get_latest_score()` pattern
- Add endpoint to existing `backend/app/api/v1/health_score.py` — no new router file needed

**Frontend patterns:**
- New component in existing `frontend/src/features/profile/components/` directory
- New hook in existing `frontend/src/features/profile/hooks/` directory
- SVG trend chart — pure SVG, NO external charting library (recharts, chart.js, d3, etc.)
- Responsive via SVG `viewBox` — no media queries needed for chart sizing
- i18n: next-intl (add to both `en.json` and `uk.json`)

### Library & Framework Requirements

- **Trend chart:** Pure SVG with `<polyline>` or `<path>` for lines, `<circle>` for data points — NO charting library. CSS `transition` for optional line-draw animation
- **Tooltips:** Simple HTML tooltip positioned via CSS `position: absolute` on hover/tap — or inline SVG `<text>` near data point. No tooltip library needed
- **Date formatting:** `Intl.DateTimeFormat` (built-in) — NOT date-fns or moment
- **Backend:** No new dependencies
- **Frontend:** No new dependencies

### File Structure Requirements

**New files:**
- `frontend/src/features/profile/components/HealthScoreTrend.tsx` — SVG trend chart component
- `frontend/src/features/profile/hooks/use-health-score-history.ts` — TanStack Query hook
- `frontend/src/features/profile/__tests__/HealthScoreTrend.test.tsx` — trend tests

**Modified files:**
- `backend/app/services/health_score_service.py` — add `get_score_history()` method
- `backend/app/api/v1/health_score.py` — add `/history` endpoint + response model
- `backend/tests/test_health_score_service.py` — add history query tests
- `backend/tests/test_health_score_api.py` — add history endpoint tests
- `frontend/src/features/profile/types.ts` — add `HealthScoreHistoryItem` type
- `frontend/src/features/profile/components/ProfilePage.tsx` — add trend section
- `frontend/src/features/profile/__tests__/ProfilePage.test.tsx` — add trend assertions
- `frontend/messages/en.json` — add trend i18n keys
- `frontend/messages/uk.json` — add trend i18n keys

### Testing Requirements

**Backend service tests (add to `test_health_score_service.py`):**
- `get_score_history()` returns scores ordered by `calculated_at` ascending
- `get_score_history()` returns empty list for user with no scores
- `get_score_history()` returns only scores for the requesting user (tenant isolation)

**Backend API tests (add to `test_health_score_api.py`):**
- `GET /api/v1/health-score/history` returns 200 with camelCase array items
- `GET /api/v1/health-score/history` returns empty `[]` when no scores
- `GET /api/v1/health-score/history` returns 401 without auth token

**Frontend tests (`HealthScoreTrend.test.tsx`):**
- Chart renders SVG with correct number of `<circle>` data points
- Chart line connects all points
- Single data point → shows encouraging message, no chart
- Empty data → renders nothing
- Accessible: `role="img"` and descriptive `aria-label` present
- Reduced motion: no animation class applied

### Previous Story Intelligence

**From Story 4.5 (immediate predecessor):**
- `FinancialHealthScore` model already exists at `backend/app/models/financial_health_score.py` — composite index `(user_id, calculated_at)` was specifically added for this story's history queries
- `get_latest_score()` in `health_score_service.py` is async and uses `select().where().order_by(desc(calculated_at)).limit(1)` — history query follows same pattern without `.limit(1)` and with `asc(calculated_at)`
- `HealthScoreResponse` Pydantic model already exists in `health_score.py` — reuse for history items
- `HealthScoreRing.tsx` has zone color logic (`getZoneColor()`) — extract or import for trend line coloring
- `use-health-score.ts` hook handles 404 → null gracefully — history hook returns empty array instead
- Frontend tests mock `window.matchMedia` for `prefers-reduced-motion` — reuse same mock pattern
- Code review from 4.5 established: use `JSON` (not `JSONB`) in SQLModel definitions for SQLite test compatibility
- Test baseline after 4.5: 299 backend + 209 frontend tests

**From Stories 4.1-4.3:**
- SSE progress messages are backend-owned — no new SSE step needed for this story
- `SkeletonList` component available for loading states

### Git Intelligence

**Recent commit patterns (Stories 4.1-4.5):**
- Commit message format: `Story X.Y: Title Description`
- Story 4.5 commit `dd3256e` is the most relevant — established the health score infrastructure this story extends
- All health score files are already in place; this story adds history functionality on top

### Key Implementation Details

**History service method:**
```python
# In health_score_service.py — add alongside existing get_latest_score()
async def get_score_history(session: AsyncSession, user_id: UUID) -> list[FinancialHealthScore]:
    result = await session.exec(
        select(FinancialHealthScore)
        .where(FinancialHealthScore.user_id == user_id)
        .order_by(FinancialHealthScore.calculated_at.asc())
    )
    return list(result.all())
```

**History API endpoint:**
```python
# In health_score.py — add alongside existing get_health_score()
@router.get("/health-score/history")
async def get_health_score_history(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[HealthScoreResponse]:
    scores = await get_score_history(session, current_user.id)
    return scores  # Pydantic serializes with camelCase aliases
```

**SVG trend chart approach:**
```tsx
// HealthScoreTrend.tsx — key implementation concept
const padding = { top: 10, right: 10, bottom: 20, left: 30 };
const chartWidth = 300; // viewBox width
const chartHeight = 120;

// Scale data points to SVG coordinates
const xScale = (i: number) => padding.left + (i / (data.length - 1)) * (chartWidth - padding.left - padding.right);
const yScale = (score: number) => chartHeight - padding.bottom - (score / 100) * (chartHeight - padding.top - padding.bottom);

// Build polyline points string
const points = data.map((d, i) => `${xScale(i)},${yScale(d.score)}`).join(' ');

<svg viewBox={`0 0 ${chartWidth} ${chartHeight}`} width="100%" role="img" aria-label={trendAriaLabel}>
  {/* Y-axis labels: 0, 50, 100 */}
  {/* Area fill */}
  <polygon points={`${points} ${xScale(data.length-1)},${yScale(0)} ${xScale(0)},${yScale(0)}`} fill={zoneColor} opacity={0.1} />
  {/* Line */}
  <polyline points={points} fill="none" stroke={zoneColor} strokeWidth={2} />
  {/* Data points */}
  {data.map((d, i) => <circle key={i} cx={xScale(i)} cy={yScale(d.score)} r={3} fill={zoneColor} />)}
  {/* X-axis date labels */}
</svg>
```

### DO NOT

- Do NOT add month-over-month spending comparison — that's Story 4.7
- Do NOT add category spending breakdown charts — that's Story 4.8
- Do NOT install any charting library (recharts, chart.js, d3, nivo, etc.) — trend chart is pure SVG
- Do NOT paginate the history endpoint — scores grow slowly (~1 per upload); simple array is sufficient
- Do NOT create a new Alembic migration — no schema changes needed
- Do NOT modify the existing `HealthScoreRing` component — the trend chart is a separate component rendered below it
- Do NOT add drill-down into individual breakdown history — just show overall score trend

### Project Structure Notes

- All new files align with established project structure
- New frontend component and hook go in existing `frontend/src/features/profile/` directories
- Backend additions extend existing files — no new service or API files needed
- No new route needed — trend renders on existing `/profile` page within the health score section
- No conflicts with existing code paths

### References

- [Source: _bmad-output/planning-artifacts/epics.md#L981-999 — Story 4.6] — acceptance criteria, trend visualization, single-upload message
- [Source: _bmad-output/planning-artifacts/architecture.md] — DB naming, API naming, frontend patterns
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md] — Apple Fitness-inspired pattern, progressive disclosure Layer 2 includes historical trends
- [Source: backend/app/models/financial_health_score.py] — FinancialHealthScore model with composite index for history queries
- [Source: backend/app/services/health_score_service.py] — existing get_latest_score() async pattern to follow
- [Source: backend/app/api/v1/health_score.py] — existing endpoint and HealthScoreResponse model to reuse
- [Source: frontend/src/features/profile/components/HealthScoreRing.tsx] — zone color logic to reuse
- [Source: frontend/src/features/profile/hooks/use-health-score.ts] — TanStack Query hook pattern to follow
- [Source: _bmad-output/implementation-artifacts/4-5-financial-health-score-calculation-display.md] — previous story intelligence, file list, dev notes

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

None — clean implementation with no blockers.

### Completion Notes List

- Task 1: Added `get_score_history()` async method to `health_score_service.py` — queries all scores for user ordered by `calculated_at ASC`, returns list (empty for new users)
- Task 2: Added `GET /api/v1/health-score/history` endpoint returning `list[HealthScoreResponse]` with camelCase serialization, empty array for no scores, scoped to authenticated user
- Task 3: Created `HealthScoreTrend.tsx` — pure SVG line/area chart with zone coloring, responsive viewBox, tooltips on hover/tap, `prefers-reduced-motion` support, accessible `role="img"` + `aria-label`
- Task 4: Created `use-health-score-history.ts` TanStack Query hook (5 min staleTime); added `HealthScoreHistoryItem` and `HealthScoreHistory` types
- Task 5: Integrated trend chart into ProfilePage below HealthScoreRing — shows chart for 2+ points, encouraging message for 1 point, nothing for empty, loading skeleton
- Task 6: Added i18n strings (trendTitle, trendEmpty, trendLabel) in English and Ukrainian
- Task 7: Added 6 backend tests (3 service + 3 API) and 7 frontend tests (6 HealthScoreTrend + 1 ProfilePage trend integration). Full suite: 305 backend + 218 frontend, zero regressions.

### Change Log

- 2026-04-09: Story 4.6 implementation complete — health score history endpoint, SVG trend chart, i18n, full test coverage
- 2026-04-09: Code review (AI) — fixed 6 issues: extracted shared zone utils (score-zones.ts), replaced dead `animate-draw-line` CSS class with inline stroke-dasharray animation, gated trend section behind health score existence, clamped tooltip to viewBox, used semantic React keys, added non-reduced-motion test. Status → done.

### File List

**New files:**
- `frontend/src/features/profile/components/HealthScoreTrend.tsx`
- `frontend/src/features/profile/hooks/use-health-score-history.ts`
- `frontend/src/features/profile/__tests__/HealthScoreTrend.test.tsx`
- `frontend/src/features/profile/score-zones.ts`

**Modified files:**
- `backend/app/services/health_score_service.py`
- `backend/app/api/v1/health_score.py`
- `backend/tests/test_health_score_service.py`
- `backend/tests/test_health_score_api.py`
- `frontend/src/features/profile/types.ts`
- `frontend/src/features/profile/components/ProfilePage.tsx`
- `frontend/src/features/profile/components/HealthScoreRing.tsx`
- `frontend/src/features/profile/__tests__/ProfilePage.test.tsx`
- `frontend/messages/en.json`
- `frontend/messages/uk.json`
