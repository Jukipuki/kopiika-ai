# Story 2.5: Async Pipeline Processing with Celery

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want my uploaded statements processed asynchronously,
so that I don't have to wait on a loading screen.

## Acceptance Criteria

1. **Given** a file has been uploaded and validated
   **When** the processing job is queued
   **Then** a Celery task is created and dispatched to a worker via Redis broker

2. **Given** the Celery worker picks up a task
   **When** it runs the Ingestion Agent (LangGraph node)
   **Then** raw parsed transactions are extracted, structured, and persisted to PostgreSQL

3. **Given** a processing job for 200-500 transactions
   **When** the full ingestion pipeline runs
   **Then** it completes within 60 seconds

4. **Given** a Celery task fails due to a transient error
   **When** the retry mechanism activates
   **Then** it retries up to 3 times with exponential backoff before marking as failed, preserving any partial results via checkpointing

## Tasks / Subtasks

- [x] Task 1: Create Celery Processing Task (AC: #1, #2)
  - [x] 1.1: Create `backend/app/tasks/processing_tasks.py` with `process_upload` task decorated with `@celery_app.task(bind=True, max_retries=3, acks_late=True)`
  - [x] 1.2: Implement synchronous database session factory in `backend/app/core/database.py` — `get_sync_session()` using `create_engine` (not async) with `NullPool` for Celery worker context
  - [x] 1.3: In `process_upload` task: load ProcessingJob from DB, update status to `"processing"`, set step to `"ingestion"`
  - [x] 1.4: Download file bytes from S3 using boto3 (sync — Celery is not async)
  - [x] 1.5: Load Upload record to retrieve `detected_format` and `detected_encoding`, reconstruct `FormatDetectionResult` for parser selection
  - [x] 1.6: Call `parse_and_store_transactions()` — **create a synchronous wrapper** since the existing function is async and Celery workers are sync
  - [x] 1.7: On success: update ProcessingJob `status="completed"`, `progress=100`, `step="done"`, commit session
  - [x] 1.8: On failure: update ProcessingJob `status="failed"`, set `error_code` and `error_message`, commit session

- [x] Task 2: Implement Retry Logic with Exponential Backoff (AC: #4)
  - [x] 2.1: Catch transient errors (S3 connection errors, database connection errors) and call `self.retry(exc=exc, countdown=2**self.request.retries)` — exponential backoff: 1s, 2s, 4s
  - [x] 2.2: On `MaxRetriesExceededError`: mark job as `"failed"` with `error_code="MAX_RETRIES_EXCEEDED"`
  - [x] 2.3: Catch permanent errors (UnsupportedFormatError, ValueError) — do NOT retry, immediately mark as `"failed"`
  - [x] 2.4: Ensure partial results are preserved: if parsing partially succeeded before failure, commit any persisted transactions before marking job as failed

- [x] Task 3: Dispatch Celery Task from Upload Endpoint (AC: #1)
  - [x] 3.1: In `backend/app/api/v1/uploads.py`, after `create_upload_record()` returns, dispatch Celery task: `process_upload.delay(str(job.id))`
  - [x] 3.2: Import `process_upload` from `app.tasks.processing_tasks`
  - [x] 3.3: Ensure task dispatch happens AFTER the DB commit in `create_upload_record()` — the worker must be able to find the ProcessingJob in the DB

- [x] Task 4: Create Job Status Endpoint (AC: #1, #2, #3)
  - [x] 4.1: Create `backend/app/api/v1/jobs.py` with `GET /api/v1/jobs/{job_id}` endpoint
  - [x] 4.2: Return `JobStatusResponse` with: `job_id`, `status`, `step`, `progress`, `error` (if failed), `result` (if completed: `total_rows`, `parsed_count`, `flagged_count`)
  - [x] 4.3: Enforce tenant isolation: only return job if `job.user_id == current_user_id`
  - [x] 4.4: Register jobs router in `backend/app/api/v1/router.py`

- [x] Task 5: Update Celery App Configuration (AC: #3, #4)
  - [x] 5.1: Add task autodiscovery to `celery_app.py`: `celery_app.autodiscover_tasks(["app.tasks"])`
  - [x] 5.2: Add task time limit: `task_time_limit=120` (hard kill after 120s), `task_soft_time_limit=90` (SoftTimeLimitExceeded after 90s)
  - [x] 5.3: Add `CELERY_TASK_TRACK_STARTED=True` so task state is visible
  - [x] 5.4: Add worker concurrency hint in config comment (default prefork pool, concurrency=2 for dev)

- [x] Task 6: Add Sync Database URL to Config (AC: #2)
  - [x] 6.1: Add `SYNC_DATABASE_URL` to `Settings` in `config.py` — derived from `DATABASE_URL` by replacing `postgresql+asyncpg://` with `postgresql+psycopg2://` (or `sqlite:///` for test)
  - [x] 6.2: Add `psycopg2-binary` to `pyproject.toml` dependencies (sync PostgreSQL driver for Celery worker) — already present

- [x] Task 7: Store Parse Results on ProcessingJob (AC: #2, #3)
  - [x] 7.1: Add `result_data` field to ProcessingJob model: `result_data: Optional[dict] = Field(default=None, sa_type=sa.JSON)` — stores `{"total_rows": N, "parsed_count": N, "flagged_count": N, "persisted_count": N}`
  - [x] 7.2: Create Alembic migration to add `result_data` column to `processing_jobs` table
  - [x] 7.3: Update `process_upload` task to store parse results in `result_data` after successful processing

- [x] Task 8: Backend Tests (AC: #1, #2, #3, #4)
  - [x] 8.1: Test `process_upload` task — happy path: mock S3 download, verify transactions persisted, job status = "completed"
  - [x] 8.2: Test `process_upload` task — transient error: mock S3 connection error, verify retry called with exponential backoff
  - [x] 8.3: Test `process_upload` task — permanent error: mock UnsupportedFormatError, verify job status = "failed", no retry
  - [x] 8.4: Test `process_upload` task — max retries exceeded: verify job status = "failed" with error_code
  - [x] 8.5: Test upload endpoint — verify Celery task dispatched after DB commit (mock `process_upload.delay`)
  - [x] 8.6: Test job status endpoint — happy path: returns correct status, step, progress
  - [x] 8.7: Test job status endpoint — tenant isolation: user A cannot see user B's jobs (returns 404)
  - [x] 8.8: Test job status endpoint — job not found: returns 404
  - [x] 8.9: Test `process_upload` task — performance: 500 transactions processed within 60 seconds (mark as slow test if needed)
  - [x] 8.10: Test partial results preserved on failure: if some transactions parsed before error, they remain in DB
  - [x] 8.11: Regression: all 149 existing backend tests must continue to pass (160 total: 149 existing + 11 new)

## Dev Notes

### Architecture Compliance

**Tech Stack (MUST use — do NOT introduce alternatives):**
- **Backend**: Python 3.12, FastAPI, SQLModel, Celery 5.6.x, Redis 7.x
- **Database**: PostgreSQL (RDS) — SQLite for tests with aiosqlite (async) / sqlite3 (sync Celery tests)
- **Task Queue**: Celery with Redis broker (already configured in `app/tasks/celery_app.py`)
- **Testing**: pytest + httpx (backend API), pytest with mock Celery for task tests
- **New dependency**: `psycopg2-binary` (sync PostgreSQL driver for Celery worker process)

**Critical Architecture Pattern — Celery is SYNCHRONOUS:**

Celery workers run in separate processes and are NOT async. This has critical implications:

1. **Database sessions in Celery tasks MUST be synchronous** — use `sqlmodel.Session` (not `AsyncSession`), with a sync engine created via `create_engine` (not `create_async_engine`)
2. **Use `NullPool`** for the sync engine in Celery workers to avoid connection pooling issues across forked processes
3. **S3 calls are already sync** (boto3) — no issue
4. **`parse_and_store_transactions()` is async** — create a sync wrapper or refactor to accept either session type. Recommended approach: create `sync_parse_and_store_transactions()` that uses `sqlmodel.Session` instead of `AsyncSession`
5. **Do NOT use `asyncio.run()` or `async_to_sync` in Celery tasks** — it creates event loop conflicts. Write truly synchronous code for tasks.

**Sync Database Session for Celery:**
```python
# In backend/app/core/database.py — ADD (do not modify existing async code):
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool
from sqlmodel import Session

sync_engine = create_engine(settings.SYNC_DATABASE_URL, poolclass=NullPool)

def get_sync_session() -> Session:
    return Session(sync_engine)
```

**Sync Database URL:**
```python
# In backend/app/core/config.py:
@property
def SYNC_DATABASE_URL(self) -> str:
    """Derive sync URL from async DATABASE_URL for Celery workers."""
    return self.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg2://").replace("sqlite+aiosqlite://", "sqlite://")
```

### Processing Flow (Current vs New)

**Current flow (synchronous, Story 2.1-2.4):**
```
POST /api/v1/uploads → validate → detect format → upload to S3 → create DB records → HTTP 202
[FILE SITS IN S3 UNPROCESSED]
```

**New flow (Story 2.5 adds async processing):**
```
POST /api/v1/uploads → validate → detect format → upload to S3 → create DB records
    → dispatch process_upload.delay(job_id) → HTTP 202

[CELERY WORKER PICKS UP TASK]
    → load ProcessingJob (status → "processing")
    → download file from S3
    → load Upload record (format, encoding)
    → reconstruct FormatDetectionResult
    → call sync_parse_and_store_transactions()
    → update ProcessingJob (status → "completed", result_data)

[CLIENT POLLS]
    GET /api/v1/jobs/{id} → returns current status + progress
```

### ProcessingJob Status Flow (Updated)

```
"validated"  →  "processing"  →  "completed"
                    ↓
                "failed" (after retries exhausted)
```

**Important:** Story 2.1 sets initial status to `"validated"` (not `"pending"`). The Celery task transitions from `"validated"` → `"processing"` → `"completed"` or `"failed"`.

### Celery Task Design

```python
# backend/app/tasks/processing_tasks.py

from celery.exceptions import MaxRetriesExceededError, SoftTimeLimitExceeded
from app.tasks.celery_app import celery_app

@celery_app.task(bind=True, max_retries=3, acks_late=True, track_started=True)
def process_upload(self, job_id: str) -> dict:
    """Process an uploaded bank statement file.

    Args:
        job_id: UUID string of the ProcessingJob to process.

    Returns:
        dict with parse results (total_rows, parsed_count, flagged_count).
    """
    # 1. Open sync DB session
    # 2. Load ProcessingJob, update status to "processing"
    # 3. Load Upload record for s3_key, format, encoding
    # 4. Download file from S3
    # 5. Reconstruct FormatDetectionResult
    # 6. Call sync_parse_and_store_transactions()
    # 7. Update ProcessingJob to "completed" with result_data
    # 8. Return result dict
```

**Retry decision tree:**
| Error Type | Retry? | Reason |
|---|---|---|
| S3 `ClientError` (connection) | Yes | Transient network issue |
| Database `OperationalError` | Yes | Transient connection issue |
| `SoftTimeLimitExceeded` | No | Task took too long — mark failed |
| `UnsupportedFormatError` | No | Permanent — bad file format |
| `ValueError` / `KeyError` | No | Permanent — data issue |
| Any other `Exception` | No | Unknown — mark failed, log for investigation |

### Job Status Endpoint

```python
# backend/app/api/v1/jobs.py

# GET /api/v1/jobs/{job_id}
# Response: JobStatusResponse
class JobStatusResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    job_id: str
    status: str                          # "validated" | "processing" | "completed" | "failed"
    step: Optional[str] = None           # "ingestion" | "done" | None
    progress: int = 0                    # 0-100
    error: Optional[JobError] = None     # Present only if status == "failed"
    result: Optional[JobResult] = None   # Present only if status == "completed"
    created_at: str
    updated_at: str
```

### Critical Previous Story Learnings (DO NOT REPEAT THESE BUGS)

1. **DateTime handling**: Use `datetime.now(UTC).replace(tzinfo=None)` for SQLite compatibility — timezone-aware datetimes cause deserialization issues with SQLite
2. **Money as kopiykas**: Use `Decimal` for conversion, never `float` — `int(round(Decimal(value) * 100))`
3. **UTF-8 BOM handling**: Strip BOM character (`\ufeff`) before parsing to prevent header matching failures
4. **Parser does NOT commit session**: `parser_service` adds to session but does NOT call `session.commit()` — caller (Celery task) controls transaction boundary
5. **Flagged rows in separate table**: Use `FlaggedImportRow` model (not mixed into `transactions` table)
6. **Bulk insert pattern**: Use `session.add_all()` for efficient bulk insert of transactions and flagged rows
7. **Pydantic camelCase**: API JSON uses `camelCase` via `alias_generator=to_camel` — DB/Python uses `snake_case`
8. **ProcessingJob initial status is `"validated"`** (set in `upload_service.create_upload_record()`), NOT `"pending"`
9. **Locale codes**: ISO 639-1 (`"uk"`, `"en"`) — NOT `"ua"`
10. **Existing test count**: 149 tests. All must continue to pass after this story.

### Sync Parser Service Wrapper

The existing `parse_and_store_transactions()` in `parser_service.py` uses `AsyncSession`. For Celery, create a **sync version** in the same file:

```python
def sync_parse_and_store_transactions(
    session: Session,    # sqlmodel.Session (sync)
    user_id: uuid.UUID,
    upload_id: uuid.UUID,
    file_bytes: bytes,
    format_result: FormatDetectionResult,
) -> ParseAndStoreResult:
    """Synchronous version for Celery worker context."""
    # Same logic as async version but using sync session
    # Parser.parse() is already sync (CPU-bound, no I/O)
    # Only session.add_all() and session operations differ
```

**Why not refactor the existing async function?** To avoid breaking the 149 existing tests that depend on the async interface. Adding a sync wrapper is safer.

### Project Structure Notes

**New files to create:**
```
backend/app/tasks/processing_tasks.py       # NEW — Celery task for upload processing
backend/app/api/v1/jobs.py                  # NEW — Job status endpoint
backend/tests/test_processing_tasks.py      # NEW — Celery task tests
backend/tests/test_jobs.py                  # NEW — Job status endpoint tests
backend/alembic/versions/xxxx_add_result_data_to_processing_jobs.py  # NEW — Migration
```

**Files to modify:**
```
backend/app/core/config.py                  # ADD: SYNC_DATABASE_URL property
backend/app/core/database.py                # ADD: sync_engine + get_sync_session()
backend/app/tasks/celery_app.py             # ADD: autodiscover_tasks, time limits, track_started
backend/app/api/v1/uploads.py               # ADD: dispatch process_upload.delay() after record creation
backend/app/api/v1/router.py                # ADD: register jobs router
backend/app/services/parser_service.py      # ADD: sync_parse_and_store_transactions()
backend/app/models/processing_job.py        # ADD: result_data JSON field
backend/pyproject.toml                      # ADD: psycopg2-binary dependency
```

**Do NOT modify:**
```
backend/app/agents/ingestion/parsers/base.py         # Parser interface is stable
backend/app/agents/ingestion/parsers/monobank.py     # Story 2.3 — parser is complete
backend/app/agents/ingestion/parsers/privatbank.py   # Story 2.4 — parser is complete
backend/app/agents/ingestion/parsers/generic.py      # Story 2.4 — parser is complete
backend/app/services/format_detector.py              # Story 2.2 — detection is complete
backend/app/models/transaction.py                    # Transaction model is stable
backend/app/models/flagged_import_row.py             # FlaggedImportRow model is stable
backend/app/models/upload.py                         # Upload model is stable
backend/app/services/upload_service.py               # Upload validation is stable (only uploads.py dispatches task)
```

### Testing Requirements

**Backend Tests (pytest) — minimum 11 new test cases across 2 test files:**

**test_processing_tasks.py** (Celery task tests):
- Use `celery_app.conf.update(task_always_eager=True, task_eager_propagates=True)` in test fixtures to run tasks synchronously
- Mock S3 downloads via `@patch("app.tasks.processing_tasks.boto3.client")`
- Use SQLite sync engine for test DB: `create_engine("sqlite:///./test_celery.db", poolclass=NullPool)`
- Test happy path: task runs, transactions persisted, job = "completed"
- Test transient error retry: mock S3 error, verify `self.retry()` called
- Test permanent error: mock UnsupportedFormatError, verify job = "failed", no retry
- Test max retries: verify job = "failed" with MAX_RETRIES_EXCEEDED
- Test partial results preserved on failure
- Test performance: 500 transactions < 60 seconds

**test_jobs.py** (API endpoint tests):
- Test GET /api/v1/jobs/{id} returns correct status
- Test tenant isolation (user A cannot see user B's job)
- Test 404 for non-existent job

**Regression**: All 149 existing tests must pass. The only change to existing tests is that `test_uploads.py` may need `process_upload.delay` mocked to prevent actual task dispatch during upload tests.

### Library & Framework Requirements

**Celery 5.6.x (already installed):**
- Use `@celery_app.task(bind=True, max_retries=3, acks_late=True)` decorator
- Use `self.retry(exc=exc, countdown=2**self.request.retries)` for exponential backoff
- Use `celery_app.autodiscover_tasks(["app.tasks"])` for task registration
- JSON serializer only (already configured) — pass UUIDs as strings, not objects

**Redis 7.x (already running via docker-compose):**
- Used as Celery broker and result backend (already configured)
- Connection: `redis://localhost:6379/0` (default)

**psycopg2-binary (NEW — must add to pyproject.toml):**
- Synchronous PostgreSQL driver for Celery worker processes
- `pip install psycopg2-binary` or add to `[project.dependencies]` in pyproject.toml
- Used only by sync engine in `database.py` — async code continues to use asyncpg

**Do NOT introduce:**
- `dramatiq` or `huey` (alternative task queues — Celery is the project standard)
- `asgiref` or `async_to_sync` (creates event loop conflicts in Celery)
- `celery[redis]` extras — redis is already separately installed

### Git Intelligence (Recent Commits)

```
9de745c Story 2.4: Additional Bank Format Parser
d5a064e Story 2.3: Monobank CSV Parser
557de19 Story 2.2: File Validation & Format Detection
0a58b72 Story 2.1: File Upload UI & S3 Storage
```

**Patterns established in Stories 2.1-2.4:**
- Upload endpoint returns HTTP 202 with jobId and statusUrl
- ProcessingJob status starts at `"validated"` after upload
- Parser service is async, adds to session, does NOT commit
- Tests use SQLite with aiosqlite, mock S3 via `@patch`
- Test fixtures use real CSV files in `tests/fixtures/`
- Error responses follow `{"error": {"code": "...", "message": "...", "details": {...}}}` format
- Pydantic responses use camelCase via `alias_generator=to_camel`
- Auth check via `Depends(get_current_user_id)` in deps.py
- Tenant isolation: always filter by `user_id` in queries

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 2, Story 2.5]
- [Source: _bmad-output/planning-artifacts/architecture.md — Celery configuration, async pipeline flow, backend structure, error handling, testing standards]
- [Source: _bmad-output/planning-artifacts/prd.md — FR8 (Ingestion Agent), FR12 (async 200-500 tx processing)]
- [Source: _bmad-output/implementation-artifacts/2-4-additional-bank-format-parser.md — Previous story learnings, parser patterns]
- [Source: backend/app/tasks/celery_app.py — Existing Celery configuration]
- [Source: backend/app/core/database.py — Async engine + session pattern]
- [Source: backend/app/core/config.py — Settings with REDIS_URL, DATABASE_URL]
- [Source: backend/app/core/redis.py — Async Redis client]
- [Source: backend/app/api/v1/uploads.py — Current upload endpoint (HTTP 202, no task dispatch)]
- [Source: backend/app/services/parser_service.py — parse_and_store_transactions() async function]
- [Source: backend/app/services/upload_service.py — create_upload_record() sets status="validated"]
- [Source: backend/app/models/processing_job.py — ProcessingJob model with status, step, progress fields]
- [Source: docker-compose.yml — Redis 7-alpine already running on port 6379]
- [Source: backend/Dockerfile.worker — Celery worker Dockerfile ready]
- [Source: https://docs.celeryq.dev/en/stable/userguide/tasks.html — Celery 5.6 task configuration]
- [Source: https://celery.school/sqlalchemy-session-celery-tasks — SQLAlchemy session handling in Celery tasks]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- Fixed test session management: sync SQLite tests need `StaticPool` (not `NullPool`) to share in-memory DB across connections
- Celery task `request` property cannot be patched with `patch.object` — used `patch.object(task, "retry")` instead for retry tests
- Upload tests required `process_upload.delay` mock to prevent task dispatch during endpoint tests

### Completion Notes List

- Implemented `process_upload` Celery task with full processing pipeline: load job → download S3 → parse → persist → update status
- Added `sync_parse_and_store_transactions()` wrapper in parser_service.py to support synchronous Celery workers without breaking existing async interface
- Added `get_sync_session()` with sync engine using `NullPool` for Celery worker process isolation
- Added `SYNC_DATABASE_URL` property derived from `DATABASE_URL` with driver substitution
- Created `GET /api/v1/jobs/{job_id}` endpoint with tenant isolation, camelCase response
- Implemented retry logic: transient errors (S3 ClientError, DB OperationalError) retry with exponential backoff; permanent errors (UnsupportedFormatError, ValueError, SoftTimeLimitExceeded) fail immediately
- Added `result_data` JSON column to ProcessingJob model with Alembic migration
- Updated Celery config with autodiscovery, time limits (90s soft / 120s hard), task_track_started
- Added Celery task dispatch (`process_upload.delay`) in upload endpoint after DB commit
- All 160 tests pass (149 existing + 11 new), 0 regressions
- 500 transaction performance test completes well under 60s threshold

### Change Log

- 2026-03-28: Story 2.5 implementation complete — async pipeline processing with Celery

### File List

**New files:**
- backend/app/tasks/processing_tasks.py
- backend/app/api/v1/jobs.py
- backend/tests/test_processing_tasks.py
- backend/tests/test_jobs.py
- backend/alembic/versions/c8e2f4a6b0d1_add_result_data_to_processing_jobs.py

**Modified files:**
- backend/app/core/config.py (added SYNC_DATABASE_URL property)
- backend/app/core/database.py (added sync_engine + get_sync_session)
- backend/app/tasks/celery_app.py (added autodiscover, time limits, track_started)
- backend/app/api/v1/uploads.py (added process_upload.delay dispatch)
- backend/app/api/v1/router.py (registered jobs router)
- backend/app/services/parser_service.py (added sync_parse_and_store_transactions)
- backend/app/models/processing_job.py (added result_data JSON field)
- backend/tests/test_uploads.py (added process_upload.delay mock + dispatch test)
