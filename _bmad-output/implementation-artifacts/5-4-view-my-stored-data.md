# Story 5.4: View My Stored Data

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want to view what data the system has stored about me,
So that I have transparency and control over my information.

## Acceptance Criteria

1. **Given** I am authenticated, **When** I navigate to a "My Data" section in settings, **Then** I see a summary of all data stored: number of uploads, number of transactions, financial profile data, Health Score history, and consent records
2. **Given** the data summary page, **When** I view it, **Then** I can see the date ranges of my transaction data, categories detected, and total number of insights generated
3. **Given** the data summary API endpoint `GET /api/v1/users/me/data-summary`, **When** it responds, **Then** all data is scoped to the authenticated user_id and serialized in camelCase JSON

## Tasks / Subtasks

- [x] Task 1: Create data summary API endpoint (AC: #3)
  - [x] 1.1 Create `backend/app/api/v1/data_summary.py` — new router with `GET /users/me/data-summary` endpoint using `get_current_user_id` dependency
  - [x] 1.2 Define Pydantic response schema `DataSummaryResponse` with camelCase alias_generator (`ConfigDict(alias_generator=to_camel, populate_by_name=True)`) containing: `uploadCount`, `transactionCount`, `transactionDateRange` (earliest/latest dates), `categoriesDetected` (list of unique category names), `insightCount`, `financialProfile` (latest summary or null), `healthScoreHistory` (list of score+date entries), `consentRecords` (list of type+grantedAt entries)
  - [x] 1.3 Implement query logic: aggregate counts from `uploads`, `transactions`, `insights` tables; extract distinct categories from `transactions`; fetch latest `financial_profiles` row; fetch all `financial_health_scores` ordered by `calculated_at`; fetch all `user_consents` — all scoped to authenticated `user_id`
  - [x] 1.4 Register router in `backend/app/api/v1/router.py`

- [x] Task 2: Backend tests (AC: #3)
  - [x] 2.1 Create `backend/tests/test_data_summary_api.py` — test endpoint returns correct shape with sample data (uploads, transactions, profile, scores, consents, insights)
  - [x] 2.2 Test empty state — new user with no data returns zero counts, null profile, empty arrays
  - [x] 2.3 Test tenant isolation — user A cannot see user B's data summary

- [x] Task 3: Create "My Data" section in settings UI (AC: #1, #2)
  - [x] 3.1 Create `frontend/src/features/settings/components/MyDataSection.tsx` — displays data summary with labeled stats (upload count, transaction count, date range, categories, insight count, health score timeline, consent records)
  - [x] 3.2 Create `frontend/src/features/settings/hooks/use-data-summary.ts` — hook to fetch `GET /api/v1/users/me/data-summary` following the same pattern as `use-user-profile.ts` (native fetch + AbortController + session token)
  - [x] 3.3 Integrate `MyDataSection` into `SettingsPage.tsx` — add as a new section below existing AccountInfoSection and LanguageSection
  - [x] 3.4 Add i18n keys under `settings.myData.*` namespace in `frontend/messages/en.json` and `frontend/messages/uk.json` (section title, stat labels, empty states, date formatting labels)

- [x] Task 4: Frontend tests (AC: #1, #2)
  - [x] 4.1 Create `frontend/src/features/settings/__tests__/MyDataSection.test.tsx` — renders all stats correctly from mocked API response, handles loading state, handles error state with retry
  - [x] 4.2 Update `frontend/src/features/settings/__tests__/SettingsPage.test.tsx` — assert `MyDataSection` renders within settings page
  - [x] 4.3 Run full test suite — confirm green, zero regressions

## Dev Notes

### Architecture & Patterns

- **Full-stack story**: new backend API endpoint + new frontend settings section. No database migrations needed — all data already exists in current tables.
- **Backend router pattern**: Follow `backend/app/api/v1/uploads.py` as the reference implementation. Use `APIRouter(prefix="/users/me", tags=["user-data"])`. Auth via `Annotated[uuid.UUID, Depends(get_current_user_id)]` from `backend/app/api/deps.py`.
- **Response schema pattern**: Pydantic BaseModel with `ConfigDict(alias_generator=to_camel, populate_by_name=True)` for automatic camelCase serialization. See existing schemas in uploads.py, health_score.py for examples.
- **Frontend settings pattern**: `SettingsPage.tsx` renders section components (`AccountInfoSection`, `LanguageSection`). Add `MyDataSection` as a new section following the same pattern. Use loading skeletons during fetch.
- **Frontend fetch pattern**: Native `fetch()` with session token from next-auth. See `use-user-profile.ts` for the exact pattern (AbortController, error handling, loading states).
- **i18n conventions**: Hierarchical dot-separated keys. `settings.myData.title`, `settings.myData.uploads`, etc. Both `en.json` and `uk.json` must be updated in tandem.

### Key Database Models to Query

| Model | Table | What to extract |
|-------|-------|----------------|
| `Upload` | `uploads` | `COUNT(*)` where user_id matches |
| `Transaction` | `transactions` | `COUNT(*)`, `MIN(date)`, `MAX(date)`, `DISTINCT(category)` |
| `Insight` | `insights` | `COUNT(*)` |
| `FinancialProfile` | `financial_profiles` | Latest row (total_income, total_expenses, category_totals) |
| `FinancialHealthScore` | `financial_health_scores` | All rows ordered by `calculated_at` (score + date) |
| `UserConsent` | `user_consents` | All rows (consent_type, granted_at) |

All queries MUST include `WHERE user_id = :user_id` for tenant isolation.

### Key Files to Touch

**New files:**
- `backend/app/api/v1/data_summary.py` — API router + schemas
- `backend/tests/test_data_summary_api.py` — Backend tests
- `frontend/src/features/settings/components/MyDataSection.tsx` — Data summary UI
- `frontend/src/features/settings/hooks/use-data-summary.ts` — Data fetch hook
- `frontend/src/features/settings/__tests__/MyDataSection.test.tsx` — Component tests

**Modified files:**
- `backend/app/api/v1/router.py` — Register new data_summary router
- `frontend/src/features/settings/components/SettingsPage.tsx` — Integrate MyDataSection
- `frontend/messages/en.json` — Add `settings.myData.*` keys
- `frontend/messages/uk.json` — Add matching Ukrainian translations
- `frontend/src/features/settings/__tests__/SettingsPage.test.tsx` — Assert MyDataSection renders

### Previous Story Intelligence (5.3)

- **Frontend-only story** — no patterns to reuse for backend, but confirms:
  - i18n key pattern: `namespace.section.key` with matching `en.json`/`uk.json` updates
  - Component tests co-located in `__tests__/` folders
  - Vitest + @testing-library/react, mock fetch + useRouter
  - Tailwind utility classes with existing design tokens (`text-muted-foreground`, etc.)
  - shadcn/ui components (Tooltip, Button) available for use
- **Consent guard architecture** — `ConsentGuard` wraps all dashboard routes; settings routes are inside the dashboard, so consent is enforced before user can reach My Data section. No guard changes needed.

### Git Intelligence

- Recent commits follow pattern: "Story X.Y: Title"
- Story 5.2 (privacy consent) and 5.3 (disclaimer) were the last two commits — same epic, direct predecessors
- No in-progress work or conflicts expected (clean git status)
- Backend test patterns: pytest + pytest-asyncio, SQLite in-memory test DB, dependency overrides via `app.dependency_overrides`

### Testing Standards

- **Backend**: pytest + pytest-asyncio; test DB fixtures in `conftest.py`; dependency overrides for auth. Reference: `backend/tests/test_health_score_api.py`
- **Frontend**: Vitest + @testing-library/react; `vi.mock` for next-intl and next-auth; `global.fetch` mocked. Reference: `frontend/src/features/settings/__tests__/SettingsPage.test.tsx`
- **Run commands:**
  - `cd backend && python -m pytest tests/test_data_summary_api.py -v` (new endpoint)
  - `cd frontend && pnpm test -- MyDataSection` (new component)
  - `cd frontend && pnpm test -- SettingsPage` (integration)
  - `cd backend && python -m pytest` (full backend regression)
  - `cd frontend && pnpm test` (full frontend regression)

### Project Structure Notes

- Alignment with unified project structure: feature-based folders under `features/`, tests co-located in `__tests__/`, backend routers in `api/v1/`
- No detected conflicts or variances

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 5, Story 5.4]
- [Source: backend/app/api/v1/uploads.py — Router pattern, auth dependency, response schema]
- [Source: backend/app/api/deps.py — get_current_user_id dependency]
- [Source: frontend/src/features/settings/components/SettingsPage.tsx — Settings page structure]
- [Source: frontend/src/features/settings/hooks/use-user-profile.ts — Fetch pattern]
- [Source: _bmad-output/implementation-artifacts/5-3-financial-advice-disclaimer.md — Previous story patterns]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- Fixed SQLAlchemy `func.count()` returning Row tuples instead of scalars — used `sa_select` with `scalar_one()` for aggregate queries
- Fixed SQLModel `select(Model).first()` returning ORM objects correctly vs SQLAlchemy `sa_select` returning Rows

### Completion Notes List

- Implemented `GET /api/v1/users/me/data-summary` endpoint aggregating uploads, transactions, insights, financial profile, health scores, and consent records — all scoped to authenticated user
- Created `MyDataSection` component in settings page displaying all stored data summary with loading/error/empty states
- Added English and Ukrainian i18n keys for all My Data section labels
- Backend: 5 tests (full data, empty state, tenant isolation, unauthenticated, camelCase validation)
- Frontend: 5 tests (loading, full render, empty state, error with retry, retry action) + 1 SettingsPage integration test
- Full regression: 347 backend tests passed, 311 frontend tests passed — zero regressions

### Change Log

- 2026-04-12: Story 5.4 implementation complete — data summary API + My Data settings UI
- 2026-04-12: Code review fixes — H1: financial profile now shows income/expenses instead of static text; M1: added query limits (100) on health scores and consent records; M3: fixed aria-labelledby a11y bug in loading state; M4: corrected test ordering; L1: typed category_totals as dict[str, Any]

### File List

**New files:**
- backend/app/api/v1/data_summary.py
- backend/tests/test_data_summary_api.py
- frontend/src/features/settings/components/MyDataSection.tsx
- frontend/src/features/settings/hooks/use-data-summary.ts
- frontend/src/features/settings/__tests__/MyDataSection.test.tsx

**Modified files:**
- backend/app/api/v1/router.py
- frontend/src/features/settings/components/SettingsPage.tsx
- frontend/messages/en.json
- frontend/messages/uk.json
- frontend/src/features/settings/__tests__/SettingsPage.test.tsx
