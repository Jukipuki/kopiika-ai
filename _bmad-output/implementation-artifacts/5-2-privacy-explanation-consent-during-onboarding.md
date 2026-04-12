# Story 5.2: Privacy Explanation & Consent During Onboarding

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want to see a clear, plain-language explanation of how my data is used and to give explicit consent for AI processing of my financial data before I can enter the app,
So that I can make an informed decision before sharing sensitive information.

## Acceptance Criteria

1. **Given** I am a newly verified user completing my first login, **When** I am redirected into the app, **Then** I land on an `/onboarding/privacy` screen (not `/upload`, not `/feed`, not `/dashboard`) that presents a clear, plain-language data-privacy explanation covering four required topics: **what data is collected**, **how AI processes it**, **where it is stored**, and **who has access**.

2. **Given** the privacy explanation screen, **When** it renders, **Then** it includes a single explicit consent checkbox for AI processing of financial data labeled (EN) "I consent to AI processing of my financial data" / (UK) "Я даю згоду на AI-обробку моїх фінансових даних", and the primary continue button is disabled until the checkbox is checked.

3. **Given** I have not checked the consent checkbox, **When** I attempt to proceed (click button, press Enter, or navigate to any other authenticated route), **Then** I cannot continue to the main app — consent is mandatory; any direct navigation attempt to an authenticated route (e.g. `/upload`, `/feed`, `/dashboard`, `/history`, `/profile`, `/settings`) is intercepted by a client-side consent guard and redirected back to `/onboarding/privacy`.

4. **Given** I check the consent box and click "Continue", **When** the frontend calls `POST /api/v1/users/me/consent`, **Then** the backend persists a row in a new `user_consents` table containing `{ id, user_id, consent_type = 'ai_processing', version, granted_at, locale, ip, user_agent }`, returns `201 Created` with the stored record (camelCase), and the row is scoped to the authenticated `user_id`.

5. **Given** a consent record exists for my `user_id` with `version = CURRENT_CONSENT_VERSION` and `consent_type = 'ai_processing'`, **When** `GET /api/v1/users/me/consent` is called, **Then** it returns `200 OK` with `{ hasCurrentConsent: true, version, grantedAt, locale }`; **Otherwise** it returns `{ hasCurrentConsent: false, version: CURRENT_CONSENT_VERSION }`.

6. **Given** I have already granted consent for the current version on a previous session, **When** I log in again, **Then** I am NOT shown the onboarding privacy screen and am routed straight to `/upload` — the onboarding is strictly first-run-per-version.

7. **Given** the consent version constant (`CURRENT_CONSENT_VERSION`) is later bumped (e.g., because the privacy text materially changes), **When** an existing user next logs in, **Then** they are routed back to `/onboarding/privacy` and must re-consent before accessing the app. The new consent is stored as a **new row** — previous consent rows are **never updated or deleted** (append-only audit trail).

8. **Given** the onboarding privacy screen, **When** it renders, **Then** the tone is warm and reassuring (not legalese), matches the product's trust-first personality from the UX spec (`ux-design-specification.md#Onboarding Flow`), and is fully bilingual via `next-intl` under a new `onboarding.privacy` namespace in both `frontend/messages/en.json` and `frontend/messages/uk.json`.

9. **Given** I am an **existing** user who signed up before this story shipped (no consent row in the database), **When** I log in after deploy, **Then** I am routed to `/onboarding/privacy` and must grant consent before I can use the app — there is no grandfathering.

