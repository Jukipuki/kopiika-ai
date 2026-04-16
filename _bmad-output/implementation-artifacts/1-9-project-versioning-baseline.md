# Story 1.9: Project Versioning Baseline

Status: ready-for-dev

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

- [ ] Task 1: Repo-level versioning artifacts (AC: #1, #2)
  - [ ] 1.1 Create `/VERSION` at repo root containing exactly `1.2.0\n`. Single line, no leading `v`, single trailing newline.
  - [ ] 1.2 Create `/docs/versioning.md` with the policy:
    - `MAJOR` bump on phase boundary (Phase 1 → Phase 2 = `1.x.x` → `2.0.0`).
    - `MINOR` bump per story merged, regardless of which epic owns it.
    - `PATCH` bump for bug-fix or polish stories with no new user-facing functionality.
    - Versions increase monotonically; version digits do NOT encode epic numbers.
    - Bumps happen in the same PR that closes a story (manual edit to `/VERSION` for now).
    - Baseline: `1.1.0` reflects state after Story 1.8 merged. Story 1.9 (this story) bumps to `1.2.0`.
    - Future automation (bump scripts, CHANGELOG, git tags) is tracked in [docs/tech-debt.md](docs/tech-debt.md) and separate stories.
  - [ ] 1.3 Add a one-paragraph "Versioning" section to `README.md` pointing to `docs/versioning.md` and explaining how to bump.

- [ ] Task 2: Backend — read VERSION from file (AC: #3, #6)
  - [ ] 2.1 Create `backend/app/core/version.py` exporting `APP_VERSION: str`. Read `/VERSION` once at module import using `pathlib`, walking up from the file's location until the file is found (so it works whether tests run from `backend/` or repo root). Strip whitespace. If not found (defensive), default to `"0.0.0+unknown"` and log a warning — do NOT crash.
  - [ ] 2.2 Replace the hardcoded `VERSION: str = "0.1.0"` in `backend/app/core/config.py` (line 9) by importing `APP_VERSION` from `app.core.version` and re-exporting it on `settings.VERSION`. Existing call sites (`app/main.py:51` reads `settings.VERSION`) keep working without changes.
  - [ ] 2.3 Update `backend/tests/test_health.py`: drop the hardcoded `"0.1.0"` assertion. Read `/VERSION` in the test (use the same `app.core.version.APP_VERSION` for parity) and assert the endpoint returns it.

- [ ] Task 3: Frontend — read VERSION at build, render in dashboard chrome (AC: #4, #5, #7)
  - [ ] 3.1 In `frontend/next.config.ts`: read `/VERSION` from the repo root at build time using `node:fs` + `node:path`. Inject as `NEXT_PUBLIC_APP_VERSION` via the `env` config option. Default to `"0.0.0+dev"` if file missing (defensive — avoid build failures in detached frontend builds).
  - [ ] 3.2 Create `frontend/src/components/AppVersionBadge.tsx` (`"use client"`). Renders `v{process.env.NEXT_PUBLIC_APP_VERSION}` in muted small text (`text-xs text-foreground/40`). Accepts an optional `className` prop for placement tweaks. No i18n needed — version strings are universal.
  - [ ] 3.3 Mount `<AppVersionBadge />` in [frontend/src/app/[locale]/(dashboard)/layout.tsx](frontend/src/app/[locale]/(dashboard)/layout.tsx) inside the `{!isOnboardingRoute && (...)}` block (so it inherits the same hide-on-onboarding rule as the header). Position: bottom-left fixed (the upload FAB occupies bottom-right at line 110-118). Use `className="fixed bottom-2 left-2 z-40"` or similar — keep it out of click targets.
  - [ ] 3.4 Create `frontend/src/components/__tests__/AppVersionBadge.test.tsx`. Stub `process.env.NEXT_PUBLIC_APP_VERSION = "9.9.9"`, render `<AppVersionBadge />`, assert `v9.9.9` text exists. Restore env after.

- [ ] Task 4: Verify end-to-end (AC: #1, #3, #4)
  - [ ] 4.1 Confirm `/VERSION` is `1.2.0`.
  - [ ] 4.2 Run backend: `curl http://localhost:8000/health` returns `version: "1.2.0"`.
  - [ ] 4.3 Run frontend dev server, log in, navigate to `/dashboard`, confirm `v1.2.0` badge visible bottom-left. Navigate to `/login`, confirm badge NOT visible. Navigate to `/onboarding`, confirm badge NOT visible.
  - [ ] 4.4 All existing backend tests (432+) continue to pass.
  - [ ] 4.5 All existing frontend tests (~360) continue to pass.

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

(populated by dev agent at implementation time)

### Debug Log References

(populated by dev agent at implementation time)

### Completion Notes List

(populated by dev agent at implementation time)

### File List

(populated by dev agent at implementation time)

## Change Log

| Date       | Change                                                                                       |
|------------|----------------------------------------------------------------------------------------------|
| 2026-04-16 | Story created (scoped post-1.8 code review with Oleh). Establishes semver baseline at 1.2.0. |
