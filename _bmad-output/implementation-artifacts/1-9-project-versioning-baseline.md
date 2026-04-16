# Story 1.9: Project Versioning Baseline

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer and operator**,
I want a documented semver scheme with a single source-of-truth `VERSION` file surfaced in the API and authenticated UI,
So that every deployed build is unambiguously identifiable, support conversations can reference a known version, and contributors share one bump convention.

## Acceptance Criteria

1. **Given** the repo root, **When** I open the codebase, **Then** I find a `/VERSION` file containing exactly the line `1.2.0` followed by a trailing newline (no leading `v`, no extra whitespace).

2. **Given** I read [docs/versioning.md](docs/versioning.md), **When** I look up the policy, **Then** I find: `MAJOR` = phase boundary, `MINOR` = story merged (any epic), `PATCH` = bug-fix or polish change with no new user-facing functionality. The doc explicitly states that version digits are NOT mapped to epic numbers — versions increment monotonically.

3. **Given** I `GET /health`, **When** the backend responds, **Then** the JSON body's `version` field equals the contents of `/VERSION` at runtime (read from file, not from a hardcoded string in code).

4. **Given** I am authenticated and viewing any dashboard route, **When** the page renders, **Then** I see a muted `v1.2.0` badge in a persistent footer/chrome element visible across all authenticated, non-onboarding pages.

5. **Given** I am on a public route (login, signup, forgot-password, marketing) OR on an onboarding route, **When** the page renders, **Then** the version badge is NOT shown.

6. **Given** the backend test suite, **When** I run it, **Then** the existing `test_health_endpoint` test reads `/VERSION` at test time and asserts the response matches it (no hardcoded version string in tests — drift-proof).

7. **Given** the frontend test suite, **When** I run it, **Then** the new `AppVersionBadge` component test asserts `v{NEXT_PUBLIC_APP_VERSION}` text renders.

## Tasks / Subtasks

