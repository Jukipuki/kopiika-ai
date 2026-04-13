# Story 6.5: Pipeline Performance & Upload Metrics Tracking

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **operator**,
I want to track pipeline processing times and upload success/failure rates,
so that I can monitor system health and identify performance issues.

## Acceptance Criteria

1. **Given** a pipeline job completes (success or failure) **When** the metrics are recorded **Then** processing time per agent (ingestion, categorization, education) is logged with the `job_id`

2. **Given** an upload is received **When** it is processed (success or failure) **Then** the result is logged with: `upload_id`, `file_type`, `file_size`, `bank_format_detected`, `success/failure status`, `error_type` (if failed)

3. **Given** the pipeline metrics data **When** an operator queries the database **Then** they can calculate: average processing time per agent, p95 processing time, success/failure rate by time period, and most common error types

## Tasks / Subtasks

- [x] Task 1: Add `started_at` field to `ProcessingJob` model (AC: #3)
  - [x] 1.1 In `backend/app/models/processing_job.py`, add `started_at: datetime | None = Field(default=None, nullable=True)` after `created_at`. Import `datetime` from `datetime` module (already imported for other fields — verify before adding).
  - [x] 1.2 Create a new Alembic migration: `alembic revision --autogenerate -m "add_started_at_to_processing_jobs"`. Verify the generated migration adds `started_at TIMESTAMP WITH TIME ZONE NULL` to `processing_jobs`. Also add an index on `(status, started_at)` for efficient operator time-range queries: `op.create_index("ix_processing_jobs_status_started_at", "processing_jobs", ["status", "started_at"])`.

- [x] Task 2: Instrument `process_upload` task with per-agent timing (AC: #1, #3)
  - [x] 2.1 At the top of `process_upload()` in `backend/app/tasks/processing_tasks.py`, after the job status is set to `"processing"`, add: `job.started_at = datetime.utcnow()` and `task_start = time.monotonic()`. Import `time` at the top of the file if not already imported.
  - [x] 2.2 Wrap each pipeline stage with timing bookends using `time.monotonic()`:
    - Before ingestion step (parse + store): `ingestion_start = time.monotonic()`; after it: `ingestion_ms = round((time.monotonic() - ingestion_start) * 1000)`
    - Before categorization step (LangGraph pipeline invocation): `categorization_start = time.monotonic()`; after it: `categorization_ms = round((time.monotonic() - categorization_start) * 1000)`
    - Before education/profile step (build_or_update_profile + health score): `education_start = time.monotonic()`; after it: `education_ms = round((time.monotonic() - education_start) * 1000)`
    - Accumulate into a dict: `agent_timings = {"ingestion_ms": ingestion_ms, "categorization_ms": categorization_ms, "education_ms": education_ms}`
  - [x] 2.3 Merge `agent_timings` into `result_data` before writing it to `job.result_data`. Example: `result_data = {**result_data, "agent_timings": agent_timings, "total_ms": round((time.monotonic() - task_start) * 1000)}`. This makes per-agent timing queryable via PostgreSQL's `result_data->>'agent_timings'` JSON path (see operator query examples in Dev Notes).
  - [x] 2.4 At job **completion**, emit a structured metrics log using the existing logging infrastructure (set up in 6.4): `logger.info("pipeline_completed", extra={"job_id": str(job_id), "upload_id": str(upload.id), "user_id": str(upload.user_id), "file_size": upload.file_size, "file_type": upload.mime_type, "bank_format_detected": upload.detected_format, "status": "completed", "ingestion_ms": ingestion_ms, "categorization_ms": categorization_ms, "education_ms": education_ms, "total_ms": agent_timings_total})`. This satisfies AC #1 and #2.
  - [x] 2.5 At job **failure** (inside `_mark_failed()` or immediately before calling it), emit: `logger.info("pipeline_metrics", extra={"job_id": str(job_id), "upload_id": str(upload_id), "user_id": str(user_id), "file_size": file_size, "file_type": file_type, "bank_format_detected": bank_format, "status": "failed", "error_type": error_code, "partial_timings": partial_timings_dict_or_none})`. Note: `_mark_failed()` doesn't have access to timing state — add optional `timings: dict | None = None` parameter to `_mark_failed()` so callers can pass partial timing data.

- [x] Task 3: Instrument `resume_upload` task with timing (AC: #1)
  - [x] 3.1 Apply the same `time.monotonic()` pattern to `resume_upload()`: record `task_start` at entry, record `started_at = datetime.utcnow()` on the job, capture categorization/profile timing, and emit `pipeline_completed` log with `status="resumed_completed"` at the end. Store `agent_timings` in `result_data` the same way.

- [x] Task 4: Tests (AC: #1, #2, #3)
  - [x] 4.1 In `backend/tests/tasks/test_processing_tasks.py` (or `backend/tests/tasks/test_pipeline_metrics.py` if the file doesn't exist), add a test that mocks a successful pipeline run and asserts:
    - `job.started_at` is set (not None) after `process_upload()` runs
    - `job.result_data["agent_timings"]` contains `ingestion_ms`, `categorization_ms`, `education_ms` keys — all integers ≥ 0
    - `job.result_data["total_ms"]` is an integer ≥ 0
    - A `pipeline_completed` log entry is emitted (use `caplog`) containing `job_id`, `upload_id`, `file_size`, `bank_format_detected`, `status="completed"` fields
  - [x] 4.2 Add a test for the failure path: mock an exception mid-pipeline, assert:
    - A `pipeline_metrics` log entry is emitted with `status="failed"` and `error_type` matching the raised error code
  - [x] 4.3 In `backend/tests/models/test_processing_job.py` (create if needed): verify that `ProcessingJob` can be constructed with `started_at=None` (default) and with a `datetime` value — just a simple model-level unit test, no DB needed.

## Dev Notes

### What Already Exists — Do NOT Reinvent

**`ProcessingJob` model (`backend/app/models/processing_job.py`):**
- Already has `created_at`, `updated_at` timestamps
- Already has `status` (pending/processing/completed/failed/retrying), `error_code`, `error_message`, `failed_step`, `is_retryable`, `retry_count`
- Already has `result_data` (JSON) which stores end-of-pipeline aggregates: `total_rows`, `parsed_count`, `flagged_count`, `persisted_count`, `duplicates_skipped`, `categorization_count`, `total_tokens_used`
- **Missing**: `started_at` (when Celery worker actually picked up the task — `created_at` is when the job row was created by the API handler, not when processing began; the delta is queue latency)

**`Upload` model (`backend/app/models/upload.py`):**
- Already has `file_size`, `mime_type`, `detected_format`, `detected_encoding`, `detected_delimiter`
- The metrics log in AC #2 (`file_type`, `file_size`, `bank_format_detected`) maps directly to `mime_type`, `file_size`, `detected_format`
- No new fields needed on `Upload`

**`processing_tasks.py` (`backend/app/tasks/processing_tasks.py`):**
- Already imports and uses `logger` with structured `extra={}` after Story 6.4
- Already tracks step progress via `_update_job()` helper at each pipeline stage — do NOT change this progress tracking, just add `time.monotonic()` bookends around the same code blocks
- Pipeline stages in `process_upload()`:
  1. Ingestion (step="ingestion", progress 10→30%): `sync_parse_and_store_transactions()`
  2. Categorization (step="categorization", progress 40→60%): `build_pipeline()` invocation
  3. Profile/education (step="profile", step="health-score", progress 90→92%): `build_or_update_profile()` + `calculate_health_score()`
- `_mark_failed()` helper: accepts `job_id, error_code, error_message, is_retryable` — extend with optional `timings: dict | None = None` parameter
- `resume_upload()` mirrors `process_upload()` structure but starts from LangGraph checkpoint

**Structured logging infrastructure (from Story 6.4):**
- `backend/app/core/logging.py` has `JsonFormatter` with generic `extra={}` field capture
- All fields passed via `extra={}` appear in the JSON log output automatically
- Use `logger.info("pipeline_completed", extra={...})` — no changes to logging infrastructure needed
- Logs go to stdout → CloudWatch in production; operators can query CloudWatch Insights or grep local files

### Architecture Compliance

- **Timing approach**: Use `time.monotonic()` (not `datetime.now()`) for duration measurement — monotonic clock is immune to system clock adjustments and is appropriate for elapsed time measurement
- **No new tables**: Store `agent_timings` in `result_data` JSON column rather than a dedicated metrics table — avoids schema churn at MVP stage; operators can query via PostgreSQL JSON functions
- **Privacy**: Timing logs must NOT include transaction data (descriptions, amounts, MCC codes). Only log: IDs, counts, file metadata, timing integers — same privacy rules as Story 6.4
- **Error type values**: Log the `error_code` string from `ProcessingJob.error_code` (e.g., `"llm_unavailable"`, `"unsupported_format"`, `"pipeline_timeout"`) — these are already standardized in the codebase

### Operator Query Examples (Document in Story for Reference)

Once `started_at` and `agent_timings` are in place, operators can run:

```sql
-- Average processing time per stage (last 7 days)
SELECT
  AVG((result_data->'agent_timings'->>'ingestion_ms')::int)    AS avg_ingestion_ms,
  AVG((result_data->'agent_timings'->>'categorization_ms')::int) AS avg_categorization_ms,
  AVG((result_data->'agent_timings'->>'education_ms')::int)     AS avg_education_ms,
  AVG((result_data->>'total_ms')::int)                         AS avg_total_ms
FROM processing_jobs
WHERE status = 'completed'
  AND started_at >= NOW() - INTERVAL '7 days';

-- p95 total processing time (last 24h)
SELECT PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY (result_data->>'total_ms')::int) AS p95_ms
FROM processing_jobs
WHERE status = 'completed'
  AND started_at >= NOW() - INTERVAL '24 hours';

-- Success/failure rate by day
SELECT
  DATE_TRUNC('day', started_at) AS day,
  COUNT(*) FILTER (WHERE status = 'completed') AS successes,
  COUNT(*) FILTER (WHERE status = 'failed')    AS failures,
  ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'failed') / NULLIF(COUNT(*), 0), 1) AS failure_rate_pct
FROM processing_jobs
WHERE started_at >= NOW() - INTERVAL '30 days'
GROUP BY 1
ORDER BY 1 DESC;

-- Most common error types
SELECT error_code, COUNT(*) AS occurrences
FROM processing_jobs
WHERE status = 'failed'
  AND error_code IS NOT NULL
  AND started_at >= NOW() - INTERVAL '30 days'
GROUP BY error_code
ORDER BY occurrences DESC;

-- Queue latency (time between job creation and processing start)
SELECT
  AVG(EXTRACT(EPOCH FROM (started_at - created_at)) * 1000)::int AS avg_queue_latency_ms
FROM processing_jobs
WHERE started_at IS NOT NULL
  AND created_at >= NOW() - INTERVAL '24 hours';
```

These queries require:
- `ix_processing_jobs_status_started_at` index (created in Task 1.2) for efficient `WHERE status = 'completed' AND started_at >= ...` queries
- `result_data` JSON column to contain `agent_timings` object and `total_ms` integer (set in Task 2.3)

### File Structure Requirements

**New files to create:**
- `backend/alembic/versions/XXXX_add_started_at_to_processing_jobs.py` — Alembic migration

**Files to modify:**
- `backend/app/models/processing_job.py` — add `started_at` field
- `backend/app/tasks/processing_tasks.py` — add `time.monotonic()` bookends, `started_at` assignment, metrics log events, extend `_mark_failed()` with optional `timings` param
- `backend/tests/tasks/test_processing_tasks.py` (or new `test_pipeline_metrics.py`) — metrics tests

**No frontend changes required.** This is purely backend operational observability with no user-facing changes.

### Previous Story Intelligence (Story 6.4)

- The `JsonFormatter` now captures ALL extra fields — no need to declare fields upfront; just pass them in `extra={}`
- Logging pattern established in 6.4: `logger.info("event_name", extra={"field": value, ...})` — follow this exactly
- `_mark_failed()` pattern: always calls `_update_job()` + publishes Redis `job-failed` event. Add `timings` parameter **before** the final `session.commit()` in `_mark_failed()` so timing data is logged before the failure is committed
- The `log_ctx` dict pattern from 6.4 (used in agent nodes) is NOT used in `processing_tasks.py` — tasks use per-call `extra={}` dicts directly, which is fine
- Privacy rule from 6.4: never log values from `state["transactions"]` list — for this story, we're only logging aggregate counts and timing integers, which is safe

### Git Intelligence

- Commit pattern: `"Story X.Y: Title"` for the whole story in one commit
- Tests at `backend/tests/tasks/` for Celery task tests — check if `test_processing_tasks.py` already exists; if so, add to it rather than creating a new file
- Alembic migration filenames follow the pattern: `{random_alphanum}_{description}.py` — the `--autogenerate` flag sets this automatically
- No frontend changes → single backend commit

### References

- [Source: architecture.md#APM/monitoring] — "Start with structured JSON logging to CloudWatch (free with AWS). Add Sentry for error tracking in MVP."
- [Source: backend/app/models/processing_job.py] — `result_data` JSON field, `status`, `error_code`, `created_at`/`updated_at` — `started_at` is the missing field
- [Source: backend/app/models/upload.py] — `file_size`, `mime_type`, `detected_format` for upload metrics log
- [Source: backend/app/tasks/processing_tasks.py] — pipeline stage structure (ingestion/categorization/profile steps) with progress bookends
- [Source: backend/app/core/logging.py] — `JsonFormatter` with generic extra field capture (6.4 enhancement)
- [Source: Story 6.4 Dev Agent Record] — established logging patterns, privacy rules, `_mark_failed()` structure

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- caplog doesn't capture structured logs when `propagate=False` (JsonFormatter from 6.4); switched tests to mock `logger` directly

### Completion Notes List

- Task 1: Added `started_at` Optional[datetime] field to ProcessingJob model, created Alembic migration with composite index `ix_processing_jobs_status_started_at`
- Task 2: Instrumented `process_upload()` with `time.monotonic()` timing for ingestion, categorization, and education stages; merged `agent_timings` + `total_ms` into `result_data`; emit `pipeline_completed` structured log on success and `pipeline_metrics` on failure via extended `_mark_failed(timings=...)` parameter
- Task 3: Applied same timing pattern to `resume_upload()` — records `started_at`, captures categorization/education timing, stores in `result_data`, emits `pipeline_completed` log with `status="resumed_completed"`
- Task 4: Added 4 tests to `test_processing_tasks.py` — success path (started_at, agent_timings, total_ms, pipeline_completed log), failure path (pipeline_metrics log with error_type), and 2 model-level tests for started_at default/datetime. All 419 tests pass.
- Added `_collect_partial_timings()` helper to gather available timing data at point of failure for inclusion in failure logs

### Change Log

- 2026-04-13: Story 6.5 implementation complete — pipeline performance & upload metrics tracking
- 2026-04-13: Code review fixes — added session.rollback() to resume_upload error handlers (H2), fixed migration timezone mismatch (M1), wrapped _mark_failed metrics log in try/except (M2), added resume_upload timing test (H1), expanded test assertions for AC #2 fields (M3, L3)

### File List

- `backend/app/models/processing_job.py` — added `started_at` field
- `backend/alembic/versions/l8m9n0o1p2q3_add_started_at_to_processing_jobs.py` — new migration
- `backend/app/tasks/processing_tasks.py` — timing instrumentation, metrics logging, `_mark_failed()` timings param, `_collect_partial_timings()` helper
- `backend/tests/test_processing_tasks.py` — added TestPipelineMetrics and TestProcessingJobModel test classes
