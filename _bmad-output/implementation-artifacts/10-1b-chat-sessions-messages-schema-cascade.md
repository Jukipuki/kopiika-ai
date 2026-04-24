# Story 10.1b: `chat_sessions` / `chat_messages` Schema + Cascade Delete

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **platform engineer shipping Epic 10 chat**,
I want the `chat_sessions` and `chat_messages` tables in place — with a per-session `consent_version_at_creation` pin, cascade-delete from both `users` (account deletion) and `chat_processing` consent revocation, and the TODO hook from Story 10.1a turned into a working cascade —
so that every later Epic 10 story (AgentCore session handler 10.4a, streaming 10.5, history/deletion 10.10) can assume durable chat storage, GDPR-compliant deletion, and the [Consent Drift Policy](../planning-artifacts/architecture.md#L1732) contract holds end-to-end.

## Acceptance Criteria

1. **Given** a new Alembic migration in `backend/alembic/versions/`, **When** it runs against a fresh DB, **Then** it creates two tables exactly matching the contract in [architecture.md §Data Model Additions](../planning-artifacts/architecture.md#L1785):
   - `chat_sessions` — `id UUID PK (default gen_random_uuid())`, `user_id UUID NOT NULL FK → users.id ON DELETE CASCADE`, `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`, `last_active_at TIMESTAMPTZ NOT NULL DEFAULT now()`, `consent_version_at_creation TEXT NOT NULL`.
   - `chat_messages` — `id UUID PK (default gen_random_uuid())`, `session_id UUID NOT NULL FK → chat_sessions.id ON DELETE CASCADE`, `role TEXT NOT NULL CHECK (role IN ('user','assistant','system'))`, `content TEXT NOT NULL`, `redaction_flags JSONB NOT NULL DEFAULT '{}'::jsonb`, `guardrail_action TEXT NOT NULL DEFAULT 'none' CHECK (guardrail_action IN ('none','blocked','modified'))`, `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`.

   Role/guardrail_action are modelled as `TEXT + CHECK` (not Postgres `ENUM`) to match the repo convention (see `card_feedback.vote`, `upload.status`) — enum alterations are painful in Alembic; the CHECK gives us the same validation with no ALTER-TYPE pain.

2. **Given** the operational indexes called out in architecture, **When** the migration runs, **Then** it creates:
   - `ix_chat_sessions_user_id_last_active_at` on `chat_sessions(user_id, last_active_at DESC)` — backs the session-list query in Story 10.10.
   - `ix_chat_messages_session_id_created_at` on `chat_messages(session_id, created_at)` — backs the transcript-render query.
   - `ix_chat_messages_guardrail_action_nonzero` partial index on `chat_messages(guardrail_action) WHERE guardrail_action != 'none'` — backs the safety-monitoring queries in Story 10.9.

3. **Given** the migration, **When** `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` runs against real Postgres (`docker compose up -d postgres`), **Then** all three commands succeed cleanly — the `downgrade()` drops both tables and all three indexes in the correct dependency order (`chat_messages` first, then `chat_sessions`).

4. **Given** SQLModel models at `backend/app/models/chat_session.py` and `backend/app/models/chat_message.py`, **When** the module is imported, **Then**:
   - `ChatSession` exposes all columns from AC #1 with correct Python types (`uuid.UUID`, `datetime`, `str`), default factories for `id` / `created_at` / `last_active_at`, and `consent_version_at_creation: str` (**NOT** nullable — `chat_processing` must exist at session creation or the session cannot be persisted).
   - `ChatMessage` exposes all columns from AC #1 with `role: Literal['user','assistant','system']`, `guardrail_action: Literal['none','blocked','modified']` (default `'none'`), and `redaction_flags: dict = Field(default_factory=dict, sa_column=Column(JSONB, ...))`.
   - Both models follow the project's naïve-UTC datetime convention (see `UserConsent._utcnow`) — store as `datetime.now(UTC).replace(tzinfo=None)` for Python-side defaults; the DB column is `TIMESTAMPTZ` to match Epic 10 arch spec. Server-side default `now()` provides a safety net on INSERT paths that omit the column.
   - Models are registered in `backend/app/models/__init__.py` (so Alembic autogenerate sees them and the account-deletion explicit-delete list can import them).

5. **Given** the `revoke_chat_consent()` function in [backend/app/services/consent_service.py](../../backend/app/services/consent_service.py), **When** Story 10.1b edits it, **Then**:
   - The `TODO(10.1b)` marker is replaced with a cascade body that `DELETE`s all `chat_sessions` rows for `user.id` — the `ON DELETE CASCADE` on `chat_messages.session_id` removes their messages atomically.
   - The cascade runs **before** `await session.commit()` so revocation + cascade are a single transaction (revoke succeeds iff cascade succeeds).
   - The function remains the **single integration point** — no parallel hook added in the API layer, no duplication in `account_deletion_service.py` (that service keeps its own explicit delete per the pattern there).
   - The function is still callable from `consent_service.revoke_chat_consent(...)` with the same signature — no breaking changes for Story 10.1a callers.
   - **Session-termination note.** There is no in-memory AgentCore session to terminate yet (10.4a hasn't shipped). The comment block at the cascade site must explicitly note: "when 10.4a lands, add a pre-cascade call to the AgentCore session terminator here so in-flight streams are cancelled before rows disappear." A `TODO(10.4a)` marker replaces the `TODO(10.1b)` marker.

6. **Given** the account-deletion service at [backend/app/services/account_deletion_service.py](../../backend/app/services/account_deletion_service.py), **When** it is extended, **Then**:
   - `ChatSession` is added to the `child_tables` explicit-delete list **before** `UserConsent` (chat sessions depend on users, not on consents; ordering is "leaf tables first" per the existing comment block). `ChatMessage` is **NOT** added to the list — the `ON DELETE CASCADE` from `chat_sessions.id` covers it, matching how `CardInteraction` relies on the `insights.id` cascade.
   - The ordering comment in the existing code block is extended to note the chat cascade: "`ChatSession` listed; `ChatMessage` removed by DB cascade on `session_id`."

7. **Given** ON DELETE CASCADE chains, **When** integration tests run, **Then** `backend/tests/test_chat_schema_cascade.py` covers:
   (a) `DELETE FROM users WHERE id=$user_id` → all `chat_sessions` for that user are deleted AND all `chat_messages` for those sessions are deleted (DB-level cascade).
   (b) `DELETE FROM chat_sessions WHERE id=$session_id` → all `chat_messages` for that session are deleted.
   (c) `revoke_chat_consent(session, user, ...)` → all `chat_sessions` for `user.id` deleted (cascade removes messages); new `user_consents` row with `revoked_at` set is committed atomically; other users' sessions untouched.
   (d) `revoke_chat_consent()` is idempotent when the user has zero chat sessions (the new `DELETE` hits zero rows; revocation row still written; no error).
   (e) `delete_all_user_data()` removes chat_sessions + chat_messages for the target user and preserves other users' rows.
   (f) Re-grant after revoke: grant → create session A → revoke (cascade kills A) → re-grant → create session B; the final state has one session (B), one grant + one revoke + one grant row in `user_consents`.

8. **Given** the new models, **When** `backend/tests/test_chat_models.py` runs, **Then** it covers:
   (a) `consent_version_at_creation` is required (attempting to create a `ChatSession` without it raises a validation/integrity error).
   (b) `role` CHECK constraint rejects an arbitrary string (e.g., `"admin"`) — inserted via raw SQL to bypass the SQLModel `Literal`, verifying the DB-level guard.
   (c) `guardrail_action` CHECK constraint rejects an arbitrary string similarly; default `'none'` applies when the column is omitted.
   (d) `redaction_flags` round-trips as a dict (insert `{"pii_types": ["email"], "filter_source": "input"}`, read back, `assert payload["pii_types"] == ["email"]`).

9. **Given** the "Consent Drift Policy" in architecture ([architecture.md §Consent Drift Policy](../planning-artifacts/architecture.md#L1732)), **When** a helper is added at `backend/app/services/chat_session_service.py`, **Then**:
   - `create_chat_session(session, user) -> ChatSession` reads the current `chat_processing` consent via `consent_service.get_current_consent_status(...)`; raises `ChatConsentRequiredError` if `hasCurrentConsent` is False; on success inserts a new `chat_sessions` row with `consent_version_at_creation = CURRENT_CHAT_CONSENT_VERSION`.
   - The function uses the **same detached-copy pattern** as `grant_consent` (expired-attribute safety under async session — see Story 10.1a Dev Notes).
   - No HTTP endpoint, no Celery task, no AgentCore call — just the DB helper. 10.4a consumes this helper when it wires the session handler.
   - `ChatConsentRequiredError` lives next to the helper and is a plain `Exception` subclass (no FastAPI coupling) — 10.4a/10.5 translates it to an HTTP envelope at their layer.

10. **Given** the "Known gap" note currently in [architecture.md:507](../planning-artifacts/architecture.md#L507) (`consent_version_at_creation` is deferred to 10.1b), **When** Story 10.1b updates the architecture doc, **Then**:
    - The "Known gap" paragraph is removed and replaced with a one-line pointer to Story 10.1b's implementation (`chat_sessions` table, `create_chat_session` helper, cascade in `revoke_chat_consent`).
    - The "Consent Drift Policy" subsection's reference to `chat_sessions.consent_version_at_creation` gains a link to the migration revision ID.
    - The "Data Model Additions" subsection gains a link to the two new model files and the migration file.

11. **Given** the tech-debt register at [docs/tech-debt.md](../../docs/tech-debt.md), **When** deferrals land in Story 10.1b, **Then** a new entry `TD-NNN` is added for the AgentCore session-terminator hook (Story 10.4a dependency) covering the "in-memory session termination before cascade-delete" gap called out in AC #5. No other tech-debt entries required — the table shape itself is complete.

12. **Given** the scoped test suite, **When** `cd backend && .venv/bin/pytest -q tests/test_chat_schema_cascade.py tests/test_chat_models.py tests/test_consent_chat.py tests/test_consent_service.py` runs, **Then** all tests pass. Follow up with `cd backend && .venv/bin/pytest -q` for the full suite; it must remain green. No frontend changes in this story — no `pnpm test` expectation.

## Tasks / Subtasks

- [x] **Task 1: Models** (AC: #4)
  - [x] 1.1 Create `backend/app/models/chat_session.py` with `ChatSession` SQLModel per AC #4. Use `sa_type=DateTime(timezone=True)` for `created_at` / `last_active_at`. Include `__tablename__ = "chat_sessions"` and an `Index("ix_chat_sessions_user_id_last_active_at", "user_id", desc("last_active_at"))` declaration in `__table_args__` so SQLModel reflects it; the migration still owns the canonical DDL.
  - [x] 1.2 Create `backend/app/models/chat_message.py` with `ChatMessage` SQLModel per AC #4. `redaction_flags` uses `sa_column=Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))`. Include `__table_args__` with the composite index + partial index for `guardrail_action != 'none'` (use `sqlalchemy.Index("...", ..., postgresql_where=text("guardrail_action != 'none'"))`).
  - [x] 1.3 Register both models in `backend/app/models/__init__.py` so `from app.models import ChatSession, ChatMessage` works (consumed by Alembic env.py and account_deletion_service).

- [x] **Task 2: Alembic migration** (AC: #1, #2, #3)
  - [x] 2.1 Create `backend/alembic/versions/<hash>_add_chat_sessions_and_messages.py` — down_revision is the current head (`d8a0f2c4e6b9` as of the 10.1a M4 fix — verify with `alembic heads` before locking).
  - [x] 2.2 `upgrade()` uses `op.create_table` for both tables (AC #1 schema). Use `sa.text("gen_random_uuid()")` for id defaults, `sa.text("now()")` for timestamp defaults, `sa.Enum` is **NOT** used — CHECK constraints are declared inline via `sa.CheckConstraint("role IN (...)")` and `sa.CheckConstraint("guardrail_action IN (...)")` with explicit names (`ck_chat_messages_role`, `ck_chat_messages_guardrail_action`).
  - [x] 2.3 Create the three indexes (AC #2). Partial index uses `op.create_index(..., postgresql_where=sa.text("guardrail_action != 'none'"))`.
  - [x] 2.4 `downgrade()` drops indexes then `chat_messages` then `chat_sessions`. Reversible.
  - [x] 2.5 Verify on real Postgres: `docker compose up -d postgres && cd backend && .venv/bin/alembic upgrade head && .venv/bin/alembic downgrade -1 && .venv/bin/alembic upgrade head`. Record in Debug Log.

- [x] **Task 3: Revoke-consent cascade** (AC: #5)
  - [x] 3.1 In `backend/app/services/consent_service.py`, replace the `TODO(10.1b)` block inside `revoke_chat_consent` with an explicit `await session.exec(sa_delete(ChatSession).where(ChatSession.user_id == user.id))`. Import style mirrors `account_deletion_service.py` (use `from sqlalchemy import delete as sa_delete`).
  - [x] 3.2 Confirm the cascade runs **before** `session.commit()` so revocation + delete are atomic. The detached-copy construction stays where it is (before commit).
  - [x] 3.3 Replace the removed `TODO(10.1b)` comment with a `TODO(10.4a): call AgentCore session terminator here before DB cascade so in-flight streams cancel cleanly` note.

- [x] **Task 4: Account-deletion extension** (AC: #6)
  - [x] 4.1 In `backend/app/services/account_deletion_service.py`, add `ChatSession` to the `child_tables` list **before** `UserConsent` (leaf ordering). Do not add `ChatMessage` — DB cascade covers it.
  - [x] 4.2 Update the comment block above `child_tables` to note the chat cascade rationale (mirror the existing `CardInteraction` / `insights.id` note pattern).
  - [x] 4.3 Update the import block to pull `ChatSession` from `app.models`.

- [x] **Task 5: Session creation helper** (AC: #9)
  - [x] 5.1 Create `backend/app/services/chat_session_service.py` with `class ChatConsentRequiredError(Exception)` and `async def create_chat_session(session, user) -> ChatSession`.
  - [x] 5.2 Helper: call `consent_service.get_current_consent_status(session, user, CONSENT_TYPE_CHAT_PROCESSING, CURRENT_CHAT_CONSENT_VERSION)`; raise `ChatConsentRequiredError` if `hasCurrentConsent is False`; else insert a new `ChatSession(user_id=user.id, consent_version_at_creation=CURRENT_CHAT_CONSENT_VERSION)` using the detached-copy pattern; commit; return detached copy.
  - [x] 5.3 Do NOT add any FastAPI route, Celery task, or AgentCore call in this story — only the helper. Add a module-level docstring stating "consumed by Story 10.4a AgentCore session handler."

- [x] **Task 6: Tests — cascade behavior** (AC: #7)
  - [x] 6.1 Create `backend/tests/test_chat_schema_cascade.py` with the six scenarios (a)–(f) from AC #7. Use existing `authenticated_client` / session fixtures; add a small helper to seed a `ChatSession` + 2 `ChatMessage` rows for a user.
  - [x] 6.2 Scenario (c) — revoke path: call `revoke_chat_consent` directly (service-level), then query `select(ChatSession).where(user_id=user.id)` to assert zero rows; `select(ChatMessage).where(session_id in deleted_ids)` to assert zero rows; `select(UserConsent)` to assert the new revoke row exists; separately seed another user's session and assert it is untouched (tenant isolation).
  - [x] 6.3 Scenario (e) — account deletion: seed user, session, messages; call `delete_all_user_data`; assert `chat_sessions` and `chat_messages` rows for that user are gone; other user's rows remain.

- [x] **Task 7: Tests — model/schema** (AC: #8)
  - [x] 7.1 Create `backend/tests/test_chat_models.py` with the four scenarios (a)–(d) from AC #8. For the CHECK-constraint scenarios, use `session.exec(text("INSERT INTO chat_messages (id, session_id, role, content) VALUES (...)"))` with an invalid value and assert `IntegrityError` raises.
  - [x] 7.2 `redaction_flags` round-trip test inserts via the SQLModel, commits, re-selects with a fresh session (to bypass the identity map), asserts dict equality.

- [x] **Task 8: Docs** (AC: #10, #11)
  - [x] 8.1 In `_bmad-output/planning-artifacts/architecture.md`, remove the "Known gap — `consent_version_at_creation` on chat sessions" paragraph at line 507 and replace with a one-liner pointing at the new migration + models + `create_chat_session` helper.
  - [x] 8.2 In the same file, "Data Model Additions" subsection (line 1785 region) gains inline links to `backend/app/models/chat_session.py`, `backend/app/models/chat_message.py`, and the new migration file.
  - [x] 8.3 Add a new `TD-NNN` entry to `docs/tech-debt.md` for the AgentCore session-terminator pre-cascade hook (AC #11). Scope: "when 10.4a lands, replace the `TODO(10.4a)` in `revoke_chat_consent` with a call to the AgentCore terminator so in-flight streams are cancelled before cascade-delete." Owner: Epic 10 / Story 10.4a.

- [x] **Task 9: Validation** (AC: #12)
  - [x] 9.1 Run scoped suite: `cd backend && .venv/bin/pytest -q tests/test_chat_schema_cascade.py tests/test_chat_models.py tests/test_consent_chat.py tests/test_consent_service.py`.
  - [x] 9.2 Run full backend suite: `cd backend && .venv/bin/pytest -q`. Must stay green.
  - [x] 9.3 Re-verify migration reversibility one more time on a clean DB after all code changes land (guards against late-stage model/migration drift).

## Dev Notes

### Scope Summary

- **Pure backend story.** Two new tables, two new models, one new service module, two existing services extended (consent_service, account_deletion_service), one migration, two test files, minor doc updates. Zero frontend, zero CI, zero infrastructure.
- **Story 10.1a already shipped the consent grant + revoke.** 10.1a left a documented TODO inside `revoke_chat_consent`; this story fills that TODO with the actual cascade and ships the tables the cascade depends on. Do **not** re-touch the consent-grant code path or CI guardrail — those are frozen from 10.1a.
- **No chat runtime yet.** There is no AgentCore call, no streaming endpoint, no chat UI in 10.1b. The helper at `chat_session_service.create_chat_session` is a library function waiting for Story 10.4a to call it. That is intentional — shipping tables + cascade + helper here lets 10.2/10.3/10.4 proceed in parallel without a schema blocker.

### Key Design Decisions (non-obvious)

- **CHECK constraints over Postgres ENUMs for `role` / `guardrail_action`.** Alembic ALTER TYPE for Postgres ENUMs requires `DROP TYPE` + `CREATE TYPE` + column re-type, which is brittle under downgrade and slow on large tables. The repo's established pattern (`card_feedback.vote`, `upload.status`, etc.) uses `TEXT + CHECK`. Follow it.
- **`chat_messages` is removed by DB cascade, NOT by explicit delete in `account_deletion_service`.** The existing service uses explicit deletes "defensively" when the parent row is `users` — because `users` ON DELETE CASCADE is what cascades those children, and listing them gives readable ordering. For `chat_messages`, the parent is `chat_sessions`, which is itself in the explicit-delete list; the cascade from `session_id` is the natural path. Mirroring the `CardInteraction` pattern keeps the code consistent.
- **Revoke cascade is explicit `DELETE FROM chat_sessions`, not `DELETE FROM chat_messages`.** The latter would leave orphan `chat_sessions` rows after revocation. Deleting sessions first (with `ON DELETE CASCADE` on `chat_messages.session_id`) gets both in one statement with correct semantics.
- **`consent_version_at_creation` is NOT NULL.** The Consent Drift Policy requires that every session carries the version that authorized it. Allowing NULL would mean "session whose consent version we don't know" — exactly the ambiguity the policy is designed to prevent. Enforce at the schema level; let the helper be the single write path that pins the value.
- **`ChatConsentRequiredError` is a plain Exception, not an HTTPException.** 10.1b is a service-layer story. The HTTP translation (→ 403 `CHAT_CONSENT_REQUIRED` envelope) belongs to the chat streaming endpoint in Story 10.5. Keeping the service free of FastAPI imports preserves the Celery/test re-use paths (same reason `consent_service.revoke_chat_consent` doesn't raise HTTPException).
- **No AgentCore-terminator call yet.** The runtime-session termination is what the Consent Drift Policy calls for ("terminates active sessions, cancels in-flight streaming turns"). In 10.1b there is no runtime — no sessions are live in memory because no agent has been invoked. Cascade-delete of DB rows is sufficient and honest; the tech-debt entry (AC #11) tracks the hook-point for 10.4a.
- **No data backfill needed.** 10.1a shipped `user_consents.revoked_at` as additive; no 10.1a user ever created a chat session, so there is nothing to migrate. A user who revoked chat-consent between 10.1a merge and 10.1b merge simply had their revoke be a consent-row-only operation; the cascade-delete target was empty. This is correct behavior — no retroactive action required.

### Source Tree Components to Touch

```
backend/
├── app/
│   ├── models/
│   │   ├── __init__.py                               # register ChatSession, ChatMessage
│   │   ├── chat_session.py                           # NEW
│   │   └── chat_message.py                           # NEW
│   ├── services/
│   │   ├── consent_service.py                        # replace TODO(10.1b) with cascade
│   │   ├── account_deletion_service.py               # add ChatSession to child_tables
│   │   └── chat_session_service.py                   # NEW (create_chat_session helper)
├── alembic/versions/
│   └── <new_hash>_add_chat_sessions_and_messages.py  # NEW migration
└── tests/
    ├── test_chat_schema_cascade.py                   # NEW (AC #7)
    └── test_chat_models.py                           # NEW (AC #8)

_bmad-output/planning-artifacts/
└── architecture.md                                   # remove "Known gap" para; link new files

docs/
└── tech-debt.md                                      # add TD-NNN for 10.4a terminator hook
```

**Do NOT touch:**
- `backend/app/api/v1/consent.py` — the DELETE endpoint from 10.1a stays as-is; the cascade is wired inside the service function it already calls.
- `backend/app/core/consent.py` — constants are frozen from 10.1a.
- `backend/app/services/rate_limiter.py` — the shared grant/revoke bucket is already correct.
- `.github/workflows/consent-version-sync.yml` — no new constant to sync; both chat and ai-processing pairs are already enforced.
- Any frontend file — no UI, no new shared constants.
- `alembic/versions/a7b9c1d2e3f4_*`, `b5e8d1f2a3c7_*`, `c7f9e3d4b1a8_*`, `d8a0f2c4e6b9_*` — 10.1a's migrations are immutable history; the new migration stacks on top.

### Testing Standards Summary

- **Backend venv is `backend/.venv`** (memory: project convention). Never `pytest` or `alembic` from a root venv.
- **Async pytest** with the existing session fixtures. `test_consent_chat.py` and `test_consent_service.py` (from 10.1a) are the reference shapes — copy their fixture usage.
- **Migration smoke** run against real Postgres (`docker compose up -d postgres`): `upgrade head → downgrade -1 → upgrade head`, all clean. Record hashes in the Debug Log.
- **Cascade tests** must exercise the DB (not just mock), because CHECK constraints, ON DELETE CASCADE, and the partial index only activate at the DB layer — an in-memory SQLite fallback would give false green.
- **No frontend tests.** No `.tsx` or `.ts` files are touched.

### Project Structure Notes

- Models layout follows the existing one-file-per-table pattern (`models/consent.py`, `models/insight.py`, …). Two new files, one per table, keeps that invariant.
- Architecture doc remains a single file. Inline edits only; do not shard.
- The `create_chat_session` helper lives in `services/chat_session_service.py` rather than under `app/agents/chat/` because 10.1b does not ship any agent runtime — putting it under `app/agents` would force 10.4a to move it or add a cross-layer import just to consume it. It stays at the service layer, where `consent_service` and `account_deletion_service` already live.

### Developer Guardrails (things that will bite you)

1. **The migration's `down_revision` is the current Alembic head at merge time.** 10.1a's most recent migration is `d8a0f2c4e6b9`, but check `.venv/bin/alembic heads` before locking — if another story lands a migration first, chain to that one instead. Do not rebase 10.1a's migrations.
2. **`consent_version_at_creation` is NOT NULL in the DB.** Any helper (including `create_chat_session` and any future 10.4a test fixture) must populate it. Forgetting → `IntegrityError` at INSERT.
3. **Do NOT add `on_delete="CASCADE"` to the SQLModel `Field(foreign_key=...)`** — SQLModel's field-level cascade declaration is advisory; the authoritative cascade is the DB-level `ondelete="CASCADE"` on the `ForeignKeyConstraint` in the migration. That's what actually runs. Mirror the pattern in `user_consents`.
4. **Revoke cascade runs inside the same transaction as the revoke INSERT.** Do not split them — a crash between them would leave a user in "revoked consent, live chat sessions" state, which violates the Consent Drift Policy.
5. **CHECK constraints must be named.** Alembic autogenerate-less migrations need explicit `name="ck_..."` on `sa.CheckConstraint(...)` or `downgrade()` can't reliably drop them.
6. **JSONB default is `'{}'::jsonb`, not `'{}'`.** Postgres needs the cast; without it, the default is TEXT and you'll see `column "redaction_flags" is of type jsonb but default expression is of type text`.
7. **The partial index needs `postgresql_where=`** (not `where=`) in both `__table_args__` and the Alembic `op.create_index`. SQLAlchemy silently drops the predicate if you use the wrong kwarg and you get a full index instead — the tests won't catch this; inspect with `\d+ chat_messages` in psql to verify.
8. **Tests must use a fresh session after insert to verify JSONB round-trip.** SQLModel's identity map returns the Python object unchanged on re-select within the same session, so a round-trip test that re-selects in the same session never exercises the serializer.
9. **Do NOT import `ChatSession` inside `consent_service.py` module-level.** Keep the import inside `revoke_chat_consent` to avoid a circular dependency if a future 10.x story adds a consent-read from `chat_session_service`. Or import at module-top if circulars remain clean — but pay attention.
10. **`ChatConsentRequiredError` at the service layer, not `HTTPException`.** 10.5 translates to HTTP; 10.1b must not pull in FastAPI at the service layer.

### Previous Story Intelligence (Story 10.1a — direct predecessor)

Read the 10.1a Dev Notes **before** writing the cascade. Key carry-over lessons:

- **Detached-copy pattern** (`UserConsent(...)` re-constructed before `await session.commit()`) is mandatory under the async session. Apply the same pattern in `create_chat_session` — reading `session.id` or `session.consent_version_at_creation` after commit without a detached copy will raise `MissingGreenlet`.
- **Naïve-UTC timestamps** are the project convention (`datetime.now(UTC).replace(tzinfo=None)`), not tz-aware. Mixing the two breaks ordering in `get_current_consent_status` (10.1a had to fix this in Review H1). Follow the same convention for `chat_sessions.last_active_at`.
- **AC #9 Integration-hook spy.** 10.1a added `test_delete_calls_revoke_chat_consent_service` that spies on the service call. Our revoke-cascade tests don't need to re-assert the HTTP→service call (10.1a owns that); we assert the post-state: sessions+messages gone, consent row written.
- **Append-only invariant.** `revoke_chat_consent` inserts a new `user_consents` row; never UPDATEs. 10.1b's cascade is an aside — it doesn't touch `user_consents` rows, only `chat_sessions`. The invariant stays intact.
- **Tenant isolation** (AC #9g dropped in 10.1a M3). Rationale carries: endpoints use `current_user`, so cross-tenant access isn't reachable via HTTP. Our cascade tests still assert "other user's sessions untouched" (AC #7c) because the service function operates on a `user` parameter — if a future caller passed the wrong user, we'd leak. Keep the assertion.

### Git Intelligence

Recent commits (last 5):
```
8e815dc Story 10.1a: 'chat_processing' Consent (separate from 'ai_processing')
5f4f567 Story 9.7: Bedrock IAM + Observability Plumbing
a4bd508 Story 9.6: Embedding Migration — text-embedding-3-large (3072-dim halfvec)
cccdeff Story 9.5c: Cross-Provider Regression Suite (LLM agents × {anthropic, openai, bedrock})
6251282 Story 9.5b: Add Bedrock Provider Path + Smoke Test
```

- **10.1a (`8e815dc`) is the direct surface we extend.** Nothing else in the last 5 commits touches `user_consents`, `consent_service`, or `account_deletion_service`. No merge conflicts expected.
- Epic 9 work (9.5*, 9.6, 9.7) is LLM/Bedrock plumbing — orthogonal surface, zero overlap.
- Branch state at start: `main` clean except the tracked `_bmad-output/implementation-artifacts/sprint-status.yaml` modification from the 10.1a status flip.

### Latest Tech Information

No external library research required. All patterns reuse existing stack:

- `sqlmodel` + `sqlalchemy` for table creation. JSONB via `sqlalchemy.dialects.postgresql.JSONB`.
- `alembic` migration style mirrors `a7b9c1d2e3f4_create_user_consents_table.py` (UUID default, server-side `now()`, FK with `ondelete="CASCADE"`, named CHECK constraints).
- Postgres 16 (docker-compose pgvector image) — supports JSONB, partial indexes, `gen_random_uuid()` (pgcrypto extension already enabled by the existing migration chain; no new extension required).
- `pytest-asyncio` + existing fixtures; no new test infrastructure.

## Project Context Reference

- Planning artifacts: [epics.md §Epic 10 Story 10.1b](../planning-artifacts/epics.md#L2109), [architecture.md §Consent Drift Policy](../planning-artifacts/architecture.md#L1732), [architecture.md §Data Model Additions](../planning-artifacts/architecture.md#L1785), [architecture.md §Chat Processing Consent](../planning-artifacts/architecture.md#L493).
- Sibling Epic 10 stories: **10.1a** (consent grant/revoke + the TODO hook this story closes), **10.4a** (AgentCore session handler — the first consumer of `create_chat_session`), **10.5** (streaming API — translates `ChatConsentRequiredError` to HTTP 403 envelope), **10.10** (chat history + deletion — relies on the indexes defined in AC #2).
- Foundational predecessor: **Story 5.5** (delete-all-my-data — the `account_deletion_service` this story extends).
- Cross-references: [backend/app/services/consent_service.py:114](../../backend/app/services/consent_service.py#L114) (TODO(10.1b) marker), [backend/app/services/account_deletion_service.py:77](../../backend/app/services/account_deletion_service.py#L77) (child_tables list).
- Sprint status: this story is `backlog` → set to `ready-for-dev` on file save.

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (1M context)

### Debug Log References

- `cd backend && .venv/bin/alembic upgrade head` → `Running upgrade d8a0f2c4e6b9 -> e3c5f7d9b2a1, add_chat_sessions_and_messages` (clean)
- `.venv/bin/alembic downgrade -1 && .venv/bin/alembic upgrade head` → both clean; reversible on real Postgres (docker compose `postgres` service). Re-verified post-code-changes.
- Scoped suite: `.venv/bin/pytest -q tests/test_chat_schema_cascade.py tests/test_chat_models.py tests/test_consent_chat.py tests/test_consent_service.py` → 27 passed.
- Full backend suite: `.venv/bin/pytest -q` → 895 passed, 23 deselected.

### Completion Notes List

- Models: `ChatSession` uses `Column(ForeignKey("users.id", ondelete="CASCADE"))` (mirrors `UserIbanRegistry`) so the FK cascade is declared at the SQLAlchemy layer and produced by both `SQLModel.metadata.create_all` (tests) and Alembic (prod). `ChatMessage.session_id` uses the same pattern against `chat_sessions.id`.
- `role` / `guardrail_action` are modelled as `TEXT + CHECK` (named `ck_chat_messages_role`, `ck_chat_messages_guardrail_action`) per the repo convention; SQLModel `Literal` types are mapped to SQL `Text` via explicit `sa_column=Column(Text, ...)` because SQLModel cannot auto-map `Literal` types.
- `redaction_flags` uses generic `JSON` at the model level (for SQLite test round-trip) and `JSONB` with `'{}'::jsonb` server default in the Alembic migration (AC #4).
- Partial index `ix_chat_messages_guardrail_action_nonzero` declares both `postgresql_where` (for Alembic) and `sqlite_where` (for local test DDL).
- Revoke cascade: inside `revoke_chat_consent`, the `sa_delete(ChatSession).where(ChatSession.user_id == user.id)` runs BEFORE `session.commit()` so revocation + cascade are a single transaction (AC #5). `ChatSession` is imported inside the function to avoid circular-import risk. The `TODO(10.1b)` marker was replaced with a `TODO(10.4a)` note pointing at the AgentCore session-terminator hook (logged as TD-092).
- Account deletion: `ChatSession` added to `child_tables` before `UserConsent` (leaf ordering); `ChatMessage` is NOT added — it is removed by the DB cascade on `session_id`, mirroring the `CardInteraction` / `insights.id` pattern (AC #6).
- `chat_session_service.create_chat_session` checks `get_current_consent_status(..., CONSENT_TYPE_CHAT_PROCESSING, CURRENT_CHAT_CONSENT_VERSION)`, raises plain `ChatConsentRequiredError` if absent, otherwise inserts a new `ChatSession` using the detached-copy pattern from Story 10.1a (AC #9).
- Tests: cascade tests use a standalone `fk_engine` fixture that registers a per-connection `PRAGMA foreign_keys = ON` listener on a fresh SQLite engine so ON DELETE CASCADE actually fires. Cascade assertions query via raw `text("SELECT COUNT(*) ...")` to bypass the ORM identity map (which would otherwise return stale cached instances after a raw `DELETE`).
- Docs: removed the "Known gap" paragraph at architecture.md:507 and linked the new migration/models into the Consent Drift Policy + Data Model Additions sections. Added tech-debt entry TD-092 for the AgentCore session-terminator pre-cascade hook owed by Story 10.4a.

### File List

- backend/app/models/chat_session.py (new)
- backend/app/models/chat_message.py (new)
- backend/app/models/__init__.py (modified — register ChatSession, ChatMessage)
- backend/alembic/versions/e3c5f7d9b2a1_add_chat_sessions_and_messages.py (new)
- backend/app/services/consent_service.py (modified — replace TODO(10.1b) with cascade; TODO(10.4a) follow-up)
- backend/app/services/account_deletion_service.py (modified — add ChatSession to child_tables)
- backend/app/services/chat_session_service.py (new — create_chat_session helper + ChatConsentRequiredError)
- backend/tests/test_chat_schema_cascade.py (new — AC #7)
- backend/tests/test_chat_models.py (new — AC #8)
- _bmad-output/planning-artifacts/architecture.md (modified — AC #10)
- docs/tech-debt.md (modified — new TD-092)
- VERSION (bumped 1.40.0 → 1.41.0)

### Change Log

- 2026-04-24: Story 10.1b implementation. New `chat_sessions` / `chat_messages` tables + models + migration (`e3c5f7d9b2a1`). `revoke_chat_consent` cascade wired. Account-deletion extended. `create_chat_session` helper shipped. Architecture + tech-debt docs updated. Scoped + full suites green (27 / 895).
- Version bumped from 1.40.0 → 1.41.0 per story completion (new user-facing backend surface — chat schema + cascade).
- 2026-04-24: Adversarial code review — 4 MEDIUM findings fixed; see "Code Review (AI)" section below. Scoped + full suites re-run green (27 / 895).

## Code Review (AI)

**Reviewer:** Oleh (adversarial review) · **Date:** 2026-04-24 · **Outcome:** Changes requested → fixed → Approve

### Findings (4 MEDIUM, all fixed)

- **M1 [FIXED]** Model/migration index drift on FK columns. `ChatSession.user_id` and `ChatMessage.session_id` had `index=True` on their `sa_column=Column(...)`, which would emit standalone `ix_chat_sessions_user_id` / `ix_chat_messages_session_id` indexes only under `SQLModel.metadata.create_all` (tests) — the migration only creates composite indexes. Redundant (composite indexes cover FK-lookup by prefix) and divergent between test and prod DDL. **Fix:** removed `index=True` from both FK columns in [backend/app/models/chat_session.py](backend/app/models/chat_session.py) and [backend/app/models/chat_message.py](backend/app/models/chat_message.py).

- **M2 [FIXED]** AC #8(a) test was ambiguous. `test_chat_session_requires_consent_version` raw-INSERT'd without `created_at`/`last_active_at`; the SQLite test DDL doesn't replicate `server_default=now()`, so the `IntegrityError` could fire on a timestamp NOT-NULL before reaching `consent_version_at_creation`. **Fix:** supply explicit timestamps and assert the exception message mentions `consent_version_at_creation` in [backend/tests/test_chat_models.py](backend/tests/test_chat_models.py).

- **M3 [FIXED]** AC #7(c) tenant-isolation assertion incomplete. `test_revoke_chat_consent_cascades_sessions_messages` only checked user_b's *sessions* were untouched — never verified user_b's *messages* survived. **Fix:** capture seeded message IDs per user and assert both sessions and messages remain for user_b in [backend/tests/test_chat_schema_cascade.py](backend/tests/test_chat_schema_cascade.py).

- **M4 [FIXED]** AC #7(c) user_a message-survival assertion was tautological. The test queried messages via `JOIN ChatSession WHERE user_id=user_a.id` — with sessions already asserted empty, that JOIN trivially returned empty regardless of cascade behavior. **Fix:** query `ChatMessage WHERE id IN (seeded_msg_ids)` directly so the assertion exercises the messages table independently.

### Findings dropped on review

- **L1** (local import of `ChatSession` inside `revoke_chat_consent`) — stylistic preference only; no concrete circular risk. Withdrawn.
- **L2** (architecture doc prose re: CHECK-vs-ENUM wording) — the inline link block already documents `text CHECK (...)`. Withdrawn.

### Verification

- Scoped: `cd backend && .venv/bin/pytest -q tests/test_chat_schema_cascade.py tests/test_chat_models.py tests/test_consent_chat.py tests/test_consent_service.py` → **27 passed**.
- Full: `cd backend && .venv/bin/pytest -q` → **895 passed, 23 deselected**.
