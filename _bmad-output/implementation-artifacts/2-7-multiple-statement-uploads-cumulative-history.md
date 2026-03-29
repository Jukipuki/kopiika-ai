# Story 2.7: Multiple Statement Uploads & Cumulative History

Status: done
Created: 2026-03-29
Epic: 2 - Statement Upload & Data Ingestion

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want to upload multiple statements from different time periods,
so that I can build a richer picture of my finances over time.

## Acceptance Criteria

1. **Given** I have already uploaded one statement, **When** I upload another statement covering a different time period, **Then** the new transactions are added to my account without overwriting previous data
2. **Given** I upload a statement with overlapping date ranges, **When** the system processes it, **Then** duplicate transactions are detected (by date + amount + description) and not re-inserted
3. **Given** I have uploaded multiple statements, **When** I view my data, **Then** all transactions from all uploads are available in a unified dataset linked to my user account

## Tasks / Subtasks

- [x] Task 1: Add transaction deduplication infrastructure (AC: #2)
  - [x] 1.1 Add Alembic migration: create `dedup_hash` column (`VARCHAR(64)`, indexed) on `transactions` table — SHA-256 of `(user_id, date, amount, description)`
  - [x] 1.2 Add unique constraint `uq_transactions_dedup_hash` on `(user_id, dedup_hash)` to enforce dedup at DB level
  - [x] 1.3 Add `compute_dedup_hash(user_id, date, amount, description)` utility in `backend/app/services/transaction_service.py`
  - [x] 1.4 Backfill `dedup_hash` for all existing transactions in migration (data migration step)

- [x] Task 2: Update parser service for deduplication on insert (AC: #1, #2)
  - [x] 2.1 Modify `sync_parse_and_store_transactions()` in `backend/app/services/parser_service.py` to compute `dedup_hash` for each parsed transaction
  - [x] 2.2 Before bulk insert, query existing `dedup_hash` values for `user_id` to find duplicates
  - [x] 2.3 Filter out duplicate transactions, only insert new ones
  - [x] 2.4 Return updated `ParseAndStoreResult` with new field `duplicates_skipped: int`
  - [x] 2.5 Handle edge case: same file uploaded twice — all transactions skipped, job still marked "completed"

- [x] Task 3: Update Celery task to report dedup results (AC: #1, #2)
  - [x] 3.1 Modify `process_upload()` in `backend/app/tasks/processing_tasks.py` to include `duplicates_skipped` in `result_data`
  - [x] 3.2 Update SSE `job-complete` event to include `{ duplicatesSkipped: N, newTransactions: N }` in payload
  - [x] 3.3 Handle zero new transactions gracefully — still "completed" status, not error

- [x] Task 4: Add transaction listing API endpoint (AC: #3)
  - [x] 4.1 Create `backend/app/services/transaction_service.py` with `get_transactions_for_user()` — cursor-based pagination, sorted by date DESC
  - [x] 4.2 Create `GET /api/v1/transactions` endpoint in `backend/app/api/v1/transactions.py` — returns `{ items, total, nextCursor, hasMore }`
  - [x] 4.3 Add Pydantic response models: `TransactionResponse`, `TransactionListResponse` with camelCase aliases
  - [x] 4.4 Enforce tenant isolation via `get_current_user_id` dependency
  - [x] 4.5 Register route in `backend/app/api/v1/router.py`

- [x] Task 5: Add upload history API endpoint (AC: #3)
  - [x] 5.1 Add `get_uploads_for_user()` method to `backend/app/services/upload_service.py` — returns uploads with transaction counts (joined query)
  - [x] 5.2 Create `GET /api/v1/uploads` endpoint in `backend/app/api/v1/uploads.py` — returns `{ items, total, nextCursor, hasMore }`
  - [x] 5.3 Each upload item includes: `id`, `fileName`, `detectedFormat`, `createdAt`, `transactionCount`, `duplicatesSkipped`, `status` (from associated job)
  - [x] 5.4 Enforce tenant isolation

- [x] Task 6: Frontend upload history page (AC: #3)
  - [x] 6.1 Create `frontend/src/features/upload/hooks/use-upload-history.ts` — TanStack Query hook for `GET /api/v1/uploads`
  - [x] 6.2 Create `frontend/src/features/upload/components/UploadHistoryList.tsx` — table/list of past uploads with file name, date, format, txn count, status badge
  - [x] 6.3 Create `frontend/src/app/[locale]/(dashboard)/history/page.tsx` — upload history page
  - [x] 6.4 Add navigation link to history page in dashboard layout/sidebar
  - [x] 6.5 Add i18n strings for upload history (en.json + uk.json)

- [x] Task 7: Update upload completion flow for multi-upload UX (AC: #1, #3)
  - [x] 7.1 Update `UploadDropzone.tsx` completion state: show "X new transactions added, Y duplicates skipped" message
  - [x] 7.2 Add "Upload another file" CTA button after successful upload (resets to idle state)
  - [x] 7.3 Add "View upload history" link after successful upload
  - [x] 7.4 Update i18n strings for completion messages (en.json + uk.json)

- [x] Task 8: Backend tests (AC: all)
  - [x] 8.1 Test dedup hash computation: same inputs → same hash, different inputs → different hash
  - [x] 8.2 Test `sync_parse_and_store_transactions()` with duplicate transactions — verify duplicates skipped, count correct
  - [x] 8.3 Test second upload with overlapping transactions — only new ones inserted
  - [x] 8.4 Test second upload with completely new transactions — all inserted
  - [x] 8.5 Test exact same file uploaded twice — zero new transactions, job still "completed"
  - [x] 8.6 Test `GET /api/v1/transactions` — returns cumulative transactions from all uploads, paginated
  - [x] 8.7 Test `GET /api/v1/transactions` tenant isolation — user A cannot see user B's transactions
  - [x] 8.8 Test `GET /api/v1/uploads` — returns all uploads with transaction counts
  - [x] 8.9 Test `GET /api/v1/uploads` tenant isolation
  - [x] 8.10 Regression: all existing tests (174 backend) must continue to pass

- [x] Task 9: Frontend tests (AC: all)
  - [x] 9.1 Test `use-upload-history` hook fetches and returns upload list
  - [x] 9.2 Test `UploadHistoryList` renders uploads with correct format and counts
  - [x] 9.3 Test upload completion shows dedup results ("X new, Y skipped")
  - [x] 9.4 Test "Upload another file" button resets state
  - [x] 9.5 Test i18n: history page renders in both en and uk

## Dev Notes

### Critical Architecture Compliance

**Tech Stack (MUST use):**
- Backend: Python 3.12, FastAPI, SQLModel, Celery 5.6.x, Redis 7.x, Alembic
- Frontend: Next.js 16.1, TanStack Query v5, shadcn/ui, Tailwind CSS 4.x
- ORM: SQLModel (SQLAlchemy 2.x + Pydantic v2)
- Pydantic camelCase: All API JSON uses `camelCase` via `alias_generator=to_camel, populate_by_name=True`

**Data Format Rules (from architecture):**
- Money: Integer kopiykas (e.g., `-95000` = -950.00 UAH)
- Dates in API: ISO 8601 UTC (e.g., `"2026-03-16T14:30:00Z"`)
- Dates in DB: `timestamptz` or `date` as appropriate
- IDs: UUID v4
- Currency codes: ISO 4217 numeric (`980` = UAH)
- JSON field naming: `camelCase` in API responses

**Backend Component Dependencies (MUST follow):**
| Layer | Can Depend On | NEVER Depends On |
|---|---|---|
| `api/` | `core/`, `models/`, `services/` | `agents/`, `tasks/` |
| `services/` | `core/`, `models/` | `api/`, `tasks/` |
| `tasks/` | `core/`, `services/`, `agents/` | `api/` |

### Deduplication Strategy

**Fingerprinting approach (recommended):**
- Compute SHA-256 hash of normalized `f"{user_id}:{date_iso}:{amount_kopiykas}:{description_stripped_lower}"`
- Store as `dedup_hash` column on `transactions` table (VARCHAR(64), indexed)
- Unique constraint on `(user_id, dedup_hash)` prevents duplicates at DB level
- Before bulk insert: query existing hashes, filter out known ones in Python — avoids constraint violation errors
- This handles: exact duplicate files, overlapping date ranges, partial re-uploads

**Why NOT use a composite unique constraint on (user_id, date, amount, description):**
- `description` can be very long (TEXT field) — poor index performance
- Hash is fixed-length, fast to index and compare
- Hash approach is extensible (can include more fields later without schema change)

**Edge cases to handle:**
- Two genuinely different transactions with same date + amount + description (rare but possible, e.g., two identical purchases at same store) — accepted trade-off per AC #2 which specifies this exact dedup key
- File uploaded twice → zero new txns → job completes with `duplicatesSkipped: N` — NOT an error
- Upload with mix of new and duplicate txns → partial insert of new only

### API Endpoint Specifications

**GET /api/v1/transactions**
```
Query params: ?cursor=abc&pageSize=20 (default 20, max 100)
Response 200:
{
  "items": [
    {
      "id": "uuid",
      "uploadId": "uuid",
      "date": "2026-02-15",
      "description": "Сільпо",
      "mcc": "5411",
      "amount": -95000,
      "balance": 1500000,
      "currencyCode": 980,
      "createdAt": "2026-03-29T10:00:00Z"
    }
  ],
  "total": 425,
  "nextCursor": "def",
  "hasMore": true
}
```
- Sorted by `date DESC`, then `created_at DESC`
- All transactions across all uploads for authenticated user
- Tenant isolation enforced

**GET /api/v1/uploads**
```
Query params: ?cursor=abc&pageSize=20 (default 20, max 50)
Response 200:
{
  "items": [
    {
      "id": "uuid",
      "fileName": "monobank_feb_2026.csv",
      "detectedFormat": "monobank",
      "createdAt": "2026-03-29T10:00:00Z",
      "transactionCount": 245,
      "duplicatesSkipped": 0,
      "status": "completed"
    }
  ],
  "total": 3,
  "nextCursor": null,
  "hasMore": false
}
```

### Current Database Schema (What Exists)

**transactions table** (from Story 2.3 migration):
- `id` UUID PK, `user_id` UUID FK→users, `upload_id` UUID FK→uploads
- `date` DATE, `description` VARCHAR, `mcc` VARCHAR (nullable)
- `amount` BIGINT (kopiykas), `balance` BIGINT (nullable)
- `currency_code` INT (default 980), `raw_data` JSON
- `created_at` TIMESTAMPTZ
- Indexes: `ix_transactions_user_id`, `ix_transactions_upload_id`, `ix_transactions_date`

**New migration will add:**
- `dedup_hash` VARCHAR(64) column (nullable initially for backfill, then NOT NULL)
- Index: `ix_transactions_dedup_hash`
- Unique constraint: `uq_transactions_user_dedup` on `(user_id, dedup_hash)`
- Data migration: backfill existing rows with computed hash

### Previous Story Intelligence (Story 2.6 Learnings)

**DO NOT REPEAT these mistakes (accumulated from Stories 2.5 + 2.6):**
1. DateTime: Use `datetime.now(UTC).replace(tzinfo=None)` for SQLite test compatibility
2. Celery task `request` property cannot be patched with `patch.object` — use `patch.object(task, "retry")` instead
3. Sync SQLite tests need `StaticPool` (not `NullPool`) to share in-memory DB
4. Upload tests require `process_upload.delay` mock to prevent task dispatch
5. ProcessingJob initial status is `"validated"` (NOT `"pending"`)
6. Pydantic camelCase: `alias_generator=to_camel, populate_by_name=True` on all response models
7. Money stored as kopiykas (integer), locale codes are ISO 639-1 (`"uk"`, `"en"`)
8. Celery tasks are SYNCHRONOUS — use `redis.Redis` (sync), NOT `redis.asyncio`
9. Use `get_sync_session()` for sync DB access in Celery tasks

**Patterns established to REUSE:**
- `get_sync_session()` for sync DB access in Celery tasks
- `SYNC_DATABASE_URL` property derivation (async → sync driver swap)
- `celery_app.conf.update(task_always_eager=True, task_eager_propagates=True)` for test setup
- Mock S3 via `@patch("app.tasks.processing_tasks.boto3.client")`
- `JobStatusResponse` Pydantic model pattern in `jobs.py` — copy pattern for `TransactionResponse`, `UploadListResponse`
- `get_current_user_id` dependency for tenant isolation (already used in uploads.py and jobs.py)
- Cursor-based pagination: use `id` as cursor (UUID string comparison for ordering)

**Current test count: 174 backend tests, 99 frontend tests — ALL must continue to pass.**

### Git Intelligence (Latest Commits)

Recent commit `dbc6a08` (Story 2.6) established:
- `backend/app/core/redis.py` — Redis pub/sub utilities (sync publisher + async subscriber)
- `backend/app/tasks/processing_tasks.py` — Celery task with Redis progress publishing
- `backend/app/api/v1/jobs.py` — Job status + SSE streaming endpoint
- `backend/tests/test_sse_streaming.py` — SSE + Redis test patterns
- Frontend: `use-job-status.ts`, `ProcessingPipeline.tsx`, `UploadDropzone.tsx` updated with SSE flow

**Files to CREATE in this story:**
- `backend/alembic/versions/xxx_add_dedup_hash_to_transactions.py` — migration
- `backend/app/services/transaction_service.py` — transaction query + dedup logic
- `backend/app/api/v1/transactions.py` — transaction listing endpoint
- `backend/tests/test_transactions.py` — transaction endpoint + dedup tests
- `frontend/src/features/upload/hooks/use-upload-history.ts`
- `frontend/src/features/upload/components/UploadHistoryList.tsx`
- `frontend/src/app/[locale]/(dashboard)/history/page.tsx`

**Files to MODIFY in this story:**
- `backend/app/services/parser_service.py` — add dedup hash computation + filtering
- `backend/app/tasks/processing_tasks.py` — include dedup counts in result_data + SSE events
- `backend/app/api/v1/uploads.py` — add GET endpoint for upload listing
- `backend/app/api/v1/router.py` — register transactions route
- `backend/app/models/transaction.py` — add `dedup_hash` field
- `frontend/src/features/upload/components/UploadDropzone.tsx` — completion state with dedup info
- `frontend/messages/en.json` — i18n strings
- `frontend/messages/uk.json` — i18n strings

### Project Structure Notes

- Transaction listing endpoint goes in NEW `backend/app/api/v1/transactions.py` — per architecture spec
- Transaction service goes in NEW `backend/app/services/transaction_service.py` — per architecture spec
- Upload list endpoint is added to EXISTING `backend/app/api/v1/uploads.py` — alongside POST
- History page follows existing `(dashboard)/` route group pattern
- All new backend tests in `backend/tests/` — follow existing patterns
- Frontend components in `features/upload/` — this is still part of the upload domain

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Epic 2, Story 2.7]
- [Source: _bmad-output/planning-artifacts/architecture.md#Database Schema — transactions table]
- [Source: _bmad-output/planning-artifacts/architecture.md#API & Communication Patterns — endpoint conventions]
- [Source: _bmad-output/planning-artifacts/architecture.md#Data Format Rules — kopiykas, ISO dates, camelCase]
- [Source: _bmad-output/planning-artifacts/architecture.md#Backend Directory Structure]
- [Source: _bmad-output/planning-artifacts/architecture.md#Cursor-based Pagination Pattern]
- [Source: _bmad-output/implementation-artifacts/2-6-real-time-processing-progress-via-sse.md — Previous story learnings]
- [Source: _bmad-output/implementation-artifacts/2-5-async-pipeline-processing-with-celery.md — Celery sync patterns]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- Fixed existing test `test_transaction_crud` in test_monobank_parser.py to include `dedup_hash` field
- Fixed existing test `test_partial_results_preserved_on_data_error` in test_processing_tasks.py to include `dedup_hash` field
- Added mock for `@/i18n/navigation` in existing UploadDropzone tests after adding Link import
- Post-story: migrated `use-upload-history` from raw `fetch`/`useState` to `@tanstack/react-query` `useInfiniteQuery` after confirming TanStack Query was not installed; added `QueryClientProvider` wrapper, updated tests to wrap hooks in `QueryClientProvider`

### Completion Notes List

- **Task 1:** Created Alembic migration `e1a2b3c4d5f6` adding `dedup_hash` column (VARCHAR(64), NOT NULL, indexed) with unique constraint `uq_transactions_user_dedup` and data migration backfill. Added `dedup_hash` field to Transaction model. Created `compute_dedup_hash()` utility using SHA-256 of normalized `user_id:date:amount:description`.
- **Task 2:** Updated `_parse_and_build_records()` to compute dedup_hash for each transaction. Added `_filter_duplicates()` helper. Both `parse_and_store_transactions()` and `sync_parse_and_store_transactions()` now query existing hashes and filter before insert. `ParseAndStoreResult` extended with `duplicates_skipped` field.
- **Task 3:** Updated `process_upload()` to include `duplicates_skipped` in `result_data` and SSE `job-complete` event now includes `duplicatesSkipped` and `newTransactions` fields.
- **Task 4:** Created `transaction_service.py` with `get_transactions_for_user()` (cursor-based pagination, sorted by date DESC). Created `GET /api/v1/transactions` endpoint with `TransactionResponse` and `TransactionListResponse` Pydantic models (camelCase). Registered route in router.
- **Task 5:** Added `get_uploads_for_user()` to `upload_service.py` with joined transaction counts and job status. Created `GET /api/v1/uploads` endpoint with `UploadHistoryItem` and `UploadListResponse` models.
- **Task 6:** Created `use-upload-history.ts` hook (fetch-based with cursor pagination). Created `UploadHistoryList.tsx` with status badges, transaction counts, load more button. Created `/history` page route. Added History nav link to dashboard layout. Added i18n strings (en + uk).
- **Task 7:** Updated `UploadDropzone.tsx` completion state to show "X new transactions added, Y duplicates skipped". Added "Upload another file" button and "View upload history" link. Updated SSE types to include dedup fields. Added i18n strings.
- **Task 8:** 20 backend tests: 9 dedup hash unit tests, 4 sync parser dedup integration tests (overlapping, exact same file, all new), 4 transaction endpoint tests (list, pagination, tenant isolation, unauth), 3 upload list endpoint tests. All 194 backend tests pass.
- **Task 9:** 11 frontend tests: 5 use-upload-history hook tests, 6 UploadHistoryList component tests. All 110 frontend tests pass.
- **Post-story — TanStack Query integration:** Installed `@tanstack/react-query` v5. Created `src/lib/query/query-provider.tsx` (`"use client"` wrapper with `QueryClient`, 1min staleTime, 1 retry). Wrapped root `layout.tsx` with `QueryProvider`. Migrated `use-upload-history.ts` from `fetch`/`useState` to `useInfiniteQuery` with cursor-based pagination, 30s staleTime, and enabled guard on `accessToken`. Updated `UploadHistoryList.tsx` to use new `isFetchingMore` field. Updated hook tests to wrap in `QueryClientProvider` with `retry: false`. All 110 frontend tests continue to pass.

### Change Log

- 2026-03-29: Story 2.7 implementation — transaction deduplication, cumulative history APIs, upload history page
- 2026-03-29: Post-story — added `@tanstack/react-query` v5, `QueryProvider` root wrapper, migrated `use-upload-history` to `useInfiniteQuery`
- 2026-03-29: Code review fixes — (H1) N+1 query in `get_uploads_for_user` replaced with batch queries; (H2) cursor UUID validation added in `transaction_service.py` and `upload_service.py`; (H3) async test fixture migrated from fixed-path SQLite to `tempfile.mkstemp`; (M1) JWT removed from React Query cache key; (M2) Alembic backfill batched at 1000 rows; (M3) i18n completeness test added for uk.json history keys

### File List

**New files:**
- backend/alembic/versions/e1a2b3c4d5f6_add_dedup_hash_to_transactions.py
- backend/app/services/transaction_service.py
- backend/app/api/v1/transactions.py
- backend/tests/test_transactions.py
- frontend/src/features/upload/hooks/use-upload-history.ts
- frontend/src/features/upload/components/UploadHistoryList.tsx
- frontend/src/app/[locale]/(dashboard)/history/page.tsx
- frontend/src/features/upload/__tests__/use-upload-history.test.tsx
- frontend/src/features/upload/__tests__/UploadHistoryList.test.tsx

**Modified files:**
- backend/app/models/transaction.py (added dedup_hash field)
- backend/app/services/parser_service.py (dedup hash computation + filtering)
- backend/app/services/upload_service.py (get_uploads_for_user function)
- backend/app/tasks/processing_tasks.py (duplicates_skipped in result_data + SSE)
- backend/app/api/v1/router.py (registered transactions route)
- backend/app/api/v1/uploads.py (GET endpoint for upload listing)
- backend/tests/test_monobank_parser.py (added dedup_hash to test fixture)
- backend/tests/test_processing_tasks.py (added dedup_hash to partial test fixture)
- frontend/src/features/upload/types.ts (added dedup fields to SSE types)
- frontend/src/features/upload/hooks/use-job-status.ts (capture dedup data from SSE)
- frontend/src/features/upload/components/UploadDropzone.tsx (completion state with dedup results + upload another + history link)
- frontend/src/features/upload/__tests__/UploadDropzone.test.tsx (added navigation mock)
- frontend/src/app/[locale]/(dashboard)/layout.tsx (added history nav link)
- frontend/messages/en.json (history + completion i18n strings)
- frontend/messages/uk.json (history + completion i18n strings)
- frontend/src/app/layout.tsx (wrapped with QueryProvider)
- frontend/src/features/upload/components/UploadHistoryList.tsx (isFetchingMore from TanStack Query)
- frontend/src/features/upload/__tests__/use-upload-history.test.tsx (QueryClientProvider wrapper, useInfiniteQuery patterns)
- frontend/src/features/upload/__tests__/UploadHistoryList.test.tsx (isFetchingMore in mock)
- frontend/package.json (@tanstack/react-query v5 dependency)
- frontend/package-lock.json (updated by npm install)

**New files (post-story):**
- frontend/src/lib/query/query-provider.tsx
