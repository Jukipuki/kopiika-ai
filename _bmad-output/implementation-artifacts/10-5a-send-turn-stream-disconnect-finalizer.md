# Story 10.5a: `send_turn_stream` Disconnect Finalizer + Canary Scan on Error Paths

Status: done

<!-- Closes TD-108 (HIGH) and TD-109 short-term (HIGH). TD-109 medium-term (rolling-window canary matcher) remains open. -->

## Story

As a **platform engineer responsible for the Epic 10 chat audit-trail and canary-leak alarms**,
I want **`ChatSessionHandler.send_turn_stream` to (1) wrap Steps 4–6 in an outer `try/finally` with a `_finalized` gate so that a client disconnect mid-stream still persists `accumulated_text` as an assistant row + any tool rows + bumps `last_active_at` (TD-108), and (2) always run `scan_for_canaries(accumulated_text, canaries)` from that same outer `finally` — including on the `ChatGuardrailInterventionError`, `ChatTransientError`, and `GeneratorExit` paths — emitting `chat.canary.leaked` ERROR with the canary-set version and persisting a `guardrail_action='blocked'` row when a canary slipped through (TD-109 short-term)** —
so that **Story 10.9's `chat.stream.disconnected` distribution and `chat.canary.leaked` Sev-2 alarm both report on the full population of partial writes (not the happy-path-only subset they see today), the AC #14 invariant 4 contract — *"a client disconnect does NOT skip persistence"* — actually holds in the DB, and the canary exfiltration vector through error-path short-circuits is closed at the audit layer before the wire-gating rolling-window matcher (TD-109 medium-term) is built.**

## Scope Boundaries

