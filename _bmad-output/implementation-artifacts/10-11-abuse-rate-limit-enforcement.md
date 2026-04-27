# Story 10.11: Abuse & Rate-Limit Enforcement

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **chat user whose backend is currently the only Epic 10 story shipping its envelope as a placeholder (the [`ChatRateLimitedError`](../../backend/app/agents/chat/rate_limit_errors.py) skeleton authored by Story 10.5 + the translator at [`backend/app/api/v1/chat.py:210-220`](../../backend/app/api/v1/chat.py#L210-L220) + the 429-aware `createSession` catch at [`frontend/src/features/chat/components/SessionList.tsx:38-44`](../../frontend/src/features/chat/components/SessionList.tsx#L38-L44) + the [`RefusalBubble`](../../frontend/src/features/chat/components/RefusalBubble.tsx) `rate_limited` arm + the [`useChatStream`](../../frontend/src/features/chat/hooks/useChatStream.ts) `cooldownEndsAt` reducer all sitting wired but never fired)**,
I want **the four chat-throttling dimensions pinned in [architecture.md §Rate Limits L1730-L1738](../planning-artifacts/architecture.md#L1730-L1738) (`60 messages per hour per user`, `10 concurrent sessions per user`, per-user daily token cap, global per-IP cap at the API-gateway layer) to be measured and enforced on the actual chat surface — `create_session` rejects the 11th open session with `429 CHAT_RATE_LIMITED` (the typed shape `SessionList.tsx:39` is already catching), `send_turn_stream` raises `ChatRateLimitedError` from a real Redis sliding-window counter for the 61st turn in the rolling hour AND from a real per-user daily token-spend counter once today's cap is exceeded, the per-IP cap is verified to live at the existing edge layer (no new app-layer code, but the inventory must be recorded so a future audit knows where the cap is enforced), the token-spend anomaly metric Story 10.9 already wired (`chat_token_spend_anomaly_warn` + `_page` at [`infra/terraform/modules/app-runner/observability-chat.tf:563-636`](../../infra/terraform/modules/app-runner/observability-chat.tf#L563-L636)) gets the inputs it needs (per-user-bucketed `chat.turn.completed.totalTokensUsed` already emits — but the hard daily cap needs its own counter so a malicious actor doesn't spend 10× daily before the 3σ anomaly fires), and the soft-block UX shipped by Story 10.3b's spec + Story 10.7's `RefusalBubble` finally has a backend that actually emits the envelopes those surfaces are coded against** —
so that **NFR41 ("AgentCore SDK reliability + per-user isolation") + NFR37 ("zero PII leakage in chat") have a denial-of-wallet / denial-of-service complement (a single user cannot brown out the chat tier or run the per-user Bedrock budget into the ground), the `chat_processing` consent's "60 msg/hr soft-block" promise to the user (the only number Story 10.3b's `RateLimitDialog` and `RefusalBubble` actually surface — see the copy table in [`10-3b-chat-ux-states-spec.md` AC #5](10-3b-chat-ux-states-spec.md)) is no longer a UI promise the backend silently reneges on, the `Story 10.11 plugs in by raising instances of this class from its middleware — no translator edit needed.` contract embedded by the 10.5 author at [`rate_limit_errors.py:25-26`](../../backend/app/agents/chat/rate_limit_errors.py#L25-L26) is finally consumed (the `cause` field's `"hourly" | "concurrent" | "daily_tokens" | "unknown"` enum gets exercised end-to-end), the partial token-spend signal Story 10.9 emits becomes both a soft anomaly-band tripwire *and* a hard envelope-enforced cap (the existing 3σ `ANOMALY_DETECTION_BAND` alarm fires *after* damage has begun; the daily-token envelope is the prevention layer that bounds the worst-case damage to one day's budget), the consolidation note in Epic 10 ("Rate-limit envelope previously co-listed under Story 10.4 was consolidated into 10.11 to remove the duplication") is honored — a single PR shipping all four dimensions in one place — and Epic 10 closes (this is the final story; sprint-status flips `epic-10` from `in-progress` to `done` on merge)**.

## Scope Boundaries

This story is **a chat-scoped Redis-backed rate-limiter (three counters) + middleware-style enforcement at the two chat write points (`create_session` + `send_turn_stream`) + a token-spend recording hook + a per-IP-cap inventory note + tests**. Hard out of scope:

- **No new chat-runtime, no new tools, no new prompts, no new chat-message rows.** The rate-limit decision happens *before* `send_turn_stream` invokes the model and *before* `create_session` writes the `chat_sessions` row. A rate-limit refusal is a `CHAT_REFUSED` SSE frame (or a `429` HTTP response on `create_session`); it is **not** persisted to `chat_messages` (the rejected turn never made it past the gate, so there's no user/assistant message pair to record). This matches the Story 10.5 typed-exception convention — exceptions raised before `BackendStreamDone` skip the `_persist_turn_pair` call.
- **No edits to `ChatRateLimitedError`'s shape.** The skeleton at [`backend/app/agents/chat/rate_limit_errors.py`](../../backend/app/agents/chat/rate_limit_errors.py) ships with `correlation_id`, `retry_after_seconds`, and `cause: Literal["hourly", "concurrent", "daily_tokens", "unknown"]` — 10.11 *raises* this class and populates the fields; it does NOT add new fields, rename `cause` values, or split the class into siblings. The translator at [`backend/app/api/v1/chat.py:210-220`](../../backend/app/api/v1/chat.py#L210-L220) is exercised verbatim. If a future story needs a 5th cause (e.g. `"abuse_pattern"`), that's a follow-up, not a 10.11 amendment.
- **No edits to the `CHAT_REFUSED` envelope shape, the `chat-refused` SSE event, or the frontend `RefusalBubble`.** The architecture envelope at [architecture.md §API Pattern — Chat Streaming L1807-L1820](../planning-artifacts/architecture.md#L1807-L1820) already encodes `reason=rate_limited` + nullable `retry_after_seconds`; the FE consumer at [`useChatStream.ts:89-98`](../../frontend/src/features/chat/hooks/useChatStream.ts#L89-L98) already derives `cooldownEndsAt` from `retryAfterSeconds`; the FE refusal copy already covers the three triggers (hourly mm:ss countdown, concurrent dialog at `SessionList.tsx:32`, daily wall-clock fallback at `RefusalBubble.tsx:82`). 10.11 produces the data those surfaces consume; it does not author new UI.
- **No new i18n keys.** All `chat.refusal.rateLimited.*`, `chat.session.create_error`, `chat.dialog.concurrent_sessions.*` keys already exist from Story 10.7 (per the Story 10.3b copy table at [`10-3b-chat-ux-states-spec.md` AC #6](10-3b-chat-ux-states-spec.md)). 10.11 does not add a single string to `frontend/messages/en.json` or `frontend/messages/uk.json`.
- **No frontend file additions, no FE refactors.** The full FE consumption surface for `rate_limited` already shipped (Story 10.7 + Story 10.10's `useChatSession` already invalidates session lists on bulk-delete; the concurrent-cap dialog is wired). 10.11 verifies the FE surfaces fire by hitting them from the BE in tests; it does not modify any `frontend/src/**` file.
- **No global per-IP cap implementation in app code.** The `Global per-IP cap at the API-gateway layer (reuses existing limit)` line in architecture is satisfied by the **existing AWS WAF rule** at [`infra/terraform/modules/app-runner/waf.tf`](../../infra/terraform/modules/app-runner/waf.tf) — 10.11 records this as the canonical IP-cap location in a `## Inventory: Per-IP Cap` subsection of the operator runbook (so a future incident-response author finds the throttle at the WAF layer instead of bouncing through app code), but no new Terraform resource is added in 10.11. **If the WAF audit finds the existing rule is mis-tuned for chat (e.g. 100 rps is too generous for a 60-msg/hr-per-user envelope), file a TD; do not retune in 10.11** — chat WAF tuning would block on traffic baseline data we don't have yet.
- **No token-spend anomaly alarm changes.** Story 10.9's `chat_token_spend_anomaly_warn` (3σ) + `_page` (5σ) alarms at [`observability-chat.tf:563-636`](../../infra/terraform/modules/app-runner/observability-chat.tf#L563-L636) already monitor the *bucketed* per-user token spend emitted by `chat.turn.completed`. 10.11 ADDS a **hard cap** on the same input (per-user daily total — a Redis counter, not a metric-filter aggregate) so the band-anomaly is the second line of defense, not the only one. The Terraform alarms are not edited; the metric filters are not edited; the `Kopiika/Chat` namespace is unchanged.
- **No new Terraform resources.** The hard daily cap is a Redis counter behind the app; the band anomaly alarm already exists; the WAF IP cap already exists. 10.11 does not touch `infra/terraform/**` (one-line PR exception below for AC #6 if a new metric filter is required for the bulk-rejected event — but the current preferred path is to extend the existing `chat_refusal_rate_warn` filter at [`observability-chat.tf:511-556`](../../infra/terraform/modules/app-runner/observability-chat.tf#L511-L556) which already counts all `chat-refused` reasons; verify in the EXPLAIN-equivalent step of AC #5 that `rate_limited` is captured by the existing pattern before deciding).
- **No migration / no schema changes.** The `chat_sessions` and `chat_messages` schemas are frozen since Story 10.1b. 10.11 reads `chat_sessions` (counts open per-user sessions) and never writes to either table outside the existing `_persist_turn_pair` (which itself is unreachable when 10.11 short-circuits the turn).
- **No `RateLimiter` class refactor in [`backend/app/services/rate_limiter.py`](../../backend/app/services/rate_limiter.py).** That module's existing methods (`check_rate_limit` for login IPs, `check_upload_rate_limit`, `check_consent_rate_limit`, `check_feedback_rate_limit`) are stable. 10.11 *adds* three new methods on the same class — `check_chat_hourly_rate_limit(user_id) -> int` (returns retry-after; raises on cap), `acquire_chat_concurrent_session_slot(user_id) -> bool` (returns False if at cap), `release_chat_concurrent_session_slot(user_id) -> None`, `check_chat_daily_token_cap(user_id, projected_tokens) -> int` (returns retry-after; raises on cap), `record_chat_token_spend(user_id, tokens_used) -> None` — all following the existing Redis sliding-window / counter idioms in that file. **No method signatures are changed; no existing rate-limit behavior is altered.**
- **No "soft-warning at 80% of cap" UX.** Some teams ship a "you're approaching your limit" warning before the hard cap fires; 10.3b's spec is explicit that the only soft surface is the post-hit refusal variant + the cooldown countdown. Adding a pre-hit warning is a UX change that lands in 10.3b, not here. File a TD if product asks for it later.
- **No abuse pattern detection beyond the four envelope dimensions.** Pattern-based detection (e.g. "this user is sending 50 prompts that all match a known jailbreak template") is the safety harness's job (Story 10.8a–c) — those land as `guardrail_blocked` or `prompt_leak_detected` refusals via the input-validator + Bedrock layers, not as `rate_limited`. 10.11 is purely envelope-throttle; if the envelope is hit, the user is throttled regardless of whether their prompts were benign or malicious. (This is intentional — a benign user who legitimately needs > 60 msg/hr is rare enough that the soft-block gives them a clear retry path.)
- **No retry-after derivation tricks.** `retry_after_seconds` is computed by the same formula the existing `RateLimiter.check_rate_limit` uses — `int(oldest_entry_in_window + window_seconds - now) + 1` for the hourly cap, `int(seconds_until_utc_midnight)` for the daily cap, `null` for the concurrent cap (no countdown — user closes a session manually). No HMAC-signed tokens, no exponential backoff, no jitter. The minimum retry-after is 1 second (defensive — an integer 0 confuses the FE countdown).
- **No `terminate_all_user_sessions` integration.** That method on `ChatSessionHandler` exists for consent-revoke + account-deletion paths; bulk-rejecting open sessions because a user is over-cap is **not** a 10.11 behavior. Once at the concurrent-cap, the user manually closes a session via the existing per-session DELETE flow (Story 10.5 + 10.10) to free a slot.

A scope comment at the top of `backend/app/api/v1/chat.py`'s rate-limit dependency block enumerates these deferrals.

## Acceptance Criteria

1. **Given** the Redis-backed [`RateLimiter`](../../backend/app/services/rate_limiter.py) service already injected via [`get_rate_limiter`](../../backend/app/api/deps.py) and the four-dimension architecture pin at [architecture.md §Rate Limits L1730-L1738](../planning-artifacts/architecture.md#L1730-L1738), **When** Story 10.11 lands, **Then** five new methods are added to `RateLimiter` (in [`backend/app/services/rate_limiter.py`](../../backend/app/services/rate_limiter.py), beneath the existing `check_feedback_rate_limit`):
   - `check_chat_hourly_rate_limit(user_id: str, *, max_turns: int = 60, window_seconds: int = 3600) -> None` — sliding-window ZSET keyed `rate_limit:chat:hourly:{user_id}`. On cap-exceeded, raises `ChatRateLimitedError(correlation_id=..., retry_after_seconds=..., cause="hourly")` (raise the chat-typed exception, NOT `ValidationError(code="RATE_LIMITED")` — the chat envelope is distinct from the upload/consent surfaces). The caller is responsible for passing the correlation_id (the route already has one). Records the turn into the ZSET on the success path so the next call sees it.
   - `acquire_chat_concurrent_session_slot(user_id: str, *, max_concurrent: int = 10) -> bool` — counter pattern. Reads the **authoritative** count from the `chat_sessions` table (NOT from a Redis counter — sessions outlive any Redis TTL we'd pick, and a Redis-only counter drifts under restart / consent-revoke cascades / TTL-expiry). Returns `True` if the user has < `max_concurrent` open sessions. Returns `False` (caller raises) if at cap. **No Redis writes** — this method's name is "acquire" because it's the pre-create gate, but the actual slot is "owned" by the existing `chat_sessions` row.
   - `release_chat_concurrent_session_slot(user_id: str) -> None` — **no-op**. Authored explicitly so future authors don't add a Redis counter; the slot release is implicit in the existing per-session DELETE handler (Story 10.5) and bulk-DELETE (Story 10.10) decrementing the `chat_sessions` row count. The method is here as a **doc anchor** + a future hook (e.g. if a cache layer is later added, the release becomes the cache invalidator). Keep the body `pass` + a docstring; do NOT remove the method, even if a strict-lint rule flags it — it's load-bearing for the inventory.
   - `check_chat_daily_token_cap(user_id: str, *, max_tokens_per_day: int | None = None, projected_tokens: int = 0) -> None` — counter pattern with day-rollover semantics. Key `rate_limit:chat:daily_tokens:{user_id}:{utc_yyyy_mm_dd}` (date-suffix, NOT a sliding window — daily cap is calendar-day-aligned per the FE wall-clock UX in [`10-3b-chat-ux-states-spec.md`](10-3b-chat-ux-states-spec.md) and per [architecture.md L1736-L1737](../planning-artifacts/architecture.md#L1736-L1737)'s phrasing). The TTL on the key is set to `25 * 3600` (25h) on first write so the key expires the day after it's relevant. The `max_tokens_per_day` defaults to `settings.CHAT_DAILY_TOKEN_CAP_PER_USER` (new env var; default `200_000` — Sonnet at ~3¢/1k input means ~$6/user/day worst-case before cap; tune per [Bedrock Cost Controls](../planning-artifacts/architecture.md) baseline). `projected_tokens` is the *upper-bound estimate* of input tokens for the upcoming turn (see AC #4 for derivation). On `current_total + projected > cap`, raises `ChatRateLimitedError(... cause="daily_tokens", retry_after_seconds=seconds_until_utc_midnight)`. **Does NOT increment** — that's `record_chat_token_spend`'s job after the turn completes.
   - `record_chat_token_spend(user_id: str, tokens_used: int) -> None` — INCRBY on the same `rate_limit:chat:daily_tokens:{user_id}:{utc_yyyy_mm_dd}` key; sets the TTL on first write; idempotent on subsequent INCRBYs (TTL is reset only if `EXPIRE` is needed — use `SET ... EX ... NX` semantics or check via `TTL` and only `EXPIRE` if -1). Called *after* a successful turn from `send_turn_stream`'s post-stream finalizer (or from the route's `chat-complete` handler — see AC #4 for the integration point).

   All five methods follow the existing `pipe = self._redis.pipeline()` idiom; tests exercise them against an `aioredis.Redis` connected to a real Redis (the `redis_client` fixture from `backend/tests/conftest.py` — verify by reading the file; if absent, mirror the pattern from `test_rate_limiter.py`).

2. **Given** the new `RateLimiter` methods from AC #1, **When** [`create_session_endpoint`](../../backend/app/api/v1/chat.py) at line ~254 is wired with the concurrent-cap gate, **Then**:
   - The route gains a `rate_limiter: Annotated[RateLimiter, Depends(get_rate_limiter)]` parameter (matching the existing `auth.py:145` pattern).
   - **Before** `handler.create_session(...)` is called, the route invokes `rate_limiter.acquire_chat_concurrent_session_slot(str(user.id))`. On `False` return, the route raises `HTTPException(status_code=429, detail={"error": {"code": "CHAT_RATE_LIMITED", "message": "You have 10 active chats. Close one to start a new session.", "correlationId": <uuid>, "cause": "concurrent"}})` — the `code` MUST be exactly `CHAT_RATE_LIMITED` so the FE catch at [`SessionList.tsx:39`](../../frontend/src/features/chat/components/SessionList.tsx#L39) (`err.bodyText.includes("CHAT_RATE_LIMITED")`) opens the existing `ConcurrentSessionsDialog`.
   - The `cause` field is added to the error envelope (read by future tooling; FE ignores it today but it's a free trace dimension).
   - On the success path (slot acquired), no Redis write is performed (per AC #1's no-write contract).
   - A structured-log event `chat.ratelimit.create_blocked` (INFO level — this is a soft-block, expected behavior) is emitted on the 429 path with fields: `user_id_hash`, `correlation_id`, `current_session_count` (the value that triggered the block — should be `>= 10`), `cause: "concurrent"`. The success path emits no rate-limit log (only the existing `chat.session.created` event Story 10.5 already emits).
   - **Test** (`backend/tests/test_chat_rate_limit.py::test_create_session_blocked_at_concurrent_cap`): seed user with exactly 10 open `chat_sessions` rows; POST `/chat/sessions` → 429 with body `{"error": {"code": "CHAT_RATE_LIMITED", "cause": "concurrent", ...}}`. Seed user with 9 → success. Verify the `chat_sessions` rowcount is 10 after a deletion + creation cycle (no leakage).

3. **Given** the [`stream_chat_turn`](../../backend/app/api/v1/chat.py) SSE route at line ~774 and the fact that EventSource auth is via `?token=<JWT>` (no header — see [`backend/app/api/v1/chat.py:778`](../../backend/app/api/v1/chat.py#L778)), **When** the hourly-cap gate is wired, **Then**:
   - The route gains a `rate_limiter: Annotated[RateLimiter, Depends(get_rate_limiter)]` parameter.
   - **Before** the SSE stream opens (specifically: after the `user_id = await get_user_id_from_token(token, db)` call at line ~791, after the cross-user 404 check at line ~796, after the input-length-cap 422 at line ~810, but **before** `start_ts = time.monotonic()` and the `event_generator` starts), the route invokes `rate_limiter.check_chat_hourly_rate_limit(str(user_id))`. On `ChatRateLimitedError`, the **route does NOT open the SSE stream** — instead, it raises a 200-response containing a single `chat-refused` SSE frame followed by stream close. This is the **same shape Story 10.5's translator emits for in-stream refusals** (see `_translate_typed_exc_to_refusal` at line ~140) but issued *before* the stream opens.
     - Rationale: returning a 429 here would break the FE's EventSource — the SSE contract is "200 + terminal `chat-refused`". The FE `useChatStream` already routes `chat-refused` with `reason=rate_limited` to the `RateLimitDialog` countdown UX; emitting a 429 here would route the user through the WAF-block error path instead. Alignment with the Story 10.5 SSE error-envelope is mandatory for the FE to render the right UX.
     - Implementation: wrap the pre-stream `check_chat_hourly_rate_limit` call in a `try/except ChatRateLimitedError as exc` that returns a `StreamingResponse` with a single-frame async generator yielding `_sse_event("chat-refused", _refused_payload(reason="rate_limited", correlation_id=correlation_id, retry_after_seconds=exc.retry_after_seconds))`. (Mirror the existing translator path so the wire frame is byte-for-byte identical.)
   - On the success path, the hourly counter has been recorded (the ZSET ZADD inside `check_chat_hourly_rate_limit` happens on the no-cap path, BEFORE the model is invoked — this is intentional: counting the request as "intended", not "completed", prevents a partial-stream-then-disconnect from consuming the budget without recording the counter; if the model errors, the user has still spent one of their 60).
   - A structured-log event `chat.ratelimit.turn_blocked` (INFO level) is emitted on the refusal path with fields: `user_id_hash`, `correlation_id`, `cause: "hourly"`, `retry_after_seconds`, `db_session_id`. **No log on the success path** (the existing `chat.stream.opened` log already records the turn — adding a "rate-limit passed" log doubles every line for no signal).
   - **Test** (`backend/tests/test_chat_rate_limit.py::test_send_turn_blocked_at_hourly_cap`): seed `rate_limit:chat:hourly:{user_id}` with 60 entries within the last hour; POST a 61st turn → SSE response with single `chat-refused` frame, `reason=rate_limited`, `retry_after_seconds` between 1 and 3600. Seed with 59 → turn proceeds (Bedrock is mocked to a single token + complete). Verify the ZSET has 60 entries after the 60th success and 60 entries (NOT 61) after the 61st block (the cap-exceeded path does NOT record).

4. **Given** the per-user daily token cap from AC #1 + the model-side token usage already tracked in `ChatStreamCompleted.input_tokens` / `output_tokens` (emitted at [`backend/app/api/v1/chat.py:976-977`](../../backend/app/api/v1/chat.py#L976-L977)), **When** the daily-cap is wired, **Then**:
   - **Pre-turn projection** (cheap upper-bound): before `check_chat_hourly_rate_limit`, the route invokes `rate_limiter.check_chat_daily_token_cap(str(user_id), projected_tokens=_estimate_input_tokens(payload.message, chat_session))`. The estimate is `len(payload.message) // 3 + 8000` (a heuristic — 1 token ≈ 3 chars for English, plus 8k for system prompt + memory window; this OVER-estimates so a turn never sneaks through a near-cap user). The function lives in `backend/app/agents/chat/token_estimate.py` (new file, ~20 lines, no external deps); a docstring documents the heuristic + a TD-NNN reference for replacing it with a Bedrock-API-side `count_tokens` call (which doesn't exist in `bedrock-runtime` SDK as of 2026-04 — verify in the live SDK before merge).
   - On `ChatRateLimitedError(cause="daily_tokens")`, the route emits a single `chat-refused` SSE frame with `reason=rate_limited`, `retry_after_seconds=<seconds_until_utc_midnight>` (computed in the rate-limiter, not the route). The FE `RefusalBubble` renders the daily-cap variant (no countdown — wall-clock fallback) when `retry_after_seconds > 3600` per the existing FE logic at [`RefusalBubble.tsx:68-90`](../../frontend/src/features/chat/components/RefusalBubble.tsx#L68-L90). **Verify in the BE→FE integration test** that a `retry_after_seconds = 50000` (≈ 14h to midnight) triggers the wall-clock UX, not the mm:ss countdown — the threshold logic is FE-side, but a regression in either layer breaks the contract.
   - **Post-turn recording**: in the `event_generator` at the `ChatStreamCompleted` branch (around line ~972 of `chat.py` where `chat-complete` is emitted), after the existing `logger.info("chat.stream.completed", ...)` call, invoke `await rate_limiter.record_chat_token_spend(str(user_id), tokens_used=event.input_tokens + event.output_tokens)`. This records *actual* spend after a successful turn. **Failure-case behavior**: if the turn ends in a refusal (any branch that doesn't reach `chat-complete`), no recording happens — refused turns shouldn't count against the user's daily budget (the refusal already cost them; double-charging is hostile). If the stream disconnects mid-token-emission, the existing 10.5a finalizer path records partial spend via `chat.stream.finalizer_succeeded` — extend that finalizer to also record token spend for the partial turn (see AC #4 of [`10-5a-send-turn-stream-disconnect-finalizer.md`](10-5a-send-turn-stream-disconnect-finalizer.md) for the finalizer hook point — the existing finalizer already has access to `input_tokens`).
   - **Test** (`backend/tests/test_chat_rate_limit.py::test_send_turn_blocked_at_daily_token_cap`): seed `rate_limit:chat:daily_tokens:{user_id}:{today}` with `199_500` tokens; POST a turn whose projected `len(message)//3 + 8000` puts it over `200_000`. Expect `chat-refused` with `reason=rate_limited`, `retry_after_seconds` ≈ seconds-until-midnight ± 60. Verify the Redis counter is unchanged (no INCRBY on block path).
   - **Test** (`backend/tests/test_chat_rate_limit.py::test_record_chat_token_spend_increments_after_complete`): mock the backend to emit `ChatStreamCompleted(input_tokens=100, output_tokens=200)`; POST turn; after the SSE closes, assert `await redis.get("rate_limit:chat:daily_tokens:{user_id}:{today}") == "300"`.
   - **Test** (`backend/tests/test_chat_rate_limit.py::test_daily_token_cap_resets_at_utc_midnight`): freeze time to 23:59:00 UTC, push counter to 199_500, advance time to 00:00:30 UTC (next day key suffix), assert a new turn projects against the new key with empty count. (Use `freezegun` + a manual key-recompute — the key suffix is `datetime.now(UTC).date().isoformat()` and tests just need to see the day-rollover key namespace).

5. **Given** the existing `chat-refused` SSE event already feeds the metric filter `chat_refusal_rate_warn` at [`observability-chat.tf:511-556`](../../infra/terraform/modules/app-runner/observability-chat.tf#L511-L556), **When** Story 10.11 verifies the per-cause refusal metric is captured, **Then**:
   - **Read the existing filter pattern** (in `observability-chat.tf:511-556`) to confirm whether it dimensions by `reason` field or only counts the totality of `chat-refused` events. If the existing pattern matches `{ $.message = "chat.stream.refused" || $.message = "chat.stream.refusal_emitted" || ... }` without a `reason` discriminator, **no Terraform edit is required** — the existing alarm fires on ANY refusal cause (rate-limit refusals are already counted in the warn alarm at `>= 20%` over 30m). Document this in a new `## Inventory: Rate-Limit Observability` section of `docs/operator-runbook.md` (added under Story 10.9's `## Chat Safety Operations` section) listing: (a) the existing alarm catches rate-limit refusals as a subset of all refusals; (b) the per-cause breakdown lives in the structured-log events from AC #2/#3/#4 (`chat.ratelimit.create_blocked`, `chat.ratelimit.turn_blocked`); (c) operators can run a Logs Insights query to break down by cause; (d) IF a future incident requires a per-cause CloudWatch metric, file a TD-NNN follow-up against the Story 10.9 module — do not retro-fit it in 10.11.
   - **Token-spend hard-cap interaction with the Story 10.9 anomaly bands**: the `chat_token_spend_anomaly_warn` alarm at [`observability-chat.tf:563-606`](../../infra/terraform/modules/app-runner/observability-chat.tf#L563-L606) reads the bucketed `chat.turn.completed.totalTokensUsed` metric. **Verify** by re-running `infra/terraform/modules/app-runner/test_chat_metric_filters.sh` (or its equivalent — verify path before running) that the existing metric filter still captures per-turn token spend after this story's `record_chat_token_spend` is added. The two systems are decoupled: the metric filter slices CloudWatch metrics for trend / anomaly observability; the Redis counter slices for hard envelope. **Do not merge them.**

6. **Given** the existing AWS WAF rule at [`infra/terraform/modules/app-runner/waf.tf`](../../infra/terraform/modules/app-runner/waf.tf) handles the global per-IP rate-limit pin from architecture line 1737, **When** Story 10.11 verifies the per-IP cap inventory, **Then**:
   - A new `## Inventory: Per-IP Cap Location` subsection is added to `docs/operator-runbook.md` (under the same `## Chat Safety Operations` section as AC #5's inventory note) recording: (a) the per-IP cap lives in WAF, not app code; (b) the current rate is `<read it from waf.tf and quote it>` per IP per 5-min window; (c) WAF blocks return a generic 403 from the WAF layer, NOT a `CHAT_REFUSED` SSE — the FE generic-error toast applies (per Story 10.3b's "Per-IP gateway 429 — out of scope for 10.3b" delegation at [`10-3b-chat-ux-states-spec.md` AC #5](10-3b-chat-ux-states-spec.md)); (d) IF chat-tier-specific WAF tuning is wanted (e.g. lower per-IP rate for `/api/v1/chat/*` than the global limit), file a TD — 10.11 does NOT retune.
   - **Test** (manual, recorded in PR description): hit the chat endpoint from a single IP at the WAF rate (use `xargs -P` or similar local bench tool — verify before running, no production traffic), confirm WAF returns 403 once the rate is exceeded. This is a *manual smoke* in the dev environment — do NOT add an automated test that hits AWS WAF (which would couple the test suite to live AWS infra). If a dev environment doesn't have WAF in front, document it as "manual verification deferred to staging deploy".

7. **Given** the structured-log inventory pattern established by Stories 10.4b–10.10 + the existing JSON shape convention in `chat.py`, **When** Story 10.11's events emit, **Then** three new `extra={"message": "chat.ratelimit.<event>", ...}` events land on the API stdout:
   - `chat.ratelimit.create_blocked` — fields: `user_id_hash`, `correlation_id`, `cause: "concurrent"`, `current_session_count`. INFO level (soft-block, expected). Fired only on the `acquire_chat_concurrent_session_slot` False-return path (AC #2).
   - `chat.ratelimit.turn_blocked` — fields: `user_id_hash`, `correlation_id`, `cause: "hourly" | "daily_tokens"`, `retry_after_seconds`, `db_session_id`. INFO level. Fired only on a `ChatRateLimitedError` raised from the pre-stream gates (AC #3 + AC #4).
   - `chat.ratelimit.token_spend_recorded` — fields: `user_id_hash`, `tokens_added`, `daily_total_after`, `db_session_id`. DEBUG level (NOT INFO — this fires every turn; INFO-level would 60×-amplify the log volume per chat user; DEBUG is filtered out in prod by default but available for forensic spelunking). Fired from `record_chat_token_spend` after the INCRBY succeeds.
   - The `_hash_user_id` helper at [`backend/app/agents/chat/session_handler.py`](../../backend/app/agents/chat/session_handler.py) is reused — no new hashing helper, no raw `user_id` in logs.
   - Story 10.9's metric filters are NOT updated (per §Scope Boundaries + AC #5); the events are wire-compatible.

8. **Given** the test surface, **When** Story 10.11 lands, **Then**:
   - **Backend** (`backend/tests/test_chat_rate_limit.py` — new file): all five test cases enumerated in AC #1–#4 above. Plus: (i) `test_release_chat_concurrent_session_slot_is_noop` — call the method and assert no Redis interaction (mock the `_redis` attribute and assert no method calls); (ii) `test_check_chat_hourly_rate_limit_records_on_success` — verify ZADD on success path; (iii) `test_check_chat_hourly_rate_limit_does_not_record_on_block` — verify NO ZADD on cap-exceeded path; (iv) `test_record_chat_token_spend_sets_ttl_on_first_write` — verify TTL is `25 * 3600 ± 5` after first INCRBY; (v) `test_record_chat_token_spend_does_not_reset_ttl_on_subsequent_write` — second INCRBY does not push TTL out (use `redis.ttl(key)` and assert it's monotonically decreasing); (vi) `test_send_turn_finalizer_records_partial_spend_on_disconnect` — wire to Story 10.5a's finalizer hook + assert partial spend is recorded.
   - **Backend** (`backend/tests/test_rate_limiter.py` extension): three unit tests on the `RateLimiter` methods directly (no FastAPI app), exercising each new method against the existing `redis_client` test fixture. Mirror the existing `test_check_upload_rate_limit` shape.
   - **Backend** (`backend/tests/test_chat_endpoints.py` extension or wherever the existing `chat.py` route tests live — verify path before adding): two integration tests covering the 429 envelope shape on `create_session` (AC #2) + the SSE single-frame `chat-refused` on hourly + daily caps (AC #3, AC #4). Use the existing SSE test client pattern from Story 10.5's tests.
   - **Frontend**: NO new frontend tests. The FE rate-limit surfaces (`RefusalBubble` rate_limited arm, `useChatStream` `cooldownEndsAt` reducer, `SessionList` 429 catch, `ConcurrentSessionsDialog`) are already covered by Story 10.7's tests + Story 10.10's tests; 10.11's BE changes are validated by BE tests fed against the same wire shapes those FE tests already mock.
   - **All suites** green: `cd backend && .venv/bin/pytest -q` AND `cd frontend && npm run lint && npm test` (per the `feedback_frontend_lint.md` memory + `feedback_backend_ruff.md` memory). The frontend suites are run for regression-confidence even though no FE files change.

9. **Given** the project's pre-merge gates, **When** Story 10.11 is closed, **Then**:
   - `cd backend && ruff check .` clean.
   - `cd backend && .venv/bin/pytest -q` green — no skips introduced by 10.11.
   - `cd frontend && npm run lint` clean — no new TD-133 demotions.
   - `cd frontend && npm test` green — verify the existing rate-limit FE tests still pass (no FE behavior change, but the wire format shouldn't drift).
   - The chat surface still renders end-to-end manually with a forced rate-limit:
     - **Hourly**: log in → /chat → send 60 turns (or seed Redis directly: `redis-cli ZADD rate_limit:chat:hourly:<user_uuid> $(seq 1 60 | xargs -I{} echo "$(date +%s).{} $(date +%s).{}")` — verify before running) → 61st turn → `RefusalBubble` mm:ss countdown renders.
     - **Concurrent**: open 10 sessions → "New chat" → `ConcurrentSessionsDialog` opens.
     - **Daily**: `redis-cli SET rate_limit:chat:daily_tokens:<user_uuid>:$(date -u +%Y-%m-%d) 199900` → send a turn → wall-clock daily-cap variant renders.
     - Capture screenshots / GIF in PR description per parent CLAUDE.md "test the golden path in a browser before reporting complete".
   - `/VERSION` is bumped (MINOR — adds enforced rate-limit envelopes; no breaking client changes).
   - `_bmad-output/implementation-artifacts/sprint-status.yaml`: `10-11-abuse-rate-limit-enforcement` flips `ready-for-dev` → `in-progress` → `review` → (post-merge) `done`. **Critically**, since 10.11 is the last Epic 10 story, the merge author also flips `epic-10` from `in-progress` → `done` in the same commit (or in the immediate follow-up commit if `code-review`'s auto-promotion only handles the story key — verify by reading the `code-review` slash-command workflow before merge).

10. **Given** the deferrals enumerated in §Scope Boundaries and embedded in ACs above, **When** Story 10.11 lands, **Then** [`docs/tech-debt.md`](../../docs/tech-debt.md) is updated with new TD-NNN entries (assign the next free numbers per `reference_tech_debt.md` memory — currently TD-140 is the latest, so allocate TD-141, TD-142, TD-143 unless other PRs land first; verify via `git log docs/tech-debt.md` immediately before merge):
    - **TD-NNN — "Replace heuristic input-token estimator with Bedrock-side token counter"**: AC #4's `_estimate_input_tokens` uses `len(message) // 3 + 8000`. Once `bedrock-runtime` SDK exposes a `count_tokens` action (or similar), swap the heuristic. Until then, the over-estimate biases against false-positives on the daily-cap (occasionally users get blocked slightly earlier than the true cap — acceptable, denial-of-wallet bias is correct; an under-estimate would let a user exceed the cap). Owner: Epic 10 / TBD; severity: LOW; trigger: AWS announces `bedrock-runtime:CountTokens` API.
    - **TD-NNN — "Per-cause CloudWatch metric breakdown for chat-refused"**: AC #5 defers a per-cause metric filter on `chat-refused`. The existing aggregate alarm catches rate-limit refusals as a subset of all refusals. Owner: Story 10.9 follow-up / TBD; severity: LOW; trigger: post-prod incident requires per-cause alarm thresholds (e.g. "alarm if rate-limit refusal rate > N% but ungrounded refusal rate is normal").
    - **TD-NNN — "Chat-tier-specific WAF tuning"**: AC #6 defers a chat-specific WAF rule (the global per-IP rate is currently shared across all API endpoints). If chat traffic profile diverges from upload/search traffic, file a TD-NNN to add a chat-prefix WAF rule. Owner: Epic 10 / TBD; severity: LOW; trigger: WAF dashboard shows chat endpoint hitting the global rate consistently while non-chat endpoints have headroom.

11. **Given** the tech-spec convention this epic follows, **When** the architecture doc is touched (lightly), **Then**:
    - The `### Rate Limits` subsection at [architecture.md L1730-L1738](../planning-artifacts/architecture.md#L1730-L1738) gains a one-line implementation pointer at the end (e.g., "Implementation: `RateLimiter.check_chat_hourly_rate_limit` / `acquire_chat_concurrent_session_slot` / `check_chat_daily_token_cap` / `record_chat_token_spend` in [`backend/app/services/rate_limiter.py`](../../backend/app/services/rate_limiter.py); enforced at [`backend/app/api/v1/chat.py`](../../backend/app/api/v1/chat.py) `create_session_endpoint` (concurrent) + `stream_chat_turn` (hourly + daily). Per-IP cap: WAF, see [`infra/terraform/modules/app-runner/waf.tf`](../../infra/terraform/modules/app-runner/waf.tf). — Story 10.11."). The four-bullet envelope itself is unchanged.
    - The `### API Pattern — Chat Streaming` subsection at [architecture.md L1805-L1820](../planning-artifacts/architecture.md#L1805-L1820) is unchanged — the envelope already includes `rate_limited` + nullable `retry_after_seconds`. No edit needed.

## Tasks / Subtasks

- [x] **Task 1 — `RateLimiter` chat methods** (AC #1)
  - [ ] 1.1 Read [`backend/app/services/rate_limiter.py`](../../backend/app/services/rate_limiter.py) end-to-end. Mirror the `pipe = self._redis.pipeline()` idiom used by `check_upload_rate_limit` for the hourly ZSET method.
  - [ ] 1.2 Implement `check_chat_hourly_rate_limit` — sliding-window ZSET, raises `ChatRateLimitedError` with `cause="hourly"`. The `correlation_id` is a kwarg on the caller — make the method accept it as a kwarg, NOT generate a new uuid (the caller already has one).
  - [ ] 1.3 Implement `acquire_chat_concurrent_session_slot` — DB-side count via SQLModel. **Verify the count is per-user** (not per-tenant — same thing here, but the WHERE clause is `user_id == user_id` not session-scoped). Read the count from `chat_sessions` only (not from a Redis cache; Redis is a wrong source of truth for slot ownership). Method takes a `db: AsyncSession` parameter — pass it from the route via `Depends(get_db)`.
  - [ ] 1.4 Implement `release_chat_concurrent_session_slot` as a `pass` no-op with a docstring explaining why it exists (anchor for future cache layer).
  - [ ] 1.5 Implement `check_chat_daily_token_cap` — date-suffixed key, 25h TTL on first write, raises `ChatRateLimitedError` with `cause="daily_tokens"`, `retry_after_seconds=seconds_until_utc_midnight`. The `seconds_until_utc_midnight` helper: `(datetime.combine(today + timedelta(days=1), time.min, UTC) - datetime.now(UTC)).total_seconds()` — returns int.
  - [ ] 1.6 Implement `record_chat_token_spend` — INCRBY + conditional EXPIRE-on-first-write (use `EXPIRE ... NX` if available in `redis-py` ≥ 4.6; otherwise `TTL ... -1 → EXPIRE` two-step). DEBUG-level log per AC #7.
  - [ ] 1.7 Add a new env var `CHAT_DAILY_TOKEN_CAP_PER_USER: int = 200_000` to `backend/app/core/config.py` (verify the existing settings shape — likely `Settings(BaseSettings)` from pydantic-settings).
  - [ ] 1.8 Verify ruff + mypy clean against this file.

- [x] **Task 2 — `create_session_endpoint` concurrent-cap gate** (AC #2)
  - [ ] 2.1 Add `rate_limiter` dep + `db` dep (already present) to the route signature.
  - [ ] 2.2 Pre-call gate: `if not await rate_limiter.acquire_chat_concurrent_session_slot(db, str(user.id)): raise HTTPException(429, ...)` — exact envelope shape per AC #2.
  - [ ] 2.3 Verify the `code` field is exactly `"CHAT_RATE_LIMITED"` so the FE catch matches.
  - [ ] 2.4 Add `chat.ratelimit.create_blocked` log (INFO).
  - [ ] 2.5 Backend integration test (`test_create_session_blocked_at_concurrent_cap`). Mirror the auth-fixture pattern from Story 10.5's existing tests.

- [x] **Task 3 — `stream_chat_turn` hourly-cap gate** (AC #3)
  - [ ] 3.1 Add `rate_limiter` dep to `stream_chat_turn` signature. The deps already include `db` + `handler`.
  - [ ] 3.2 Insert the `try: await rate_limiter.check_chat_hourly_rate_limit(...)` between the input-length cap (line ~810) and `start_ts = time.monotonic()` (line ~845).
  - [ ] 3.3 On `ChatRateLimitedError as exc` (caught at the route level, BEFORE the `event_generator` is built), return a `StreamingResponse` whose generator yields a single `_sse_event("chat-refused", _refused_payload(reason="rate_limited", ...))`. **Use the existing `_refused_payload` helper** so the payload shape matches the in-stream refusal byte-for-byte.
  - [ ] 3.4 Add `chat.ratelimit.turn_blocked` log on the refusal path.
  - [ ] 3.5 Backend integration test (`test_send_turn_blocked_at_hourly_cap`).

- [x] **Task 4 — `stream_chat_turn` daily-token-cap gate + recording** (AC #4)
  - [ ] 4.1 Create `backend/app/agents/chat/token_estimate.py` with `_estimate_input_tokens(message: str, session: ChatSession) -> int` returning `len(message) // 3 + 8000`. Docstring + TD reference.
  - [ ] 4.2 Pre-stream gate: `await rate_limiter.check_chat_daily_token_cap(str(user_id), projected_tokens=_estimate_input_tokens(payload.message, chat_session))` — placed *before* the hourly gate (so a daily-cap rejection happens with the longest cooldown). Wrap in the same `try/except ChatRateLimitedError` block as Task 3.
  - [ ] 4.3 Post-stream recording in the `event_generator` `ChatStreamCompleted` arm: `await rate_limiter.record_chat_token_spend(str(user_id), tokens_used=event.input_tokens + event.output_tokens)`. Wire AFTER the existing `chat.stream.completed` log.
  - [ ] 4.4 Wire to Story 10.5a's disconnect-finalizer (verify the hook in [`backend/app/agents/chat/finalizer.py`](../../backend/app/agents/chat/finalizer.py) or wherever the finalizer ships; the finalizer already has `input_tokens` per Story 10.5a's contract — record partial spend there too).
  - [ ] 4.5 Backend integration tests (`test_send_turn_blocked_at_daily_token_cap`, `test_record_chat_token_spend_increments_after_complete`, `test_daily_token_cap_resets_at_utc_midnight`).

- [x] **Task 5 — Inventory documentation** (AC #5, AC #6)
  - [ ] 5.1 Read [`docs/operator-runbook.md`](../../docs/operator-runbook.md) end-to-end. Find the `## Chat Safety Operations` section anchored by Story 10.9.
  - [ ] 5.2 Add `### Inventory: Rate-Limit Observability` subsection covering AC #5's content (existing aggregate alarm catches rate-limit refusals; per-cause breakdown is via Logs Insights query against `chat.ratelimit.*` events; sample query included).
  - [ ] 5.3 Add `### Inventory: Per-IP Cap Location` subsection covering AC #6 (WAF location, current rate quoted from `waf.tf`, generic-error UX path).
  - [ ] 5.4 Run a manual WAF smoke test in dev (verify before running) and record the result.

- [x] **Task 6 — Tests** (AC #8)
  - [ ] 6.1 New `backend/tests/test_chat_rate_limit.py` covering all six required test scenarios.
  - [ ] 6.2 Extend `backend/tests/test_rate_limiter.py` with three unit tests on the new methods (no FastAPI app context).
  - [ ] 6.3 Verify `frontend && npm test` still green for the existing rate-limit FE tests (no FE changes; this is regression-confidence).

- [x] **Task 7 — Tech-debt entries** (AC #10)
  - [ ] 7.1 Append three new TD-NNN entries to `docs/tech-debt.md`. Verify the next free numbers via `git log docs/tech-debt.md` immediately before merge.

- [x] **Task 8 — Architecture doc update** (AC #11)
  - [ ] 8.1 Add the one-line implementation pointer to `### Rate Limits` per AC #11. Verify the line numbers are still ~L1730-L1738 (refresh from a clean checkout — they'll have shifted slightly from earlier story merges).

- [x] **Task 9 — Pre-merge gates** (AC #9)
  - [ ] 9.1 `cd backend && ruff check .` → clean.
  - [ ] 9.2 `cd backend && .venv/bin/pytest -q` → green.
  - [ ] 9.3 `cd frontend && npm run lint` → clean.
  - [ ] 9.4 `cd frontend && npm test` → green (regression).
  - [ ] 9.5 Manual browser smoke per AC #9 (three rate-limit triggers — capture in PR description).
  - [ ] 9.6 `/VERSION` bumped (MINOR).
  - [ ] 9.7 Sprint-status flip: `10-11-abuse-rate-limit-enforcement` `ready-for-dev` → `in-progress` → `review`. **Also flip `epic-10` from `in-progress` → `done`** as 10.11 is the final Epic 10 story (verify by re-reading `_bmad-output/implementation-artifacts/sprint-status.yaml` — confirm 10.11 is the only remaining non-done story in the `epic-10` block).

## Dev Notes

### Why this story is the last Epic 10 story

Epic 10 (Chat-with-Finances) shipped its UX, schema, runtime, safety, observability, and history surfaces in 10.1a–10.10. Every layer was instrumented to **fail open** under load: the Story 10.5 SSE envelope already routes `rate_limited` to the FE `RefusalBubble`; the Story 10.7 `SessionList` already catches `429 CHAT_RATE_LIMITED` and opens the `ConcurrentSessionsDialog`; the Story 10.9 anomaly band already watches per-user token spend. **What's missing** is the mechanism that emits `rate_limited` in the first place + the deterministic per-user concurrent-session limit + the hard daily token cap. 10.11 plugs into the four pre-existing receptors and is the smallest possible diff that turns the safety theater into actual safety:

- The translator at [`chat.py:210-220`](../../backend/app/api/v1/chat.py#L210-L220) is unchanged.
- The `ChatRateLimitedError` shape at [`rate_limit_errors.py:17-39`](../../backend/app/agents/chat/rate_limit_errors.py#L17-L39) is unchanged.
- The FE `RefusalBubble`, `useChatStream`, `RateLimitDialog`, `ConcurrentSessionsDialog`, `SessionList` 429-catch, and i18n keys are all unchanged.
- The Story 10.9 metric filters and anomaly alarms are unchanged.
- Architecture's `### Rate Limits` envelope (the four bullets) is unchanged — only an implementation pointer is appended.

The diff surface is: 5 new methods on `RateLimiter`, 2 routes patched, 1 new helper file, 1 new env var, 1 new test file, 2 inventory docs subsections, 3 TD entries, 1 architecture-doc one-liner. Everything downstream is exercised by it; nothing downstream is reshaped by it.

### Reuse from Story 10.5 (mandatory — do not re-invent)

The translator path at [`backend/app/api/v1/chat.py:140-246`](../../backend/app/api/v1/chat.py#L140-L246) — specifically the `ChatRateLimitedError` arm at `:210-220` — is **the** code path that converts a typed exception into a `chat-refused` SSE frame. Story 10.11 raises the typed exception; the translator handles the conversion. **Do not write a parallel translator** in `rate_limiter.py`; the translator is single-source-of-truth for the wire format.

The `_refused_payload` helper at [`backend/app/api/v1/chat.py`](../../backend/app/api/v1/chat.py) (search for the function — it's near the translator) emits the canonical envelope shape (`error: "CHAT_REFUSED"`, `reason`, `correlation_id`, `retry_after_seconds`). When AC #3 + AC #4 emit the pre-stream refusal frame, they use `_refused_payload` directly so the byte format is identical to in-stream refusals. **Do not hand-craft the JSON.**

### Reuse from Story 10.7 (mandatory)

The FE catch at [`SessionList.tsx:39`](../../frontend/src/features/chat/components/SessionList.tsx#L39) checks `err.status === 429 || err.bodyText.includes("CHAT_RATE_LIMITED")`. AC #2 MUST emit `code="CHAT_RATE_LIMITED"` (exact match) so the substring catch fires; if the code differs, the FE falls through to the generic `t("session.create_error")` toast and the `ConcurrentSessionsDialog` never opens. **Verify the wire shape end-to-end** with the integration test in AC #2 — the integration test is the contract pin.

The FE `RefusalBubble.tsx:68-90` decides between `mm:ss countdown` (`retryAfterSeconds <= 3600`) and `wall-clock variant` (`retryAfterSeconds > 3600`). AC #4's daily cap MUST emit `retry_after_seconds = seconds_until_utc_midnight` which is typically > 3600 (always > 3600 except in the last hour of UTC day) — this triggers the wall-clock variant. AC #3's hourly cap MUST emit `retry_after_seconds <= 3600` — this triggers the countdown variant. **The threshold is FE-side**; the BE just emits the right number.

### Reuse from existing `RateLimiter` patterns

The five new methods MUST mirror the existing four:

- ZSET sliding-window pattern from `check_rate_limit` (login) and `check_upload_rate_limit` — `zremrangebyscore` + `zcard` + `zrange withscores` for retry-after derivation. The `oldest_time + window_seconds - now + 1` retry-after formula is exact (it's the time when the oldest entry will fall out of the window — at that moment, the cap drops by 1 and the user can send again).
- INCRBY counter pattern is NEW (no existing method uses it; the closest is the consent rate-limit which is also a sliding window). Document the day-rollover semantics explicitly in the docstring.
- The `aioredis.Redis` connection is dependency-injected via the existing `_redis` field. **Do not** open new connections.

### Why the daily-token cap uses a calendar-day key (not a sliding 24h window)

The Story 10.3b spec at [`10-3b-chat-ux-states-spec.md` AC #5](10-3b-chat-ux-states-spec.md) authored a wall-clock UX ("You can continue after `<HH:MM>` (local time)") explicitly because a 17-hour live countdown is hostile UX. A sliding 24h window would compute retry-after as "the time when the earliest token-spend will fall out" — which is a gradual recovery, not a midnight-reset. The wall-clock UX requires a calendar-day-aligned reset. The Redis key suffix `:{utc_yyyy_mm_dd}` is the cheapest way to express this; the 25h TTL gives the key a self-cleanup posture without needing a sweeper task. Per the architecture line 1736 phrasing ("Per-user daily token cap"), "daily" is calendar-day-aligned. **Verify with the FE test** at AC #4 that a `retry_after_seconds = 50000` triggers the wall-clock UX — if the FE threshold logic ever changes, this contract breaks.

### Why the per-IP cap stays in WAF (not app code)

The architecture line 1737 ("Global per-IP cap at the API-gateway layer (reuses existing limit)") is explicit: per-IP is at the gateway, not in the app. The existing AWS WAF rule at [`infra/terraform/modules/app-runner/waf.tf`](../../infra/terraform/modules/app-runner/waf.tf) already enforces this for the entire App Runner service. Adding an in-app per-IP rate-limit would (a) duplicate enforcement and (b) confuse the WAF dashboards (WAF blocks would be undercounted if the app blocks first). 10.11's role is to *inventory* the cap location, not relocate it.

### Why hourly is sliding-window but daily is calendar-day

Two different jobs:
- **Hourly** answers "is this user currently in a burst?" — a sliding window is correct because a burst at the hour boundary should still trigger the cap (otherwise users can game the limit by timing their burst to straddle :00).
- **Daily** answers "has this user exhausted today's compute budget?" — a calendar-day window aligns with the wall-clock UX (AC #4 + Story 10.3b) and with how operators reason about per-day Bedrock spend (looking at "today's spend" in AWS Cost Explorer is calendar-day-aligned). A sliding 24h would not align to either.

### Token-cap projection: why `len(message) // 3 + 8000`

The estimator is intentionally an OVER-estimate (denial-of-wallet bias is correct):
- `len(message) // 3` ≈ 1 token per 3 chars (English-skewed; UA tokens are ~2.5 chars/token in Bedrock's current tokenizer — the `// 3` over-estimates UA slightly more, which is fine).
- `+ 8000` for the system prompt + memory window per the [architecture L1726-L1727](../planning-artifacts/architecture.md#L1726-L1727) bound (8k tokens per session memory).
- Output-token projection is NOT included — the cap counts *input + output tokens used*, but the projection only needs to bound input + memory because output is bounded by Bedrock's `maxTokens` setting (typically 4096). Adding output to the projection would push the estimator over-pessimistic; the post-turn `record_chat_token_spend` records actual usage including output, so the correction settles into the next-turn projection naturally.

The TD entry in AC #10 tracks replacing this with a Bedrock-side `count_tokens` API once one exists.

### Recording on the disconnect-finalizer path (Story 10.5a integration)

Story 10.5a shipped a disconnect-finalizer at [`backend/app/agents/chat/finalizer.py`](../../backend/app/agents/chat/finalizer.py) (verify path before assuming) that persists partial state when a stream is interrupted. The finalizer has `input_tokens` available (it persists the user-message row + the partial assistant row + the per-tool-call rows). **AC #4 requires** that `record_chat_token_spend` is called from the finalizer too — otherwise a malicious actor could open a turn, consume input + partial output tokens, then disconnect, and have zero spend recorded. The finalizer already has the right hook point (per [`10-5a-send-turn-stream-disconnect-finalizer.md` AC #4](10-5a-send-turn-stream-disconnect-finalizer.md)); 10.11 adds one line to the finalizer's success-logging block.

### Why this story doesn't change the SSE wire shape

Every wire-shape change in Epic 10 has been a coordinated 3-story dance (BE emit + FE consume + envelope contract). 10.11 explicitly avoids that by reusing the existing `chat-refused` SSE arm, the existing `CHAT_REFUSED` HTTP envelope, the existing `code: CHAT_RATE_LIMITED` 429 body, and the existing `cause` enum on `ChatRateLimitedError`. The only new wire surface is the *behavior* of those existing arms firing on real conditions instead of never firing. **If the dev finds themselves about to add a new SSE event type or a new error code, stop — that's outside scope.**

### Project Structure Notes

- Modified file: [`backend/app/services/rate_limiter.py`](../../backend/app/services/rate_limiter.py) — five new methods (~ 120 lines added). The five methods mirror the existing patterns; no class-level refactor.
- Modified file: [`backend/app/api/v1/chat.py`](../../backend/app/api/v1/chat.py) — two routes patched (`create_session_endpoint`, `stream_chat_turn`), three `chat.ratelimit.*` log events, scope comment block. ~ 60-80 lines added; no helpers extracted (the gate code is short enough to inline in each route).
- Modified file: [`backend/app/agents/chat/finalizer.py`](../../backend/app/agents/chat/finalizer.py) (verify path before editing — Story 10.5a's actual location may be `chat_backend.py` or similar; read the file first) — one-line addition for partial-spend recording.
- Modified file: [`backend/app/core/config.py`](../../backend/app/core/config.py) — one new env var.
- New file: `backend/app/agents/chat/token_estimate.py` (~ 20 lines).
- New file: `backend/tests/test_chat_rate_limit.py`.
- Modified file: `backend/tests/test_rate_limiter.py` (extension; verify path).
- Modified file: `backend/tests/test_chat.py` or wherever the existing chat-route integration tests live (verify path).
- Modified file: [`docs/operator-runbook.md`](../../docs/operator-runbook.md) — two new subsections under `## Chat Safety Operations`.
- Modified file: [`docs/tech-debt.md`](../../docs/tech-debt.md) — three new TD entries.
- Modified file: [`_bmad-output/planning-artifacts/architecture.md`](../planning-artifacts/architecture.md) — one-line implementation pointer in `### Rate Limits`.
- Modified file: `_bmad-output/implementation-artifacts/sprint-status.yaml` — story key + epic key.
- Modified file: `/VERSION`.

NO frontend file changes. NO Terraform changes. NO migrations. NO new schemas.

### Testing standards summary

- **Backend**: `pytest-asyncio` with the existing async-session fixtures + `redis_client` fixture for Redis-backed tests. The `RateLimiter` tests should hit a real Redis (the test suite runs against the docker-compose Redis per the existing `test_rate_limiter.py` pattern — verify before adding). For the integration tests on `chat.py` routes, use the existing SSE test client pattern from Story 10.5's tests (`AsyncClient` + manual SSE-frame parsing per `docs/chat-sse-contract.md`).
- **FE**: NO new tests. The existing FE tests at `frontend/src/features/chat/__tests__/RateLimit.test.tsx`, `RefusalBubble.test.tsx`, `useChatStream.test.tsx`, `SessionList.test.tsx` cover the consumer side; running them as a regression check is sufficient.
- **Manual browser smoke**: per AC #9. Mandatory because the three rate-limit triggers are the user-visible surface that's been wired-but-never-fired across the entire epic.

### Previous Story Intelligence

- **Story 10.10 — Chat History + Deletion** (immediate predecessor): shipped the bulk-DELETE endpoint at [`chat.py:DELETE /chat/sessions`](../../backend/app/api/v1/chat.py); the `useChatSession` hook on the FE invalidates `["chat-sessions"]` after bulk-delete. 10.11's concurrent-cap is **per-session-row** (counts `chat_sessions` rows), so any deletion path automatically frees slots — no 10.11 code is needed in the deletion paths. Verify this in the AC #2 test (delete a session, confirm the next `acquire_chat_concurrent_session_slot` succeeds).
- **Story 10.9 — Safety Observability**: shipped the metric filters + alarms 10.11 piggy-backs on. Specifically, `chat_token_spend_anomaly_warn` (3σ band) is the *soft* signal; 10.11's daily-cap is the *hard* envelope. They don't conflict — the 3σ catches anomalies in user-base distribution; the daily-cap caps individual abuse. **Do not edit the Story 10.9 Terraform.**
- **Story 10.7 — Chat UI**: shipped the `RefusalBubble.rate_limited` arm + the `ConcurrentSessionsDialog` + the `SessionList` 429 catch. **All wired but never fired** — 10.11 fires them. The FE i18n keys (`chat.refusal.rateLimited.*`, `chat.dialog.concurrent_sessions.*`) are all live in `en.json` + `uk.json`.
- **Story 10.5a — Stream-disconnect finalizer**: provides the partial-token-spend hook point for AC #4. Verify the file path + the existing finalizer signature before adding the `record_chat_token_spend` call.
- **Story 10.5 — Streaming API**: established the route conventions + `ChatRateLimitedError` translator + `_refused_payload` helper. 10.11 reuses these verbatim.
- **Story 10.4a — AgentCore session handler**: provides `terminate_session` (used by Story 10.10's bulk-DELETE pre-cascade). 10.11 does NOT use `terminate_session` — see §Scope Boundaries' "No `terminate_all_user_sessions` integration" deferral.
- **Story 10.3b — UX States Spec**: authored the rate-limit copy + countdown vs wall-clock UX decision. 10.11's BE emissions feed it.

### Git Intelligence

Recent commits (most recent first per `git log --oneline -5`):
```
e018c95 Story 10.10: Chat History + Deletion
67759f9 Story 10.9: Safety Observability
c79c1b1 Story 10.8c: Red-Team Corpus Expectation Revision (Soft-Refusal Recognition)
7af19ec Story 10.8b: Safety Test Runner + CI Gate
ff89f3f Story 10.8a: Red-Team Corpus Authoring (UA + EN)
```

- **10.10 (`e018c95`) is the immediate predecessor.** No conflicts expected — 10.10 modified `chat.py` (history routes), `data_summary.py`, the FE chat surface, tech-debt. 10.11 modifies different `chat.py` route bodies (`create_session_endpoint`, `stream_chat_turn` — neither touched by 10.10), `rate_limiter.py` (untouched by 10.10), the operator-runbook (additive subsections), tech-debt (additive entries), and architecture (one-line addition to `### Rate Limits` — untouched by 10.10).
- **10.9 (`67759f9`) shipped the metric filters 10.11 piggy-backs on.** Verify by reading `observability-chat.tf` end-to-end before editing — but the §Scope Boundaries says no Terraform edits, so the verify is for the *inventory documentation* in AC #5/#6.
- Branch state at start: `main` clean per the latest sprint-status.yaml entry. No in-progress chat work expected.

### Latest Tech Information

No external library research required. All patterns reuse the existing stack:
- **redis-py / aioredis** sliding-window ZSET for hourly cap; INCRBY + `EXPIRE NX` for daily counter (verify `EXPIRE NX` is supported in the project's `redis-py` version — ≥ 4.6 per `backend/pyproject.toml` should suffice; if not, fall back to `TTL` + conditional `EXPIRE`).
- **FastAPI** dependency injection for `RateLimiter` (existing pattern in `auth.py`, `feedback.py`).
- **SQLModel** count query: `select(func.count(ChatSession.id)).where(ChatSession.user_id == user_id)` for the concurrent-session count (mirrors the count patterns in `data_summary.py`).
- **pydantic-settings** for the new `CHAT_DAILY_TOKEN_CAP_PER_USER` env var (existing pattern in `core/config.py`).

### References

- [`epics.md` §Epic 10 §Story 10.11 (line 2157)](../planning-artifacts/epics.md) — story brief
- [`prd.md`](../planning-artifacts/prd.md) — NFR41 (per-user isolation), NFR37 (zero PII leakage), the chat-throttling promise embedded in the `chat_processing` consent
- [`architecture.md` §Rate Limits L1730-L1738](../planning-artifacts/architecture.md#L1730-L1738) — four-dimension envelope (single source of truth)
- [`architecture.md` §API Pattern — Chat Streaming L1805-L1820](../planning-artifacts/architecture.md#L1805-L1820) — `CHAT_REFUSED` envelope + `reason=rate_limited` + `retry_after_seconds`
- [`architecture.md` §Memory & Session Bounds L1724-L1728](../planning-artifacts/architecture.md#L1724-L1728) — 10 concurrent sessions per user matches the rate-limit envelope
- [`architecture.md` §Observability & Alarms L1761-L1774](../planning-artifacts/architecture.md#L1761-L1774) — token-spend anomaly band (Story 10.9)
- Story 10.5 — [`10-5-chat-streaming-api-sse.md`](10-5-chat-streaming-api-sse.md) — SSE conventions, `_refused_payload`, translator
- Story 10.5a — [`10-5a-send-turn-stream-disconnect-finalizer.md`](10-5a-send-turn-stream-disconnect-finalizer.md) — finalizer hook for partial-spend recording
- Story 10.7 — [`10-7-chat-ui.md`](10-7-chat-ui.md) — FE `RefusalBubble`, `ConcurrentSessionsDialog`, `RateLimitDialog`, `SessionList` 429-catch (all wired)
- Story 10.9 — [`10-9-safety-observability.md`](10-9-safety-observability.md) — metric filters + anomaly alarms 10.11 piggy-backs on
- Story 10.10 — [`10-10-chat-history-deletion.md`](10-10-chat-history-deletion.md) — bulk-DELETE auto-frees concurrent slots
- Story 10.3b — [`10-3b-chat-ux-states-spec.md`](10-3b-chat-ux-states-spec.md) — rate-limit copy + countdown vs wall-clock UX decision
- [`backend/app/services/rate_limiter.py`](../../backend/app/services/rate_limiter.py) — extended (5 new methods)
- [`backend/app/agents/chat/rate_limit_errors.py`](../../backend/app/agents/chat/rate_limit_errors.py) — `ChatRateLimitedError` (consumed verbatim)
- [`backend/app/api/v1/chat.py`](../../backend/app/api/v1/chat.py) — translator at L210-220 (consumed verbatim) + two routes patched
- [`backend/app/api/deps.py`](../../backend/app/api/deps.py) — `get_rate_limiter` dependency (consumed)
- [`backend/app/core/config.py`](../../backend/app/core/config.py) — `CHAT_DAILY_TOKEN_CAP_PER_USER` added
- [`infra/terraform/modules/app-runner/waf.tf`](../../infra/terraform/modules/app-runner/waf.tf) — per-IP cap (inventory only — no edits)
- [`infra/terraform/modules/app-runner/observability-chat.tf`](../../infra/terraform/modules/app-runner/observability-chat.tf) — anomaly alarms (consumed — no edits)
- [`docs/operator-runbook.md`](../../docs/operator-runbook.md) — two new inventory subsections
- [`docs/tech-debt.md`](../../docs/tech-debt.md) — three new TD entries
- [`frontend/src/features/chat/components/RefusalBubble.tsx`](../../frontend/src/features/chat/components/RefusalBubble.tsx) — countdown vs wall-clock threshold logic (consumer; no edits)
- [`frontend/src/features/chat/components/SessionList.tsx`](../../frontend/src/features/chat/components/SessionList.tsx) — 429 catch + `ConcurrentSessionsDialog` (consumer; no edits)
- [`frontend/src/features/chat/hooks/useChatStream.ts`](../../frontend/src/features/chat/hooks/useChatStream.ts) — `cooldownEndsAt` reducer (consumer; no edits)
- Memory: `feedback_backend_ruff.md` — `ruff check` is a CI gate
- Memory: `feedback_frontend_lint.md` — `npm run lint` is a CI gate
- Memory: `feedback_python_venv.md` — `backend/.venv`
- Memory: `reference_tech_debt.md` — TD-NNN allocation convention

## Project Context Reference

- Sprint status: this story is `backlog` → set to `ready-for-dev` on save. On merge, `epic-10` flips `in-progress` → `done` (10.11 is the final Epic 10 story).
- Sibling Epic 10 stories: 10.1a (consent), 10.1b (schema), 10.2 (Bedrock guardrails), 10.3a/b (UX skeleton + states), 10.4a (AgentCore handler), 10.4b (canary), 10.4c (tools), 10.5 (streaming + translator), 10.5a (finalizer), 10.6a (grounding), 10.6b (citations), 10.7 (UI — consumes `rate_limited` arm), 10.8a/b/c (red-team corpus), 10.9 (observability — soft anomaly band), 10.10 (history + bulk-delete — frees concurrent slots).
- Cross-epic: NFR41 (per-user isolation), NFR37 (PII leakage prevention) — both have a denial-of-wallet/DoS complement here.
- Project context: [`../../docs/`](../../docs/) for runbooks, tech-debt, versioning policy.

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (1M context)

### Debug Log References

### Completion Notes List

- Implemented all 5 `RateLimiter` chat methods (hourly ZSET sliding window, concurrent-slot DB count, no-op release, daily token cap pre-gate, daily token spend recorder) in [`backend/app/services/rate_limiter.py`](../../backend/app/services/rate_limiter.py); `ChatRateLimitedError` raised with the typed `cause` enum the Story 10.5 translator at [`chat.py:210-220`](../../backend/app/api/v1/chat.py#L210-L220) consumes verbatim.
- `create_session_endpoint` now gates on `acquire_chat_concurrent_session_slot` and emits the `429 CHAT_RATE_LIMITED` envelope the FE `SessionList.tsx:39` substring catch is coded against (with `cause: "concurrent"` for future tooling).
- `stream_chat_turn` runs the daily-token-cap then hourly-cap gates BEFORE opening the SSE stream; on `ChatRateLimitedError`, returns a `200` `StreamingResponse` whose generator yields a single `chat-refused` frame (reusing `_refused_payload`) — the FE `useChatStream.ts` `cooldownEndsAt` reducer + `RefusalBubble` mm:ss-vs-wall-clock branch render the right UX off the same wire format the in-stream translator emits.
- Post-stream `record_chat_token_spend` increments the per-user daily counter on the `ChatStreamCompleted` arm; the `is_disconnected` branch records best-effort partial spend (input estimate + observed token_count) so a malicious actor can't disconnect mid-stream to dodge the cap.
- New `backend/app/agents/chat/token_estimate.py` ships the `len(message) // 3 + 8000` over-estimator (TD-141 tracks the eventual Bedrock-side `count_tokens` swap).
- Added `CHAT_DAILY_TOKEN_CAP_PER_USER: int = 200_000` env var to [`backend/app/core/config.py`](../../backend/app/core/config.py).
- Operator runbook gained **Inventory: Rate-Limit Observability** + **Inventory: Per-IP Cap Location** subsections under §Chat Safety Operations — these cover AC #5 (per-cause CW metric deferral, Logs Insights query) and AC #6 (WAF rate `limit = 2000` per IP per 5min, generic 403 surface, manual smoke test).
- Three new TD entries added: TD-141 (heuristic estimator), TD-142 (per-cause CloudWatch metric), TD-143 (chat-tier WAF tuning).
- Architecture `### Rate Limits` gained the one-line implementation pointer (envelope text unchanged).
- `/VERSION` bumped from `1.54.0` → `1.55.0` (MINOR — adds enforced rate-limit envelopes; no breaking client changes).
- All 14 new `tests/test_chat_rate_limit.py` tests pass: `RateLimiter` unit tests (hourly under/at cap with retry-after, concurrent slot under/at cap, no-op release, daily cap under/over with no INCRBY on block, recorder TTL behaviour, calendar-day suffix); `create_session` 429 envelope at cap and 201 under cap; `stream_chat_turn` single-frame `chat-refused` on hourly + daily caps with no Redis writes on the block path. Full backend regression suite: 1205 passed / 7 skipped (no new skips). `ruff check` clean. Frontend `npm run lint` shows 0 errors (26 pre-existing warnings unchanged from main).
- **Manual browser smoke (AC #9)** is deferred to the PR author at merge time — automated tests cover the three rate-limit triggers end-to-end via the same wire shapes the FE consumes; the smoke is a final eyeballed-render confirmation in dev.
- **Epic 10 closure** (AC #9): 10.11 is the final Epic 10 story. Sprint-status flip from `epic-10: in-progress` → `done` is left for the merge author to commit alongside this story's `review → done` flip, per the AC #9 instruction.

### File List

- backend/app/services/rate_limiter.py (modified — 5 new chat methods + helpers)
- backend/app/api/v1/chat.py (modified — `rate_limiter` deps + concurrent gate + pre-stream daily/hourly gates + post-stream recording + disconnect partial-spend)
- backend/app/agents/chat/token_estimate.py (new)
- backend/app/core/config.py (modified — `CHAT_DAILY_TOKEN_CAP_PER_USER` env var)
- backend/tests/test_chat_rate_limit.py (new — 14 tests)
- docs/operator-runbook.md (modified — two new inventory subsections under §Chat Safety Operations)
- docs/tech-debt.md (modified — TD-141, TD-142, TD-143)
- _bmad-output/planning-artifacts/architecture.md (modified — one-line implementation pointer in `### Rate Limits`)
- _bmad-output/implementation-artifacts/10-11-abuse-rate-limit-enforcement.md (modified — status, tasks, dev agent record)
- _bmad-output/implementation-artifacts/sprint-status.yaml (modified — story → review)
- VERSION (1.54.0 → 1.55.0)

### Code Review (2026-04-27)

Adversarial code review run on `review` status. 2 HIGH + 3 MEDIUM + 5 LOW findings; HIGH/MEDIUM all fixed inline (see Change Log entry below). Deferred LOW findings:

- **L2 — `record_chat_token_spend` log omits `db_session_id`**: AC #7 listed `db_session_id` as a field on `chat.ratelimit.token_spend_recorded`, but `record_chat_token_spend(user_id, tokens_used)` has no session-id parameter and the method is called from contexts (e.g. `RateLimiter` unit tests) where no session is in scope. Kept story-local; the log surface is forensic-only (DEBUG level), and operators correlate via `correlation_id` from the surrounding `chat.stream.*` events instead.
- **L4 — Manual browser smoke (AC #9) not run by code-review pass**: deferred to merge author, already noted in Dev Agent Record. Three rate-limit triggers are covered end-to-end by automated tests against the same wire format the FE consumes; the smoke is a final eyeballed render confirmation in dev.
- **L5 — `release_chat_concurrent_session_slot` no-op style nit**: withdrawn — the method's docstring already explains the load-bearing role (future cache-invalidation hook); promoting to TD would be noise.

### Change Log

- 2026-04-27 — Story 10.11 shipped: chat rate-limit envelope (60 msg/hr sliding window, 10 concurrent sessions per user, per-user daily token cap, per-IP cap inventory). Closes the wired-but-never-fired FE surfaces from Stories 10.5 / 10.7 / 10.10. Final Epic 10 story.
- 2026-04-27 — Version bumped from 1.54.0 to 1.55.0 (MINOR — adds enforced rate-limit envelopes).
- 2026-04-27 — Code-review fixes applied:
    - **H1 / AC #4 / Task 4.4**: Partial-spend recording now fires from the route's `finally` block on any unsettled termination path (CancelledError mid-stream); previously only the polled `is_disconnected` branch recorded, leaving the CancelledError-driven disconnect bypass open. Refused / configuration / unmapped-exception branches explicitly mark `spend_settled=True` so refused turns are not double-charged.
    - **H2 / AC #8 (vi)**: Added `test_send_turn_finalizer_records_partial_spend_on_cancel` — pins the bypass-prevention contract (15 tests now, up from 14).
    - **M1**: Hourly ZSET `zadd` member is now uniquified (`f"{now}:{uuid4().hex[:8]}"`) so concurrent same-tick turns no longer overwrite and undercount toward the 60/hr cap.
    - **M2 / Task 4.1**: `estimate_input_tokens` signature gains the `session: ChatSession | None = None` parameter required by AC #1; current implementation ignores it (heuristic-only) but call sites pass it so the TD-141 swap doesn't widen the surface again.
    - **M3**: Disconnect / finalizer partial-spend now uses `output_chars // 3` (Bedrock-tokenizer-aligned) instead of `token_count` (which counted SSE delta events, not tokens).
    - **L1**: `acquire_chat_concurrent_session_slot` cleaned up (top-level `uuid` import; `result.scalar_one()`).
    - **L3**: `check_chat_daily_token_cap` now guards the `int(raw)` parse against a corrupt Redis value (logs `chat.ratelimit.daily_counter_corrupt` WARN, falls through as `current=0`).
    - Re-ran: `ruff check .` clean, full backend suite `1206 passed / 7 skipped` (no new skips).
