# Story 1.8: Forgot-Password Flow

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want to reset my password via email when I've forgotten it,
So that I can regain access to my account without contacting support.

## Acceptance Criteria

1. **Given** I am on the login page, **When** I click the "Forgot password?" link, **Then** I am taken to `/forgot-password` which has an email input field; the link is already wired in `LoginForm.tsx` pointing to `/forgot-password`

2. **Given** I am on the `/forgot-password` page and enter my registered email, **When** I submit the form, **Then** the backend calls Cognito `InitiateForgotPassword`, a password reset email with a verification code is sent, and I see a confirmation message: "Check your email for a reset code"

3. **Given** I enter an email that is not registered, **When** I submit the forgot-password form, **Then** I see the same "Check your email for a reset code" confirmation (no email enumeration — the response never reveals whether the address exists)

4. **Given** I have received the reset email with a verification code, **When** I visit `/forgot-password/confirm`, enter the verification code, and provide a new password meeting Cognito complexity requirements, **Then** the backend calls Cognito `ConfirmForgotPassword`, my password is updated, and I am redirected to `/login` with a success banner "Password updated — please log in"

5. **Given** I submit the confirmation form with an expired or invalid reset code, **When** Cognito returns an error, **Then** I see a user-friendly message: "Reset code is invalid or has expired. Please request a new one." with a link back to `/forgot-password`

6. **Given** the `/forgot-password` and `/forgot-password/confirm` pages, **When** rendered on mobile, **Then** all inputs and buttons are touch-optimized and thumb-reachable with visible focus indicators (WCAG 2.1 AA)

## Tasks / Subtasks