This story is a **surgical fix** to one method (`ChatSessionHandler.send_turn_stream` at [backend/app/agents/chat/session_handler.py:546-862](../../backend/app/agents/chat/session_handler.py#L546-L862)). Explicit deferrals — **must not** ship here:

- **No rolling-window canary matcher (TD-109 medium-term).** A streaming-aware canary scan that gates the *wire* (not just the DB) — scanning each delta + a trailing overlap of `max(canary_length)-1` chars and stopping the stream on match — is a separate story (≈ 1 day, requires a new incremental matcher API alongside the current atomic `scan_for_canaries`). 10.5a closes the audit-trail + alarm gap; the wire-gate gap is tracked separately. **The `accumulated_text` already streamed to the client is NOT clawed back** — the UI's "refusal frames discard in-flight tokens" contract from Story 10.5 AC #4 + 10.3b still does the per-session mitigation; 10.5a's job is to make sure the leak *fires the alarm* and *persists the blocked row*.
- **No refactor of `send_turn` (the non-streaming variant).** `send_turn` already has straight-line persistence — it has no analogue of the GeneratorExit problem because there is no iterator for the caller to abandon. Touching `send_turn` would risk regressing 10.4a/b/c's tests for zero benefit. The shared private helpers extracted by Story 10.5 (`_persist_user_turn`, `_load_canaries_and_prompt`, `_maybe_summarize_context`, `_persist_tool_rows_and_assistant`, `_scan_and_handle_canaries`) stay unchanged in signature and behavior.
- **No changes to `ChatBackend.invoke_stream` or `DirectBedrockBackend.invoke_stream`.** The disconnect-detection seam is at the *handler* layer (where the `async for backend_event` loop runs) and at the *API* layer (`request.is_disconnected()` + `agen.aclose()`). The backend is a passive producer — it streams until cancelled. No new backend method, no new event type.
- **No changes to the SSE wire contract or the `ChatStreamEvent` dataclass set.** `ChatStreamCompleted` is still only yielded on the happy path; the finalizer-driven persist on disconnect does NOT yield a synthetic `ChatStreamCompleted` (the peer is gone). The API-layer `chat.stream.disconnected` log already exists and does not change.
- **No changes to `chat.stream.*` log namespace, field set, or alarm wiring.** The `chat.canary.leaked` event already exists at [session_handler.py:790-801](../../backend/app/agents/chat/session_handler.py#L790-L801) on the happy-path Step 5 branch — 10.5a re-emits it from the outer `finally` with the *same* field set. Story 10.9 owns the metric filter + alarm; 10.5a does not preempt that wiring.
- **No changes to the API layer (`backend/app/api/v1/chat.py`).** The fix is entirely inside `send_turn_stream`. The API's existing `await agen.aclose()` at [chat.py:691](../../backend/app/api/v1/chat.py#L691) already fires the `GeneratorExit` that drives the new finalizer; no SSE-layer changes are required.
- **No new tests beyond the ones AC #5 enumerates.** The existing 10.5 tests at `backend/tests/agents/chat/test_send_turn_stream.py` and `backend/tests/api/test_chat_routes.py` continue to pass unchanged; 10.5a *adds* finalizer-path tests, does not modify existing ones.

A one-line scope comment at the top of the modified `send_turn_stream` method enumerates the above so the next engineer does not accidentally expand scope into the wire-gate work.

## Acceptance Criteria

1. **Given** `ChatSessionHandler.send_turn_stream` at [backend/app/agents/chat/session_handler.py:546-862](../../backend/app/agents/chat/session_handler.py#L546-L862), **When** this story lands, **Then** Steps 4 → 5 → 6 (the `async for backend_event` loop, the canary scan, and the assistant-row + tool-row persistence) are wrapped in a single outer `try: ... finally:` block with a local `_finalized = False` flag declared immediately *before* the `try`. The four existing terminal paths set `_finalized = True` at the end of their persistence-and-commit sequences, **before** the `raise`:
   - End of happy-path Step 6 (after `await db.commit()` at [session_handler.py:830](../../backend/app/agents/chat/session_handler.py#L830), before the `tool_call_count = ...` accounting block).
   - End of the `ChatPromptLeakDetectedError` branch (after `await db.commit()` at [session_handler.py:789](../../backend/app/agents/chat/session_handler.py#L789), before the `logger.error("chat.canary.leaked", ...)` call — the log is part of the terminal sequence and should fire before `_finalized` flips so a finalizer-driven re-scan does not double-emit on the same `accumulated_text`).
   - End of the `(ChatToolLoopExceededError, ChatToolNotAllowedError, ChatToolAuthorizationError)` branch (after `await db.commit()` at [session_handler.py:701](../../backend/app/agents/chat/session_handler.py#L701), before the per-exception `logger.error(...)` and `raise`).
   - End of the `ChatGuardrailInterventionError` branch (after `await db.commit()` at [session_handler.py:754](../../backend/app/agents/chat/session_handler.py#L754), before the `exc.correlation_id = correlation_id` stamp and `raise`).
   - The `_finalized = True` assignments are **the last DB-touching statements** in each branch — if a `db.commit()` itself raises, `_finalized` stays `False` and the outer `finally` re-attempts persistence (best-effort, see AC #4).

2. **Given** the outer `finally` block, **When** it runs with `_finalized is False`, **Then** the finalizer executes the following sequence (a unified late-write path that handles disconnect, `GeneratorExit`, server-shutdown `asyncio.CancelledError`, and any unanticipated exception that escapes Steps 4–6 *outside* the four terminal branches above):
   - **Step F.1 — canary scan on accumulated text (TD-109 short-term).** If `accumulated_text` is non-empty, call `scan_for_canaries(accumulated_text, canaries)` inside its own `try/except`. On `ChatPromptLeakDetectedError` (`exc_canary`):
     - Persist a `ChatMessage(role='assistant', content=accumulated_text, guardrail_action='blocked', redaction_flags={"filter_source": "canary_detector", "canary_slot": exc_canary._matched_position_slot, "canary_prefix": exc_canary.matched_canary_prefix})` row.
     - Emit `logger.error("chat.canary.leaked", extra={...})` with the **identical field set** to the happy-path Step 5 emission ([session_handler.py:790-801](../../backend/app/agents/chat/session_handler.py#L790-L801)) — `correlation_id`, `db_session_id`, `canary_slot`, `canary_prefix`, `canary_set_version_id`, `output_char_len`, `output_prefix_hash` — **plus one additional field** `finalizer_path: bool = True` to let Story 10.9's CloudWatch Insights query distinguish happy-path vs. error-path leak emissions for the leak-rate dashboard. Operator triage gets richer signal; the alarm threshold (Sev-2) is unchanged.
     - The `ChatPromptLeakDetectedError` is **NOT re-raised** from the finalizer — the finalizer's contract is best-effort persistence, not exception propagation (see AC #4). The original exception that triggered the finalizer (e.g. `GeneratorExit`, `ChatGuardrailInterventionError`) is the one Python re-raises out of the `finally`.
   - **Step F.2 — assistant-row persistence on the no-canary disconnect path.** If F.1 found NO canary AND `accumulated_text` is non-empty, persist a `ChatMessage(role='assistant', content=accumulated_text)` row (no `guardrail_action`, no `redaction_flags` — this is a clean partial write, distinguishable from the happy-path final state only by the absence of a corresponding `ChatStreamCompleted` SSE frame on the wire, which is exactly the AC #14 invariant 4 spec).
   - **Step F.3 — tool-row persistence.** Iterate `tool_results` (the local list populated by the `BackendToolHop` handler at [session_handler.py:665](../../backend/app/agents/chat/session_handler.py#L665)) and persist each as a `ChatMessage(role='tool', content=_serialize_tool_call(tc), guardrail_action='none' if tc.ok else 'blocked', redaction_flags={...})` row. The serialization helpers are **identical** to the four existing terminal-branch persistence blocks; no new helper is authored. **Important:** because the four terminal branches each persist `tool_results` *themselves*, the finalizer only runs Step F.3 when none of those branches ran (i.e. `_finalized is False`) — so there is **no double-write risk** on `tool_results`.
   - **Step F.4 — `last_active_at` bump.** `await db.exec(sa_update(ChatSession).where(ChatSession.id == handle.db_session_id).values(last_active_at=_now()))` followed by `await db.commit()`. This matches the pattern at [session_handler.py:826-829](../../backend/app/agents/chat/session_handler.py#L826-L829).
   - The four sub-steps run in sequence inside a single `try: ... except Exception: pass` envelope (AC #4). The `_finalized = True` flip happens at the end of the successful finalizer path (so a `finally`-block exception cannot leave `_finalized` ambiguous if downstream code grows a check for it — defensive but cheap).

3. **Given** the `_finalized` gate flag and the canary re-scan inside the finalizer, **When** the four existing terminal branches run their persistence-and-commit sequences before flipping `_finalized = True`, **Then** the finalizer's Step F.1 canary re-scan **is skipped** for those branches (because `_finalized is True` short-circuits the entire finalizer body). The happy-path Step 5 canary scan at [session_handler.py:768-770](../../backend/app/agents/chat/session_handler.py#L768) and the existing `ChatPromptLeakDetectedError` branch at [session_handler.py:771-802](../../backend/app/agents/chat/session_handler.py#L771-L802) remain the **single source of truth** for canary handling on those paths. The finalizer's scan is **only** the safety net for the three short-circuiting paths the existing code does not cover today: (a) `GeneratorExit` from `agen.aclose()` on client disconnect, (b) `ChatGuardrailInterventionError` raised on a *trailing* chunk after deltas have already streamed, (c) `ChatTransientError` (Bedrock throttle) raised mid-stream.
   - For path (b), this is a behavior **change**: the existing `ChatGuardrailInterventionError` branch persists `tool_results` but does NOT scan `accumulated_text` for canaries (it does not even reference `accumulated_text` — see [session_handler.py:731-766](../../backend/app/agents/chat/session_handler.py#L731-L766)). After 10.5a, a Guardrail intervention on a trailing chunk that *also* contained a canary the model emitted earlier in the stream will fire `chat.canary.leaked` ERROR + persist a `guardrail_action='blocked'` assistant row in addition to the existing intervention persistence. The two persistence sequences MUST NOT both write an assistant row — to enforce this, the `ChatGuardrailInterventionError` branch is amended to flip `_finalized = True` *only when no `accumulated_text` was streamed* (i.e. `if not accumulated_text: _finalized = True`); when `accumulated_text` is non-empty, the branch persists tool rows + bumps `last_active_at` + raises **without** flipping `_finalized`, allowing the finalizer to do the canary scan + assistant-row persistence. Concretely: the `_finalized = True` line in the intervention branch is conditional on `not accumulated_text`. The `tool_results` persistence in that branch is moved *inside* the same conditional so the finalizer's Step F.3 is the single writer for `tool_results` when the finalizer takes over. **Test coverage:** AC #5 (vi).

4. **Given** the finalizer is best-effort by contract (it must not mask the original exception that triggered it — `GeneratorExit`, `asyncio.CancelledError`, `ChatGuardrailInterventionError`, `ChatTransientError`), **When** any DB operation inside the finalizer raises, **Then** the exception is caught and logged but **not** re-raised. The implementation:
   ```python
   finally:
       if not _finalized:
           try:
               # F.1, F.2, F.3, F.4 sequence
               ...
               _finalized = True
           except Exception as exc_finalizer:  # noqa: BLE001
               logger.error(
                   "chat.stream.finalizer_failed",
                   extra={
                       "correlation_id": correlation_id,
                       "db_session_id": str(handle.db_session_id),
                       "error_class": type(exc_finalizer).__name__,
                       "error_message": str(exc_finalizer)[:200],
                       "accumulated_char_len": len(accumulated_text),
                       "tool_results_count": len(tool_results),
                   },
               )
   ```
   - The `chat.stream.finalizer_failed` event is a **new** ERROR-level structured log — it should never fire in steady state. It surfaces a class of bug (e.g. DB connection pool exhausted exactly at disconnect time) that would otherwise be invisible. Story 10.9 will add a Sev-2 alarm on this event count > 0 over a 5-minute window. The 200-char truncation on `error_message` matches the existing convention at [session_handler.py:608](../../backend/app/agents/chat/session_handler.py#L608).
   - The bare `Exception` catch is intentional and `noqa`'d — the finalizer must survive arbitrary downstream failures (DB driver errors, asyncio shutdown races, SQLAlchemy session-state bugs) to honor the "must not mask original exception" contract. `BaseException` (which would catch `GeneratorExit` / `KeyboardInterrupt` / `SystemExit`) is **NOT** caught; those propagate normally.
   - The `try/finally` is **not** a `try/except/else/finally` — there is no `else` branch. The finalizer cares only about whether `_finalized is True` at the moment it runs, not about how the body exited.

5. **Given** the test contract (pattern matches the existing `backend/tests/agents/chat/test_send_turn_stream.py` from Story 10.5), **When** this story lands, **Then** the following **new** tests are added to that file (one block per finalizer scenario) and pass:
   - **(i) Disconnect mid-token-stream → assistant row persisted.** Mock `ChatBackend.invoke_stream` to yield 3× `BackendTokenDelta(text="hello ")` then *never terminate* (use an `asyncio.Future` that is never set so the iterator hangs). Drive `send_turn_stream` to first delta, then call `agen.aclose()` from the test (simulates the API layer's response to `request.is_disconnected()`). Assert: `chat_messages` contains exactly one `role='assistant'` row with `content='hello hello hello '`, `guardrail_action` is the column default (NOT `'blocked'`), `redaction_flags` is NULL. `chat_sessions.last_active_at` bumped. No `ChatStreamCompleted` was yielded. No `chat.canary.leaked` log fired.
   - **(ii) Disconnect mid-stream with a canary in `accumulated_text` → blocked row + leaked log.** Same setup as (i) but the canned deltas include the active canary string. Assert: `chat_messages` contains exactly one `role='assistant'` row with `guardrail_action='blocked'`, `redaction_flags['filter_source'] == 'canary_detector'`, `redaction_flags['canary_slot']` and `redaction_flags['canary_prefix']` populated. The `chat.canary.leaked` ERROR log fired exactly once with `finalizer_path=True` in `extra`. `chat_sessions.last_active_at` bumped. No `ChatStreamCompleted` was yielded.
   - **(iii) `ChatGuardrailInterventionError` on trailing chunk with prior `accumulated_text` → finalizer persists.** Mock `ChatBackend.invoke_stream` to yield 2× `BackendTokenDelta(text="some text")` then raise `ChatGuardrailInterventionError(intervention_kind="content_filter", trace_summary="...")` on the next iteration. Assert: the intervention exception propagates out of `send_turn_stream` (the *caller* — API layer — sees the original exception). `chat_messages` contains one `role='assistant'` row with `content='some textsome text'`, `guardrail_action` is the column default if no canary in the deltas (or `'blocked'` if a canary was embedded — exercise both sub-cases). `chat.stream.guardrail_intervened` INFO log STILL fires from the existing intervention branch; `chat.canary.leaked` fires only in the canary-embedded sub-case. `chat_sessions.last_active_at` bumped exactly once (the existing branch's bump is moved inside the conditional per AC #3, so the finalizer is the sole bumper when `accumulated_text` is non-empty).
   - **(iv) `ChatGuardrailInterventionError` with empty `accumulated_text` → existing branch wins.** Mock `ChatBackend.invoke_stream` to raise `ChatGuardrailInterventionError(intervention_kind="denied_topic")` on the FIRST iteration (no deltas streamed). Assert: behavior is **unchanged** from pre-10.5a — no assistant row written, partial tool rows persisted (none in this test, the loop never produced one), `chat_sessions.last_active_at` bumped, exception re-raised. The `_finalized = True` conditional flip happened, and the finalizer's `if not _finalized:` short-circuited to no-op. **This is the regression-pin test for the existing intervention branch.**
   - **(v) `ChatTransientError` mid-stream after partial deltas → finalizer persists.** Mock `ChatBackend.invoke_stream` to yield 2× `BackendTokenDelta` then raise `ChatTransientError("Bedrock throttle")`. Assert: `ChatTransientError` propagates out of `send_turn_stream`. `chat_messages` contains a `role='assistant'` row with the accumulated content. `chat_sessions.last_active_at` bumped. `chat.canary.leaked` does not fire (no canary in the deltas).
   - **(vi) Happy-path turn → finalizer no-ops.** The existing happy-path test from Story 10.5 — re-run as-is — must still pass. Add an explicit assertion that `chat.stream.finalizer_failed` was NOT logged (regression pin against the finalizer accidentally running on the success path).
   - **(vii) Finalizer DB failure → `chat.stream.finalizer_failed` logged, original exception propagates.** Disconnect mid-stream as in (i), but patch `db.commit` (or the `sa_update(ChatSession)` exec call) to raise `RuntimeError("db pool exhausted")` on the finalizer's call. Assert: `chat.stream.finalizer_failed` ERROR log fires with `error_class='RuntimeError'` and `accumulated_char_len > 0`. The original `GeneratorExit` (or whatever triggered the disconnect) propagates out — NOT the `RuntimeError`.
   - **(viii) Existing `ChatPromptLeakDetectedError` happy-path — regression pin.** Re-run the existing test (iv) from Story 10.5's `test_send_turn_stream.py` (`ChatPromptLeakDetectedError raised after stream drains`). Assert no behavior change: `chat.canary.leaked` fires exactly once (NOT twice — the finalizer must short-circuit because the existing branch flipped `_finalized`).
   - **(ix) Existing `ChatToolLoopExceededError` happy-path — regression pin.** Re-run existing test (v). Assert no behavior change; finalizer short-circuits.
   - **Coverage:** ≥ 90% on the modified `send_turn_stream` method (existing 10.5 coverage target preserved). Run with `pytest backend/tests/agents/chat/test_send_turn_stream.py -q --cov=backend/app/agents/chat/session_handler --cov-report=term-missing`. Debug Log records the command output and the per-line coverage delta vs. pre-10.5a.

6. **Given** the API-layer integration tests at `backend/tests/api/test_chat_routes.py` (Story 10.5 AC #11), **When** this story lands, **Then** test (xiv) — *"Client disconnect mid-stream (simulated by cancelling the TestClient response iterator) → `chat.stream.disconnected` log emitted; DB state consistent with AC #5's invariant"* — is **strengthened** with two additional assertions:
   - After the disconnect, query `chat_messages` for the session and assert: exactly one `role='assistant'` row exists with `content` equal to the concatenation of the deltas the test received before cancelling, AND `chat_sessions.last_active_at` was bumped by the finalizer (compare to the pre-stream timestamp). This is the **end-to-end** verification that AC #14 invariant 4 holds across the full HTTP boundary, not just at the handler unit-test boundary.
   - The pre-10.5a behavior of test (xiv) — that the disconnect log fires — is **preserved**; only the assertions about DB state are added. The test's name does not change.
   - No new test file is created. The existing test is amended in place; the diff is recorded in the Debug Log.

7. **Given** the tech-debt register at [docs/tech-debt.md](../../docs/tech-debt.md), **When** this story lands, **Then**:
   - **TD-108** moves from the active register to the `## Resolved` section with a single-paragraph resolution note: `### TD-108 — send_turn_stream client-disconnect finalizer does not persist partial state [RESOLVED 2026-04-25 — Story 10.5a]`. Resolution body: lists the four `_finalized = True` insertion points + the outer `finally` Steps F.1–F.4, and the test IDs from AC #5 (i)–(vii) that pin the contract. Cross-references the commit hash of the 10.5a merge.
   - **TD-109** is **updated in place** in the active register — its short-term fix is **closed** (struck through under "Fix shape:" with a "✅ shipped in Story 10.5a (2026-04-25), see AC #2 Step F.1 + AC #5 (ii)" annotation), and the entry's title is amended to `### TD-109 — Canary scan does not gate partial token stream — wire-gate only [HIGH]` (drops "(only gates DB commit)" since the DB commit gap is now closed). The `Why deferred` paragraph is rewritten to reflect that only the rolling-window matcher / wire-gate work remains. Effort line is updated to drop the `Short-term ~2h;` segment, leaving `Effort: ~1 day` for the medium-term work.
   - The `## Resolved` insertion for TD-108 follows the existing chronological-newest-first convention at the top of that section (placed **above** the existing `### TD-081` entry).
   - Dev agent greps `docs/tech-debt.md` for any other `TD-.*108` or `TD-.*109` cross-references and updates them inline — known sites: the TD-109 "Fix shape" bullet that says "in the outer `finally` (see TD-108)" is rewritten to past tense and points to Story 10.5a's commit. Records grep output in Debug Log.

8. **Given** the code-comment block at the top of `send_turn_stream` (lines 524-544 in [session_handler.py](../../backend/app/agents/chat/session_handler.py#L524-L544)), **When** this story lands, **Then** invariant (4) — *"a client disconnect does NOT skip persistence — the caller is responsible for draining the iterator even on cancel; the API layer honors this via the FastAPI StreamingResponse pattern"* — is **rewritten** to reflect the new finalizer-driven mechanism:
   ```
   (4) a client disconnect does NOT skip persistence — Steps 4–6 are
       wrapped in an outer try/finally with a _finalized gate. The four
       terminal branches (happy-path, canary-leak, tool-abort, guardrail-
       intervention) each flip _finalized=True before raising; the finally
       runs the late-write path (canary re-scan + assistant row + tool
       rows + last_active_at bump) only when _finalized is False. This
       handles GeneratorExit (client disconnect via agen.aclose()),
       asyncio.CancelledError (server shutdown), and any unanticipated
       exception. The finalizer is best-effort (its own try/except
       Exception → chat.stream.finalizer_failed log) and never masks
       the original exception. See Story 10.5a (TD-108 + TD-109 short-
       term resolution).
   ```
   - Invariants (1)–(3) are **unchanged**.
   - One additional invariant (5) is appended:
   ```
   (5) the canary scan ALSO runs from the outer finally on the
       GeneratorExit / ChatGuardrailInterventionError(non-empty
       accumulated_text) / ChatTransientError paths, emitting
       chat.canary.leaked ERROR with finalizer_path=True. This is the
       audit-layer safety net for canaries that slip past the happy-
       path Step 5 scan due to mid-stream short-circuits. The wire-gate
       (rolling-window matcher) remains TD-109 medium-term.
   ```

9. **Given** the architecture document at [_bmad-output/planning-artifacts/architecture.md](../planning-artifacts/architecture.md), **When** this story lands, **Then** **no architecture amendment is required**. The L1802-L1815 §API Pattern — Chat Streaming contract is silent on the finalizer mechanism (it is an implementation detail of the handler, not a wire contract). The `correlation_id` audit-trail invariant at L1815 is *strengthened* by 10.5a (more turns reach the DB with their `correlation_id`-stamped rows) but the prose itself is already correct. No ADR is required — this is bug-fix scope, not an architectural decision.

10. **Given** the `chat.stream.*` log namespace registered with Story 10.9, **When** the new `chat.stream.finalizer_failed` ERROR event is added, **Then** Story 10.9's metric-filter authoring backlog is amended to include this event:
    - A note is added to the active TD-NNN entry tracking Story 10.9's pre-implementation event inventory (or a fresh TD-NNN opens if no such inventory exists yet — dev agent greps `docs/tech-debt.md` for `Story 10.9` or `chat.stream` and decides; records in Debug Log).
    - The event's intended alarm: **Sev-2 on count > 0 over a 5-minute window**. Rationale: the event represents a *post-disconnect persistence failure* — a class of audit-trail violation that is invisible to the user but breaks the AC #14 invariant 4 contract. Sev-2 (vs. Sev-1) reflects that no user-facing flow is broken; an operator should investigate within business hours.
    - The `finalizer_path` boolean field added to `chat.canary.leaked` (per AC #2 Step F.1) is also flagged for Story 10.9's CloudWatch Insights query — a per-`finalizer_path` breakdown lets the leak-rate dashboard distinguish "model emitted canary on happy path" (model alignment regression) from "model emitted canary mid-stream + something short-circuited" (could indicate adversarial prompt successfully steering toward error path).

11. **Given** the test execution standard, **When** the story is marked done, **Then** the full chat test suite plus the API integration tests run green:
    ```
    pytest backend/tests/agents/chat/ backend/tests/api/test_chat_routes.py -q --cov=backend/app/agents/chat/session_handler --cov-report=term-missing
    ```
    Coverage on `session_handler.py` is **≥** the post-Story-10.5 baseline (no regression). Debug Log records the command output, the line count covered before vs. after, and any newly-uncovered lines (with rationale or follow-up TD).

## Tasks / Subtasks

- [x] **Task 1: Wrap Steps 4–6 in outer `try/finally` with `_finalized` gate** (AC: #1, #3)
  - [x] 1.1 Add `_finalized = False` local immediately before the existing Step-4 `try:`.
  - [x] 1.2 Wrap Steps 4–6 in an outer `try: ... finally:` — internal try/except branches preserved.
  - [x] 1.3 Insert `_finalized = True` at the four terminal-branch sites after `await db.commit()`.
  - [x] 1.4 Amend `ChatGuardrailInterventionError` branch per AC #3 — `_finalized` + tool_results + bump are now conditional on `not accumulated_text`.

- [x] **Task 2: Implement outer `finally` finalizer body** (AC: #2, #4)
  - [x] 2.1 `if not _finalized:` + inner `try/except Exception:` envelope.
  - [x] 2.2 F.1 canary re-scan with `finalizer_path=True` on `chat.canary.leaked`.
  - [x] 2.3 F.2 clean-assistant-row persist on the no-canary path.
  - [x] 2.4 F.3 tool-row persist (no new helper — reuses `_serialize_tool_call`).
  - [x] 2.5 F.4 `last_active_at` bump + commit.
  - [x] 2.6 `chat.stream.finalizer_failed` ERROR log + terminal `_finalized = True` flip.

- [x] **Task 3: Tests** (AC: #5, #6, #11)
  - [x] 3.1 Added tests (i)–(viii) plus an existing-tool-loop regression pin (ix). The pre-10.5a `test_guardrail_intervention_grounding_no_assistant_row` was rewritten as the (iii) test — its prior assertion ("no assistant row" with non-empty `accumulated_text`) directly contradicts AC #3's behavior change, so a literal "do not modify existing test" reading is impossible. The (iv) regression pin covers the empty-`accumulated_text` path.
  - [ ] 3.2 Disconnect API test (xiv) — **DEFERRED → tracked as TD-110**. The original test (xiv) referenced by AC #6 was never authored in Story 10.5 (the file's existing tests cover (i)–(xiii) shapes only; no disconnect test exists). httpx's `ASGITransport` does NOT propagate client-disconnect signals into FastAPI's `request.is_disconnected()` reliably (verified empirically — a `client.stream(...)` early-break does not flip the flag), so an in-process test cannot exercise the disconnect path end-to-end without a real socket. The handler-unit tests (i), (ii), (vii) cover the finalizer's DB-state contract directly; the API-layer wire-up of `agen.aclose()` was already verified by Story 10.5's review fixes. Real-socket disconnect E2E (uvicorn + raw TCP client) is now tracked as **TD-110** in [docs/tech-debt.md](../../docs/tech-debt.md).
  - [x] 3.3 Full suite green: `pytest backend/tests/agents/chat/ backend/tests/api/test_chat_routes.py -q --cov=app.agents.chat.session_handler --cov-report=term-missing` → **187 passed, 3 skipped**, **91% coverage on `session_handler.py`** (305 stmts, 28 missing) — above the AC #11 ≥90% threshold. Missing lines are all outside 10.5a scope: `send_turn` non-streaming branches (407, 416-418), `_summarize_and_rebuild_context` summarization sub-paths (617-627, 741-751, 773, 948), `terminate_all_user_sessions` fail-open path (1078-1098).

- [x] **Task 4: Update inline invariant comment block** (AC: #8)
  - [x] 4.1 Invariant (4) rewritten per AC #8.
  - [x] 4.2 Invariant (5) appended.
  - [x] 4.3 Invariants (1)–(3) unchanged.

- [x] **Task 5: Tech-debt register update** (AC: #7, #10)
  - [x] 5.1 TD-108 moved to `## Resolved` (placed above the existing TD-081 entry).
  - [x] 5.2 TD-109 updated in place — short-term ✅ struck through, title amended to "wire-gate only", `Why deferred` rewritten, `Effort` reduced to "~1 day".
  - [x] 5.3 Cross-references: the only in-file cross-ref was TD-109's "see TD-108" bullet, which is now strikethrough-annotated with the 10.5a pointer.
  - [x] 5.4 Story-10.9 event inventory: amended TD-099 in place — added the `finalizer_path` dimension on `chat.canary.leaked` and a new sev-2 alarm on `chat.stream.finalizer_failed` (per AC #10 rationale).

- [x] **Task 6: Confirm no API-layer changes required** (AC: scope)
  - [x] 6.1 Verified [backend/app/api/v1/chat.py:485-525](../../backend/app/api/v1/chat.py#L485-L525) (`is_disconnected` loop) and [chat.py:679-693](../../backend/app/api/v1/chat.py#L679-L693) (`finally → agen.aclose()`). `await agen.aclose()` at chat.py:691 is the `GeneratorExit`-trigger; the new finalizer runs from there. No API-layer change required.

## Dev Notes

### Architecture Patterns and Constraints

- **The finalizer is a handler-internal mechanism, not a wire contract.** No new SSE event type, no new `ChatStreamEvent` dataclass, no new public API on `ChatSessionHandler`. The fix is a local refactor of one ~250-line method.
- **Best-effort semantics are load-bearing.** The Python language guarantees that a `finally` block runs on `GeneratorExit` and `asyncio.CancelledError`; the contract this story relies on is that the handler's `finally` block can do DB I/O before re-raising. Async DB drivers (asyncpg via SQLAlchemy 2.x async) honor this — but only because we do NOT catch `BaseException`. Catching `BaseException` would swallow the cancellation signal and hang the FastAPI `StreamingResponse` cleanup. AC #4's bare-`Exception` catch is the correct envelope.
- **The `_finalized` flag — vs. an enum or a state machine — is intentional.** A boolean is sufficient because the finalizer has only two states (run-the-late-write or skip). A richer state machine would be premature and would invite the next engineer to add new states without thinking about the disconnect path. If a future story needs to discriminate between disconnect-vs.-server-shutdown-vs.-other in the late-write path, the cleanest extension is a separate `disconnect_reason: Literal[...] | None` local — not an expansion of `_finalized`.
- **The behavior change in the `ChatGuardrailInterventionError` branch (AC #3) is the riskiest part of this story.** Pre-10.5a, that branch is the sole owner of persistence on intervention. Post-10.5a, ownership splits based on whether `accumulated_text` was streamed before the intervention fired. The split is correct — Bedrock can intervene on the trailing chunk *after* the model has already emitted (potentially canary-bearing) text — but it is a behavior change. AC #5 (iii) and (iv) are the regression pins; both MUST pass before merge.
- **TD-109 medium-term remains open.** The wire-gate (rolling-window canary matcher) is the durable fix for mid-stream exfil; 10.5a closes only the audit-layer + alarm gap. The TD-109 entry in `docs/tech-debt.md` continues to track the wire-gate work; trigger condition is unchanged: any `chat.canary.leaked` event in prod, OR Story 10.8a red-team corpus exercising mid-stream canary exfil.

### Source Tree Components to Touch

- [backend/app/agents/chat/session_handler.py](../../backend/app/agents/chat/session_handler.py) — `send_turn_stream` method (the surgical change). Lines 524–862 are the complete touch surface; no other module is modified.
- [backend/tests/agents/chat/test_send_turn_stream.py](../../backend/tests/agents/chat/test_send_turn_stream.py) — add tests per AC #5.
- [backend/tests/api/test_chat_routes.py](../../backend/tests/api/test_chat_routes.py) — strengthen test (xiv) per AC #6.
- [docs/tech-debt.md](../../docs/tech-debt.md) — TD-108 → resolved, TD-109 updated in place per AC #7.

### Testing Standards Summary

- **Unit-level** (handler): `pytest backend/tests/agents/chat/test_send_turn_stream.py -q` — must pass with the new tests added and the existing tests unmodified.
- **Integration** (API + DB): `pytest backend/tests/api/test_chat_routes.py -q` — test (xiv) strengthened in place, no new test file.
- **Full chat surface** (regression): `pytest backend/tests/agents/chat/ backend/tests/api/test_chat_routes.py -q` — green.
- **Coverage target** (per AC #11): no regression on `session_handler.py` line coverage vs. post-10.5 baseline. The new finalizer branches MUST be covered by AC #5 tests (i), (ii), (iii), (v), (vii).
- **No new dependency.** Existing `pytest-asyncio` + `aiosqlite` (test fixture DB) cover everything.

### Project Structure Notes

- **Alignment with unified project structure:** the change stays within `backend/app/agents/chat/session_handler.py` — the same module Story 10.4a created and Story 10.5 extended. No new file. No new module-level export.
- **Detected conflicts or variances:** none. The `_finalized` flag is a local; no naming collision with anything else in the file (grep confirms zero hits for `_finalized` in `backend/`).

### References

- [Source: docs/tech-debt.md#TD-108 (lines 1648-1665)](../../docs/tech-debt.md#L1648-L1665) — the canonical problem statement and fix shape.
- [Source: docs/tech-debt.md#TD-109 (lines 1669-1685)](../../docs/tech-debt.md#L1669-L1685) — the canary-scan-on-error-paths short-term fix being bundled.
- [Source: _bmad-output/implementation-artifacts/10-5-chat-streaming-api-sse.md AC #14 (lines 222-227)](10-5-chat-streaming-api-sse.md) — the invariant being enforced; specifically invariant 4 ("a client disconnect does NOT skip persistence").
- [Source: _bmad-output/implementation-artifacts/10-5-chat-streaming-api-sse.md AC #2 + AC #5](10-5-chat-streaming-api-sse.md) — the parent story's `send_turn_stream` contract that 10.5a is repairing.
- [Source: backend/app/agents/chat/session_handler.py:644-862](../../backend/app/agents/chat/session_handler.py#L644-L862) — the method body being modified.
- [Source: backend/app/api/v1/chat.py:485-525, 680-693](../../backend/app/api/v1/chat.py#L485-L525) — the `is_disconnected` + `agen.aclose()` sites that drive the new finalizer (read-only — out of scope to modify).
- [Source: backend/app/agents/chat/canary.py — `scan_for_canaries` + `ChatPromptLeakDetectedError`](../../backend/app/agents/chat/canary.py) — the atomic canary-scan API the finalizer reuses verbatim.

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (1M context) — 2026-04-25.

### Debug Log References

- **Task 6.1 (API-layer scope):** confirmed `await agen.aclose()` at [backend/app/api/v1/chat.py:691](../../backend/app/api/v1/chat.py#L691) inside `event_generator`'s `finally` is the GeneratorExit trigger. The route's `is_disconnected()` poll at chat.py:507 returns from `event_generator`, the outer `finally` cancels `anext_task` and `aclose()`s the agen — fires `GeneratorExit` into the handler's outer `try/finally`. No API change.
- **Task 3.3 (full suite + coverage):** `pytest backend/tests/agents/chat/ backend/tests/api/test_chat_routes.py -q --cov=app.agents.chat.session_handler --cov-report=term-missing` → **187 passed, 3 skipped**. Coverage on `session_handler.py`: **91%** (305 stmts, 28 missing) — above the AC #11 ≥90% threshold. Missing lines are all outside 10.5a scope: `send_turn` non-streaming branches (407, 416-418), `_summarize_and_rebuild_context` summarization sub-paths (617-627, 741-751, 773, 948), `terminate_all_user_sessions` fail-open path (1078-1098). All eight new finalizer tests + the pre-10.5a regression pins covered. Tooling notes: `pytest-cov 5.0.0` + `coverage 7.9.2` work cleanly; `numpy 2.4.4` triggered `ImportError: cannot load module more than once per process` under coverage tracing, downgraded to `numpy<2.4` (resolved to 2.3.5) to unblock — pgvector still emits a benign `UserWarning: The NumPy module was reloaded` under coverage which can be silenced via filter if it becomes noisy in CI.
- **Task 5.3 (cross-ref grep):** `grep -n 'TD-108\|TD-109' docs/tech-debt.md` → only in-file references were the TD-108 entry itself and TD-109's `Why deferred` + `Fix shape` bullets. TD-109's "see TD-108" bullet is now strikethrough-annotated with the 10.5a pointer.
- **Task 5.4 (event-inventory tracking decision):** TD-099 (existing entry that already pins the `chat.canary.leaked` metric-filter contract for Story 10.9) was the natural home for the new `chat.stream.finalizer_failed` event + the `finalizer_path` dimension. Extended TD-099 in place rather than opening a new TD — preserves the single canonical Story-10.9 inventory entry.
- **Test (iii) reconciliation:** the pre-10.5a `test_guardrail_intervention_grounding_no_assistant_row` test asserted "no assistant row written" with `BackendTokenDelta(text='partial')` followed by a guardrail intervention. AC #3 explicitly changes that contract — non-empty `accumulated_text` on intervention now delegates persistence to the finalizer, which writes an assistant row. The story's "existing tests pass unchanged" boundary contradicts AC #3 directly for this case, so the existing test was rewritten to match the new (iii) contract; AC #5 (iv) covers the regression-pin behavior for the empty-`accumulated_text` path.
- **Test (xiv) deferral:** httpx `ASGITransport` does not propagate client-disconnect signals into FastAPI's `request.is_disconnected()` poll under `client.stream(...)` early-break or context-manager exit. Empirically verified: an attempted in-process disconnect test ran the stream to completion (5-second `asyncio.sleep` interleaved between deltas, client broke after first chunk) without `chat.stream.disconnected` ever firing. A real-socket E2E (uvicorn + raw TCP) is the right shape; out of scope for 10.5a since the handler-unit tests (i)/(ii)/(vii) cover the contract directly and the API wire-up was already verified by Story 10.5's review fixes.

### Completion Notes List

- Wrapped `ChatSessionHandler.send_turn_stream` Steps 4–6 in an outer `try/finally` with a `_finalized` gate. The four terminal branches (happy-path, tool-abort, canary-leak, guardrail-intervention) each flip `_finalized = True` after `await db.commit()`. The intervention branch's `_finalized` flip + persistence are conditional on empty `accumulated_text`; with prior streamed text the branch raises without flipping, delegating to the finalizer.
- Implemented finalizer body: F.1 canary re-scan with `finalizer_path=True` on `chat.canary.leaked`, F.2 clean assistant-row persist on no-canary path, F.3 tool-row persist (reusing `_serialize_tool_call`), F.4 `last_active_at` bump + commit. Best-effort envelope: any in-finalizer exception logs `chat.stream.finalizer_failed` and is swallowed so the original `GeneratorExit` / `ChatGuardrailInterventionError` / `ChatTransientError` propagates.
- Eight new tests in `test_send_turn_stream.py` (i)–(viii) per AC #5 plus an inherited (ix) regression pin from the pre-existing tool-loop test. The (iii) test rewrites the pre-10.5a `test_guardrail_intervention_grounding_no_assistant_row` to match AC #3's behavior change.
- `chat.canary.leaked` now distinguishes happy-path (Step 5, no `finalizer_path` field) vs error-path (finalizer F.1, `finalizer_path=True`) emissions for Story 10.9's leak-rate dashboard.
- `chat.stream.finalizer_failed` is a new ERROR-level event covered by AC #4 and pinned by Story 10.9 in the amended TD-099 — sev-2 alarm on `count > 0` over 5 min.
- TD-108 moved to `## Resolved` in `docs/tech-debt.md`; TD-109 short-term struck through (medium-term wire-gate stays open).
- VERSION bumped 1.46.0 → 1.46.1 (PATCH per `docs/versioning.md` — bug-fix / hardening, no new user-facing feature).
- AC #6 (API-layer disconnect test) deferred with rationale in Debug Log; the unit-level (i)/(ii)/(vii) tests cover the contract.
- AC #11 coverage verified: **91% on `session_handler.py`** (305 stmts, 28 missing — all outside 10.5a scope). Required `pytest-cov 5.0.0` + downgrading `numpy` from 2.4.4 → 2.3.5 to bypass numpy's module-reload guard under coverage tracing.

### File List

- `backend/app/agents/chat/session_handler.py` (modified — finalizer + `_finalized` gate; invariants (4) rewritten + (5) appended)
- `backend/tests/agents/chat/test_send_turn_stream.py` (modified — eight new tests, (iii) replaces the pre-10.5a intervention-no-assistant test, autouse `app` logger propagation fixture for caplog)
- `docs/tech-debt.md` (modified — TD-108 → Resolved, TD-109 short-term closed, TD-099 amended for the new event + `finalizer_path` dimension)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (modified — `10-5a-...: ready-for-dev` → `review`)
- `_bmad-output/implementation-artifacts/10-5a-send-turn-stream-disconnect-finalizer.md` (modified — Status, Tasks, Dev Agent Record, Change Log)
- `VERSION` (modified — `1.46.0` → `1.46.1`)

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-04-25 | Story created (TD-108 + TD-109 short-term scope). | Planning |
| 2026-04-25 | Implemented `_finalized`-gated outer `try/finally` + finalizer body in `send_turn_stream`; added eight finalizer-path tests; updated tech-debt register; VERSION 1.46.0 → 1.46.1. AC #6 (API-layer disconnect test) deferred — see Debug Log. | Dev (claude-opus-4-7) |
| 2026-04-25 | Code review (`bmad-bmm-code-review`): fixed H2 (finalizer F.2/F.3 ordering inverted relative to happy path — swapped so tool rows precede the assistant row; pinned by new `test_finalizer_persists_tool_rows_before_assistant_row`); H1 (Task 3.2's silent deferral promoted to TD-110 in `docs/tech-debt.md`, checkbox unchecked); M1 (test (vii) now asserts `agen.aclose()` returns `None` to pin the bare-`Exception` envelope against future `BaseException` regressions); M2 (added canary-embedded sub-case `test_intervention_with_prior_accumulated_text_canary_embedded` per AC #5 (iii)); M3 (trimmed three narrative comment blocks in `send_turn_stream` that duplicated AC text). Full chat suite: 189 passed, 3 skipped. | Reviewer (claude-opus-4-7) |
