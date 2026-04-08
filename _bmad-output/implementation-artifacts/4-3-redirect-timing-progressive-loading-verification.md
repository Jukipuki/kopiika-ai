# Story 4.3: Redirect Timing & Progressive Loading State Verification

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->
<!-- Source: Epic 3 Retrospective — High Action Item #3 -->

## Story

As a **developer**,
I want to verify that the redirect to Teaching Feed and `ProgressiveLoadingState` activation work correctly,
so that users see accurate progress when the pipeline is running.

## Acceptance Criteria

1. **Given** a user triggers the pipeline (uploads a statement), **When** they are redirected to the Teaching Feed via `router.push('/feed?jobId=X')`, **Then** `ProgressiveLoadingState` activates and shows progress messages from the SSE stream.

2. **Given** the `isStreaming` flag in `useFeedSSE`, **When** traced through `FeedContainer`, **Then** the flag correctly reflects whether an SSE stream is active (`true` while pipeline runs, `false` when `job-complete` or `job-failed` received).

3. **Given** the pipeline completes and `job-complete` fires, **When** `ProgressiveLoadingState` is showing and cards become available, **Then** it transitions smoothly to the card display without a flash of empty state or jarring state change.

4. **Given** the `ProgressiveLoadingState` is displayed below the card stack (line 108 of `FeedContainer`), **When** new cards are streaming in AND existing cards are already loaded, **Then** it does not visually conflict with the card stack (no layout shift, clear visual separation).

5. **Given** the investigation reveals a bug or race condition, **When** the issue is identified, **Then** a fix is implemented with tests verifying the correct behavior.

## Tasks / Subtasks

