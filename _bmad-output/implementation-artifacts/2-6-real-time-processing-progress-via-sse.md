# Story 2.6: Real-Time Processing Progress via SSE

Status: done
Created: 2026-03-28
Epic: 2 - Statement Upload & Data Ingestion

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want to see real-time progress of my statement processing,
so that I know the system is working and how long to wait.

## Acceptance Criteria

1. **Given** I have uploaded a file and received a jobId, **When** I stay on the app screen, **Then** the frontend opens an SSE connection to `GET /api/v1/jobs/{id}/stream`
2. **Given** the pipeline is processing, **When** each pipeline step completes, **Then** the Celery worker updates Redis with progress, and an SSE event is pushed to the frontend with step name and percentage
3. **Given** the pipeline completes successfully, **When** the `job-complete` SSE event fires, **Then** the frontend receives `{"jobId": "uuid", "status": "completed", "totalInsights": N}` and transitions to showing results
4. **Given** the pipeline fails, **When** the `job-failed` SSE event fires, **Then** the frontend shows a user-friendly error message (not technical details) with a retry option
5. **Given** the SSE connection drops, **When** the frontend reconnects, **Then** it receives the current state and resumes progress display without duplicate events

## Tasks / Subtasks

- [x] Task 1: Add Redis Pub/Sub utilities for job progress (AC: #2)
  - [x] 1.1 Add `publish_job_progress(job_id, data)` helper to `backend/app/core/redis.py`
  - [x] 1.2 Add `subscribe_job_progress(job_id)` async generator to `backend/app/core/redis.py`
  - [x] 1.3 Use Redis PUBLISH/SUBSCRIBE on channel `job:progress:{job_id}`
  - [x] 1.4 Store latest state with `HSET job:state:{job_id}` so reconnecting clients get current state immediately (AC: #5)

- [x] Task 2: Update Celery task to publish progress to Redis (AC: #2)
  - [x] 2.1 Import and call `publish_job_progress()` in `backend/app/tasks/processing_tasks.py` at each progress checkpoint
  - [x] 2.2 Publish `pipeline-progress` events with `{step, progress, message}` payload
  - [x] 2.3 Publish `job-complete` event on success with `{status: "completed", totalInsights: 0}` (totalInsights=0 until Epic 3)
  - [x] 2.4 Publish `job-failed` event on failure with `{status: "failed", error: {code, message}}`
  - [x] 2.5 Store final state in Redis hash for reconnection support
  - [x] 2.6 NOTE: Celery tasks are SYNCHRONOUS — use `redis.Redis` (sync client), NOT `aioredis`

- [x] Task 3: Create SSE streaming endpoint (AC: #1, #3, #4, #5)
  - [x] 3.1 Add `GET /api/v1/jobs/{job_id}/stream` endpoint in `backend/app/api/v1/jobs.py`
  - [x] 3.2 Use `fastapi.responses.StreamingResponse` with `media_type="text/event-stream"`
  - [x] 3.3 On connection, immediately send current state from Redis hash (AC: #5 — reconnection)
  - [x] 3.4 Subscribe to Redis pub/sub channel and yield SSE-formatted events
  - [x] 3.5 Send `job-complete` or `job-failed` terminal events then close stream
  - [x] 3.6 Enforce user_id tenant isolation (same as existing GET endpoint)
  - [x] 3.7 Add heartbeat/keepalive every 15s to prevent proxy timeouts
  - [x] 3.8 Handle client disconnect gracefully (cleanup Redis subscription)

- [x] Task 4: Create `use-job-status` frontend hook (AC: #1, #3, #4, #5)
  - [x] 4.1 Create `frontend/src/features/upload/hooks/use-job-status.ts`
  - [x] 4.2 Use `EventSource` API to connect to `/api/v1/jobs/{id}/stream`
  - [x] 4.3 Parse SSE events: `pipeline-progress`, `job-complete`, `job-failed`
  - [x] 4.4 Return `{ status, step, progress, error, result, isConnected }` state
  - [x] 4.5 Implement auto-reconnect with exponential backoff on connection drop (AC: #5)
  - [x] 4.6 Clean up EventSource on unmount
  - [x] 4.7 Include auth token in SSE request (via query param or cookie — EventSource doesn't support headers)

- [x] Task 5: Build `ProcessingPipeline` progress UI component (AC: #2, #3, #4)
  - [x] 5.1 Create `frontend/src/features/upload/components/ProcessingPipeline.tsx`
  - [x] 5.2 Display 5-stage vertical list: Reading transactions → Categorizing spending → Detecting patterns → Scoring financial health → Generating insights
  - [x] 5.3 Active stage shows pulse animation, completed stages show checkmark
  - [x] 5.4 Map backend `step` values to 5 UX stages (backend currently sends "ingestion"/"done")
  - [x] 5.5 Add educational micro-content per stage (i18n: `uk` + `en`)
  - [x] 5.6 Add `role="progressbar"` with `aria-valuenow`, `aria-live="polite"` for accessibility
  - [x] 5.7 Respect `prefers-reduced-motion` — show static layout without animations
  - [x] 5.8 On `job-complete`: transition to completion state
  - [x] 5.9 On `job-failed`: show error card with user-friendly message + retry CTA

- [x] Task 6: Update `UploadProgress` component to use new pipeline UI (AC: #1, #2, #3, #4)
  - [x] 6.1 Replace static spinner in `frontend/src/features/upload/components/UploadProgress.tsx` with `ProcessingPipeline`
  - [x] 6.2 Wire `use-job-status` hook with `jobId` from upload response
  - [x] 6.3 Show trust message during processing: "Your data stays encrypted and private"
  - [x] 6.4 Handle error state: display friendly message + "Try again" button
  - [x] 6.5 Handle completion: show summary stats (transactions processed) and CTA

- [x] Task 7: Backend tests (AC: all)
  - [x] 7.1 Test SSE endpoint streams progress events correctly
  - [x] 7.2 Test SSE endpoint enforces tenant isolation (404 for other users)
  - [x] 7.3 Test SSE endpoint returns current state on reconnection
  - [x] 7.4 Test SSE endpoint closes after terminal event (job-complete/job-failed)
  - [x] 7.5 Test Redis pub/sub publish and subscribe utilities
  - [x] 7.6 Test Celery task publishes progress events to Redis
  - [x] 7.7 Regression: all 160 existing tests must continue to pass

- [x] Task 8: Frontend tests (AC: all)
  - [x] 8.1 Test `use-job-status` hook connects to SSE and parses events
  - [x] 8.2 Test `use-job-status` hook auto-reconnects on disconnect
  - [x] 8.3 Test `ProcessingPipeline` component renders stages correctly
  - [x] 8.4 Test error state renders retry button
  - [x] 8.5 Test accessibility: `role="progressbar"`, `aria-live`

## Dev Notes

### Critical Architecture Compliance

**Tech Stack (MUST use):**
- Backend: Python 3.12, FastAPI, SQLModel, Celery 5.6.x, Redis 7.x
- Frontend: Next.js 16.1, TanStack Query v5, Vercel AI SDK (for SSE consumption patterns)
- SSE: FastAPI `StreamingResponse` (backend) → native `EventSource` API (frontend)
- Pydantic camelCase: All API JSON uses `camelCase` via `alias_generator=to_camel, populate_by_name=True`

**SSE Event Format (from architecture):**
```
event: pipeline-progress
data: {"jobId": "uuid", "step": "categorization", "progress": 30, "message": "Categorizing 245 transactions..."}

event: insight-ready
data: {"jobId": "uuid", "insightId": "uuid", "type": "spendingInsight"}

event: job-complete
data: {"jobId": "uuid", "status": "completed", "totalInsights": 12}

event: job-failed
data: {"jobId": "uuid", "status": "failed", "error": {"code": "LLM_ERROR", "message": "..."}}
```
SSE event names use `kebab-case`. [Source: architecture.md#SSE Event Structure, lines 612-626]

**Redis Integration Pattern:**
- Celery workers (sync context) → use `redis.Redis` (sync) to PUBLISH progress + HSET state
- FastAPI SSE endpoint (async context) → use `redis.asyncio.Redis` to SUBSCRIBE + HGET state
- Channel: `job:progress:{job_id}` for pub/sub
- Hash key: `job:state:{job_id}` for current state snapshot (enables reconnection)
- Set TTL on Redis keys (e.g., 1 hour) to prevent stale data buildup

**Celery is SYNCHRONOUS — critical reminder from Story 2.5:**
- Celery tasks use `sqlmodel.Session` (sync), NOT `AsyncSession`
- Use `redis.Redis` for publishing (sync), NOT `redis.asyncio`
- The sync Redis client can be created inline or via a simple factory — do NOT import the async `get_redis()` from `core/redis.py`
- Existing `get_sync_session()` pattern in `core/database.py` for DB access

**Backend Component Dependencies (MUST follow):**
| Layer | Can Depend On | NEVER Depends On |
|---|---|---|
| `api/` (jobs.py SSE endpoint) | `core/`, `models/` | `agents/`, `tasks/` |
| `tasks/` (Celery progress publishing) | `core/`, `services/`, `agents/` | `api/` |

**Authentication for SSE:**
- `EventSource` API does NOT support custom headers
- Options: (a) Pass JWT via query param `?token=xxx`, (b) Use cookie-based auth, (c) Validate via initial DB lookup like existing `GET /jobs/{id}`
- Recommended: Use same `get_current_user_id` dependency as existing job endpoint — FastAPI can extract JWT from query params for SSE
- ALWAYS verify `job.user_id == current_user_id` for tenant isolation

### ProcessingJob Status Flow (Updated)
```
"validated" → "processing" → "completed"
                    ↓
               "failed" (after retries exhausted)
```
Progress checkpoints in Celery task (current Story 2.5 implementation):
- 10% → "ingestion" step (task picked up)
- 30% → parsing complete
- 100% → "done" step (all persisted)

**For this story, expand progress granularity:**
- 10% → "ingestion" (Reading transactions...)
- 30% → "ingestion" complete (Parsing done)
- 40% → future: categorization step (placeholder for Epic 3)
- 60% → future: pattern detection (placeholder for Epic 3)
- 80% → future: triage/scoring (placeholder for Epic 3)
- 100% → "done" (Complete)

**NOTE:** Until Epic 3 implements the full LangGraph pipeline agents, the processing jumps from ingestion (30%) to done (100%). The frontend 5-stage UI should still show all stages but stages 2-5 will complete rapidly. This is by design — the UI is forward-compatible.

### UX Requirements (from UX Design Specification)

**5-Stage Processing Pipeline Visualization:**
1. "Reading your transactions..." + educational micro-content
2. "Categorizing your spending..." + education about categories
3. "Detecting patterns..." + what patterns mean
4. "Scoring your financial health..." + how scoring works
5. "Generating personalized insights..." + what insights will show

**Component States:**
- `stage-N-active` — current stage with pulse animation
- `stage-N-complete` — checkmark + faded
- `complete` — all stages done, transitions to CompletionCelebration
- `error` — specific stage shows warning, error card appears

**Accessibility (MUST implement):**
- `role="progressbar"` with `aria-valuenow` (current stage number)
- `aria-live="polite"` announces stage transitions to screen readers
- Respect `prefers-reduced-motion` — static layout, no animations
- Focus management: auto-focus CTA after processing completes

**Loading Feedback Tiering:**
- Short waits (<2s): skeleton placeholders
- Medium waits (2-30s): ProcessingPipeline with stage indicators + educational micro-content
- Long waits (>30s): ProcessingPipeline + progress percentage + "we'll notify you" option

**Error States (errors are cards, not modals):**
- Never show technical errors to user
- Show: "We couldn't process this file" + actionable guidance
- Partial parse: "We processed 80% of your transactions" + transparency note
- Always provide retry CTA

**Trust Message:** Display "Your data stays encrypted and private" during processing
[Source: ux-design-specification.md#ProcessingPipeline component, lines 1019-1047]

### Frontend Architecture Notes

**File locations (from architecture):**
```
frontend/src/features/upload/
├── components/
│   ├── UploadDropzone.tsx        # Existing - drag-drop upload
│   ├── UploadProgress.tsx        # Existing - UPDATE to use ProcessingPipeline
│   ├── ProcessingPipeline.tsx    # NEW - 5-stage progress visualization
│   └── FileFormatGuide.tsx       # Existing - format help
├── hooks/
│   ├── use-upload.ts             # Existing - upload mutation
│   └── use-job-status.ts         # NEW - SSE streaming hook
└── types.ts                      # UPDATE - add SSE event types
```

**i18n:** All user-facing strings in `frontend/src/i18n/messages/en.json` and `uk.json`. Processing stage labels, error messages, educational micro-content must be translated.

**Animation Tokens (from UX spec):**
- `slow`: 400ms — processing stage changes
- `dramatic`: 800ms — completion celebration
- Easing: `ease-out` for enter, `ease-in` for exit
- Use Framer Motion or CSS transitions

### Previous Story Intelligence (Story 2.5 Learnings)

**DO NOT REPEAT these mistakes:**
1. DateTime: Use `datetime.now(UTC).replace(tzinfo=None)` for SQLite test compatibility
2. Celery task `request` property cannot be patched with `patch.object` — use `patch.object(task, "retry")` instead
3. Sync SQLite tests need `StaticPool` (not `NullPool`) to share in-memory DB
4. Upload tests require `process_upload.delay` mock to prevent task dispatch
5. ProcessingJob initial status is `"validated"` (NOT `"pending"`)
6. Pydantic camelCase: `alias_generator=to_camel, populate_by_name=True` on all response models
7. Money stored as kopiykas (integer), locale codes are ISO 639-1 (`"uk"`, `"en"`)

**Patterns established in Story 2.5 to REUSE:**
- `get_sync_session()` for sync DB access in Celery tasks
- `SYNC_DATABASE_URL` property derivation (async → sync driver swap)
- `celery_app.conf.update(task_always_eager=True, task_eager_propagates=True)` for test setup
- Mock S3 via `@patch("app.tasks.processing_tasks.boto3.client")`
- `JobStatusResponse` Pydantic model pattern in `jobs.py`

**Current test count: 160 tests — ALL must continue to pass.**

### Git Intelligence (Latest Commit: Story 2.5)

Recent commit `13b3bbe` (Story 2.5) established:
- `backend/app/tasks/processing_tasks.py` — Celery `process_upload` task (modify to add Redis publishing)
- `backend/app/api/v1/jobs.py` — Job status endpoint (add SSE `/stream` endpoint here)
- `backend/app/core/database.py` — Sync engine + `get_sync_session()` (reuse pattern)
- `backend/app/core/config.py` — `SYNC_DATABASE_URL`, `REDIS_URL` already configured
- `backend/app/core/redis.py` — Basic async Redis client exists (extend with pub/sub utilities)
- `backend/app/models/processing_job.py` — Has `status`, `step`, `progress`, `error_code`, `error_message`, `result_data`

### Project Structure Notes

- SSE endpoint goes in existing `backend/app/api/v1/jobs.py` alongside current `GET /jobs/{id}` — architecture specifies `jobs.py` handles both status and SSE streaming
- Redis pub/sub utilities added to existing `backend/app/core/redis.py` — NOT a new file
- New frontend components follow `features/upload/components/` convention
- New frontend hook follows `features/upload/hooks/` convention
- All new backend tests go in `backend/tests/` — follow existing `test_jobs.py` and `test_processing_tasks.py` patterns

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Epic 2, Story 2.6]
- [Source: _bmad-output/planning-artifacts/architecture.md#SSE Event Structure, lines 612-626]
- [Source: _bmad-output/planning-artifacts/architecture.md#API & Communication Patterns, lines 306-317]
- [Source: _bmad-output/planning-artifacts/architecture.md#Internal Communication, lines 1094-1102]
- [Source: _bmad-output/planning-artifacts/architecture.md#Backend Directory Structure, lines 878-891]
- [Source: _bmad-output/planning-artifacts/prd.md#FR13 - SSE streaming]
- [Source: _bmad-output/planning-artifacts/prd.md#Performance targets, line 605]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md#ProcessingPipeline component, lines 1019-1047]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md#Feedback Patterns, lines 1214-1241]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md#Error Recovery Journey, lines 828-858]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md#Animation Patterns, lines 1347-1364]
- [Source: _bmad-output/implementation-artifacts/2-5-async-pipeline-processing-with-celery.md - Previous story learnings]

## Dev Agent Record

### Agent Model Used
Claude Opus 4.6

### Debug Log References
- Greenlet error in SSE tests: Resolved by pre-capturing `job.id` as plain UUID before SQLAlchemy session commit to avoid lazy-loading in async test context
- intl-mock updated to support nested key lookups (e.g., `stages.readingTransactions`) for ProcessingPipeline i18n

### Completion Notes List
- Implemented full Redis Pub/Sub for real-time job progress: sync publisher (Celery) + async subscriber (FastAPI SSE)
- SSE endpoint at `GET /api/v1/jobs/{id}/stream` with query-param JWT auth (EventSource limitation)
- Celery task publishes pipeline-progress at 10% and 30%, job-complete on success, job-failed on error
- Redis state storage (SET with 1hr TTL) enables reconnection support (AC #5)
- 15s heartbeat/keepalive prevents proxy timeouts
- Frontend `useJobStatus` hook with EventSource, auto-reconnect with exponential backoff (max 10 attempts)
- 5-stage ProcessingPipeline component with educational micro-content, i18n (en/uk), accessibility (progressbar, aria-live)
- `prefers-reduced-motion` respected via `motion-safe:` Tailwind prefix
- UploadDropzone updated: upload → SSE processing → completion flow
- Backend: 171 tests pass (160 existing + 11 new SSE/Redis tests)
- Frontend: 99 tests pass (86 existing + 13 new hook/component tests)

### Change Log
- 2026-03-28: Story 2.6 implementation complete — real-time processing progress via SSE
- 2026-03-28: Code review — fixed 7 issues (3 HIGH, 4 MEDIUM): race condition in SSE subscribe-before-state-check, docstring accuracy, duplicate _seed removal, terminal-state reconnect guard, auth duplication note, heartbeat test, auth edge-case tests. Backend 174 passed, frontend 99 passed.

### File List
- backend/app/core/redis.py (modified — added pub/sub utilities: publish_job_progress, subscribe_job_progress, get_job_state)
- backend/app/tasks/processing_tasks.py (modified — added publish_job_progress calls at progress checkpoints)
- backend/app/api/v1/jobs.py (modified — added SSE streaming endpoint GET /jobs/{id}/stream with query-param auth)
- backend/tests/test_sse_streaming.py (new — 11 tests for SSE endpoint, Redis utilities, Celery publishing)
- frontend/src/features/upload/types.ts (modified — added SSE event types and JobStatusState)
- frontend/src/features/upload/hooks/use-job-status.ts (new — SSE hook with EventSource, auto-reconnect)
- frontend/src/features/upload/components/ProcessingPipeline.tsx (new — 5-stage progress UI with a11y)
- frontend/src/features/upload/components/UploadProgress.tsx (modified — integrated ProcessingPipeline)
- frontend/src/features/upload/components/UploadDropzone.tsx (modified — wired useJobStatus hook)
- frontend/src/features/upload/__tests__/use-job-status.test.tsx (new — 7 tests for SSE hook)
- frontend/src/features/upload/__tests__/ProcessingPipeline.test.tsx (new — 6 tests for pipeline component)
- frontend/src/features/upload/__tests__/UploadDropzone.test.tsx (modified — updated for new SSE flow)
- frontend/src/test-utils/intl-mock.ts (modified — support nested key lookups)
- frontend/messages/en.json (modified — added processing pipeline translations)
- frontend/messages/uk.json (modified — added processing pipeline translations)
- _bmad-output/implementation-artifacts/sprint-status.yaml (modified — status update)
- _bmad-output/implementation-artifacts/2-6-real-time-processing-progress-via-sse.md (modified — task completion)
