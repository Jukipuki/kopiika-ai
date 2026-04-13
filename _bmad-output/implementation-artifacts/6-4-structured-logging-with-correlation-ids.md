# Story 6.4: Structured Logging with Correlation IDs

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **operator**,
I want structured JSON logs with correlation IDs across all pipeline agents,
so that I can trace and debug issues end-to-end.

## Acceptance Criteria

1. **Given** any backend operation (API request, pipeline step, Celery task) **When** it executes **Then** a structured JSON log entry is produced with: `timestamp`, `level`, `service`, `user_id`, `job_id`, `message`, and relevant context fields

2. **Given** a pipeline processing job **When** it progresses through multiple agents **Then** all log entries share the same `job_id` correlation ID, enabling end-to-end tracing

3. **Given** log levels **When** they are used **Then** they follow the convention: `DEBUG` (SQL queries, LLM prompts), `INFO` (pipeline step completed, upload received), `WARNING` (LLM retry, low confidence), `ERROR` (pipeline failure, auth failure), `CRITICAL` (DB connection lost, Redis down)

4. **Given** production logs **When** they are emitted **Then** they never contain sensitive financial data (transaction amounts, descriptions) — only IDs, timestamps, and operation metadata

## Tasks / Subtasks

- [x] Task 1: Enhance `JsonFormatter` to capture all structured extra fields (AC: #1, #2)
  - [x] 1.1 In `backend/app/core/logging.py`, replace the hardcoded 6-field extraction loop with a generic approach: iterate over all keys in `record.__dict__` that were added via `extra={}` — exclude standard `LogRecord` attributes (use a `_LOG_RECORD_BUILTIN_ATTRS` frozenset). This ensures any field passed via `extra=` (including `job_id`, `step`, `duration_ms`, etc.) is captured in the JSON output
  - [x] 1.2 Add `service` field to every log entry: derive from `record.name` by taking the segment after `"app."` (e.g., `"app.agents.categorization.node"` → `"agents.categorization"`, `"app.api.v1.uploads"` → `"api.uploads"`, `"app.tasks.processing_tasks"` → `"tasks"`). If `record.name` does not start with `"app."`, use `record.name` as-is
  - [x] 1.3 Remove the explicit `"logger"` field from JSON output (superseded by `"service"`) — or keep it as `"logger"` alongside `"service"` for backward compat; either is acceptable but pick one and be consistent

- [x] Task 2: Fix JSON-in-string anti-pattern in agent nodes (AC: #1, #2, #3)
  - [x] 2.1 In `backend/app/agents/categorization/node.py` line ~109–114, replace the JSON-in-string `logger.info('{"level": "INFO", "step": "categorization", ...}', ...)` call with: `logger.info("batch_categorized", extra={"step": "categorization", "batch_size": len(transactions), "tokens_used": tokens, "model": getattr(llm, "model_name", getattr(llm, "model", "unknown"))})`
  - [x] 2.2 In `backend/app/agents/education/node.py` line ~86, replace `logger.info('{"level": "INFO", "step": "education", "message": "No categorized transactions, skipping"}')` with `logger.info("education_skipped", extra={"step": "education", "reason": "no_categorized_transactions"})`
  - [x] 2.3 In `backend/app/agents/education/node.py` line ~127–132, replace the JSON-in-string logger.info with: `logger.info("education_completed", extra={"step": "education", "cards_generated": len(cards), "locale": locale, "literacy_level": literacy_level})`
  - [x] 2.4 In `backend/app/agents/education/node.py` line ~143, replace `logger.error('{"level": "ERROR", "step": "education", "error": "%s"}', exc)` with: `logger.error("education_failed", extra={"step": "education"}, exc_info=True)` — pass `exc_info=True` so the formatter captures the traceback via `record.exc_info`; do NOT include `exc` in the message string as it may contain PII

- [x] Task 3: Add `job_id` and `user_id` to all pipeline agent log calls (AC: #2)
  - [x] 3.1 In `backend/app/agents/categorization/node.py`, in the `categorization_node(state)` function, extract `job_id = state["job_id"]` and `user_id = state["user_id"]` at the top of the function. Add `"job_id": job_id, "user_id": user_id` to every existing `logger.*` call within this function (warnings for parse failures, errors for LLM unavailability, the batch_categorized info log)
  - [x] 3.2 In `backend/app/agents/education/node.py`, in the `education_node(state)` function, extract `job_id = state["job_id"]` and `user_id = state["user_id"]` at the top. Add these to all logger calls within the function
  - [x] 3.3 In `backend/app/tasks/processing_tasks.py`, verify all logger calls already include `job_id` (they currently do via `extra={"job_id": job_id}`). After Task 1.1 fix, these will start appearing in JSON output correctly — no code change needed beyond confirming

- [x] Task 4: Add request logging middleware (AC: #1, #3, #4)
  - [x] 4.1 Create `backend/app/core/middleware.py` with `RequestLoggingMiddleware(BaseHTTPMiddleware)`:
    - Generate a `request_id = str(uuid.uuid4())` per request
    - Record `start_time = time.monotonic()` before calling `await call_next(request)`
    - After response: `duration_ms = round((time.monotonic() - start_time) * 1000)`
    - Extract `path` from `request.url.path` — do NOT log query params (may contain tokens)
    - Log: `logger.info("http_request", extra={"method": request.method, "path": path, "status_code": response.status_code, "duration_ms": duration_ms, "request_id": request_id})`
    - Add `X-Request-ID: {request_id}` to response headers
    - NEVER log: `Authorization` header, request body, query string, or path segments that look like UUIDs (they are resource IDs, not sensitive, but keep consistent)
    - Do not log `/health` endpoint (exclude with a check on `path == "/health"`)
  - [x] 4.2 Register `RequestLoggingMiddleware` in `backend/app/main.py` — add `app.add_middleware(RequestLoggingMiddleware)` after the CORS middleware. Import from `app.core.middleware`

- [x] Task 5: Privacy audit of existing log statements (AC: #4)
  - [x] 5.1 Grep all `logger.*` calls in `backend/app/` for any that reference: `description`, `amount`, `mcc`, `txn["`, `transaction["` — fix any that log actual financial values by replacing with IDs only
  - [x] 5.2 In `backend/app/agents/categorization/node.py`: confirm `_build_prompt()` logs are not captured at INFO level (the prompt itself contains transaction descriptions/amounts). If any `logger.debug` or similar call logs the prompt, it is acceptable at DEBUG level per architecture, but must never be at INFO or above

- [x] Task 6: Tests (all ACs)
  - [x] 6.1 Create `backend/tests/core/test_logging.py`:
    - Test that `JsonFormatter.format()` captures all fields passed via `extra={}` in the JSON output, not just the 6 hardcoded ones (test with `job_id`, `step`, `duration_ms`)
    - Test that `service` field is present in every log entry
    - Test `service` derivation: `"app.agents.categorization.node"` → `"agents.categorization"`
    - Test that `exc_info` is serialized as `"exception"` string, not raw Python object
    - Test that standard `LogRecord` builtins (like `args`, `lineno`, `filename`) are NOT included in the JSON output
  - [x] 6.2 Create `backend/tests/core/test_middleware.py` (or add to existing test file):
    - Test that `GET /health` returns 200 without generating a log entry (use `caplog` or mock logger)
    - Test that a standard API request returns `X-Request-ID` response header
    - Test that `X-Request-ID` value is a valid UUID string
    - Test that the request log entry contains `method`, `path`, `status_code`, `duration_ms`, `request_id` fields
    - Use the async test client pattern from `backend/tests/conftest.py`
  - [x] 6.3 In `backend/tests/agents/test_categorization.py`, add a test:
    - Call `categorization_node(state)` with a mock state that includes `job_id="test-job-id"` and a mock LLM
    - Capture logs via `caplog` (pytest's log capture)
    - Assert that at least one log entry contains `"job_id"` in its output (verifying AC #2)

## Dev Notes

### What Already Exists — Do NOT Reinvent

**`backend/app/core/logging.py`:**
- Already has `JsonFormatter` class outputting to stdout via `StreamHandler`
- Already has `setup_logging()` called in `main.py` at startup
- Logger hierarchy: `"app"` logger configured at INFO; all module loggers use `logging.getLogger(__name__)` which starts with `"app."` since the package is named `app`
- **GAP**: `JsonFormatter` only captures 6 hardcoded extra fields: `action`, `user_id`, `resource_type`, `resource_id`, `ip`, `event`. Fields like `job_id`, `step`, `duration_ms` are silently dropped — `processing_tasks.py` already passes `extra={"job_id": ...}` but it never appears in JSON output

**`backend/app/agents/state.py`:**
- `FinancialPipelineState` already has `job_id: str`, `user_id: str`, `upload_id: str` — all agent nodes receive this state
- Every agent node already has `state["job_id"]` and `state["user_id"]` available; just not used in log calls yet

**`backend/app/tasks/processing_tasks.py`:**
- Already passes `extra={"job_id": job_id}` in many log calls — these will automatically start working correctly once Task 1.1 fixes the formatter
- Already uses `logger.error`, `logger.warning`, `logger.info`, `logger.exception` consistently

**Existing log calls that already pass `job_id` correctly (will work after Task 1):**
- `logger.error("ProcessingJob not found", extra={"job_id": job_id})` — `processing_tasks.py:52`
- `logger.info("...", extra={"job_id": job_id, "result": ...})` — processing_tasks.py

**JSON-in-string anti-pattern (must fix in Task 2):**
- `categorization/node.py:109`: `logger.info('{"level": "INFO", "step": "categorization", "batch_size": %d, ...}', ...)`
- `education/node.py:86`: `logger.info('{"level": "INFO", "step": "education", "message": "No categorized transactions, skipping"}')`
- `education/node.py:127`: `logger.info('{"level": "INFO", "step": "education", "cards_generated": %d, ...}', ...)`
- `education/node.py:143`: `logger.error('{"level": "ERROR", "step": "education", "error": "%s"}', exc)`
These embed JSON as a raw string in the `message` field — they are not structured and cannot be queried by field in CloudWatch. Fix by moving to `extra={}` dict.

### Architecture Compliance

- **Log format** (from `architecture.md`): `{"timestamp": "...", "level": "INFO", "service": "api", "user_id": "uuid", "job_id": "uuid", "message": "Pipeline step completed", "step": "categorization", "duration_ms": 1234}`
- **Log levels** (exact from architecture): DEBUG for SQL queries + LLM prompts; INFO for step completed + upload received; WARNING for LLM retry + low confidence; ERROR for pipeline failure + auth failure; CRITICAL for DB down + Redis down
- **Error response format**: All HTTP errors return `{"error": {"code": "...", "message": "...", "details": {...}}}` — from `backend/app/core/exceptions.py` — middleware must NOT interfere with this
- **Middleware pattern**: App already uses `CORSMiddleware` from Starlette's `BaseHTTPMiddleware` — use the same `add_middleware()` pattern for `RequestLoggingMiddleware`
- **Privacy**: Never log transaction amounts, descriptions, MCC codes, or any field from the `transactions` list in `FinancialPipelineState`. Log only: IDs (`job_id`, `user_id`, `upload_id`, `transaction_id`), counts (`batch_size`, `cards_generated`), metadata (`model`, `locale`, `step`)

### `JsonFormatter` Fix — Implementation Guidance

The current formatter has:
```python
for key in ("action", "user_id", "resource_type", "resource_id", "ip", "event"):
    value = getattr(record, key, None)
    if value is not None:
        log_data[key] = value
```

Replace with a generic approach using a `_LOG_RECORD_BUILTIN_ATTRS` frozenset to exclude standard `LogRecord` attributes:
```python
# Standard LogRecord attributes to exclude from extra field capture
_LOG_RECORD_BUILTIN_ATTRS: frozenset[str] = frozenset({
    "args", "asctime", "created", "exc_info", "exc_text", "filename",
    "funcName", "levelname", "levelno", "lineno", "message", "module",
    "msecs", "msg", "name", "pathname", "process", "processName",
    "relativeCreated", "stack_info", "thread", "threadName", "taskName",
})

# In format():
for key, value in record.__dict__.items():
    if key not in _LOG_RECORD_BUILTIN_ATTRS and not key.startswith("_"):
        log_data[key] = value
```

For `service` field derivation:
```python
name = record.name  # e.g., "app.agents.categorization.node"
if name.startswith("app."):
    service = name[4:]  # strip "app." prefix → "agents.categorization.node"
else:
    service = name
log_data["service"] = service
```

### File Structure Requirements

**New files to create:**
- `backend/app/core/middleware.py` — `RequestLoggingMiddleware` class
- `backend/tests/core/test_logging.py` — unit tests for enhanced `JsonFormatter`
- `backend/tests/core/test_middleware.py` — middleware tests (or add to existing test structure)

**Files to modify:**
- `backend/app/core/logging.py` — generic extra-field capture + `service` field
- `backend/app/agents/categorization/node.py` — fix JSON-in-string, add `job_id`/`user_id` to node-level logs
- `backend/app/agents/education/node.py` — fix JSON-in-string, add `job_id`/`user_id`
- `backend/app/main.py` — register `RequestLoggingMiddleware`
- `backend/tests/agents/test_categorization.py` — add `job_id` log propagation test

**No frontend changes required.** This is purely backend operational observability.

### Previous Story Intelligence (Story 6.3)

- Agent nodes already follow `try/except` with `failed_node` state mutation — do not alter this error-propagation pattern when adding `exc_info=True` to logger calls
- `CircuitBreakerOpenError` is re-raised (not caught) in both categorization and education nodes — do NOT add `exc_info=True` to any log before a re-raise (it would be confusing); only on the `except Exception as exc` final handler
- Pattern from 6.3: when adding fields, update BOTH the initial-run and resume paths in `processing_tasks.py` — for this story, the logging fix via the formatter is transparent (no code path changes in tasks)
- Test helper `_make_state()` in `backend/tests/agents/test_categorization.py` was updated in 6.2 to include `completed_nodes`, `failed_node`, `literacy_level` — use this updated helper; also ensure `job_id` and `user_id` are present in the state dict it returns

### Git Intelligence (from recent commits)

- Commit pattern: each story is one commit titled `"Story X.Y: Title"`
- Backend tests at `backend/tests/` (API/integration) and `backend/tests/agents/` (agent unit tests)
- Core module tests likely go in `backend/tests/core/` — check if that directory exists; create if needed (check for existing `__init__.py` pattern in other test subdirectories)
- No frontend changes in this story — single-backend commit

### Testing Requirements

- **`JsonFormatter` tests**: Use `logging.makeLogRecord({"msg": "test", "levelname": "INFO", "name": "app.tasks.processing_tasks", ...})` and `logging.LogRecord` directly; set extra fields by manually setting attributes on the record; call `formatter.format(record)` and parse resulting JSON
- **Middleware tests**: Use the async test client from `conftest.py`; check response headers directly on the test client response object; use `caplog` fixture or `unittest.mock.patch` on the logger to capture log output
- **`caplog` usage for agent tests**: `caplog.set_level(logging.INFO, logger="app.agents.categorization.node")` before calling `categorization_node(state)`; after call, inspect `caplog.records` for records with `job_id` attribute
- Privacy test: Write a test that calls `categorization_node` with a state containing a transaction with `description="SALARY FROM EMPLOYER"` and asserts that no log message contains `"SALARY FROM EMPLOYER"`

### References

- [Source: architecture.md#Logging Format] — Required JSON structure with service, job_id, duration_ms
- [Source: architecture.md#Backend Core Modules] — `core/logging.py` is the designated structured logging setup module
- [Source: backend/app/core/logging.py] — current `JsonFormatter` with 6-field limitation
- [Source: backend/app/agents/state.py] — `FinancialPipelineState` with `job_id`, `user_id`
- [Source: backend/app/agents/categorization/node.py#109-114] — JSON-in-string anti-pattern (categorization)
- [Source: backend/app/agents/education/node.py#86,127-132,143] — JSON-in-string anti-pattern (education)
- [Source: backend/app/tasks/processing_tasks.py#52] — already passes `extra={"job_id": ...}` correctly
- [Source: backend/app/main.py] — where to register new middleware

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (claude-opus-4-6)

### Debug Log References

### Completion Notes List

- Task 1: Replaced hardcoded 6-field extraction in `JsonFormatter` with generic `record.__dict__` iteration using `_LOG_RECORD_BUILTIN_ATTRS` frozenset. Added `service` field derived from `record.name` (strips `app.` prefix). Removed `logger` field (superseded by `service`).
- Task 2: Fixed 4 JSON-in-string anti-pattern log calls across `categorization/node.py` and `education/node.py` — replaced with proper `extra={}` structured logging. Used `exc_info=True` for error handler in education node.
- Task 3: Extracted `job_id`/`user_id` from pipeline state at top of `categorization_node` and `education_node`. Propagated via `log_ctx` dict to all logger calls including `_categorize_batch` helper. Confirmed `processing_tasks.py` already passes `job_id` correctly.
- Task 4: Created `RequestLoggingMiddleware` with per-request UUID, timing, path logging. Excludes `/health` endpoint. Adds `X-Request-ID` response header. Registered after CORS middleware.
- Task 5: Privacy audit confirmed no logger calls reference `description`, `amount`, `mcc`, or transaction dict fields. `_build_prompt()` does not log at any level.
- Task 6: Created 15 unit tests for `JsonFormatter` (extra fields, service derivation, exc_info, builtins exclusion), 4 async tests for middleware (health exclusion, X-Request-ID header, UUID validation, required fields), 2 tests for categorization (job_id propagation, PII privacy).

### Change Log

- 2026-04-13: Implemented Story 6.4 — Structured logging with correlation IDs. Enhanced JsonFormatter for generic extra field capture, fixed JSON-in-string anti-pattern in agent nodes, added job_id/user_id correlation across pipeline, created RequestLoggingMiddleware, privacy audit passed, 21 new tests added.
- 2026-04-13: Code review fixes (5 issues) — [H1] Passed log_ctx to `_parse_llm_response` so parse-failure warnings include job_id/user_id; [M1] Fixed service derivation to drop module filename (e.g. `agents.categorization` not `agents.categorization.node`); [M2] Added `default=str` safety net to `json.dumps` in JsonFormatter; [M3] Enhanced privacy test to also verify formatted JSON output doesn't leak PII; [M4] Added OPTIONS preflight skip to RequestLoggingMiddleware.

### File List

**New files:**
- `backend/app/core/middleware.py` — RequestLoggingMiddleware class
- `backend/tests/core/__init__.py` — test package init
- `backend/tests/core/test_logging.py` — 15 JsonFormatter unit tests
- `backend/tests/core/test_middleware.py` — 4 middleware async tests

**Modified files:**
- `backend/app/core/logging.py` — generic extra-field capture + service field
- `backend/app/agents/categorization/node.py` — fixed JSON-in-string, added job_id/user_id correlation, passed log_ctx to _categorize_batch
- `backend/app/agents/education/node.py` — fixed JSON-in-string, added job_id/user_id correlation
- `backend/app/main.py` — registered RequestLoggingMiddleware
- `backend/tests/agents/test_categorization.py` — added job_id propagation test + privacy test
