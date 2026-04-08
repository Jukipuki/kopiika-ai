# Story 4.1: SSE Progress Message Decoupling

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->
<!-- Source: Epic 3 Retrospective — Critical Action Item #1 -->

## Story

As a **developer**,
I want the backend to own human-readable progress messages sent via SSE pipeline-progress events,
so that adding new pipeline steps requires zero frontend changes to progress copy.

## Acceptance Criteria

1. **Given** the backend sends a `pipeline-progress` SSE event, **When** any pipeline step emits progress, **Then** the event payload includes a `message` field with a human-readable, locale-aware string (e.g., "Categorizing your transactions...", "Generating financial insights...").

2. **Given** the frontend `ProgressiveLoadingState` component receives a `pipeline-progress` event, **When** it renders the progress state, **Then** it displays `data.message` directly instead of mapping `data.step` to a hardcoded `PHASE_COPY` dictionary.

3. **Given** a new pipeline step is added in a future epic, **When** it emits `pipeline-progress` events with a `message` field, **Then** the frontend displays the message without any code changes to `ProgressiveLoadingState.tsx`.

4. **Given** the SSE progress events, **When** they include both `message` and `step` fields, **Then** the `step` field is retained for programmatic use (progress bar percentage, analytics) while `message` is used for display.

5. **Given** the fallback scenario where `message` is missing from the SSE payload (backward compatibility), **When** `ProgressiveLoadingState` renders, **Then** it falls back to a generic "Processing..." string rather than crashing or showing undefined.

## Tasks / Subtasks

