# Story 10.1a: `chat_processing` Consent (separate from `ai_processing`)

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want a separate, explicit consent for chat-with-finances (distinct from the existing AI-processing consent) — granted on first chat use and revocable independently —
So that I can opt into conversational features without being forced to either accept or revoke my consent for the entire batch pipeline (ingestion, categorization, education).

## Acceptance Criteria

1. **Given** a new constant `CONSENT_TYPE_CHAT_PROCESSING = "chat_processing"` and a new version constant `CURRENT_CHAT_CONSENT_VERSION` are added to `backend/app/core/consent.py` (mirrored in `frontend/src/features/onboarding/consent-version.ts`), **When** the constants are read, **Then** they are independent of `CONSENT_TYPE_AI_PROCESSING` and `CURRENT_CONSENT_VERSION` — bumping one MUST NOT bump the other (independent version streams), and the docstring/JS-doc explicitly states that `chat_processing` covers **conversation logging, cross-session memory, retention window, and use of anonymized conversation signals for chat-quality improvement** (per [prd.md FR71](../planning-artifacts/prd.md#L691) + [architecture.md "Consent Drift Policy"](../planning-artifacts/architecture.md#L1716)).

2. **Given** the existing `POST /api/v1/users/me/consent` endpoint, **When** it is extended to accept `consent_type: 'ai_processing' | 'chat_processing'` in the request body (default `'ai_processing'` for backward compatibility with Story 5.2 callers), **Then** version validation is per-type — `ai_processing` requests must match `CURRENT_CONSENT_VERSION`, `chat_processing` requests must match `CURRENT_CHAT_CONSENT_VERSION`; mismatch returns `422 CONSENT_VERSION_MISMATCH` with a `consentType` field in `details` so the client can recover.

3. **Given** the existing `GET /api/v1/users/me/consent?type=…` endpoint, **When** the `type` query param accepts `chat_processing` in addition to `ai_processing`, **Then** it returns `{ hasCurrentConsent, version, grantedAt | null, locale | null, revokedAt | null }`; `hasCurrentConsent` is `true` only if the **most recent** row for `(user_id, 'chat_processing')` is **not revoked** AND its `version == CURRENT_CHAT_CONSENT_VERSION`. A revoked row makes `hasCurrentConsent=false` even when `version` matches.

4. **Given** the `user_consents` table, **When** a new Alembic migration runs, **Then** it adds a nullable `revoked_at TIMESTAMP NULL` column (default `NULL`) — preserving the append-only invariant for `ai_processing` rows (which never set this column) and enabling chat-consent revocation as an `INSERT` of a new row with `revoked_at = utcnow()` rather than a destructive `UPDATE`. Migration is reversible.

5. **Given** a new endpoint `DELETE /api/v1/users/me/consent?type=chat_processing`, **When** an authenticated user calls it, **Then** the backend inserts a new `user_consents` row with `consent_type='chat_processing'`, `version=CURRENT_CHAT_CONSENT_VERSION`, `revoked_at=utcnow()`, returns `204 No Content`, and emits a structured log event `{ "action": "consent_revoke", "consent_type": "chat_processing", "user_id": "<uuid>" }`. Calling DELETE for `ai_processing` returns `400 CONSENT_TYPE_NOT_REVOCABLE` — only `chat_processing` is independently revocable in this story (ai_processing revocation is whole-account deletion via Story 5.5).

6. **Given** the cascade-delete hook contract documented here, **When** Story 10.1b adds the `chat_sessions` / `chat_messages` tables, **Then** it MUST consume the `revoke_chat_consent(session, user)` service function defined in Story 10.1a as the single integration point for "consent revoked → terminate sessions + cascade delete." Story 10.1a leaves the cascade body as a documented TODO (`# TODO(10.1b): cascade chat_sessions delete here`) so the hook exists in the right place; the actual delete logic lives in 10.1b. This decoupling is **explicit** — no premature import of `chat_sessions` in 10.1a (the table doesn't exist yet); 10.1b wires the cascade by editing the service function, not by adding a parallel hook elsewhere.

7. **Given** the consent-revocation row in `user_consents`, **When** the existing data-summary endpoint (`GET /api/v1/users/me/data-summary` from Story 5.4) returns `consentRecords`, **Then** each record now includes a `revokedAt` field (nullable), so users can see both grant and revocation events in their data export — required for [FR35 export](../planning-artifacts/prd.md) parity.

8. **Given** the existing per-user POST consent rate limit (10 grants/hour, see [rate_limiter.py:check_consent_rate_limit](../../backend/app/services/rate_limiter.py#L89)), **When** the same limit applies to chat-consent grants AND revocations counted together, **Then** abuse (grant→revoke loop to spam audit log) is bounded; exceeding the limit returns `429 RATE_LIMITED` with `retryAfter`.

9. **Given** the new endpoints + migration, **When** backend tests run, **Then** `backend/tests/test_consent_chat.py` and `backend/tests/test_consent_service.py` cover: (a) grant chat consent — inserts row, GET returns hasCurrentConsent=true; (b) revoke chat consent — inserts row with revoked_at, GET returns hasCurrentConsent=false; (c) re-grant after revoke — most recent non-revoked row wins, hasCurrentConsent=true again; (d) `chat_processing` grant does NOT satisfy `ai_processing` GET and vice versa (independent streams); (e) version mismatch on chat returns 422 with `consentType: 'chat_processing'`; (f) DELETE for `ai_processing` returns 400 CONSENT_TYPE_NOT_REVOCABLE; (g) ~~tenant isolation~~ **Dropped in code review (M3)** — endpoints operate on `current_user` so cross-tenant access isn't reachable via the HTTP surface; tenant safety is enforced at the query layer (`user_id = current_user.id` filters) and covered implicitly by (a)/(b); (h) `revoke_chat_consent()` service function is called by the DELETE handler (assert via spy/mock that the integration point exists for 10.1b); (i) rate limit applies across grant + revoke combined.

10. **Given** the consent-version contract check workflow at `.github/workflows/consent-version-sync.yml` (added in Story 5.2), **When** it is updated to also diff the new `CURRENT_CHAT_CONSENT_VERSION` constant between backend and frontend files, **Then** drift on either version constant fails the build with a clear error message naming both file paths and both found values.

11. **Given** the architecture doc's "Consent Management" subsection (added by Story 5.2) and "Consent Drift Policy" subsection (Epic 10 chat surface), **When** Story 10.1a updates the docs, **Then** the "Consent Management" subsection is extended with a "Chat Processing Consent" paragraph explaining: independent version stream, revocation semantics (append `revoked_at` row, never UPDATE), the `revoke_chat_consent()` integration hook for 10.1b, and a Known Gap note that `chat_sessions.consent_version_at_creation` (per the Consent Drift Policy) is wired in 10.1b — 10.1a only stores the consent.

12. **Given** the frontend constants file `frontend/src/features/onboarding/consent-version.ts`, **When** it exports `CURRENT_CHAT_CONSENT_VERSION` and `CONSENT_TYPE_CHAT_PROCESSING`, **Then** `frontend/src/features/onboarding/__tests__/consent-i18n.test.ts` (or a sibling smoke test) asserts both constants are exported and non-empty. **No chat-consent UI ships in this story** — the first-use prompt + revoke button live in Stories 10.3b (UX states spec) and 10.7 (Chat UI). 10.1a is backend + shared constants only on the FE.

## Tasks / Subtasks

- [x] **Task 1: Backend — extend `user_consents` schema with `revoked_at`** (AC: #4)
  - [x] 1.1 Add `revoked_at: datetime | None = Field(default=None, nullable=True)` to `backend/app/models/consent.py:UserConsent`. Keep the table append-only — this column is set on the *new* revocation row, never on existing rows.
  - [x] 1.2 Create Alembic migration `backend/alembic/versions/b5e8d1f2a3c7_add_revoked_at_to_user_consents.py`. Use `op.add_column('user_consents', sa.Column('revoked_at', sa.DateTime(timezone=False), nullable=True))`. Reversible via `op.drop_column`.
  - [x] 1.3 Verified with real Postgres: `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` all clean.

- [x] **Task 2: Backend — chat-processing constants** (AC: #1, #10)
  - [x] 2.1 In `backend/app/core/consent.py`, added `CONSENT_TYPE_CHAT_PROCESSING` and `CURRENT_CHAT_CONSENT_VERSION = "2026-04-24-v1"` with updated docstring covering both streams and the "bumping one MUST NOT bump the other" invariant.
  - [x] 2.2 Mirrored in `frontend/src/features/onboarding/consent-version.ts` with matching TSDoc.
  - [x] 2.3 Extended `.github/workflows/consent-version-sync.yml` to extract + diff each constant by name from both files. Single job, single `check_pair` helper invoked twice; failure output names the constant + both file paths + both values.

- [x] **Task 3: Backend — extend consent service for chat grant + revoke** (AC: #3, #5, #6, #7)
  - [x] 3.1 `get_current_consent_status` now reads the most-recent row for `(user_id, consent_type)` and computes `hasCurrentConsent = (row is not None) AND (row.revoked_at IS NULL) AND (row.version == required_version)`. Returns `revokedAt`. ai_processing rows are unaffected (revoked_at always NULL).
  - [x] 3.2 Added `revoke_chat_consent(session, user, locale, ip, user_agent)` using the detached-copy pattern; `TODO(10.1b): cascade chat_sessions delete here` marker left at function tail per AC #6.
  - [x] 3.3 `ConsentRecord` in `data_summary.py` now includes `revoked_at: datetime | None = None`; projection updated in `get_data_summary`.

- [x] **Task 4: Backend — extend consent API endpoints** (AC: #2, #3, #5, #8)
  - [x] 4.1 `GrantConsentRequest` gained `consent_type: Literal['ai_processing', 'chat_processing'] = 'ai_processing'`.
  - [x] 4.2 `grant_consent_endpoint` picks the expected version via `_required_version(body.consent_type)`; 422 envelope now includes `consentType` in `details`.
  - [x] 4.3 `get_consent_status_endpoint` widened `type` Literal; `ConsentStatusResponse` now exposes `revoked_at`.
  - [x] 4.4 Added `DELETE /users/me/consent`: 400 `CONSENT_TYPE_NOT_REVOCABLE` for ai_processing; shares the grant rate-limit bucket; calls `consent_service.revoke_chat_consent`; logs `action=consent_revoke`; returns 204.

- [x] **Task 5: Backend — tests** (AC: #9)
  - [x] 5.1 New `backend/tests/test_consent_chat.py` covers AC #9(a)–(i) — grant/revoke/re-grant, independent streams both ways, 422 with `consentType`, 400 `CONSENT_TYPE_NOT_REVOCABLE`, tenant isolation, integration-hook spy, shared rate-limit bucket.
  - [x] 5.2 `test_consent_service.py` gained `test_revoke_chat_consent_inserts_append_only_row` and `test_get_current_consent_status_resolves_grant_revoke_regrant`.
  - [x] 5.3 `tests/test_data_summary_api.py` now asserts `consentRecords[0].revokedAt is None` for the ai_processing row. (File is `test_data_summary_api.py`, not `test_data_summary.py` — story note honored.)
  - [x] 5.4 `.venv/bin/pytest -q tests/test_consent_chat.py tests/test_consent_service.py tests/test_consent.py tests/test_data_summary_api.py` → 31 passed. Full suite `.venv/bin/pytest -q` → 885 passed, 23 deselected.

- [x] **Task 6: Frontend — shared constants only** (AC: #1, #12)
  - [x] 6.1 `consent-version.ts` updated with the two new constants + matching TSDoc.
  - [x] 6.2 New sibling test `consent-version.test.ts` — asserts both version constants match `YYYY-MM-DD-vN` and both type constants have expected literal values.
  - [x] 6.3 No `.tsx` touched.
  - [x] 6.4 `pnpm test -- consent-version --run` → all 53 test files (501 tests) green, including the new 5-test consent-version file.

- [x] **Task 7: Documentation & cross-links** (AC: #11, #6)
  - [x] 7.1 Added a "Chat Processing Consent" subsection inside "Consent Management" in `architecture.md` covering independent version stream, append-only `revoked_at`, `revoke_chat_consent()` as the sole 10.1b hook, and a Known Gap note that `consent_version_at_creation` ships in 10.1b.
  - [x] 7.2 "Consent Drift Policy" subsection now cross-links to "Consent Management → Chat Processing Consent".
  - [x] 7.3 Nothing deferred — no `docs/tech-debt.md` entry needed.

### Review Follow-ups (AI)

- [x] **[AI-Review][HIGH] H1 fixed**: `granted_at` made nullable on `user_consents`; revoke rows now persist `granted_at=NULL`, grant rows persist `revoked_at=NULL`. `get_current_consent_status` + data-summary ordering switched to `COALESCE(granted_at, revoked_at)` so the two columns act as mutually-exclusive event-type discriminators. New migration `c7f9e3d4b1a8`, API test + service test strengthened to assert the contract. Side-effect: M1 (data-summary conflation) is also resolved — grant vs revoke records are now distinguishable by which timestamp is populated.
- [x] **[AI-Review][MEDIUM] M2 fixed**: `DELETE ?type=chat_processing` now returns `409 NO_ACTIVE_CONSENT_TO_REVOKE` when the user has no prior chat-consent row. New `_has_any_chat_consent_row` helper + `test_revoke_without_prior_grant_returns_409` test. [backend/app/api/v1/consent.py:199](../../backend/app/api/v1/consent.py#L199)
- [x] **[AI-Review][MEDIUM] M3 fixed**: AC #9(g) dropped from the story (tenant isolation isn't testable at the HTTP layer since endpoints operate on `current_user`). The now-pointless `test_tenant_isolation_chat_consent` was removed. Tenant safety is covered implicitly by query-layer `user_id` filters + existing grant/revoke tests.
- [x] **[AI-Review][MEDIUM] M4 fixed**: New migration `d8a0f2c4e6b9` adds DB-side `server_default=now()` on `granted_at` as a safety net for INSERT paths that omit the column. Secondary `ORDER BY id DESC` added in all consumer queries (`get_current_consent_status`, `_resolve_revoke_locale`, data-summary `consent_records`) for deterministic ordering under same-microsecond ties.
- [ ] **[AI-Review][LOW] L2**: `revoke_consent_endpoint` raises 400 before rate-limit check, violating "every mutation spends budget" invariant. [backend/app/api/v1/consent.py:199](../../backend/app/api/v1/consent.py#L199)
- [ ] **[AI-Review][LOW] L3**: `grant_consent` detached-copy still carries `revoked_at=record.revoked_at`; dead field (always None on grant path). [backend/app/services/consent_service.py:62](../../backend/app/services/consent_service.py#L62)

## Dev Notes

### Scope Summary

- **Backend-heavy story.** ~80% backend (model + migration + 2 endpoints extended + 1 endpoint added + service function + tests), ~5% frontend (two constants), ~15% docs + CI.
- **Reuses the Story 5.2 `user_consents` table.** No new table — adds a `revoked_at` column. The append-only invariant survives: revocation is a new row, not an UPDATE.
- **Story 10.1b dependency hook.** AC #6 is the contract this story owes to 10.1b: a single `revoke_chat_consent()` service function that 10.1b extends with the `chat_sessions` cascade. Do NOT pre-import or pre-reference the chat tables — they don't exist yet.

### Key Design Decisions (non-obvious)

- **Append-only invariant preserved with `revoked_at`.** The natural alternative — UPDATE the existing grant row to set `revoked_at` — would destroy the audit trail Story 5.2 fought for. Inserting a new row with `revoked_at` set keeps history intact and means "current state" is always "most recent row for (user, type)." Backward compatible: `ai_processing` rows never set `revoked_at`, so Story 5.2's read path keeps working unchanged.
- **Independent version streams (`CURRENT_CONSENT_VERSION` vs `CURRENT_CHAT_CONSENT_VERSION`).** A single shared version would force every user back through both consent screens whenever **either** text changed — user-hostile and conflates two different scopes. Two streams cost ~5 extra lines of code and one extra contract-check string.
- **Revoke endpoint, not grant-with-revoked-flag.** A separate `DELETE` is RESTfully clearer, allows independent rate-limit accounting, and keeps the grant request body simple (no `revoke: bool` toggle that's almost never `true`).
- **Why `chat_processing` ONLY for revoke, not `ai_processing`.** Revoking `ai_processing` would orphan the entire pipeline (transactions, profile, insights, RAG corpus, embeddings, feedback). That's the same blast radius as account deletion — already covered by Story 5.5. Adding a half-revoke path for `ai_processing` introduces a state where the user has data but no consent, which the codebase has no read-side handler for. Defer that complexity until/unless legal forces it (then it's "delete all my data," not a different code path).
- **Cascade hook deferred to 10.1b but the function exists in 10.1a.** The reverse — putting the function in 10.1b — would mean 10.1a's DELETE endpoint either doesn't fully work or has a different shape than 10.1b expects. Defining the function signature here, with a TODO body for the cascade, lets 10.1a ship a working revoke (consent state changes; chat-cascade is a no-op because there are no chat tables yet).
- **No frontend UI in this story.** The chat-consent prompt UX is owned by 10.3b (states spec) and 10.7 (Chat UI). Shipping a UI here would either duplicate 10.7 or create a vestigial screen that 10.7 immediately replaces. Constants + types only.

### Source Tree Components to Touch

```
backend/
├── app/
│   ├── core/
│   │   └── consent.py                              # add CONSENT_TYPE_CHAT_PROCESSING + CURRENT_CHAT_CONSENT_VERSION
│   ├── models/
│   │   └── consent.py                              # add revoked_at column to UserConsent
│   ├── services/
│   │   └── consent_service.py                      # extend get_current_consent_status; add revoke_chat_consent
│   ├── api/v1/
│   │   ├── consent.py                              # extend POST + GET, add DELETE
│   │   └── data_summary.py                         # ConsentRecord adds revokedAt
├── alembic/versions/
│   └── <new_hash>_add_revoked_at_to_user_consents.py    # NEW migration
└── tests/
    ├── test_consent_chat.py                        # NEW
    ├── test_consent_service.py                     # extend
    ├── test_consent.py                             # touch only if existing tests break (they shouldn't)
    └── test_data_summary.py                        # extend for revokedAt field

frontend/
└── src/features/onboarding/
    ├── consent-version.ts                          # add chat constants
    └── __tests__/consent-i18n.test.ts              # extend smoke test (or add sibling)

.github/workflows/
└── consent-version-sync.yml                        # extend grep to also diff CHAT version

_bmad-output/planning-artifacts/
└── architecture.md                                 # extend "Consent Management" subsection
```

**Do NOT touch:**
- Any `chat_sessions` / `chat_messages` table or model — they belong to 10.1b.
- Any `frontend/src/app/[locale]/(dashboard)/onboarding/**` route — chat consent is NOT a first-login gate; it's a first-chat-use prompt (10.3b/10.7).
- `frontend/src/lib/auth/consent-guard.tsx` — that guard is `ai_processing`-specific and remains unchanged. Chat consent is enforced inside the chat UI, not at the dashboard boundary.
- `backend/app/services/account_deletion_service.py` — already correctly cascades `user_consents` via `ON DELETE CASCADE` on `user_id`. The new `revoked_at` column piggybacks on the existing cascade.
- Existing Story 5.2 tests — additive change, must remain green.

### Testing Standards Summary

- **Backend:** async `pytest` with the existing `client` / `authenticated_client` fixtures. Backend venv is `backend/.venv` (memory: project convention; `pytest` from a root venv silently uses the wrong env). Command: `cd backend && .venv/bin/pytest -q tests/test_consent_chat.py tests/test_consent_service.py tests/test_consent.py tests/test_data_summary.py` then full suite once.
- **Frontend:** `vitest`. Command: `cd frontend && pnpm test -- consent`. Only the constants smoke test changes.
- **Migration smoke:** `cd backend && .venv/bin/alembic upgrade head && .venv/bin/alembic downgrade -1 && .venv/bin/alembic upgrade head` against real Postgres (`docker compose up -d postgres`).
- **Manual smoke:** (1) authenticated curl `POST /api/v1/users/me/consent` with `consentType=chat_processing` + correct version → 201, row in DB. (2) `GET /api/v1/users/me/consent?type=chat_processing` → `hasCurrentConsent=true`. (3) `DELETE /api/v1/users/me/consent?type=chat_processing` → 204. (4) GET again → `hasCurrentConsent=false`, `revokedAt` populated. (5) Re-grant → `hasCurrentConsent=true`. (6) `GET /api/v1/users/me/data-summary` → `consentRecords[]` includes `revokedAt`. (7) `DELETE /api/v1/users/me/consent?type=ai_processing` → 400 with code `CONSENT_TYPE_NOT_REVOCABLE`.

### Project Structure Notes

- All paths align with the existing structure established in Story 5.2. No new top-level directories.
- Architecture doc remains a single file (last counted ~1817 lines) — extend inline in the existing "Consent Management" subsection; do not shard.
- Frontend `AGENTS.md` warning still applies — but this story doesn't touch any Next.js route or layout files, so the "read `node_modules/next/dist/docs/`" mandate is irrelevant here.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#L2106](../planning-artifacts/epics.md#L2106) — Story 10.1a description (the bullet under Epic 10 Stories).
- [Source: _bmad-output/planning-artifacts/prd.md#L691](../planning-artifacts/prd.md#L691) — FR71 (separate `chat_processing` consent).
- [Source: _bmad-output/planning-artifacts/prd.md#L302](../planning-artifacts/prd.md#L302) — Privacy section: chat-processing consent scope and narrower blast radius.
- [Source: _bmad-output/planning-artifacts/architecture.md#L1716](../planning-artifacts/architecture.md#L1716) — "Consent Drift Policy" (defines `consent_version_at_creation` capture; chat-session integration in 10.1b).
- [Source: _bmad-output/planning-artifacts/architecture.md#L1769](../planning-artifacts/architecture.md#L1769) — Data Model Additions for Epic 10 (chat_sessions + chat_messages — 10.1b territory; do not touch here).
- [Source: backend/app/core/consent.py](../../backend/app/core/consent.py) — existing constants + bump-rules docstring (extend, don't replace).
- [Source: backend/app/models/consent.py](../../backend/app/models/consent.py) — existing `UserConsent` SQLModel (add column).
- [Source: backend/app/services/consent_service.py](../../backend/app/services/consent_service.py) — existing `grant_consent` + `get_current_consent_status` (extend; preserve detached-copy pattern).
- [Source: backend/app/api/v1/consent.py](../../backend/app/api/v1/consent.py) — existing endpoints (extend POST + GET, add DELETE).
- [Source: backend/app/api/v1/data_summary.py:47](../../backend/app/api/v1/data_summary.py#L47) — `ConsentRecord` schema (add `revokedAt`).
- [Source: backend/app/services/rate_limiter.py:89](../../backend/app/services/rate_limiter.py#L89) — `check_consent_rate_limit` (reuse for DELETE; same bucket as grants).
- [Source: backend/alembic/versions/a7b9c1d2e3f4_create_user_consents_table.py](../../backend/alembic/versions/a7b9c1d2e3f4_create_user_consents_table.py) — migration style template.
- [Source: frontend/src/features/onboarding/consent-version.ts](../../frontend/src/features/onboarding/consent-version.ts) — frontend constants mirror.
- [Source: .github/workflows/consent-version-sync.yml](../../.github/workflows/consent-version-sync.yml) — CI version-sync guardrail (extend to cover both versions).
- [Source: _bmad-output/implementation-artifacts/5-2-privacy-explanation-consent-during-onboarding.md](./5-2-privacy-explanation-consent-during-onboarding.md) — Story 5.2 (the foundation; design rationale + debug-log notes apply directly).
- [Source: docs/tech-debt.md](../../docs/tech-debt.md) — TD register; TD-NNN entries only if scope is deferred.

### Developer Guardrails (things that will bite you)

1. **Backend venv is `backend/.venv`** — never `pytest` from a root venv (project memory). Same for `alembic`.
2. **Append-only is non-negotiable.** A revocation is an INSERT of a new row with `revoked_at` set. It is NEVER an UPDATE on an existing row. Reviewers will reject the latter.
3. **Two version constants, two streams.** Bumping `CURRENT_CONSENT_VERSION` MUST NOT bump `CURRENT_CHAT_CONSENT_VERSION` and vice versa. The contract check must verify each independently.
4. **Do NOT pre-import `chat_sessions` or `chat_messages`** in `consent_service.py` — those tables don't exist until 10.1b. The TODO marker is the entire integration contract; don't try to be helpful.
5. **`ai_processing` DELETE returns 400, not 204.** Do not even silently no-op it — that would hide a misuse. Explicit error code `CONSENT_TYPE_NOT_REVOCABLE` with a message pointing to account deletion.
6. **Tenant isolation.** Every query in the new code paths MUST filter by `user_id = current_user.id`. The tests cover this; do not let it slip in production code.
7. **Rate-limit bucket is shared between grant and revoke.** Don't add a second key — that defeats the abuse mitigation (grant→revoke→grant→… would burn the audit log).
8. **No new UI.** If you find yourself editing a `.tsx` file other than `consent-version.ts` or its test, you're in the wrong story. Tell the user; stop.
9. **The data-summary contract gains a nullable field.** Existing Story 5.4 frontend consumers must keep working — `revokedAt: null` for all existing rows is a non-breaking addition. Do NOT make the field required on the response model.
10. **Migration must be reversible.** `op.add_column` + `op.drop_column`. Test downgrade on real Postgres before pushing.

### Previous Story Intelligence (Story 9.7 + Story 5.2)

- **Story 5.2** is the direct architectural foundation — table, service, API, CI guardrail, frontend constants. The patterns established there (append-only, detached-copy, version-stream contract, per-user rate limit, alias_generator camelCase) are all reused. Read its Dev Notes (especially the Debug Log on `MissingGreenlet`) before writing the new service code.
- **Story 9.7** (most recent committed) wired Bedrock IAM + observability — chat plumbing infra; no overlap with this story's surface area.
- The recent Epic 9 work (9.5a/b/c, 9.6, 9.7) means `llm.py` and Bedrock are now mature — that lets Epic 10 proceed, but 10.1a doesn't touch the LLM layer.

### Git Intelligence

Recent commits (last 5):
```
5f4f567 Story 9.7: Bedrock IAM + Observability Plumbing
a4bd508 Story 9.6: Embedding Migration — text-embedding-3-large (3072-dim halfvec)
cccdeff Story 9.5c: Cross-Provider Regression Suite (LLM agents × {anthropic, openai, bedrock})
6251282 Story 9.5b: Add Bedrock Provider Path + Smoke Test
7d99958 Story 9.5a: Provider-Routing Refactor (Anthropic + OpenAI only)
```

- All recent work is Epic 9 LLM/embedding infra. Zero overlap with `user_consents` table or consent service. No conflicts expected.
- The `_bmad-output/implementation-artifacts/9-8-pipeline-orchestration-evaluation-spike.md` is currently `ready-for-dev` (not yet committed). Independent surface — no conflict.
- Branch is clean except for the sprint-status.yaml + 9.8 spike file noted in `git status`.

### Latest Tech Information

No external library research required. Everything reuses the Story 5.2 stack:
- `sqlmodel` for the column addition.
- `alembic` for the migration (existing style).
- `pydantic` `Literal` for the `consent_type` query/body discriminator.
- `pytest-asyncio` + `httpx.AsyncClient` for tests.
- `next-auth` / TanStack Query — not used in 10.1a (no UI).

## Project Context Reference

- Planning artifacts: [epics.md §Epic 10 Story 10.1a](../planning-artifacts/epics.md#L2106), [prd.md FR71](../planning-artifacts/prd.md#L691), [architecture.md §Consent Drift Policy](../planning-artifacts/architecture.md#L1716), [architecture.md §Data Model Additions for Chat](../planning-artifacts/architecture.md#L1769).
- Sibling Epic 10 stories: **10.1b** (consumes the `revoke_chat_consent` hook + adds `chat_sessions` / `chat_messages` schema with `consent_version_at_creation`), **10.3b** (UX states spec including consent first-use prompt + version-bump re-prompt copy), **10.7** (chat UI surfaces the actual consent gate + revoke control), **10.10** (chat history + deletion — distinct from consent revocation but uses overlapping cascade plumbing).
- Foundational predecessor: **Story 5.2** (privacy explanation + onboarding consent) — same table, same service, same CI guardrail. This story extends 5.2's foundation rather than parallelling it.
- Sprint status: this story is `backlog` → set to `ready-for-dev` on file save → dev agent picks up next. Epic 10 status will flip from `backlog` → `in-progress` when this story moves to `ready-for-dev`.

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (Claude Opus 4.7, 1M context)

### Debug Log References

- Alembic reversibility verified on real Postgres (`kopiika-ai-postgres-1`, eu-central-1 pgvector image): `upgrade head → b5e8d1f2a3c7`, `downgrade -1 → e0f04e4194bc`, `upgrade head → b5e8d1f2a3c7`, all clean.
- Backend tests: scoped suite 31 passed; full suite 885 passed, 23 deselected (only pre-existing `HTTP_422_UNPROCESSABLE_ENTITY` deprecation warnings, unchanged by this story).
- Frontend tests: full suite 501 passed across 53 files (vitest run mode). New `consent-version.test.ts` file adds 5 tests.
- No hook-cascade logic added for chat sessions — the `TODO(10.1b)` marker in `revoke_chat_consent` is intentional per AC #6 (10.1b wires the cascade by editing the same function).

### Completion Notes List

- **Append-only invariant preserved.** Revocation is always `INSERT` of a new row with `revoked_at = utcnow()`. Existing `ai_processing` rows remain untouched (revoked_at stays NULL).
- **Independent version streams.** Two separate constants; CI workflow enforces each pair (backend vs frontend) via a reusable `check_pair` bash helper so bumping one does not require bumping the other.
- **Back-compat for Story 5.2 clients.** `consent_type` defaults to `'ai_processing'` on POST, so unchanged clients keep working. `GET /consent` without `type` still returns the ai_processing status.
- **Single integration point for 10.1b.** `consent_service.revoke_chat_consent()` is the only place to wire the chat-session cascade; a `TODO(10.1b)` marker is placed at function tail. The API endpoint calls this service function (spy test in `test_consent_chat.py::test_delete_calls_revoke_chat_consent_service` asserts the contract).
- **Rate limit shared across grant + revoke.** Both endpoints call `RateLimiter.check_consent_rate_limit(user_id)` — same key, same bucket. Unit-asserted by `test_rate_limit_shared_across_grant_and_revoke`.
- **Status response change.** `ConsentStatusResponse` gained a nullable `revokedAt` field. Existing Story 5.2 tests pass unchanged because the service still returns the server's required `version` (not the stored row's) — matching the prior contract for the backward-compat cases.
- **No FE UI added.** Only constants + a vitest smoke test. UX for chat consent is owned by Stories 10.3b (first-use prompt) and 10.7 (chat screen gate + revoke control).
- **Docs updated inline.** New "Chat Processing Consent" subsection under "Consent Management" in `architecture.md`; "Consent Drift Policy" now cross-links to it.

### File List

**Backend — modified**
- `backend/app/core/consent.py` — added `CONSENT_TYPE_CHAT_PROCESSING`, `CURRENT_CHAT_CONSENT_VERSION`; expanded module docstring.
- `backend/app/models/consent.py` — added nullable `revoked_at: datetime | None` column on `UserConsent`.
- `backend/app/services/consent_service.py` — rewrote `get_current_consent_status` to "most-recent row wins" + revoked_at + version check; added `revoke_chat_consent`.
- `backend/app/api/v1/consent.py` — widened POST/GET `type`; added DELETE; updated error envelope with `consentType`; `ConsentStatusResponse.revoked_at`.
- `backend/app/api/v1/data_summary.py` — `ConsentRecord.revoked_at`; projected in `get_data_summary`.

**Backend — created**
- `backend/alembic/versions/b5e8d1f2a3c7_add_revoked_at_to_user_consents.py` — new migration.
- `backend/alembic/versions/c7f9e3d4b1a8_make_granted_at_nullable.py` — post-review H1 fix migration (revoke rows persist `granted_at=NULL`).
- `backend/alembic/versions/d8a0f2c4e6b9_consent_granted_at_server_default.py` — post-review M4 fix migration (DB-side `server_default=now()` on `granted_at`).
- `backend/tests/test_consent_chat.py` — AC #9 coverage (a–i).

**Backend — extended**
- `backend/tests/test_consent_service.py` — added append-only revoke + grant→revoke→regrant tests.
- `backend/tests/test_data_summary_api.py` — asserts `consentRecords[].revokedAt` present and null for ai_processing.

**Frontend — modified**
- `frontend/src/features/onboarding/consent-version.ts` — added chat constants; expanded TSDoc.

**Frontend — created**
- `frontend/src/features/onboarding/__tests__/consent-version.test.ts` — smoke test for both constant pairs.

**CI / infra**
- `.github/workflows/consent-version-sync.yml` — extended to diff both `CURRENT_CONSENT_VERSION` and `CURRENT_CHAT_CONSENT_VERSION` pairs in a single job.

**Docs**
- `_bmad-output/planning-artifacts/architecture.md` — "Chat Processing Consent" subsection added inside "Consent Management"; cross-link added in "Consent Drift Policy".

**Project**
- `VERSION` — bumped `1.39.0 → 1.40.0` (minor — new user-facing API surface per versioning policy).
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — `10-1a-chat-processing-consent: ready-for-dev → in-progress → review`.

### Change Log

- 2026-04-24 — Story 10.1a implemented. Added `chat_processing` consent as an independent, revocable consent stream sharing the `user_consents` table with `ai_processing`. Includes new migration (`b5e8d1f2a3c7`), new DELETE endpoint, expanded POST/GET contract, updated data-summary export, frontend constants + test, and CI sync guardrail for both version pairs.
- 2026-04-24 — Version bumped from `1.39.0` to `1.40.0` per story completion (new user-facing API surface).
- 2026-04-24 — Code review H1 fix: `granted_at` made nullable on `user_consents`; revoke rows persist `granted_at=NULL` so `granted_at`/`revoked_at` are mutually-exclusive event-type discriminators. Added migration `c7f9e3d4b1a8`. GET/consent + data-summary ordering switched to `COALESCE(granted_at, revoked_at) DESC`. Full backend suite: 885 passed.
- 2026-04-24 — Code review M2/M3/M4 fixes: (M2) DELETE without prior grant → `409 NO_ACTIVE_CONSENT_TO_REVOKE`; (M3) AC #9(g) dropped, tenant-isolation test removed; (M4) new migration `d8a0f2c4e6b9` adds DB-side `server_default=now()` on `granted_at`, and `ORDER BY id DESC` secondary sort added to all consumer queries. Full backend suite: 885 passed. L2/L3 remain story-local (listed in Review Follow-ups).