- [x] Task 1: Trace and verify the redirect → SSE → progressive loading flow (AC: #1, #2)
  - [x] 1.1 Trace `UploadDropzone.tsx` redirect: confirm `router.push('/feed?jobId=X')` fires after `activeJobId` and `lastUploadResult` are set
  - [x] 1.2 Verify `FeedContainer` receives `jobId` from URL params and passes to `useFeedSSE`
  - [x] 1.3 Verify `useFeedSSE` connects EventSource with jobId and sets `isStreaming=true`
  - [x] 1.4 Verify `FeedContainer` line 34: `isStreaming && (!cards || cards.length === 0)` correctly shows `ProgressiveLoadingState`
  - [x] 1.5 Document findings — if flow works correctly, note it; if bug found, proceed to Task 3

- [x] Task 2: Verify transition from progressive loading to card display (AC: #3, #4)
  - [x] 2.1 Trace `job-complete` handler in `useFeedSSE`: sets `isStreaming=false`, invalidates `["teaching-feed"]` query
  - [x] 2.2 Verify race condition: after `isStreaming=false`, `cards` must be populated before the empty state renders — TanStack Query invalidation triggers refetch, but there's a brief window where `isStreaming=false` and `cards` may still be empty
  - [x] 2.3 If race condition exists: fix by either (a) invalidating query BEFORE setting `isStreaming=false`, or (b) adding a `wasStreaming` ref to prevent empty state flash during the refetch
  - [x] 2.4 Verify `ProgressiveLoadingState` at line 108 (below card stack) doesn't cause layout shift when it disappears

- [x] Task 3: Fix any identified issues (AC: #5)
  - [x] 3.1 If race condition found in Task 2.2: implement fix with appropriate state management
  - [x] 3.2 If layout shift found in Task 2.4: add smooth transition or min-height to prevent jump
  - [x] 3.3 If no bugs found: document "verified working" in completion notes

- [x] Task 4: Tests (AC: #1–#5)
  - [x] 4.1 Add/update `FeedContainer.test.tsx`: test that `ProgressiveLoadingState` shows when `isStreaming=true` and no cards
  - [x] 4.2 Add/update `FeedContainer.test.tsx`: test transition — when `isStreaming` goes `false` and cards arrive, `ProgressiveLoadingState` disappears and cards render
  - [x] 4.3 Add/update `FeedContainer.test.tsx`: test that `ProgressiveLoadingState` renders below card stack when `isStreaming=true` AND cards exist
  - [x] 4.4 Verify all existing 273 backend + 184 frontend tests continue to pass

## Dev Notes

### Scope Summary

**Investigation + potential fix story.** Primarily frontend. Trace the upload→redirect→SSE→progressive loading flow end-to-end and fix any issues found.

### Current State Analysis

**Redirect flow (verified by investigation):**
1. `UploadDropzone.tsx` (line 66-70): `useEffect` redirects to `/feed?jobId=X` when `activeJobId` and `lastUploadResult` are both set
2. `FeedContainer.tsx` (line 20): receives `jobId` as prop
3. `useFeedSSE` (line 39): sets `isStreaming=true` on EventSource connect
4. `FeedContainer.tsx` (line 34): shows `ProgressiveLoadingState` when `isStreaming && (!cards || cards.length === 0)`

**Potential race condition:**
In `useFeedSSE` `job-complete` handler (lines 65-71):
```typescript
setIsStreaming(false);      // Line 67
setPhase(null);             // Line 68
queryClient.invalidateQueries(...)  // Line 69
```
`isStreaming` becomes `false` before the query refetch completes. There's a brief window where `isStreaming=false` AND `cards.length === 0` — this would show the empty state ("No insights. Go to upload") for a frame before cards load.

**Second `ProgressiveLoadingState` instance:**
`FeedContainer.tsx` line 108: `{isStreaming && <ProgressiveLoadingState phase={phase} />}` renders below the card stack when streaming AND cards already exist. When streaming ends, this disappears — potential layout shift.

### Files to Investigate/Change

- `frontend/src/features/upload/components/UploadDropzone.tsx` — redirect trigger (lines 66-70)
- `frontend/src/features/teaching-feed/components/FeedContainer.tsx` — streaming state rendering (lines 34, 108)
- `frontend/src/features/teaching-feed/hooks/use-feed-sse.ts` — `job-complete` handler (lines 65-71)
- `frontend/src/features/teaching-feed/__tests__/FeedContainer.test.tsx` — add transition tests

### Architecture Compliance

- No API or backend changes expected
- Follows existing React state management patterns
- Any fix should preserve SSE reconnection behavior

### Previous Story Intelligence

From Story 3.7 (Progressive Card Appearance & SSE Integration): The redirect-before-completion was a deliberate design choice (review fix H3). Progressive loading was designed to bridge the gap. This story verifies that bridge works correctly.

From Story 3.9 (Infinite Pagination): `useInfiniteQuery` invalidation re-fetches all loaded pages. The race condition window may be slightly larger due to refetching multiple pages vs a single query.

### Testing Notes

- Frontend tests use `vitest` + `@testing-library/react`
- Test baseline: **273 backend tests**, **184 frontend tests**
- Key mock: `useFeedSSE` return value transitions (`isStreaming: true` → `false`) while `useTeachingFeed` returns cards

### Project Structure Notes

- All changes within `frontend/src/features/teaching-feed/` and `frontend/src/features/upload/`
- No cross-feature impact beyond the upload→feed redirect

### References

- [Source: frontend/src/features/upload/components/UploadDropzone.tsx#L66-70] — redirect trigger
- [Source: frontend/src/features/teaching-feed/hooks/use-feed-sse.ts#L65-71] — job-complete handler with potential race condition
- [Source: frontend/src/features/teaching-feed/components/FeedContainer.tsx#L34-35] — progressive loading gate
- [Source: frontend/src/features/teaching-feed/components/FeedContainer.tsx#L108] — streaming indicator below cards
- [Source: _bmad-output/implementation-artifacts/epic-3-retro-2026-04-07.md#Challenge 6] — redirect timing issue
- [Source: _bmad-output/implementation-artifacts/3-7-progressive-card-appearance-sse-integration.md] — original SSE integration (review fix H3)

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

None — no debugging required; issues were identified by static trace analysis.

### Completion Notes List

- ✅ Traced full redirect→SSE→progressive loading flow: all 4 steps verified correct (UploadDropzone → FeedPage searchParams → FeedContainer prop → useFeedSSE connect).
- 🐛 **Race condition found and fixed (AC #3, #5)**: `job-complete` handler in `useFeedSSE` sets `isStreaming=false` before `queryClient.invalidateQueries` refetch completes. In first-pipeline scenario (no cached cards), brief window shows empty state. Fixed by exposing `isFetching` from `useTeachingFeed` and adding a guard in `FeedContainer`: when `cards=[]` and `isFetching=true`, show skeleton instead of empty state.
- ⚠️ **Layout shift found and fixed (AC #4)**: `ProgressiveLoadingState` at line 108 (below card stack) disappears abruptly when streaming ends. Fixed with `AnimatePresence` + `motion.div exit={{ opacity: 0 }}` for a smooth 300ms fade-out.
- ✅ 3 new tests added to `FeedContainer.test.tsx`: transition test (4.2), race condition guard test, and inline streaming indicator with cards test (4.3 variant).
- ✅ All 193 frontend tests pass, all 273 backend tests pass — no regressions.

### Review Fixes Applied (Code Review 2026-04-08)

- 🔧 **[H1] Race condition guard scoped with `wasStreamingRef`**: `isFetching` guard was over-broad — any background refetch on an empty feed would flash skeletons. Added `wasStreamingRef` to track streaming→idle transitions so the guard only activates immediately after streaming ends.
- 🔧 **[M1] Transition test now tests actual state transition**: Rewrote test to start with `isStreaming: true` (ProgressiveLoadingState visible), then rerender with `isStreaming: false` + cards. Previously only tested final state.
- 🔧 **[M2] AnimatePresence test limitation documented**: Added comment noting exit animation cannot be verified in jsdom; test covers structural co-existence only.
- 🔧 **[M3] Skeleton JSX duplication extracted**: Created `SkeletonList` component to eliminate duplicate 7-line skeleton block.
- ℹ️ **[L1] Dev Notes `phase` → `message` stale reference**: Not fixed (documentation only, renamed in Story 4.1).
- ℹ️ **[L2] No `job-failed` FeedContainer test**: Not fixed (hook-level coverage exists; container test deferred).

### File List

- `frontend/src/features/teaching-feed/hooks/use-teaching-feed.ts` — added `isFetching` to return value
- `frontend/src/features/teaching-feed/components/FeedContainer.tsx` — added `wasStreamingRef` to scope race condition guard; extracted `SkeletonList` component; wrapped inline `ProgressiveLoadingState` in `AnimatePresence`/`motion.div` for smooth exit
- `frontend/src/features/teaching-feed/__tests__/FeedContainer.test.tsx` — rewrote transition + race condition tests to verify actual state transitions; documented AnimatePresence mock limitation

## Change Log

- 2026-04-08: Story 4.3 implemented — fixed race condition (empty-state flash after stream end) and layout shift (inline ProgressiveLoadingState fade-out). 3 new tests added.
- 2026-04-08: Code review fixes — scoped race condition guard with `wasStreamingRef` (H1), rewrote transition tests (M1), documented animation test limitation (M2), extracted `SkeletonList` (M3).
