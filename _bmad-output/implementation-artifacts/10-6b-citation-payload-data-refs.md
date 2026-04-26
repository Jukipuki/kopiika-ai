# Story 10.6b: Citation Payload + Data Refs in API

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **platform engineer shipping Epic 10's grounded-chat contract (FR68: "Chat responses include citations back to the underlying data … when making data-specific claims")**,
I want **(1) a backend "citation assembler" that reads the `role='tool'` rows persisted by Story 10.4c for the turn just completed, projects each tool's payload into a typed `Citation` value, deduplicates across rows, and returns an ordered tuple of citations attached to the assistant's response; (2) a new `ChatCitationsAttached` stream event surfaced as a new `chat-citations` SSE frame emitted after the final `chat-token` and before `chat-complete`; (3) `ChatTurnResponse` (the non-streaming `send_turn` return) extended with the same `citations` tuple so both transports share one shape; and (4) a documented JSON contract for the four citation kinds (`transaction`, `category`, `profile_field`, `rag_doc`) with field-level types, deduplication keys, and label-rendering rules — exposed in [docs/chat-sse-contract.md](../../docs/chat-sse-contract.md) under a new `chat-citations` section** —
so that **Story 10.7's chat UI has a single, stable wire contract to render citation chips against (the layout slot already pinned by Story 10.3a §Citation Chip Row), Story 10.6a's grounding measurement gains a per-turn artefact ("did the model's claim actually reference any of the data the tools returned?") that future iterations of the harness can score against, and the architecture's FR68 line stops being aspirational prose and becomes a wire-level invariant a downstream test can pin.**

## Scope Boundaries

This story is the **server-side citation contract** + **wire-format extension** that closes the citation hand-off declared by Stories 10.3a, 10.4c, 10.5, and 10.5a. Explicit deferrals — **must not** ship here:

