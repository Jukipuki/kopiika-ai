# Story 1.6: Language Selection (Ukrainian & English)

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want to select my preferred language (Ukrainian or English),
So that I can use the application in my native language.

## Acceptance Criteria

1. **Given** I am on the registration or settings page, **When** I select Ukrainian or English as my preferred language, **Then** my preference is saved to my user profile

2. **Given** I have a language preference set, **When** I navigate the application, **Then** all UI text is displayed in my selected language using next-intl

3. **Given** I change my language preference in settings, **When** I save the change, **Then** the UI immediately switches to the new language without page reload

4. **Given** a new user has not set a language preference, **When** they first load the application, **Then** the language defaults to Ukrainian (primary market)

## Tasks / Subtasks

- [x] Task 1: Install & Configure next-intl (AC: #2, #4)
  - [x] 1.1 Install `next-intl` package: `npm install next-intl`
  - [x] 1.2 Create `frontend/src/i18n/routing.ts` — define supported locales (`uk`, `en`) and default locale (`uk`) using `defineRouting()`
  - [x] 1.3 Create `frontend/src/i18n/request.ts` — implement `getRequestConfig()` to load messages per locale. MUST return `locale` (required in next-intl v4 — without it, "Unable to find next-intl locale" error occurs)
  - [x] 1.4 Create `frontend/src/i18n/navigation.ts` — use `createNavigation()` with routing config to produce locale-aware `Link`, `redirect`, `usePathname`, `useRouter`
  - [x] 1.5 Update `frontend/next.config.ts` — wrap with `createNextIntlPlugin()` from `next-intl/plugin`, pointing to `./src/i18n/request.ts`
  - [x] 1.6 Update `frontend/src/proxy.ts` — integrate `createMiddleware` from `next-intl/middleware` with auth session check. Export function as `proxy` (NOT `middleware` — Next.js 16). Runtime is `nodejs` (NOT `edge`). Combine locale routing with existing auth protection logic
  - [x] 1.7 Update `frontend/src/app/layout.tsx` — change hardcoded `lang="en"` to dynamic `lang={locale}` from params. Wrap children with `NextIntlClientProvider` passing `messages` and `locale`
  - [x] 1.8 Add `generateStaticParams()` to `frontend/src/app/[locale]/layout.tsx` returning `[{locale: 'uk'}, {locale: 'en'}]` for static rendering support

- [x] Task 2: Create Translation Message Files (AC: #2)
  - [x] 2.1 Create `frontend/messages/uk.json` with all Ukrainian translations organized by namespace (auth, dashboard, common, settings, errors)
  - [x] 2.2 Create `frontend/messages/en.json` with all English translations using same key structure
  - [x] 2.3 Replace ALL hardcoded English strings in existing components with `useTranslations()` / `getTranslations()` calls:
    - `LoginForm.tsx` — "Email", "Password", "Forgot password?", "Sign In", "Don't have an account?", "Sign up", validation messages
    - `SignupForm.tsx` — "Create your account", "Verify your email", form labels, validation messages
    - `auth-guard.tsx` — loading skeleton aria labels
    - `(dashboard)/layout.tsx` — "Log out" button text, navigation labels
    - `SessionExpiredDialog.tsx` — dialog title, description, button text
    - `page.tsx` (root) — "Kopiika AI", status text
  - [x] 2.4 Use `useTranslations('namespace')` in Client Components and `getTranslations('namespace')` in Server Components (async)

- [x] Task 3: Create Language Selector Component (AC: #1, #3)
  - [x] 3.1 Create `frontend/src/components/layout/LocaleSwitcher.tsx` — a toggle/dropdown that switches between Ukrainian ("Українська") and English ("English"). Use shadcn/ui Select or DropdownMenu component (install if needed: `npx shadcn@latest add select`). Display current language name and flag emoji (🇺🇦/🇬🇧)
  - [x] 3.2 On language change: (a) call `PATCH /api/v1/auth/me` to persist preference to backend, (b) use next-intl's `useRouter().replace()` with new locale to switch URL, (c) show Sonner toast: "Preference saved" / "Налаштування збережено"
  - [x] 3.3 Add `LocaleSwitcher` to dashboard layout header — must be accessible from main interface (NOT buried deep in settings per UX spec). Place next to logout button in header area
  - [x] 3.4 For unauthenticated pages (login, signup): add a minimal locale toggle (just "UA | EN" text links) that switches URL locale without backend call. Place in top-right corner of auth layout
  - [x] 3.5 Ensure language switcher is keyboard navigable, has proper `aria-label`, and visible focus indicators (WCAG 2.1 AA)

- [x] Task 4: Backend — Language Preference Update Endpoint (AC: #1)
  - [x] 4.1 Add `PATCH /api/v1/auth/me` endpoint in `backend/app/api/v1/auth.py` — accepts `{"locale": "uk"}` or `{"locale": "en"}` in request body. Validates locale is one of `["uk", "en"]`. Updates `user.locale` in database. Returns updated `UserProfileResponse`. Requires authentication via `get_current_user` dependency
  - [x] 4.2 Create Pydantic schema `UpdateProfileRequest` with `locale: str` field, add `@field_validator('locale')` to ensure only `"uk"` or `"en"` are accepted. Use `alias_generator=to_camel` for API consistency
  - [x] 4.3 On successful update, set `user.updated_at = datetime.now(UTC)` (NOT deprecated `utcnow()`)

- [x] Task 5: Fix Hardcoded Locale References (AC: #2, #4)
  - [x] 5.1 Update `frontend/src/lib/auth/next-auth-config.ts` — change hardcoded `signIn: "/en/login"` to dynamic locale-based URL. Expose `locale` in session callback so components can access `session.user.locale`
  - [x] 5.2 Update all locale fallbacks from `|| "en"` to `|| "uk"` (Ukrainian is default per AC#4):
    - `frontend/src/app/[locale]/(auth)/login/page.tsx` line 10
    - `frontend/src/app/[locale]/(auth)/signup/page.tsx` line 11
    - `frontend/src/app/[locale]/(dashboard)/layout.tsx` line 19
    - `frontend/src/proxy.ts` line 15
  - [x] 5.3 Ensure root redirect: when user visits `/` (no locale prefix), next-intl middleware redirects to `/uk/` (default locale)

- [x] Task 6: Locale-Aware Formatting Utilities (AC: #2)
  - [x] 6.1 Create `frontend/src/lib/format/currency.ts` — format UAH amounts per locale: Ukrainian `12 450,00 ₴` (space thousands, comma decimal, ₴ suffix) vs English `₴12,450.00` (standard). Use `Intl.NumberFormat` with locale parameter
  - [x] 6.2 Create `frontend/src/lib/format/date.ts` — format dates per locale: Ukrainian `16.03.2026 14:30` / `14 лютого 2026` vs English `03/16/2026 2:30 PM` / `February 14, 2026`. Use `Intl.DateTimeFormat` with locale parameter
  - [x] 6.3 These are utility files for future stories (Epic 2+). No UI integration needed yet, but create them now to establish the pattern

- [x] Task 7: Backend Tests (AC: #1, #4)
  - [x] 7.1 Test `PATCH /api/v1/auth/me` with valid locale `"uk"` → 200, user.locale updated
  - [x] 7.2 Test `PATCH /api/v1/auth/me` with valid locale `"en"` → 200, user.locale updated
  - [x] 7.3 Test `PATCH /api/v1/auth/me` with invalid locale `"fr"` → 422 validation error
  - [x] 7.4 Test `PATCH /api/v1/auth/me` without authentication → 401
  - [x] 7.5 Test `GET /api/v1/auth/me` returns locale field in response
  - [x] 7.6 Test default locale is `"uk"` for new users (verify User model default)
  - [x] 7.7 All existing backend tests from stories 1.1-1.5 MUST continue to pass (regression check)

- [x] Task 8: Frontend Tests (AC: #1, #2, #3)
  - [x] 8.1 Test `LocaleSwitcher` renders current language and switches locale on selection
  - [x] 8.2 Test `LocaleSwitcher` calls PATCH endpoint to persist language change
  - [x] 8.3 Test `LocaleSwitcher` shows toast confirmation on successful change
  - [x] 8.4 Test translated strings render correctly for both `uk` and `en` locales (at least LoginForm)
  - [x] 8.5 Test auth layout locale toggle works without backend call (unauthenticated context)
  - [x] 8.6 Test currency formatting utility: Ukrainian vs English format
  - [x] 8.7 Test date formatting utility: Ukrainian vs English format
  - [x] 8.8 All existing frontend tests from stories 1.1-1.5 MUST continue to pass (regression check)

## Dev Notes

### Critical Architecture Decisions

- **next-intl v4.8.x is the i18n framework** — per architecture spec. It provides Server Component support, sub-pathname routing (`/uk/...`, `/en/...`), and ~2KB bundle size. Do NOT use `react-intl`, `i18next`, or `react-i18next`.
- **proxy.ts runtime is Node.js, NOT Edge** — Next.js 16 changed `middleware.ts` → `proxy.ts` with `proxy()` function. The proxy runtime is `nodejs` and cannot be configured to `edge`. This is a breaking change from Next.js 15.
- **Ukrainian is the DEFAULT locale** — the primary market is Ukraine (9.88M+ Monobank users). Default to `"uk"`, not `"en"`. The User model already has `locale: str = Field(default="uk")`.
- **Language toggle accessible from main interface** — UX spec explicitly states: "Not buried in settings — accessible from the main interface." Place LocaleSwitcher in the dashboard header alongside logout button. Additionally provide a minimal locale toggle on auth pages.
- **Auto-save, no "Save" button** — UX spec: "Changes save automatically (no 'Save' button needed). Sonner toast confirms: 'Preference saved'". Language change should trigger immediate backend save + UI switch.
- **DM Sans font with Cyrillic support** — UX spec specifies DM Sans for its "excellent Cyrillic support — Ukrainian characters (і, ї, є, ґ) render cleanly." Load via `next/font` from Google Fonts.
- **Authentic localization, not just translation** — Financial terminology, cultural framing, number formatting (comma decimals, space thousands separators, ₴ suffix) require careful Ukrainian localization. "Making your money work harder" vs Ukrainian-native framing.

### Technical Requirements

- **next-intl setup files**: `routing.ts` (defineRouting), `request.ts` (getRequestConfig — MUST return locale), `navigation.ts` (createNavigation). Messages in `frontend/messages/{locale}.json`.
- **proxy.ts integration**: Combine `createMiddleware` from `next-intl/middleware` with existing NextAuth `auth()` session check. Auth protection runs AFTER locale routing. Matcher must exclude `_next/static`, `_next/image`, `favicon.ico`.
- **Message file structure**: Organize by namespace — `auth.*`, `dashboard.*`, `common.*`, `settings.*`, `errors.*`. Keep flat within namespaces (no deep nesting). Both `uk.json` and `en.json` MUST have identical key structures.
- **PATCH endpoint pattern**: Follow existing auth endpoint patterns — validate input → update DB → return response. Use `get_current_user` dependency for auth + user loading. Update `user.updated_at` on every change.
- **Pydantic camelCase**: API accepts/returns `{"locale": "uk"}` — the `locale` field is already camelCase-compatible. Use `alias_generator=to_camel` on the request schema for consistency.
- **next-intl v4 requirement**: `getRequestConfig()` in `request.ts` MUST return `locale` property. Without it, you get "Unable to find next-intl locale" error even if routing works.

### Architecture Compliance

- **API prefix**: `/api/v1/` — PATCH endpoint at `/api/v1/auth/me`
- **Response format**: Success → `UserProfileResponse` with `locale` field. Error → `{"error": {"code": "VALIDATION_ERROR", "message": "...", "details": {...}}}`
- **JSON field naming**: `camelCase` via Pydantic `alias_generator=to_camel` (established in Story 1.3)
- **HTTP status codes**: 200 (successful update), 401 (not authenticated), 422 (invalid locale value)
- **Dependency injection**: Use existing `get_current_user` from `api/deps.py` — returns full User object for update
- **Database naming**: `snake_case` — `locale` column already exists in users table with `server_default='uk'`
- **Locale codes**: ISO 639-1 — `"uk"` (Ukrainian), `"en"` (English). NOT `"ua"` for Ukrainian.

### Library & Framework Requirements

| Library | Version | Purpose | Notes |
|---|---|---|---|
| `next-intl` | v4.8.x | Frontend i18n framework | **NEW — install via `npm install next-intl`** |
| `next/font` | (built-in) | DM Sans font loading | Use `next/font/google` for DM Sans with Cyrillic subset |
| `@shadcn/ui` Select | latest | Language selector dropdown | Install via `npx shadcn@latest add select` if not present |
| `sonner` | latest | Toast notifications | Already installed. Use for "Preference saved" confirmation |
| `next-auth` | `@beta` (5.0.0-beta.30) | Session + locale in JWT | Already installed. Expose locale in session callback |
| `sqlmodel` | latest | ORM for User model | Already installed. `locale` field already on User model |

**Do NOT use:** `react-intl` (heavier, less Next.js integration), `i18next`/`react-i18next` (different paradigm, not recommended for App Router), `next-translate` (less maintained)

### File Structure Requirements

**New files to create:**

```
frontend/
├── messages/
│   ├── uk.json                                  # CREATE — Ukrainian translations
│   └── en.json                                  # CREATE — English translations
├── src/
│   ├── i18n/
│   │   ├── routing.ts                           # CREATE — defineRouting() config
│   │   ├── request.ts                           # CREATE — getRequestConfig() for Server Components
│   │   └── navigation.ts                        # CREATE — createNavigation() wrappers
│   ├── components/layout/
│   │   └── LocaleSwitcher.tsx                    # CREATE — Language toggle component
│   └── lib/format/
│       ├── currency.ts                          # CREATE — Locale-aware currency formatting
│       └── date.ts                              # CREATE — Locale-aware date formatting
```

**Files to modify:**

```
frontend/
├── next.config.ts                               # MODIFY — Wrap with createNextIntlPlugin
├── src/
│   ├── proxy.ts                                 # MODIFY — Integrate next-intl middleware
│   ├── app/layout.tsx                           # MODIFY — Dynamic lang attr, NextIntlClientProvider
│   ├── app/[locale]/(auth)/layout.tsx           # MODIFY — Add minimal locale toggle
│   ├── app/[locale]/(auth)/login/page.tsx       # MODIFY — Use translations, fix default to "uk"
│   ├── app/[locale]/(auth)/signup/page.tsx      # MODIFY — Use translations, fix default to "uk"
│   ├── app/[locale]/(dashboard)/layout.tsx      # MODIFY — Add LocaleSwitcher, use translations
│   ├── features/auth/components/LoginForm.tsx   # MODIFY — Replace hardcoded strings with t()
│   ├── features/auth/components/SignupForm.tsx  # MODIFY — Replace hardcoded strings with t()
│   ├── features/auth/components/SessionExpiredDialog.tsx # MODIFY — Translate dialog text
│   ├── lib/auth/auth-guard.tsx                  # MODIFY — Translate aria labels
│   └── lib/auth/next-auth-config.ts             # MODIFY — Dynamic signIn URL, expose locale in session

backend/
├── app/api/v1/auth.py                           # MODIFY — Add PATCH /api/v1/auth/me endpoint
```

**Existing files to reuse (DO NOT recreate):**
- `backend/app/models/user.py` — User model with `locale` field already defined (default "uk")
- `backend/app/api/deps.py` — `get_current_user()`, `get_db()` dependencies
- `backend/app/core/exceptions.py` — AuthenticationError, ForbiddenError (reuse patterns)
- `backend/app/core/tenant.py` — User-scoped query utilities (if needed)
- `frontend/src/lib/auth/auth-guard.tsx` — AuthGuard component (modify, don't recreate)
- `frontend/src/lib/auth/next-auth-config.ts` — NextAuth config (modify, don't recreate)

### Testing Requirements

**Backend tests** (pytest + httpx AsyncClient):
- Mirror existing `tests/conftest.py` fixtures: async SQLite engine, mock Cognito service, HTTP client
- Test PATCH endpoint: valid locale update, invalid locale rejection, unauthenticated access
- Test User model default locale is "uk"
- All existing 25+ backend tests from stories 1.1-1.5 MUST continue to pass

**Frontend tests** (Vitest + React Testing Library):
- Mirror existing test patterns from `LoginForm.test.tsx` and `AuthGuard.test.tsx`
- Mock `next-intl` hooks (`useTranslations`, `useLocale`) for component tests
- Test LocaleSwitcher: renders, switches locale, calls API, shows toast
- Test translated content renders in both locales
- Test formatting utilities (currency, date) for both locales
- All existing 23+ frontend tests from stories 1.1-1.5 MUST continue to pass

### Previous Story Intelligence (from Story 1.5)

**Critical patterns established — FOLLOW these:**
- `proxy.ts` uses `auth()` from NextAuth for server-side session check. Combine next-intl `createMiddleware` with this existing auth logic — do NOT break auth protection
- `entrypoint.sh` runs `alembic upgrade head` before app startup — no new migration needed (locale column already exists)
- `core/logging.py` provides JSON structured logging — use for any new backend operations
- Alembic migration already includes `locale` column: `sa.Column('locale', ..., server_default='uk')` — no database migration needed
- Frontend test patterns: mock `useSession()` from NextAuth, use `render()` + `screen` from Testing Library
- Backend test patterns: async SQLite in-memory DB, `AsyncClient` for API tests, mock Cognito service

**Critical bugs fixed in 1.4-1.5 — DO NOT reintroduce:**
- Replaced hardcoded `/en/` locale with dynamic locale extraction in auth redirects — Story 1.6 must complete this fix by making all locale references dynamic
- `SessionExpiredDialog` must auto-logout (no "Continue session" option)
- IP extraction must check `X-Forwarded-For` before `request.client` fallback
- `user.updated_at = datetime.now(UTC)` — not deprecated `utcnow()`

**Dependencies already installed — do NOT reinstall:**
- Backend: boto3, python-jose[cryptography], pydantic[email], httpx, pytest-asyncio, aiosqlite, sqlmodel, asyncpg, alembic
- Frontend: next-auth@beta, @auth/core, react-hook-form, @hookform/resolvers, zod, vitest, @testing-library/*, sonner

**Spec deviations from 1.5 to be aware of:**
- `next-intl` was claimed "Already installed" in 1.5 dev notes but is NOT in `package.json` — must install now
- `shadcn/ui` is NOT configured — if LocaleSwitcher needs shadcn Select component, must install shadcn first or use native HTML select with Tailwind styling

### Git Intelligence

**Recent commits:**
- `490f150` Story 1.4: User Login, Logout & Session Management
- `3ded222` Story 1.3: AWS Cognito Integration & User Registration
- `a6c15bc` Story 1.2: AWS Infrastructure Provisioning
- `720d284` Initial commit

**Code conventions from recent work:**
- Commit message format: `Story X.Y: Description`
- Python: Ruff for linting, async/await everywhere, type hints on all functions
- TypeScript: `"use client"` directive for interactive components, strict mode
- Tests: co-located for frontend (`__tests__/`), separate `tests/` for backend
- i18n comments exist in `signup/page.tsx`: `/* i18n: auth.signup.title */` — use these as hints for translation keys

### Latest Technical Information

- **next-intl v4 + Next.js 16**: `middleware.ts` renamed to `proxy.ts`, function `middleware()` → `proxy()`. Runtime is `nodejs` (NOT `edge` — edge is no longer supported in proxy). Configuration flags renamed: `skipMiddlewareUrlNormalize` → `skipProxyUrlNormalize`.
- **next-intl v4 critical requirement**: `getRequestConfig()` in `request.ts` MUST return `locale`. Without it, you get "Unable to find next-intl locale" error even if routing works correctly.
- **next-intl setup chain**: `routing.ts` (defineRouting) → `request.ts` (getRequestConfig) → `navigation.ts` (createNavigation) → `proxy.ts` (createMiddleware) → `next.config.ts` (createNextIntlPlugin). All 5 files must be configured correctly.
- **createNextIntlPlugin**: Import from `next-intl/plugin`. Usage: `const withNextIntl = createNextIntlPlugin('./src/i18n/request.ts'); export default withNextIntl(nextConfig);`
- **Message files location**: `frontend/messages/` (at project root, not inside `src/`) is the default convention. Can be customized in `request.ts`.
- **DM Sans Google Font**: Load via `import { DM_Sans } from 'next/font/google'` with `subsets: ['latin', 'cyrillic']` for Ukrainian support.

### Project Structure Notes

- Alignment with unified project structure: `i18n/` folder follows architecture spec (`frontend/src/i18n/`), `messages/` at frontend root per next-intl convention
- `LocaleSwitcher.tsx` goes in `frontend/src/components/layout/` per architecture spec (alongside future Header.tsx, Sidebar.tsx)
- Format utilities go in `frontend/src/lib/format/` per architecture spec
- No new backend directories needed — PATCH endpoint added to existing `auth.py`

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 1, Story 1.6]
- [Source: _bmad-output/planning-artifacts/architecture.md — Internationalization, Frontend Architecture, Database Schema, API Patterns]
- [Source: _bmad-output/planning-artifacts/prd.md — FR29 (Language Selection), FR11 (Bilingual Content), Bilingual UI Requirements]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md — Language Switching UX, DM Sans Typography, Currency/Date Formatting, Settings Patterns]
- [Source: _bmad-output/implementation-artifacts/1-5-protected-routes-tenant-isolation.md — Previous story patterns, proxy.ts, tenant isolation, Alembic migration]
- [Source: backend/app/models/user.py — User model with locale field (default "uk")]
- [Source: backend/alembic/versions/feb18f356210_create_user_table.py — Migration includes locale column]
- [Source: frontend/src/proxy.ts — Existing auth protection logic to integrate with next-intl]
- [Source: frontend/src/lib/auth/next-auth-config.ts — Hardcoded signIn URL, locale in JWT]
- [Source: next-intl.dev/docs/getting-started/app-router — Official setup guide]
- [Source: nextjs.org/docs/app/api-reference/file-conventions/proxy — Next.js 16 proxy.ts docs]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (claude-opus-4-6)

### Debug Log References

- DM Sans font does NOT have `cyrillic` subset — only `latin` and `latin-ext` per next/font type definitions. Changed to `subsets: ["latin", "latin-ext"]`.
- `python` command not available on this system — use `.venv/bin/python` from backend virtual environment.
- next-intl ICU plural format in mock: simple regex replacement `{key[^}]*}` handles basic interpolation but doesn't fully parse ICU plurals. Sufficient for test assertions using regex matchers.

### Completion Notes List

- All 8 tasks completed successfully
- 47 frontend tests passing (8 test files), 45 backend tests passing
- next-intl v4 integrated with Next.js 16 proxy.ts (not middleware.ts)
- Ukrainian (uk) set as default locale throughout
- shadcn/ui not configured — built LocaleSwitcher as custom Tailwind button instead of shadcn Select
- NextAuth `pages.signIn` requires a static string — cannot be dynamic per locale. Set to `/uk/login` (default locale). The proxy.ts handles locale-aware auth redirects before this fallback is reached
- Created shared test helper `test-utils/intl-mock.ts` for mocking next-intl in vitest tests

### Change Log

- Task 1: Installed next-intl, created i18n/routing.ts, i18n/request.ts, i18n/navigation.ts, updated next.config.ts, proxy.ts, layout.tsx, [locale]/layout.tsx
- Task 2: Created messages/uk.json, messages/en.json, replaced all hardcoded strings with useTranslations() in LoginForm, SignupForm, VerificationForm, SessionExpiredDialog, AuthGuard, login page, signup page
- Task 3: Created LocaleSwitcher.tsx with PATCH API call + router.replace. Added to dashboard layout header. Added AuthLocaleToggle to auth layout
- Task 4: Added PATCH /api/v1/auth/me endpoint with UpdateProfileRequest schema and field_validator
- Task 5: Fixed hardcoded /en/ references to dynamic locale, changed default from "en" to "uk" in next-auth-config, auth-guard, pages
- Task 6: Created lib/format/currency.ts and lib/format/date.ts with Intl.NumberFormat/DateTimeFormat
- Task 7: Added 6 backend tests for PATCH /me and locale behavior (45 total passing)
- Task 8: Added next-intl mocks to LoginForm, SignupForm, AuthGuard, proxy tests. Created new tests for LocaleSwitcher, AuthLayout toggle, currency, date formatting (47 total passing)
- Code review fixes: Fixed hardcoded /uk/dashboard callbackUrl in LoginForm (uses useLocale()); replaced plain `<a>` forgot-password link with next-intl Link; made LocaleSwitcher toast conditional on PATCH success; replaced manual locale extraction with useLocale() in DashboardLayout and AuthGuard; switched VerificationForm to next-intl router; added runtime="nodejs" to proxy.ts; strengthened currency/date test assertions; documented NextAuth signIn static URL limitation

### File List

**Deleted files:**
- `frontend/src/i18n/.gitkeep` — Removed (replaced by actual i18n source files)

**New files created:**
- `frontend/messages/uk.json` — Ukrainian translations
- `frontend/messages/en.json` — English translations
- `frontend/src/i18n/routing.ts` — next-intl routing config (locales: uk, en)
- `frontend/src/i18n/request.ts` — next-intl server request config
- `frontend/src/i18n/navigation.ts` — locale-aware navigation utilities
- `frontend/src/components/layout/LocaleSwitcher.tsx` — language toggle component
- `frontend/src/lib/format/currency.ts` — locale-aware currency formatting
- `frontend/src/lib/format/date.ts` — locale-aware date formatting
- `frontend/src/test-utils/intl-mock.ts` — shared next-intl test mock helper
- `frontend/src/components/layout/__tests__/LocaleSwitcher.test.tsx` — LocaleSwitcher tests
- `frontend/src/app/[locale]/(auth)/__tests__/AuthLayout.test.tsx` — auth layout locale toggle tests
- `frontend/src/lib/format/__tests__/currency.test.ts` — currency formatting tests
- `frontend/src/lib/format/__tests__/date.test.ts` — date formatting tests

**Modified files:**
- `frontend/package.json` — added next-intl dependency
- `frontend/package-lock.json` — lockfile updated for next-intl
- `frontend/next.config.ts` — wrapped with createNextIntlPlugin
- `frontend/src/proxy.ts` — integrated next-intl middleware with auth
- `frontend/src/app/layout.tsx` — dynamic lang attr, NextIntlClientProvider
- `frontend/src/app/[locale]/layout.tsx` — added generateStaticParams
- `frontend/src/app/[locale]/(auth)/layout.tsx` — added AuthLocaleToggle
- `frontend/src/app/[locale]/(auth)/login/page.tsx` — useTranslations, next-intl Link
- `frontend/src/app/[locale]/(auth)/signup/page.tsx` — useTranslations, next-intl Link
- `frontend/src/app/[locale]/(dashboard)/layout.tsx` — added LocaleSwitcher, useTranslations
- `frontend/src/features/auth/components/LoginForm.tsx` — translated all strings
- `frontend/src/features/auth/components/SignupForm.tsx` — translated all strings
- `frontend/src/features/auth/components/VerificationForm.tsx` — translated all strings
- `frontend/src/features/auth/components/SessionExpiredDialog.tsx` — translated dialog text
- `frontend/src/lib/auth/auth-guard.tsx` — translated aria labels, default locale to "uk"
- `frontend/src/lib/auth/next-auth-config.ts` — signIn URL to /uk/login, locale in session
- `frontend/src/types/next-auth.d.ts` — added locale to Session type
- `backend/app/api/v1/auth.py` — added PATCH /me endpoint with UpdateProfileRequest
- `backend/tests/test_auth.py` — added 6 locale-related tests
- `frontend/src/features/auth/__tests__/LoginForm.test.tsx` — added next-intl mock, fixed redirect URL
- `frontend/src/features/auth/__tests__/SignupForm.test.tsx` — added next-intl mock
- `frontend/src/features/auth/__tests__/AuthGuard.test.tsx` — added next-intl mock
- `frontend/src/features/auth/__tests__/proxy.test.ts` — added next-intl/middleware mock, updated assertions