- [x] Task 1: Update `useFeedSSE` hook to extract `message` from pipeline-progress events (AC: #2, #4)
  - [x] 1.1 In `pipeline-progress` event listener, extract `data.message` alongside existing `data.step`
  - [x] 1.2 Add `message` state: `const [message, setMessage] = useState<string | null>(null)`
  - [x] 1.3 Set `message` from `data.message ?? null` on each pipeline-progress event
  - [x] 1.4 Clear `message` to `null` on `job-complete` and `job-failed` events
  - [x] 1.5 Return `message` from the hook: `return { pendingInsightIds, isStreaming, phase, message }`

- [x] Task 2: Update `ProgressiveLoadingState` to use backend message (AC: #2, #3, #5)
  - [x] 2.1 Change props interface: add `message: string | null`, keep `phase` for backward compat during transition
  - [x] 2.2 Remove `PHASE_COPY` hardcoded dictionary entirely
  - [x] 2.3 Display: `message ?? "Processing..."` (fallback for missing message)
  - [x] 2.4 Remove `phase` prop usage — component now depends only on `message`

- [x] Task 3: Update `FeedContainer` to pass `message` to `ProgressiveLoadingState` (AC: #2)
  - [x] 3.1 Destructure `message` from `useFeedSSE` return value
  - [x] 3.2 Pass `message={message}` to `<ProgressiveLoadingState />`
  - [x] 3.3 Remove `phase` prop from `<ProgressiveLoadingState />` (no longer needed)

- [x] Task 4: Verify backend already sends `message` field in all pipeline-progress events (AC: #1)
  - [x] 4.1 Audit all `publish_job_progress` calls in `backend/app/tasks/processing_tasks.py` — confirm every `pipeline-progress` event includes a `message` field
  - [x] 4.2 If any event is missing `message`, add it with an appropriate human-readable string

- [x] Task 5: Tests (AC: #1–#5)
  - [x] 5.1 Update `use-feed-sse.test.ts`: verify `message` state is set from `data.message` on `pipeline-progress` events
  - [x] 5.2 Update `use-feed-sse.test.ts`: verify `message` is cleared to `null` on `job-complete` and `job-failed`
  - [x] 5.3 Update `ProgressiveLoadingState` tests: verify `message` prop is rendered directly
  - [x] 5.4 Update `ProgressiveLoadingState` tests: verify fallback to "Processing..." when `message` is `null`
  - [x] 5.5 Update `FeedContainer.test.tsx`: verify `message` is passed through from hook to component
  - [x] 5.6 Verify all existing 273 backend + 184 frontend tests continue to pass

## Dev Notes

### Scope Summary

**Frontend-primary story** with minor backend audit. The backend already sends `message` in most SSE events — this story makes the frontend use it instead of its hardcoded copy.

### Current State Analysis

**The problem:** `ProgressiveLoadingState.tsx` (lines 5-9) has a hardcoded `PHASE_COPY` dictionary mapping step names to copy strings. `useFeedSSE.ts` (line 48) only extracts `data.step` and ignores `data.message`. Adding a new pipeline step (e.g., "profile-aggregation" in Epic 4) would silently fall through to "AI is still thinking..." on the frontend.

**Backend already sends `message`:** `processing_tasks.py` includes `message` in every `publish_job_progress` call:
- Line 65: `"message": "Reading transactions..."`
- Line 88+: Additional messages for categorization, education steps

**Frontend ignores `message`:** `useFeedSSE.ts` line 48 reads `data.step` but not `data.message`. `ProgressiveLoadingState.tsx` maps `step → PHASE_COPY[step]`.

**Existing bug:** `PHASE_COPY` uses key `parsing` but backend sends step `ingestion`. The "Crunching your numbers..." copy never actually displays — it always falls through to "AI is still thinking..." for the ingestion phase. This further validates removing the hardcoded mapping.

### Files to Change

- `frontend/src/features/teaching-feed/hooks/use-feed-sse.ts` — add `message` state, extract from SSE data
- `frontend/src/features/teaching-feed/components/ProgressiveLoadingState.tsx` — remove `PHASE_COPY`, use `message` prop
- `frontend/src/features/teaching-feed/components/FeedContainer.tsx` — pass `message` through
- `frontend/src/features/teaching-feed/__tests__/use-feed-sse.test.ts` — test `message` state
- `frontend/src/features/teaching-feed/__tests__/FeedContainer.test.tsx` — test `message` passthrough
- `backend/app/tasks/processing_tasks.py` — audit/verify `message` field presence (may need no changes)

### Architecture Compliance

- SSE event format: `{ event: "pipeline-progress", jobId, step, progress, message }` — `step` retained for programmatic use, `message` added for display
- No new API endpoints or database changes
- Follows existing SSE pattern in `backend/app/api/v1/jobs.py`

### Testing Notes

- Frontend tests use `vitest` + `@testing-library/react`
- Test baseline to maintain: **273 backend tests**, **184 frontend tests**
- Mock `EventSource` in `use-feed-sse.test.ts` to include `message` in `pipeline-progress` event data

### Project Structure Notes

- All frontend changes within `frontend/src/features/teaching-feed/` — no cross-feature impact
- Backend changes (if any) limited to `backend/app/tasks/processing_tasks.py`

### References

- [Source: frontend/src/features/teaching-feed/components/ProgressiveLoadingState.tsx#L5-9] — hardcoded PHASE_COPY to remove
- [Source: frontend/src/features/teaching-feed/hooks/use-feed-sse.ts#L45-51] — pipeline-progress listener to update
- [Source: frontend/src/features/teaching-feed/components/FeedContainer.tsx#L25,L108] — wiring to update
- [Source: backend/app/tasks/processing_tasks.py#L60-65] — backend already sends message field
- [Source: _bmad-output/implementation-artifacts/epic-3-retro-2026-04-07.md#Action Items] — Critical item #1

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- Pre-existing: FeedContainer.test.tsx was missing `next-intl` mock — all 10 existing tests were failing before this story. Fixed by adding `vi.mock("next-intl")` with project's `intl-mock` utility.
- Pre-existing: Backend `test_sse_streaming.py::test_happy_path_publishes_progress_events` expected 6 publish calls but pipeline emits 9 (5 progress + N insight-ready + 1 complete). Fixed by filtering calls by event type instead of hardcoding count.

### Completion Notes List

- ✅ Task 1: Added `message` state to `useFeedSSE` hook; extracts `data.message` from pipeline-progress events, clears on job-complete/job-failed
- ✅ Task 2: Removed `PHASE_COPY` dictionary from `ProgressiveLoadingState`; component now renders `message ?? "Processing..."` directly
- ✅ Task 3: Updated `FeedContainer` to destructure `message` from hook and pass to `ProgressiveLoadingState`; removed `phase` prop
- ✅ Task 4: Audited all 5 `publish_job_progress` calls with `pipeline-progress` event in `processing_tasks.py` — all include `message` field. No backend changes needed.
- ✅ Task 5: Added 5 new useFeedSSE tests (message set, message null fallback, cleared on job-complete, cleared on job-failed), rewrote 4 ProgressiveLoadingState tests for new interface, added 2 new FeedContainer tests (message passthrough, null fallback). Fixed pre-existing next-intl mock issue and backend SSE test assertion. All 188 frontend tests pass. All 273 backend tests pass.

### File List

- `frontend/src/features/teaching-feed/hooks/use-feed-sse.ts` — modified (added message state, extraction, clearing; removed dead phase state)
- `frontend/src/features/teaching-feed/components/ProgressiveLoadingState.tsx` — modified (removed PHASE_COPY, new message prop interface, i18n fallback via useTranslations)
- `frontend/src/features/teaching-feed/components/FeedContainer.tsx` — modified (pass message instead of phase)
- `frontend/src/features/teaching-feed/__tests__/use-feed-sse.test.ts` — modified (5 new message tests, removed dead phase test)
- `frontend/src/features/teaching-feed/__tests__/ProgressiveLoadingState.test.tsx` — modified (rewritten for message prop, added next-intl mock)
- `frontend/src/features/teaching-feed/__tests__/FeedContainer.test.tsx` — modified (3 new tests incl. inline streaming+cards, fixed next-intl mock, removed phase from mocks)
- `backend/tests/test_sse_streaming.py` — modified (fixed pre-existing assertion: filter calls by event type instead of hardcoded count)
- `frontend/messages/en.json` — modified (added feed.processing key)
- `frontend/messages/uk.json` — modified (added feed.processing key)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — modified (status: review → done)

## Change Log

- 2026-04-07: Decoupled SSE progress messages — frontend now displays backend-provided `message` field instead of hardcoded PHASE_COPY dictionary. Fixed pre-existing FeedContainer test mock issue and backend SSE test assertion.
- 2026-04-07: Code review fixes — removed dead `phase` state from useFeedSSE hook, added i18n fallback for ProgressiveLoadingState (en/uk), added missing inline streaming+cards test.
