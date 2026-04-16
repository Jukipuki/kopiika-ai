# Story 2.8: Upload Completion UX & Summary

Status: done
Created: 2026-04-16
Epic: 2 — Statement Upload & Data Ingestion

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want to see the full pipeline processing progress and an upload summary before being taken to the Teaching Feed,
so that I know what was processed and feel confident in the results before viewing insights.

## Acceptance Criteria

1. **Given** I have uploaded a statement file and received a `jobId`, **When** the frontend opens the SSE stream, **Then** I see a pipeline progress view (not the Teaching Feed) showing each agent step completing in sequence — the frontend does NOT automatically redirect to the Teaching Feed on upload.

2. **Given** the pipeline is running and SSE `pipeline-progress` events arrive, **When** each agent step completes, **Then** the progress view shows step name, a human-readable message (from Story 4.1 `message` field), and a visual progress indicator; steps shown include **Ingestion**, **Categorization**, **Pattern Detection** (Phase 1.5 placeholder: skipped gracefully if not yet active), **Triage** (placeholder: skipped gracefully if not yet active), **Education**.

3. **Given** the pipeline completes and a `job-complete` SSE event is received, **When** the completion payload is processed, **Then** the frontend displays an upload summary card showing: detected bank name (`bankName`), total transactions parsed (`transactionCount`), statement date range (`dateRange`), and total insight cards generated (`totalInsights`), with a "View Insights" call-to-action button.

4. **Given** the `job-complete` SSE payload, **When** it is returned from the backend, **Then** it includes the fields: `bankName` (string, bank detected by format parser), `transactionCount` (integer), `dateRange` (object with ISO date `start` and `end`), `totalInsights` (integer) — the backend populates these from the completed pipeline state.

5. **Given** the user reads the upload summary, **When** they click "View Insights", **Then** they are navigated to the Teaching Feed (`/feed` route).

6. **Given** the pipeline fails before completion, **When** the `job-failed` SSE event fires, **Then** the progress view shows a user-friendly error message with a retry option (existing behaviour from Story 2.6) — the summary card is not shown.

## Tasks / Subtasks

