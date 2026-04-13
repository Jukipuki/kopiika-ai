# Story 6.6: Operator Job Status & Health Queries

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **operator**,
I want to query job status and pipeline health via database queries,
So that I can monitor the system without a dedicated dashboard in MVP.

## Acceptance Criteria

1. **Given** the `processing_jobs` table **When** an operator queries it **Then** they can see: job status (pending/processing/completed/failed/retrying), timestamps (`created_at`, `started_at`, `updated_at` as completion proxy), agent step/progress, error details (`error_code`, `error_message`, `failed_step`), and `user_id`

2. **Given** an operator wants to check pipeline health **When** they run SQL queries against the database **Then** they can determine: number of jobs by status, average completion time over last 24h, failure rate, and stuck jobs (status='processing' for > 5 minutes without update)

3. **Given** the operational data **When** it is queried **Then** all job and metric tables have appropriate indexes for efficient querying — specifically `created_at` on `processing_jobs` (status and user_id indexes already exist from earlier stories)

## Tasks / Subtasks

- [x] Task 1: Add `created_at` index to `processing_jobs` via Alembic migration (AC: #3)
  - [x] 1.1 Create new migration: `alembic revision --autogenerate -m "add_created_at_index_to_processing_jobs"`. The migration should add: `op.create_index("ix_processing_jobs_created_at", "processing_jobs", ["created_at"])`. Autogenerate may not detect this (it's not on the model) — write the index creation manually in the migration file if needed.
  - [x] 1.2 Verify rollback: the `downgrade()` function should call `op.drop_index("ix_processing_jobs_created_at", table_name="processing_jobs")`.

- [x] Task 2: Create operator SQL runbook document (AC: #1, #2)
  - [x] 2.1 Create `docs/operator-runbook.md` in the project root `docs/` directory (create directory if it doesn't exist). This is NOT a backend Python file — it's a Markdown document for operators.
  - [x] 2.2 Document the `processing_jobs` schema (all fields, their meaning, and which indexes exist) so operators know what's queryable.
  - [x] 2.3 Include ready-to-use SQL queries for all AC #1 and #2 use cases — see Dev Notes section for the exact queries.
  - [x] 2.4 Include the performance metric queries from Story 6.5 (`agent_timings` JSON, `started_at`) for completeness — operators have one reference document.

- [x] Task 3: Tests (AC: #3)
  - [x] 3.1 Add a test to `backend/tests/test_structure.py` that verifies the migration file for `created_at` index exists: `assert len(list((PROJECT_ROOT / "backend" / "alembic" / "versions").glob("*add_created_at_index*"))) == 1`. This is a lightweight structural check — no DB connection needed.
  - [x] 3.2 Add a test to `backend/tests/test_jobs.py` that verifies the `ProcessingJob` model exposes the fields an operator needs: `created_at`, `started_at`, `updated_at`, `status`, `step`, `progress`, `error_code`, `error_message`, `failed_step`, `user_id`. Simple model instantiation test — no DB.

## Dev Notes

### What Already Exists — Do NOT Reinvent

**Existing `processing_jobs` indexes (already created in prior migrations):**
- `idx_processing_jobs_user_id` on `user_id` — from initial table creation (4c94b3ca32be)
- `idx_processing_jobs_status` on `status` — from initial table creation (4c94b3ca32be)
- `idx_processing_jobs_upload_id` on `upload_id` — from initial table creation (4c94b3ca32be)
- `ix_processing_jobs_status_started_at` on `(status, started_at)` — from Story 6.5 (l8m9n0o1p2q3)

**Missing and required by AC #3:**
- `ix_processing_jobs_created_at` on `created_at` — for time-range queries without a status filter (e.g., "show me all jobs from today", "queue latency trend by hour")

**`ProcessingJob` model fields available to operators** (`backend/app/models/processing_job.py`):
```python
id: UUID             # Primary key
user_id: UUID        # Owner — indexed
upload_id: UUID      # Source file — indexed
status: str          # pending | processing | completed | failed | retrying — indexed
step: str | None     # Current pipeline step (ingestion/categorization/profile/health-score/done)
progress: int        # 0–100 progress percentage
error_code: str | None     # Standardized error code (e.g., "llm_unavailable")
error_message: str | None  # Human-readable error detail
failed_step: str | None    # Which step caused the failure
retry_count: int           # Number of retry attempts made
max_retries: int           # Max retries allowed (default 3)
is_retryable: bool         # Whether failure can be retried
last_error_at: datetime | None  # Timestamp of most recent error
started_at: datetime | None     # When Celery worker started processing (None = still queued)
created_at: datetime       # When job row was created (= when upload was submitted)
updated_at: datetime       # When job was last modified (≈ completion time for done/failed jobs)
result_data: dict | None   # JSON: total_rows, parsed_count, flagged_count, persisted_count,
                           #        duplicates_skipped, categorization_count, total_tokens_used,
                           #        agent_timings: {ingestion_ms, categorization_ms, education_ms},
                           #        total_ms
```

**"Completed" timestamp:** There is no dedicated `completed_at` field. Use `updated_at` as a proxy — it is updated on every status change, so for `status='completed'` or `status='failed'` jobs, `updated_at` represents the completion time. Queue latency = `started_at - created_at`. Processing duration = `updated_at - started_at` (for completed jobs). `result_data->'total_ms'` is the precise in-worker timing.

### Operator SQL Query Reference (for the runbook)

All queries below run against the `processing_jobs` table. Connect via `psql` or any PostgreSQL client with read access.

**AC #1 — View job details:**
```sql
-- Full details of a specific job
SELECT id, user_id, status, step, progress,
       error_code, error_message, failed_step,
       retry_count, started_at, created_at, updated_at,
       result_data
FROM processing_jobs
WHERE id = '<job-uuid>';

-- All jobs for a user (most recent first)
SELECT id, status, step, progress, error_code, created_at, updated_at
FROM processing_jobs
WHERE user_id = '<user-uuid>'
ORDER BY created_at DESC
LIMIT 20;
```

**AC #2 — Pipeline health queries:**
```sql
-- Count of jobs by status (snapshot)
SELECT status, COUNT(*) AS count
FROM processing_jobs
GROUP BY status
ORDER BY count DESC;

-- Average completion time last 24h (uses updated_at - started_at)
SELECT
  AVG(EXTRACT(EPOCH FROM (updated_at - started_at)) * 1000)::int AS avg_completion_ms,
  COUNT(*) AS completed_count
FROM processing_jobs
WHERE status = 'completed'
  AND started_at IS NOT NULL
  AND started_at >= NOW() - INTERVAL '24 hours';

-- Failure rate last 24h
SELECT
  COUNT(*) FILTER (WHERE status = 'completed') AS successes,
  COUNT(*) FILTER (WHERE status = 'failed')    AS failures,
  ROUND(
    100.0 * COUNT(*) FILTER (WHERE status = 'failed')
    / NULLIF(COUNT(*), 0), 1
  ) AS failure_rate_pct
FROM processing_jobs
WHERE created_at >= NOW() - INTERVAL '24 hours';

-- Stuck jobs: status='processing' for more than 5 minutes without an update
SELECT id, user_id, upload_id, step, progress,
       started_at, updated_at,
       EXTRACT(EPOCH FROM (NOW() - updated_at)) / 60 AS minutes_stalled
FROM processing_jobs
WHERE status = 'processing'
  AND updated_at < NOW() - INTERVAL '5 minutes'
ORDER BY updated_at ASC;
```

**Performance metrics (from Story 6.5 — included for completeness):**
```sql
-- Average processing time per pipeline stage (last 7 days)
SELECT
  AVG((result_data->'agent_timings'->>'ingestion_ms')::int)      AS avg_ingestion_ms,
  AVG((result_data->'agent_timings'->>'categorization_ms')::int) AS avg_categorization_ms,
  AVG((result_data->'agent_timings'->>'education_ms')::int)      AS avg_education_ms,
  AVG((result_data->>'total_ms')::int)                           AS avg_total_ms
FROM processing_jobs
WHERE status = 'completed'
  AND started_at >= NOW() - INTERVAL '7 days';

-- p95 total processing time (last 24h)
SELECT PERCENTILE_CONT(0.95)
       WITHIN GROUP (ORDER BY (result_data->>'total_ms')::int) AS p95_ms
FROM processing_jobs
WHERE status = 'completed'
  AND started_at >= NOW() - INTERVAL '24 hours';

-- Success/failure rate by day (last 30 days)
SELECT
  DATE_TRUNC('day', created_at) AS day,
  COUNT(*) FILTER (WHERE status = 'completed') AS successes,
  COUNT(*) FILTER (WHERE status = 'failed')    AS failures,
  ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'failed') / NULLIF(COUNT(*), 0), 1) AS failure_rate_pct
FROM processing_jobs
WHERE created_at >= NOW() - INTERVAL '30 days'
GROUP BY 1
ORDER BY 1 DESC;

-- Most common error types (last 30 days)
SELECT error_code, COUNT(*) AS occurrences
FROM processing_jobs
WHERE status = 'failed'
  AND error_code IS NOT NULL
  AND created_at >= NOW() - INTERVAL '30 days'
GROUP BY error_code
ORDER BY occurrences DESC;

-- Queue latency: time between job creation and worker pickup
SELECT
  AVG(EXTRACT(EPOCH FROM (started_at - created_at)) * 1000)::int AS avg_queue_latency_ms
FROM processing_jobs
WHERE started_at IS NOT NULL
  AND created_at >= NOW() - INTERVAL '24 hours';
```

### Architecture Compliance

- **No new API endpoints**: Story 6.6 is MVP operational monitoring via direct database queries. No REST API for operators in this story — that's explicitly deferred per architecture ADR ("Start with structured JSON logging to CloudWatch. Advanced APM deferred post-MVP").
- **No model field changes**: All needed fields already exist on `ProcessingJob`. The only schema change is adding an index.
- **No frontend changes**: Purely backend/infrastructure and documentation.
- **Migration naming**: Follow the pattern `{8_char_random_hex}_{description}.py`. Use `alembic revision` and let it auto-generate the prefix, OR generate an 8-character hex manually (e.g., `m9n0o1p2`). The `--autogenerate` flag will NOT detect the new index unless the model uses `__table_args__` — write the `op.create_index` call manually in the migration.
- **Privacy**: Operator runbook SQL examples must NOT suggest querying `result_data` for transaction content. The queries in this story only query IDs, timestamps, counts, and timing integers — safe per privacy rules established in Story 6.4.

### File Structure Requirements

**New files:**
- `backend/alembic/versions/XXXX_add_created_at_index_to_processing_jobs.py` — Alembic migration adding `ix_processing_jobs_created_at`
- `docs/operator-runbook.md` — SQL runbook for operators (Markdown, not Python)

**Files to modify:**
- `backend/tests/test_structure.py` — add migration file existence check
- `backend/tests/test_jobs.py` — add `ProcessingJob` field availability test

**No changes to:**
- `backend/app/models/processing_job.py` — model is complete
- `backend/app/tasks/processing_tasks.py` — no task changes needed
- Any frontend files

### Previous Story Intelligence (Story 6.5)

- Migration file naming: generated prefix is random alphanumeric (e.g., `l8m9n0o1p2q3`) — let `alembic revision` auto-assign the prefix.
- Test pattern: for model-level tests that don't need a DB, just instantiate `ProcessingJob(...)` with keyword args and assert attribute existence.
- The `docs/` directory may not exist at project root — create it. Use `mkdir -p docs/` or check before creating.
- `result_data` is `sa.JSON` type in the model; operators access it via PostgreSQL JSON operators (`->`, `->>`) — not via Python.
- All 419 tests pass after Story 6.5. This story adds 2 lightweight tests (no DB needed) — should remain green.

### Git Intelligence

- Commit pattern: `"Story X.Y: Title"` for the whole story in one commit
- This story has no Celery task changes, no frontend changes → single backend commit
- Migration file must be committed alongside the tests

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 6.6] — AC definition
- [Source: backend/app/models/processing_job.py] — full field list for ProcessingJob
- [Source: backend/alembic/versions/4c94b3ca32be_create_uploads_processing_jobs.py] — existing indexes: `idx_processing_jobs_user_id`, `idx_processing_jobs_status`, `idx_processing_jobs_upload_id`
- [Source: backend/alembic/versions/l8m9n0o1p2q3_add_started_at_to_processing_jobs.py] — `ix_processing_jobs_status_started_at` composite index added in Story 6.5
- [Source: Story 6.5 Dev Notes#Operator Query Examples] — performance metric queries (included in runbook)
- [Source: architecture.md#APM/monitoring] — "Advanced monitoring/APM tooling deferred but observability is a day-one NFR. Start with structured JSON logging to CloudWatch."

## Dev Agent Record

### Agent Model Used

claude-opus-4-6

### Debug Log References

### Completion Notes List

- All 3 tasks completed in a single session with no HALT conditions
- Task 1: Created Alembic migration `m9n0o1p2q3r4_add_created_at_index_to_processing_jobs.py` adding `ix_processing_jobs_created_at` index on `created_at` column. Downgrade properly drops the index.
- Task 2: Created `docs/operator-runbook.md` with full schema documentation, all AC #1 job detail queries, all AC #2 pipeline health queries (status counts, avg completion time, failure rate, stuck jobs), and Story 6.5 performance metric queries for a single operator reference.
- Task 3: Added `test_created_at_index_migration_exists` to `test_structure.py` (structural check) and `test_processing_job_exposes_operator_fields` to `test_jobs.py` (model field availability). Both lightweight, no DB needed.
- Full regression suite: 422 tests pass, 0 failures, 2 warnings (pre-existing deprecation warnings)

### File List

**New files:**
- `backend/alembic/versions/m9n0o1p2q3r4_add_created_at_index_to_processing_jobs.py`
- `docs/operator-runbook.md`

**Modified files:**
- `backend/tests/test_structure.py`
- `backend/tests/test_jobs.py`

### Change Log

- Story 6.6: Added `created_at` index to `processing_jobs` for efficient time-range queries, created operator SQL runbook with schema docs and ready-to-use queries, added 2 lightweight tests (Date: 2026-04-13)
- Code review fixes: Added `result_data` JSON structure documentation to runbook, added `result_data` to operator field test, fixed avg completion time query to use `created_at` time anchor consistent with failure rate query (Date: 2026-04-13)
