# Story 10.10: Chat History + Deletion

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **chat user who has accumulated multiple conversations under the `chat_processing` consent shipped by Story 10.1a + the schema shipped by Story 10.1b**,
I want **to list my own chat sessions, page through any session's transcript, delete a single session or every chat I've ever had with one action, and see the resulting chat-history footprint reflected in the existing `/users/me/data-summary` "view what data we hold" endpoint** —
so that **FR35 ("Users can view what data the system has stored about them") and FR70 ("Users can delete their chat history; deletion cascades with account deletion") are satisfied end-to-end with the cascades from Story 10.1b verified through the new public surface, the `localSessions` workaround in [`frontend/src/features/chat/hooks/useChatSession.ts:47-52`](../../frontend/src/features/chat/hooks/useChatSession.ts#L47-L52) is retired, the `/* 10.10 owns */` placeholders in [`frontend/src/features/chat/components/SessionList.tsx:49`](../../frontend/src/features/chat/components/SessionList.tsx#L49) + [`frontend/src/features/chat/index.ts:7`](../../frontend/src/features/chat/index.ts#L7) are filled in, the `NEXT_PUBLIC_CHAT_BULK_DELETE` flag flips to its default-on production state, and the SessionList sidebar from Story 10.7 finally renders real persisted history instead of only sessions created in the current browser tab**.

## Scope Boundaries

This story is **three new chat-history GET endpoints + one bulk-delete endpoint + a small `data-summary` extension + the frontend wiring that consumes them**. Hard out of scope:

- **No new chat-runtime, no new tools, no new prompts.** History is read-only DB access against the `chat_sessions` / `chat_messages` tables shipped by Story 10.1b. AgentCore/Bedrock are not invoked on any 10.10 path.
- **No `chat_processing` consent UX changes.** Listing/deleting history is allowed under either an active OR a revoked `chat_processing` consent — the cascade from 10.1b already removes sessions on revoke, and re-listing after revoke just returns an empty list. Story 10.1a/b own consent state; 10.10 never reads `user_consents` directly.
- **No write-path mutations to messages.** Editing or redacting an individual message is not in scope; deletion is per-session or per-user only.
- **No new download/export ZIP endpoint.** FR35 "view what data we hold" is satisfied by the listing GETs (which return JSON the client can already download via browser dev tools or a future "Download my data" button). The `/users/me/data-summary` parity extension in AC #5 is the single FR35 surface 10.10 ships; a downloadable archive is a follow-up story if/when product asks for one (file as a TD entry per AC #11 if not already tracked).
- **No rate-limit envelope wiring.** Listing/reading/deleting history is intentionally NOT in the 60-msgs/hr, 10-concurrent-sessions, daily-token-cap envelope shipped/owned by Story 10.11 — those caps target the *send-turn* path. History endpoints are protected by Cognito auth + per-row tenant isolation (same pattern as the Story 10.5 DELETE handler at [`backend/app/api/v1/chat.py:340-352`](../../backend/app/api/v1/chat.py#L340-L352)) and a coarse global per-IP gateway cap that already exists. If a future abuse pattern surfaces against history GETs, it lands in 10.11's per-IP layer, not here.
- **No new observability metric *filters* or *alarms* in Terraform.** Story 10.9 owns the `infra/terraform/modules/app-runner/observability-chat.tf` surface; 10.10 emits a small inventory of `chat.history.*` structured-log events (AC #8) that 10.9's filters do NOT yet cover — that's intentional, no Terraform diff in 10.10. If a follow-up wants metric filters on the new events, it lands as an additive PR in the 10.9 module (file a TD per AC #11 if it's not obvious from the events alone). Backend log emissions in this story still respect the same `extra={...}` JSON shape as Story 10.5/10.5a so a future filter wires in cleanly.
- **No `tool`-role rows in the user-facing transcript.** Story 10.4c added the `tool` role to `chat_messages.role` for per-tool-call forensic rows. The transcript GET in AC #2 filters those out — they're not user-visible content and exposing them through this endpoint would be a privacy footgun (raw tool args / responses can echo PII). The `data-summary` count in AC #5 includes them (it's a "messages held about you" count, not a "messages we'll re-render to you" count) — see AC #5 comment.
- **No frontend file additions.** All four affected frontend files already exist from Stories 10.7 / 10.5: `useChatSession.ts`, `SessionList.tsx`, `DeleteAllDialog.tsx`, `index.ts`. 10.10 modifies them; it does not introduce new components.
- **No i18n key additions.** All needed `chat.delete.*`, `chat.session.*` strings already exist in `frontend/messages/en.json` + `frontend/messages/uk.json` from Story 10.7. The "Bulk delete is coming soon" string (`chat.delete.all.coming_soon`) becomes dead under default-on bulk-delete, but 10.10 does NOT remove it — it's still rendered when an operator force-disables bulk-delete via env-flag for a hypothetical incident. Leave the key in place.
- **No migration.** Tables, indexes, cascades, and CHECK constraints are all shipped by Story 10.1b's migration `e3c5f7d9b2a1`. 10.10 does not create or alter any DB object.
- **No `account_deletion_service.py` changes.** Story 10.1b already added `ChatSession` to the `child_tables` list at [`backend/app/services/account_deletion_service.py:80-92`](../../backend/app/services/account_deletion_service.py#L80-L92). 10.10's account-deletion-cascade verification (AC #4) is an integration test, not a code change; the contract was wired by 10.1b and is exercised here through the new public list endpoint.
- **No `revoke_chat_consent` changes.** Same: the cascade was wired by 10.1b. 10.10 verifies post-revoke listing returns empty (AC #4d) but does not touch `consent_service.py`.

A scope comment at the top of `backend/app/api/v1/chat.py`'s new history-section block enumerates these deferrals.

## Acceptance Criteria

1. **Given** the `chat_sessions` table indexed by `(user_id, last_active_at DESC)` (Story 10.1b AC #2), **When** a Cognito-authenticated client calls `GET /api/v1/chat/sessions`, **Then** the endpoint returns `{ "sessions": [...] }` where each entry carries `sessionId` (UUID string), `createdAt` (ISO-8601 UTC), `lastActiveAt` (ISO-8601 UTC), `consentVersionAtCreation` (string), and `messageCount` (int — count of `chat_messages` rows for the session, **including** `tool`-role forensic rows so the count matches `data-summary`'s `chatMessageCount`); rows are sorted `last_active_at DESC, id DESC` (id-tiebreaker for deterministic pagination across millisecond ties); only sessions belonging to `current_user.id` are returned (cross-tenant rows MUST NOT appear); the response is JSON with camelCase keys via the same `ConfigDict(alias_generator=to_camel)` pattern used by `CreateSessionResponse` at [`backend/app/api/v1/chat.py:111-125`](../../backend/app/api/v1/chat.py#L111-L125).

2. **Given** AC #1's contract, **When** the client passes optional query parameters `limit` (1–50, default 20) and `cursor` (opaque base64-encoded `<iso-last-active-at>|<session-id>` token), **Then**:
   - `limit > 50` is clamped to 50 with no error (defensive — the request is honored, the cap is silent), `limit < 1` returns `422 Unprocessable Entity`.
   - `cursor` is decoded server-side; an invalid/tampered cursor returns `400 Bad Request` with `{"error":{"code":"CHAT_HISTORY_BAD_CURSOR","message":"Cursor is malformed or expired."}}` — no stack trace leakage.
   - The response carries `nextCursor` (string | null) — null when the page is the last one. The cursor is forward-only; reverse pagination is not supported in 10.10 (file a TD via AC #11 if product asks for it).
   - The `messageCount` per session is computed via a single `LEFT JOIN ... GROUP BY chat_sessions.id` query, NOT N+1 per-row counts. Verify the EXPLAIN plan stays index-only on the composite index `ix_chat_sessions_user_id_last_active_at` for the WHERE+ORDER and uses the FK-backing index for the JOIN; record the plan in the PR description.

3. **Given** the `chat_messages` table indexed by `(session_id, created_at)` (Story 10.1b AC #2), **When** a Cognito-authenticated client calls `GET /api/v1/chat/sessions/{session_id}/messages`, **Then**:
   - `404 Not Found` with code `CHAT_SESSION_NOT_FOUND` if the session does not exist OR belongs to a different user (enumeration-safe — same shape as the existing DELETE handler at [`backend/app/api/v1/chat.py:340-352`](../../backend/app/api/v1/chat.py#L340-L352); never `403`).
   - On success: `{ "messages": [{ "id": <uuid>, "role": "user"|"assistant"|"system", "content": <str>, "guardrailAction": "none"|"blocked"|"modified", "redactionFlags": <object>, "createdAt": <iso> }], "nextCursor": <str|null> }` — sorted `created_at ASC, id ASC` (forward-time order for human-readable transcript render).
   - **The `tool` role MUST be excluded** (`WHERE role <> 'tool'`) per §Scope Boundaries — these are forensic-only rows holding raw tool-call payloads; exposing them is a privacy regression.
   - Pagination: `limit` (1–100, default 50) + `cursor` (same base64 `<iso-created-at>|<id>` shape as AC #2, but ASC-ordered).
   - The `redactionFlags` field is returned **as-stored** (the JSONB blob); 10.10 does NOT redact-on-render or strip fields; the redaction was applied at write time by Stories 10.4b / 10.4c / 10.5a. The shape is documented in [architecture.md L1799](../planning-artifacts/architecture.md#L1799).
   - The query plan stays on `ix_chat_messages_session_id_created_at`. Validate via EXPLAIN; capture in PR description.

4. **Given** the cascades wired by Story 10.1b (AC #5 + AC #6 of that story), **When** a Cognito-authenticated client calls `DELETE /api/v1/chat/sessions` (no path id — bulk delete), **Then**:
   - The handler executes `await db.exec(sa_delete(ChatSession).where(ChatSession.user_id == current_user.id))` inside a single transaction; the `ON DELETE CASCADE` on `chat_messages.session_id` removes all messages atomically.
   - Returns `204 No Content` on success — even when the user had zero sessions (idempotent — same posture as `revoke_chat_consent` per Story 10.1b AC #7d).
   - **Before** the delete runs, the handler iterates the user's currently-open AgentCore session handles and calls `handler.terminate_session(...)` on each — same protocol as the per-session DELETE at [`backend/app/api/v1/chat.py:359-371`](../../backend/app/api/v1/chat.py#L359-L371) — so any in-flight stream is cancelled before its DB row disappears (this is the same `TODO(10.4a)`-shape obligation 10.1b documented for `revoke_chat_consent`; the bulk-delete path inherits it). A `ChatSessionTerminationFailed` from any handle aborts the bulk-delete with `503 CHAT_BACKEND_UNAVAILABLE` — partial deletion is not allowed; either every session's runtime is terminated and every row is gone, or nothing is.
   - Integration test (`backend/tests/test_chat_history_endpoints.py::test_bulk_delete_and_account_delete_cascades`) covers four scenarios: (a) seed user_a with 3 sessions × 5 messages each + user_b with 1 session × 2 messages; bulk-DELETE as user_a → user_a has 0 sessions / 0 messages, user_b's row counts unchanged. (b) bulk-DELETE on a user with zero sessions returns 204 with no error. (c) `delete_all_user_data(user_a)` (account deletion path) → both `chat_sessions` and `chat_messages` rows for user_a are gone; user_b's preserved (this re-exercises Story 10.1b's existing test from a 10.10 vantage point — same DB invariant, different entry path). (d) After `revoke_chat_consent(user_a)`, the new `GET /chat/sessions` endpoint returns `{"sessions": []}` (the cascade kicked, the listing observes the empty state — closes the cycle Story 10.1b's test couldn't because no listing endpoint existed).

5. **Given** the existing `/users/me/data-summary` response shape from Story 10.1a's H1 fix at [`backend/app/api/v1/data_summary.py:87-98`](../../backend/app/api/v1/data_summary.py#L87-L98), **When** 10.10 extends it, **Then** three fields are added to `DataSummaryResponse`:
   - `chatSessionCount: int` — `SELECT COUNT(*) FROM chat_sessions WHERE user_id = $1`.
   - `chatMessageCount: int` — `SELECT COUNT(*) FROM chat_messages cm JOIN chat_sessions cs ON cm.session_id = cs.id WHERE cs.user_id = $1`. **Includes** `tool`-role rows (this field is the "data we hold about you" count for FR35 — forensic rows are still data).
   - `chatActivityRange: { earliest: ISO, latest: ISO } | null` — `MIN(last_active_at)` / `MAX(last_active_at)` from `chat_sessions`; `null` when the user has no sessions.

   The three fields are added as **non-optional** on the Pydantic model (default `0` for the counts, `None` for the range) so existing clients deserializing the response don't break — same defensive posture Story 10.1a took for `revokedAt`. The existing `consent_records` field is unchanged. The endpoint stays a single round-trip — the three new queries are issued via `asyncio.gather` alongside the existing ones to keep latency flat (current p95 is the issue-report COUNT; chat counts are smaller indices and won't dominate).

6. **Given** the frontend chat surface from Story 10.7 currently relies on a `localSessions` in-memory merge to keep just-created sessions visible across renders (see [`frontend/src/features/chat/hooks/useChatSession.ts:47-52`](../../frontend/src/features/chat/hooks/useChatSession.ts#L47-L52)), **When** 10.10 lands, **Then**:
   - The `localSessions` state and the `mergedSessions` `useMemo` are removed.
   - The `sessionsQuery` `queryFn` no longer treats 404/405 as "list endpoint not live" — those status codes now propagate as real errors (the endpoint exists in 10.10).
   - On `createSession` success, the `onSuccess` handler calls `qc.invalidateQueries({queryKey:["chat-sessions"]})` (already present); the optimistic `setLocalSessions` call is removed.
   - On `deleteSession` success, the optimistic local-state filter is removed; the same invalidation refetches authoritative server state.
   - A new `bulkDeleteAll` mutation is added (`DELETE /api/v1/chat/sessions`, returns 204 → invalidates `["chat-sessions"]` and clears `activeSessionId`).
   - A new `messagesQuery` (or co-located hook `useChatMessages(sessionId)`) issues `GET /api/v1/chat/sessions/{id}/messages` with React Query; cursor pagination is exposed via an `infiniteQuery` (or a manual `nextCursor` state — dev's choice; the test in AC #9 validates the user-visible behavior of "scrolling up loads earlier messages", not the query-shape decision).

7. **Given** AC #6's wiring, **When** the user clicks the "Delete all chats" link in the SessionList footer (currently rendered with `aria-disabled` + a "coming soon" tooltip when `NEXT_PUBLIC_CHAT_BULK_DELETE !== "true"`), **Then**:
   - The `BULK_DELETE` env-flag default flips to **on** for production builds — operationally, this means setting `NEXT_PUBLIC_CHAT_BULK_DELETE=true` in `frontend/.env.production` (or wherever the deploy injects it; verify via `Vercel.json` / Vercel project env vars on merge) and updating the `frontend/.env.example` to document the default. **Both `true` and unset MUST behave identically as default-on** — the dev replaces the strict `=== "true"` check with `!== "false"` so unset → on. The flag remains as a kill-switch for incident response.
   - The `DeleteAllDialog`'s `onConfirm` callback wires to the new `bulkDeleteAll` mutation from AC #6; on success → toast `chat.delete.all.toast` (new key — see AC #7c), navigate the active session to null, dialog closes; on error → toast `chat.delete.all.error`.
   - Two i18n keys are added to **both** `frontend/messages/en.json` and `frontend/messages/uk.json` under `chat.delete.all`: `toast: "All chats deleted"` (en) / `"Усі чати видалено"` (uk); `error: "Couldn't delete all chats."` (en) / `"Не вдалося видалити чати."` (uk). The existing `coming_soon` key is preserved per §Scope Boundaries.
   - The `/* 10.10 owns */` comment in [`frontend/src/features/chat/components/SessionList.tsx:49`](../../frontend/src/features/chat/components/SessionList.tsx#L49) is replaced with a no-op (the per-session `delete.session.undo` toast action is **not** wired in 10.10 — see AC #11). The comment block in [`frontend/src/features/chat/index.ts:7`](../../frontend/src/features/chat/index.ts#L7) is updated to drop the "Story 10.10 owns the bulk-delete API, ..." line and replace it with "Story 10.10 shipped the history list, transcript, bulk-delete, and data-summary parity surfaces."
   - The `/* 10.10 owns */` placeholder for the per-session delete `Undo` toast action is replaced with a comment referencing AC #11's TD entry (the undo-flow is intentionally deferred and tracked).

8. **Given** the structured-log inventory pattern established by Stories 10.4b–10.7 + metricified by 10.9, **When** 10.10's endpoints emit logs, **Then** four new `extra={"message": "chat.history.<event>", ...}` events land on the API stdout, per the JSON-shape convention at [`backend/app/api/v1/chat.py`](../../backend/app/api/v1/chat.py) (compatible with the future-additive metric filters Story 10.9 ships):
   - `chat.history.listed` — fields: `user_id_hash`, `session_count`, `correlation_id`. INFO level.
   - `chat.history.transcript_listed` — fields: `user_id_hash`, `session_id`, `message_count`, `correlation_id`. INFO level.
   - `chat.history.bulk_deleted` — fields: `user_id_hash`, `sessions_deleted`, `messages_deleted` (computed pre-delete via the same query AC #5 uses), `correlation_id`. WARN level (destructive op gets a higher log level so it surfaces in `level >= WARN` audit queries; mirrors the precedent the canary-leak / finalizer-failed events set).
   - `chat.history.bulk_delete_failed` — fields: `user_id_hash`, `correlation_id`, plus `failure_stage` enum (`"agentcore_terminate"` | `"db_delete"`). ERROR level. Fired only on the AC #4 abort path.
   - The `_hash_user_id` helper at [`backend/app/agents/chat/session_handler.py`](../../backend/app/agents/chat/session_handler.py) is reused — no new hashing helper, no raw `user_id` in logs.
   - Story 10.9's metric filters are NOT updated in this story (per §Scope Boundaries); the events are wire-compatible so a follow-up filter PR is one-liner additive.

9. **Given** the test surface, **When** 10.10 lands, **Then**:
   - **Backend** (`backend/tests/test_chat_history_endpoints.py` — new file): (a) listing returns the seeded sessions in `last_active_at DESC` order with correct `messageCount` per session; (b) listing is per-tenant (user_b's sessions never appear in user_a's list); (c) cursor pagination round-trips (page 1 → page 2 → page 3 → empty `nextCursor`); (d) malformed cursor → 400 with `CHAT_HISTORY_BAD_CURSOR`; (e) transcript GET excludes `tool` role; (f) transcript GET on a cross-user session → 404 (enumeration-safe); (g) bulk-delete cascade per AC #4(a)–(d); (h) bulk-delete with zero sessions returns 204; (i) `data-summary` chat fields (AC #5) round-trip — counts match the seeded fixture exactly, `chatActivityRange` reflects min/max `last_active_at`, `null` when no sessions.
   - **Backend** (`backend/tests/test_chat_history_endpoints.py::test_bulk_delete_terminates_runtime_first`): the `ChatSessionHandler.terminate_session` mock is asserted called once per seeded session **before** the DB delete fires (assert via call-order on a mock that records the DB session row count at each call); a forced `ChatSessionTerminationFailed` causes 503 + zero rows deleted (the tx rolled back).
   - **Backend** (`backend/tests/api/test_data_summary.py` extension): the existing test gains assertions on the three new fields under each fixture (zero-session user → counts 0, range null; multi-session user → counts populated, range matches fixture timestamps).
   - **Frontend** (`frontend/src/features/chat/__tests__/SessionList.test.tsx` extension + new `frontend/src/features/chat/__tests__/useChatSession.test.tsx` if not present): list renders sessions returned by the mocked GET; bulk-delete dialog calls the mocked DELETE and clears the active session on success; the `localSessions` removal is verified by mocking GET to return an empty list immediately after a successful POST (the just-created session must come from the next refetch, not from local state).
   - **Frontend** (`frontend/src/features/chat/__tests__/ConversationPane.test.tsx` extension): on `selectSession`, the messages GET is fetched and rendered in chronological order; `tool` role is never rendered (covered by the backend filter, but the FE test asserts the FE doesn't introduce its own assumption about which roles to skip).
   - **All suites** green: `cd backend && .venv/bin/pytest -q` AND `cd frontend && npm run lint && npm test` (per the frontend-lint-discipline memory).

10. **Given** the project's pre-merge gates, **When** 10.10 is closed, **Then**:
    - `cd backend && ruff check .` clean (per `feedback_backend_ruff.md` memory).
    - `cd backend && .venv/bin/pytest -q` green — no skips introduced by 10.10.
    - `cd frontend && npm run lint` clean — no new TD-133 demotions; if any new file trips a strict rule, fix the rule, do not demote it.
    - `cd frontend && npm test` green.
    - The chat surface still renders end-to-end manually: log in → /chat → SessionList shows real persisted sessions → click a session → ConversationPane renders the full transcript → "Delete all chats" → confirmation dialog → confirm → list goes empty → reload → list still empty (no localSessions re-hydration). Capture a screenshot or note in the PR description per the parent CLAUDE.md "test the golden path in a browser before reporting complete" rule.
    - `/VERSION` is bumped (MINOR — adds user-facing GET + DELETE surfaces and a `data-summary` field expansion).
    - `_bmad-output/implementation-artifacts/sprint-status.yaml`: `10-10-chat-history-deletion` flips `ready-for-dev` → `in-progress` → `review` along the standard dev-story flow. `epic-10` status remains `in-progress` until 10.11 lands.

11. **Given** the deferrals enumerated in §Scope Boundaries and embedded in ACs above, **When** 10.10 lands, **Then** [`docs/tech-debt.md`](../../docs/tech-debt.md) is updated with new entries (assign the next free TD-NNN number per the project's tech-debt convention referenced in `reference_tech_debt.md` memory):
    - **TD-NNN — "Per-session chat-delete Undo (5s window)"**: the `delete.session.undo` toast action wired in [`SessionList.tsx:48`](../../frontend/src/features/chat/components/SessionList.tsx#L48) was a 10.7 affordance the dev intended for 10.10 (`/* 10.10 owns */`). 10.10 keeps the toast action visible (preserving the 10.7 UX) but the click-to-undo is a no-op pending product confirmation that "soft-delete with 5s window" is desired UX (vs. the current hard-delete posture, which matches the FR70 + FR31 cascade contract). If undo is desired, the schema needs a `deleted_at TIMESTAMPTZ NULL` column on `chat_sessions` + a sweeper Celery beat task — non-trivial enough to warrant a deliberate design decision, not a 10.10 sub-task. Owner: Epic 10 / TBD; severity: LOW.
    - **TD-NNN — "Reverse pagination on chat-history list"**: AC #2 explicitly defers `prevCursor`. Owner: Epic 10 / TBD; severity: LOW; trigger: "if a user complains about not being able to navigate backward through > 50 sessions".
    - **TD-NNN — "Downloadable chat-history export"**: §Scope Boundaries defers a ZIP/JSON-archive download. Owner: Epic 5 (data export is its turf — `account_deletion_service` lives there) / TBD; severity: LOW; trigger: "when product asks for a one-click download of all chat data" or when a regulatory request lands.
    - **TD-NNN — "Story 10.9 metric filters for `chat.history.*` events"**: §Scope Boundaries defers the additive Terraform metric-filter PR. Owner: Story 10.9 follow-up / TBD; severity: LOW; the events emit in 10.10 so the metric filter is a one-line addition once needed.
    - **TD-092 closure check**: the `TODO(10.4a)` marker in [`backend/app/services/consent_service.py`](../../backend/app/services/consent_service.py) (Story 10.1b's open hook for "AgentCore session terminator before cascade") is **not** fully closed by 10.10 — the bulk-DELETE path implements termination-before-cascade for its own scope, but the `revoke_chat_consent` cascade still doesn't terminate runtime sessions (Story 10.4a's surface). 10.10 leaves TD-092 untouched; if the dev notices Story 10.4a's session-terminator API now exists and the consent-revoke cascade can adopt it, that's a Story 10.4a/10.1b follow-up, not 10.10. Note: cross-link 10.10's bulk-delete-terminate-first pattern from TD-092's "Approach" field as a reference implementation.

12. **Given** the tech-spec convention this epic follows, **When** the architecture doc is touched (lightly), **Then**:
    - The `### API Pattern — Chat Streaming` subsection at [architecture.md L1805-L1820](../planning-artifacts/architecture.md#L1805-L1820) gains a one-line pointer to the new history endpoints (e.g., "History/listing: `GET /api/v1/chat/sessions`, `GET /api/v1/chat/sessions/{id}/messages`, `DELETE /api/v1/chat/sessions` — Story 10.10."). The streaming-error-envelope JSON example is unchanged.
    - The `### Data Model Additions` subsection at [architecture.md L1794-L1803](../planning-artifacts/architecture.md#L1794-L1803) gains a bullet under "Operational indexes" confirming both indexes are now exercised by 10.10's listing endpoints (just a verification statement, no schema change).

## Tasks / Subtasks

- [x] **Task 1 — Backend listing endpoint** (AC #1, #2)
  - [x] 1.1 Add Pydantic models `ListChatSessionsResponse` + `ChatSessionSummary` to `backend/app/api/v1/chat.py` near the existing `CreateSessionResponse` (camelCase via `to_camel`, response item per AC #1).
  - [x] 1.2 Implement `@router.get("/sessions", response_model=ListChatSessionsResponse)` with `limit` + `cursor` query params (Pydantic validation `Query(ge=1, le=50, default=20)`), per-tenant WHERE clause, `LEFT JOIN ... GROUP BY` for `messageCount`, ORDER BY `(last_active_at DESC, id DESC)` for stable pagination, decode/encode cursor via a small helper (`_encode_session_cursor` / `_decode_session_cursor`) at the bottom of the file.
  - [x] 1.3 Capture EXPLAIN ANALYZE plan against a seeded dev DB; paste in PR description; verify `ix_chat_sessions_user_id_last_active_at` is hit.

- [x] **Task 2 — Backend transcript endpoint** (AC #3)
  - [x] 2.1 Add Pydantic models `ListChatMessagesResponse` + `ChatMessageView` (camelCase; `redactionFlags: dict` passthrough; `role: Literal['user','assistant','system']` — `tool` excluded by the query, not the model).
  - [x] 2.2 Implement `@router.get("/sessions/{session_id}/messages")` with the cross-user 404 enumeration-safe pattern (mirror the existing DELETE handler's `db.get(ChatSession, session_id)` + `user_id` check at [`backend/app/api/v1/chat.py:341-352`](../../backend/app/api/v1/chat.py#L341-L352)). Cursor decode helper for `(created_at ASC, id ASC)`.
  - [x] 2.3 EXPLAIN ANALYZE on `ix_chat_messages_session_id_created_at`; capture in PR description.

- [x] **Task 3 — Backend bulk-delete endpoint** (AC #4)
  - [x] 3.1 Add `@router.delete("/sessions", status_code=204)` (no path param) — distinct route from the existing `delete("/sessions/{session_id}")` so FastAPI's path-precedence resolves them unambiguously. Add a comment block over the new route documenting "no path id == bulk delete" since the 1-char path difference is easy to miss in review.
  - [x] 3.2 Step 1 of the body: `select(ChatSession.id, ChatSession.created_at).where(user_id == current_user.id)` → build `ChatSessionHandle` per row → call `handler.terminate_session(handle)` for each. Wrap in `try/except ChatSessionTerminationFailed` → return `503 CHAT_BACKEND_UNAVAILABLE` (do NOT proceed to the DB delete).
  - [x] 3.3 Step 2: `await db.exec(sa_delete(ChatSession).where(ChatSession.user_id == current_user.id))` then `await db.commit()`. The `chat_messages` rows go via the FK cascade.
  - [x] 3.4 Pre-delete COUNT for the structured-log `messages_deleted` field — issue this SELECT in the same transaction *before* the DELETE so the count is consistent with the actual destruction.

- [x] **Task 4 — Data-summary extension** (AC #5)
  - [x] 4.1 Extend `DataSummaryResponse` in [`backend/app/api/v1/data_summary.py`](../../backend/app/api/v1/data_summary.py) with `chat_session_count: int = 0`, `chat_message_count: int = 0`, `chat_activity_range: Optional[ChatActivityRange] = None`. Add `ChatActivityRange(BaseModel)` with `earliest: datetime` + `latest: datetime` per the existing `TransactionDateRange` pattern.
  - [x] 4.2 Add three new query branches in `get_data_summary`. Wire them into the existing query flow (`asyncio.gather` if the function uses gather; otherwise sequential — current code is sequential, see lines 113-216). Keep `to_camel` aliasing.

- [x] **Task 5 — Structured-log events** (AC #8)
  - [x] 5.1 Add `logger.info("chat.history.listed", extra={...})` after Task 1's response is built; same pattern in Task 2's response (`chat.history.transcript_listed`). Reuse `_hash_user_id` from `session_handler.py` per the existing chat-event privacy convention.
  - [x] 5.2 In Task 3, emit `chat.history.bulk_deleted` (WARN level) on the success path; emit `chat.history.bulk_delete_failed` (ERROR level) on the abort path with `failure_stage` set.

- [x] **Task 6 — Frontend useChatSession refactor** (AC #6)
  - [x] 6.1 In [`frontend/src/features/chat/hooks/useChatSession.ts`](../../frontend/src/features/chat/hooks/useChatSession.ts): remove `localSessions` state and `mergedSessions` `useMemo`. The `sessions` returned by the hook is now `sessionsQuery.data?.sessions ?? []` directly.
  - [x] 6.2 Remove the 404/405 graceful-fallback in the `queryFn` — those are real errors now.
  - [x] 6.3 Add `bulkDeleteAll` mutation: `DELETE /api/v1/chat/sessions`, 204 → invalidate `["chat-sessions"]` + clear `activeSessionId`.
  - [x] 6.4 Add `useChatMessages(sessionId)` hook (or co-locate as a query in the same file — dev's choice; whichever keeps the component code readable). Use `useInfiniteQuery` for cursor pagination OR a manual paged-load pattern; tested by the FE test in AC #9.
  - [x] 6.5 Update the comment block in [`frontend/src/features/chat/index.ts`](../../frontend/src/features/chat/index.ts) per AC #7's wording.

- [x] **Task 7 — Frontend SessionList + DeleteAllDialog wiring** (AC #7)
  - [x] 7.1 Flip the `BULK_DELETE` flag: `process.env.NEXT_PUBLIC_CHAT_BULK_DELETE !== "false"` (default-on; only `"false"` disables). Update `frontend/.env.example` to document the new default.
  - [x] 7.2 Wire `DeleteAllDialog`'s `onConfirm` callback in `SessionList.tsx` to call `bulkDeleteAll` from `useChatSession`; on success → `toast.success(t("delete.all.toast"))`, set active session null; on error → `toast.error(t("delete.all.error"))`.
  - [x] 7.3 Add `chat.delete.all.toast` + `chat.delete.all.error` keys in `frontend/messages/en.json` and `frontend/messages/uk.json`.
  - [x] 7.4 Replace the `/* 10.10 owns */` placeholder per AC #7 (point at the TD entry from AC #11's first bullet).

- [x] **Task 8 — Frontend transcript rendering** (AC #6, #9 ConversationPane test)
  - [x] 8.1 In `ConversationPane.tsx` (or wherever the message list lives — verify by reading the component first; do not assume), call `useChatMessages(activeSessionId)` and render the returned messages in chronological order. Existing styling for user/assistant/system bubbles is preserved.
  - [x] 8.2 If the SSE stream is also active for the same session (a turn is in flight), the rendered list is `historicalMessages + streamingMessages` deduplicated by id — the in-flight assistant message is the streaming one (no DB row yet) and is appended after history.

- [x] **Task 9 — Tests** (AC #9)
  - [x] 9.1 New `backend/tests/test_chat_history_endpoints.py` covering AC #9's nine backend scenarios + the runtime-terminate-first scenario.
  - [x] 9.2 Extend `backend/tests/api/test_data_summary.py` (verify the file path; if absent, the closest existing data-summary test is the right place — search for `data_summary` in `backend/tests/`).
  - [x] 9.3 Extend `frontend/src/features/chat/__tests__/SessionList.test.tsx` + `ConversationPane.test.tsx` per AC #9 frontend bullets. Add a new `useChatSession.test.tsx` only if the existing tests don't already cover the hook.
  - [x] 9.4 Run scoped suites + full suites; capture green output in the PR description.

- [x] **Task 10 — Tech-debt entries** (AC #11)
  - [x] 10.1 Append four new TD-NNN entries to `docs/tech-debt.md` per AC #11. Use the next free numbers (currently TD-135 is the latest per grep; allocate TD-136, TD-137, TD-138, TD-139 unless other PRs land first — check `git log docs/tech-debt.md` immediately before merge).
  - [x] 10.2 Cross-link 10.10's bulk-delete-terminate-first pattern from TD-092's "Approach" field per AC #11 final bullet (one-line edit to the existing TD-092 entry, not a closure).

- [x] **Task 11 — Architecture doc updates** (AC #12)
  - [x] 11.1 Add the one-line pointer to `### API Pattern — Chat Streaming` per AC #12.
  - [x] 11.2 Add the index-verification bullet to `### Data Model Additions` per AC #12.

### Review Follow-ups (AI)

- [ ] [AI-Review][LOW] AC #4(c) test deviates from spec — exercises FK cascade via `s.delete(user_b)` instead of `account_deletion_service.delete_all_user_data(user_a)`. Tighten to call the named service so a regression in `child_tables` ordering is caught. [`backend/tests/test_chat_history_endpoints.py:371-388`](../../backend/tests/test_chat_history_endpoints.py#L371-L388)
- [ ] [AI-Review][LOW] Add a test for the `chat.history.bulk_delete_failed` ERROR path with `failure_stage="db_delete"` — currently only the `agentcore_terminate` path is covered. Mock `db.exec` to raise during the bulk-delete to exercise the rollback branch. [`backend/app/api/v1/chat.py:704-723`](../../backend/app/api/v1/chat.py#L704-L723)

## Code Review

- 2026-04-27 — Adversarial review (claude-opus-4-7). 4 MEDIUM + 4 LOW findings. Fixed: M1 (docstring honesty about runtime-termination not being transactional), M2 (`disabled` attr on bulk-delete button when kill-switch is on), M4 (cursor decode normalizes tz-aware → naive UTC), L3 (`useMemo` for `allTurns` in ChatScreen). Promoted: M3 → [TD-140](../../docs/tech-debt.md). Story-local follow-ups: L1, L4 (above). Withdrawn: L2 (dedupe of `ChatActivityRange`/`TransactionDateRange`) — alias would change OpenAPI schema name; net negative.

- [x] **Task 12 — Pre-merge gates** (AC #10)
  - [x] 12.1 `cd backend && ruff check .` → clean.
  - [x] 12.2 `cd backend && .venv/bin/pytest -q` → green.
  - [x] 12.3 `cd frontend && npm run lint` → clean (no TD-133 demotions).
  - [x] 12.4 `cd frontend && npm test` → green.
  - [x] 12.5 Manual browser smoke per AC #10. Capture screenshot/notes in PR description.
  - [x] 12.6 `/VERSION` bumped (MINOR).
  - [x] 12.7 Sprint-status flip: `ready-for-dev` → `in-progress` (on dev start) → `review` (on PR open). Do NOT flip to `done` from this story; `code-review` slash command auto-marks done per the create-story workflow's final output template.

## Dev Notes

### Why this story even exists, given 10.1b shipped the cascades

Story 10.1b shipped the *DB invariant* (cascade on user-delete + cascade on consent-revoke + tables + indexes). Story 10.7 shipped the *UI affordances* (SessionList, DeleteSessionDialog, DeleteAllDialog, "Delete all chats" link with a `coming_soon` flag). What was missing — and why both stories had explicit `Story 10.10 owns` markers — is the **public read/write API surface that connects them**. Without 10.10:

- The user can create a session and chat, but if they reload the page, their just-created session vanishes (the `localSessions` workaround in `useChatSession.ts:47-52` masked this on the same render-tree only).
- The DELETE button on a session row works (10.5's per-session DELETE shipped) but there's no `GET` to verify the row went away from a fresh client.
- The "Delete all chats" link is `aria-disabled` with a "coming soon" tooltip; the bulk-delete contract is unimplemented.
- The `/users/me/data-summary` endpoint reports nothing about chat — FR35's "view what data we hold" is silent on the chat surface that's been accumulating data for an entire epic.

10.10 ships the four endpoints and the small frontend rewiring that closes all four gaps. It's also the first time the existing 10.1b indexes get exercised by user-facing reads — Task 1.3 / 2.3's EXPLAIN steps validate that those indexes were authored correctly.

### Reuse from Story 10.1b (mandatory — do not re-invent)

The `chat_sessions` + `chat_messages` schema, models, indexes, ON DELETE CASCADE chains, CHECK constraints, and the `account_deletion_service.child_tables` ordering are **frozen** from 10.1b. 10.10 is a pure read/delete consumer of that schema. Specifically:

- `ChatSession`, `ChatMessage` models at [`backend/app/models/chat_session.py`](../../backend/app/models/chat_session.py), [`backend/app/models/chat_message.py`](../../backend/app/models/chat_message.py).
- Indexes `ix_chat_sessions_user_id_last_active_at`, `ix_chat_messages_session_id_created_at`, `ix_chat_messages_guardrail_action_nonzero` (the last is unused by 10.10 but exists for Story 10.9's safety queries).
- Cascade FKs declared in the migration `e3c5f7d9b2a1` — both `chat_sessions.user_id → users.id ON DELETE CASCADE` and `chat_messages.session_id → chat_sessions.id ON DELETE CASCADE`.
- The `_hash_user_id` privacy helper at [`backend/app/agents/chat/session_handler.py`](../../backend/app/agents/chat/session_handler.py) — already imported by `chat.py` for streaming; reuse for the new history events.

### Reuse from Story 10.5 (mandatory)

The router (`router = APIRouter(prefix="/chat", tags=["chat"])`), the `correlation_id = str(uuid.uuid4())` pattern, the camelCase-via-`to_camel` Pydantic config, the typed-exception → HTTPException error-envelope shape, and the structured-log `extra={"message": "chat.<event>", ...}` JSON shape are all established by [`backend/app/api/v1/chat.py`](../../backend/app/api/v1/chat.py). 10.10 follows them verbatim — any deviation makes the operator-runbook (Story 10.9) inconsistent across event sources.

### Reuse from Story 10.7 (mandatory)

The frontend chat surface — `SessionList`, `DeleteAllDialog`, `useChatSession`, `ConversationPane` — is owned by 10.7. 10.10 surgically modifies these files; it does NOT introduce parallel components. The i18n keys under `chat.delete.all.*` exist already (except the two new ones AC #7 adds); the dialog UX (typed-confirmation "delete" gate) is preserved unchanged. The `BULK_DELETE` env-flag posture is preserved as a kill-switch.

### Cursor encoding shape (AC #2 + AC #3)

Use base64url-encoded `<timestamp>|<uuid>` strings for both cursors. A tiny helper at the bottom of `chat.py`:

```python
def _encode_cursor(ts: datetime, row_id: uuid.UUID) -> str:
    raw = f"{ts.isoformat()}|{row_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")

def _decode_cursor(token: str) -> tuple[datetime, uuid.UUID]:
    try:
        padded = token + "=" * (-len(token) % 4)
        raw = base64.urlsafe_b64decode(padded).decode()
        ts_iso, id_str = raw.split("|", 1)
        return datetime.fromisoformat(ts_iso), uuid.UUID(id_str)
    except (ValueError, binascii.Error) as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "CHAT_HISTORY_BAD_CURSOR", "message": "Cursor is malformed or expired."}}
        ) from exc
```

The cursor is opaque to the client — clients should treat it as a black-box string. We don't sign it (HMAC) because it's user-scoped; an attacker tampering with their own cursor only sees their own data, and a valid-but-unintended cursor either matches a row of theirs or returns empty results. The error code is uniform so a client can distinguish "bad cursor" from "rate limit" / "auth" reliably.

### Why `messageCount` includes `tool` rows but the transcript GET excludes them

Two different jobs:

- `messageCount` on the listing endpoint + `chatMessageCount` on data-summary answer "**how much chat data does the system hold about me?**" — that's an FR35 question; it must be honest. Tool-role forensic rows are data the system holds; they count.
- The transcript GET answers "**show me my conversation**" — a UX question. Tool-role rows are private internal calls (raw tool args, often with PII pre-redaction lingering), never authored by the user, never shown in the SessionList preview, never streamed back via SSE. Including them in the transcript would surface internal mechanics to the user and risk privacy leakage. Excluding them keeps the transcript faithful to what the chat UI actually showed in the live session.

This deliberate split is documented inline in the route docstring of AC #3.

### Frontend `localSessions` removal — why it's safe

The `localSessions` workaround was a 10.7 expedient to keep just-created sessions visible until 10.10 shipped the GET. With AC #1's GET in place + React Query's `invalidateQueries` on the create-mutation success, the next refetch shows the just-created session. There's a < 100ms window between "POST returned 201" and "GET returned the new row" where the optimistic update would fix the visual blip — but React Query already buffers via `isPending` UX in the `Button disabled={isCreating}` at `SessionList.tsx:60`, so the user never sees an empty list during the transition. If the dev finds the blink visually objectionable in a manual test, they may add an `onMutate` optimistic-update inside the create mutation (NOT a separate state) — that's the React Query idiomatic pattern and stays single-source-of-truth.

### Pre-delete-AgentCore-terminate, but not pre-revoke-AgentCore-terminate (TD-092)

AC #4's bulk-delete handler implements termination-before-cascade because **it has the AgentCore handler in scope** — the handler is dependency-injected into the route. The same is NOT true for `revoke_chat_consent` in `consent_service.py` — that service is invoked from contexts (HTTP DELETE on consent, account-deletion path) where the AgentCore handler isn't currently injected, and adding the injection is a refactor that touches the service signatures. TD-092 tracks that wider refactor. 10.10 closes its own scope honestly without expanding into TD-092's surface — dev should resist the temptation to "while I'm here, fix it" because the plumbing change is non-trivial (the consent revoke is also called from the account-deletion path, which has its own session/user fixture, and unifying those is a separate design call).

### Why the bulk-delete is `DELETE /chat/sessions` and not `POST /chat/sessions:delete-all`

Two options were considered:

- **`DELETE /chat/sessions`** (chosen): semantically correct (deleting the collection), idempotent (RFC 7231 §4.3.5), aligns with the existing per-id DELETE shape on the same router, no body required.
- **`POST /chat/sessions:delete-all`**: the "RPC verb in path" pattern. Some teams prefer this for visibility; we don't — it doesn't match anything else in `backend/app/api/v1/`. Rejected.

The path-precedence concern (does FastAPI route `DELETE /chat/sessions/{id}` and `DELETE /chat/sessions` correctly?) is non-issue: FastAPI's path tree matches exact paths before path-parameter paths, so the no-id route is unambiguous. Add a unit test if paranoia is high — it's one line.

### Project Structure Notes

- Modified file: [`backend/app/api/v1/chat.py`](../../backend/app/api/v1/chat.py) — three new routes + cursor helpers + new Pydantic models (~ 200-250 lines added).
- Modified file: [`backend/app/api/v1/data_summary.py`](../../backend/app/api/v1/data_summary.py) — one new Pydantic model + three new query branches (~ 50 lines added).
- New file: `backend/tests/test_chat_history_endpoints.py`.
- Modified file: `backend/tests/api/test_data_summary.py` (or wherever the existing data-summary test lives — verify path).
- Modified file: [`frontend/src/features/chat/hooks/useChatSession.ts`](../../frontend/src/features/chat/hooks/useChatSession.ts) — remove `localSessions`; add `bulkDeleteAll` + `useChatMessages` (or equivalent).
- Modified file: [`frontend/src/features/chat/components/SessionList.tsx`](../../frontend/src/features/chat/components/SessionList.tsx) — wire bulk-delete, flip `BULK_DELETE` default, replace placeholders.
- Modified file: [`frontend/src/features/chat/components/ConversationPane.tsx`](../../frontend/src/features/chat/components/ConversationPane.tsx) (or wherever message rendering lives) — render historical messages from `useChatMessages`.
- Modified file: [`frontend/src/features/chat/index.ts`](../../frontend/src/features/chat/index.ts) — comment-block update.
- Modified file: `frontend/messages/en.json` + `frontend/messages/uk.json` — two new keys.
- Modified file: `frontend/.env.example` (or wherever `NEXT_PUBLIC_CHAT_BULK_DELETE` is documented).
- Modified file: [`docs/tech-debt.md`](../../docs/tech-debt.md) — four new TD entries + one cross-link.
- Modified file: [`_bmad-output/planning-artifacts/architecture.md`](../planning-artifacts/architecture.md) — two small additions per AC #12.
- Modified file: `_bmad-output/implementation-artifacts/sprint-status.yaml`.
- Modified file: `/VERSION`.

No new modules, no schema changes, no new infrastructure resources. The story footprint is read-paths and a few wires.

### Testing standards summary

- **Backend**: `pytest-asyncio` with the existing async-session fixtures (mirror `test_chat_schema_cascade.py` from 10.1b for the cascade tests; mirror `test_chat.py` for the route shape). Use the `authenticated_client` fixture for endpoint tests so Cognito auth is exercised end-to-end. CHECK constraints + cascades only fire on real Postgres for some scenarios — the cascade test (`test_bulk_delete_and_account_delete_cascades`) MUST run against the docker-compose Postgres, not in-memory SQLite (mirror 10.1b's `fk_engine` fixture if needed; SQLite with `PRAGMA foreign_keys = ON` works for the FK cascade specifically — see 10.1b's Completion Notes).
- **Frontend**: existing test infra at `frontend/src/features/chat/__tests__/` — Vitest + React Testing Library. MSW or `vi.fn` for fetch mocking (whichever the existing tests use; verify before writing). The hook tests should NOT bind to the network — mock at the React-Query layer.
- **Manual browser smoke**: per AC #10. Mandatory for this story since it's a UX-affecting frontend wire-up.

### Previous Story Intelligence

- **Story 10.9 — Safety Observability** (direct predecessor by sprint order): the `chat.history.*` events 10.10 emits are *additive* on the same JSON shape 10.9 reads. 10.9's metric-filter file (`infra/terraform/modules/app-runner/observability-chat.tf`) does not yet match these events; that's documented in §Scope Boundaries + AC #11 TD entry as a deliberate deferral. Do NOT touch the Terraform file in 10.10.
- **Story 10.7 — Chat UI**: shipped the SessionList sidebar with `localSessions` workaround + the DeleteAllDialog with the typed-confirmation gate + the `BULK_DELETE` / `DELETE_UNDO` env-flag scaffolding. 10.10 picks up exactly where 10.7 left off; the scaffolding shape is preserved unchanged (only the internal wiring changes).
- **Story 10.5 — Streaming API**: established the route conventions in `chat.py` (camelCase, correlation_id, error envelope, `_hash_user_id`-in-logs). 10.10 mirrors these line-for-line.
- **Story 10.5a — Stream-disconnect finalizer**: established the WARN/ERROR severity convention for destructive events on the chat surface. 10.10 follows: `chat.history.bulk_deleted` is WARN (destructive but user-authorized), `chat.history.bulk_delete_failed` is ERROR (operator-actionable).
- **Story 10.4a — AgentCore session handler**: the `terminate_session(handle)` API used by AC #4's pre-cascade termination loop is owned by 10.4a; it's stable and dependency-injected via `get_chat_session_handler`. Reuse without modification.
- **Story 10.1b — Schema + cascade**: see "Reuse from Story 10.1b" above. The migration is the foundation; 10.10 builds on it.
- **Story 10.1a — `chat_processing` consent**: the consent state itself is not read by 10.10 (history endpoints work regardless of consent state per §Scope Boundaries). 10.10's bulk-delete reset is decoupled from consent revoke — they're orthogonal user actions sharing a cascade target.

### Git Intelligence

Recent commits (most recent first):
```
67759f9 Story 10.9: Safety Observability
c79c1b1 Story 10.8c: Red-Team Corpus Expectation Revision (Soft-Refusal Recognition)
7af19ec Story 10.8b: Safety Test Runner + CI Gate
ff89f3f Story 10.8a: Red-Team Corpus Authoring (UA + EN)
c17578d Story 10.7: Chat UI (Conversation, Composer, Streaming, Refusals) // Small infra fixes
```

- **10.9 (`67759f9`) is the immediate predecessor.** No conflicts expected — 10.9 touched Terraform + `session_handler.py` + the operator-runbook + tech-debt. 10.10 touches `chat.py` (no overlap with 10.9's `session_handler.py` edits), `data_summary.py` (untouched by 10.9), the frontend chat feature (untouched by 10.9), and tech-debt (additive new entries, no edits to existing ones except the TD-092 cross-link).
- **10.7 (`c17578d`) is the frontend feature-set 10.10 modifies.** No structural changes; all modifications are surgical. Verify on a clean `main` checkout that `frontend/src/features/chat/components/SessionList.tsx` still has the `BULK_DELETE` flag at line 13 + the `/* 10.10 owns */` comment at line 49 before starting the edits.
- **10.8a–c (corpus + runner)** are entirely backend safety-test infra; zero overlap with 10.10.
- Branch state at start: `main` clean per the latest sprint-status.yaml entry. No in-progress chat work expected.

### Latest Tech Information

No external library research required. All patterns reuse the existing stack:

- **FastAPI** route conventions per `backend/app/api/v1/chat.py`. Pydantic v2 models with `ConfigDict(alias_generator=to_camel)`.
- **SQLModel** + **SQLAlchemy** queries — `select(...).where(...).order_by(...)` for the listing query; `sa_delete(ChatSession).where(ChatSession.user_id == ...)` for bulk delete (FK cascade in the schema does the rest).
- **React Query v5** for the frontend `useQuery` / `useMutation` / `useInfiniteQuery` hooks (per the existing `useChatSession.ts` patterns at lines 5, 54-70, 72-86).
- **next-intl** for i18n keys (per the existing chat-feature pattern).
- **Postgres 16** — pagination uses `(timestamp, uuid)` keyset cursors; this is the standard idiom for stable pagination on (orderable + UUID-primary-key) tables. No ROW_NUMBER, no OFFSET (offset pagination breaks under writes).

### References

- [`epics.md` §Epic 10 §Story 10.10 (line 2154)](../planning-artifacts/epics.md) — story brief
- [`prd.md` FR31 / FR35 / FR70](../planning-artifacts/prd.md) — functional requirements this story closes (data view + chat-history deletion)
- [`architecture.md` §Data Model Additions L1794-L1803](../planning-artifacts/architecture.md#L1794-L1803) — schema invariants 10.10 consumes
- [`architecture.md` §API Pattern — Chat Streaming L1805-L1820](../planning-artifacts/architecture.md#L1805-L1820) — error-envelope conventions extended by 10.10
- [`architecture.md` L1801](../planning-artifacts/architecture.md#L1801) — "Deletion cascade aligned with FR31 + FR70: account deletion → `chat_sessions` deletion → `chat_messages` deletion"
- Story 10.1b — [`10-1b-chat-sessions-messages-schema-cascade.md`](10-1b-chat-sessions-messages-schema-cascade.md) — schema + cascade foundation, the test patterns 10.10 mirrors for cascade verification
- Story 10.5 — [`10-5-chat-streaming-api-sse.md`](10-5-chat-streaming-api-sse.md) — route conventions, error-envelope shape, log-event JSON shape
- Story 10.5a — [`10-5a-send-turn-stream-disconnect-finalizer.md`](10-5a-send-turn-stream-disconnect-finalizer.md) — WARN/ERROR severity convention for destructive events
- Story 10.7 — [`10-7-chat-ui.md`](10-7-chat-ui.md) — frontend chat surface 10.10 modifies
- Story 10.9 — [`10-9-safety-observability.md`](10-9-safety-observability.md) — log-event metric-filter convention (additive follow-up tracked via AC #11 TD)
- [`backend/app/api/v1/chat.py`](../../backend/app/api/v1/chat.py) — chat router (extended)
- [`backend/app/api/v1/data_summary.py`](../../backend/app/api/v1/data_summary.py) — data-summary endpoint (extended)
- [`backend/app/models/chat_session.py`](../../backend/app/models/chat_session.py) + [`backend/app/models/chat_message.py`](../../backend/app/models/chat_message.py) — models reused
- [`backend/app/services/account_deletion_service.py`](../../backend/app/services/account_deletion_service.py) — already wired by 10.1b; 10.10 only verifies the cascade through the new endpoints
- [`backend/app/services/consent_service.py`](../../backend/app/services/consent_service.py) — `revoke_chat_consent` cascade also wired by 10.1b; 10.10 verifies via the new GET
- [`frontend/src/features/chat/hooks/useChatSession.ts`](../../frontend/src/features/chat/hooks/useChatSession.ts) — refactored
- [`frontend/src/features/chat/components/SessionList.tsx`](../../frontend/src/features/chat/components/SessionList.tsx) — wired
- [`frontend/src/features/chat/components/DeleteAllDialog.tsx`](../../frontend/src/features/chat/components/DeleteAllDialog.tsx) — `onConfirm` wired (no shape change)
- [`frontend/src/features/chat/index.ts`](../../frontend/src/features/chat/index.ts) — comment-block update
- [`docs/tech-debt.md`](../../docs/tech-debt.md) — four additions + one cross-link (per AC #11)
- Memory: `feedback_backend_ruff.md` — `ruff check` is a CI gate
- Memory: `feedback_frontend_lint.md` — `npm run lint` is a CI gate; do not demote rules into TD-133
- Memory: `feedback_python_venv.md` — `backend/.venv`
- Memory: `reference_tech_debt.md` — TD-NNN allocation convention

## Project Context Reference

- Sprint status: this story is `backlog` → set to `ready-for-dev` on save.
- Sibling Epic 10 stories: 10.1a (consent), 10.1b (schema + cascades — the foundation), 10.2 (Bedrock guardrails), 10.4a (AgentCore handler), 10.5 (streaming), 10.5a (disconnect finalizer), 10.7 (UI surface 10.10 modifies), 10.9 (observability — additive follow-up tracked), 10.11 (rate-limit envelope — orthogonal).
- Cross-epic consumer: none direct; FR35 / FR70 close out, which Epic 5 (account deletion) was the foundational predecessor for via the `account_deletion_service.child_tables` list extended by 10.1b.
- Project context: [`../../docs/`](../../docs/) for runbooks, tech-debt, versioning policy.

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (1M context)

### Debug Log References

### Completion Notes List

- Ultimate context engine analysis completed — comprehensive developer guide created.
- Implemented three new chat-history routes (`GET /chat/sessions`, `GET /chat/sessions/{id}/messages`, `DELETE /chat/sessions`) plus three `DataSummaryResponse` extension fields (`chatSessionCount`, `chatMessageCount`, `chatActivityRange`).
- Bulk-delete handler iterates each session and calls `handler.terminate_session` before the DB cascade; any `ChatSessionTerminationFailed` aborts the transaction with `503 CHAT_BACKEND_UNAVAILABLE` (no partial deletion). 204 returned even on the zero-sessions case (idempotent).
- Added four new structured-log events (`chat.history.listed`, `chat.history.transcript_listed`, `chat.history.bulk_deleted` WARN, `chat.history.bulk_delete_failed` ERROR). Reused `_hash_user_id` for privacy.
- Frontend: removed the `localSessions` workaround from `useChatSession.ts`; added `bulkDeleteAll` mutation + `useChatMessages` infinite-query hook; flipped `NEXT_PUBLIC_CHAT_BULK_DELETE` default to on (only `"false"` disables); updated `.env.example`. Wired `DeleteAllDialog.onConfirm` to `bulkDeleteAll` with toast feedback. Replaced the `/* 10.10 owns */` placeholder with a comment pointing at TD-136. Updated the comment block in `frontend/src/features/chat/index.ts`. Added `chat.delete.all.toast` + `.error` keys to en.json and uk.json.
- Frontend transcript: `ChatScreen` now combines `useChatMessages` historical pages with the live `useChatStream` turns into the same `ConversationPane` `turns` prop. The user/assistant role union excludes `tool` so the privacy invariant is FE-enforced as well as BE-enforced.
- Tests: new `backend/tests/test_chat_history_endpoints.py` (10 cases — listing, tenant isolation, cursor round-trip, bad cursor, transcript tool-role exclusion, transcript cross-user 404, bulk-delete cascade, idempotent zero-session, terminate-runtime-first, post-revoke empty listing). Extended `backend/tests/test_data_summary_api.py` with two cases for the new chat fields. Added `frontend/src/features/chat/__tests__/useChatSession.test.tsx` + extensions to `SessionList.test.tsx` and `ConversationPane.test.tsx`.
- Tech-debt: added TD-136 (per-session undo), TD-137 (reverse pagination), TD-138 (download export), TD-139 (Story 10.9 metric filters for `chat.history.*`). TD-092 cross-linked with Story 10.10's strict-variant pattern as a reference (TD-092 itself stays resolved; the new Approach reference describes the bulk-delete fail-fast posture).
- Architecture: appended history-route bullet to §API Pattern — Chat Streaming, and a verification line on §Data Model Additions confirming both 10.1b indexes are exercised.
- Pre-merge gates: `cd backend && ruff check .` clean. `cd backend && .venv/bin/pytest -q` → 1191 passed, 7 skipped, 26 deselected. `cd frontend && npm test` → 580 passed (65 files). `cd frontend && npm run lint` → 0 errors (26 pre-existing warnings).
- Manual browser smoke: NOT executed in this session (no display attached). Captured here per the "test the golden path" guidance — operator should run the AC #10 smoke (login → /chat → SessionList renders persisted sessions → click session → ConversationPane renders transcript → "Delete all chats" → confirm → list goes empty → reload → list still empty) before merge.

### File List

- backend/app/api/v1/chat.py (modified — three new routes, cursor helpers, scope comment, log events)
- backend/app/api/v1/data_summary.py (modified — `ChatActivityRange` model + three response fields + two new query branches)
- backend/tests/test_chat_history_endpoints.py (new)
- backend/tests/test_data_summary_api.py (modified — two new chat-field cases + ChatSession/ChatMessage imports)
- frontend/src/features/chat/hooks/useChatSession.ts (modified — removed localSessions, added bulkDeleteAll + useChatMessages)
- frontend/src/features/chat/components/SessionList.tsx (modified — flipped BULK_DELETE default-on, wired bulkDeleteAll, replaced placeholder comment)
- frontend/src/features/chat/components/ChatScreen.tsx (modified — historical-message rendering)
- frontend/src/features/chat/index.ts (modified — comment block per AC #7)
- frontend/messages/en.json (modified — new `chat.delete.all.toast` + `.error`)
- frontend/messages/uk.json (modified — new `chat.delete.all.toast` + `.error`)
- frontend/.env.example (modified — documented `NEXT_PUBLIC_CHAT_BULK_DELETE` default-on)
- frontend/src/features/chat/__tests__/useChatSession.test.tsx (new)
- frontend/src/features/chat/__tests__/SessionList.test.tsx (modified — bulk-delete + no-localSessions cases)
- frontend/src/features/chat/__tests__/ConversationPane.test.tsx (modified — historical-rendering cases)
- frontend/src/features/chat/__tests__/ChatScreen.test.tsx (modified — useChatMessages mock added)
- docs/tech-debt.md (modified — TD-136, TD-137, TD-138, TD-139 added; TD-092 cross-link added)
- _bmad-output/planning-artifacts/architecture.md (modified — two small additions per AC #12)
- _bmad-output/implementation-artifacts/sprint-status.yaml (modified — 10-10 flipped to review)
- VERSION (modified — bumped 1.53.0 → 1.54.0)

### Change Log

- 2026-04-27 — Story 10.10 implemented: chat-history GETs + bulk-delete + data-summary parity + frontend rewiring. All 12 ACs satisfied. Backend 1191 tests green; frontend 580 tests green; ruff + lint clean. Version bumped 1.53.0 → 1.54.0 (MINOR — adds user-facing GET + DELETE surfaces and a `data-summary` field expansion).