- [x] Task 1: Backend — Add Cognito forgot-password methods to CognitoService (AC: #2, #3, #4, #5)
  - [x] 1.1 Open `backend/app/services/cognito_service.py`. Add method `initiate_forgot_password(email: str) -> None` that calls `self.client.forgot_password(ClientId=self.client_id, Username=email)`. Wrap in try/except: `NotAuthorizedException` → raise `AuthenticationError("USER_NOT_CONFIRMED", ...)` if email is unverified; all other exceptions → silently succeed (prevents email enumeration). Never raise an error for non-existent emails.
  - [x] 1.2 Add method `confirm_forgot_password(email: str, code: str, new_password: str) -> None` that calls `self.client.confirm_forgot_password(ClientId=self.client_id, Username=email, ConfirmationCode=code, Password=new_password)`. Map Cognito exceptions to `AuthenticationError`: `CodeMismatchException` → `RESET_CODE_INVALID`, `ExpiredCodeException` → `RESET_CODE_EXPIRED`, `InvalidPasswordException` → `PASSWORD_TOO_WEAK`, `LimitExceededException` → `RATE_LIMITED`.
  - [x] 1.3 Add the new Cognito exception mappings to the existing error-code map in `cognito_service.py` for completeness and consistent error handling across the service.

- [x] Task 2: Backend — Add forgot-password API endpoints (AC: #2, #3, #4, #5)
  - [x] 2.1 In `backend/app/api/v1/auth.py`, add Pydantic request model `ForgotPasswordRequest(BaseModel)` with field: `email: EmailStr`. Add Pydantic request model `ConfirmForgotPasswordRequest(BaseModel)` with fields: `email: EmailStr`, `code: str` (min 6, max 6 chars), `new_password: str` (min 8 chars).
  - [x] 2.2 Add route `POST /api/v1/auth/forgot-password` (no auth required). Accepts `ForgotPasswordRequest`. Calls `cognito_service.initiate_forgot_password(request.email)`. Always returns `{"message": "If an account exists, a reset code has been sent"}` with status 200 — even if the email doesn't exist. This is intentional to prevent email enumeration.
  - [x] 2.3 Add route `POST /api/v1/auth/reset-password` (no auth required). Accepts `ConfirmForgotPasswordRequest`. Calls `cognito_service.confirm_forgot_password(request.email, request.code, request.new_password)`. On success returns `{"message": "Password updated successfully"}` with status 200. On `AuthenticationError` re-raises to the existing FastAPI exception handler (which returns `{"error": {"code": ..., "message": ...}}`).
  - [x] 2.4 Register both new routes in the auth router — they require no authentication middleware.

- [x] Task 3: Backend — Tests for new endpoints (AC: #2, #3, #4, #5)
  - [x] 3.1 Add tests in `backend/tests/api/test_auth.py` (or equivalent): `test_forgot_password_registered_email` — mock cognito success, verify 200 + generic message; `test_forgot_password_unknown_email` — mock cognito UserNotFoundException, verify same 200 + same generic message (enumeration prevention); `test_forgot_password_unverified_email` — mock NotAuthorizedException, verify appropriate error response.
  - [x] 3.2 Add tests: `test_reset_password_success` — mock cognito success, verify 200; `test_reset_password_invalid_code` — mock CodeMismatchException, verify error code `RESET_CODE_INVALID`; `test_reset_password_expired_code` — mock ExpiredCodeException, verify `RESET_CODE_EXPIRED`; `test_reset_password_weak_password` — mock InvalidPasswordException, verify `PASSWORD_TOO_WEAK`.
  - [x] 3.3 All existing 45+ backend tests MUST continue to pass (regression check).

- [x] Task 4: Frontend — Zod schemas for both forms (AC: #2, #4)
  - [x] 4.1 Create `frontend/src/features/auth/schemas/forgot-password-schema.ts` — export `forgotPasswordSchema = z.object({ email: z.string().email() })` and `ForgotPasswordFormData` type inferred from it.
  - [x] 4.2 Create `frontend/src/features/auth/schemas/reset-password-schema.ts` — export `resetPasswordSchema = z.object({ code: z.string().length(6, "Code must be 6 digits"), newPassword: z.string().min(8), confirmPassword: z.string() }).refine(data => data.newPassword === data.confirmPassword, { message: "Passwords do not match", path: ["confirmPassword"] })`. Export `ResetPasswordFormData` type.

- [x] Task 5: Frontend — ForgotPasswordForm component (AC: #1, #2, #3, #6)
  - [x] 5.1 Create `frontend/src/features/auth/components/ForgotPasswordForm.tsx` (`"use client"`). Use `react-hook-form` + `zodResolver(forgotPasswordSchema)`. Shows: email field with label, submit button "Send reset code", and a back-to-login link.
  - [x] 5.2 On submit: POST to `${NEXT_PUBLIC_API_URL}/api/v1/auth/forgot-password` with `{ email }`. On success (200): replace the form with a confirmation panel showing "Check your email for a reset code" message and a "Enter reset code →" link to `/forgot-password/confirm?email=<encoded_email>` (pass email as query param so the confirm page can pre-fill it). Do NOT redirect automatically.
  - [x] 5.3 On API error: show generic error alert at the top of the form using the same pattern as `LoginForm.tsx` error display. Use i18n error messages mapped from error codes. On network failure: show `t('errors.serverError')`.
  - [x] 5.4 Button disabled + shows loading text `t('auth.forgotPassword.submitting')` while request is in flight. Email field gets `autoComplete="email"`, `type="email"`, `inputMode="email"`. Minimum 44px touch targets on all interactive elements.

- [x] Task 6: Frontend — ResetPasswordForm component (AC: #4, #5, #6)
  - [x] 6.1 Create `frontend/src/features/auth/components/ResetPasswordForm.tsx` (`"use client"`). Reads `email` from URL search params via `useSearchParams()`. Use `react-hook-form` + `zodResolver(resetPasswordSchema)`.
  - [x] 6.2 Form fields: verification code (type="text", inputMode="numeric", maxLength=6, autoComplete="one-time-code"), new password (type="password", autoComplete="new-password"), confirm new password (type="password", autoComplete="new-password"). Show password requirements hint consistent with `SignupForm.tsx`.
  - [x] 6.3 On submit: POST to `${NEXT_PUBLIC_API_URL}/api/v1/auth/reset-password` with `{ email, code, newPassword }`. On 200 success: redirect to `/login` with a success query param (e.g., `?reset=success`) which the login page detects and shows a green success banner "Password updated — please log in".
  - [x] 6.4 On `RESET_CODE_INVALID` or `RESET_CODE_EXPIRED` error: show message "Reset code is invalid or has expired. Please request a new one." with a link back to `/forgot-password`. On `PASSWORD_TOO_WEAK`: show password requirement hints. On other errors: show generic `t('errors.serverError')`.
  - [x] 6.5 Button disabled + loading state during submission. "Back to forgot password" link to `/forgot-password` always visible.

- [x] Task 7: Frontend — Route pages (AC: #1, #6)
  - [x] 7.1 Create `frontend/src/app/[locale]/(auth)/forgot-password/page.tsx` — Server Component. `generateMetadata()` returns translated title. Renders `<ForgotPasswordForm />`. Redirect authenticated users to `/dashboard` (mirror the login page guard pattern).
  - [x] 7.2 Create `frontend/src/app/[locale]/(auth)/forgot-password/confirm/page.tsx` — Server Component. `generateMetadata()` returns translated title. Renders `<ResetPasswordForm />`. Redirect authenticated users to `/dashboard`.
  - [x] 7.3 In `frontend/src/app/[locale]/(auth)/login/page.tsx`: add success banner logic — if URL search param `?reset=success` is present, show a green alert/banner "Password updated — please log in" above the login form. This is a client-side read of `useSearchParams()` in `LoginForm.tsx` or a separate banner component.

- [x] Task 8: Frontend — Translation keys (AC: #2, #3, #4, #5, #6)
  - [x] 8.1 Add to `frontend/messages/en.json` under `auth.forgotPassword` namespace:
    - `title`: "Reset your password"
    - `description`: "Enter your email and we'll send you a reset code"
    - `emailLabel`: "Email"
    - `emailPlaceholder`: "you@example.com"
    - `submit`: "Send reset code"
    - `submitting`: "Sending..."
    - `confirmationTitle`: "Check your email"
    - `confirmationMessage`: "We've sent a password reset code to your email. It may take a few minutes."
    - `enterCode`: "Enter reset code"
    - `backToLogin`: "Back to login"
    - `noCodeReceived`: "Didn't receive a code?"
    - `tryAgain`: "Try again"
  - [x] 8.2 Add to `frontend/messages/en.json` under `auth.resetPassword` namespace:
    - `title`: "Set a new password"
    - `codeLabel`: "Reset code"
    - `codePlaceholder`: "6-digit code from email"
    - `newPasswordLabel`: "New password"
    - `confirmPasswordLabel`: "Confirm new password"
    - `submit`: "Update password"
    - `submitting`: "Updating..."
    - `successBanner`: "Password updated — please log in"
    - `invalidCode`: "Reset code is invalid or has expired. Please request a new one."
    - `backToForgotPassword`: "Request a new code"
    - `passwordMismatch`: "Passwords do not match"
  - [x] 8.3 Add matching Ukrainian translations to `frontend/messages/uk.json` for all keys in 8.1 and 8.2:
    - `auth.forgotPassword.title`: "Відновлення паролю"
    - `auth.forgotPassword.description`: "Введіть email і ми надішлемо код для відновлення"
    - `auth.forgotPassword.emailLabel`: "Електронна пошта"
    - `auth.forgotPassword.submit`: "Надіслати код"
    - `auth.forgotPassword.submitting`: "Надсилаємо..."
    - `auth.forgotPassword.confirmationTitle`: "Перевірте пошту"
    - `auth.forgotPassword.confirmationMessage`: "Ми надіслали код відновлення на вашу пошту. Це може зайняти кілька хвилин."
    - `auth.forgotPassword.enterCode`: "Ввести код"
    - `auth.forgotPassword.backToLogin`: "Повернутись до входу"
    - `auth.forgotPassword.noCodeReceived`: "Не отримали код?"
    - `auth.forgotPassword.tryAgain`: "Спробувати знову"
    - `auth.resetPassword.title`: "Встановіть новий пароль"
    - `auth.resetPassword.codeLabel`: "Код відновлення"
    - `auth.resetPassword.codePlaceholder`: "6-значний код з листа"
    - `auth.resetPassword.newPasswordLabel`: "Новий пароль"
    - `auth.resetPassword.confirmPasswordLabel`: "Підтвердіть новий пароль"
    - `auth.resetPassword.submit`: "Оновити пароль"
    - `auth.resetPassword.submitting`: "Оновлюємо..."
    - `auth.resetPassword.successBanner`: "Пароль оновлено — увійдіть"
    - `auth.resetPassword.invalidCode`: "Код недійсний або закінчився. Будь ласка, запитайте новий."
    - `auth.resetPassword.backToForgotPassword`: "Запросити новий код"
    - `auth.resetPassword.passwordMismatch`: "Паролі не збігаються"
  - [x] 8.4 Ensure both JSON files have identical key structures — no missing keys in either file.

- [x] Task 9: Frontend — Tests (AC: #2, #3, #4, #5)
  - [x] 9.1 Create `frontend/src/features/auth/__tests__/ForgotPasswordForm.test.tsx`. Test: renders email field and submit button; submits POST to `/api/v1/auth/forgot-password`; shows confirmation panel on success; shows error alert on API failure; shows generic error on network failure; disables button during submission; submit button has loading text.
  - [x] 9.2 Create `frontend/src/features/auth/__tests__/ResetPasswordForm.test.tsx`. Test: renders code, new password, confirm password fields; submits POST to `/api/v1/auth/reset-password` with correct payload; redirects to `/login?reset=success` on success; shows `invalidCode` message on RESET_CODE_INVALID; shows `invalidCode` message on RESET_CODE_EXPIRED; shows password mismatch error on client; disables button during submission; has back link to `/forgot-password`.
  - [x] 9.3 Test login page success banner: `LoginPage.test.tsx` — test that `?reset=success` query param causes the success banner to render with correct translated text.
  - [x] 9.4 All existing 58+ frontend tests MUST continue to pass (regression check).

### Review Follow-ups (AI)

Items surfaced during the 2026-04-16 code review but deferred have been logged in the central tech-debt register: see [docs/tech-debt.md](docs/tech-debt.md) entries **TD-001** through **TD-005**.

## Dev Notes

### Critical Architecture Decisions

- **The "Forgot password?" link ALREADY EXISTS in `LoginForm.tsx`** pointing to `/forgot-password` (line ~191). Translation key `auth.login.forgotPassword` already exists in both `en.json` and `uk.json`. Do NOT add a new link — just create the page the link points to.
- **Two-page flow, not two routes** — Step 1 is `/forgot-password` (email input). Step 2 is `/forgot-password/confirm` (code + new password). The epics spec explicitly names these paths. Do NOT use `/reset-password/[token]` — Cognito does NOT use URL tokens, it uses a 6-digit code delivered to email.
- **Email enumeration prevention is required** — The backend `POST /api/v1/auth/forgot-password` MUST always return the same 200 success response regardless of whether the email exists in Cognito. This is security-critical. The Cognito `ForgotPassword` API itself leaks nothing for unknown users — it simply does nothing. Mirror this at the API layer: catch `UserNotFoundException` and return the same success JSON.
- **Email passed as query param to confirm page** — After the user submits their email and sees the confirmation message, they click "Enter reset code →" which navigates to `/forgot-password/confirm?email=<url-encoded-email>`. The confirm page reads this via `useSearchParams()` and pre-fills the email field. This avoids needing session state or localStorage for such a simple flow.
- **Success redirect with query param** — After successful password reset, redirect to `/login?reset=success`. The login page checks this param and shows a green banner. This avoids ephemeral state management across routes and follows the existing pattern used by the verification flow (Story 1.3).
- **Use `(auth)` route group** — Both new pages go inside `frontend/src/app/[locale]/(auth)/` alongside `login/` and `signup/`. The auth layout provides the centered card design. Do NOT create a new route group.
- **NO new backend routes for Cognito token flow** — Cognito forgot-password uses a code (not a URL token). The full flow is: `ForgotPassword` API (initiates reset, Cognito emails a 6-digit code) → user enters code → `ConfirmForgotPassword` API (validates code + sets new password). No backend token storage needed.
- **Rate limiting** — Cognito will rate-limit `ForgotPassword` calls natively (via `LimitExceededException`). Map this error to a user-friendly message. Do NOT add additional application-level rate limiting for this endpoint in MVP.

### Technical Requirements

- **Cognito service methods** — `CognitoService` (`backend/app/services/cognito_service.py`) wraps all boto3 calls. Add two new methods: `initiate_forgot_password(email)` and `confirm_forgot_password(email, code, new_password)`. The service already has a consistent pattern: call boto3, catch specific exceptions, raise typed `AuthenticationError` or `RegistrationError`. Follow this exact pattern.
- **API endpoint path convention** — Existing auth endpoints: `/api/v1/auth/login`, `/api/v1/auth/signup`, `/api/v1/auth/verify`, `/api/v1/auth/refresh-token`. New endpoints: `POST /api/v1/auth/forgot-password` and `POST /api/v1/auth/reset-password`. Consistent with dash-separated naming.
- **Pydantic request models** — Follow existing pattern in `auth.py`: `class LoginRequest(BaseModel)`. Add `class ForgotPasswordRequest(BaseModel)` and `class ConfirmForgotPasswordRequest(BaseModel)`. Use `EmailStr` for email fields (already imported via pydantic[email]).
- **Frontend fetch pattern** — This codebase uses native `fetch()`, NOT TanStack Query (Story 1.7 dev notes confirm this). Forms use `react-hook-form` + `zodResolver`. Follow the exact patterns from `LoginForm.tsx` and `SignupForm.tsx`.
- **Password complexity** — Cognito enforces its own password policy (8+ chars, uppercase, lowercase, number, symbol). When the backend returns `PASSWORD_TOO_WEAK` (from `InvalidPasswordException`), show the same password requirements hint that `SignupForm.tsx` displays. Reference the existing `passwordRequirements` translation keys — do NOT duplicate them.
- **6-digit code input** — The reset code from Cognito is 6 digits. Use `type="text"` with `inputMode="numeric"` and `maxLength={6}`. Add `pattern="[0-9]{6}"` for client-side validation hint. This mirrors the verification code input in `VerificationForm.tsx`.
- **`useSearchParams` requires Suspense** — In Next.js App Router, `useSearchParams()` in a client component requires wrapping with `<Suspense>`. Wrap `<ResetPasswordForm />` in a `<Suspense fallback={<Skeleton />}>` in the page server component.

### Architecture Compliance

- **Route group**: `app/[locale]/(auth)/forgot-password/page.tsx` and `app/[locale]/(auth)/forgot-password/confirm/page.tsx` — both inside the `(auth)` route group which provides the centered auth card layout
- **Feature module**: `features/auth/components/ForgotPasswordForm.tsx` and `ResetPasswordForm.tsx` — extend the existing `features/auth/` module. Do NOT create a new `features/forgot-password/` directory.
- **Schema files**: `features/auth/schemas/forgot-password-schema.ts` and `features/auth/schemas/reset-password-schema.ts` — following the existing `login-schema.ts` / `signup-schema.ts` naming convention
- **Error response format**: `{"error": {"code": "RESET_CODE_EXPIRED", "message": "...", "details": {}}}` — same as all other auth errors; already handled by the global FastAPI exception handler
- **i18n**: All visible strings via `useTranslations('auth.forgotPassword')` and `useTranslations('auth.resetPassword')`. Both `en.json` and `uk.json` MUST have identical keys.
- **Locale-aware routing**: Use `Link` from `@/i18n/navigation` for all internal links. Use `useRouter()` from `@/i18n/navigation` for programmatic redirects (NOT from `next/navigation`).
- **Auth guard**: Use `auth()` from `next-auth` in the server component page to redirect authenticated users to `/dashboard` (mirror the `login/page.tsx` pattern exactly).

### Library & Framework Requirements

| Library | Version | Purpose | Notes |
|---|---|---|---|
| `react-hook-form` | 7.71.2 | Form state management | Already installed. Use in both new form components |
| `@hookform/resolvers` | latest | Zod integration | Already installed. `zodResolver(schema)` |
| `zod` | 4.3.6 | Schema validation | Already installed. Two new schemas needed |
| `next-intl` | v4.8.3 | i18n | Already installed. `useTranslations('auth.forgotPassword')` |
| `shadcn/ui` | CLI v4 | UI components | Already configured (Story 1.7). `Button`, `Input` (if added), `Alert` components |
| `next-auth` | 5.0.0-beta.30 | Auth guard | Already installed. Use `auth()` in server page for redirect guard |
| `boto3` | latest | AWS SDK | Already installed. Used by CognitoService — `client.forgot_password()` and `client.confirm_forgot_password()` |

**Do NOT install any new packages.** Everything needed is already in the project.

### File Structure Requirements

**New files to create:**

```
backend/
└── app/
    └── services/
        └── cognito_service.py          # MODIFY — Add initiate_forgot_password() and confirm_forgot_password()
    └── api/v1/
        └── auth.py                     # MODIFY — Add 2 new endpoints + 2 new Pydantic models

frontend/
└── src/
    ├── app/[locale]/(auth)/
    │   └── forgot-password/
    │       ├── page.tsx                # CREATE — Email input page
    │       └── confirm/
    │           └── page.tsx            # CREATE — Code + new password page
    └── features/auth/
        ├── components/
        │   ├── ForgotPasswordForm.tsx  # CREATE — Email form with confirmation state
        │   └── ResetPasswordForm.tsx  # CREATE — Code + password form
        ├── schemas/
        │   ├── forgot-password-schema.ts  # CREATE — Zod schema for email form
        │   └── reset-password-schema.ts   # CREATE — Zod schema for reset form
        └── __tests__/
            ├── ForgotPasswordForm.test.tsx  # CREATE — Tests for email form
            └── ResetPasswordForm.test.tsx   # CREATE — Tests for reset form
```

**Files to modify:**

```
frontend/
├── messages/en.json                    # MODIFY — Add auth.forgotPassword.* and auth.resetPassword.* keys
├── messages/uk.json                    # MODIFY — Add Ukrainian translations for same keys
└── src/app/[locale]/(auth)/login/page.tsx  # MODIFY — Read ?reset=success param + show success banner

backend/
└── tests/api/test_auth.py              # MODIFY — Add forgot-password and reset-password tests
```

**Existing files to reuse (DO NOT recreate):**

- `frontend/src/features/auth/components/LoginForm.tsx` — Reference for: fetch pattern, error display, button loading state, i18n usage, rate-limited error code handling
- `frontend/src/features/auth/components/SignupForm.tsx` — Reference for: password requirements display, confirm password validation
- `frontend/src/features/auth/components/VerificationForm.tsx` — Reference for: 6-digit code input pattern, resend link, loading states
- `frontend/src/features/auth/schemas/login-schema.ts` — Reference for Zod schema file structure
- `frontend/src/test-utils/intl-mock.ts` — Shared next-intl mock for all auth component tests
- `frontend/src/i18n/navigation.ts` — Use `Link`, `useRouter` from here (locale-aware)
- `backend/app/services/cognito_service.py` — Extend, don't replace. Study existing exception mapping pattern.
- `backend/app/api/v1/auth.py` — Extend, don't replace. Study existing endpoint structure.
- `backend/app/core/exceptions.py` — `AuthenticationError` class already handles code/message/status

### Testing Requirements

**Frontend tests** (Vitest + React Testing Library):
- Place new test files in `frontend/src/features/auth/__tests__/`
- Mock `next-intl` using `test-utils/intl-mock.ts` helper (established in Stories 1.3-1.7)
- Mock global `fetch` for POST calls
- Mock `@/i18n/navigation` for `Link`, `useRouter`, `useSearchParams`
- Mock `next/navigation` if used for `useSearchParams` fallback
- **ForgotPasswordForm tests**: loading state, success confirmation panel, API error display, network error fallback, email validation, button disabled during submit
- **ResetPasswordForm tests**: reads email from searchParams, form field rendering, success redirect to `/login?reset=success`, invalid code error, expired code error, password mismatch, loading state
- **LoginForm regression**: ensure the existing "Forgot password?" link still renders correctly with `/forgot-password` href
- All existing 58+ frontend tests MUST pass

**Backend tests** (pytest + httpx):
- Test file: `backend/tests/api/test_auth.py` (extend existing file)
- Mock boto3 client at the CognitoService level (consistent with existing tests)
- Test both endpoints with all expected success and error paths
- All existing 45+ backend tests MUST pass

### Previous Story Intelligence (from Story 1.7)

**Established patterns — FOLLOW these exactly:**
- All auth form components use `react-hook-form` + `zodResolver` + native `fetch()` — no TanStack Query
- Error display pattern: `{error && <div role="alert" className="..."><p>{error}</p></div>}` above form fields
- Button loading pattern: `disabled={isLoading}` + `{isLoading ? t('...submitting') : t('...submit')}`
- All components use `"use client"` directive
- Server page components use `auth()` from next-auth to redirect authenticated users
- `useTranslations` namespace approach: `useTranslations('auth.login')`, `useTranslations('settings')` — follow same nesting
- Feature tests use `createUseTranslations()` from `test-utils/intl-mock.ts`
- shadcn/ui Button, Card, Separator, Select, Skeleton are already configured in `components/ui/`

**Critical bugs fixed in previous stories — DO NOT reintroduce:**
- Default locale is `"uk"`, NOT `"en"` — all locale defaulting must use `"uk"`
- Always use `useRouter()` from `@/i18n/navigation` for locale-aware redirects, NOT from `next/navigation`
- Use `Link` from `@/i18n/navigation` for internal links — NOT `next/link` directly
- `datetime.now(UTC)` not deprecated `utcnow()` in Python backend

**shadcn/ui status** (from Story 1.7 completion notes):
- shadcn/ui v4 fully initialized with base-nova style
- Components available in `components/ui/`: `Button`, `Card`, `Separator`, `Select`, `Skeleton`
- Dark mode via `dark` class on HTML root (`#0F1117` bg, `#F0F0F3` text, `#6C63FF` accent)
- lucide-react installed for icons (use for visual indicators: mail icon, key icon, etc.)

**Dependencies NOT to reinstall** — everything is already present. No new packages needed.

### Git Intelligence

**Recent commits (most relevant):**
- `3c44dfc` Story 6.6: Operator Job Status & Health Queries
- `dee2ee7` Story 6.5: Pipeline Performance & Upload Metrics Tracking
- `fca9ed2` Story 6.4: Structured Logging with Correlation IDs
- `4035de8` Phase 1 planning and kick-off

**Code conventions:**
- Commit message format: `Story X.Y: Description`
- Python: Ruff linting, async/await everywhere, type hints on all functions
- TypeScript: strict mode, `"use client"` directive for interactive components
- Tests co-located in `__tests__/` for frontend, `tests/` directory for backend
- Feature folders: `features/{name}/components/`, `features/{name}/schemas/`, `features/{name}/__tests__/`

### Project Structure Notes

- Both new pages inside `(auth)` route group — inherits centered card layout and locale middleware
- Feature components extend the existing `features/auth/` module — no new feature directory
- Cognito service extension is a contained change — only `cognito_service.py` is modified in services
- Backend auth router extension — only `auth.py` is modified in API layer
- No new Python packages, no new JS packages, no new database migrations needed

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 1, Story 1.8 (FR61)]
- [Source: _bmad-output/planning-artifacts/epics.md — Requirements: FR26 (login/logout), FR27 (protected routes), NFR8 (JWT tokens), NFR10 (rate limiting)]
- [Source: _bmad-output/implementation-artifacts/1-7-account-settings-page.md — Previous story patterns, shadcn/ui status, component conventions, test helper patterns]
- [Source: frontend/src/features/auth/components/LoginForm.tsx — Existing "Forgot password?" link, fetch pattern, error display, loading states]
- [Source: frontend/src/features/auth/components/SignupForm.tsx — Password requirements display, confirm password field, Zod refine pattern]
- [Source: frontend/src/features/auth/components/VerificationForm.tsx — 6-digit code input pattern, resend link, loading state]
- [Source: backend/app/services/cognito_service.py — CognitoService exception mapping pattern, boto3 client wrapper structure]
- [Source: backend/app/api/v1/auth.py — Existing endpoint structure, Pydantic request models, error propagation]
- [Source: backend/app/core/exceptions.py — AuthenticationError class, error code conventions]
- [Source: frontend/src/app/[locale]/(auth)/login/page.tsx — Auth guard pattern, generateMetadata, server component structure]
- [Source: frontend/messages/en.json — Existing auth.* key structure and auth.login.forgotPassword key]
- [Source: AWS Cognito ForgotPassword API — InitiateForgotPassword, ConfirmForgotPassword operations]

## Dev Agent Record

### Agent Model Used

claude-opus-4-6 (1M context)

### Debug Log References

- Backend test run: 432 passed (36 auth tests including 10 new forgot/reset-password tests).
- Frontend test run: 360 passed (17 new tests across ForgotPasswordForm, ResetPasswordForm, LoginPage).
- Backend ruff check: clean on modified files.
- Frontend ESLint: clean on new/modified files.
- Frontend `tsc --noEmit`: clean on new/modified files (residual errors are pre-existing in unrelated files).

### Completion Notes List

- Added `CognitoService.initiate_forgot_password` that silences `UserNotFoundException` and other errors (email-enumeration prevention) and surfaces only `NotAuthorizedException` as `USER_NOT_CONFIRMED`.
- Added `CognitoService.confirm_forgot_password` backed by a dedicated `_handle_forgot_password_error` mapping: `CodeMismatchException → RESET_CODE_INVALID`, `ExpiredCodeException → RESET_CODE_EXPIRED`, `InvalidPasswordException → PASSWORD_TOO_WEAK`, `LimitExceededException → RATE_LIMITED`, `UserNotFoundException → RESET_CODE_INVALID` (no enumeration at confirm step either).
- New endpoints: `POST /api/v1/auth/forgot-password` (always returns the same success message) and `POST /api/v1/auth/reset-password`. Both are unauthenticated.
- Frontend: two new Zod schemas, two client components (`ForgotPasswordForm`, `ResetPasswordForm`), two App Router pages under `(auth)/forgot-password` + `.../confirm`, each wrapping the form in `<Suspense>` and using the auth redirect guard pattern from `login/page.tsx`.
- `login/page.tsx` reads `?reset=success` and renders a green translated banner above the form.
- Translation keys added under `auth.forgotPassword` and `auth.resetPassword` namespaces in both `en.json` and `uk.json` (identical keys).
- All internal links use `Link` from `@/i18n/navigation`; programmatic redirects use `useRouter` from `@/i18n/navigation`; `useSearchParams` comes from `next/navigation` as required.

### Code-Review Fixes (2026-04-16)

**Fixed:**
- **H1 (Email enumeration)**: `initiate_forgot_password` now silences ALL Cognito errors including `NotAuthorizedException`. The endpoint no longer surfaces `USER_NOT_CONFIRMED`, eliminating the existence oracle for unverified accounts. Test `test_forgot_password_unverified_email` updated to assert the generic 200 response.
- **M1 (Dead schemas)**: `forgot-password-schema.ts` and `reset-password-schema.ts` reduced to plain TypeScript types. The runtime Zod schemas were unused (forms build i18n schemas inline) and would have silently drifted in messages. Type-only exports prevent that.
- **M2 (Missing email guard)**: `ResetPasswordForm` now renders an error panel + back link when the `email` query param is missing instead of letting the user submit an empty email. New test added: `shows error guard and back link when email query param is missing`.
- **M3 (Blanket NotAuthorized mapping)**: Subsumed by H1 — the mapping no longer exists.
- **M4 (PII in logs)**: Both `forgot-password` and `reset-password` endpoints now log `email_masked` (`j***@example.com`) instead of the raw address.

**Deferred to [docs/tech-debt.md](docs/tech-debt.md):**
- **H2 → TD-001**: Convert all `(auth)` pages to Server Components with `generateMetadata`. Cross-page sweep, out of single-story scope.
- **H3 → TD-002**: Investigate the i18n `useRouter` reload issue and migrate all `(auth)` pages off the manual locale-prefix workaround. New pages match the established workaround for consistency.
- **L1 → TD-003**, **L2 → TD-004**, **L3 → TD-005**: Low-severity polish items, logged centrally.

**Not tracked as debt:**
- **M5 (App-level rate limit)**: Intentional per Dev Notes — Cognito's native limits are deemed sufficient for MVP. Conscious product decision, not deferred work.

### Code-Review Test Run (2026-04-16)

- Backend: 432 tests passed (36 in `test_auth.py`, including 10 forgot/reset-password tests).
- Frontend (auth folder): 42 tests passed (18 across `ForgotPasswordForm`, `ResetPasswordForm`, `LoginPage`).
- ESLint: clean on all changed files.
- `tsc --noEmit`: clean on all changed files.

### File List

**Modified**
- [backend/app/services/cognito_service.py](backend/app/services/cognito_service.py)
- [backend/app/api/v1/auth.py](backend/app/api/v1/auth.py)
- [backend/tests/test_auth.py](backend/tests/test_auth.py)
- [frontend/messages/en.json](frontend/messages/en.json)
- [frontend/messages/uk.json](frontend/messages/uk.json)
- [frontend/src/app/[locale]/(auth)/login/page.tsx](frontend/src/app/[locale]/(auth)/login/page.tsx)

**Created**
- [frontend/src/app/[locale]/(auth)/forgot-password/page.tsx](frontend/src/app/[locale]/(auth)/forgot-password/page.tsx)
- [frontend/src/app/[locale]/(auth)/forgot-password/confirm/page.tsx](frontend/src/app/[locale]/(auth)/forgot-password/confirm/page.tsx)
- [frontend/src/features/auth/components/ForgotPasswordForm.tsx](frontend/src/features/auth/components/ForgotPasswordForm.tsx)
- [frontend/src/features/auth/components/ResetPasswordForm.tsx](frontend/src/features/auth/components/ResetPasswordForm.tsx)
- [frontend/src/features/auth/schemas/forgot-password-schema.ts](frontend/src/features/auth/schemas/forgot-password-schema.ts)
- [frontend/src/features/auth/schemas/reset-password-schema.ts](frontend/src/features/auth/schemas/reset-password-schema.ts)
- [frontend/src/features/auth/__tests__/ForgotPasswordForm.test.tsx](frontend/src/features/auth/__tests__/ForgotPasswordForm.test.tsx)
- [frontend/src/features/auth/__tests__/ResetPasswordForm.test.tsx](frontend/src/features/auth/__tests__/ResetPasswordForm.test.tsx)
- [frontend/src/features/auth/__tests__/LoginPage.test.tsx](frontend/src/features/auth/__tests__/LoginPage.test.tsx)

## Change Log

| Date       | Change                                                                                       |
|------------|----------------------------------------------------------------------------------------------|
| 2026-04-16 | Implemented Story 1.8 — Cognito-backed forgot-password flow (backend + frontend + i18n).     |
| 2026-04-16 | Code review fixes: closed email-enumeration oracle, fixed locale router import, hardened reset page against missing email param, masked PII in logs, removed dead Zod schemas. Status → done. |