- [x] Task 1: Repo-level versioning artifacts (AC: #1, #2)
  - [x] 1.1 Create `/VERSION` at repo root containing exactly `1.2.0\n`. Single line, no leading `v`, single trailing newline.
  - [x] 1.2 Create `/docs/versioning.md` with the policy:
    - `MAJOR` bump on phase boundary (Phase 1 → Phase 2 = `1.x.x` → `2.0.0`).
    - `MINOR` bump per story merged, regardless of which epic owns it.
    - `PATCH` bump for bug-fix or polish stories with no new user-facing functionality.
    - Versions increase monotonically; version digits do NOT encode epic numbers.
    - Bumps happen in the same PR that closes a story (manual edit to `/VERSION` for now).
    - Baseline: `1.1.0` reflects state after Story 1.8 merged. Story 1.9 (this story) bumps to `1.2.0`.
    - Future automation (bump scripts, CHANGELOG, git tags) is tracked in [docs/tech-debt.md](docs/tech-debt.md) and separate stories.
  - [x] 1.3 Add a one-paragraph "Versioning" section to `README.md` pointing to `docs/versioning.md` and explaining how to bump.

- [x] Task 2: Backend — read VERSION from file (AC: #3, #6)
  - [x] 2.1 Create `backend/app/core/version.py` exporting `APP_VERSION: str`. Read `/VERSION` once at module import using `pathlib`, walking up from the file's location until the file is found (so it works whether tests run from `backend/` or repo root). Strip whitespace. If not found (defensive), default to `"0.0.0+unknown"` and log a warning — do NOT crash.
  - [x] 2.2 Replace the hardcoded `VERSION: str = "0.1.0"` in `backend/app/core/config.py` (line 9) by importing `APP_VERSION` from `app.core.version` and re-exporting it on `settings.VERSION`. Existing call sites (`app/main.py:51` reads `settings.VERSION`) keep working without changes.
  - [x] 2.3 Update `backend/tests/test_health.py`: drop the hardcoded `"0.1.0"` assertion. Read `/VERSION` in the test (use the same `app.core.version.APP_VERSION` for parity) and assert the endpoint returns it.

- [x] Task 3: Frontend — read VERSION at build, render in dashboard chrome (AC: #4, #5, #7)
  - [x] 3.1 In `frontend/next.config.ts`: read `/VERSION` from the repo root at build time using `node:fs` + `node:path`. Inject as `NEXT_PUBLIC_APP_VERSION` via the `env` config option. Default to `"0.0.0+dev"` if file missing (defensive — avoid build failures in detached frontend builds).
  - [x] 3.2 Create `frontend/src/components/AppVersionBadge.tsx` (`"use client"`). Renders `v{process.env.NEXT_PUBLIC_APP_VERSION}` in muted small text (`text-xs text-foreground/40`). Accepts an optional `className` prop for placement tweaks. No i18n needed — version strings are universal.
  - [x] 3.3 Mount `<AppVersionBadge />` in [frontend/src/app/[locale]/(dashboard)/layout.tsx](frontend/src/app/[locale]/(dashboard)/layout.tsx) inside the `{!isOnboardingRoute && (...)}` block (so it inherits the same hide-on-onboarding rule as the header). Position: bottom-left fixed (the upload FAB occupies bottom-right at line 110-118). Use `className="fixed bottom-2 left-2 z-40"` or similar — keep it out of click targets.
  - [x] 3.4 Create `frontend/src/components/__tests__/AppVersionBadge.test.tsx`. Stub `process.env.NEXT_PUBLIC_APP_VERSION = "9.9.9"`, render `<AppVersionBadge />`, assert `v9.9.9` text exists. Restore env after.

- [x] Task 4: Verify end-to-end (AC: #1, #3, #4)
  - [x] 4.1 Confirm `/VERSION` is `1.2.0`. (byte-verified: `1 . 2 . 0 \n`)
  - [x] 4.2 Backend: `test_health_endpoint` asserts `/health` returns `APP_VERSION` (= `1.2.0`) via ASGITransport — functionally equivalent to the curl check. Left as the automated gate; live curl is a manual smoke check for the reviewer.
  - [x] 4.3 Manual browser verification is for the reviewer — not automatable here. Next.js production build (`npx next build`) succeeded and the string `1.2.0` was confirmed inlined into the `AppVersionBadge` component chunk; the badge is mounted inside the existing `!isOnboardingRoute` block so it inherits the onboarding-hide rule for free, and public `(auth)` routes render a separate layout with no dashboard chrome.
  - [x] 4.4 All 432 backend tests pass (incl. the updated `test_health_endpoint`).
  - [x] 4.5 All 363 frontend tests pass (40 files) — includes the new `AppVersionBadge` tests.

## Dev Notes

### Versioning Policy (the convention this story establishes)

- **MAJOR** — phase boundary. `1.x.x` → `2.0.0` when Phase 2 starts.
- **MINOR** — every story merged, any epic, any time. No relationship to epic numbers.
- **PATCH** — bug-fix or polish-only stories with no new user-visible functionality.
- Versions are **monotonic**. They never decrease. They do not encode planning structure (epic numbers, sprint numbers, etc.).
- Bumps happen in the **same PR** as the story being merged. The PR that closes a story modifies `/VERSION`.
- Baseline: **1.1.0** = state of project after Story 1.8 merged. This story (1.9) is itself a story, so on merge → **1.2.0**.

### Why a root `VERSION` file (not `package.json` / `pyproject.toml`)

- Monorepo with two languages — embedding the canonical version in either manifest forces the other to import or duplicate.
- Plain text at repo root is trivially readable from any tool, language, or shell script.
- Future automation (bump script, CI tag, changelog generator) reads/writes one file regardless of stack.
- Frontend's `package.json` `version` field can stay at its current value or be ignored — `NEXT_PUBLIC_APP_VERSION` is the source of truth for runtime.

### Why bottom-left for the badge

- Upload FAB occupies fixed bottom-right ([dashboard/layout.tsx:110-118](frontend/src/app/[locale]/(dashboard)/layout.tsx#L110-L118)).
- Bottom-left is empty across all current dashboard routes.
- Top-right is occupied by the header nav.
- Footer-bar approach (full-width strip) wastes vertical space on mobile.
- Fixed bottom-left, low-opacity, small font keeps it discoverable without competing with primary actions.

### Why hide on onboarding routes

- Onboarding intentionally strips dashboard chrome (header is also hidden — see line 62 condition). The version badge is operational metadata, not user-facing functionality; hiding it during onboarding keeps the flow clean.

### Existing scaffolding to reuse

- `/health` endpoint already exists at [backend/app/main.py:49-51](backend/app/main.py#L49-L51) and already returns `{"status", "version"}`. Just swap the source of `version` from hardcoded `settings.VERSION = "0.1.0"` to file-backed.
- Existing test at [backend/tests/test_health.py:16](backend/tests/test_health.py#L16) hardcodes `"0.1.0"` — that's the line to change.
- `next.config.ts` is currently a near-empty file ([frontend/next.config.ts](frontend/next.config.ts)) — adding the build-time env injection is a 5-line change.

### What's deferred (do NOT do in this story)

- `CHANGELOG.md` / release notes generation
- Bump automation (scripts, make targets, husky/lint-staged hooks)
- Git tag automation in CI on merge to main
- Version display in additional places (settings page, about page, support email signatures)
- Build hash / commit SHA in version string (`1.2.0+abc1234`)
- Linking version → git tag in the UI ("v1.2.0 → GitHub release")

These are good follow-ups; each gets its own story.

### Testing Requirements

- **Backend**: extend the existing health test (don't duplicate). Read `APP_VERSION` in the test for parity to catch drift. The test should fail if someone bumps `/VERSION` but not the file the endpoint reads from (impossible by design, but the test guards the wiring).
- **Frontend**: one isolated unit test for `AppVersionBadge`. No e2e — the unit test plus AC #4.3 manual check covers it.
- All existing 432+ backend and ~360 frontend tests must continue to pass.

### File Structure Requirements

**New files to create:**
```
/VERSION                                        # Single line: "1.2.0\n"
/docs/versioning.md                             # Policy doc
backend/app/core/version.py                     # Reads /VERSION → APP_VERSION
frontend/src/components/AppVersionBadge.tsx     # Renders v{version}
frontend/src/components/__tests__/AppVersionBadge.test.tsx  # Component test
```

**Files to modify:**
```
backend/app/core/config.py                      # Replace hardcoded VERSION with import from app.core.version
backend/tests/test_health.py                    # Read /VERSION dynamically instead of asserting "0.1.0"
frontend/next.config.ts                         # Read /VERSION → NEXT_PUBLIC_APP_VERSION via env
frontend/src/app/[locale]/(dashboard)/layout.tsx # Mount <AppVersionBadge /> inside !isOnboardingRoute block
README.md                                        # Add "Versioning" section pointing to docs/versioning.md
```

**Existing files to reuse (DO NOT recreate):**
- [backend/app/main.py](backend/app/main.py) — `/health` endpoint already returns version; no endpoint changes needed
- [backend/app/core/config.py](backend/app/core/config.py) — `settings.VERSION` already exists; just change the source
- [frontend/src/app/[locale]/(dashboard)/layout.tsx](frontend/src/app/[locale]/(dashboard)/layout.tsx) — already has `!isOnboardingRoute` chrome-hiding logic; mount the badge inside that conditional

### Library & Framework Requirements

No new packages. Use Node's built-in `node:fs` and `node:path` in `next.config.ts`. Use Python's `pathlib` (stdlib) in `backend/app/core/version.py`.

### References

- [Source: Conversation 2026-04-16 — versioning policy decision (story=minor, fix=patch, phase=major; monotonic; no epic encoding)]
- [Source: docs/tech-debt.md — central register where deferred follow-ups (CHANGELOG, automation, git tags) will be logged if not already there]
- [Source: backend/app/main.py — existing /health endpoint]
- [Source: backend/app/core/config.py — existing settings.VERSION location]
- [Source: backend/tests/test_health.py — existing test that hardcodes 0.1.0]
- [Source: frontend/next.config.ts — minimal config, easy to extend]
- [Source: frontend/src/app/[locale]/(dashboard)/layout.tsx — authenticated layout with onboarding-aware chrome]

## Dev Agent Record

### Agent Model Used

claude-opus-4-6 (1M context)

### Debug Log References

- Byte-level verification of `/VERSION`: `od -c` → `1 . 2 . 0 \n` (exactly one trailing newline, no BOM, no leading `v`).
- Next.js production build (`npx next build`) — confirmed the `1.2.0` string is inlined into the `AppVersionBadge` chunk as `let r="1.2.0"`, proving the `NEXT_PUBLIC_APP_VERSION` env was injected at build time and replaced at compile time (not deferred to runtime).
- Pre-existing lint/type errors in `frontend/src/lib/query/query-provider.tsx` and three test files are NOT introduced by this story — verified via `git stash` baseline run; no new lint or type errors in changed files.

### Completion Notes List

- **Single source of truth.** `/VERSION` (one-line, trailing newline) is the only place the `1.2.0` string lives in version-controlled code. Backend reads it via `pathlib` walk-up from `backend/app/core/version.py`; frontend reads it at build time in `next.config.ts` and injects `NEXT_PUBLIC_APP_VERSION`. Tests assert against the module that itself reads the file, so the wiring is drift-proof — bumping `/VERSION` propagates to endpoint, bundle, and both test suites on the next run without any test-side changes.
- **Defensive fallbacks, not crashes.** Backend falls back to `"0.0.0+unknown"` with a `logger.warning` if the file is missing (e.g., a pathological container layout). Frontend falls back to `"0.0.0+dev"` in `next.config.ts` so a detached frontend build doesn't fail when the repo root isn't present. Neither path is expected in normal operation.
- **`settings.VERSION` preserved.** The existing import surface (`settings.VERSION` consumed by `app/main.py:51` and the FastAPI `version=` kwarg on line 26) is untouched — only its *source* changed. Zero call-site churn.
- **Onboarding / public-route hiding is inherited, not duplicated.** `<AppVersionBadge />` is mounted inside the existing `{!isOnboardingRoute && (...)}` conditional in the dashboard layout, so AC #5's onboarding-hide requirement reuses the same predicate as the header. Public `(auth)` routes (login, signup, forgot-password) use a separate `(auth)/layout.tsx` that has no dashboard chrome at all — badge is physically absent there, not conditionally hidden.
- **Bottom-left positioning.** The badge uses `fixed bottom-2 left-2 z-40` (vs the upload FAB's `bottom-6 right-6 z-50`), so it sits below the FAB in z-order and out of its click-target zone. `pointer-events-none` prevents the badge from ever blocking clicks even if a future element lands on top of it.
- **Frontend test isolates env cleanly.** Uses `vi.stubEnv` + `vi.unstubAllEnvs` so the stubbed `NEXT_PUBLIC_APP_VERSION` never leaks into other tests in the suite. Added a second test for the `className` override contract to protect future placement tweaks.
- **Test suite results:** backend 432/432 ✓, frontend 363/363 ✓ (40 files, including the new 2 tests for `AppVersionBadge`).
- **Reviewer manual smoke list** (not automatable here, do as part of review):
  1. `curl http://localhost:8000/health` → expect `{"status":"healthy","version":"1.2.0"}`.
  2. `cd frontend && npm run dev`, log in, confirm muted `v1.2.0` in bottom-left on `/dashboard`, `/feed`, `/settings`, `/profile`, `/history`, `/upload`.
  3. Visit `/login`, `/signup`, `/forgot-password` → badge absent (different layout).
  4. Visit `/onboarding/privacy` → badge absent (same hide-on-onboarding rule as header).

### File List

**New:**
- `VERSION`
- `docs/versioning.md`
- `backend/app/core/version.py`
- `frontend/src/components/AppVersionBadge.tsx`
- `frontend/src/components/__tests__/AppVersionBadge.test.tsx`

**Modified:**
- `README.md` — added "Versioning" section linking to `docs/versioning.md`.
- `backend/app/core/config.py` — `VERSION` now reads from `app.core.version.APP_VERSION` instead of the hardcoded `"0.1.0"`.
- `backend/tests/test_health.py` — asserts against `APP_VERSION` instead of the hardcoded `"0.1.0"`, preventing future drift.
- `frontend/next.config.ts` — reads `/VERSION` at build time via `node:fs` + `node:path`, injects as `NEXT_PUBLIC_APP_VERSION` via `env`.
- `frontend/src/app/[locale]/(dashboard)/layout.tsx` — mounts `<AppVersionBadge />` inside the `!isOnboardingRoute` block.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — story status `ready-for-dev` → `in-progress` → `review`.

### Code Review — 2026-04-16

Adversarial review of the implementation against ACs #1–#7 surfaced 7 findings (1 HIGH, 3 MEDIUM, 3 LOW). HIGH + MEDIUM fixed inline; LOW documented but not actioned.

**HIGH — fixed**
- **H1: `test_health_endpoint` could not detect a missing `/VERSION` file.** Original test asserted `data["version"] == APP_VERSION`, but since `APP_VERSION` is itself the module-load fallback-aware value, a deleted or relocated `/VERSION` would collapse both the endpoint and the assertion to `"0.0.0+unknown"` and the test would still pass. AC #6 explicitly says *"reads /VERSION at test time"*. Fix: [backend/tests/test_health.py](backend/tests/test_health.py) now walks up from the test file to read `/VERSION` directly with `pathlib`, asserts the endpoint matches that value, AND asserts `APP_VERSION` itself matches (catches fallback-sentinel drift).

**MEDIUM — fixed**
- **M1: `settings.VERSION` was a pydantic-settings field and silently env-overridable.** A stray `VERSION` env var (easy to inject from a CI runner or PaaS) would override the file-backed source of truth. Fix: [backend/app/core/config.py](backend/app/core/config.py#L11) — `VERSION` is now declared as `ClassVar[str] = APP_VERSION`, so pydantic-settings no longer treats it as a readable field. Verified: `VERSION=99.99.99 python -c "from app.core.config import settings; print(settings.VERSION)"` → `1.2.0`. Call sites (`app/main.py:26, 51`) unchanged.
- **M2: `AppVersionBadge`'s `className` prop *replaced* default styling instead of extending it.** Any caller passing `className` silently lost `text-xs`, `text-foreground/40`, `pointer-events-none`. Fix: [frontend/src/components/AppVersionBadge.tsx](frontend/src/components/AppVersionBadge.tsx) now uses `cn()` (tailwind-merge) to merge caller classes on top of the default typography. The `"use client"` directive was also removed — the component has no hooks, state, or browser APIs and `process.env.NEXT_PUBLIC_APP_VERSION` is inlined at build time (bonus L1 cleanup that fell out of the same edit). Test updated: [AppVersionBadge.test.tsx](frontend/src/components/__tests__/AppVersionBadge.test.tsx) now asserts the merged behavior (`toContain("custom-placement")` + defaults still present).
- **M3: "fixed position ≠ footer" per AC #4 wording.** On reflection: `position: fixed` bottom-left is a widely accepted pattern for "chrome" — persistent and visible across all pages, which is what AC #4 actually requires. No change made; interpretation logged for future reference.

**LOW — not actioned**
- **L1** (implicitly resolved by M2): unnecessary `"use client"` on a zero-side-effect component — dropped as part of M2.
- **L2** → [TD-006](../../../docs/tech-debt.md) (fallback sentinels diverge across backend/frontend). Promoted to the tech-debt register because the fix has a clear shape and is worth opportunistic pickup.
- **L3**: task 3.3 text said "inside the `{!isOnboardingRoute && (...)}` block"; actual code mounts as a separate conditional with the same predicate. Functionally identical — story-local note only, not promoted (cosmetic task-text drift is not worth tracking in the debt register).

**Verification:**
- Backend: 432/432 tests pass (`pytest` — 140s), including the strengthened `test_health_endpoint`.
- Frontend: 363/363 tests pass (40 files, vitest), including the updated `AppVersionBadge.test.tsx` asserting merged-classname behavior.
- Manual: `settings.VERSION = "1.2.0"` still readable via existing call sites; a `VERSION` env var no longer overrides it.

## Change Log

| Date       | Change                                                                                       |
|------------|----------------------------------------------------------------------------------------------|
| 2026-04-16 | Story created (scoped post-1.8 code review with Oleh). Establishes semver baseline at 1.2.0. |
| 2026-04-16 | Implementation complete. VERSION file wired to backend `/health` and frontend dashboard badge. 432 backend + 363 frontend tests pass. Status → review. |
| 2026-04-16 | Code review complete. H1/M1/M2 fixed inline (test re-reads `/VERSION` directly; `settings.VERSION` now `ClassVar` to block env override; `AppVersionBadge` merges `className` via `cn()`). All tests still green. Status → done. |
