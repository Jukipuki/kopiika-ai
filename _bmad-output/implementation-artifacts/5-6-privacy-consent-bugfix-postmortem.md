Story 5.6: Privacy & Consent Bugfix Post-Mortem

## Summary

Manual testing of Epic 5 privacy/consent features uncovered several bugs across
backend, frontend, and the ingestion pipeline. All were fixed in a single session.

## Fixes

### 1. POST /api/v1/users/me/consent — 500 Internal Server Error

**File:** `backend/app/api/v1/consent.py`
**Root cause:** After `grant_consent()` committed the session, the `current_user`
SQLAlchemy object became expired. Accessing `current_user.id` in the logger
triggered a lazy reload outside an async greenlet context, raising
`MissingGreenlet`.
**Fix:** Changed `str(current_user.id)` to `str(record.user_id)` in the log
statement — the record is freshly returned and already loaded.
**Side note:** The consent *was* persisted before the logging error, so re-login
correctly showed consent as already granted.

### 2. Button-inside-button hydration error (DataDeletion)

**File:** `frontend/src/features/settings/components/DataDeletion.tsx`
**Root cause:** `AlertDialogTrigger` with `asChild` rendered its own `<button>`,
and the child `<Button>` component also rendered a `<button>` — nested buttons
are invalid HTML and cause React hydration errors.
**Fix:** Replaced `asChild` pattern with base-ui's `render` prop on
`AlertDialogTrigger`, so only one `<button>` element is rendered.

### 3. Authenticated users can access login/signup pages

**Files:** `frontend/src/app/[locale]/(auth)/login/page.tsx`,
`frontend/src/app/[locale]/(auth)/signup/page.tsx`
**Root cause:** Auth pages had no guard to redirect authenticated users away.
Manually navigating to `/en/login` while logged in showed the login form.
**Fix:** Added `useAuth()` check — if authenticated, redirect to
`/${locale}/dashboard`.

### 4. New users get `locale: "uk"` regardless of registration locale

**Files:** `backend/app/api/v1/auth.py`,
`frontend/src/features/auth/components/SignupForm.tsx`
**Root cause:** `SignupRequest` had no `locale` field; `User` model defaults to
`locale="uk"`. A user registering on `en/` got `uk` stored in the DB.
**Fix:** Added optional `locale` field to `SignupRequest` (defaults to `"uk"`,
validated to `"uk"|"en"`). Frontend now sends the current URL locale in the
signup request body.

### 5. Login redirect ignores user's stored locale

**File:** `frontend/src/features/auth/components/LoginForm.tsx`
**Root cause:** After login, `router.push(callbackUrl)` used the URL locale
(e.g. `en`) instead of the user's backend locale (e.g. `uk`). The settings page
also appeared to show the wrong locale because it read from the URL, not the
backend.
**Fix:** After login, extract `loginData.user.locale` and redirect to the
user's stored locale. Uses `window.location.href` when locale differs to ensure
full locale context switch.

### 6. English Monobank CSV exports not detected / parsed incorrectly

**Files:** `backend/app/services/format_detector.py`,
`backend/app/agents/ingestion/parsers/monobank.py`
**Root cause:** Monobank fingerprints and parser header mappings only contained
Ukrainian strings. English exports (e.g. `"Date and time"`,
`"Card currency amount, (UAH)"`) were not recognized as Monobank, fell through
to the generic parser, where `"Card currency amount, (UAH)"` matched both
"amount" and "currency" keyword heuristics — causing the amount value (`-525.0`)
to be treated as a currency string.
**Fix:** Added English fingerprints to `MONOBANK_FINGERPRINTS`
(`"card currency amount"`, `"cashback amount"`) and English header variants to
the Monobank parser's `HEADER_MAPPINGS`.

## Files Changed

- `backend/app/api/v1/consent.py`
- `backend/app/api/v1/auth.py`
- `backend/app/services/format_detector.py`
- `backend/app/agents/ingestion/parsers/monobank.py`
- `frontend/src/features/settings/components/DataDeletion.tsx`
- `frontend/src/features/auth/components/LoginForm.tsx`
- `frontend/src/features/auth/components/SignupForm.tsx`
- `frontend/src/app/[locale]/(auth)/login/page.tsx`
- `frontend/src/app/[locale]/(auth)/signup/page.tsx`

## Code Review Fixes (2026-04-13)

Fixes applied during adversarial code review:

1. **LoginForm.tsx** — Added missing `locale` to `useCallback` dependency array (stale closure bug)
2. **LoginForm.tsx** — Fixed open redirect via `callbackUrl` query param; now validates it starts with `/` and rejects `//` protocol-relative URLs
3. **auth.py** — Made `SignupRequest.validate_locale` raise `ValueError` (422) for invalid locales, consistent with `UpdateProfileRequest`
4. **format_detector.py** — Restructured `MONOBANK_FINGERPRINTS` into language-grouped `MONOBANK_FINGERPRINT_GROUPS` so each export only needs to match one language group, preventing fragile threshold math
5. **login/page.tsx, signup/page.tsx** — Replaced `return null` with loading indicator during auth check to prevent content flash
6. **test_auth.py** — Added 3 tests for signup locale (en, default, invalid)
7. **test_format_detection.py** — Added English Monobank CSV detection test
8. **test_monobank_parser.py** — Added 5 tests for English Monobank parser (fields, amounts, descriptions, MCC, balance)
9. **fixtures/monobank_english.csv** — New test fixture for English Monobank exports