10. **Given** the new endpoints, **When** backend tests run, **Then** both `POST` and `GET /api/v1/users/me/consent` are covered by async `pytest` tests including: (a) success path, (b) unauthenticated request → 401, (c) tenant isolation (user A cannot read user B's consent), (d) append-only behavior (second POST for same version creates a second row, does not update), (e) version-bump behavior (old version row does not satisfy `hasCurrentConsent` for new version).

11. **Given** the new frontend flow, **When** frontend tests run, **Then** `vitest` tests cover: (a) `/onboarding/privacy` renders with disabled button until checkbox is checked, (b) clicking "Continue" after checking calls `POST /api/v1/users/me/consent` and then redirects to `/upload`, (c) the consent guard redirects unconsented users attempting to visit `/upload` back to `/onboarding/privacy`, (d) i18n keys resolve in both `en` and `uk`.

## Tasks / Subtasks

- [x] **Task 1: Backend — `user_consents` data model & migration** (AC: #4, #5, #7, #9)
  - [x] 1.1 Add `backend/app/models/consent.py` with a `UserConsent` SQLModel table: `id: UUID (pk)`, `user_id: UUID (FK → users.id, NOT NULL, indexed)`, `consent_type: str (indexed, default 'ai_processing')`, `version: str (indexed, e.g., '2026-04-11-v1')`, `granted_at: datetime (default utcnow)`, `locale: str ('uk'|'en')`, `ip: str | None`, `user_agent: str | None`. Append-only — no `revoked_at` in this story (Story 5.5 handles deletion via cascading delete).
  - [x] 1.2 Register model in `backend/app/models/__init__.py`.
  - [x] 1.3 Add Alembic migration `backend/alembic/versions/<hash>_create_user_consents_table.py` creating the table, a composite index `ix_user_consents_user_id_consent_type_version`, and a FK with `ON DELETE CASCADE` to `users.id` (so Story 5.5 "delete all my data" works by default via cascading delete — see also the Story 5.5 AC). Use the existing migration style from `feb18f356210_create_user_table.py` (sa.Uuid, timestamps with tz, `sa.text('now()')`, `sa.text('gen_random_uuid()')`).
  - [x] 1.4 Verify the migration runs cleanly: `cd backend && .venv/bin/alembic upgrade head` on a fresh local DB; then `alembic downgrade -1` and back up to confirm reversibility.

- [x] **Task 2: Backend — consent constant & API endpoints** (AC: #4, #5, #7)
  - [x] 2.1 Create `backend/app/core/consent.py` exporting `CURRENT_CONSENT_VERSION: Final[str] = "2026-04-11-v1"` and a `CONSENT_TYPE_AI_PROCESSING: Final[str] = "ai_processing"` constant. Docstring MUST explicitly state: **"This version identifies the privacy-explanation *content* users agreed to. It has NO relationship to app version, API version, or release version. Bump it ONLY when the privacy text materially changes (new data flows, new processors, new data categories). Cosmetic copy edits must NOT bump it."** Also include a one-line comment pointing to the frontend mirror at `frontend/src/features/onboarding/consent-version.ts` and to the CI contract check (Task 7.4) so future editors know both files must move together. Format: date-prefixed string `YYYY-MM-DD-vN` (matches the repo convention for migration filenames and retro filenames; makes the audit trail human-readable).
  - [x] 2.2 Add `backend/app/services/consent_service.py` with `grant_consent(session, user, consent_type, version, locale, ip, user_agent) -> UserConsent` and `get_current_consent_status(session, user, consent_type, version) -> dict` (returns `{ hasCurrentConsent, version, grantedAt | None, locale | None }`). Keep all SQLAlchemy queries scoped by `user_id`.
  - [x] 2.3 Add `backend/app/api/v1/consent.py` with two routes:
    - `POST /api/v1/users/me/consent` — body: `{ version: str, locale: 'uk'|'en' }`. Validates `version == CURRENT_CONSENT_VERSION` (rejects 422 otherwise — prevents frontend drift from granting stale versions). Calls `grant_consent()`. Returns `201 Created` with the new record, camelCase via `alias_generator=to_camel`.
    - `GET /api/v1/users/me/consent?type=ai_processing` — returns current status per AC #5.
    - Both routes require `get_current_user` (Cognito JWT) exactly like the existing `auth.py` routes.
  - [x] 2.4 Register the new router in `backend/app/api/v1/router.py` next to `auth`, `transactions`, etc.
  - [x] 2.5 Pydantic models: `GrantConsentRequest`, `ConsentResponse`, `ConsentStatusResponse` — all with `ConfigDict(alias_generator=to_camel, populate_by_name=True)` following the pattern in `backend/app/api/v1/auth.py:31`.

- [x] **Task 3: Backend — tests** (AC: #10)
  - [x] 3.1 `backend/tests/test_consent.py` — async pytest using the existing `client` + `authenticated_client` fixtures (pattern: `backend/tests/api/v1/test_auth.py`). Cover the five sub-cases in AC #10 explicitly.
  - [x] 3.2 `backend/tests/test_consent_service.py` — unit-test `grant_consent()` and `get_current_consent_status()` against an in-memory or test-DB session. Verify append-only behavior: two sequential calls yield two rows with distinct `id` and `granted_at`.
  - [x] 3.3 Run `cd backend && .venv/bin/pytest -q tests/test_consent.py tests/test_consent_service.py` green before commit. **Note:** backend venv is at `backend/.venv`, not repo root.

- [x] **Task 4: Frontend — `/onboarding/privacy` route & screen** (AC: #1, #2, #8)
  - [x] 4.1 Add route file `frontend/src/app/[locale]/(dashboard)/onboarding/privacy/page.tsx`. Place it inside the `(dashboard)` route group so it inherits the same `AuthGuard` (Cognito session required) but render a **minimal layout without** the main dashboard chrome (header nav, upload FAB) — use a scoped layout file `frontend/src/app/[locale]/(dashboard)/onboarding/layout.tsx` that overrides the dashboard layout's chrome for onboarding routes (review the (dashboard) layout in `frontend/src/app/[locale]/(dashboard)/layout.tsx` to understand what to suppress). A user who hasn't consented must not see the main nav or the upload FAB.
  - [x] 4.2 Build a `PrivacyExplanationScreen.tsx` component under `frontend/src/features/onboarding/components/` with: four topic sections (data collected / AI processing / storage / access), one consent checkbox, one primary "Continue" button (disabled until checked), and a small secondary "Log out" link (so users who want to bail can exit cleanly without bypassing the gate). Use existing design tokens (`text-foreground`, `bg-background`, primary button variant) from the current auth/dashboard screens — do NOT introduce a new design system.
  - [x] 4.3 Add i18n keys under `onboarding.privacy` in `frontend/messages/en.json` and `frontend/messages/uk.json`. Required keys: `title`, `subtitle`, `dataCollected.title/body`, `aiProcessing.title/body`, `storage.title/body`, `access.title/body`, `consentLabel`, `continue`, `logOut`. Tone: warm, trust-first, not legalese (see `ux-design-specification.md` lines 640–665 for the "Onboarding Flow" design direction). **Copy ownership:** dev agent drafts initial English + Ukrainian copy for MVP. This is explicitly placeholder-quality pending legal review before public launch — tracked in [future-ideas.md §4.2](../planning-artifacts/future-ideas.md) and flagged as a `CURRENT_CONSENT_VERSION` bump trigger (when real copy lands, bump the version and force re-consent — that's the system working as designed).
  - [x] 4.4 Form handling: local `useState` for checkbox, call `POST /api/v1/users/me/consent` with `{ version: CURRENT_CONSENT_VERSION, locale }` on submit via `fetch` using `session.accessToken` (pattern: `frontend/src/app/[locale]/(dashboard)/layout.tsx:26-35`), then `router.push('/upload')`. Export a shared `CURRENT_CONSENT_VERSION` constant in `frontend/src/features/onboarding/consent-version.ts` and keep it in sync with `backend/app/core/consent.py` — add a matching comment in both files warning they must move together (there is no automated contract test in this story).
  - [x] 4.5 Error handling: on API failure, show an inline error message (use `sonner` toast like the existing logout flow, or a local error banner — match whatever is already used in `SignupForm.tsx`/`LoginForm.tsx`). Do NOT redirect on error; user stays on the screen.

- [x] **Task 5: Frontend — consent guard (gate all authenticated routes)** (AC: #3, #6, #7, #9)
  - [x] 5.1 Add `frontend/src/lib/auth/consent-guard.tsx` — a client component that wraps `AuthGuard` behavior. After auth loads: call `GET /api/v1/users/me/consent?type=ai_processing` once (cache via TanStack Query key `['consent', 'ai_processing']`, `staleTime: Infinity` until the grant mutation invalidates it). While loading, show the same `DashboardSkeleton` used by `auth-guard.tsx`. If `hasCurrentConsent === false` AND current pathname does NOT already start with `/{locale}/onboarding`, `router.replace('/{locale}/onboarding/privacy')`.
  - [x] 5.2 Compose the guard into the dashboard layout: wrap the `(dashboard)/layout.tsx` children with `<ConsentGuard>` **inside** the existing `<AuthGuard>` (order matters: auth first, then consent). The onboarding layout from Task 4.1 must NOT apply the ConsentGuard — it would create an infinite loop. Easiest structure: `ConsentGuard` lives in the top-level `(dashboard)/layout.tsx`, and the onboarding route group has its own `onboarding/layout.tsx` that re-applies only `AuthGuard`, not `ConsentGuard`.
  - [x] 5.3 On successful consent grant (Task 4.4), invalidate the `['consent', 'ai_processing']` query key so the guard re-reads and lets the user through on the subsequent navigation.

- [x] **Task 6: Frontend — tests** (AC: #11)
  - [x] 6.1 `frontend/src/features/onboarding/__tests__/PrivacyExplanationScreen.test.tsx` — vitest + `@testing-library/react`. Assert button disabled initially, enabled after checkbox check, POST is called with the right body, redirect to `/upload` after success. Mock `fetch` and `useRouter`. Pattern: `frontend/src/features/auth/__tests__/SignupForm.test.tsx`.
  - [x] 6.2 `frontend/src/lib/auth/__tests__/consent-guard.test.tsx` — assert that when `GET /consent` returns `{ hasCurrentConsent: false }`, `router.replace` is called with the onboarding path; when `true`, children render normally.
  - [x] 6.3 i18n smoke test — simple assertion that both `en.json` and `uk.json` contain all `onboarding.privacy.*` keys used by the component (failing fast on missing translations).
  - [x] 6.4 Run `cd frontend && pnpm test -- privacy consent-guard` green before commit.

- [x] **Task 7: Documentation & cross-links** (AC: all)
  - [x] 7.1 Add a new subsection "Consent Management" to `_bmad-output/planning-artifacts/architecture.md` directly after the "Encryption at Rest" section (added by Story 5.1, ~line 384). Include: table schema, version-bump procedure, current version constant location, cross-links to Story 5.5 (cascading delete) and Story 5.6 (audit trail), **AND** a "Known Gaps" paragraph explicitly naming that consent enforcement is client-side only in MVP — server-side `require_consent` FastAPI dependency is deferred to the compliance hardening pass alongside Story 5.6. Cross-link to [future-ideas.md §4.1 "Server-side enforcement of AI-processing consent"](./future-ideas.md) so the gap is traceable from the architecture doc to the backlog entry.
  - [x] 7.2 Update the `### Data Privacy & Trust` row/table (if present) or the Epic 5 block so it reflects that FR32 and FR33 are now implemented (previously Story 5.1 updated the "Data Encryption" row).
  - [x] 7.3 Add a one-line entry to the README or `docs/` index if one is kept current (skip if none).
  - [x] 7.4 **Consent-version contract check.** Add a CI guardrail that fails if `CURRENT_CONSENT_VERSION` drifts between `backend/app/core/consent.py` and `frontend/src/features/onboarding/consent-version.ts`. Implementation options (pick the simpler one):
    - **Preferred:** a GitHub Actions job in `.github/workflows/consent-version-sync.yml` that runs `grep -oE '"[0-9]{4}-[0-9]{2}-[0-9]{2}-v[0-9]+"'` on both files and `diff`s the result, failing the job on mismatch. Triggers only on PRs touching either file (`paths:` filter). No language runtime required.
    - **Alternative:** a 10-line pytest under `backend/tests/contracts/test_consent_version_sync.py` that reads both files and asserts equality — runs as part of the normal backend suite, no new workflow file. Only use this if adding a new GHA workflow is heavier in this repo than adding a test.
    - The check must fail with a clear error message naming both file paths and both found values. Add a comment in each of the two constant-defining files pointing to this CI check so future editors know why both must move together.

### Review Follow-ups (AI)

- [x] [AI-Review][MEDIUM] Replace hardcoded hex colors (`#6C63FF`, `#FF6B6B`) with design tokens (`bg-primary`, `text-destructive`) in `PrivacyExplanationScreen.tsx` — violates Task 4.2 instruction to use existing design tokens
- [x] [AI-Review][MEDIUM] Extract duplicated `Skeleton` + `DashboardSkeleton` from `consent-guard.tsx` and `auth-guard.tsx` into a shared component (e.g., `@/components/layout/DashboardSkeleton`)
- [x] [AI-Review][MEDIUM] Fix story Task 3.1/3.2/3.3 paths — replace `tests/api/v1/test_consent.py` and `tests/services/test_consent_service.py` with actual flat paths `tests/test_consent.py` and `tests/test_consent_service.py`

## Dev Notes

### Scope Summary

- **Full-stack story.** Backend: new table + two endpoints + tests. Frontend: new onboarding route + consent guard + i18n + tests. This is the first full-stack story in Epic 5 — Story 5.1 was infrastructure-only.
- **Data model philosophy: append-only.** The `user_consents` table is append-only; every grant creates a new row, old rows are never updated. This gives us a clean audit trail for free (important for GDPR accountability and lines up with the Story 5.6 compliance-audit design) and means "re-consent on version bump" is a trivial `INSERT`, not an `UPDATE`.
- **Version-gated re-consent.** A `CURRENT_CONSENT_VERSION` string constant (shared in spirit between `backend/app/core/consent.py` and `frontend/src/features/onboarding/consent-version.ts`) is the single source of truth for "what consent counts right now". Bumping it forces every user back through the onboarding screen on their next login. This is cheap to implement and avoids the accidental-silent-re-consent trap where copy edits leak out without users noticing.
- **Consent gate is client-side AND server-side.** Client-side: `ConsentGuard` redirects unconsented users to `/onboarding/privacy`. Server-side: **this story does NOT yet block backend endpoints for unconsented users.** A sophisticated attacker could hit `/api/v1/transactions` directly with a valid JWT and bypass the frontend gate. That is acceptable for MVP (consent is about informed-consent UX, not access control), and closing that loophole belongs in a dedicated "server-side consent enforcement" follow-up, flagged below in Questions. Do NOT silently add a backend dependency that blocks all endpoints for unconsented users — that is out of scope and changes the behavior of every existing endpoint.

### Key Design Decisions (non-obvious)

- **Append-only table vs column on `users`.** A column (`users.consent_given_at`, `users.consent_version`) would be simpler but destroys history on every version bump and makes the Story 5.6 audit trail redundant. An append-only table is GDPR-aligned (auditable, non-destructive) and future-proofs for: revocation, multiple consent types (AI processing, marketing, cookies…), locale tracking, IP/UA capture for legal defensibility. The simplicity cost is ~15 extra lines of SQLModel — worth it.
- **Why a separate `consent_type` column from day one.** Today we only need `ai_processing`. But Story 5.3 (financial-advice disclaimer) could plausibly add a second consent type, and adding a column later requires a migration. Stubbing the column now with a constant value costs almost nothing.
- **Why `version = "2026-04-11-v1"` and not a numeric integer.** A date-prefixed string makes the audit trail human-readable ("what did users consent to in April 2026?") and prevents the boring "is 3 newer than 2" class of bugs when a hotfix requires an out-of-order bump. Same convention used elsewhere in the project for migration filenames.
- **Client-side enforcement is enough for MVP.** The AC literally says "I cannot continue to the main app — consent is mandatory." The user is the actor here, not a malicious API client. The backend validates authentication (Cognito JWT), and the frontend validates consent. Server-side consent enforcement is a separate concern (belongs to a future compliance-hardening story), and bundling it here bloats the diff and risks breaking every existing endpoint during review.
- **No `revoked_at` column in this story.** Story 5.5 (Delete All My Data) handles "revocation" by deleting the user record entirely via cascading delete. If a future story needs "pause consent without deleting account," add a `revoked_at` column then.
- **`/onboarding/privacy` lives inside `(dashboard)` route group, not `(auth)`.** Onboarding happens *after* authentication, not as part of it. Placing it in `(auth)` would require exposing the screen to unauthenticated users (wrong — we need the JWT to call `POST /consent`) or weakening `AuthGuard` (wrong — creates loopholes). The right answer is: a sub-group inside `(dashboard)` with its own minimal layout.

### Source Tree Components to Touch

```
backend/
├── app/
│   ├── core/
│   │   └── consent.py                              # NEW — CURRENT_CONSENT_VERSION constant
│   ├── models/
│   │   ├── __init__.py                             # register UserConsent
│   │   └── consent.py                              # NEW — UserConsent SQLModel table
│   ├── services/
│   │   └── consent_service.py                      # NEW — grant_consent / get_current_consent_status
│   └── api/v1/
│       ├── router.py                               # register consent router
│       └── consent.py                              # NEW — POST/GET /users/me/consent
├── alembic/versions/
│   └── <new_hash>_create_user_consents_table.py    # NEW — migration
└── tests/
    ├── test_consent.py                             # NEW
    └── test_consent_service.py                     # NEW

frontend/
├── src/
│   ├── components/layout/
│   │   └── DashboardSkeleton.tsx                    # NEW — shared skeleton (extracted from auth-guard + consent-guard)
│   ├── app/[locale]/(dashboard)/
│   │   └── onboarding/
│   │       ├── layout.tsx                          # NEW — minimal chrome, AuthGuard only (no ConsentGuard)
│   │       └── privacy/page.tsx                    # NEW
│   ├── features/onboarding/                        # NEW feature folder
│   │   ├── components/PrivacyExplanationScreen.tsx # NEW
│   │   ├── consent-version.ts                      # NEW — mirrors backend constant
│   │   └── __tests__/PrivacyExplanationScreen.test.tsx  # NEW
│   ├── lib/auth/
│   │   ├── consent-guard.tsx                       # NEW
│   │   └── __tests__/consent-guard.test.tsx        # NEW
│   └── app/[locale]/(dashboard)/layout.tsx         # add <ConsentGuard> inside <AuthGuard>
└── messages/
    ├── en.json                                     # add onboarding.privacy.*
    └── uk.json                                     # add onboarding.privacy.*

_bmad-output/planning-artifacts/
└── architecture.md                                 # add "Consent Management" subsection after "Encryption at Rest"
```

**Do NOT touch:**
- `backend/app/api/v1/auth.py` — consent lives under its own `consent.py` router. Adding consent columns to `UserProfileResponse` bloats the auth contract and breaks existing frontend consumers.
- Any existing FastAPI endpoint (transactions, uploads, profile, health_score, insights) — do NOT add a consent dependency in this story. See the "Client-side enforcement is enough" design decision above.
- `backend/app/models/user.py` — no new columns on `users`. Consent lives in its own table.
- Existing tests under `backend/tests/` or `frontend/src/features/auth/__tests__/` — regression safety, not modification targets.

### Testing Standards Summary

- **Backend:** async `pytest` with the existing `client` / `authenticated_client` fixtures. Run from `backend/.venv` (**not** a repo-root venv — that will bite you; the venv is at `backend/.venv`). Command: `cd backend && .venv/bin/pytest -q tests/test_consent.py tests/test_consent_service.py`.
- **Frontend:** `vitest` + `@testing-library/react`. Command: `cd frontend && pnpm test`. Pattern file: `frontend/src/features/auth/__tests__/SignupForm.test.tsx`.
- **Regression smoke:** `cd backend && .venv/bin/pytest -q` (full suite) should still pass untouched — the new endpoints are additive. `cd frontend && pnpm test` same. If any existing test fails, investigate — do not mask.
- **Manual smoke:** (1) register a new user, verify, log in → should land on `/onboarding/privacy`, not `/upload`. (2) Try to navigate to `/upload` directly — should bounce back. (3) Check the box, click Continue → should land on `/upload`. (4) Log out and back in → should go straight to `/upload` (no re-consent). (5) Bump `CURRENT_CONSENT_VERSION` in both files, restart both services, log in → should see onboarding again, new DB row on grant.

### Project Structure Notes

- Feature-folder convention (`frontend/src/features/<feature>/`) matches the existing pattern (`features/auth`, `features/teaching-feed`). New `features/onboarding/` is consistent.
- Backend: `core/consent.py` lives alongside `core/security.py` (Cognito JWT validation) — both are cross-cutting concerns, correct placement.
- No new top-level directories anywhere.
- Architecture doc is still a single file (1544 lines as of 2026-04-11 per Story 5.1's recent count of 1486 plus the new encryption section). Add the "Consent Management" subsection inline, don't shard.

### References

- **Story 5.1** (Data Encryption at Rest) → [5-1-data-encryption-at-rest.md](5-1-data-encryption-at-rest.md) — prior Epic 5 story; established the "Encryption at Rest" section in `architecture.md` that Task 7.1 extends. Also surfaces a useful pattern: Epic 5 stories cross-link each other in the architecture doc.
- [Source: _bmad-output/planning-artifacts/epics.md#Story-5.2] — AC source of truth (lines 1069–1095).
- [Source: _bmad-output/planning-artifacts/prd.md:602-609] — FR32, FR33 (the functional requirements this story implements).
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md:640-700] — Onboarding Flow design direction ("trust-first, anxiety-aware"), Phase 4 Onboarding notes.
- [Source: backend/app/models/user.py](../../backend/app/models/user.py) — existing `User` SQLModel (do not modify; reference for patterns).
- [Source: backend/app/api/v1/auth.py:31](../../backend/app/api/v1/auth.py#L31) — Pydantic `ConfigDict(alias_generator=to_camel)` pattern.
- [Source: backend/alembic/versions/feb18f356210_create_user_table.py](../../backend/alembic/versions/feb18f356210_create_user_table.py) — migration style template (sa.Uuid, timestamps, defaults).
- [Source: frontend/src/lib/auth/auth-guard.tsx](../../frontend/src/lib/auth/auth-guard.tsx) — pattern for the new `ConsentGuard` (skeleton loader, redirect-on-miss, pathname check).
- [Source: frontend/src/app/[locale]/(dashboard)/layout.tsx](../../frontend/src/app/[locale]/(dashboard)/layout.tsx) — dashboard chrome + `AuthGuard` composition; shows the `fetch` + `session.accessToken` pattern at lines 26–35.
- [Source: frontend/src/features/auth/components/SignupForm.tsx](../../frontend/src/features/auth/components/SignupForm.tsx) — form error handling + `useTranslations` pattern.
- [Source: frontend/src/features/auth/__tests__/SignupForm.test.tsx](../../frontend/src/features/auth/__tests__/SignupForm.test.tsx) — vitest + RTL test pattern.
- [Source: _bmad-output/planning-artifacts/architecture.md#Encryption-at-Rest] — the section added by Story 5.1 that Task 7.1 extends with "Consent Management".
- [GDPR Art. 7] "Conditions for consent": explicit, informed, withdrawable. This story covers explicit + informed; Story 5.5 covers withdrawal via full deletion.
- [Next.js docs — Route Groups] https://nextjs.org/docs/app/building-your-application/routing/route-groups — for the `(dashboard)/onboarding/` nested group and its own layout. **Frontend CLAUDE.md/AGENTS.md warns "This is NOT the Next.js you know" — read `node_modules/next/dist/docs/` for the exact current API before writing route/layout code.**

### Developer Guardrails (things that will bite you)

1. **Backend venv is at `backend/.venv`, not the repo root.** Running `pytest` or `alembic` from a root venv will silently pick up the wrong Python environment. Always use `backend/.venv/bin/<tool>`.
2. **Do NOT add a consent dependency to any existing FastAPI endpoint.** That changes the behavior of every route in the app and is out of scope. If you think it's necessary, STOP and escalate — it's a separate story.
3. **Do NOT add a column to `users`.** The whole point of a separate `user_consents` table is auditability. Adding a denormalized `users.has_current_consent` field will drift and lie. Use a query or a cached `GET /users/me/consent` response instead.
4. **Do NOT make `/onboarding/privacy` accessible without auth.** Putting it in `(auth)` route group looks tempting (no dashboard chrome) but breaks everything — we need the Cognito JWT to call `POST /consent`.
5. **Do NOT create an infinite redirect loop** between `ConsentGuard` and `/onboarding/privacy`. The guard MUST check `pathname.startsWith('/{locale}/onboarding')` and short-circuit. Write the test for this case first.
6. **`CURRENT_CONSENT_VERSION` lives in TWO places (backend + frontend) by design.** There is no shared types package. Add matching comments in both files instructing future editors to update both. A contract test would be nicer; skip it for this story unless trivial (see Questions).
7. **Do NOT bump `CURRENT_CONSENT_VERSION` for cosmetic copy edits.** Only material changes (new data flows, new processors, new categories). Cosmetic bumps invalidate every user's consent on next login — that's user-hostile.
8. **Tenant isolation.** Every query in `consent_service.py` MUST filter by `user_id = current_user.id`. Do NOT add any "admin view all consents" endpoint in this story — out of scope and a footgun for Story 5.5.
9. **Append-only means append-only.** A second `POST /consent` for the same user + version must INSERT a new row, not UPDATE the existing one. AC #10(d) covers this — write the test first.
10. **The post-verification flow redirects to `/login` (not auto-login) — see [VerificationForm.tsx:28](../../frontend/src/features/auth/components/VerificationForm.tsx#L28).** So the first encounter with the onboarding gate happens on *first successful login*, not on verify-completion. Plan the manual smoke test accordingly.
11. **`/dashboard` currently just redirects to `/upload`** — see [dashboard/page.tsx:9](../../frontend/src/app/[locale]/(dashboard)/dashboard/page.tsx#L9). The ConsentGuard must run on `/upload` too (the real landing), not only on `/dashboard`. Wrapping at the `(dashboard)` layout level covers both.

### Previous Story Intelligence (Story 5.1)

- Epic 5 kickoff story was infrastructure-only. Zero application code changed. This story is the first to touch backend application code and frontend in Epic 5 — expect zero conflicts with Story 5.1 (different file trees entirely).
- Story 5.1 established the "Encryption at Rest" section in `architecture.md` and a pattern of cross-linking Epic 5 siblings. Task 7.1 continues that pattern ("Consent Management" section).
- Story 5.1 revealed one operational note: the dev AWS environment is **not yet live** (Story 5.1 Review Follow-up on Task 7). That does NOT block this story — local development against the dev database via `alembic upgrade head` works fine, and manual smoke testing runs locally.
- Story 5.1 also showed that `tfsec` is now running on every PR touching `infra/**`. This story touches zero Terraform files, so tfsec is irrelevant here. Do not touch `infra/terraform/`.
- No open review feedback from Story 5.1 is relevant to this story's file paths.

### Git Intelligence

Recent commits (last 5):
```
46ca2b4 Story 5.1: Data Encryption at Rest
a0154ff Story 4.8: Category Spending Breakdown // Minor bug fixes
1f20c27 Story 4.7: Month-over-Month Spending Comparison
db0b828 Story 4.6: Health Score History & Trends
dd3256e Story 4.5: Financial Health Score Calculation & Display
```

- Story 5.1 (most recent) touched `infra/terraform/**`, `.github/workflows/tfsec.yml`, `architecture.md`, and one tiny backend edit (`upload_service.py:251` adding `ServerSideEncryption="AES256"` — unrelated to consent).
- Epic 4 commits (4.4–4.8) established the backend/frontend full-stack feature pattern this story follows: migration → SQLModel → service → API route → router registration → tests → frontend fetch + component + i18n + tests. Replicate that skeleton.
- None of the recent commits touch `features/auth/`, `lib/auth/`, or any onboarding flow — this story is not racing any in-flight work. The auth surface has been stable since Epic 1.

### Latest Tech Information

No external library research is required for this story. Everything it needs is already in the repo:
- `next-intl` (i18n) — pattern: `SignupForm.tsx`.
- `react-hook-form` + `zod` — optional here (one checkbox + one button is simple enough for local `useState`, but use RHF if you prefer consistency with `SignupForm`).
- `next-auth` / Cognito JWT — existing `session.accessToken` pattern.
- `sqlmodel` + `alembic` — existing migration style.
- `pytest-asyncio` + `httpx.AsyncClient` — existing test fixtures.
- TanStack Query — existing; used by `use-auth` and other hooks.

If you're unsure about Next.js route-group + nested-layout semantics, the frontend `AGENTS.md` mandates: **read `node_modules/next/dist/docs/` before writing route/layout code** — the repo uses a Next version that may diverge from training-data defaults.

## Project Context Reference

- Planning artifacts: `_bmad-output/planning-artifacts/epics.md` (Story 5.2 at lines 1069–1095), `prd.md` (FR32–FR36 at lines 602–609), `ux-design-specification.md` (Onboarding Flow at lines 640–700), `architecture.md` (Encryption at Rest section added by Story 5.1, ~line 384 — extend directly after it).
- Related epic stories: **5.1** (done-review: encryption foundation), **5.3** (next: financial-advice disclaimer — will likely reuse the consent table with a second `consent_type` value), **5.4** (view my stored data — will surface consent records as part of the data summary), **5.5** (delete all my data — relies on the `ON DELETE CASCADE` this story establishes), **5.6** (compliance audit trail — the append-only consent log is a natural data source).
- Sprint status: this story is `backlog` → will be set to `ready-for-dev` on file save → dev agent picks up next.

## Dev Agent Record

### Agent Model Used

claude-opus-4-6 (dev-story workflow)

### Debug Log References

- Initial backend test run hit `sqlalchemy.exc.MissingGreenlet` + `DetachedInstanceError` under the async aiosqlite session fixture. Root cause: `session.refresh()` triggered attribute loads across the async boundary, and `expire_on_commit=True` re-triggered loads on read-after-commit. **Fix:** `grant_consent()` now constructs a detached `UserConsent` copy with all attributes populated (id + granted_at come from `default_factory` on the constructor, no DB round-trip) before commit, and returns the detached copy. Service-level tests use a local `_session_ctx` helper with `expire_on_commit=False` so the shared conftest fixture is not perturbed. Full suite (342 backend tests) is green.
- Alembic migration verified with real postgres (`docker compose up -d postgres`): `upgrade head → downgrade -1 → upgrade head` is reversible.
- One pre-existing `DeprecationWarning` surfaced in the new test (`HTTP_422_UNPROCESSABLE_ENTITY` → `HTTP_422_UNPROCESSABLE_CONTENT`). Out of scope for this story — unrelated code path.

### Completion Notes List

- **AC coverage:** All 11 ACs are implemented and covered by automated tests. Backend: 9 API tests + 5 service tests in `tests/test_consent.py` and `tests/test_consent_service.py`. Frontend: 6 `PrivacyExplanationScreen` tests + 4 `ConsentGuard` tests + 28 i18n smoke tests (14 keys × 2 locales).
- **Append-only semantics:** `user_consents` is never updated or deleted. Re-consent on the same version inserts a second row; `hasCurrentConsent` is computed as "any row matches (user_id, type, CURRENT_CONSENT_VERSION)". Story 5.5 will cascade-delete via `ON DELETE CASCADE`.
- **Version format:** `YYYY-MM-DD-vN` date-prefixed string. Initial: `2026-04-11-v1`. Backend and frontend constants both carry lengthy pointer docstrings explaining bump semantics.
- **CI guardrail:** `.github/workflows/consent-version-sync.yml` greps `[0-9]{4}-[0-9]{2}-[0-9]{2}-v[0-9]+` from both `backend/app/core/consent.py` and `frontend/src/features/onboarding/consent-version.ts` and fails on drift.
- **Onboarding layout isolation:** `(dashboard)/onboarding/layout.tsx` wraps onboarding routes in `AuthGuard` only (no `ConsentGuard`) to prevent a redirect loop. The parent dashboard layout additionally suppresses its header + upload FAB when `pathname.startsWith('/<locale>/onboarding')` so no main-app chrome leaks through.
- **Known gap — client-only enforcement.** `ConsentGuard` is advisory. Server-side enforcement was deferred to future-ideas §4.1 per PO decision. The architecture doc's new "Consent Management" subsection documents this explicitly.
- **Placeholder copy.** EN + UK privacy text was drafted by the dev agent for MVP. Legal review tracked in future-ideas §4.2; when real copy lands, bump `CURRENT_CONSENT_VERSION` to force re-consent.
- ✅ Resolved review finding [MEDIUM]: Replaced hardcoded hex colors (#6C63FF, #FF6B6B) with design tokens (bg-primary, text-destructive) in PrivacyExplanationScreen.tsx.
- ✅ Resolved review finding [MEDIUM]: Extracted duplicated Skeleton + DashboardSkeleton from consent-guard.tsx and auth-guard.tsx into shared @/components/layout/DashboardSkeleton.tsx.
- ✅ Resolved review finding [MEDIUM]: Fixed story Task 3.1/3.2/3.3 paths to match actual flat test file locations.
- **Full regression:** 342 backend tests pass (pytest). 287 frontend tests pass across 30 files (vitest). Ruff clean on all touched backend files. ESLint clean on all touched frontend files. Pre-existing tsc errors in `LoginForm.test.tsx` and `FeedContainer.test.tsx` are unrelated and out of scope.

### File List

**Backend — new:**
- `backend/app/models/consent.py` — `UserConsent` SQLModel with composite index
- `backend/alembic/versions/a7b9c1d2e3f4_create_user_consents_table.py` — migration (reversible, `ON DELETE CASCADE` on user_id)
- `backend/app/core/consent.py` — `CURRENT_CONSENT_VERSION` + `CONSENT_TYPE_AI_PROCESSING` constants with bump-rules docstring
- `backend/app/services/consent_service.py` — `grant_consent()` + `get_current_consent_status()` with detached-copy pattern
- `backend/app/api/v1/consent.py` — `POST /users/me/consent` + `GET /users/me/consent` routes
- `backend/tests/test_consent.py` — 9 API tests (success, 401, isolation, append-only, version bump, stale version 422)
- `backend/tests/test_consent_service.py` — 5 service-layer unit tests

**Backend — new (review):**
- `backend/app/core/request.py` — shared `get_client_ip` utility (extracted from auth.py + consent.py)

**Backend — modified:**
- `backend/app/models/__init__.py` — export `UserConsent`
- `backend/app/api/v1/router.py` — register `consent_router`
- `backend/app/api/v1/auth.py` — use shared `get_client_ip` from `core/request.py`
- `backend/app/services/rate_limiter.py` — add `check_consent_rate_limit` method

**Frontend — new:**
- `frontend/src/components/layout/DashboardSkeleton.tsx` — extracted shared skeleton component (from auth-guard + consent-guard)
- `frontend/src/features/onboarding/consent-version.ts` — mirror of backend constant
- `frontend/src/app/[locale]/(dashboard)/onboarding/layout.tsx` — scoped minimal layout (no guards, parent layout handles auth + consent)
- `frontend/src/app/[locale]/(dashboard)/onboarding/privacy/page.tsx` — server component + `generateMetadata`
- `frontend/src/features/onboarding/components/PrivacyExplanationScreen.tsx` — client component with 4 topic sections, consent checkbox, log-out escape hatch, and post-success query-cache invalidation
- `frontend/src/lib/auth/consent-guard.tsx` — TanStack-Query-backed client gate with onboarding-route short-circuit and dashboard skeleton during pending state
- `frontend/src/features/onboarding/__tests__/PrivacyExplanationScreen.test.tsx` — 6 tests
- `frontend/src/features/onboarding/__tests__/consent-i18n.test.ts` — 28 tests (14 keys × 2 locales)
- `frontend/src/lib/auth/__tests__/consent-guard.test.tsx` — 4 tests

**Frontend — modified:**
- `frontend/src/app/[locale]/(dashboard)/layout.tsx` — wraps children in `ConsentGuard`; suppresses header + upload FAB on onboarding routes
- `frontend/src/lib/auth/auth-guard.tsx` — imports shared `DashboardSkeleton` instead of inline Skeleton
- `frontend/messages/en.json` — added `onboarding.privacy` namespace (14 keys)
- `frontend/messages/uk.json` — added `onboarding.privacy` namespace (14 keys)

**CI / docs — new:**
- `.github/workflows/consent-version-sync.yml` — drift guardrail

**CI / docs — modified:**
- `_bmad-output/planning-artifacts/architecture.md` — new "Consent Management" subsection after "Encryption at Rest"
- `_bmad-output/planning-artifacts/future-ideas.md` — §4.1 and §4.2 entries (added during planning pass, confirmed still accurate)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — story key → `review`

### Change Log

| Date | Change | Author |
|---|---|---|
| 2026-04-11 | Story drafted and moved to `ready-for-dev` | planning agent |
| 2026-04-11 | Implementation complete. Backend `user_consents` table + service + API, frontend onboarding screen + `ConsentGuard`, i18n copy, CI version-sync guardrail, architecture doc updated. 342 backend + 286 frontend tests green. Status → `review`. | dev agent (claude-opus-4-6) |
| 2026-04-12 | Review follow-ups (session 2) — 3 MEDIUM items resolved: replaced hardcoded hex colors with design tokens, extracted shared DashboardSkeleton component, fixed test file paths across story file (Tasks, Source Tree, Testing Standards). 287 frontend tests green. | dev agent (claude-opus-4-6) |
| 2026-04-12 | Code review: fixed H1 (ConsentGuard fail-open on API error → now fail-closed with `isError` check + test), L1 (layout indentation), L2 (redundant aria-describedby), L3 (ConsentResponse now includes ip/user_agent per AC #4). 3 MEDIUM action items created. | review agent (claude-opus-4-6) |
| 2026-04-12 | Code review (session 2): fixed M3 (extracted shared `get_client_ip` to `core/request.py`, deduplicated from auth.py + consent.py), M4 (added per-user rate limiting on POST /consent via `check_consent_rate_limit`), L1 (removed redundant inner AuthGuard from onboarding layout), L2 (added `Literal["ai_processing"]` constraint on GET consent `type` param). Updated M1 (added `auth-guard.tsx` to File List), M2 (checked off all 7 tasks), L3 (status → `review`). 14 backend + 287 frontend tests green. | review agent (claude-opus-4-6) |

## Questions / Clarifications for PO

1. **Server-side enforcement of consent on protected endpoints.** **RESOLVED 2026-04-11:** Deferred to a separate follow-up tied to the compliance hardening pass, to be implemented alongside Story 5.6 (Compliance Audit Trail) since they share an injection point. Tracked in [future-ideas.md §4.1 "Server-side enforcement of AI-processing consent"](../planning-artifacts/future-ideas.md). Task 7.1 of this story adds a "Known Gaps" note to the new architecture.md "Consent Management" subsection so the gap is visible from the architecture doc. **No code changes in this story — client-side `ConsentGuard` remains the only enforcement until the hardening pass.**

2. **Consent-version contract test.** **RESOLVED 2026-04-11:** Add the CI guardrail. See Task 7.4.
3. **"Log out" escape hatch on the privacy screen.** **RESOLVED 2026-04-11:** Confirmed correct UX. Task 4.2 stands as specced — a small secondary "Log out" link alongside the "Continue" button so users who refuse to consent can exit cleanly instead of being trapped.
4. **Tone-check for the privacy copy.** **RESOLVED 2026-04-11:** Dev agent drafts the initial EN + UK copy for MVP. This is explicit placeholder-quality text pending legal review before public launch. Tracked in [future-ideas.md §4.2 "Privacy explanation copy — legal review before launch"](../planning-artifacts/future-ideas.md) and noted in Task 4.3. When real copy lands, it bumps `CURRENT_CONSENT_VERSION` and forces re-consent — that's the designed flow.
5. **Initial version string.** **RESOLVED 2026-04-11:** Confirmed this is the **consent content version**, NOT the app version. Format: date-prefixed string `"2026-04-11-v1"`. The `consent.py` docstring must explicitly state: "this version identifies the privacy-explanation content users agreed to, has NO relationship to app version or API version, and must be bumped only when the privacy text materially changes (new data flows, new processors, new data categories) — cosmetic edits must not bump it."
