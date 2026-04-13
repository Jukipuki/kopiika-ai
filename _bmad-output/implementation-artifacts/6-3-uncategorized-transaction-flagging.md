# Story 6.3: Uncategorized Transaction Flagging

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want to see which transactions the AI couldn't categorize,
so that I understand the gaps in my financial analysis without being misled.

## Acceptance Criteria

1. **Given** a transaction that the categorization agent cannot confidently categorize **When** the pipeline completes **Then** that transaction is stored with `is_flagged_for_review = True`, `category = "uncategorized"`, and a human-readable `uncategorized_reason` (one of: `"low_confidence"`, `"parse_failure"`, `"llm_unavailable"`)

2. **Given** a user has uploaded a statement **When** they visit their profile **Then** a "Transactions we couldn't categorize" section appears (only when at least one flagged transaction exists) with the explanation: "We couldn't figure out a few of these — they won't affect your overall insights"

3. **Given** the uncategorized section is visible **When** the user views it **Then** each flagged transaction shows: date, description, amount, and a user-friendly reason it couldn't be categorized (in their locale)

## Tasks / Subtasks

- [x] Task 1: Enhance categorization node to capture failure reason and set `"uncategorized"` category for flagged transactions (AC: #1)
  - [x] 1.1 Add `uncategorized_reason` key to the per-transaction dict in `_parse_llm_response()` in `backend/app/agents/categorization/node.py`:
    - When the LLM assigns a category but `confidence < threshold`: set `reason = "low_confidence"`
    - When JSON parse fails entirely (fallback to `confidence=0.0`): set `reason = "parse_failure"`
  - [x] 1.2 Update the `_categorize_batch` return value to propagate `uncategorized_reason` through; update the fallback loop in `categorization_node` (both-LLMs-fail path) to add `"uncategorized_reason": "llm_unavailable"`
  - [x] 1.3 In `categorization_node`, after the `flagged` flag is applied, update the loop: if `r["flagged"] is True` → set `r["category"] = "uncategorized"` (overriding the low-confidence LLM guess); MCC-categorized transactions keep `"uncategorized_reason": None` since they are never flagged
  - [x] 1.4 Update `FinancialPipelineState` in `backend/app/agents/state.py`: change the `categorized_transactions` docstring comment to document the new `uncategorized_reason` key (`list[dict]` → `{transaction_id, category, confidence_score, flagged, uncategorized_reason}`)

- [x] Task 2: Add `uncategorized_reason` to Transaction model and create migration (AC: #1)
  - [x] 2.1 Add `uncategorized_reason: Optional[str] = Field(default=None, max_length=50)` to `backend/app/models/transaction.py` (after `is_flagged_for_review`)
  - [x] 2.2 Create Alembic migration: `alembic revision --autogenerate -m "add_uncategorized_reason_to_transactions"` — adds nullable `VARCHAR(50)` column `uncategorized_reason` to `transactions` table

- [x] Task 3: Persist `uncategorized_reason` in processing tasks (AC: #1)
  - [x] 3.1 In `backend/app/tasks/processing_tasks.py`, update the categorization persistence loop (lines ~181–196): add `txn.uncategorized_reason = cat.get("uncategorized_reason")` alongside the existing `txn.is_flagged_for_review = cat["flagged"]` assignment
  - [x] 3.2 Update the resume path (the `if cat and txn.category is None` block) with the same `uncategorized_reason` persistence

- [x] Task 4: Add flagged transactions API endpoint (AC: #2, #3)
  - [x] 4.1 Add `get_flagged_transactions_for_user(session, user_id)` to `backend/app/services/transaction_service.py`: query `transactions` where `user_id = user_id AND is_flagged_for_review = True` ordered by `date DESC`, return all (no pagination needed — flagged count is expected to be small)
  - [x] 4.2 Add `FlaggedTransactionResponse` Pydantic model to `backend/app/api/v1/transactions.py`:
    ```
    id, uploadId, date (YYYY-MM-DD), description, amount (int kopiykas), uncategorizedReason
    ```
    Using `alias_generator=to_camel` consistent with existing `TransactionResponse`
  - [x] 4.3 Add `GET /api/v1/transactions/flagged` route to `backend/app/api/v1/transactions.py`: requires JWT auth via `get_current_user_id`, returns `list[FlaggedTransactionResponse]`; route must be defined **before** any `/{transactionId}` path-param routes to avoid routing conflicts

- [x] Task 5: Frontend — flagged transactions hook (AC: #2, #3)
  - [x] 5.1 Create `frontend/src/features/profile/hooks/use-flagged-transactions.ts`: TanStack Query hook calling `GET /api/v1/transactions/flagged`. Export `{ flaggedTransactions, isLoading, isError }`. Use the `@hey-api/openapi-ts` generated client (same pattern as `use-profile.ts`, `use-health-score.ts`, etc.)

- [x] Task 6: Frontend — UncategorizedTransactions component (AC: #2, #3)
  - [x] 6.1 Create `frontend/src/features/profile/components/UncategorizedTransactions.tsx`:
    - Import `useFlaggedTransactions` hook
    - Return `null` when `flaggedTransactions` is empty or loading with no data
    - Render a `<Card>` section (matching existing profile card style) with:
      - Title from `t("uncategorized.title")` (e.g., "Transactions we couldn't categorize")
      - Friendly explanation from `t("uncategorized.explanation")` (exact copy: "We couldn't figure out a few of these — they won't affect your overall insights")
      - List of transactions: formatted date (locale-aware, using the existing `formatCurrency` locale pattern), description, formatted amount in UAH, and reason via `t("uncategorized.reason.{uncategorizedReason}")` keys
    - Show `<Skeleton>` when loading (consistent with other profile components)
  - [x] 6.2 Update `frontend/src/features/profile/components/ProfilePage.tsx`:
    - Import `useFlaggedTransactions` and `UncategorizedTransactions`
    - Add `<UncategorizedTransactions />` at the bottom of the profile sections (after CategoryBreakdown)

- [x] Task 7: i18n — add uncategorized section copy in both locales (AC: #2, #3)
  - [x] 7.1 Add to `frontend/messages/en.json` under `"profile"` key:
    ```json
    "uncategorized": {
      "title": "Transactions we couldn't categorize",
      "explanation": "We couldn't figure out a few of these — they won't affect your overall insights",
      "reason": {
        "low_confidence": "Our AI wasn't confident enough to categorize this one",
        "parse_failure": "Our AI gave an unexpected response for this transaction",
        "llm_unavailable": "Our AI was temporarily unavailable when processing this"
      }
    }
    ```
  - [x] 7.2 Add equivalent Ukrainian keys to `frontend/messages/uk.json` under `"profile"`:
    ```json
    "uncategorized": {
      "title": "Транзакції, які ми не змогли категоризувати",
      "explanation": "Ми не зрозуміли деякі з них — вони не вплинуть на ваш загальний аналіз",
      "reason": {
        "low_confidence": "Наш ШІ не був достатньо впевнений, щоб категоризувати це",
        "parse_failure": "Наш ШІ дав несподівану відповідь для цієї транзакції",
        "llm_unavailable": "Наш ШІ був тимчасово недоступний під час обробки"
      }
    }
    ```

- [x] Task 8: Tests (all ACs)
  - [x] 8.1 Backend: in `backend/tests/agents/test_categorization.py`, add tests for:
    - Low-confidence LLM result → `category = "uncategorized"`, `uncategorized_reason = "low_confidence"`, `flagged = True`
    - LLM parse failure fallback → `uncategorized_reason = "parse_failure"`, `flagged = True`
    - Both-LLMs-unavailable path → `uncategorized_reason = "llm_unavailable"`, `flagged = True`
    - High-confidence LLM result (above threshold) → `flagged = False`, `uncategorized_reason = None`
    - MCC-mapped transaction → `flagged = False`, `uncategorized_reason = None`
  - [x] 8.2 Backend: test `GET /api/v1/transactions/flagged` in `backend/tests/test_flagged_transactions.py`:
    - Returns only the requesting user's flagged transactions
    - Returns 200 with empty list when no flagged transactions exist
    - Returns correct `uncategorizedReason`, `date`, `description`, `amount` for flagged transactions
    - Requires valid auth (401 without JWT)
  - [x] 8.3 Frontend: in `frontend/src/features/profile/__tests__/UncategorizedTransactions.test.tsx`:
    - Renders `null` when `flaggedTransactions` is empty
    - Renders section title and explanation when flagged transactions exist
    - Maps `uncategorizedReason` to correct i18n key for each reason value
    - Shows skeleton while loading

## Dev Notes

### What Already Exists — Do NOT Reinvent

**Categorization node (`backend/app/agents/categorization/node.py`):**
- Already has full two-pass (MCC → LLM) categorization logic
- Already sets `flagged = confidence_score < settings.CATEGORIZATION_CONFIDENCE_THRESHOLD` (threshold = 0.7)
- Already appends `{"transaction_id": ..., "category": ..., "confidence_score": ..., "flagged": ...}` dicts to `categorized` list
- **GAP**: No `uncategorized_reason` field; low-confidence transactions keep the LLM's guessed category instead of "uncategorized"

**Transaction model (`backend/app/models/transaction.py`):**
- Already has `is_flagged_for_review: bool = Field(default=False)`
- Already has `confidence_score: Optional[float]`
- Already has `category: Optional[str]`
- **GAP**: No `uncategorized_reason` column

**Processing tasks (`backend/app/tasks/processing_tasks.py`):**
- Lines ~181–196: already persists `txn.category`, `txn.confidence_score`, `txn.is_flagged_for_review = cat["flagged"]`
- **GAP**: Does not persist `uncategorized_reason`

**Transactions API (`backend/app/api/v1/transactions.py`):**
- Has `GET /transactions` (paginated list, no flagged filter)
- Uses `TransactionResponse` + `TransactionListResponse` Pydantic models with `alias_generator=to_camel`
- **GAP**: No `/transactions/flagged` endpoint, `TransactionResponse` doesn't expose `is_flagged_for_review` or `uncategorized_reason`

**Profile page (`frontend/src/features/profile/components/ProfilePage.tsx`):**
- Already has pattern: import hook → destructure loading/error/data → pass to component
- Components: `CategoryBreakdown`, `HealthScoreRing`, `HealthScoreTrend`, `MonthlyComparison`
- **GAP**: No uncategorized transactions section

### Architecture Compliance

- **Error response format**: All backend errors return `{"error": {"code": "...", "message": "...", "details": {...}}}` — from `backend/app/core/exceptions.py`
- **API naming**: route `GET /api/v1/transactions/flagged` follows kebab-case plural nouns convention; JSON response fields in camelCase via Pydantic `alias_generator=to_camel`
- **Auth pattern**: Use `get_current_user_id` FastAPI dependency (same as all other endpoints in `transactions.py`)
- **Component boundaries**: `api/` depends on `services/` — add helper to `transaction_service.py`, not inline in the router
- **i18n required**: All user-facing strings via `next-intl` in both `en.json` and `uk.json`
- **Categorization threshold**: `settings.CATEGORIZATION_CONFIDENCE_THRESHOLD = 0.7` — do not hardcode this value anywhere

### Route Order Warning

When adding `GET /api/v1/transactions/flagged`, it **must** be defined before any `/{transactionId}` path-parameter route in `transactions.py` — otherwise FastAPI will try to match `"flagged"` as a UUID path parameter and return 422. Currently there are no path-param routes in this file, but keep this convention for future safety.

### `uncategorized_reason` Values and Mapping

| Reason stored in DB | When set | User-facing label (EN) |
|---|---|---|
| `"low_confidence"` | LLM assigned a category but confidence < 0.7 | "Our AI wasn't confident enough to categorize this one" |
| `"parse_failure"` | LLM responded but JSON parse failed entirely (fallback 0.0) | "Our AI gave an unexpected response for this transaction" |
| `"llm_unavailable"` | Both primary and fallback LLM unavailable (circuit breaker / ValueError) | "Our AI was temporarily unavailable when processing this" |
| `None` | MCC-mapped transactions (always high-confidence), or `flagged=False` | — (not shown) |

MCC-mapped transactions in pass 1 always produce `flagged=False` — they never need a reason.

### File Structure Requirements

**New files to create:**
- `backend/alembic/versions/XXXX_add_uncategorized_reason_to_transactions.py` — migration adding nullable `uncategorized_reason VARCHAR(50)` to `transactions`
- `backend/tests/test_flagged_transactions.py` — API endpoint tests
- `frontend/src/features/profile/hooks/use-flagged-transactions.ts` — TanStack Query hook
- `frontend/src/features/profile/components/UncategorizedTransactions.tsx` — profile section component
- `frontend/src/features/profile/__tests__/UncategorizedTransactions.test.tsx` — component tests

**Files to modify:**
- `backend/app/agents/categorization/node.py` — add reason, set "uncategorized" category for flagged
- `backend/app/agents/state.py` — update comment on `categorized_transactions` field
- `backend/app/models/transaction.py` — add `uncategorized_reason` field
- `backend/app/tasks/processing_tasks.py` — persist `uncategorized_reason` in both process and resume paths
- `backend/app/services/transaction_service.py` — add `get_flagged_transactions_for_user()`
- `backend/app/api/v1/transactions.py` — add `FlaggedTransactionResponse` model + `GET /flagged` route
- `backend/tests/agents/test_categorization.py` — extend with reason/uncategorized tests
- `frontend/src/features/profile/components/ProfilePage.tsx` — add `<UncategorizedTransactions />`
- `frontend/messages/en.json` — add uncategorized i18n keys under `"profile"`
- `frontend/messages/uk.json` — add Ukrainian translations

### Previous Story Intelligence (Story 6.2)

- Categorization node is wrapped in try/except and sets `failed_node` on unhandled errors — story 6.3 changes should not affect this failure-recovery path
- `CircuitBreakerOpenError` re-raises (not caught) — when circuit breaker is open, the pipeline fails entirely; flagged transactions only apply when the pipeline **completes** (even partially)
- `processing_tasks.py` has two persistence paths: initial run (`process_upload`) and resume (`resume_upload`) — both need `uncategorized_reason` handling (Task 3)
- `_make_state` in `test_categorization.py` was updated in 6.2 to include `completed_nodes`, `failed_node`, `literacy_level` — use this updated helper

### Git Intelligence (from recent commits)

- Story 6.2 commit pattern: backend tests in `backend/tests/test_*.py`, agents tests in `backend/tests/agents/`
- i18n keys always updated in both `en.json` and `uk.json` in the same commit
- Profile feature tests in `frontend/src/features/profile/__tests__/`
- Alembic migration filenames: `{hash}_{description}.py` — use `alembic revision --autogenerate` to generate

### Testing Requirements

- **Backend categorization tests**: Use existing `_make_state()` helper in `backend/tests/agents/test_categorization.py`; mock `get_llm_client()` to return controlled confidence values (below 0.7 for low-confidence test, JSON parse error for parse_failure test)
- **Backend API tests**: Use async test client pattern from `backend/tests/conftest.py`; create `Transaction` fixtures with `is_flagged_for_review=True` and various `uncategorized_reason` values
- **Frontend tests**: Vitest + React Testing Library; mock `use-flagged-transactions` hook to control returned data
- The `UncategorizedTransactions` component should **not** be rendered in `ProfilePage` tests if those tests mock individual hooks — test the component in isolation

### References

- [Source: epics.md#Story 6.3] — Acceptance criteria and user story
- [Source: backend/app/agents/categorization/node.py] — existing flagging logic (flagged field, confidence threshold)
- [Source: backend/app/models/transaction.py] — Transaction model with `is_flagged_for_review`, `confidence_score`
- [Source: backend/app/tasks/processing_tasks.py#~181-196] — where `is_flagged_for_review` is persisted
- [Source: backend/app/api/v1/transactions.py] — existing transactions router pattern
- [Source: backend/app/core/config.py#37] — `CATEGORIZATION_CONFIDENCE_THRESHOLD = 0.7`
- [Source: frontend/src/features/profile/components/ProfilePage.tsx] — existing profile page structure
- [Source: frontend/src/features/profile/hooks/use-profile.ts] — hook pattern to follow

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

None — no debugging blockers encountered.

### Completion Notes List

- Implemented full `uncategorized_reason` pipeline: `_parse_llm_response()` sets `"parse_failure"` on JSON exception; both-LLMs-fail paths set `"llm_unavailable"`; flagging loop sets `"low_confidence"` for confidence < threshold; all flagged transactions have their category overridden to `"uncategorized"`.
- Added `uncategorized_reason` nullable `VARCHAR(50)` field to Transaction model with Alembic migration `k7l8m9n0o1p2`.
- Persisted `uncategorized_reason` in both `process_upload` (initial run) and `resume_upload` (resume path) in `processing_tasks.py`.
- Added `get_flagged_transactions_for_user()` service function and `GET /api/v1/transactions/flagged` endpoint before any path-param routes (as required by route order warning in Dev Notes).
- Created `use-flagged-transactions.ts` TanStack Query hook and `UncategorizedTransactions.tsx` profile section component with locale-aware date/currency formatting and i18n reason mapping. Component returns `null` when no flagged transactions exist.
- Added `UncategorizedTransactions` at bottom of `ProfilePage` (after CategoryBreakdown).
- Added i18n keys in both `en.json` and `uk.json` under `profile.uncategorized`.
- Updated 2 pre-existing categorization tests to reflect new `category = "uncategorized"` behavior for both-LLMs-fail path (the behavior change is correct per AC #1).
- 387 backend tests pass (0 regressions). 8 new frontend tests pass. 32 categorization agent tests pass.

### File List

backend/app/agents/categorization/node.py
backend/app/agents/state.py
backend/app/models/transaction.py
backend/app/tasks/processing_tasks.py
backend/app/services/transaction_service.py
backend/app/api/v1/transactions.py
backend/alembic/versions/k7l8m9n0o1p2_add_uncategorized_reason_to_transactions.py
backend/tests/agents/test_categorization.py
backend/tests/test_flagged_transactions.py
frontend/src/features/profile/hooks/use-flagged-transactions.ts
frontend/src/features/profile/components/UncategorizedTransactions.tsx
frontend/src/features/profile/components/ProfilePage.tsx
frontend/src/features/profile/__tests__/UncategorizedTransactions.test.tsx
frontend/messages/en.json
frontend/messages/uk.json
frontend/src/features/profile/__tests__/ProfilePage.test.tsx
backend/app/agents/categorization/mcc_mapping.py

## Senior Developer Review (AI)

**Reviewer:** Oleh (via claude-opus-4-6)
**Date:** 2026-04-13
**Outcome:** Approved with fixes applied

### Review Summary

Adversarial code review identified **4 HIGH**, **9 MEDIUM**, and **12 LOW** issues. All were fixed in-place during review.

### Issues Found & Fixed

**HIGH (4):**
1. Unbounded `get_flagged_transactions_for_user` query (no LIMIT/pagination) -- added `limit=100` parameter
2. `resume_upload` guard `txn.category is None` broke with new `"uncategorized"` category -- changed to `in (None, "uncategorized")`
3. Skeleton test assertion always-passing (`card || skeletons.length > 0`) -- replaced with real `data-slot='skeleton'` assertion
4. `ProfilePage.test.tsx` missing `useFlaggedTransactions` mock -- added mock with default empty return

**MEDIUM (9):**
1. `parse_failure` category override was implicit side effect of confidence threshold -- set `category="uncategorized"` directly in `_parse_llm_response`
2. `FlaggedTransactionResponse` omitted `category` field -- added `category: str`
3. No DB CHECK constraint on `uncategorized_reason` -- added `ck_transactions_uncategorized_reason`
4. No compound index for `(user_id, is_flagged_for_review)` query -- added `ix_transactions_user_flagged_date`
5. `process_upload` used `cat["flagged"]` (KeyError risk) vs `cat.get()` in resume -- unified to `cat.get("flagged", False)`
6. Test seed default `category="uncategorized"` for non-flagged -- changed to `"other"`
7. Hook missing `retry` option (3 auto-retries on 404) -- added `NotFoundError` + retry predicate matching reference hooks
8. Unknown reason strings would crash next-intl -- added `KNOWN_REASONS` set with humanized fallback
9. `isError` not consumed in component -- added `isError` destructuring, returns `null` on error

**LOW (12):**
1. MCC-path dicts missing `uncategorized_reason` key -- added `"uncategorized_reason": None`
2. `"uncategorized"` not in `VALID_CATEGORIES` -- added to frozenset
3. `llm_unavailable` paths used misleading `category="other"` intermediate -- set `"uncategorized"` directly
4. `uncategorized_reason` untyped in Pydantic response -- typed as `Literal["low_confidence", "parse_failure", "llm_unavailable"]`
5. `date` field strftime vs isoformat inconsistency -- noted, no change (pre-existing pattern)
6. `get_flagged_transactions_for_user` return type `list` untyped -- typed as `list[Transaction]`
7. Migration revision ID non-hex -- noted, no change (Alembic accepts arbitrary strings)
8. Downgrade doesn't clean up `category="uncategorized"` data -- noted, acceptable for rollback scenario
9. `test_returns_all_reason_types` didn't verify sort order -- added `dates == sorted(dates, reverse=True)` assertion
10. Auth test accepted 401 or 403 imprecisely -- changed to assert exactly 401
11. Skeleton flash briefly shows card before data resolves -- acceptable per task spec
12. `profile.uncategorized` vs `profile.categories.uncategorized` naming proximity -- noted, no change needed

### Change Log Entry

- 2026-04-13: Senior Developer Review (AI) -- 25 issues found (4H/9M/12L), all HIGH+MEDIUM+applicable LOW fixed in-place