- **No frontend chip rendering.** Story 10.7 owns the `chat-citations` consumption: chip-row layout, detail-panel content, click-to-expand, mobile horizontal-scroll. 10.6b emits the payload and pins the contract; 10.7 binds it to the DOM. The UX layout slot (chip row position + detail-panel dismiss key) is already locked by [ux-design-specification.md L1646-L1657](../planning-artifacts/ux-design-specification.md#L1646-L1657).
- **No new database column, no Alembic migration.** Citations are **derived at assembly time** from the existing `role='tool'` rows persisted by Story 10.4c (see [session_handler.py:462-475](../../backend/app/agents/chat/session_handler.py#L462-L475)). The `chat_messages.content` JSON already carries the full `ToolResult.payload`; the assembler reads it back. No schema change keeps this story low-risk and reversible. Story 10.10 (chat history) will re-run the assembler on history fetch so the contract is identical for live + replayed turns.
- **No model-emitted inline citation markers (`[^1]`-style).** This is the simplest contract that satisfies FR68: *every* identifier the agent's tools returned during the turn becomes a citation, in tool-call invocation order. We do **not** require the model to mark which sentence cited which row. Inline markers are a future enhancement tracked under TD-NNN (see AC #11) — they need prompt-engineering + grounding-harness changes that are out of scope here.
- **No system-prompt change.** The 10.4b hardened prompt already instructs the model to "ground your answer in the data the tools return". Adding "and produce inline `[^N]` markers" would be a behavior-affecting change that invalidates Story 10.6a's baseline grounding measurement. Out of scope; TD entry below.
- **No new tools, no schema changes to existing tool outputs.** The four 10.4c tool output models (`GetTransactionsOutput`, `GetProfileOutput`, `GetTeachingFeedOutput`, `SearchFinancialCorpusOutput`) are read **as-is**. If a tool's output is structurally insufficient to build a useful citation (it isn't — verified field-by-field below), the fix is in 10.4c, not here.
- **No grounding-rate change, no Guardrail re-tune.** Citations are a **rendering contract**, not a grounding signal. Story 10.6a's `grounding_rate` metric is unaffected. The chat-grounding eval harness (Story 10.6a, [`backend/tests/eval/chat_grounding/`](../../backend/tests/eval/chat_grounding/)) does not consume citations — its judge scores on source content, not on chip count.
- **No `CHAT_REFUSED` reason enum change.** Citations attach **only** on the happy path (assistant final text persisted, no refusal). Refused / errored turns emit no `chat-citations` frame — chip strip is suppressed per [ux-design-specification.md L1803](../planning-artifacts/ux-design-specification.md#L1803) ("Citation chips do not render on refusal variants"). The wire contract already permits this — `chat-citations` is **optional** and **additive**.
- **No CloudWatch metric on citation count.** Story 10.9 owns observability authorship for chat. 10.6b emits a structured-log line (`chat.citations.attached`) so 10.9 can metricify later without code change here.
- **No teaching-feed-row citations.** Although 10.4c's `get_teaching_feed` is one of the four read-only tools, the chat UX surfaces teaching-feed content as a redirect ("re-open card X in your feed") rather than as a citable claim — see [10-4c AC #4](10-4c-tool-manifest-read-only.md): *"the model asks the user to re-open the card in the teaching feed rather than relay; this is a deliberate scope compression."* Therefore the assembler **drops** teaching-feed rows from the citation list (they are not user-facing citable evidence in chat). This is documented inline in the assembler module and in the contract doc.
- **No PII redaction inside citations.** Bedrock Guardrails output PII filter (Story 10.5) already runs on the assistant text. Citation payloads carry only fields the tool already chose to emit (transaction descriptions are pass-through per [10-4c AC #2](10-4c-tool-manifest-read-only.md), bank IBANs are not in any tool output, RAG snippets are pre-truncated to 500 chars). The assembler **does not** re-run PII detection.
- **No Phase-B `AgentCoreBackend` work.** Citation assembly is backend-agnostic: it reads `chat_messages` rows, not in-memory backend state. Phase B (TD-094) will inherit the contract automatically. No coupling to `DirectBedrockBackend` is introduced here.

A one-line scope comment at the top of the new `citations.py` module enumerates the above so a future engineer does not accidentally expand scope.

## Acceptance Criteria

1. **Given** a new module at `backend/app/agents/chat/citations.py` (sibling of `canary_detector.py` / `memory_bounds.py`), **When** the module is authored, **Then** it exposes exactly this public surface:

   ```python
   CITATION_CONTRACT_VERSION: str = "10.6b-v1"  # bump on shape changes

   class CitationKind(StrEnum):
       transaction = "transaction"
       category = "category"
       profile_field = "profile_field"
       rag_doc = "rag_doc"

   class TransactionCitation(BaseModel):
       kind: Literal["transaction"] = "transaction"
       id: uuid.UUID                      # Transaction.id
       booked_at: date
       description: str
       amount_kopiykas: int                # signed
       currency: str                       # ISO code
       category_code: str | None
       label: str                          # short render hint, e.g. "Coffee Shop · 2026-03-14"

   class CategoryCitation(BaseModel):
       kind: Literal["category"] = "category"
       code: str                           # Category.code (e.g. "groceries")
       label: str                          # human-friendly title (en/uk localized later by 10.7)

   class ProfileFieldCitation(BaseModel):
       kind: Literal["profile_field"] = "profile_field"
       field: str                          # one of: monthly_income_kopiykas, monthly_expenses_kopiykas, savings_ratio, health_score
       value: int | None
       currency: str | None                # populated for monetary fields, None for ratios/scores
       as_of: date
       label: str                          # "Monthly expenses (Apr 2026)"

   class RagDocCitation(BaseModel):
       kind: Literal["rag_doc"] = "rag_doc"
       source_id: str                      # CorpusDocRow.source_id (e.g. "en/emergency-fund")
       title: str
       snippet: str                        # first 240 chars of the tool's snippet (the tool already capped at 500)
       similarity: float                   # 0..1
       label: str                          # title (the chip-visible string)

   Citation = TransactionCitation | CategoryCitation | ProfileFieldCitation | RagDocCitation

   def assemble_citations(tool_calls: Sequence[ToolResult]) -> tuple[Citation, ...]: ...

   def citation_to_json_dict(c: Citation) -> dict: ...
   ```

   - `assemble_citations` is a **pure function** of the `tool_calls` tuple — no DB session, no I/O, no logger. Determinism + testability are the contract; persistence + logging happen one layer up in `session_handler`. It accepts `Sequence[ToolResult]` (the runtime type at the call site) but the body re-validates each `ToolResult.payload` against the corresponding tool's pydantic output model so a malformed/legacy row from 10.10 history-replay does not poison the assembler.
   - `CITATION_CONTRACT_VERSION` is exported from `backend/app/agents/chat/__init__.py` and added to the `chat.turn.completed` log field set (AC #6) so Story 10.9 can slice citation behavior by contract-version bumps. Bump the version on **any** shape change to the four citation models or to the dedup keys.
   - `citation_to_json_dict` is the canonical serializer used by both transport paths (the SSE event-to-dict mapper in `stream_events.py` and the `ChatTurnResponse` JSON serializer if/when 10.6b adds a non-streaming route). It produces snake_case keys at the boundary; the API layer's `to_camel` alias does the wire conversion (matches the 10.5 / 10.4c convention).
   - **No state, no class.** The module is a function library. A frozen-dataclass or pydantic posture would invite "let's add a `Citation.from_payload()` constructor", which mixes concerns; the deliberate shape is `assemble_citations(tool_calls)` returns `tuple[Citation, ...]` and that is the only public verb.

2. **Given** the four 10.4c tool output models, **When** `assemble_citations` projects them, **Then** it follows this **exact** projection map (the contract doc in AC #10 mirrors this table verbatim):

   | Source tool | Source field path | Citation kind | Per-row citations produced |
   |---|---|---|---|
   | `get_transactions` | `payload.rows[*]` | `TransactionCitation` (one per row) + at most one `CategoryCitation` per **distinct** `category_code` across all rows | one TX citation per row; categories deduped across the *whole turn* |
   | `get_profile` | `payload.summary.{monthly_income_kopiykas, monthly_expenses_kopiykas, savings_ratio, health_score}` | `ProfileFieldCitation` (one per *non-None* field) | up to 4 per profile call; only non-None fields cite |
   | `get_profile` | `payload.category_breakdown[*].category_code` | `CategoryCitation` (deduped against transaction-derived categories) | one per breakdown row, deduped |
   | `get_teaching_feed` | — | (none) | dropped per Scope Boundaries; assembler logs `chat.citations.dropped` DEBUG with `tool_name="get_teaching_feed"` and `row_count` |
   | `search_financial_corpus` | `payload.rows[*]` | `RagDocCitation` (one per row) | one per row; deduped by `source_id` across the turn |

   - **Failed tool calls (`ok=False`)** are skipped silently — error rows are not citable evidence. The dispatcher already logs `chat.tool.blocked` (10.4c AC #10); the citation assembler does not re-log them.
   - **Dedup keys** (used to suppress duplicates within one turn):
     - `TransactionCitation`: `("transaction", id)` — UUID equality
     - `CategoryCitation`: `("category", code)` — code equality
     - `ProfileFieldCitation`: `("profile_field", field, as_of)` — same field on the same `as_of` date dedupes (a single turn making the same get_profile call twice should not produce two chips)
     - `RagDocCitation`: `("rag_doc", source_id)` — source_id equality (multiple matched chunks of the same doc collapse to one chip)
   - **Order of emission** is **stable** and deterministic: outer iteration is `tool_calls` index order (10.4c invocation order, already preserved by series-execution); inner iteration is row index within each tool's payload. Dedup keeps the *first* occurrence; subsequent matches drop. This keeps the chip-row order matching the model's most-likely sentence-to-citation alignment without requiring inline markers.
   - **Cap:** at most **20 citations per turn**. If `assemble_citations` is about to exceed, it **truncates and emits one** structured-log line `chat.citations.truncated` WARN with `pre_truncate_count`, `kept_count=20`, `dropped_count`. The cap is a defense-in-depth against a model that fans out 5 transactions × 200 = 1000 rows → 1000 chips; the chip strip cannot meaningfully render that anyway. The cap is a module-level constant `MAX_CITATIONS_PER_TURN = 20` — greppable, not env-overridable. The cap order respects the dedup-keep-first rule (kinds are not reordered by truncation; rag_docs and profile fields are not preferentially preserved over transactions).
   - **Label-rendering rules** (locked here so 10.7 only formats; it does not invent):
     - `TransactionCitation.label` = f"{description[:40]} · {booked_at.isoformat()}" (40-char description cap, no ellipsis — the chip is a teaser; the detail panel shows the full row).
     - `CategoryCitation.label` = `code.replace("_", " ").title()` (e.g. `"groceries" → "Groceries"`, `"transfers_p2p" → "Transfers P2P"`). Localization is 10.7's concern; the assembler emits canonical English and 10.7 maps to UA copy via the existing `chat-refused` copy-map pattern.
     - `ProfileFieldCitation.label` = a fixed mapping from `field` → render template; e.g. `"monthly_expenses_kopiykas" → f"Monthly expenses ({as_of.strftime('%b %Y')})"`. The four field-template entries live in a module-level dict and are unit-tested for stability.
     - `RagDocCitation.label` = `title` (verbatim).

3. **Given** a new internal stream event `ChatCitationsAttached` in [`backend/app/agents/chat/stream_events.py`](../../backend/app/agents/chat/stream_events.py), **When** the file is amended, **Then**:
   - A new frozen dataclass is appended (pattern matches the existing five):
     ```python
     @dataclass(frozen=True)
     class ChatCitationsAttached:
         """Emitted on the happy path AFTER the final ChatTokenDelta and BEFORE
         ChatStreamCompleted. Empty tuple = no citations on this turn (the API
         layer skips emitting a chat-citations frame in that case)."""
         citations: tuple  # tuple[Citation, ...]
     ```
   - The `ChatStreamEvent` union is extended with `ChatCitationsAttached`.
   - `event_to_json_dict` adds a `kind: "citations_attached"` arm that calls `citation_to_json_dict` per element. Its dict shape:
     ```json
     {"kind": "citations_attached", "citations": [<citation_dict>, ...]}
     ```
   - `__all__` is extended with `ChatCitationsAttached`.
   - The module-level `# Non-goals` comment block has its `Citation payloads → Story 10.6b` line **deleted** (10.6b lands now); replace with a forward-pointing line: `Inline citation markers ([^N]) → TD-NNN follow-up`.

4. **Given** the streaming pipeline `ChatSessionHandler.send_turn_stream` at [`session_handler.py:562`](../../backend/app/agents/chat/session_handler.py#L562), **When** this story extends it, **Then**:
   - Immediately **after** the canary scan on accumulated final text passes (Step 5 success path, before `ChatStreamCompleted` is yielded — the existing happy-path branch in the streaming handler), call `citations = assemble_citations(result.tool_calls)`.
   - If `len(citations) > 0`, yield exactly one `ChatCitationsAttached(citations=citations)` event before `ChatStreamCompleted`. If empty, yield nothing — the API layer translates "no event" to "no `chat-citations` SSE frame".
   - Citations are **not** persisted to a new column. They are derived from the already-persisted `role='tool'` rows by the same `assemble_citations(tool_calls)` call; on history-replay (Story 10.10), the same function rebuilds them by reading those rows back as `ToolResult` instances. (Story 10.10's read path will need a small `_tool_call_from_chat_message_row(row) -> ToolResult` adapter; that adapter is **not** authored here — 10.10 owns it. 10.6b's contract is "given a sequence of `ToolResult`, here are the citations".)
   - **Refusal and error paths are unchanged.** `ChatGuardrailInterventionError`, `ChatPromptLeakDetectedError`, `ChatToolLoopExceededError`, `ChatToolNotAllowedError`, `ChatToolAuthorizationError`, `ChatTransientError`, and `ChatConfigurationError` all propagate without yielding `ChatCitationsAttached`. The chip strip is intentionally absent on refusal — UX contract from 10.3b.
   - The streaming handler's outer-finally finalizer (10.5a) does **not** emit citations. If a client disconnects mid-stream, the assistant row may persist (per 10.5a) but no `chat-citations` frame ever flushed — that is correct; the next history-replay (10.10) will re-derive them.
   - One new INFO log emitted on the happy path: `chat.citations.attached` with fields `correlation_id`, `db_session_id`, `citation_count`, `citation_kinds_histogram` (e.g. `{"transaction": 3, "category": 2, "rag_doc": 1}`), `truncated` (bool), `contract_version` (`CITATION_CONTRACT_VERSION`).

5. **Given** the non-streaming pipeline `ChatSessionHandler.send_turn` at [`session_handler.py:241`](../../backend/app/agents/chat/session_handler.py#L241), **When** this story extends it, **Then**:
   - `ChatTurnResponse` (the dataclass at [`session_handler.py:155`](../../backend/app/agents/chat/session_handler.py#L155)) gains one field: `citations: tuple = field(default_factory=tuple)  # tuple[Citation, ...]`.
   - In Step 6 (assistant row persistence), after the canary scan passes and after the `db.commit()`, call `assemble_citations(result.tool_calls)` and assign to the response. Same INFO log as AC #4 fires (`chat.citations.attached`). On any refusal path, `citations=()` and no log.
   - `send_turn` is currently called by the chat-grounding eval harness only ([test_chat_grounding_harness.py](../../backend/tests/eval/chat_grounding/test_chat_grounding_harness.py)), not by any user-facing API route. No public route changes are required for `send_turn`; the contract surface is the `ChatTurnResponse` dataclass. The harness asserts in its existing `test_send_turn_returns_citations_when_tools_called` (new test, AC #9) that `citations` is well-formed when tools fired.

6. **Given** the API layer at [`backend/app/api/v1/chat.py:462-694`](../../backend/app/api/v1/chat.py#L462-L694) (the SSE generator), **When** this story extends it, **Then**:
   - A new event-name handler is added in the inner `while True` loop (between the `ChatTokenDelta` arm at [L559](../../backend/app/api/v1/chat.py#L559) and the `ChatStreamCompleted` arm at [L576](../../backend/app/api/v1/chat.py#L576)):
     ```python
     if isinstance(event, ChatCitationsAttached):
         yield _sse_event(
             "chat-citations",
             {
                 "citations": [
                     citation_to_json_dict(c) for c in event.citations
                 ],
             },
         )
         continue
     ```
   - Frame ordering invariant: `chat-open → zero-or-more chat-thinking → one-or-more chat-token → optional one chat-citations → chat-complete`. The optional placement matches the additive-events posture of [docs/chat-sse-contract.md L9](../../docs/chat-sse-contract.md#L9): "the frontend contract MUST be tolerant of unknown event names (silently ignore, do not error)". Story 10.7's pre-10.6b client builds will see the new frame and ignore it; once 10.7 binds the consumer, citations render.
   - Payload **camelCase** at the wire — but `citation_to_json_dict` itself emits snake_case. The API layer **does** apply the same `to_camel` alias convention used by the rest of the file. Verify the keys match: `kind` is single-word (no change), `bookedAt`, `amountKopiykas`, `categoryCode`, `sourceId` — these are camelCased by the SSE writer using the existing helper or a one-shot `_camel_keys(d)` recursion that this file already pulls from `pydantic.alias_generators.to_camel`. (Use whichever path the existing file uses for the `chat-complete` payload — there is precedent at [chat.py:577-587](../../backend/app/api/v1/chat.py#L577-L587).)
   - One new entry in the `event_generator` log set is **not** required — the handler-side `chat.citations.attached` INFO is sufficient. The API layer simply forwards the frame.

7. **Given** the SSE wire-contract documentation at [docs/chat-sse-contract.md](../../docs/chat-sse-contract.md), **When** this story lands, **Then** a new section `### chat-citations` is added between `chat-token` (L58) and `chat-complete` (L66) with this content shape:
   ```
   ### `chat-citations`

   Optional frame, fires at most once per turn after the final `chat-token`
   and before `chat-complete`. Suppressed on all `chat-refused` paths and on
   turns where no tools fired (the model answered from chat history alone).
   Carries the structured citation payload that backs the chip row in the
   chat UI (Story 10.7 consumer).

   ```json
   {
     "citations": [
       {"kind": "transaction", "id": "<uuid>", "bookedAt": "2026-03-14",
        "description": "Coffee Shop", "amountKopiykas": -8500,
        "currency": "UAH", "categoryCode": "groceries",
        "label": "Coffee Shop · 2026-03-14"},
       {"kind": "category", "code": "groceries", "label": "Groceries"},
       {"kind": "profile_field", "field": "monthly_expenses_kopiykas",
        "value": 4530000, "currency": "UAH", "asOf": "2026-04-01",
        "label": "Monthly expenses (Apr 2026)"},
       {"kind": "rag_doc", "sourceId": "en/emergency-fund",
        "title": "Emergency Fund Basics", "snippet": "An emergency …",
        "similarity": 0.83, "label": "Emergency Fund Basics"}
     ]
   }
   ```

   Cap: at most **20 citations** per turn (server-side truncation, logged
   at WARN if hit). Order: tool-call invocation order, then row order
   within each tool, with first-occurrence dedup. Contract version pinned
   in `CITATION_CONTRACT_VERSION` (currently `10.6b-v1`); bumps require a
   new story.
   ```
   - The "happy-path sequence" diagram at L33-L40 is updated to:
     ```
     chat-open
       → zero-or-more: chat-thinking
       → one-or-more:  chat-token
       → at-most-one:  chat-citations
       → chat-complete (terminal)
     ```
   - The "Unknown event names" line at L119 is **deleted** (`chat-citations` is now defined; nothing else 10.6b adds is unknown).
   - The "Observability cross-reference" table at L188-L196 gains one row: `chat.citations.attached` | After the canary scan passes on the happy path | INFO (carries `citation_count` + `citation_kinds_histogram` + `contract_version`).

8. **Given** the architecture document at [_bmad-output/planning-artifacts/architecture.md](../planning-artifacts/architecture.md), **When** this story lands, **Then** **two one-line amendments** are applied (no section rewrite):
   - At [§Chat Agent Component L1780](../planning-artifacts/architecture.md#L1780), append a new bullet under the existing tool-manifest line: `- Citation contract: structured per-turn data refs assembled from tool outputs (Story 10.6b — see [docs/chat-sse-contract.md](../../docs/chat-sse-contract.md) §chat-citations); chip-row UX in Story 10.7.`
   - At [§API Pattern — Chat Streaming L1814](../planning-artifacts/architecture.md#L1814) — after the `correlation_id` paragraph — append one sentence: `On the happy path, an optional terminal-adjacent chat-citations frame carries the typed citation payload (Story 10.6b); the chip strip is suppressed on all chat-refused paths.`
   - **No ADR required.** This is implementation of FR68, not a design decision; the projection map (AC #2) is the contract.

9. **Given** the test contract, **When** this story lands, **Then** the following test files exist and pass:
   - **`backend/tests/agents/chat/test_citations.py`** — pure-function unit tests against `assemble_citations`:
     1. **Empty input.** `assemble_citations(())` → `()`.
     2. **All-failed tool calls.** Three `ToolResult(ok=False)` rows → `()`.
     3. **`get_transactions` happy path.** Single tool call with 3 rows, 2 distinct `category_code` values → 3 `TransactionCitation` + 2 `CategoryCitation`, in tool-then-row order.
     4. **`get_profile` field projection.** Summary with `monthly_expenses_kopiykas=5000000`, `monthly_income_kopiykas=None`, `savings_ratio=22`, `health_score=None` → 2 `ProfileFieldCitation` (only non-None fields). Includes `currency` only on monetary fields.
     5. **`get_profile` breakdown deduplication.** Profile breakdown contains `groceries` AND a prior `get_transactions` call returned a `groceries` transaction → exactly **one** `CategoryCitation` for `groceries` (dedupe across tools, first-occurrence wins — the transaction-derived one).
     6. **`search_financial_corpus` snippet truncation.** Tool returned a row with a 500-char snippet → citation's `snippet` is **240 chars** (the 10.6b cap, distinct from the 10.4c 500-char tool cap).
     7. **`search_financial_corpus` source-id dedupe.** Two tool-call rows for the same `source_id` (different chunks of the same doc) → one `RagDocCitation`.
     8. **`get_teaching_feed` is dropped.** Tool call with 5 rows → zero citations (and one `chat.citations.dropped` DEBUG log fired with `tool_name="get_teaching_feed"`, `row_count=5`).
     9. **Truncation cap.** Synthesize 25 transactions → 20 citations (kept first 20 by index order); one `chat.citations.truncated` WARN log fired with `pre_truncate_count=25`, `kept_count=20`, `dropped_count=5`.
     10. **Malformed payload defense.** A `ToolResult` whose `payload` does not validate against the tool's pydantic model (simulating a 10.10 history-replay shape drift) is **silently skipped**; one `chat.citations.malformed_payload` WARN log fired with `tool_name`, `validation_error_summary`. The assembler does **not** raise.
     11. **Label rendering.** Per AC #2 label rules, assert exact strings for one example of each kind.
     12. **Order stability.** Two tool calls (transactions first, profile second) → citations enumerate transactions before profile fields (tool-call order), and within transactions, row 0 before row 1.
     13. **JSON round-trip.** `citation_to_json_dict(c)` produces a dict round-trippable through `Citation.model_validate(d)` (per-kind, all four kinds).
   - **`backend/tests/agents/chat/test_session_handler.py` extended** — new tests:
     1. `test_send_turn_attaches_citations_when_tools_called` — happy-path `send_turn` with mocked backend that returns `tool_calls=(<TX call>, <profile call>)`; assert `response.citations` is non-empty and well-formed; assert `chat.citations.attached` log emitted.
     2. `test_send_turn_attaches_no_citations_when_no_tools` — same, but `tool_calls=()` → `response.citations == ()`, no log fired.
     3. `test_send_turn_stream_yields_citations_event` — drive `send_turn_stream`, collect events, assert exactly one `ChatCitationsAttached` between the last `ChatTokenDelta` and `ChatStreamCompleted`.
     4. `test_send_turn_stream_no_citations_event_when_empty` — same, but tools returned no citable rows → no `ChatCitationsAttached` event.
     5. `test_canary_leak_path_emits_no_citations` — canary path raises before AC #4's emit point → no `ChatCitationsAttached` yielded.
     6. `test_grounding_intervention_emits_no_citations` — `ChatGuardrailInterventionError` from backend → no `ChatCitationsAttached` yielded (asserts the existing 10.6a regression-pin contract still holds).
   - **`backend/tests/api/test_chat_routes.py` extended** — new tests:
     1. `test_chat_route_emits_chat_citations_frame` — full SSE turn with backend stub that produces `tool_calls=(<TX call>,)`; assert the SSE byte stream contains exactly one `event: chat-citations\ndata: {...}` frame with the camelCased payload, between the last `chat-token` and the `chat-complete`.
     2. `test_chat_route_no_chat_citations_frame_when_empty` — same but no tool calls → SSE stream contains no `chat-citations` frame.
     3. `test_chat_route_chat_citations_payload_is_camel_case` — assert keys: `kind`, `bookedAt`, `amountKopiykas`, `categoryCode`, `sourceId`, `asOf` (no snake_case keys present).
   - **`backend/tests/agents/chat/test_stream_events.py` extended** — round-trip test: `event_to_json_dict(ChatCitationsAttached(citations=(<one of each kind>,)))` produces the AC #3 dict shape; the dict can be JSON-serialized without an encoder hook (UUIDs and dates serialize as strings via the existing serializer or `default=str`).
   - **No new harness / no new live-Bedrock test.** Story 10.6a's `backend/tests/eval/chat_grounding/` is unchanged — citations are not a grounding signal. The chat-grounding harness's run report is **not** extended with citation counts (out of scope; if a future story wants it, that is a small additive amendment to the report shape, gated by `schema_version` bump).
   - **Full suite** runs with `cd backend && uv run pytest tests/agents/chat/ tests/api/test_chat_routes.py -q` green; coverage on `citations.py` ≥ 95% (it's a pure function; high coverage is cheap and the projection map is the contract).

10. **Given** developer-facing documentation, **When** this story lands, **Then**:
    - The new `chat-citations` section per AC #7 is committed to [docs/chat-sse-contract.md](../../docs/chat-sse-contract.md).
    - A short developer-facing aside is added to the same file (under the new section): the **projection map** table from AC #2 is reproduced verbatim. This is the source of truth for the wire shape; the assembler module's docstring points back here. (Story 10.7 reads this doc to scaffold the chip components; duplicating the table inside ux-design-specification.md is **not** necessary — a one-line link from there to the contract suffices.)
    - One link is added to [_bmad-output/planning-artifacts/ux-design-specification.md L1648](../planning-artifacts/ux-design-specification.md#L1648) (the existing "chip content contract … owned by Story 10.6b" sentence) pointing to [docs/chat-sse-contract.md#chat-citations](../../docs/chat-sse-contract.md). Editorial only.

11. **Given** the tech-debt register at [docs/tech-debt.md](../../docs/tech-debt.md), **When** this story lands, **Then** the following entries are opened:
    - **TD-122 — Inline citation markers (`[^N]`) for sentence-to-citation alignment [LOW]**
      - **Why deferred:** Sentence-level alignment requires (a) a system-prompt amendment instructing the model to emit `[^N]` markers, (b) prompt-engineering iteration validated against Story 10.6a's grounding harness baseline (a behavior change that invalidates the baseline measurement), (c) a UI affordance (10.7) for hover/tap-to-highlight. The flat list 10.6b ships satisfies FR68 ("citations back to the underlying data"); markers are a UX uplift, not a correctness gap.
      - **Fix shape:** Extend [`backend/app/agents/chat/system_prompt.py`](../../backend/app/agents/chat/system_prompt.py) with a marker-emission instruction; add a regex-based marker-extractor to `citations.py`; re-baseline the chat-grounding harness (Story 10.6a) under the new prompt.
      - **Effort:** ~1–2 days (mostly prompt iteration + harness re-baseline).
      - **Trigger:** Story 10.7 completes citation-chip rendering and operator/user feedback indicates the flat list is insufficient ("which sentence cited which row?").

    - **TD-123 — Citation-count CloudWatch metric + alarm [LOW]**
      - **Why deferred:** Story 10.9 owns chat observability authorship and will batch metric publishing for all `chat.*` log events. 10.6b emits the `chat.citations.attached` log with `citation_count` + `citation_kinds_histogram`; metricification is a one-line metric-filter + alarm in 10.9's Terraform.
      - **Fix shape:** New CloudWatch metric `ChatCitationCountP50` / `ChatCitationCountP95` from the structured log; warn if P95 drops to 0 sustained 30m (signals tools stopped firing — a regression).
      - **Effort:** ~30 min after 10.9's metric-filter scaffolding lands.
      - **Trigger:** Story 10.9 production rollout.

    - **TD-124 — Localization of `CategoryCitation.label` and `ProfileFieldCitation.label` [LOW]**
      - **Why deferred:** The label-render rules in AC #2 emit canonical English strings ("Groceries", "Monthly expenses (Apr 2026)"). Story 10.7 will need a UA mapping for the chip-visible text. Doing the i18n inside `citations.py` would couple the assembler to the i18n stack (currently in frontend only); doing it on the FE keeps the assembler pure.
      - **Fix shape:** Add a UA copy-map in the FE chat-citations consumer (Story 10.7); the assembler's `label` becomes a render hint / fallback rather than the displayed string.
      - **Effort:** ~½ day, owned by Story 10.7.
      - **Trigger:** Story 10.7 implementation.

    - Grep `docs/tech-debt.md` for `TD-.*citation|TD-.*10\.6b` → no stale entries before this story; the three new ones above are the only matches. Record in Debug Log.
    - **No existing TD entry is closed** by this story.

12. **Given** the Epic 10 dependency chain, **When** this story lands, **Then**:
    - The `# Citation payloads → Story 10.6b` comment in [`backend/app/agents/chat/stream_events.py:13`](../../backend/app/agents/chat/stream_events.py#L13) is **deleted** (10.6b lands now); a new line is added below the dataclasses cluster: `# Inline citation markers ([^N]) → TD-122 follow-up`.
    - The `# - Citation payload in SSE frames → Story 10.6b` comment in [`backend/app/api/v1/chat.py:24`](../../backend/app/api/v1/chat.py#L24) is **deleted**; a new past-tense line is added: `# - Citation payload in SSE frames → Story 10.6b (DONE — see docs/chat-sse-contract.md §chat-citations).`
    - The `Story 10.6b's citation assembler` comment in [`backend/app/agents/chat/session_handler.py:117`](../../backend/app/agents/chat/session_handler.py#L117) is updated to past-tense: `Story 10.6b's citation assembler (citations.py) deserializes this on history replay (Story 10.10's read path).`
    - The `Story 10.6b reads role='tool' rows for citation assembly` comment in [`session_handler.py:36`](../../backend/app/agents/chat/session_handler.py#L36) is updated to: `Story 10.6b assembles citations from role='tool' rows (DONE); Story 10.10 replays them on history fetch.`
    - The `Story 10.6b's citation assembler reads these rows later` comment at [`session_handler.py:461`](../../backend/app/agents/chat/session_handler.py#L461) is amended: `Story 10.10's history-replay path re-uses citations.assemble_citations on these rows.`
    - The `Story 10.6b's citation assembler` comment in [`backend/app/agents/chat/tools/rag_corpus_tool.py:39`](../../backend/app/agents/chat/tools/rag_corpus_tool.py#L39) is updated to past-tense: `Story 10.6b's citation assembler (citations.py) projects each row into a RagDocCitation; the source_id field is the dedup key.`
    - Dev agent greps for any remaining `Story 10.6b` references in `backend/` and `docs/` and updates inline; records grep output in Debug Log.

13. **Given** the test execution standard, **When** the story is marked done, **Then** the following commands run green:
    ```
    cd backend && uv run pytest tests/agents/chat/ tests/api/test_chat_routes.py -q
    ```
    (the new test files + extended files pass without regressing any pre-10.6b test). Debug Log records the command output. Coverage report on `app/agents/chat/citations.py` ≥ 95%.

14. **Given** the version and release record, **When** the story is marked done, **Then**:
    - `VERSION` is bumped from `1.47.0` → `1.48.0` (MINOR — new wire-format event + new public module, additive only; no breaking change).
    - The Change Log section of this story file records the version bump and the wire-contract additions.

## Tasks / Subtasks

- [x] **Task 1: Author `citations.py` module** (AC: #1, #2)
  - [x] 1.1 Create `backend/app/agents/chat/citations.py` with the public surface from AC #1.
  - [x] 1.2 Implement the projection map from AC #2.
  - [x] 1.3 Implement deduplication via a single `set` keyed by AC #2 dedup tuples.
  - [x] 1.4 Implement `MAX_CITATIONS_PER_TURN = 20` truncation with the WARN log.
  - [x] 1.5 Implement label-rendering rules with a module-level dict for profile-field templates.
  - [x] 1.6 Top-of-file scope-comment block.
  - [x] 1.7 Re-export `Citation`, `CITATION_CONTRACT_VERSION`, `assemble_citations` from `backend/app/agents/chat/__init__.py`.

- [x] **Task 2: Extend `stream_events.py`** (AC: #3)
  - [x] 2.1 Append `ChatCitationsAttached` dataclass.
  - [x] 2.2 Extend `ChatStreamEvent` union; extend `event_to_json_dict`; extend `__all__`.
  - [x] 2.3 Update the module's `# Non-goals` comment block per AC #3.

- [x] **Task 3: Wire `send_turn_stream`** (AC: #4)
  - [x] 3.1 Insert citation assembly + `ChatCitationsAttached` yield between Step 5 canary scan and `ChatStreamCompleted`.
  - [x] 3.2 Emit `chat.citations.attached` INFO log with the AC #4 field set.
  - [x] 3.3 Refusal/error paths bypass the citation emit point — `test_send_turn_stream.py` continues to pass.

- [x] **Task 4: Wire `send_turn`** (AC: #5)
  - [x] 4.1 Added `citations: tuple = field(default_factory=tuple)` to `ChatTurnResponse`.
  - [x] 4.2 Post-canary/post-commit, call `assemble_citations(result.tool_calls)` and assign.
  - [x] 4.3 Emit `chat.citations.attached` INFO log (shared `_log_citations_attached` helper).

- [x] **Task 5: API layer SSE frame** (AC: #6)
  - [x] 5.1 Import `ChatCitationsAttached` + `citation_to_json_dict` in `app/api/v1/chat.py`.
  - [x] 5.2 New event-handler arm between `ChatToolHopCompleted` and `ChatTokenDelta`.
  - [x] 5.3 Added `_camelify_keys` recursion (uses `pydantic.alias_generators.to_camel`); matches `chat-complete` camelCase posture.

- [x] **Task 6: Documentation updates** (AC: #7, #8, #10)
  - [x] 6.1 New `### chat-citations` section in `docs/chat-sse-contract.md`.
  - [x] 6.2 Updated happy-path sequence diagram.
  - [x] 6.3 Deleted the "Unknown event names" line about 10.6b.
  - [x] 6.4 New observability-table row for `chat.citations.attached`.
  - [x] 6.5 Reproduced projection map under the new section.
  - [x] 6.6 Two amendments to `architecture.md` (§Chat Agent Component bullet + §API Pattern sentence).
  - [x] 6.7 Inline link from `ux-design-specification.md` chip-row section to the new contract.

- [x] **Task 7: Tests** (AC: #9)
  - [x] 7.1 `tests/agents/chat/test_citations.py` — 13 tests authored.
  - [x] 7.2 Extended `tests/agents/chat/test_session_handler.py` with 6 new tests.
  - [x] 7.3 Extended `tests/api/test_chat_routes.py` with 3 new tests.
  - [x] 7.4 Extended `tests/agents/chat/test_stream_events.py` with one round-trip test.
  - [x] 7.5 Full chat + chat-routes suite green (214 passed, 3 skipped); coverage on `citations.py` = 97%.

- [x] **Task 8: Tech-debt + cross-reference housekeeping** (AC: #11, #12)
  - [x] 8.1 Opened TD-122, TD-123, TD-124 in `docs/tech-debt.md`.
  - [x] 8.2 Updated comment cross-references in `session_handler.py`, `chat_backend.py`, `rag_corpus_tool.py`, `chat.py`, `stream_events.py`.
  - [x] 8.3 Grepped `Story 10.6b` across `backend/` and `docs/`; remaining matches are intentional (module headers, test names, past-tense cross-refs).
  - [x] 8.4 `grep -E 'TD-.*citation|TD-.*10\.6b'` → only TD-122/123/124 match (per Debug Log).

- [x] **Task 9: Test execution + version bump** (AC: #13, #14)
  - [x] 9.1 `cd backend && uv run pytest tests/agents/chat/ tests/api/test_chat_routes.py -q` → 214 passed, 3 skipped.
  - [x] 9.2 Bumped `VERSION` from `1.47.0` to `1.48.0`.
  - [x] 9.3 Populated Dev Agent Record / Completion Notes / File List / Change Log.

## Dev Notes

### Architecture Patterns and Constraints

- **Derive-on-demand, no new schema.** The single biggest design call: 10.6b adds **zero** Alembic migrations. Citations are a pure function of `role='tool'` rows that 10.4c already persists. Story 10.10's history-replay path will pass those rows back through `assemble_citations` to rebuild citations on the wire — no denormalized `chat_messages.citations` column needed. This keeps the story low-risk and reversible: if the citation contract changes in 10.6c (TD-122) we redeploy the assembler, no DB rewrite.
- **Pure function as the public surface.** `assemble_citations(tool_calls) -> tuple[Citation, ...]` is intentionally I/O-free. Persistence + logging happen one layer up. This makes the citation logic trivially testable (13 unit tests, no DB fixture, no async event loop), and lets Story 10.10 reuse the function in a non-async history-fetch path without coupling it to an `AsyncSession`.
- **First-occurrence dedup, not most-frequent or most-similar.** The dedup contract picks the first occurrence of a key (transaction UUID, category code, profile field+as_of, RAG source_id) within the turn's tool-call sequence. This matches the model's likely sentence-to-citation alignment without inline markers: the first time a category is mentioned by the tools is usually the first time the model would cite it. A "most-similar" dedup (e.g. RAG by highest similarity) would invert order and confuse 10.7's chip strip.
- **Cap the chip strip server-side.** `MAX_CITATIONS_PER_TURN = 20` is a defense-in-depth cap, not a UX rule. UX (10.7) will likely scroll horizontally past 5–6 chips on mobile, but the contract is to never emit more than 20. A model that fans out 200 transactions × 1 chip each would otherwise produce a 200-chip strip that no UI can render.
- **Refusal paths emit no citations.** A `chat-refused` frame is the terminal frame; the chip row is suppressed per [ux-design-specification.md L1803](../planning-artifacts/ux-design-specification.md#L1803). This is a UX contract first (citations on a refusal would imply the model "almost answered"), but enforcing it server-side keeps the wire contract clean: every `chat-refused` is exclusive of `chat-citations`.
- **The `get_teaching_feed` drop is intentional.** 10.4c's teaching-feed tool is a discovery/redirect surface ("re-open card X"), not a citable evidence surface. Including `TeachingFeedRow` as a chip kind would invite the model to cite "card titles" as if they were sources, which they are not — the source is the underlying data the card itself was derived from. The drop is documented in the assembler module's top-of-file comment so a future engineer doesn't "fix" the apparent omission.
- **No PII redaction inside citations.** All four tool outputs are already PII-bounded (transaction descriptions are pass-through but the Bedrock output PII filter runs over the assistant text in Story 10.5; tool payloads carry only what the tool chose to emit; RAG snippets are 500-char-capped pre-truncations of public corpus docs). Adding a redaction pass here would duplicate Guardrails work and risk masking real data the user *wants* to see in the chip.
- **Tool-call invocation order is the wire order.** Story 10.4c's series-execution tool loop preserves invocation order in the `result.tool_calls` tuple. Within each tool's payload, row index order is the inner sort. This is deterministic and stable across runs of the same prompt — important for snapshot-testing in 10.7.
- **`CITATION_CONTRACT_VERSION` is a thoroughfare for 10.9 + 10.10.** Bumping the version on any shape change lets Story 10.10's history-replay path emit a `contract_version_at_turn` field on legacy rows so the FE can degrade gracefully (and 10.9 can alarm on contract-version drift). For 10.6b, the version is `10.6b-v1`; subsequent bumps live with the changing story.

### Source Tree Components to Touch

- `backend/app/agents/chat/citations.py` — **new** module (the public surface from AC #1).
- [`backend/app/agents/chat/__init__.py`](../../backend/app/agents/chat/__init__.py) — re-export `Citation`, `CITATION_CONTRACT_VERSION`, `assemble_citations`.
- [`backend/app/agents/chat/stream_events.py`](../../backend/app/agents/chat/stream_events.py) — append `ChatCitationsAttached`, extend union + serializer + `__all__`.
- [`backend/app/agents/chat/session_handler.py`](../../backend/app/agents/chat/session_handler.py) — `send_turn_stream` (Step 5 → emit citations event); `send_turn` + `ChatTurnResponse` (add `citations` field).
- [`backend/app/api/v1/chat.py`](../../backend/app/api/v1/chat.py) — SSE event_generator new arm; past-tense comment update.
- [`docs/chat-sse-contract.md`](../../docs/chat-sse-contract.md) — new `chat-citations` section + sequence-diagram update + observability-table row.
- [`_bmad-output/planning-artifacts/architecture.md`](../planning-artifacts/architecture.md) — two one-line amendments (§Chat Agent Component, §API Pattern).
- [`_bmad-output/planning-artifacts/ux-design-specification.md`](../planning-artifacts/ux-design-specification.md) — one inline link at L1648.
- [`docs/tech-debt.md`](../../docs/tech-debt.md) — three new TD entries (TD-122, TD-123, TD-124).
- [`backend/tests/agents/chat/test_citations.py`](../../backend/tests/agents/chat/test_citations.py) — **new** (13 tests).
- [`backend/tests/agents/chat/test_session_handler.py`](../../backend/tests/agents/chat/test_session_handler.py) — extend (6 new tests).
- [`backend/tests/api/test_chat_routes.py`](../../backend/tests/api/test_chat_routes.py) — extend (3 new tests).
- [`backend/tests/agents/chat/test_stream_events.py`](../../backend/tests/agents/chat/test_stream_events.py) — extend (1 round-trip test).
- [`VERSION`](../../VERSION) — `1.47.0` → `1.48.0`.

### Testing Standards Summary

- `cd backend && uv run pytest tests/agents/chat/ tests/api/test_chat_routes.py -q` — green.
- `coverage run -m pytest tests/agents/chat/test_citations.py && coverage report --include='app/agents/chat/citations.py'` — ≥ 95%.
- **No live-Bedrock test added.** The chat-grounding harness (`backend/tests/eval/chat_grounding/`) is unchanged.
- **No regression on Story 10.5 / 10.5a / 10.6a tests.** AC #4 / #5 changes are additive; the existing canary-leak / grounding-intervention / disconnect-finalizer tests must continue passing without edit.
- **Coverage target on the streaming handler is preserved.** The Step 5 → emit-citations addition is a straight-line block; the existing 10.5a coverage on `send_turn_stream` (≥ 90%) does not regress.

### Project Structure Notes

- **Alignment with unified project structure:** `citations.py` is a sibling of `canary_detector.py`, `memory_bounds.py`, `input_validator.py` under `backend/app/agents/chat/`. The five-module flat layout (handlers + dispatcher + tools/ subpackage) established by 10.4a/b/c is preserved; no new subpackage.
- **Detected conflicts or variances:** none. The wire-contract addition is pre-declared by 10.5 ("Story 10.6b will add `chat-citations`; this contract is additive."), so the docs/chat-sse-contract.md update is closing a loop, not opening a new contract.

### References

- [Source: _bmad-output/planning-artifacts/epics.md L2136-L2137 (Story 10.6b definition)](../planning-artifacts/epics.md#L2136-L2137) — the canonical scope statement.
- [Source: _bmad-output/planning-artifacts/prd.md L688 (FR68)](../planning-artifacts/prd.md#L688) — the citation requirement.
- [Source: _bmad-output/planning-artifacts/architecture.md §Chat Agent Component L1780](../planning-artifacts/architecture.md#L1780) — the tool-manifest line that 10.6b appends a citation-contract bullet to.
- [Source: _bmad-output/planning-artifacts/architecture.md §API Pattern — Chat Streaming L1802-L1815](../planning-artifacts/architecture.md#L1802-L1815) — the SSE envelope framework 10.6b extends with one optional frame.
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md L1646-L1657 §Citation Chip Row](../planning-artifacts/ux-design-specification.md#L1646-L1657) — the layout slot 10.6b's payload feeds.
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md L1803](../planning-artifacts/ux-design-specification.md#L1803) — "Citation chips do not render on refusal variants" (drives the AC #4 / #5 refusal-path-suppression rule).
- [Source: docs/chat-sse-contract.md L9, L119](../../docs/chat-sse-contract.md#L119) — the additive-events posture; 10.7 client tolerance for unknown events.
- [Source: backend/app/agents/chat/session_handler.py:113-130 `_serialize_tool_call`](../../backend/app/agents/chat/session_handler.py#L113-L130) — the JSON serialization shape 10.6b's history-replay path (10.10) will deserialize.
- [Source: backend/app/agents/chat/session_handler.py:462-475 (tool-row persistence)](../../backend/app/agents/chat/session_handler.py#L462-L475) — the rows the assembler reads (live path consumes `result.tool_calls` directly; replay path consumes the persisted rows).
- [Source: backend/app/agents/chat/tools/__init__.py `TOOL_MANIFEST`](../../backend/app/agents/chat/tools/__init__.py) — the four tools the projection map dispatches on.
- [Source: backend/app/agents/chat/tools/transactions_tool.py `TransactionRow`](../../backend/app/agents/chat/tools/transactions_tool.py) — fields available for `TransactionCitation`.
- [Source: backend/app/agents/chat/tools/profile_tool.py `ProfileSummary` / `CategoryBreakdownRow`](../../backend/app/agents/chat/tools/profile_tool.py) — fields available for `ProfileFieldCitation` + `CategoryCitation`.
- [Source: backend/app/agents/chat/tools/rag_corpus_tool.py `CorpusDocRow`](../../backend/app/agents/chat/tools/rag_corpus_tool.py) — fields available for `RagDocCitation`.
- [Source: backend/app/agents/chat/stream_events.py](../../backend/app/agents/chat/stream_events.py) — the file 10.6b extends with `ChatCitationsAttached`.
- [Source: backend/app/api/v1/chat.py:559-587](../../backend/app/api/v1/chat.py#L559-L587) — the SSE generator block 10.6b inserts the new arm into.
- [Source: _bmad-output/implementation-artifacts/10-4c-tool-manifest-read-only.md AC #8](10-4c-tool-manifest-read-only.md) — the tool-row persistence contract 10.6b reads.
- [Source: _bmad-output/implementation-artifacts/10-5-chat-streaming-api-sse.md](10-5-chat-streaming-api-sse.md) — the SSE generator framework + heartbeat protocol.
- [Source: _bmad-output/implementation-artifacts/10-5a-send-turn-stream-disconnect-finalizer.md](10-5a-send-turn-stream-disconnect-finalizer.md) — the disconnect-finalizer interplay (AC #4 verifies citations are *not* emitted from the finalizer).
- [Source: _bmad-output/implementation-artifacts/10-6a-grounding-enforcement-harness.md](10-6a-grounding-enforcement-harness.md) — the no-regenerate / refusal-path contract 10.6b inherits (AC #4 verifies grounding refusals emit no citations).
- [Source: docs/tech-debt.md TD-094 (Phase B AgentCore)](../../docs/tech-debt.md) — Phase B inherits the citation contract automatically (no coupling).

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (1M context)

### Debug Log References

- `cd backend && uv run pytest tests/agents/chat/ tests/api/test_chat_routes.py -q` → **214 passed, 3 skipped** (1 pre-existing FastAPI deprecation warning, unrelated).
- `uv run pytest tests/agents/chat/test_citations.py --cov=app.agents.chat.citations --cov-report=term-missing -q` → **13 passed**, coverage **97%** on `citations.py` (4 missed lines are defensive branches: payload not-a-dict, generic-tool fall-through, `__all__` export tail).
- `grep -rn 'Story 10\.6b' backend/ docs/` → all remaining hits are either the new module header (`citations.py`), test docstrings, past-tense cross-references in `chat_backend.py`/`session_handler.py`/`rag_corpus_tool.py`/`api/v1/chat.py`/`stream_events.py`, or the story file itself. None are stale forward-pointers.
- `grep -rnE 'TD-.*citation|TD-.*10\.6b' docs/` → matches only the three new entries TD-122 / TD-123 / TD-124 (and one back-pointer line in this story file).

### Completion Notes List

- **Pure-function assembler** (`backend/app/agents/chat/citations.py`): four pydantic citation models + `assemble_citations(tool_calls) -> tuple[Citation, ...]` + `citation_to_json_dict`. No DB, no I/O — trivially testable, ready for Story 10.10's history-replay reuse.
- **Wire-contract additive only**: new `chat-citations` SSE frame is optional; pre-10.6b clients ignore it (per the contract's additive-events posture). All `chat-refused` paths suppress the chip strip.
- **CamelCase at the wire**: added a small `_camelify_keys` recursion in `app/api/v1/chat.py` so the citation payload follows the same camelCase convention as `chat-complete` without giving each citation model its own alias generator.
- **Telemetry**: handler emits `chat.citations.attached` (INFO) with `citation_count`, `citation_kinds_histogram`, `truncated`, `contract_version`. Story 10.9 will metricify (TD-123).
- **Three TD entries opened**: TD-122 (inline `[^N]` markers), TD-123 (CloudWatch metric), TD-124 (UA localization).
- **Refusal-path regression pin**: extended `test_session_handler.py` with `test_canary_leak_path_emits_no_citations` and `test_grounding_intervention_emits_no_citations` to lock in the contract that `chat-citations` never accompanies a refusal.

### File List

- `backend/app/agents/chat/citations.py` — **new** module.
- `backend/app/agents/chat/__init__.py` — re-export `Citation`, `CITATION_CONTRACT_VERSION`, `assemble_citations`.
- `backend/app/agents/chat/stream_events.py` — `ChatCitationsAttached` dataclass + union/serializer/`__all__` updates; `# Non-goals` comment refreshed.
- `backend/app/agents/chat/session_handler.py` — citations attached on both `send_turn` (added `citations` field on `ChatTurnResponse`) and `send_turn_stream` (yield `ChatCitationsAttached` between final token and `ChatStreamCompleted`); shared `_log_citations_attached` helper; cross-reference comments updated to past tense.
- `backend/app/agents/chat/chat_backend.py` — comment refreshed to past tense.
- `backend/app/agents/chat/tools/rag_corpus_tool.py` — comment refreshed to past tense.
- `backend/app/api/v1/chat.py` — new `chat-citations` SSE arm, `citation_to_json_dict` import, `_camelify_keys` helper, `# - Citation payload …` comment refreshed to past tense.
- `docs/chat-sse-contract.md` — new `chat-citations` section, projection-map table, sequence-diagram update, observability-table row, removed forward-pointing "Unknown event names" line.
- `docs/tech-debt.md` — TD-122 / TD-123 / TD-124 added.
- `_bmad-output/planning-artifacts/architecture.md` — bullet under §Chat Agent Component + sentence under §API Pattern.
- `_bmad-output/planning-artifacts/ux-design-specification.md` — inline link in chip-row content-contract paragraph.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — `10-6b-citation-payload-data-refs: review`.
- `_bmad-output/implementation-artifacts/10-6b-citation-payload-data-refs.md` — Status, Tasks, Dev Agent Record, File List, Change Log.
- `backend/tests/agents/chat/test_citations.py` — **new** (13 tests, 97% module coverage).
- `backend/tests/agents/chat/test_session_handler.py` — 6 new tests under §Story 10.6b.
- `backend/tests/agents/chat/test_stream_events.py` — round-trip test for `ChatCitationsAttached`.
- `backend/tests/api/test_chat_routes.py` — 3 new SSE-frame tests under §Story 10.6b.
- `VERSION` — `1.47.0` → `1.48.0`.

### Change Log

- 2026-04-26 — Story 10.6b implemented: pure-function `citations.py` assembler, `ChatCitationsAttached` stream event, `chat-citations` SSE frame, `ChatTurnResponse.citations` field, `chat.citations.attached` INFO log, projection-map docs, three new TD entries (TD-122/123/124).
- 2026-04-26 — Version bumped from 1.47.0 to 1.48.0 per story completion (MINOR — additive wire-format event + new public module).
- 2026-04-26 — Code review fixes applied:
  - M1: `assemble_citations_with_meta` now exposes truncation; `chat.citations.attached` log carries an honest `truncated` field on both `send_turn` and `send_turn_stream` paths.
  - M2: TD-125 opened against `CorpusDocRow` lacking a `title` field; [docs/chat-sse-contract.md](../../docs/chat-sse-contract.md) §chat-citations sample updated to show realistic `title == sourceId` and back-link to TD-125.
  - M3: `assemble_citations` re-typed to `Sequence[ToolResult]` per AC #1 (was `Sequence[object]`).
  - L1: `test_grounding_intervention_emits_no_citations` restructured so the no-citations assertion is reachable.
  - L2: `# Inline citation markers ([^N]) → TD-122` forward-pointer moved below the dataclass cluster in `stream_events.py` per AC #3.