- [x] **Task 1: Backend — enrich `job-complete` SSE payload** (AC: #3, #4)
  - [x] 1.1 In [backend/app/tasks/processing_tasks.py#L359-366](backend/app/tasks/processing_tasks.py#L359-366), compute the summary payload at pipeline completion: `bank_name`, `transaction_count`, `date_range`, `total_insights`.
    - `bankName`: derive from `upload.detected_format` via a small helper (`"monobank" → "Monobank"`, `"privatbank" → "PrivatBank"`, `None`/`"unknown"` → localized "Bank statement" or empty string — let frontend fall back to `formatDetected*` i18n if empty).
    - `transactionCount`: total **new** rows persisted for this upload → `result.persisted_count - result.flagged_count` (this is `new_transactions`, already computed at line 131). NOT cumulative across uploads.
    - `dateRange`: `{ start: min(date), end: max(date) }` across transactions in this upload — query `SELECT MIN(date), MAX(date) FROM transactions WHERE upload_id = :upload_id` (ISO 8601 date strings `"YYYY-MM-DD"`; omit field if no transactions).
    - `totalInsights`: `len(insight_cards)` (already in payload).
  - [x] 1.2 Add a `_get_upload_summary(session, upload, new_transactions, insight_count)` helper in `processing_tasks.py` (or inline) that assembles the dict. Keep the computation near the existing `publish_job_progress(job-complete)` call.
  - [x] 1.3 Extend the published `job-complete` event payload with the new fields (camelCase keys to match existing SSE wire format):
    ```python
    publish_job_progress(job_id, {
        "event": "job-complete",
        "jobId": job_id,
        "status": "completed",
        "duplicatesSkipped": result.duplicates_skipped,
        "newTransactions": new_transactions,
        "totalInsights": len(insight_cards),
        "bankName": bank_name,              # NEW
        "transactionCount": new_transactions,  # NEW — alias of newTransactions for AC clarity
        "dateRange": {"start": "...", "end": "..."} or None,  # NEW
    })
    ```
  - [x] 1.4 Also update the synthetic `job-complete` event in [backend/app/api/v1/jobs.py#L221-226](backend/app/api/v1/jobs.py#L221-226) (fallback when job is already "completed" at stream-connect time): read summary fields from `job.result_data` and include them in the synthetic event. This requires Task 1.5.
  - [x] 1.5 Persist summary fields to `ProcessingJob.result_data` (existing JSON column) alongside existing keys, so they survive reconnect and match the live SSE payload:
    ```python
    job.result_data = {
        ...,  # existing keys
        "bank_name": bank_name,
        "date_range_start": "2026-02-01",  # or None
        "date_range_end": "2026-02-28",    # or None
        "insight_count": len(insight_cards),
    }
    ```
  - [x] 1.6 Mirror the same enrichment in the `resume_upload` task's `job-complete` event at [backend/app/tasks/processing_tasks.py#L647-652](backend/app/tasks/processing_tasks.py#L647-652) — read from already-persisted transactions for this upload (resume path re-runs categorization/education, but ingestion is already done so transactions exist).

- [x] **Task 2: Frontend — remove auto-redirect and keep user on upload page** (AC: #1, #6)
  - [x] 2.1 In [frontend/src/features/upload/components/UploadDropzone.tsx#L68-72](frontend/src/features/upload/components/UploadDropzone.tsx#L68-72), **delete** the `useEffect` that calls `router.push(\`/feed?jobId=${activeJobId}\`)`. The user stays on `/upload` for the full pipeline.
  - [x] 2.2 Remove the now-unused `useRouter` import from `UploadDropzone.tsx` if not referenced elsewhere (it currently is only used by the deleted effect).
  - [x] 2.3 The existing `state === "uploading"` branch (which renders `<UploadProgress>`) already covers the in-flight pipeline view — verify it still renders for the full pipeline duration (not just file upload).
  - [x] 2.4 The existing `processingFailed` branch (lines 247-264) already handles `job-failed` with retry CTA — leave it.
  - [x] 2.5 Verify (by running the app or via tests) that on `job-complete` arrival the component transitions from the uploading/progress view to the completion/summary view without a flash.

- [x] **Task 3: Frontend — extract `message` from SSE and surface it in the progress view** (AC: #2)
  - [x] 3.1 Extend [frontend/src/features/upload/types.ts#L61-70](frontend/src/features/upload/types.ts#L61-70) `JobStatusState`: add `message: string | null`.
  - [x] 3.2 Extend the same file's `JobCompleteEvent` type: add `bankName?: string | null`, `transactionCount?: number`, `dateRange?: { start: string; end: string } | null`.
  - [x] 3.3 Extend `JobStatusState.result` to include the new summary fields: `{ totalInsights, duplicatesSkipped?, newTransactions?, bankName?, transactionCount?, dateRange? }`.
  - [x] 3.4 In [frontend/src/features/upload/hooks/use-job-status.ts#L64-75](frontend/src/features/upload/hooks/use-job-status.ts#L64-75) (pipeline-progress handler), set `message: data.message ?? null` into state.
  - [x] 3.5 In the same file's `job-complete` handler (lines 77-98), include `bankName`, `transactionCount`, `dateRange` in `result` and clear `message` to `null`.
  - [x] 3.6 Initial `initialState` (line 13-22): add `message: null`.
  - [x] 3.7 In [frontend/src/features/upload/components/UploadProgress.tsx](frontend/src/features/upload/components/UploadProgress.tsx), pass `message={jobStatus.message}` to `<ProcessingPipeline>`.
  - [x] 3.8 In [frontend/src/features/upload/components/ProcessingPipeline.tsx](frontend/src/features/upload/components/ProcessingPipeline.tsx):
    - Accept a new prop `message: string | null`.
    - Replace the per-stage `education.${stageKey}` subtitle (line 115) with the backend-driven `message` when the stage is active. Pattern from Story 4.1: render `message ?? t('fallbackMessage')` where `fallbackMessage` is a generic "Processing…" localized string (reuse `feed.processing` or add `upload.processing.fallback`).
    - Keep stage labels (`t(\`stages.${stageKey}\`)`) as-is — they are the fixed "step name" visual.

- [x] **Task 4: Frontend — re-sequence pipeline stages to match AC #2 canonical list** (AC: #2)
  - [x] 4.1 Update `STAGES` in [frontend/src/features/upload/components/ProcessingPipeline.tsx#L8-14](frontend/src/features/upload/components/ProcessingPipeline.tsx#L8-14) to the epic-canonical ordered list:
    ```ts
    const STAGES = [
      "ingestion",        // was: readingTransactions
      "categorization",   // was: categorizingSpending
      "patternDetection", // was: detectingPatterns (rename for clarity)
      "triage",           // NEW — placeholder for Epic 8; skipped gracefully today
      "education",        // was: generatingInsights
    ] as const;
    ```
  - [x] 4.2 Update i18n keys to match in [frontend/messages/en.json](frontend/messages/en.json) and [frontend/messages/uk.json](frontend/messages/uk.json) under `upload.processing.stages.*` and `upload.processing.education.*`. Keep the existing copy tone — this is a rename/remap, not new copy:
    - `ingestion` → "Reading your transactions..." (EN) / reuse existing UA string
    - `categorization` → "Categorizing your spending..."
    - `patternDetection` → "Detecting patterns..."
    - `triage` → "Prioritizing what matters..." (NEW copy, localized in both locales)
    - `education` → "Generating personalized insights..."
  - [x] 4.3 Update `getActiveStageIndex()` in the same file to map backend `step` values to the new stage order:
    - `"ingestion"` → 0
    - `"categorization"` → 1
    - `"patterns"` / `"pattern_detection"` → 2 (future Epic 8)
    - `"triage"` → 3 (future Epic 8)
    - `"profile"` → 3 (temporary — profile build sits between categorization and education; map to triage slot so the existing event advances progress)
    - `"health-score"` → 3 (temporary — same reason; see Phase-1.5 note below)
    - `"education"` → 4
    - `"done"` → `STAGES.length`
  - [x] 4.4 **Phase 1.5 behaviour note** (implement, don't just document): Pattern Detection and Triage agents do not exist yet (Epic 8). When the backend skips these steps (i.e., jumps from `categorization` → `profile`/`health-score` → `education`), the frontend MUST render those stages as "done" (checkmark) once `progress >= 60` for Pattern Detection and `progress >= 80` for Triage, so the UI visually shows all 5 stages completing, not 3 stages skipping. The existing `isDone = isCompleted || index < activeIndex` logic handles this automatically when `getActiveStageIndex` advances — confirm it works without a visible gap.

- [x] **Task 5: Frontend — build the upload summary card** (AC: #3, #5)
  - [x] 5.1 Create [frontend/src/features/upload/components/UploadSummaryCard.tsx](frontend/src/features/upload/components/UploadSummaryCard.tsx) — a client component that takes `bankName`, `transactionCount`, `dateRange`, `totalInsights` and renders:
    - Checkmark icon + celebratory headline (i18n: `upload.summary.title`, e.g., "Your statement is ready").
    - Detected bank line ("Monobank statement detected" — reuse existing `formatDetected*` i18n fallback if `bankName` is null/empty).
    - Transaction count ("{count, plural, one {# transaction} other {# transactions}} analyzed" — new i18n key `upload.summary.transactionCount`).
    - Date range formatted with `next-intl` `useFormatter().dateTime` ("Jan 15 – Feb 28, 2026" style — new i18n key `upload.summary.dateRange` with interpolation).
    - Insight count ("{count, plural, one {# insight card} other {# insight cards}} generated" — new key `upload.summary.insightCount`).
    - Primary CTA button: "View Insights" (new key `upload.summary.viewInsights`) → `<Link href="/feed">`.
    - Secondary links: reuse existing `uploadAnother` button + `viewHistory` link from the current completion block.
  - [x] 5.2 Replace the existing `processingComplete` block in [frontend/src/features/upload/components/UploadDropzone.tsx#L266-309](frontend/src/features/upload/components/UploadDropzone.tsx#L266-309) with `<UploadSummaryCard {...jobStatus.result!} onUploadAnother={...} />`. Keep the `onUploadAnother` reset behavior (clears `activeJobId`, `selectedFile`, `lastUploadResult`, error).
  - [x] 5.3 Graceful fallback when summary fields are missing (e.g., `dateRange` null for a file with no parseable dates): hide that specific line rather than rendering "undefined". Preserve existing "X new, Y duplicates skipped" dedup line from Story 2.7 — it still belongs here.
  - [x] 5.4 Ensure the CTA uses `@/i18n/navigation` `Link` (not `next/link`) for locale-aware routing. The feed route is `/feed` (no `?jobId` query — the pipeline is already complete, so Feed's progressive-loading SSE path is not needed on this navigation).

- [x] **Task 6: Backend tests** (AC: #3, #4)
  - [x] 6.1 Extend [backend/tests/test_sse_streaming.py](backend/tests/test_sse_streaming.py) (existing: `test_happy_path_publishes_progress_events`): assert the final `job-complete` event payload now contains `bankName`, `transactionCount`, `dateRange.start`, `dateRange.end`, `totalInsights` with expected values.
  - [x] 6.2 Extend [backend/tests/test_processing_tasks.py](backend/tests/test_processing_tasks.py): after `process_upload.delay` runs in eager mode, assert `job.result_data` contains the new summary keys (`bank_name`, `date_range_start`, `date_range_end`, `insight_count`).
  - [x] 6.3 Add a test: when no transactions are persisted (e.g., all flagged or all duplicates), `dateRange` is `null` in the SSE payload and the synthetic fallback in `jobs.py` doesn't crash.
  - [x] 6.4 Add a test for the synthetic `job-complete` fallback in [backend/tests/test_sse_streaming.py](backend/tests/test_sse_streaming.py) or similar: simulate SSE reconnect after job is already `"completed"` — the fallback event in [jobs.py#L221-226](backend/app/api/v1/jobs.py#L221-226) should include `bankName`/`transactionCount`/`dateRange`/`totalInsights` pulled from `result_data`.
  - [x] 6.5 Regression: all existing backend tests must continue to pass (baseline: see sprint-status — last known ~273+).

- [x] **Task 7: Frontend tests** (AC: #1, #2, #3, #5, #6)
  - [x] 7.1 Update [frontend/src/features/upload/__tests__/UploadDropzone.test.tsx](frontend/src/features/upload/__tests__/UploadDropzone.test.tsx): remove any assertion that `router.push('/feed?jobId=...')` is called after upload success. Add the inverse: router.push is NOT called.
  - [x] 7.2 Update [frontend/src/features/upload/__tests__/use-job-status.test.tsx](frontend/src/features/upload/__tests__/use-job-status.test.tsx) to cover: `message` is extracted from `pipeline-progress` events; `bankName`/`transactionCount`/`dateRange` are captured from `job-complete`; `message` is cleared on terminal events.
  - [x] 7.3 Update [frontend/src/features/upload/__tests__/ProcessingPipeline.test.tsx](frontend/src/features/upload/__tests__/ProcessingPipeline.test.tsx) for the renamed stages (`ingestion`/`categorization`/`patternDetection`/`triage`/`education`) and the new `message` prop behavior (message rendered when active; fallback when null).
  - [x] 7.4 Add `UploadSummaryCard.test.tsx`: renders bank name, transaction count, date range, insight count; "View Insights" link has `href="/feed"`; hides date-range line when `dateRange` prop is null; plural/singular copy renders correctly.
  - [x] 7.5 Add an integration-style UploadDropzone test: when `useJobStatus` returns `status: "completed"` with a full `result` object, the summary card is rendered (not the old "File uploaded successfully!" message) and the "View Insights" link is present.
  - [x] 7.6 Add an UploadDropzone test: when `useJobStatus` returns `status: "failed"`, the summary card is NOT rendered; the retry CTA IS rendered (AC #6).
  - [x] 7.7 Regression: all existing frontend tests must continue to pass.

- [x] **Task 8: i18n strings** (AC: #2, #3)
  - [x] 8.1 Add to both [frontend/messages/en.json](frontend/messages/en.json) and [frontend/messages/uk.json](frontend/messages/uk.json):
    ```json
    "upload": {
      "processing": {
        "stages": {
          "ingestion": "...",
          "categorization": "...",
          "patternDetection": "...",
          "triage": "...",
          "education": "..."
        },
        "education": { /* same 5 keys — subtitle/education copy per stage */ },
        "fallbackMessage": "Processing..."
      },
      "summary": {
        "title": "Your statement is ready",
        "transactionCount": "{count, plural, one {# transaction} other {# transactions}} analyzed",
        "dateRange": "{start} – {end}",
        "insightCount": "{count, plural, one {# insight card} other {# insight cards}} generated",
        "viewInsights": "View Insights"
      }
    }
    ```
  - [x] 8.2 Remove obsolete keys (`readingTransactions`, `categorizingSpending`, `detectingPatterns`, `scoringHealth`, `generatingInsights`) from both locales. Search all callers before removing — only `ProcessingPipeline.tsx` consumes these.
  - [x] 8.3 If your project has an i18n-parity test (Story 2.7 added one for history keys per H3), extend it to cover the new `upload.summary.*` and renamed `upload.processing.stages.*` keys.

## Dev Notes

### Critical Architecture Compliance

**Tech Stack (MUST use):**
- Backend: Python 3.12, FastAPI, SQLModel, Celery 5.6.x, Redis 7.x, Alembic
- Frontend: Next.js 16.1 (App Router — **read `node_modules/next/dist/docs/` before writing any new Next API usage**, per `frontend/AGENTS.md`), TanStack Query v5, `next-intl`, shadcn/ui, Tailwind CSS 4.x, `motion/react` (not `framer-motion` — this project uses `motion/react`)
- ORM: SQLModel (SQLAlchemy 2.x + Pydantic v2)
- Pydantic camelCase: all API JSON uses `camelCase` via `alias_generator=to_camel, populate_by_name=True`
- SSE wire format: events are hand-built JSON via `publish_job_progress({...})` in Redis — they are **not** Pydantic models, so camelCase keys are written directly in the dict literal.

**Backend component dependency rules (never violate):**
| Layer | Can Depend On | NEVER Depends On |
|---|---|---|
| `api/` | `core/`, `models/`, `services/` | `agents/`, `tasks/` |
| `services/` | `core/`, `models/` | `api/`, `tasks/` |
| `tasks/` | `core/`, `services/`, `agents/` | `api/` |

**Data format rules:**
- Dates in API: ISO 8601 (use `"YYYY-MM-DD"` strings for `dateRange`, since `Transaction.date` is a `DATE` column — do **not** include time component).
- Money: integer kopiykas (not relevant to this story, but keep in mind).
- JSON field naming: camelCase in all SSE payloads and API responses.

### What changes — and what deliberately does NOT

**Changes:**
- Upload page keeps the user in place during the full pipeline (no auto-redirect).
- Pipeline stage visual on upload page has 5 canonical stages matching the epic-wide pipeline (Ingestion → Categorization → Pattern Detection → Triage → Education).
- Each in-progress stage displays the backend-provided `message` (reusing Story 4.1's decoupled-message pattern, but on a different component).
- `job-complete` SSE payload gains `bankName`, `transactionCount`, `dateRange`, `totalInsights`.
- Completion state on upload page becomes a richer "UploadSummaryCard" with a "View Insights" CTA.

**Deliberately unchanged (don't touch):**
- Teaching Feed's `FeedContainer` / `useFeedSSE` / `ProgressiveLoadingState` — Story 4.1/4.3 already decoupled that. Navigating to `/feed` (without `?jobId`) means Feed renders from cached data via TanStack Query; no SSE needed there.
- `use-upload-history` / `UploadHistoryList` — Story 2.7's history UI stays as-is.
- Deduplication behavior and the existing `duplicatesSkipped` / `newTransactions` SSE fields — both still flow through; the summary card continues to show the dedup line.

### Why the existing redirect must go

The current flow ([UploadDropzone.tsx#L68-72](frontend/src/features/upload/components/UploadDropzone.tsx#L68-72)) redirects to `/feed?jobId=X` immediately after `POST /uploads` resolves. That was a deliberate Epic 3 choice (Story 3.7 review fix H3) to let `ProgressiveLoadingState` carry the wait experience inside Feed.

Story 2.8 replaces that model: the wait experience lives on the upload page (with a richer multi-stage pipeline view and a summary card), and the user **explicitly** clicks "View Insights" to enter the feed. This gives the "completion celebration" moment the UX spec calls for, and prevents the current jarring pattern of Feed rendering a bare "ProgressiveLoading" while the user is mentally still in the upload context.

Note that Story 4.3's fixes (empty-state flash guard via `wasStreamingRef`, fade-out animations) are **still valuable** for the Feed page itself — they protect Feed whenever the user arrives there with a live job (e.g., shared link, reconnect). Leave them alone.

### Backend pipeline topology (current state, as of Story 6.5)

The Celery `process_upload` task ([backend/app/tasks/processing_tasks.py](backend/app/tasks/processing_tasks.py)) emits these SSE `pipeline-progress` events (step → progress → message):

| Step | Progress | Message |
|---|---|---|
| `ingestion` | 10 | "Reading transactions..." |
| `ingestion` | 30 | "Parsing complete" |
| `categorization` | 40 | "Categorizing N transactions..." |
| `categorization` | 60 | "Categorization complete" |
| `education` | 80 | "Generated N financial insights" |
| `profile` | 90 | "Building your financial profile..." |
| `health-score` | 92 | "Calculating your Financial Health Score..." |
| _(terminal)_ `job-complete` | 100 | N/A |

**There is no `pattern-detection` or `triage` step yet** — those are Epic 8 work. The 5-stage frontend visual (Task 4) must gracefully handle their absence by advancing the checkmark past those stages when `categorization → profile/health-score` progresses.

### Example: final `job-complete` SSE payload (after this story)

```json
{
  "event": "job-complete",
  "jobId": "7f1c...",
  "status": "completed",
  "bankName": "Monobank",
  "transactionCount": 245,
  "dateRange": { "start": "2026-02-01", "end": "2026-02-28" },
  "totalInsights": 12,
  "duplicatesSkipped": 0,
  "newTransactions": 245
}
```

### Bank name mapping (Task 1.1 helper)

```python
BANK_DISPLAY_NAMES = {
    "monobank": "Monobank",
    "privatbank": "PrivatBank",
}

def get_bank_display_name(detected_format: str | None) -> str | None:
    if not detected_format:
        return None
    return BANK_DISPLAY_NAMES.get(detected_format, None)
```

Place this in [backend/app/services/format_detector.py](backend/app/services/format_detector.py) or a new `backend/app/services/bank_display.py`. Import from `processing_tasks.py`. The frontend already has an equivalent `FORMAT_LABEL_MAP` fallback via `formatDetected*` i18n keys — so returning `None` on unknown formats is safe (frontend falls back gracefully).

### Date range query

```python
from sqlmodel import select, func

min_date, max_date = session.exec(
    select(func.min(Transaction.date), func.max(Transaction.date))
    .where(Transaction.upload_id == upload.id)
).one()

date_range = (
    {"start": min_date.isoformat(), "end": max_date.isoformat()}
    if min_date and max_date
    else None
)
```

`Transaction.date` is a `DATE` column per [backend/app/models/transaction.py](backend/app/models/transaction.py#L18). `.isoformat()` gives `"YYYY-MM-DD"`.

### Previous Story Intelligence (Stories 2.6, 2.7, 4.1, 4.3)

**Patterns to REUSE:**
- `publish_job_progress(job_id, {...})` from [backend/app/core/redis.py](backend/app/core/redis.py) — hand-built camelCase dict; the same pattern is used 7× in `processing_tasks.py`. Copy verbatim.
- Backend-owned human-readable messages: Story 4.1 established that the backend sends `message` and the frontend displays it directly without mapping dictionaries. Follow that pattern here — **do not** add a new hardcoded `PHASE_COPY` map on the upload page. The `education.${stageKey}` subtitle in the current `ProcessingPipeline` should be replaced by `jobStatus.message`, not duplicated.
- `get_sync_session()` for sync DB access inside Celery tasks (already used in `processing_tasks.py`).
- Pydantic camelCase via `alias_generator=to_camel, populate_by_name=True` for any new response models (none needed in this story — SSE is dict-based).
- `@/i18n/navigation` `Link` / `useRouter` for all frontend navigation — NEVER import from `next/link` or `next/navigation` directly (Story 2.7 already used this pattern).
- Cursor tracking via refs (`wasStreamingRef` in `FeedContainer`) for state-transition guards — relevant only for Feed; upload page doesn't need it because the summary card is shown immediately on `job-complete` and there's no race with a separate query refetch.

**Do NOT repeat these mistakes (accumulated from Stories 2.5–2.7, 4.1):**
1. DateTime: use `datetime.now(UTC).replace(tzinfo=None)` for SQLite test compatibility (helper `_utcnow` already exists in `processing_tasks.py`).
2. Celery task `request` property cannot be patched with `patch.object` — use `patch.object(task, "retry")` instead.
3. Sync SQLite tests need `StaticPool` (not `NullPool`) to share in-memory DB.
4. Upload tests require `process_upload.delay` mock to prevent task dispatch.
5. Celery tasks are SYNCHRONOUS — use `redis.Redis` (sync), NOT `redis.asyncio`.
6. Frontend tests wrap hooks using TanStack Query in `QueryClientProvider` with `retry: false` (see `use-upload-history.test.tsx`).
7. Add `vi.mock("@/i18n/navigation")` and `vi.mock("next-intl")` with `createUseTranslations()` from `@/test-utils/intl-mock` to every frontend component test.
8. When renaming i18n keys, grep **both** `frontend/src` and `frontend/messages` AND the test files — stale refs break the next-intl runtime, not tests.

### Project Structure Notes

- New frontend component: `frontend/src/features/upload/components/UploadSummaryCard.tsx` — same folder as `UploadDropzone.tsx`, `ProcessingPipeline.tsx`, `UploadProgress.tsx`, `UploadHistoryList.tsx`. No new feature folder.
- New test file: `frontend/src/features/upload/__tests__/UploadSummaryCard.test.tsx`.
- Backend helper: prefer a small function in `backend/app/services/format_detector.py` (keeps bank-format knowledge co-located) over a new module.
- No new API endpoints, no new database columns, no new migrations — summary fields ride on the existing `ProcessingJob.result_data` JSON column.
- The `/feed` page itself is untouched by this story. Navigation CTA goes to `/feed` (the existing route at [frontend/src/app/[locale]/(dashboard)/feed/page.tsx](frontend/src/app/[locale]/(dashboard)/feed/page.tsx)), without a `jobId` query parameter.

### Git Intelligence (Latest Commits)

Most recent commits on `main` (last 6):
- `738db34` Story 1.9: Project Versioning Baseline
- `d6e4d25` Story 1.8: Forgot-Password Flow
- `4035de8` Phase 1 planning and kick-off
- `3c44dfc` Story 6.6: Operator Job Status & Health Queries
- `dee2ee7` Story 6.5: Pipeline Performance & Upload Metrics Tracking
- `fca9ed2` Story 6.4: Structured Logging with Correlation IDs

None of the recent commits touch `processing_tasks.py`, `UploadDropzone.tsx`, `ProcessingPipeline.tsx`, or `use-job-status.ts` — working tree for those files is clean relative to the last 6 commits. No merge-conflict risk.

Story 6.5 added `pipeline_metrics` log emission at pipeline completion; the new summary fields should NOT be duplicated into that metrics log — they are user-facing summary data, not operational telemetry. Keep the two concerns separate.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 2.8: Upload Completion UX & Summary](_bmad-output/planning-artifacts/epics.md#L705-735)
- [Source: _bmad-output/implementation-artifacts/2-7-multiple-statement-uploads-cumulative-history.md](_bmad-output/implementation-artifacts/2-7-multiple-statement-uploads-cumulative-history.md) — dedup fields in SSE payload; existing completion block pattern
- [Source: _bmad-output/implementation-artifacts/4-1-sse-progress-message-decoupling.md](_bmad-output/implementation-artifacts/4-1-sse-progress-message-decoupling.md) — backend-owned `message` pattern to reuse
- [Source: _bmad-output/implementation-artifacts/4-3-redirect-timing-progressive-loading-verification.md](_bmad-output/implementation-artifacts/4-3-redirect-timing-progressive-loading-verification.md) — prior assumption (redirect-to-feed) that this story explicitly reverses
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md#Design Opportunities](_bmad-output/planning-artifacts/ux-design-specification.md#L59) — "cumulative intelligence as visible UX"; "Completion Celebration" moment
- [Source: backend/app/tasks/processing_tasks.py#L359-366](backend/app/tasks/processing_tasks.py#L359-366) — current `job-complete` payload (to enrich)
- [Source: backend/app/api/v1/jobs.py#L221-226](backend/app/api/v1/jobs.py#L221-226) — synthetic fallback `job-complete` (to update)
- [Source: frontend/src/features/upload/components/UploadDropzone.tsx#L68-72](frontend/src/features/upload/components/UploadDropzone.tsx#L68-72) — auto-redirect to delete
- [Source: frontend/src/features/upload/components/UploadDropzone.tsx#L266-309](frontend/src/features/upload/components/UploadDropzone.tsx#L266-309) — existing completion block to replace
- [Source: frontend/src/features/upload/hooks/use-job-status.ts](frontend/src/features/upload/hooks/use-job-status.ts) — SSE event consumer
- [Source: frontend/src/features/upload/components/ProcessingPipeline.tsx](frontend/src/features/upload/components/ProcessingPipeline.tsx) — pipeline visual to extend with `message` prop and re-sequence
- [Source: frontend/AGENTS.md](frontend/AGENTS.md) — "This is NOT the Next.js you know" — consult `node_modules/next/dist/docs/` before using any Next.js API not already present elsewhere in the codebase.

## Dev Agent Record

### Agent Model Used

claude-opus-4-6 (1M context) via Claude Code CLI

### Debug Log References

- Backend full suite: `438 passed, 2 warnings in 153.71s` (no regressions; Story 2.8 added 6 new tests)
- Frontend full suite: `377 passed (377)` across 41 test files (no regressions; Story 2.8 added 7 new UploadSummaryCard tests + 4 new use-job-status/UploadDropzone tests + 2 new ProcessingPipeline tests)
- Lint baseline: 21 problems pre-change → 19 after (net −2; pre-existing errors in `query-provider.tsx` are out of scope)
- TypeScript: only pre-existing errors remain in unrelated files (`FeatureErrorBoundary.test.tsx`, `LoginForm.test.tsx`, `FeedContainer.test.tsx`)

### Completion Notes List

- AC #1, #6: Auto-redirect from `UploadDropzone.tsx` deleted; failure branch retains existing retry CTA. Verified by `does not auto-redirect to /feed after a successful upload (Story 2.8)` and `does NOT render the summary card when job has failed (Story 2.8 AC #6)` tests.
- AC #2: `ProcessingPipeline` re-sequenced to canonical 5 stages (`ingestion` → `categorization` → `patternDetection` → `triage` → `education`). Backend-driven `message` is rendered under the active stage (with `fallbackMessage` i18n fallback). Phase-1.5 placeholder behaviour confirmed: when backend jumps `categorization` → `profile`/`health-score`, both pattern-detection and triage advance to "done".
- AC #3, #4: `process_upload` now computes `bank_name`, `transactionCount` (= new transactions for this upload), `dateRange` (min/max `Transaction.date` cast to `YYYY-MM-DD`), and `totalInsights`. The four fields are emitted in the live `job-complete` SSE payload AND persisted to `ProcessingJob.result_data` so the synthetic fallback in `jobs.py` returns the same shape on reconnect. `resume_upload` mirrors the enrichment.
- AC #5: New `UploadSummaryCard` renders headline, bank line, transaction count, date range, insight count, dedup line, and a primary "View Insights" CTA → `/feed` (no `?jobId`, since the pipeline is already complete and `ProgressiveLoadingState` is no longer needed for this navigation).
- Bank name mapping centralised in `app.services.format_detector.get_bank_display_name`; unknown formats return `None` so the frontend falls back to the existing `formatDetected*` localized labels.
- Dev Notes initially asserted `Transaction.date` is a `DATE` column — actually it is a `datetime`. `_get_upload_summary` strips the time component via `.date().isoformat()` to produce `"YYYY-MM-DD"`.
- i18n parity: en + uk both updated with renamed `processing.stages.*`/`processing.education.*` keys plus new `processing.fallbackMessage` and `summary.*` keys (plurals localised for Ukrainian one/few/many/other forms).
- The summary card is wrapped in a `stopPropagation` div inside the dropzone container so clicks on the card do not re-trigger the file picker.

### File List

**Backend (modified):**
- `backend/app/services/format_detector.py` — added `BANK_DISPLAY_NAMES` map and `get_bank_display_name()` helper.
- `backend/app/tasks/processing_tasks.py` — added `_get_upload_summary()` helper; enriched `job-complete` payload and `result_data` in both `process_upload` and `resume_upload`.
- `backend/app/api/v1/jobs.py` — synthetic `job-complete` fallback now reads `bank_name`, `date_range_*`, `insight_count`, `new_transactions` from `result_data`.

**Backend tests (modified):**
- `backend/tests/test_sse_streaming.py` — extended `test_happy_path_publishes_progress_events` assertions; added `TestSSESyntheticCompleteFallback` class with two reconnect-fallback tests.
- `backend/tests/test_processing_tasks.py` — added `TestProcessUploadSummaryPayload` class with four tests covering result_data, payload, null `dateRange`, and unknown-format `bankName=null`.

**Frontend (modified):**
- `frontend/src/features/upload/types.ts` — added `DateRange`, `JobStatusResult`; extended `JobCompleteEvent` and `JobStatusState` with the new fields and `message`.
- `frontend/src/features/upload/hooks/use-job-status.ts` — initial state gets `message: null`; `pipeline-progress` writes `message`; `job-complete` writes `bankName`/`transactionCount`/`dateRange` and clears `message`; `job-failed` clears `message`.
- `frontend/src/features/upload/components/ProcessingPipeline.tsx` — re-sequenced stages, accepts `message` prop, renders backend message under active stage with `fallbackMessage`; `getActiveStageIndex` updated for new ordering plus Phase-1.5 step routing.
- `frontend/src/features/upload/components/UploadProgress.tsx` — passes `message={jobStatus.message}` to `ProcessingPipeline`.
- `frontend/src/features/upload/components/UploadDropzone.tsx` — removed auto-redirect `useEffect`, removed `useRouter`/`History`/`CheckCircle2`/`Link`/`toast` imports for the completion block, and replaced the inline completion view with the new `UploadSummaryCard`. Wrapped in a `stopPropagation` div.
- `frontend/messages/en.json` + `frontend/messages/uk.json` — renamed `processing.stages.*` (`ingestion`/`categorization`/`patternDetection`/`triage`/`education`), renamed matching `processing.education.*`, added `processing.fallbackMessage`, added `summary.*` block (`title`, `bankDetected`, `transactionCount`, `dateRange`, `insightCount`, `viewInsights`).

**Frontend (created):**
- `frontend/src/features/upload/components/UploadSummaryCard.tsx` — new client component with View Insights CTA + secondary "Upload another"/"View upload history" links.
- `frontend/src/features/upload/__tests__/UploadSummaryCard.test.tsx` — 7 unit tests (title, bank line, View Insights link href, transaction/insight counts, date-range null hiding, fallback bank label, secondary actions).

**Frontend tests (modified):**
- `frontend/src/features/upload/__tests__/use-job-status.test.tsx` — extended pipeline-progress test to assert `message`; added "captures bankName, transactionCount, dateRange" + "clears message on terminal events" tests.
- `frontend/src/features/upload/__tests__/ProcessingPipeline.test.tsx` — renamed stage assertions to canonical 5 stages; added "renders backend-driven message", "falls back to localized fallbackMessage", and "advances past pattern-detection/triage placeholders" tests; added the `message` prop to all existing render calls.
- `frontend/src/features/upload/__tests__/UploadDropzone.test.tsx` — added per-test mockable `useJobStatus`; new tests "does not auto-redirect", "renders UploadSummaryCard with View Insights when job completes", and "does NOT render the summary card when job has failed".

**Sprint status:**
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — `2-8-upload-completion-ux-summary: ready-for-dev → in-progress → review`

## Senior Developer Review (AI)

**Reviewer:** Oleh (via Claude Opus 4.6 — adversarial code-review pass)
**Date:** 2026-04-16
**Outcome:** Approved with fixes applied. All HIGH/MEDIUM findings resolved in-place; LOW findings routed to the tech-debt register (see below).

### Findings & disposition

| # | Severity | Title | Disposition |
|---|---|---|---|
| H1 | HIGH | Synthetic `job-complete` / `job-failed` / `job-retrying` SSE data omitted `"event"` field; frontend's `if (data.event === "job-complete")` guard silently rejected reconnect-time payloads — UploadSummaryCard would never render after an SSE reconnect. | **Fixed** — added `"event"` to all three synthetic payloads in [backend/app/api/v1/jobs.py:216-260](backend/app/api/v1/jobs.py#L216-L260). New regression test `test_synthetic_terminal_payloads_include_event_field_in_json` parses the SSE data line and asserts the field is present. |
| M1 | MEDIUM | `processing.education.*` i18n block was dead code after the `message`-from-backend rewrite (Task 8.2 missed). | **Fixed** — block removed from both [en.json](frontend/messages/en.json) and [uk.json](frontend/messages/uk.json); grep confirms zero references remaining. |
| M2 | MEDIUM | `does not auto-redirect` test (Task 7.1) asserted symptoms (pathname, missing summary card) but never verified `router.push` itself. A regression of the deleted redirect would have passed. | **Fixed** — hoisted `mockRouterPush` spy in [UploadDropzone.test.tsx:19-26](frontend/src/features/upload/__tests__/UploadDropzone.test.tsx#L19-L26); test now asserts `expect(mockRouterPush).not.toHaveBeenCalled()`. |
| M3 | MEDIUM | `_get_upload_summary` `hasattr(min_date, "date")` branch was dead defensive code that could silently produce wrong wire-format dates if SQLite ever returned ISO strings. | **Fixed** — branch removed in [processing_tasks.py:39-54](backend/app/tasks/processing_tasks.py#L39-L54); helper now trusts the `Transaction.date: datetime` column type. |
| M4 | MEDIUM | Synthetic `job-failed` had the same missing-`event` bug as H1. | **Fixed** — bundled with H1 fix; regression test covers both branches. |
| L1 | LOW | Resume path may double-count insights (`prior_insight_count + len(insight_cards)` with no Insight-row dedup on resume). | → [TD-007](../../docs/tech-debt.md) |
| L2 | LOW | Redundant `if job.result_data else None` after `(job.result_data or {})` in resume path. | Withdrawn — pure cosmetic; not worth a TD entry. |
| L3 | LOW | Dropzone outer container retains `border-primary/30 bg-primary/5` "selected" styling while UploadSummaryCard renders. | → [TD-008](../../docs/tech-debt.md) |
| L4 | LOW | Story Task 8.3 (i18n parity test extension) not visibly addressed. | Withdrawn on review — no Story 2.7 i18n-parity test exists in the repo (verified via grep); Task 8.3 is N/A. |

### Verification

- Backend: `439 passed` (was 438 — added the H1 regression test).
- Frontend: `377 passed` across 41 test files (no regressions; M2 fix tightened the existing test, no new test count).

## Change Log

| Date | Author | Change |
|------|--------|--------|
| 2026-04-16 | Claude Opus 4.6 (Dev Agent) | Story 2.8 implementation complete — backend `job-complete` enriched, frontend auto-redirect removed, 5-stage pipeline visual rewired with backend-driven `message`, new `UploadSummaryCard` with "View Insights" CTA, en/uk i18n updated, 19 new tests added (377 frontend + 438 backend total passing). Status → review. |
| 2026-04-16 | Claude Opus 4.6 (Code Reviewer) | Adversarial review: 1 HIGH (H1: synthetic SSE missing `event` field), 4 MEDIUM (M1-M4), 4 LOW. All HIGH/MEDIUM fixed in-place; L1/L3 promoted to TD-007/TD-008; L2/L4 withdrawn. New regression test added. Backend 439 passed, frontend 377 passed. Status → done. |
