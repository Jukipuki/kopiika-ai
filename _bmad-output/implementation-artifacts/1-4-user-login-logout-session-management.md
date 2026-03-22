# Story 1.4: User Login, Logout & Session Management

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user,
I want to log in and log out securely with proper session management,
So that my financial data is protected.

## Acceptance Criteria

1. **Given** I have a verified account, **When** I enter correct email and password, **Then** I am authenticated via Cognito, receive JWT tokens (access < 15 min, refresh with rotation), and am redirected to the main app

2. **Given** I am logged in, **When** I click logout, **Then** my session is terminated, tokens are invalidated, and I am redirected to the login page

3. **Given** I am logged in and inactive for 30 minutes, **When** the session timeout triggers, **Then** I am automatically logged out and prompted to re-authenticate

4. **Given** an IP address has attempted 10 failed logins in 15 minutes, **When** another login attempt is made from that IP, **Then** the attempt is rate-limited and a retry-after message is shown

## Tasks / Subtasks

- [x]Task 1: Backend Login Endpoint (AC: #1, #4)
  - [x]1.1 Add `authenticate_user(email, password)` to `CognitoService` using `admin_initiate_auth()` with backend client (`ADMIN_USER_PASSWORD_AUTH` flow)
  - [x]1.2 Add Cognito login error mapping: `NotAuthorizedException` → 401 INVALID_CREDENTIALS, `UserNotConfirmedException` → 403 EMAIL_NOT_VERIFIED, `UserNotFoundException` → 401 INVALID_CREDENTIALS (same as wrong password to prevent enumeration), `PasswordResetRequiredException` → 403 PASSWORD_RESET_REQUIRED
  - [x]1.3 Create `POST /api/v1/auth/login` endpoint — accepts `{email, password}`, calls `cognito_service.authenticate_user()`, returns `{accessToken, refreshToken, expiresIn, user: {id, email, locale}}`
  - [x]1.4 Implement IP-based rate limiting with Redis: track failed attempts per IP, limit to 10 per 15 min, return 429 with `Retry-After` header and `RATE_LIMITED` error code
  - [x]1.5 Create or update user record on first login: if User with matching `cognito_sub` doesn't exist in DB, create one (handles case where user registered before local DB existed)

- [x]Task 2: Backend Token Refresh & Profile Endpoints (AC: #1, #3)
  - [x]2.1 Add `refresh_tokens(refresh_token)` to `CognitoService` using `admin_initiate_auth()` with `REFRESH_TOKEN_AUTH` flow
  - [x]2.2 Create `POST /api/v1/auth/refresh-token` endpoint — accepts `{refreshToken}`, returns new `{accessToken, expiresIn}`
  - [x]2.3 Create `GET /api/v1/auth/me` endpoint — requires auth via `get_current_user` dependency, returns user profile `{id, email, locale, isVerified, createdAt}`

- [x]Task 3: Backend Logout Endpoint (AC: #2)
  - [x]3.1 Add `global_sign_out(access_token)` to `CognitoService` — calls Cognito `admin_user_global_sign_out()` to invalidate all refresh tokens
  - [x]3.2 Create `POST /api/v1/auth/logout` endpoint — requires auth, calls `global_sign_out`, returns `{message: "Logged out successfully"}`

- [x]Task 4: Frontend Login Page & Form (AC: #1, #4)
  - [x]4.1 Create `login-schema.ts` in `features/auth/schemas/` — Zod schema: email (valid email), password (min 1 char, no complexity check on login)
  - [x]4.2 Create `LoginForm.tsx` in `features/auth/components/` — email + password fields, RHF + zodResolver, onBlur validation, error display for server errors (invalid credentials, rate limited, email not verified), loading state on submit button
  - [x]4.3 Create login page at `app/[locale]/(auth)/login/page.tsx` — renders LoginForm, link to signup page, link to forgot-password (placeholder)
  - [x]4.4 Handle login API call: POST to backend `/api/v1/auth/login`, on success call NextAuth `signIn("credentials")` to establish session, on error display user-friendly message
  - [x]4.5 Handle rate limit error: display "Too many login attempts. Please try again in X minutes." with countdown timer, disable submit button

- [x]Task 5: NextAuth Credentials Provider Integration (AC: #1)
  - [x]5.1 Add `CredentialsProvider` to NextAuth config in `next-auth-config.ts` — `authorize()` callback calls backend `/api/v1/auth/login`, returns user object with tokens
  - [x]5.2 Update JWT callback to handle credentials provider tokens (accessToken, refreshToken, expiresAt)
  - [x]5.3 Implement token refresh in JWT callback: check `expiresAt`, if expired call backend `/api/v1/auth/refresh-token` with refreshToken, update session tokens
  - [x]5.4 Update `pages` config: set `signIn: "/[locale]/(auth)/login"` instead of `/signup`

- [x]Task 6: Frontend Logout Flow (AC: #2)
  - [x]6.1 Create logout button component or add logout action to dashboard layout header/nav
  - [x]6.2 On click: call backend `POST /api/v1/auth/logout` (to invalidate Cognito tokens), then call NextAuth `signOut({ callbackUrl: "/en/login" })`
  - [x]6.3 Show success toast via Sonner: "You've been logged out successfully" (auto-dismiss 4s)

- [x]Task 7: Session Timeout & Inactivity Detection (AC: #3)
  - [x]7.1 Create `useIdleTimeout` hook in `features/auth/hooks/` — tracks mouse, keyboard, touch, scroll events; resets timer on activity; triggers callback after 30 min of inactivity
  - [x]7.2 Integrate `useIdleTimeout` in dashboard layout — on timeout: show session-expired dialog, then sign out
  - [x]7.3 Create session-expired dialog component: "Your session has expired due to inactivity. Please log in again." with "Log in" button

- [x]Task 8: Update AuthGuard & Navigation (AC: #1, #2)
  - [x]8.1 Update `auth-guard.tsx` redirect target from `/signup` to `/login`
  - [x]8.2 Update NextAuth `pages.signIn` from `/en/signup` to `/en/login`
  - [x]8.3 Add "Already have an account? Log in" link on signup page
  - [x]8.4 Add "Don't have an account? Sign up" link on login page
  - [x]8.5 Handle post-login redirect: if user was redirected to login from a protected route, redirect back to intended destination after successful login (use `callbackUrl` parameter)

- [x]Task 9: Backend Tests (AC: #1, #2, #3, #4)
  - [x]9.1 Test login success with valid credentials → 200 + tokens
  - [x]9.2 Test login with invalid password → 401 INVALID_CREDENTIALS
  - [x]9.3 Test login with unverified email → 403 EMAIL_NOT_VERIFIED
  - [x]9.4 Test login with non-existent email → 401 INVALID_CREDENTIALS (no enumeration)
  - [x]9.5 Test rate limiting → 429 RATE_LIMITED after 10 failed attempts
  - [x]9.6 Test token refresh → 200 + new access token
  - [x]9.7 Test token refresh with invalid token → 401
  - [x]9.8 Test GET /me with valid token → 200 + user profile
  - [x]9.9 Test GET /me without token → 401
  - [x]9.10 Test logout → 200

- [x]Task 10: Frontend Tests (AC: #1, #2, #4)
  - [x]10.1 LoginForm renders email and password fields
  - [x]10.2 Email validation on blur shows error for invalid email
  - [x]10.3 Form submission calls login API with correct payload
  - [x]10.4 Invalid credentials error displays user-friendly message
  - [x]10.5 Rate limit error displays countdown timer
  - [x]10.6 Successful login redirects to dashboard

## Dev Notes

### Critical Architecture Decisions

- **Auth flow**: Frontend LoginForm → Backend API `/api/v1/auth/login` → Cognito `admin_initiate_auth()` → tokens returned → NextAuth CredentialsProvider creates session. This is consistent with Story 1.3's signup flow (frontend → backend → Cognito).
- **Backend Cognito client** has `ALLOW_ADMIN_USER_PASSWORD_AUTH` + `ALLOW_REFRESH_TOKEN_AUTH` enabled. Use `admin_initiate_auth()` with `AuthFlow='ADMIN_USER_PASSWORD_AUTH'` for login.
- **Frontend Cognito client** has `ALLOW_USER_SRP_AUTH`. Story 1.3 deferred direct SRP integration; Story 1.4 continues using backend API approach for consistency.
- **NextAuth session strategy**: JWT (not database). Tokens stored in encrypted HttpOnly cookies.
- **User enumeration prevention**: Return identical 401 error for both "wrong password" and "user not found" — never reveal whether an email is registered via the login endpoint.
- **Forgot password**: Out of scope for 1.4 (architecture shows `forgot-password/page.tsx` planned). Add placeholder link on login page pointing to `/forgot-password`.
- **Next.js 16 breaking change**: `middleware.ts` renamed to `proxy.ts`, exported function renamed from `middleware` to `proxy`. If adding auth middleware, use `proxy.ts`.

### Technical Requirements

- **JWT access tokens**: < 15 min expiry (Cognito configured: 15 min)
- **Refresh tokens**: 30 day expiry with rotation (Cognito configured)
- **Session timeout**: 30 min inactivity — implement via frontend idle detection hook, NOT server-side session tracking
- **Rate limiting**: 10 failed login attempts per IP per 15 min via Redis. Use sorted set or sliding window counter pattern. Key format: `rate_limit:login:{ip}`. TTL: 15 min.
- **Token refresh**: NextAuth JWT callback checks `expiresAt`. When token expired, call backend `/api/v1/auth/refresh-token`. If refresh fails (token revoked/expired), force logout.
- **CORS**: Already configured to allow Authorization header from frontend domain

### Architecture Compliance

- **API prefix**: `/api/v1/auth/` — extend existing router in `api/v1/router.py`
- **Response format**: Success → `{accessToken, refreshToken, expiresIn, user: {...}}`. Error → `{"error": {"code": "ERROR_CODE", "message": "...", "details": {...}}}`
- **JSON field naming**: `camelCase` via Pydantic `alias_generator=to_camel`
- **HTTP status codes**: 200 (login success), 401 (invalid credentials/token), 403 (unverified/forbidden), 429 (rate limited)
- **Error handling**: Use existing `AuthenticationError` exception class from `core/exceptions.py`. Add new error codes: `INVALID_CREDENTIALS`, `EMAIL_NOT_VERIFIED`, `PASSWORD_RESET_REQUIRED`, `RATE_LIMITED`, `TOKEN_REFRESH_FAILED`
- **Dependency injection**: Use existing `get_db()`, `get_current_user()`, `get_cognito_service()` from `api/deps.py`
- **Structured logging**: Log all login attempts (success/failure) with `user_id` (if known), `ip`, `action`, `timestamp` using JSON format from `core/logging.py`

### Library & Framework Requirements

| Library | Version | Purpose | Notes |
|---|---|---|---|
| `next-auth` | `@beta` (5.0.0-beta.30) | Session management, CredentialsProvider | Already installed. Add CredentialsProvider alongside existing CognitoProvider |
| `amazon-cognito-identity-js` | 6.3.16 | Cognito SDK (installed, unused for now) | Keep for future SRP migration; not used in 1.4 |
| `react-hook-form` | 7.71.2 | Form state management | Already installed |
| `zod` | 4.3.6 | Schema validation | Already installed |
| `@hookform/resolvers` | 5.2.2 | Zod resolver for RHF | Already installed |
| `boto3` | latest | Cognito `admin_initiate_auth()` | Already installed |
| `python-jose[cryptography]` | latest | JWT verification | Already installed |
| `redis` / `aioredis` | latest | Rate limiting storage | **May need to add** — check if Redis client is already a dependency. Use `redis.asyncio` for async Redis operations |
| `sonner` | latest | Toast notifications (logout success) | **Check if installed**, otherwise add |

**Do NOT use:** `aws-amplify` (too heavy, architecture chose direct SDK), `fastapi-cloudauth` (manual JWKS preferred for debuggability)

### File Structure Requirements

**New files to create:**

```
backend/
├── app/api/v1/auth.py              # MODIFY — add login, logout, refresh-token, me endpoints
├── app/services/cognito_service.py  # MODIFY — add authenticate_user(), refresh_tokens(), global_sign_out()
├── app/services/rate_limiter.py     # CREATE — Redis-based IP rate limiting service
├── app/core/redis.py                # CREATE — Redis client initialization (if not exists)
├── tests/test_auth.py               # MODIFY — add login/logout/refresh/me/rate-limit tests

frontend/
├── src/app/[locale]/(auth)/login/page.tsx                    # CREATE — login page
├── src/features/auth/components/LoginForm.tsx                 # CREATE — login form component
├── src/features/auth/components/SessionExpiredDialog.tsx      # CREATE — session timeout dialog
├── src/features/auth/schemas/login-schema.ts                  # CREATE — Zod login validation
├── src/features/auth/hooks/use-idle-timeout.ts                # CREATE — inactivity detection hook
├── src/features/auth/__tests__/LoginForm.test.tsx             # CREATE — login form tests
├── src/lib/auth/next-auth-config.ts                           # MODIFY — add CredentialsProvider, update pages
├── src/lib/auth/auth-guard.tsx                                # MODIFY — redirect to /login
├── src/app/[locale]/(auth)/signup/page.tsx                    # MODIFY — add "Already have account?" link
├── src/app/[locale]/(dashboard)/layout.tsx                    # MODIFY — add logout button, integrate idle timeout
```

**Existing files to reuse (DO NOT recreate):**
- `backend/app/core/security.py` — JWT verification via JWKS (ready to use)
- `backend/app/core/exceptions.py` — AuthenticationError, RegistrationError (extend with new codes)
- `backend/app/core/config.py` — Cognito settings (already has all needed env vars)
- `backend/app/api/deps.py` — `get_current_user()`, `get_db()`, `get_cognito_service()`
- `backend/app/models/user.py` — User model with cognito_sub lookup
- `frontend/src/features/auth/hooks/use-auth.ts` — `useAuth()` hook (ready to use)
- `frontend/src/types/next-auth.d.ts` — NextAuth type extensions

### Testing Requirements

**Backend tests** (pytest + httpx AsyncClient):
- Mirror existing `tests/conftest.py` fixtures: async SQLite engine, mock Cognito service, HTTP client
- Add mock for Redis rate limiter
- Mock Cognito `admin_initiate_auth()` responses (success with tokens, NotAuthorizedException, UserNotConfirmedException)
- All existing 15 tests from stories 1.1-1.3 MUST continue to pass

**Frontend tests** (Vitest + React Testing Library):
- Mirror existing `SignupForm.test.tsx` patterns: render, userEvent, mock fetch
- Mock `signIn` from NextAuth for login flow testing
- Use `vi.mock()` for API calls and NextAuth functions

**E2E considerations** (Playwright, optional for this story):
- Login → dashboard flow
- Logout → login redirect
- Invalid credentials error display

### Previous Story Intelligence (from Story 1.3)

**Critical bugs fixed in 1.3 — DO NOT reintroduce:**
- `security.py:64` — JWT decode used wrong variable `key` instead of `rsa_key`. Already fixed.
- `cognito_service.py` — `_handle_cognito_error()` must be typed `-> NoReturn`, not `-> None`
- Always update `user.updated_at = datetime.now(UTC)` when modifying user records (not deprecated `utcnow()`)
- All imports at top level — no inline `from sqlmodel import select` inside functions
- Pydantic request models MUST have field validation (e.g., `min_length` for password)

**Patterns established in 1.3 to follow:**
- `CognitoService` methods: wrap boto3 calls in try/except, map `ClientError` to app exceptions via `_handle_cognito_error()`
- Auth endpoint pattern: validate input → call cognito_service → update DB → return response
- Frontend form pattern: Zod schema → RHF with zodResolver → onBlur validation → fetch to backend API → handle errors
- Error display: coral red border on input + error message below field; server errors as alert banner above form
- Test pattern: mock cognito service, use async SQLite, test both success and error paths

**Dependencies already installed — do NOT reinstall:**
- Backend: boto3, python-jose[cryptography], pydantic[email], httpx, pytest-asyncio, aiosqlite
- Frontend: next-auth@beta, @auth/core, amazon-cognito-identity-js, react-hook-form, @hookform/resolvers, zod, vitest, @testing-library/*

### Git Intelligence

**Recent commits:**
- `3ded222` Story 1.3: AWS Cognito Integration & User Registration
- `a6c15bc` Story 1.2: AWS Infrastructure Provisioning
- `720d284` Initial commit

**Code conventions from recent work:**
- Commit message format: `Story X.Y: Description`
- Python: Ruff for linting, async/await everywhere, type hints on all functions
- TypeScript: `"use client"` directive for interactive components, strict mode
- Tests: co-located for frontend (`__tests__/`), separate `tests/` for backend

### Latest Technical Information

- **Auth.js v5 (NextAuth)**: Still in beta (v5.0.0-beta.30) but production-ready and widely used. Auth.js is now maintained by Better Auth team. Use `next-auth@beta` for installation. API is stable.
- **Next.js 16**: `middleware.ts` renamed to `proxy.ts` with `proxy` exported function. If creating auth proxy for route protection, use `proxy.ts` not `middleware.ts`.
- **Cognito SRP**: `amazon-cognito-identity-js` remains the recommended SDK for client-side SRP. For this story, using backend `admin_initiate_auth()` for consistency with signup flow.
- **Redis async**: Use `redis.asyncio` (built into `redis` package v4.2+) for async Redis operations in FastAPI.

### Project Structure Notes

- Alignment with unified project structure: all auth files go in `features/auth/` (frontend) and `api/v1/auth.py` + `services/cognito_service.py` (backend)
- No new top-level directories needed
- Rate limiter service goes in `services/rate_limiter.py` following existing service pattern

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 1, Story 1.4]
- [Source: _bmad-output/planning-artifacts/architecture.md — Authentication & Security, API Patterns, Frontend State Management]
- [Source: _bmad-output/planning-artifacts/prd.md — NFR8 (JWT), NFR9 (Session timeout), NFR10 (Rate limiting), Security Requirements]
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md — Form patterns, Error states, Accessibility, Responsive design]
- [Source: _bmad-output/implementation-artifacts/1-3-aws-cognito-integration-user-registration.md — Previous story learnings, Code patterns, Bug fixes]
- [Source: infra/terraform/ — Cognito configuration (SRP auth, token expiry, password policy)]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (claude-opus-4-6)

### Debug Log References

- All 25 backend tests passed (7 existing + 10 new login/logout/refresh/me + 8 structure/health)
- All 12 frontend tests passed (6 existing SignupForm + 6 new LoginForm)
- Backend linting (Ruff): All checks passed
- Frontend linting (ESLint): All checks passed

### Completion Notes List

- Implemented full login flow: Frontend LoginForm → Backend `/api/v1/auth/login` → Cognito `admin_initiate_auth()` → JWT tokens → NextAuth CredentialsProvider session
- Added IP-based rate limiting via Redis sorted set (10 attempts/15 min window), returns 429 with Retry-After header
- User enumeration prevention: identical 401 for wrong password and non-existent user
- Implemented token refresh in NextAuth JWT callback: auto-refreshes expired access tokens via backend `/api/v1/auth/refresh-token`
- Logout flow: calls backend `global_sign_out` to invalidate Cognito tokens, then NextAuth `signOut`, shows Sonner toast
- Session timeout: `useIdleTimeout` hook tracks mouse/keyboard/touch/scroll/click events, shows SessionExpiredDialog after 30 min inactivity
- AuthGuard now redirects to `/login` with `callbackUrl` for post-login redirect back to intended page
- Added navigation links between signup and login pages
- Installed `sonner` for toast notifications
- Created user on first login (subtask 1.5) for users who may exist in Cognito but not in local DB

### File List

**New files:**
- backend/app/core/redis.py — Redis client initialization
- backend/app/services/rate_limiter.py — IP-based rate limiting service
- frontend/src/features/auth/schemas/login-schema.ts — Zod login validation schema
- frontend/src/features/auth/components/LoginForm.tsx — Login form component
- frontend/src/features/auth/components/SessionExpiredDialog.tsx — Session timeout dialog
- frontend/src/features/auth/hooks/use-idle-timeout.ts — Inactivity detection hook
- frontend/src/app/[locale]/(auth)/login/page.tsx — Login page
- frontend/src/features/auth/__tests__/LoginForm.test.tsx — Login form tests

**Modified files:**
- backend/app/services/cognito_service.py — Added authenticate_user(), refresh_tokens(), global_sign_out(), _handle_auth_error()
- backend/app/api/v1/auth.py — Added login, refresh-token, me, logout endpoints with request/response models
- backend/app/api/deps.py — Added get_rate_limiter dependency
- backend/app/core/exceptions.py — Updated authentication_error_handler for Retry-After header
- backend/tests/conftest.py — Added mock_rate_limiter fixture, extended mock_cognito_service
- backend/tests/test_auth.py — Added 10 new tests for login/logout/refresh/me/rate-limit
- frontend/src/lib/auth/next-auth-config.ts — Added CredentialsProvider, token refresh, updated pages config
- frontend/src/lib/auth/auth-guard.tsx — Redirect to /login with callbackUrl
- frontend/src/types/next-auth.d.ts — Added error and locale to session/JWT types
- frontend/src/app/layout.tsx — Added Sonner Toaster component
- frontend/src/app/[locale]/(auth)/signup/page.tsx — Added "Already have account? Log in" link
- frontend/src/app/[locale]/(dashboard)/layout.tsx — Added logout button, idle timeout, session-expired dialog
- frontend/package.json — Added sonner dependency

## Change Log

- 2026-03-22: Story 1.4 implementation complete — login, logout, session management, token refresh, rate limiting, idle timeout, navigation updates, 10 backend tests, 6 frontend tests
- 2026-03-22: Code review fixes applied (7 issues: 4 HIGH, 3 MEDIUM):
  - H1: Fixed refresh_tokens() to include SECRET_HASH when backend client has a secret
  - H2: Removed "Continue session" from SessionExpiredDialog to comply with AC#3 (auto-logout)
  - H3: Added structured logging (login success/failure, logout) with ip/user_id/action fields
  - H4: Fixed IP extraction to use X-Forwarded-For header before request.client fallback
  - M1: Replaced hardcoded /en/ locale with dynamic locale extraction in all auth redirects
  - M2: Added TokenRefreshFailed handling in useAuth — treats expired session as unauthenticated
  - M3: Added test assertions verifying rate limiter interactions on login success/failure
  - L2: Refactored logout to pass cognito_sub directly instead of re-parsing access token
