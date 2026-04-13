# Story 6.1: User-Friendly Error Messages & Error States

Status: done

## Story

As a **user**,
I want to see friendly, helpful error messages when something goes wrong,
so that I'm not confused or alarmed by technical errors.

## Acceptance Criteria

1. **Given** any error occurs in the application **When** it is displayed to the user **Then** the message is user-friendly, actionable, and never exposes technical details (stack traces, error codes, internal paths)

2. **Given** a file format is not recognized **When** the system detects it **Then** the user sees a friendly message suggesting corrective actions (e.g., "We don't recognize this file format yet. Try exporting a CSV from your Monobank app")

3. **Given** the frontend encounters an API error **When** the error boundary catches it **Then** each feature area (Teaching Feed, Profile, Upload, Settings) has its own error boundary showing a lighthearted recovery message ("Our AI tripped over your spreadsheet — give it another try?")

4. **Given** error messages **When** they are displayed **Then** they are available in both Ukrainian and English via next-intl, and the tone is warm and humorous (not clinical or alarming)

## Tasks / Subtasks

- [x] Task 1: Create per-feature React Error Boundaries (AC: #3, #4)
  - [x] 1.1 Create reusable `FeatureErrorBoundary` component in `frontend/src/components/error/FeatureErrorBoundary.tsx`
  - [x] 1.2 Add error boundary around Teaching Feed (`/feed`) — currently only has Next.js `error.tsx`; wrap the feature component level too
  - [x] 1.3 Add error boundary around Profile (`/profile`)
  - [x] 1.4 Add error boundary around Upload (`/upload`)
  - [x] 1.5 Add error boundary around Settings (`/settings`)
  - [x] 1.6 Each boundary shows a feature-specific lighthearted recovery message with "Try again" button

- [x] Task 2: Add comprehensive i18n error message keys (AC: #1, #2, #4)
  - [x] 2.1 Audit existing error keys in `frontend/messages/en.json` and `uk.json` — extend with missing error scenarios
  - [x] 2.2 Add per-feature error boundary messages (warm, humorous tone) in both languages
  - [x] 2.3 Add unrecognized file format message with actionable suggestion
  - [x] 2.4 Add generic fallback error messages for uncaught scenarios
  - [x] 2.5 Ensure all existing raw error strings in components are replaced with i18n keys

- [x] Task 3: Implement global TanStack Query error handler (AC: #1)
  - [x] 3.1 Add `onError` default in `QueryClient` config at `frontend/src/lib/query/query-provider.tsx`
  - [x] 3.2 Intercept 401 errors globally to trigger session expiry flow (existing `SessionExpiredDialog`)
  - [x] 3.3 Intercept 429 errors globally to show rate-limit toast
  - [x] 3.4 Ensure 500 errors never surface raw backend messages — map to generic user-friendly message

- [x] Task 4: Backend error response hardening (AC: #1)
  - [x] 4.1 Add catch-all exception handler in `backend/app/main.py` for unhandled exceptions — return generic `{"error": {"code": "INTERNAL_ERROR", "message": "Something went wrong"}}` with 500 status, log full traceback server-side
  - [x] 4.2 Audit all API routes for any places that might leak stack traces or internal paths in error responses
  - [x] 4.3 Ensure Pydantic `RequestValidationError` handler returns user-friendly messages (not raw Pydantic output)

- [x] Task 5: Tests (all ACs)
  - [x] 5.1 Frontend: test each `FeatureErrorBoundary` renders correct i18n message and retry button
  - [x] 5.2 Frontend: test global query error handler behavior for 401, 429, 500
  - [x] 5.3 Backend: test catch-all exception handler returns sanitized response
  - [x] 5.4 Backend: test `RequestValidationError` handler returns friendly format

## Dev Notes

### Architecture Compliance

- **Error response format:** All backend errors MUST return `{"error": {"code": "ERROR_CODE", "message": "...", "details": {...}}}` — this is the established pattern in `backend/app/core/exceptions.py`
- **Never expose internals:** Rule #7 from architecture enforcement guidelines — never expose internal errors to frontend, map to user-friendly error codes
- **i18n required:** All user-facing strings via `next-intl` (`useTranslations` hook). Both `en.json` and `uk.json` must be updated in lockstep
- **TanStack Query for all data fetching:** Rule #8 — no raw `fetch` in components

### Existing Error Infrastructure (What Already Exists — Do NOT Reinvent)

**Backend (`backend/app/core/exceptions.py`):**
- `AuthenticationError` (401), `RegistrationError` (400), `ValidationError` (422), `ForbiddenError` (403) — all with consistent JSON error format
- Exception handlers registered in `backend/app/main.py` via `app.add_exception_handler()`
- **GAP:** No catch-all handler for unhandled `Exception` — this is what Task 4.1 adds

**Frontend error handling already in place:**
- `frontend/src/app/[locale]/(dashboard)/feed/error.tsx` — Next.js error page for feed (generic "Something went wrong" + retry)
- `frontend/src/features/upload/components/UploadDropzone.tsx` — comprehensive error display with `ERROR_KEY_MAP` mapping 11 error codes to i18n keys + suggestion maps
- `frontend/src/features/upload/hooks/use-upload.ts` — returns typed `UploadError` with `code`, `message`, `details`, `suggestions[]`
- `frontend/src/features/auth/components/SessionExpiredDialog.tsx` — session timeout dialog
- `frontend/src/lib/query/query-provider.tsx` — basic QueryClient config (`staleTime: 60s`, `retry: 1`), **no global error handler yet**

**Frontend i18n error keys already exist in `messages/en.json`:**
- `errors.rateLimited`, `errors.invalidCredentials`, `errors.serverError`, `errors.loginFailed`, `errors.signupFailed`, `errors.verificationFailed`
- `upload.errors.*` — 9 specific upload error codes
- `upload.suggestions.*` — 8+ suggestion messages
- `processing.errorMessage`, `processing.retry`
- `profile.loadError`, `feed.loadError`, `spending.loadError`, `spendingComparison.loadError`

### File Structure Requirements

**New files to create:**
- `frontend/src/components/error/FeatureErrorBoundary.tsx` — reusable error boundary component (class component required for React error boundaries)

**Files to modify:**
- `frontend/messages/en.json` — add new error boundary messages, missing error scenarios
- `frontend/messages/uk.json` — same keys, Ukrainian translations
- `frontend/src/lib/query/query-provider.tsx` — add global `onError` / `MutationCache` / `QueryCache` error defaults
- `frontend/src/app/[locale]/(dashboard)/feed/page.tsx` (or layout) — wrap with FeatureErrorBoundary
- `frontend/src/app/[locale]/(dashboard)/profile/page.tsx` (or layout) — wrap with FeatureErrorBoundary
- `frontend/src/app/[locale]/(dashboard)/upload/page.tsx` (or layout) — wrap with FeatureErrorBoundary
- `frontend/src/app/[locale]/(dashboard)/settings/page.tsx` (or layout) — wrap with FeatureErrorBoundary
- `backend/app/main.py` — add catch-all exception handler + RequestValidationError handler

### Library & Framework Requirements

- **React Error Boundaries** require class components (`componentDidCatch`/`getDerivedStateFromError`) — no hooks equivalent. Use a class component wrapper that accepts render props or children
- **next-intl:** Use `useTranslations('errors')` namespace for error messages
- **TanStack Query v5:** Global error handling via `QueryCache({ onError })` and `MutationCache({ onError })` in QueryClient constructor
- **shadcn/ui:** Use existing `Button` component for retry actions. Consider `Sonner` toast for non-blocking error notifications (already likely available or easily added via shadcn CLI)

### Previous Story Intelligence

**From Story 5.6 (Privacy & Consent Bugfix Post-Mortem):**
- Hydration errors can occur from button-inside-button nesting — be careful with error boundary trigger elements
- The `DataDeletion.tsx` fix used base-ui's `render` prop instead of `asChild` to avoid nested buttons
- Auth pages now have guards — error states should respect locale redirects
- Backend `MissingGreenlet` error from accessing expired SQLAlchemy objects after commit — error handlers should not access ORM objects after commits

### Git Intelligence

Recent commits (Epic 5) show:
- Consistent pattern of co-located tests in `frontend/src/features/*/\__tests__/`
- Backend tests in `backend/tests/` (flat structure, not mirroring `app/`)
- i18n messages updated in both `en.json` and `uk.json` simultaneously
- New UI components placed in `frontend/src/components/ui/` (shadcn pattern)
- Feature-specific components in `frontend/src/features/*/components/`

### Testing Requirements

- **Frontend tests:** Use the same pattern as `frontend/src/features/settings/__tests__/*.test.tsx` — Vitest + React Testing Library
- **Backend tests:** Use the same pattern as `backend/tests/test_*.py` — pytest with async test client
- **Error boundary tests:** Render a component that throws, verify error UI appears with correct i18n message and retry button
- **Global error handler tests:** Mock failed queries, verify toast/dialog behavior for 401/429/500

### References

- [Source: architecture.md#Error Handling] — Error handling patterns per layer
- [Source: architecture.md#Enforcement Guidelines] — Rules #7, #8 on error handling
- [Source: architecture.md#Structure Patterns] — Frontend/backend file organization
- [Source: architecture.md#API Response Formats] — `{"error": {"code": "...", "message": "...", "details": {...}}}`
- [Source: epics.md#Story 6.1] — Acceptance criteria and user story
- [Source: exceptions.py] — Existing custom exception classes
- [Source: query-provider.tsx] — Current TanStack Query config (gap: no global error handler)

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- Pre-existing flaky tests in LoginForm.test.tsx and SignupForm.test.tsx (auth form submission mocking) — unrelated to this story

### Completion Notes List

- Task 1: Created `FeatureErrorBoundary` using Next.js `unstable_catchError` from `next/error` (no class component needed). Wrapped feed, profile, upload, and settings pages. Updated existing `feed/error.tsx` to use i18n.
- Task 2: Added `errors.boundary.*` keys (feed, profile, upload, settings, retry) with warm/humorous tone in both EN and UK. Added `errors.generic`, `errors.rateLimitToast`, and `errors.fileFormatUnrecognized`. Audited existing components — no raw error strings found (existing code already uses i18n).
- Task 3: Refactored `QueryProvider` to use `QueryCache`/`MutationCache` with global `onError`. Handles 401 (signOut), 429 (toast), 500+ (toast). Parses HTTP status from error message pattern `HTTP XXX` used by existing hooks.
- Task 4: Added `unhandled_exception_handler` (catch-all for `Exception`) and `request_validation_error_handler` (for `RequestValidationError`) in `exceptions.py`. Registered both in `main.py`. Audited all API routes — all HTTPExceptions already use structured error format.
- Task 5: 7 frontend tests for FeatureErrorBoundary (all features + retry), 4 frontend tests for QueryProvider (401/429/500/404), 4 backend tests for error handlers. All pass.

### Change Log

- 2026-04-13: Implemented Story 6.1 — user-friendly error messages & error states
- 2026-04-13: Code review fixes — removed dead i18n key, fixed upload history error pattern for global handler compatibility, rewrote misleading backend test, added mutation error tests, added error logging to FeatureErrorBoundary, documented feed/error.tsx duplication

### File List

**New files:**
- frontend/src/components/error/FeatureErrorBoundary.tsx
- frontend/src/components/error/__tests__/FeatureErrorBoundary.test.tsx
- frontend/src/lib/query/__tests__/query-provider.test.tsx
- backend/tests/test_error_handlers.py

**Modified files:**
- frontend/messages/en.json
- frontend/messages/uk.json
- frontend/src/lib/query/query-provider.tsx
- frontend/src/app/[locale]/(dashboard)/feed/page.tsx
- frontend/src/app/[locale]/(dashboard)/feed/error.tsx
- frontend/src/app/[locale]/(dashboard)/profile/page.tsx
- frontend/src/app/[locale]/(dashboard)/upload/page.tsx
- frontend/src/app/[locale]/(dashboard)/settings/page.tsx
- frontend/src/features/upload/hooks/use-upload-history.ts
- backend/app/core/exceptions.py
- backend/app/main.py
