# Story 1.7: Account Settings Page

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want to view and manage my account settings,
So that I can control my profile and preferences.

## Acceptance Criteria

1. **Given** I am authenticated, **When** I navigate to the settings page, **Then** I see my email address, preferred language, and account creation date displayed clearly

2. **Given** I am on the settings page, **When** I change my language preference and save, **Then** the change is persisted to the backend via `PATCH /api/v1/auth/me` and the UI switches to the selected language immediately

3. **Given** I am on the settings page, **When** I view it on mobile (< 768px width), **Then** the layout is responsive, touch-optimized (44px+ touch targets), and all controls are thumb-reachable

4. **Given** the settings page is rendered, **When** I inspect the UI, **Then** all components use shadcn/ui primitives with proper WCAG 2.1 AA compliance (4.5:1 contrast, visible focus indicators, keyboard navigation, screen reader support)

## Tasks / Subtasks

- [x] Task 1: Initialize shadcn/ui in the Frontend Project (AC: #4)
  - [x] 1.1 Run `npx shadcn@latest init` in `frontend/` — select default style, confirm Tailwind v4 + App Router detection. This creates `components.json` and configures the `components/ui/` path
  - [x] 1.2 Install required shadcn/ui components: `npx shadcn@latest add card separator select button skeleton` — these are copied into `frontend/src/components/ui/`
  - [x] 1.3 Verify shadcn/ui components render correctly with existing Tailwind v4 CSS variables in `globals.css`. If shadcn init overwrites CSS variables, merge them — preserve existing `--background`, `--foreground` values and add shadcn's theme tokens
  - [x] 1.4 Ensure `globals.css` has both dark and light mode CSS variable sets compatible with shadcn/ui theming (dark mode uses `prefers-color-scheme` or class-based toggle)

- [x] Task 2: Create Settings Page Route & Layout (AC: #1, #3)
  - [x] 2.1 Create `frontend/src/app/[locale]/(dashboard)/settings/page.tsx` — Server Component that imports and renders `<SettingsPage />` client component. Add `generateMetadata()` returning translated page title
  - [x] 2.2 Add "Settings" navigation link to `frontend/src/app/[locale]/(dashboard)/layout.tsx` — link to `/{locale}/settings` using next-intl's `Link` component. Place alongside existing header items. Add a gear/cog icon (use inline SVG or lucide-react if already available)
  - [x] 2.3 Add translation keys `dashboard.settings` to both `messages/uk.json` ("Налаштування") and `messages/en.json` ("Settings") for the nav link label

- [x] Task 3: Create Settings Feature Module (AC: #1, #2)
  - [x] 3.1 Create `frontend/src/features/settings/components/SettingsPage.tsx` — `"use client"` component that fetches user profile via `GET /api/v1/auth/me` and displays settings sections. Uses `useSession()` to get `accessToken` for API call. Show loading skeleton while data loads
  - [x] 3.2 Create `frontend/src/features/settings/components/AccountInfoSection.tsx` — read-only display section showing: user email (from API response `email` field), account creation date (from `createdAt` field, formatted via `lib/format/date.ts` using current locale), email verification status (from `isVerified` field). Use shadcn/ui `Card` + `Separator` components
  - [x] 3.3 Create `frontend/src/features/settings/components/LanguageSection.tsx` — language preference section with shadcn/ui `Select` component showing current locale. On change: call `PATCH /api/v1/auth/me` with `{ locale: newLocale }`, then use next-intl `useRouter().replace()` to switch URL locale. Show sonner toast on success: `t('settings.preferenceSaved')`. Follow the same API call pattern as `LocaleSwitcher.tsx`
  - [x] 3.4 Create `frontend/src/features/settings/hooks/use-user-profile.ts` — custom hook that fetches `GET /api/v1/auth/me` with Bearer token from session. Returns `{ profile, isLoading, error, refetch }`. Use native `fetch()` + `useState`/`useEffect` (consistent with existing codebase patterns — NOT TanStack Query)

- [x] Task 4: Add Settings Translation Keys (AC: #1, #2)
  - [x] 4.1 Add `settings` namespace keys to `frontend/messages/en.json`:
    - `settings.title`: "Account Settings"
    - `settings.accountInfo`: "Account Information"
    - `settings.email`: "Email"
    - `settings.emailVerified`: "Verified"
    - `settings.emailNotVerified`: "Not verified"
    - `settings.memberSince`: "Member since"
    - `settings.languagePreference`: "Language"
    - `settings.languageDescription`: "Choose your preferred language for the interface"
    - `settings.ukrainian`: "Українська"
    - `settings.english`: "English"
    - Keep existing: `settings.language`, `settings.preferenceSaved`
  - [x] 4.2 Add matching `settings` namespace keys to `frontend/messages/uk.json` with proper Ukrainian translations:
    - `settings.title`: "Налаштування акаунту"
    - `settings.accountInfo`: "Інформація про акаунт"
    - `settings.email`: "Електронна пошта"
    - `settings.emailVerified`: "Підтверджено"
    - `settings.emailNotVerified`: "Не підтверджено"
    - `settings.memberSince`: "Учасник з"
    - `settings.languagePreference`: "Мова"
    - `settings.languageDescription`: "Оберіть бажану мову інтерфейсу"
    - `settings.ukrainian`: "Українська"
    - `settings.english`: "English"
  - [x] 4.3 Ensure both JSON files have identical key structures (no missing keys in either file)

- [x] Task 5: Responsive Layout & Mobile Optimization (AC: #3)
  - [x] 5.1 Style `SettingsPage` with Tailwind mobile-first: full-width on mobile with `px-4 py-6`, centered max-width on tablet/desktop with `md:max-w-2xl md:mx-auto md:px-6 lg:max-w-3xl`
  - [x] 5.2 Ensure all interactive elements (Select dropdown, links) have minimum 44x44px touch targets via `min-h-[44px] min-w-[44px]` classes
  - [x] 5.3 Settings sections stack vertically with `space-y-6` gap on all breakpoints
  - [x] 5.4 Test at breakpoints: 320px (small mobile), 375px (standard mobile), 768px (tablet), 1024px (desktop)

- [x] Task 6: Accessibility Compliance (AC: #4)
  - [x] 6.1 Use semantic HTML: `<main>` wrapper, `<section>` for each settings group, `<h1>` for page title, `<h2>` for section headings
  - [x] 6.2 All form controls have associated `<label>` elements or `aria-label` attributes
  - [x] 6.3 Read-only email field: use `<input readOnly>` or `<p>` with `aria-label="Email address"` — do NOT use disabled input (disabled elements are not focusable/readable by screen readers)
  - [x] 6.4 Language `Select` component: add `aria-label={t('settings.languagePreference')}` and ensure focus ring is visible (2px accent outline, 2px offset)
  - [x] 6.5 Keyboard navigation: Tab through all interactive elements in visual order, Enter/Space to activate Select dropdown, Escape to close
  - [x] 6.6 Screen reader: verification badge announced as `aria-label="Email verified"` or `aria-label="Email not verified"`
  - [x] 6.7 Color contrast: verify all text meets 4.5:1 ratio against background in both light and dark modes

- [x] Task 7: Backend Tests (AC: #1)
  - [x] 7.1 Verify `GET /api/v1/auth/me` returns `email`, `locale`, `isVerified`, `createdAt` fields — write test if not already covered
  - [x] 7.2 Verify `PATCH /api/v1/auth/me` updates locale — already tested in Story 1.6, confirm tests still pass
  - [x] 7.3 All existing 45+ backend tests MUST continue to pass (regression check)

- [x] Task 8: Frontend Tests (AC: #1, #2, #3, #4)
  - [x] 8.1 Test `SettingsPage` renders loading skeleton while profile is being fetched
  - [x] 8.2 Test `SettingsPage` displays email, locale, and creation date after successful fetch
  - [x] 8.3 Test `AccountInfoSection` renders email, formatted date, and verification badge
  - [x] 8.4 Test `LanguageSection` renders current locale in Select dropdown
  - [x] 8.5 Test `LanguageSection` calls `PATCH /api/v1/auth/me` and switches locale on language change
  - [x] 8.6 Test `LanguageSection` shows toast on successful language change
  - [x] 8.7 Test error state when `GET /api/v1/auth/me` fails (shows error message with retry)
  - [x] 8.8 Test all translated strings render correctly for both `uk` and `en` locales
  - [x] 8.9 All existing 47+ frontend tests from stories 1.1-1.6 MUST continue to pass (regression check)

## Dev Notes

### Critical Architecture Decisions

- **shadcn/ui MUST be initialized** — AC #4 requires shadcn/ui primitives. The project does NOT currently have shadcn configured. Run `npx shadcn@latest init` first. The shadcn CLI v4 (March 2026) auto-detects Next.js + Tailwind v4 + App Router. Components are copied into `frontend/src/components/ui/` as owned source code (not npm dependencies).
- **Use EXISTING `GET /api/v1/auth/me` endpoint** — do NOT create a new `/api/v1/settings` endpoint. The existing `GET /api/v1/auth/me` already returns all needed fields: `id`, `email`, `locale`, `isVerified`, `createdAt`. The `PATCH /api/v1/auth/me` endpoint already handles locale updates. Architecture doc mentions `/api/v1/settings` but the codebase has already consolidated user settings into the auth/me endpoints — follow the EXISTING pattern.
- **Use native `fetch()`, NOT TanStack Query** — the existing codebase (Stories 1.1-1.6) consistently uses raw `fetch()` for API calls (see `LoginForm.tsx`, `SignupForm.tsx`, `LocaleSwitcher.tsx`). TanStack Query is in the architecture spec for later adoption but has NOT been introduced yet. Stay consistent with current patterns to avoid adding a new dependency in Epic 1.
- **Language change reuses LocaleSwitcher pattern** — `LanguageSection` should follow the exact same API call + locale switch pattern as `LocaleSwitcher.tsx`. Call `PATCH /api/v1/auth/me` with Bearer token, then `router.replace(pathname, { locale: newLocale })`.
- **Auto-save, no "Save" button** — UX spec explicitly states: "Changes save automatically (no 'Save' button needed). Sonner toast confirms: 'Preference saved'". Language selection triggers immediate save on change.
- **Settings is a flat page** — no nested routes or sub-pages. All settings visible on a single scrollable page. No tabs or accordion navigation needed for current scope.
- **Dark mode is the default** — UX spec specifies dark mode (Monobank-familiar aesthetic) as default. Ensure shadcn/ui CSS variables support the dark theme with the project's existing color scheme (`#0F1117` background, `#F0F0F3` text, `#6C63FF` accent).

### Technical Requirements

- **shadcn/ui CLI v4 setup**: Run `npx shadcn@latest init` in the `frontend/` directory. It will auto-detect Next.js 16 + Tailwind v4 + App Router. Then `npx shadcn@latest add card separator select button skeleton` to install needed components. Check `components.json` is created correctly.
- **Page route**: `frontend/src/app/[locale]/(dashboard)/settings/page.tsx` — inside the `(dashboard)` route group, so AuthGuard protects it automatically via the dashboard layout.
- **API call pattern**: Use `session.accessToken` from `useSession()` as Bearer token. `const API_URL = process.env.NEXT_PUBLIC_API_URL`. Follow the same fetch + error handling pattern as `LocaleSwitcher.tsx`.
- **Date formatting**: Use existing `lib/format/date.ts` utility. Call `formatDate(profile.createdAt, locale)` where locale comes from `useLocale()`. The utility already handles Ukrainian vs English formatting.
- **Error handling**: If `GET /api/v1/auth/me` fails, show a user-friendly error card with retry button. Use i18n error message: `errors.serverError`. If `PATCH /api/v1/auth/me` fails, show sonner toast error. Do NOT expose technical errors.

### Architecture Compliance

- **API prefix**: `/api/v1/` — use existing endpoints, no new backend routes needed
- **Response format**: `UserProfileResponse` returns `{ id, email, locale, isVerified, createdAt }` with camelCase field names (Pydantic `alias_generator=to_camel`)
- **Error response format**: `{ "error": { "code": "...", "message": "...", "details": {...} } }` — map to user-friendly i18n strings
- **HTTP status codes**: 200 (successful read/update), 401 (not authenticated), 422 (validation error)
- **Component naming**: PascalCase for components (`SettingsPage.tsx`), camelCase for hooks (`use-user-profile.ts`)
- **Feature folder structure**: `features/settings/components/`, `features/settings/hooks/`, `features/settings/__tests__/`
- **Locale codes**: ISO 639-1 — `"uk"` (Ukrainian), `"en"` (English). NOT `"ua"`.
- **Navigation**: Add settings link to dashboard header. Use next-intl `Link` from `@/i18n/navigation` for locale-aware routing

### Library & Framework Requirements

| Library | Version | Purpose | Notes |
|---|---|---|---|
| `shadcn/ui` | CLI v4 (latest) | Component library | **NEW — run `npx shadcn@latest init` then `add card separator select button skeleton`** |
| `lucide-react` | latest | Icons (gear icon for nav) | **May be installed by shadcn init** — check after init. If not, `npm install lucide-react` |
| `next-intl` | v4.8.3 | i18n | Already installed. Use `useTranslations('settings')` |
| `sonner` | latest | Toast notifications | Already installed. Reuse for preference saved/error toasts |
| `next-auth` | 5.0.0-beta.30 | Session + access token | Already installed. Use `useSession()` to get `accessToken` |
| `react-hook-form` | 7.71.2 | Form handling | Already installed. NOT needed for this story (auto-save, no form submit) |
| `zod` | 4.3.6 | Validation | Already installed. NOT needed for this story (Select component limits choices) |

**Do NOT install:** TanStack Query (not yet adopted), axios (project uses fetch), any CSS-in-JS library (project uses Tailwind)

### File Structure Requirements

**New files to create:**

```
frontend/
├── src/
│   ├── app/[locale]/(dashboard)/settings/
│   │   └── page.tsx                              # CREATE — Settings route page
│   ├── features/settings/
│   │   ├── components/
│   │   │   ├── SettingsPage.tsx                   # CREATE — Main settings client component
│   │   │   ├── AccountInfoSection.tsx             # CREATE — Email, date, verification display
│   │   │   └── LanguageSection.tsx                # CREATE — Language preference selector
│   │   ├── hooks/
│   │   │   └── use-user-profile.ts                # CREATE — Fetch user profile hook
│   │   └── __tests__/
│   │       └── SettingsPage.test.tsx               # CREATE — Settings page tests
│   └── components/ui/                             # POPULATED by shadcn init — Card, Select, etc.
```

**Files to modify:**

```
frontend/
├── src/
│   └── app/[locale]/(dashboard)/layout.tsx        # MODIFY — Add Settings nav link
├── messages/
│   ├── en.json                                    # MODIFY — Add settings.* translation keys
│   └── uk.json                                    # MODIFY — Add settings.* translation keys
├── globals.css                                    # MODIFY — Merge shadcn CSS variables (if needed after init)
├── components.json                                # CREATED by shadcn init
```

**Existing files to reuse (DO NOT recreate):**

- `frontend/src/components/layout/LocaleSwitcher.tsx` — reference API call pattern and locale switching logic
- `frontend/src/lib/format/date.ts` — `formatDate()` for locale-aware date display
- `frontend/src/lib/format/currency.ts` — not needed for this story but exists
- `frontend/src/lib/auth/auth-guard.tsx` — already wraps dashboard routes
- `frontend/src/lib/auth/next-auth-config.ts` — session config with accessToken
- `frontend/src/test-utils/intl-mock.ts` — shared next-intl mock for tests
- `frontend/src/i18n/navigation.ts` — locale-aware `Link`, `useRouter`, `usePathname`
- `backend/app/api/v1/auth.py` — existing GET/PATCH /me endpoints (no changes needed)
- `backend/app/models/user.py` — User model with all fields (no changes needed)

### Testing Requirements

**Frontend tests** (Vitest + React Testing Library):
- Place in `features/settings/__tests__/SettingsPage.test.tsx`
- Mock `next-intl` using `test-utils/intl-mock.ts` helper (established in Story 1.6)
- Mock `next-auth/react` `useSession()` to return `{ data: { accessToken: 'test-token' }, status: 'authenticated' }`
- Mock global `fetch` for `GET /api/v1/auth/me` and `PATCH /api/v1/auth/me`
- Mock `sonner` toast function
- Mock `@/i18n/navigation` for `Link`, `useRouter`, `usePathname`
- Test loading state: skeleton renders while fetch is pending
- Test success state: profile data displays correctly
- Test language change: Select triggers PATCH call + locale switch
- Test error state: error message renders with retry button
- All existing 47+ frontend tests from stories 1.1-1.6 MUST pass

**Backend tests** (pytest + httpx):
- No new backend endpoints — only verify existing tests pass
- All existing 45+ backend tests MUST pass (regression check)
- Optional: add test asserting `GET /api/v1/auth/me` response schema includes all fields settings page needs

### Previous Story Intelligence (from Story 1.6)

**Critical patterns established — FOLLOW these:**
- `LocaleSwitcher.tsx` demonstrates the exact API call pattern for `PATCH /api/v1/auth/me` — copy this pattern for `LanguageSection` (fetch with Bearer token, handle response, toast, router.replace)
- `proxy.ts` combines next-intl middleware with NextAuth auth check — no changes needed
- `useLocale()` from `next-intl` provides current locale — use for date formatting and Select default value
- `useRouter()` from `@/i18n/navigation` provides `replace(pathname, { locale })` — use for locale switching
- `test-utils/intl-mock.ts` provides `createUseTranslations()` helper — use in all component tests
- `SessionExpiredDialog` auto-logs out on session expiry — no settings page changes needed
- DM Sans font loaded with `latin` + `latin-ext` subsets (NOT `cyrillic` — it doesn't exist as a separate subset in next/font)

**Critical bugs fixed in 1.4-1.6 — DO NOT reintroduce:**
- Default locale is `"uk"` (Ukrainian), NOT `"en"` — ensure settings page defaults correctly
- `user.updated_at = datetime.now(UTC)` — not deprecated `utcnow()`
- No hardcoded `/en/` locale references — all routing uses dynamic locale from `useLocale()`
- `SessionExpiredDialog` must auto-logout (no "Continue session" option)

**Spec deviations from 1.6 to be aware of:**
- shadcn/ui was NOT configured in 1.6 — `LocaleSwitcher` was built as a custom Tailwind button. Story 1.7 MUST initialize shadcn/ui now (AC #4 requires it)
- `settings.language` and `settings.preferenceSaved` translation keys already exist — do NOT duplicate them, add new keys alongside

**Dependencies already installed — do NOT reinstall:**
- Backend: boto3, python-jose[cryptography], pydantic[email], httpx, pytest-asyncio, aiosqlite, sqlmodel, asyncpg, alembic
- Frontend: next-auth@beta, @auth/core, react-hook-form, @hookform/resolvers, zod, vitest, @testing-library/*, sonner, next-intl

### Git Intelligence

**Recent commits:**
- `5d9eb31` Story 1.5: Protected Routes & Tenant Isolation // Story 1.6: Language Selection (Ukrainian & English)
- `490f150` Story 1.4: User Login, Logout & Session Management
- `3ded222` Story 1.3: AWS Cognito Integration & User Registration
- `a6c15bc` Story 1.2: AWS Infrastructure Provisioning
- `720d284` Initial commit

**Code conventions from recent work:**
- Commit message format: `Story X.Y: Description`
- Python: Ruff for linting, async/await everywhere, type hints on all functions
- TypeScript: `"use client"` directive for interactive components, strict mode
- Tests: co-located in `__tests__/` for frontend, separate `tests/` for backend
- Feature folders: `features/{name}/components/`, `features/{name}/hooks/`, `features/{name}/__tests__/`
- Translation keys: namespace-based (`settings.key`), flat within namespace

### Latest Technical Information

- **shadcn/ui CLI v4 (March 2026)**: Auto-detects Next.js + Tailwind v4 + React 19. Full support for `@theme` directive and `@theme inline`. All components updated for Tailwind v4. Run `npx shadcn@latest init` in existing project — it will not override your Next.js setup. Then `npx shadcn@latest add <component>` to install specific components. The `info` command shows framework version, CSS vars, installed components.
- **shadcn/ui components with Tailwind v4**: Use CSS variables for theming. Components are copied into `components/ui/` as source files you own. Works with `prefers-color-scheme` or class-based dark mode.
- **Radix UI**: shadcn/ui v4 uses the unified `radix-ui` package (not individual `@radix-ui/*` packages). This is handled by the CLI — no manual Radix installation needed.
- **lucide-react**: May be installed by `npx shadcn@latest init` as a peer dependency. If not, install manually for icons.

### Project Structure Notes

- Settings page at `app/[locale]/(dashboard)/settings/page.tsx` — inside the `(dashboard)` route group which provides AuthGuard protection and the header/navigation layout
- Feature module at `features/settings/` — follows the established pattern from `features/auth/`
- shadcn components at `components/ui/` — replacing the empty `.gitkeep` with actual component files
- No new backend directories or files needed — all endpoints exist
- Navigation link added to dashboard `layout.tsx` — consistent with existing header structure

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 1, Story 1.7]
- [Source: _bmad-output/planning-artifacts/architecture.md — Frontend Architecture, Settings Feature, shadcn/ui, API Patterns, Database Schema, Testing Standards]
- [Source: _bmad-output/planning-artifacts/prd.md — FR30 (Account Settings), FR29 (Language Selection), NFRs (Accessibility, Performance, Security)]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md — Settings Page Design, Language Switching UX, Mobile Responsive Patterns, WCAG 2.1 AA, Visual Design Tokens, Animation Timing]
- [Source: _bmad-output/implementation-artifacts/1-6-language-selection-ukrainian-english.md — Previous story patterns, LocaleSwitcher API pattern, test helpers, shadcn status, translation structure]
- [Source: frontend/src/components/layout/LocaleSwitcher.tsx — API call pattern for PATCH /me + locale switching]
- [Source: backend/app/api/v1/auth.py — GET /me + PATCH /me endpoints (already exist)]
- [Source: backend/app/models/user.py — User model fields (email, locale, is_verified, created_at)]
- [Source: frontend/messages/en.json — Existing translation structure and settings.* keys]
- [Source: frontend/src/lib/format/date.ts — Locale-aware date formatting utility]
- [Source: ui.shadcn.com/docs/installation/next — shadcn/ui Next.js installation guide]
- [Source: ui.shadcn.com/docs/tailwind-v4 — shadcn/ui Tailwind v4 setup guide]
- [Source: ui.shadcn.com/docs/changelog/2026-03-cli-v4 — shadcn CLI v4 March 2026 release]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- Pre-existing `vitest.config.ts` type error (vite/vitest plugin mismatch) — does not affect tests or our implementation. Build was already failing before this story.

### Completion Notes List

- Initialized shadcn/ui v4 (base-nova style) with Tailwind v4 auto-detection. Installed components: button, card, separator, select, skeleton.
- Fixed shadcn init overwriting DM Sans font reference to Geist — restored DM Sans as primary font.
- Added `dark` class to HTML root element for class-based dark mode (project default is dark). Updated dark mode CSS variables to match project design system (#0F1117 bg, #F0F0F3 fg, #6C63FF accent).
- Created settings page route at `app/[locale]/(dashboard)/settings/page.tsx` with `generateMetadata()` for translated title.
- Added settings gear icon nav link to dashboard header using lucide-react `Settings` icon.
- Created feature module with SettingsPage (loading/error/success states), AccountInfoSection (email, verification badge, creation date), LanguageSection (shadcn Select with auto-save via PATCH /me), and useUserProfile hook (native fetch, not TanStack Query).
- Language change follows exact same pattern as LocaleSwitcher.tsx — PATCH /me + router.replace with new locale + sonner toast.
- All translation keys added for both `en` and `uk` locales with identical key structures.
- Responsive layout: mobile-first with px-4 py-6, centered max-w-2xl on tablet, lg:max-w-3xl on desktop. 44px min touch targets on interactive elements.
- Accessibility: semantic HTML (main, section, h1, h2), aria-labels on select and verification badge, keyboard navigation via shadcn Select primitives.
- 10 new frontend tests: loading skeleton, profile display, account info rendering, unverified badge, language section rendering, PATCH call on language change, toast notification, error state, retry functionality, translated strings.
- All 45 backend tests pass (no regressions).
- All 57 frontend tests pass (47 existing + 10 new, no regressions).

### Change Log

- 2026-03-23: Story 1.7 implementation complete — Account Settings page with shadcn/ui components, language preference management, responsive layout, and accessibility compliance.
- 2026-03-23: Code review — Fixed 7 issues (3 HIGH, 4 MEDIUM): added error toast on PATCH failure, replaced raw button with shadcn Button, fixed useUserProfile infinite loading + AbortController, semantic HTML consistency, added PATCH failure test, documented 4 undocumented file changes. All 58 frontend + 45 backend tests pass.

### File List

**New files:**
- frontend/components.json (shadcn/ui configuration)
- frontend/src/components/ui/button.tsx (shadcn Button component)
- frontend/src/components/ui/card.tsx (shadcn Card component)
- frontend/src/components/ui/separator.tsx (shadcn Separator component)
- frontend/src/components/ui/select.tsx (shadcn Select component)
- frontend/src/components/ui/skeleton.tsx (shadcn Skeleton component)
- frontend/src/lib/utils.ts (cn() utility for class merging)
- frontend/src/app/[locale]/(dashboard)/settings/page.tsx (Settings page route)
- frontend/src/features/settings/components/SettingsPage.tsx (Main settings client component)
- frontend/src/features/settings/components/AccountInfoSection.tsx (Account info display)
- frontend/src/features/settings/components/LanguageSection.tsx (Language preference selector)
- frontend/src/features/settings/hooks/use-user-profile.ts (User profile fetch hook)
- frontend/src/features/settings/__tests__/SettingsPage.test.tsx (Settings page tests)

**Modified files:**
- frontend/src/app/globals.css (shadcn CSS variables, dark mode colors)
- frontend/src/app/layout.tsx (added dark class, removed Geist font)
- frontend/src/app/[locale]/(dashboard)/layout.tsx (added settings nav link)
- frontend/messages/en.json (added settings.* and errors.retry translation keys, dashboard.settings)
- frontend/messages/uk.json (added settings.* and errors.retry translation keys, dashboard.settings)
- frontend/package.json (shadcn dependencies: radix-ui, base-ui, lucide-react, clsx, tailwind-merge, tw-animate-css)
- _bmad-output/implementation-artifacts/sprint-status.yaml (1-7 status: in-progress → review)
- frontend/src/proxy.ts (removed stale `export const runtime` — fix from prior story)
- frontend/tsconfig.json (added vitest.config.ts to exclude — fix from prior story)
- frontend/src/features/auth/__tests__/LoginForm.test.tsx (refactored Link mock to async import — fix from prior story)
- frontend/src/features/auth/__tests__/proxy.test.ts (replaced untyped Function/any with proper types — fix from prior story)
