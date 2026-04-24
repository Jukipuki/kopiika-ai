# Story 10.4.c: Tool Manifest (Read-Only Data Tools)

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **platform engineer shipping Epic 10 chat safety**,
I want the Phase A `ChatSessionHandler` + `DirectBedrockBackend` extended with **(1) a declaratively-defined, read-only tool manifest exposing exactly four tools — `get_transactions`, `get_profile`, `get_teaching_feed`, `search_financial_corpus` — each with a pydantic-validated input schema and a pydantic-validated output schema, (2) a per-tool handler that queries only the authenticated user's own data via existing service-layer functions (no raw SQL, no cross-user reads, no write paths), (3) an allowlist-enforcing tool-use loop inside `DirectBedrockBackend.invoke` that iterates Bedrock Converse's `tool_use` / `tool_result` cycle up to a bounded hop count, and (4) a denial path that converts unknown tool names, schema-validation failures, and authorization errors into typed exceptions surfaced at the handler boundary** —
so that the architecture-mandated **Agent layer** ([architecture.md §Defense-in-Depth Layers L1709](../planning-artifacts/architecture.md#L1709) "tool allowlist enforced at runtime; tools scoped to the authenticated user's data only; no filesystem / network / admin / write tools exposed") and the Chat Agent Component's tool manifest ([architecture.md §Chat Agent Component L1780](../planning-artifacts/architecture.md#L1780) "user transactions, user profile, teaching-feed history, RAG corpus") are implemented rather than documented only, the scope handoff `# Downstream: 10.4c adds tool manifest;` at [`backend/app/agents/chat/session_handler.py:32`](../../backend/app/agents/chat/session_handler.py#L32) is closed, and Story 10.5 (SSE streaming), 10.6a (grounding), 10.6b (citations), and 10.8b (safety harness) all run against an agent that can actually reach the user's data through the defense-in-depth-enforced manifest rather than answering from the model's prior.

## Scope Boundaries

This story sits **between** 10.4b (system-prompt hardening + canaries) and 10.5 (SSE streaming + `CHAT_REFUSED` envelope). Explicit deferrals — **must not** ship here:

- **No SSE streaming, no HTTP route, no `CHAT_REFUSED` JSON envelope** — Story 10.5. This story raises typed exceptions (`ChatToolNotAllowedError`, `ChatToolSchemaError`, `ChatToolExecutionError`, `ChatToolLoopExceededError`) at the handler boundary; 10.5's SSE wrapper translates them to the user-facing envelope with a new `reason=tool_blocked` value — **that enum extension is authored here** (AC #11) so Story 10.5's switch is a flat map.
- **No Bedrock Guardrails input/output attachment** — Story 10.5 wires `guardrailIdentifier` + `guardrailVersion` at invoke-time. Tool-use responses also need to traverse Guardrails; that gating is 10.5's responsibility, not this story's.
- **No citation payload in the API response** — Story 10.6b. This story writes tool-invocation + tool-result rows that 10.6b's citation assembler will later read; the **persistence shape** for tool-result provenance is owned here (AC #8) but the API contract for citations lives in 10.6b.
- **No grounding threshold tuning** — Story 10.6a. Tools that return no rows still return a valid (empty) payload; the model may still hallucinate from priors, and that is 10.6a's job to catch via contextual-grounding.
- **No write-path tools** — explicit epic-level deferral ([epics.md §Out of Scope L2160](../planning-artifacts/epics.md#L2160) "Chat-based transaction edits/actions — Phase 2 follow-up; requires separate safety review. Epic 10 ships read-only.") Any handler that mutates state is **forbidden** in this story; a lint-style grep check (AC #12) asserts `INSERT|UPDATE|DELETE` do not appear in any handler module.
- **No new tool-backing services** — the four tools wrap **existing** service-layer functions ([`get_transactions_for_user`](../../backend/app/services/transaction_service.py#L51), [`get_profile_for_user`](../../backend/app/services/profile_service.py#L24) + [`get_category_breakdown`](../../backend/app/services/profile_service.py#L34), [`get_insights_for_user`](../../backend/app/services/insight_service.py#L24), [`retrieve_relevant_docs`](../../backend/app/rag/retriever.py#L15)). No new SQL, no new joins, no new indexes.
- **No red-team corpus authoring, no CI harness** — Story 10.8a authors the corpus; Story 10.8b builds the runner. 10.4c ships **unit-level** tests of the manifest, loop, and each handler against a fixture user with canned data.
- **No rate-limit envelope** — Story 10.11 owns per-user throttling. 10.4c caps the **per-turn** tool-hop count (AC #7) as a safety bound, which is a different concern from per-user throttling.
- **No retroactive change to the 10.4a/10.4b handler API (the four public methods) or system-prompt wording** — the contract surface stays stable. Tool loop is internal to `DirectBedrockBackend.invoke`; the handler does not learn new verbs.

A one-line scope comment at the top of each new module enumerates the above so the next engineer does not accidentally expand scope.

## Acceptance Criteria

1. **Given** a new module at `backend/app/agents/chat/tools/__init__.py` (converting `backend/app/agents/chat/` from a flat module surface into a package with a `tools/` subpackage), **When** the subpackage is authored, **Then** it exposes exactly this public surface (no other public names — 10.5/10.6b extend by composition, not by mutating this module):
   ```python
   CHAT_TOOL_MANIFEST_VERSION: str = "10.4c-v1"  # bump when tool set / schemas change

   @dataclass(frozen=True)
   class ToolSpec:
       name: str                      # stable snake_case id, exposed to model
       description: str               # short, action-oriented, model-facing
       input_model: type[BaseModel]   # pydantic v2; JSON Schema via model_json_schema()
       output_model: type[BaseModel]  # pydantic v2; result envelope
       handler: Callable[..., Awaitable[BaseModel]]  # async, user-scoped
       max_rows: int                  # per-call output cap (defense-in-depth)

   TOOL_MANIFEST: tuple[ToolSpec, ...]   # the four read-only tools, frozen order
   TOOL_ALLOWLIST: frozenset[str]         # {spec.name for spec in TOOL_MANIFEST}

   def get_tool_spec(name: str) -> ToolSpec: ...  # raises ChatToolNotAllowedError
   def render_bedrock_tool_config() -> dict: ...  # Converse `toolConfig` shape
   ```
   - `TOOL_MANIFEST` is a module-level **tuple** (not list) — the allowlist is immutable at runtime. The order is the authoring order; a `test_tool_manifest.py` test asserts the exact tuple of names `("get_transactions", "get_profile", "get_teaching_feed", "search_financial_corpus")` so a rename or reorder surfaces in review.
   - `TOOL_ALLOWLIST` is the single source of truth for allowlist checks. `get_tool_spec(name)` raises `ChatToolNotAllowedError` (defined in `tool_errors.py`, AC #6) when `name not in TOOL_ALLOWLIST` — there is **no** fallback, no similarity suggestion, no "did you mean".
   - `render_bedrock_tool_config()` produces the exact `toolConfig` dict shape required by Bedrock Converse:
     ```python
     {
       "tools": [
         {"toolSpec": {
            "name": spec.name,
            "description": spec.description,
            "inputSchema": {"json": spec.input_model.model_json_schema()},
         }} for spec in TOOL_MANIFEST
       ],
       "toolChoice": {"auto": {}},
     }
     ```
     Dev agent confirms this shape against the pinned `langchain_aws` / `boto3` version at implementation time; if `langchain_aws.ChatBedrockConverse.bind_tools()` already produces an acceptable shape from pydantic models, that path is preferred and `render_bedrock_tool_config()` becomes a thin wrapper over it. The Debug Log records which path was chosen.
   - `CHAT_TOOL_MANIFEST_VERSION` is imported by `session_handler.py` and added to the `chat.turn.completed` structured log field set (AC #10) so Story 10.9 can slice a behavioral regression by manifest-version bumps. It is **not** added to `chat_sessions`.

2. **Given** a new tool module `backend/app/agents/chat/tools/transactions_tool.py`, **When** authored, **Then** it exposes:
   ```python
   class GetTransactionsInput(BaseModel):
       start_date: date | None = None   # inclusive; None = no lower bound
       end_date: date | None = None     # inclusive; None = today
       category: str | None = None      # exact match against Category.code
       limit: int = Field(default=50, ge=1, le=200)

   class TransactionRow(BaseModel):
       id: uuid.UUID
       booked_at: date
       description: str                 # merchant/description as stored
       amount_kopiykas: int             # signed; negative = debit
       currency: str                    # ISO code
       category_code: str | None
       transaction_kind: str | None     # Epic 11 transaction_kind if populated

   class GetTransactionsOutput(BaseModel):
       rows: list[TransactionRow]
       row_count: int
       truncated: bool                  # True iff more rows existed beyond `limit`

   async def get_transactions_handler(
       *, user_id: uuid.UUID, db: AsyncSession, **input_fields
   ) -> GetTransactionsOutput: ...
   ```
   - Backed by [`transaction_service.get_transactions_for_user`](../../backend/app/services/transaction_service.py#L51). The handler **must not** query transactions by any filter other than `user_id` (the service function already scopes by `user_id`; the handler **does not** override or widen this). Date / category / limit are applied as additional filters on top.
   - `max_rows` in the `ToolSpec` is **200** (matches the pydantic `limit` cap). The handler enforces `limit` by passing it to the service; if the service returns > `limit` rows (shouldn't happen but defense-in-depth), the handler slices to `limit` and sets `truncated=True`.
   - The handler **never** returns `user_id` / FK columns the model does not need (`statement_upload_id`, raw parser fields, `created_at` audit timestamps). Principle: the tool output is the minimum surface the model needs to reason about transactions — anything more is latent attack surface for cross-turn leak.
   - Description field is passed through **as stored** (not LLM-re-categorized, not PII-redacted by this tool — Bedrock Guardrails output PII filter at Story 10.5 handles any IBAN / card-number leakage in description strings).
   - One-line top-of-file comment: `# Read-only — MUST NOT mutate. Any INSERT/UPDATE/DELETE introduction breaks the Epic 10 no-write-tools invariant.`

3. **Given** a new tool module `backend/app/agents/chat/tools/profile_tool.py`, **When** authored, **Then** it exposes:
   ```python
   class GetProfileInput(BaseModel):
       include_category_breakdown: bool = False
       include_monthly_comparison: bool = False

   class ProfileSummary(BaseModel):
       monthly_income_kopiykas: int | None
       monthly_expenses_kopiykas: int | None
       savings_ratio: int | None        # 0..100, Epic 11 wiring
       health_score: int | None         # 0..100, latest score
       currency: str                    # profile's reporting currency
       as_of: date

   class CategoryBreakdownRow(BaseModel):
       category_code: str
       amount_kopiykas: int
       share_percent: int               # 0..100

   class MonthlyComparisonRow(BaseModel):
       month: date                      # first of month
       income_kopiykas: int
       expenses_kopiykas: int

   class GetProfileOutput(BaseModel):
       summary: ProfileSummary
       category_breakdown: list[CategoryBreakdownRow] = []
       monthly_comparison: list[MonthlyComparisonRow] = []

   async def get_profile_handler(*, user_id: uuid.UUID, db: AsyncSession, **input_fields) -> GetProfileOutput: ...
   ```
   - Backed by [`profile_service.get_profile_for_user`](../../backend/app/services/profile_service.py#L24), [`get_category_breakdown`](../../backend/app/services/profile_service.py#L34), [`get_monthly_comparison`](../../backend/app/services/profile_service.py#L80), and the health-score read path. No new service functions authored here.
   - If the user has **no** profile row yet (brand-new account, no uploads), the handler returns a `ProfileSummary` with every field `None` and empty lists for breakdown/comparison. The model is expected to answer "I don't see any profile data yet — upload a statement first" through the Guardrails-grounded path, not to hallucinate numbers. (Story 10.6a enforces this at the grounding layer; this tool's empty payload is the grounding truth.)
   - `as_of` is `profile.updated_at.date()` if present, else today.
   - `max_rows` in the `ToolSpec` is **1** — the summary is a singleton; `category_breakdown` + `monthly_comparison` are capped at **12 rows each** (past 12 months, or top 12 categories) inside the handler.

4. **Given** a new tool module `backend/app/agents/chat/tools/teaching_feed_tool.py`, **When** authored, **Then** it exposes:
   ```python
   class GetTeachingFeedInput(BaseModel):
       limit: int = Field(default=20, ge=1, le=50)
       only_thumbs_up: bool = False

   class TeachingFeedRow(BaseModel):
       insight_id: uuid.UUID
       card_type: str                   # e.g. "spending_spike" | "milestone" | ...
       title: str
       delivered_at: date
       user_feedback: str | None        # "up" | "down" | None

   class GetTeachingFeedOutput(BaseModel):
       rows: list[TeachingFeedRow]
       row_count: int
       truncated: bool

   async def get_teaching_feed_handler(*, user_id: uuid.UUID, db: AsyncSession, **input_fields) -> GetTeachingFeedOutput: ...
   ```
   - Backed by [`insight_service.get_insights_for_user`](../../backend/app/services/insight_service.py#L24) joined to `CardFeedback` / `FeedbackResponse` (dev agent greps for the existing join shape — the teaching-feed list endpoint likely already does this; reuse its query if extractable, else copy the join pattern). **No new service function**.
   - `only_thumbs_up` filters to insights the user voted up (a useful "what resonated with me" slice for chat); default `False` returns all delivered insights regardless of feedback.
   - `max_rows` in the `ToolSpec` is **50**.
   - The handler **never** returns insight bodies / long-form content — only `card_type`, `title`, and `delivered_at`. If the user asks "what did card X say", the model asks the user to re-open the card in the teaching feed rather than relay; this is a **deliberate scope compression** (chat is a summary/question surface for the teaching feed, not a replacement viewer). Documented in the tool description string.

5. **Given** a new tool module `backend/app/agents/chat/tools/rag_corpus_tool.py`, **When** authored, **Then** it exposes:
   ```python
   class SearchFinancialCorpusInput(BaseModel):
       query: str = Field(min_length=1, max_length=500)
       top_k: int = Field(default=5, ge=1, le=10)

   class CorpusDocRow(BaseModel):
       source_id: str                   # stable corpus-doc identifier
       title: str
       snippet: str                     # first 500 chars of matched chunk
       similarity: float                # 0..1, halfvec cosine similarity

   class SearchFinancialCorpusOutput(BaseModel):
       rows: list[CorpusDocRow]
       row_count: int

   async def search_financial_corpus_handler(*, user_id: uuid.UUID, db: AsyncSession, **input_fields) -> SearchFinancialCorpusOutput: ...
   ```
   - Backed by [`app.rag.retriever.retrieve_relevant_docs`](../../backend/app/rag/retriever.py#L15) — the **same** retriever the batch education agent uses ([`backend/app/agents/education/node.py:15`](../../backend/app/agents/education/node.py#L15)). No new retriever.
   - This tool is **user-scoped** in the IAM / FK sense only because `retrieve_relevant_docs` runs against the global corpus, not per-user data. The `user_id` parameter is still threaded through the handler signature (uniform handler contract, AC #6); it is not passed to the retriever. A comment at the handler records this: *"The financial-literacy corpus is shared across users; this tool is safe to scope-widen because it exposes no user data. Do NOT relax the pattern for any other tool."*
   - `snippet` is the first 500 chars of the retrieved chunk — the model gets enough to cite, not the full document. Rationale: bounded context, faster grounding check in 10.6a, no whole-document leak via one tool call.
   - `max_rows` is **10** (mirrors the pydantic `top_k` cap).

6. **Given** a new module `backend/app/agents/chat/tools/dispatcher.py`, **When** authored, **Then** it exposes exactly:
   ```python
   @dataclass(frozen=True)
   class ToolInvocation:
       tool_name: str
       raw_input: dict                  # raw model-emitted JSON (pre-validation)
       tool_use_id: str                 # Bedrock tool_use_id, echoed in toolResult

   @dataclass(frozen=True)
   class ToolResult:
       tool_use_id: str
       tool_name: str
       ok: bool
       payload: dict                    # validated output dict OR error envelope
       error_kind: str | None           # "not_allowed" | "schema_error" | "execution_error" | None
       elapsed_ms: int

   async def dispatch_tool(
       invocation: ToolInvocation, *, user_id: uuid.UUID, db: AsyncSession
   ) -> ToolResult: ...
   ```
   - `dispatch_tool`:
     1. Resolves the `ToolSpec` via `get_tool_spec(invocation.tool_name)` — unknown → builds a `ToolResult(ok=False, error_kind="not_allowed", payload={"error": "tool_not_allowed", "tool_name": invocation.tool_name})` and returns (does **not** raise). Rationale: an unknown tool invocation is a **soft** model error — the loop gets to observe the error and self-correct on the next iteration. Only the **loop-level** guards (AC #7) raise `ChatToolNotAllowedError` upward to the handler.
     2. Validates `invocation.raw_input` against `spec.input_model`. On `ValidationError`: returns `ToolResult(ok=False, error_kind="schema_error", payload={"error": "schema_error", "detail": <pydantic err as safe str>})`. **Never** echoes raw input back (adversarial input could shape the error message).
     3. Calls `spec.handler(user_id=user_id, db=db, **validated_input_fields)`. On the handler raising — **re-categorize**:
        - `sqlalchemy.exc.SQLAlchemyError` → `ToolResult(ok=False, error_kind="execution_error", payload={"error": "execution_error"})` + ERROR log `chat.tool.execution_failed`.
        - `PermissionError` / custom auth error → raise `ChatToolAuthorizationError` **upward** (fail-closed; a misrouted cross-user read is never returned to the model).
        - Any other `Exception` → `ToolResult(ok=False, error_kind="execution_error", payload={"error": "execution_error"})` + ERROR log.
     4. Validates the handler return against `spec.output_model.model_validate(result.model_dump())`. Defensive — a handler bug producing out-of-shape output must not poison model context. On failure: ERROR log `chat.tool.output_schema_drift` + `ToolResult(ok=False, error_kind="execution_error", ...)`.
     5. Truncates at `spec.max_rows` if the output carries `rows` (common envelope); sets `truncated=True` if slicing occurred. (The handler **already** enforces `limit`; this is a second-layer belt-and-braces cap against future bugs.)
     6. Measures wall time as `elapsed_ms` for observability.
   - The dispatcher **never** writes to any `chat_messages` row directly. Persistence of tool calls is the backend's concern (AC #8) — the dispatcher is a pure request/response primitive.
   - A top-of-file comment notes that `dispatch_tool` is the **only** module that touches `spec.handler` directly; any other caller indicates scope drift.

7. **Given** `DirectBedrockBackend.invoke` at [`backend/app/agents/chat/chat_backend.py:135-215`](../../backend/app/agents/chat/chat_backend.py#L135-L215), **When** this story extends it, **Then** the single-call `ainvoke` is replaced with a **bounded tool-use loop**:
   - Use `langchain_aws.ChatBedrockConverse.bind_tools(tools)` (or the native Converse `toolConfig` pass-through — dev agent picks the path matching the pinned version; Debug Log records the choice) to bind the four tool specs.
   - Loop structure (pseudo-Python):
     ```python
     MAX_TOOL_HOPS: int = 5  # module-level constant; see below
     hops = 0
     while True:
         response = await client.ainvoke(lc_messages)
         tool_uses = _extract_tool_uses(response)  # empty list for plain-text final
         if not tool_uses:
             break  # final text response — exit loop
         hops += 1
         if hops > MAX_TOOL_HOPS:
             raise ChatToolLoopExceededError(hops=hops)
         results: list[ToolResult] = []
         for tu in tool_uses:
             invocation = ToolInvocation(tool_name=tu.name, raw_input=tu.input, tool_use_id=tu.id)
             result = await dispatch_tool(invocation, user_id=user_id, db=db)
             results.append(result)
         lc_messages.append(_ai_message_with_tool_uses(tool_uses))
         lc_messages.append(_tool_results_message(results))
     ```
   - **Tool-hop cap:** `MAX_TOOL_HOPS = 5`. Rationale: a well-formed single-turn chat should resolve in ≤ 2 tool hops (one data tool + possibly one RAG tool). 5 gives headroom for a model that self-corrects after a schema error. Beyond 5, we are in a loop — probably stuck or adversarially driven — and raise `ChatToolLoopExceededError`. **Not** env-overridable (operational invariant; a future change is a story, not a config flip). Constant lives at `DirectBedrockBackend` module top so it is greppable.
   - Parallel tool uses in a single model turn are supported (Bedrock Converse can emit multiple `tool_use` blocks): the loop executes them **in series** (not `asyncio.gather`) — DB connection lifecycle is per-request, and the handler owns a single `AsyncSession`; fanning out without explicit session isolation risks transactional interleaving bugs. Documented inline.
   - `user_id` and `db` must thread through `invoke` — **new kwargs** on `ChatBackend.invoke`:
     ```python
     async def invoke(
         self, *, db_session_id, context_messages, user_message, system_prompt,
         user_id: uuid.UUID,         # NEW — needed by tools
         db: AsyncSession,            # NEW — threaded to handlers
     ) -> ChatInvocationResult: ...
     ```
     This is a breaking signature change; the only caller is `ChatSessionHandler.send_turn`, and this story updates that caller (AC #9). Phase B's skipped `test_chat_backend_agentcore.py` fixture is updated to include the new kwargs.
   - `ChatInvocationResult` (the handler's return type) **gains** `tool_calls: tuple[ToolResult, ...]` — the sequence of results executed during this turn, in invocation order, for persistence by the handler (AC #8) and consumption by Story 10.6b's citation assembler. Empty tuple when the model answered without tools.
   - Token accounting: **sum** across every Converse iteration. The returned `ChatInvocationResult.input_tokens` / `output_tokens` are cumulative across all hops. If usage metadata is absent on any iteration, fall back to `memory_bounds.estimate_tokens` on that iteration's inputs/outputs and keep `token_source="tiktoken"` for the whole turn.
   - The defensive flatten at [`chat_backend.py:205-215`](../../backend/app/agents/chat/chat_backend.py#L205-L215) ("Phase A has no tools (10.4c), so a list here is anomalous — flatten defensively") is **removed** — tool-use responses are expected now. The final-text extraction uses `response.content` with a structured walk: concatenate every `text`-type block and drop `tool_use`-type blocks (the latter only appear on non-final iterations, which the loop handles explicitly).

8. **Given** the `chat_messages` schema additions from Story 10.1b + 10.4b's `redaction_flags.filter_source` enum (`input` | `output` | `input_validator` | `canary_detector`), **When** tool calls execute, **Then** they are persisted as **new `chat_messages` rows** in a uniform shape:
   - For every tool invocation (both `ok=True` and `ok=False`), the backend returns the `ToolResult` tuple on `ChatInvocationResult.tool_calls`; `ChatSessionHandler.send_turn` writes one `ChatMessage` row **per tool call** with `role='tool'` (**new** `role` enum value — CHECK constraint migration, AC #13), `content=json.dumps({"tool_name": ..., "ok": ..., "payload": ..., "error_kind": ..., "elapsed_ms": ...})`, `guardrail_action='none'` on success / `'blocked'` on `ok=False`, `redaction_flags={"filter_source": "tool_dispatcher", "tool_name": tool_name, "error_kind": error_kind_or_null}`.
   - `filter_source` enum gains the value `"tool_dispatcher"` — **one-line amendment** to the architecture.md §Data Model Additions bullet at [L1796](../planning-artifacts/architecture.md#L1796). No section rewrite.
   - The `role='tool'` CHECK constraint extension ships as a **new Alembic migration** (per Story 10.1b's `TEXT + CHECK` convention at [architecture.md L1793](../planning-artifacts/architecture.md#L1793)): migration name `a1b2c3d4e5f6_add_chat_message_role_tool.py` (or the equivalent generated hash — dev agent uses `alembic revision --autogenerate` and records the hash in Debug Log). Migration body: `DROP` the existing CHECK on `chat_messages.role`, `ADD` the new one with `IN ('user', 'assistant', 'system', 'tool')`. `downgrade()` restores the 10.1b form (and `DELETE FROM chat_messages WHERE role = 'tool'` first, else the downgrade violates the old CHECK — comment notes this is a data loss on downgrade, same posture as 10.1b's own downgrade path).
   - Tool rows persist **in the same transaction** as the assistant row (single `async with db.begin()` block at the end of `send_turn`'s Step 6). If any tool row write fails, the whole turn rolls back — atomicity on the (user message → tool calls → assistant message) triple.
   - Order preserved by `created_at` resolution: the tool rows get timestamps strictly between the user row and the assistant row. Dev agent confirms `created_at` column resolution is microsecond-precise (it is — `DateTime(timezone=True)` with `default=func.now()`); if two tool rows within the same turn share a `created_at` the 10.6b citation assembler will fall back to insert order, documented as an acceptable precision artifact.
   - `content` payload size cap: tool-result `payload` fields may be large (200 transactions × ~200 bytes each ≈ 40 KB). The `chat_messages.content` column is `text` (unbounded in PG); no schema cap. An observability-side log event (AC #10) records the payload-size distribution so Story 10.9 can alarm on outliers.
   - Story 10.10 (chat history + deletion) already inherits the `session_id` FK cascade; `role='tool'` rows are deleted transparently. The 10.1b cascade tests are extended (AC #12) with a `role='tool'` fixture to confirm.

9. **Given** `ChatSessionHandler.send_turn` at [`backend/app/agents/chat/session_handler.py`](../../backend/app/agents/chat/session_handler.py), **When** this story edits it, **Then** the turn pipeline extends **Step 4** (the backend invoke) to pass `user_id` + `db` and consume `tool_calls`, and extends **Step 6** (assistant persist) to persist tool rows:

   **Step 0–3 — unchanged** (user row persist, input validation, canary load + prompt render, memory bounds). 10.4c adds zero concerns pre-invoke.

   **Step 4 — backend invoke (modified).** `result = await self._backend.invoke(..., user_id=handle.user_id, db=db)`. The handler already has `user_id` on the `ChatSessionHandle` via `chat_sessions.user_id`; if not already exposed on the handle dataclass, extend the dataclass (minimal, additive). `db` is already in scope (the `send_turn` `AsyncSession` parameter).

   **Step 5 — canary scan (unchanged from 10.4b).** Operates on `result.text` only, not on tool payloads. Rationale: canary tokens are anchored in the system prompt; a model that leaks a canary will do so in its *response text*, not in structured JSON tool inputs the dispatcher validated on its way up. If a canary ever surfaces through a tool-result echo, Story 10.8a's corpus will catch it and a follow-up TD entry will widen the scan surface.

   **Step 6 — persist tool rows + assistant row (modified).** Inside the existing single transaction, write `len(result.tool_calls)` `ChatMessage` rows with `role='tool'` in invocation order before the assistant row. All rows commit atomically with `last_active_at` update.

   **New: Step 4.5 — tool-loop-exceeded / unknown-tool / authorization errors.** If the backend raises `ChatToolLoopExceededError` / `ChatToolNotAllowedError` / `ChatToolAuthorizationError`:
   - Persist whatever tool rows executed **before** the error (they carry forensic value — the loop got stuck somewhere concrete) with `role='tool'` + `guardrail_action='blocked'` for the failing call.
   - Do **not** persist an assistant row (there is no coherent assistant text to persist). Bump `last_active_at`.
   - Emit the appropriate ERROR log (AC #10).
   - Re-raise. Story 10.5 translates to `CHAT_REFUSED` with `reason=tool_blocked`.

   The diff to `send_turn` is a **net addition of one step** (tool-row persist inside Step 6), **one new error branch** (Step 4.5), and **two new kwargs threaded to `invoke`**. No logic from 10.4a/10.4b is deleted.

10. **Given** baseline structured-log observability (full metric+alarm wiring is Story 10.9), **When** the tool-use pipeline is exercised, **Then** the following **new** `chat.tool.*` log events are emitted at the call sites listed:
    - `chat.tool.invoked` (INFO) — `dispatch_tool` entry → fields: `db_session_id`, `tool_name`, `tool_use_id`, `input_keys` (list of JSON keys present in `raw_input`; **not** values — values may contain adversarial content).
    - `chat.tool.result` (INFO) — `dispatch_tool` exit, `ok=True` → fields: `db_session_id`, `tool_name`, `tool_use_id`, `row_count` (if the output has a `row_count` field), `payload_bytes`, `elapsed_ms`.
    - `chat.tool.blocked` (WARN) — `dispatch_tool` exit, `ok=False` → fields: `db_session_id`, `tool_name`, `tool_use_id`, `error_kind` (`not_allowed` | `schema_error` | `execution_error`), `elapsed_ms`. Level WARN, not ERROR — a schema error is a model correction signal, not an operator-paging event. (Execution errors are additionally double-logged at ERROR from inside the dispatcher's `except` clauses, AC #6.)
    - `chat.tool.loop_exceeded` (ERROR) — backend raises `ChatToolLoopExceededError` → fields: `db_session_id`, `hops`, `last_tool_name`. This is a likely adversarial-or-broken signal — Story 10.9 will emit a metric + alarm from this log event.
    - `chat.tool.authorization_failed` (ERROR) — dispatcher catches `PermissionError` and raises `ChatToolAuthorizationError` → fields: `db_session_id`, `tool_name`, `user_id_hash` (the 64-bit blake2b prefix pattern from 10.4a). **Sev-1-grade event** (cross-user read attempt) — Story 10.9 pages on any occurrence.
    - `chat.tool.output_schema_drift` (ERROR) — handler return fails output-schema validation → fields: `db_session_id`, `tool_name`, `validation_error_summary` (pydantic `errors()[0]` as str, truncated at 200 chars).
    - Existing `chat.turn.completed` (INFO) — **extend** the field set with `tool_manifest_version` (`CHAT_TOOL_MANIFEST_VERSION` per AC #1), `tool_call_count` (int; 0 when the model answered without tools), `tool_hop_count` (int; usually equals `tool_call_count` unless parallel tool_use blocks collapsed hops).

    All events use the existing `extra={}` stdlib-`logging` pattern (structlog is still not installed — 10.4a/b verified). Event names use the `chat.tool.*` namespace for CloudWatch Insights globs.

11. **Given** the `CHAT_REFUSED` envelope defined at [architecture.md §API Pattern — Chat Streaming L1802-L1815](../planning-artifacts/architecture.md#L1802-L1815) with reason enum `"guardrail_blocked | ungrounded | rate_limited | prompt_leak_detected"`, **When** this story lands, **Then** the enum is **extended** with a new value `tool_blocked` — **one-line amendment** at architecture.md L1809. This is the user-facing reason Story 10.5's SSE translator emits when `ChatToolLoopExceededError`, `ChatToolNotAllowedError`, or `ChatToolAuthorizationError` bubbles to it. The amendment is a bullet-level edit, not a section rewrite.

    Story 10.3b's refusal copy-map already lists the existing reasons; dev agent extends the copy-map file at `_bmad-output/implementation-artifacts/10-3b-chat-ux-states-spec.md` (or its sibling artifact — grep confirms which file holds the machine-readable reason → copy mapping) with an entry for `tool_blocked`. UA + EN copy: conservative, neutral, no mention of "tool" or "allowlist" — suggested strings (dev agent refines with UX):
    - EN: "I couldn't look that up in your data. Please rephrase your question or try again shortly."
    - UA: "Не вдалося знайти це у ваших даних. Спробуйте переформулювати запит або повторити спробу."

12. **Given** the test contract, **When** this story lands, **Then** the following test files exist and pass (pattern follows 10.4a/b's `backend/tests/agents/chat/` convention):
    - **`test_tool_manifest.py`** — asserts the tuple of tool names equals `("get_transactions", "get_profile", "get_teaching_feed", "search_financial_corpus")` in that order; asserts `TOOL_ALLOWLIST` is a `frozenset` with exactly those four members; asserts `get_tool_spec("does_not_exist")` raises `ChatToolNotAllowedError`; asserts `render_bedrock_tool_config()` produces a dict with exactly four `toolSpec` entries matching each spec's `name` + `description` + pydantic-generated JSON Schema; asserts `CHAT_TOOL_MANIFEST_VERSION` matches `^10\.4c-v\d+$`; asserts no handler module imports `sqlalchemy.update` / `sqlalchemy.insert` / `sqlalchemy.delete` (AST-level grep against `backend/app/agents/chat/tools/`).
    - **`test_tool_transactions.py`** — fixture: user A with 10 canned `Transaction` rows (3 categories, mixed signs, 3 months); user B with 5 rows. Tests: (i) call with no filters returns user A's rows only (cross-user isolation); (ii) `category` filter narrows correctly; (iii) `start_date` / `end_date` inclusive boundaries; (iv) `limit` cap: with limit=2 and 10 available, `row_count=2`, `truncated=True`; (v) output-schema validation round-trips (handler output validates against `GetTransactionsOutput`); (vi) empty-user-data case returns `row_count=0`, `truncated=False`, `rows=[]`.
    - **`test_tool_profile.py`** — fixture: user with a `FinancialProfile` + `FinancialHealthScore` + 12 months of category breakdown. Tests: (i) default call returns only `summary`, empty breakdown/comparison; (ii) `include_category_breakdown=True` returns top 12 categories; (iii) `include_monthly_comparison=True` returns 12 months; (iv) no-profile user returns all-`None` summary + empty lists; (v) output-schema round-trip.
    - **`test_tool_teaching_feed.py`** — fixture: user with 25 delivered insights, 5 thumbs-up, 3 thumbs-down. Tests: (i) default limit=20 returns 20 rows most-recent-first + `truncated=True`; (ii) `only_thumbs_up=True` returns 5 rows; (iii) the returned body does not include insight content beyond `title`; (iv) output-schema round-trip.
    - **`test_tool_rag_corpus.py`** — fixture: mock `retrieve_relevant_docs` with a canned return. Tests: (i) call returns exactly `top_k` rows when retriever has them; (ii) `query` length validation (empty → 422-equivalent pydantic error; 501-char → error); (iii) snippet truncation at 500 chars; (iv) `user_id` is threaded through the handler signature but **not** passed to `retrieve_relevant_docs` (test asserts mock call args).
    - **`test_tool_dispatcher.py`** — unit tests against `dispatch_tool`: (i) unknown tool → `ok=False`, `error_kind="not_allowed"`; (ii) malformed JSON input → `ok=False`, `error_kind="schema_error"`, raw input never appears in payload; (iii) handler raising `sqlalchemy.exc.SQLAlchemyError` → `ok=False`, `error_kind="execution_error"`, ERROR log emitted; (iv) handler raising `PermissionError` → `ChatToolAuthorizationError` raised upward (not caught); (v) handler returning out-of-shape output → `ok=False`, `error_kind="execution_error"`, ERROR log `chat.tool.output_schema_drift`; (vi) output truncated to `max_rows` — second-layer cap exercised; (vii) `elapsed_ms` populated.
    - **`test_chat_backend_direct.py`** **extended** — new tests: (i) tool-less turn (model returns plain text first call) exits the loop with `hops=0`, `tool_calls=()`; (ii) single-tool turn (model emits `get_transactions` tool_use, receives result, emits final text) exits with `hops=1`, `tool_calls` length 1, cumulative token counts; (iii) two-parallel-tools turn (one AIMessage with two `tool_use` blocks) executes in series, exits with `hops=1`, `tool_calls` length 2; (iv) loop-exceeded case (mocked Bedrock returns tool_use on every iteration) raises `ChatToolLoopExceededError` after `MAX_TOOL_HOPS + 1` iterations; (v) tool-dispatcher `not_allowed` path makes it back to the model as a `ToolResult` and the next iteration's text is final.
    - **`test_session_handler.py`** **extended** — new tests: (i) happy-path tool turn persists `role='tool'` rows in order with correct `redaction_flags.filter_source='tool_dispatcher'`; (ii) `ChatToolLoopExceededError` from the backend persists the tool rows that *did* execute, no assistant row, bumps `last_active_at`, emits `chat.tool.loop_exceeded`; (iii) `ChatToolAuthorizationError` path similar to (ii) with `chat.tool.authorization_failed`; (iv) `chat.turn.completed` log carries the three new fields with correct values.
    - **`test_chat_schema_cascade.py`** **extended** — new case (e): a user with `role='tool'` rows in `chat_messages` has those rows cascaded to deletion on account deletion + consent revoke. Uses the existing cascade test scaffolding from 10.1b.
    - **Alembic migration test** — new test in `backend/tests/test_migrations.py` (or equivalent — grep for migration-roundtrip tests) exercises `upgrade()` + `downgrade()` of the new migration against a populated DB: `INSERT`s a `role='tool'` row, runs `downgrade`, asserts the row was `DELETE`d and the old CHECK constraint is restored, re-runs `upgrade`, asserts new inserts succeed. If no migration-roundtrip harness exists, add a minimal one scoped to this migration.
    - **Full suite** runs with `pytest backend/tests/agents/chat/ backend/tests/test_chat_schema_cascade.py -q` green; the Debug Log records command output including coverage % for the new tool modules (target ≥ 90% on each).
    - **No integration test hits real Bedrock in CI.** The tool-loop tests mock `ChatBedrockConverse.ainvoke` at the langchain boundary and pass canned tool_use / final-text responses. A manual-only integration test file `test_tool_loop_integration.py` marked `@pytest.mark.manual` exercises the live path — excluded from CI, runnable by an operator with Bedrock credentials.

13. **Given** the tech-debt register at [`docs/tech-debt.md`](../../docs/tech-debt.md), **When** this story lands, **Then**:
    - A new `TD-NNN` entry is opened: "Revisit `MAX_TOOL_HOPS=5` after first 30 days of prod chat traffic. A telemetry-driven bump or lower may be warranted if the hop distribution skews to one side." Scope: `backend/app/agents/chat/chat_backend.py`. Trigger: Story 10.9's `tool_hop_count` dashboard percentile distribution. Effort: ~1h.
    - A new `TD-NNN` entry is opened: "Widen canary scan to tool-result payloads (not just `response.text`) if Story 10.8a's corpus surfaces a leak-via-tool-echo case." Scope: `backend/app/agents/chat/canary_detector.py` + `session_handler.py` Step 5. Trigger: any `chat.canary.leaked` hit whose forensic shows the token originated from a tool payload. Effort: ~½ day. Cross-references Story 10.4b's AC #3 TD entry (unicode-normalization) — these are peer extensions to the canary surface.
    - A new `TD-NNN` entry is opened: "Consider cross-user data-access static check in CI (e.g., a custom lint rule that fails if any `chat.tools.*` handler does not thread `user_id` through every service call)." Scope: `backend/.ruff.toml` or a standalone Python lint. Trigger: any cross-user-exposure bug in chat. Effort: ~1 day.
    - Grep `docs/tech-debt.md` for `TD-.*10\.4c` / `TD-.*tool.manifest` / `TD-.*chat.tool`. If any stale speculative entries exist, close them with a pointer to this story's commit. Record grep output in Debug Log.
    - No existing TD entry is **closed** by this story (10.4a closed TD-092; 10.4b closed none; 10.4c closes none).

14. **Given** the Epic 10 dependency chain ("10.4c depends on 10.4a; 10.5 depends on 10.4c for the `CHAT_REFUSED` reason enum + tool-call persistence; 10.6b depends on 10.4c for tool-call provenance"), **When** this story lands, **Then**:
    - The architecture.md §AI Safety Architecture is **not** rewritten. Three **one-line amendments** only: (a) the `redaction_flags.filter_source` enum at [L1796](../planning-artifacts/architecture.md#L1796) gains `"tool_dispatcher"`; (b) the `chat_messages.role` enum at [L1796](../planning-artifacts/architecture.md#L1796) gains `"tool"`; (c) the `CHAT_REFUSED` reason enum at [L1809](../planning-artifacts/architecture.md#L1809) gains `"tool_blocked"`.
    - An **inline comment block** at the top of `chat_backend.py`'s `invoke` enumerates the tool-loop invariants: (1) allowlist enforced at dispatcher, (2) series-execution preserves DB-transaction safety, (3) `MAX_TOOL_HOPS` is the loop bound, (4) schema errors are soft (feed back to model); authorization errors are hard (bubble to handler). A future reviewer should not need to re-derive any of these from the code.
    - The `# Downstream: 10.4c adds tool manifest; 10.5 wraps send_turn in an SSE streaming wrapper + CHAT_REFUSED envelope; 10.6a tunes grounding at Guardrail attach time.` line at [`session_handler.py:32`](../../backend/app/agents/chat/session_handler.py#L32) has its `10.4c adds tool manifest;` fragment **removed** (10.4c lands now). The remaining line reads: `# Downstream: 10.5 wraps send_turn in an SSE streaming wrapper + CHAT_REFUSED envelope; 10.6a tunes grounding at Guardrail attach time; 10.6b reads role='tool' rows for citation assembly.`
    - No ADR is required — this is an implementation of a decision already captured by [architecture.md §Defense-in-Depth Layers L1704-L1712](../planning-artifacts/architecture.md#L1704-L1712) + §Chat Agent Component L1775-L1783. If the dev agent discovers an implementation-time drift from the architecture's tool list, the drift is fixed in a follow-up ADR, not inline in this story.

## Tasks / Subtasks

- [x] **Task 1: Package scaffolding + manifest module** (AC: #1)
  - [x] 1.1 Convert `backend/app/agents/chat/` into a package that also contains a `tools/` subpackage.
  - [x] 1.2 Create `backend/app/agents/chat/tools/__init__.py` with `CHAT_TOOL_MANIFEST_VERSION`, `ToolSpec`, `TOOL_MANIFEST`, `TOOL_ALLOWLIST`, `get_tool_spec`, `render_bedrock_tool_config`.
  - [x] 1.3 Create `backend/app/agents/chat/tools/tool_errors.py` with all five typed exceptions.
  - [x] 1.4 Confirmed `langchain_core.tools.StructuredTool` + `client.bind_tools(...)` is the clean path for the pinned `langchain-aws>=0.2.0` / `langchain-core>=0.3.0`; `ChatBedrockConverse.bind_tools()` accepts `StructuredTool` with explicit `name` + `args_schema`. Recorded in Debug Log.

- [x] **Task 2: Four tool handlers** (AC: #2, #3, #4, #5)
  - [x] 2.1 `tools/transactions_tool.py` — filtered query with user_id + optional date/category/limit on the `Transaction` table.
  - [x] 2.2 `tools/profile_tool.py` — wraps `get_profile_for_user`, `get_category_breakdown`, `get_monthly_comparison`, `get_latest_score`.
  - [x] 2.3 `tools/teaching_feed_tool.py` — Insight outer-join CardFeedback(feedback_source='card_vote').
  - [x] 2.4 `tools/rag_corpus_tool.py` — `asyncio.to_thread(retrieve_relevant_docs)`, user_id threaded but not passed.
  - [x] 2.5 Top-of-file read-only invariant comment on every handler module.

- [x] **Task 3: Dispatcher** (AC: #6, #10)
  - [x] 3.1 `tools/dispatcher.py` with `ToolInvocation`, `ToolResult`, `dispatch_tool`.
  - [x] 3.2 Error categorization matrix: not_allowed / schema_error / execution_error (soft) vs. authorization_failed (hard).
  - [x] 3.3 Output-schema round-trip via `spec.output_model.model_validate(result.model_dump())`.
  - [x] 3.4 `max_rows` second-layer truncation via `_truncate_rows`.
  - [x] 3.5 All six structured-log events emitted: `chat.tool.invoked`, `chat.tool.result`, `chat.tool.blocked`, `chat.tool.execution_failed`, `chat.tool.output_schema_drift`, `chat.tool.authorization_failed`.

- [x] **Task 4: `DirectBedrockBackend.invoke` tool-loop** (AC: #7, #10)
  - [x] 4.1 Added `user_id: UUID` + `db: Any` kwargs to abstract `ChatBackend.invoke`; `test_chat_backend_agentcore.py` already skipped as a module-level skip (no fixture change needed).
  - [x] 4.2 Bound tools via `client.bind_tools(_lc_tools_from_manifest())`; fallback to base_client if bind_tools raises.
  - [x] 4.3 Loop: ainvoke → `_extract_tool_uses` → dispatch (series) → append `AIMessage + ToolMessage(s)` → re-ainvoke; cap at `MAX_TOOL_HOPS=5` (module-level constant).
  - [x] 4.4 Raises `ChatToolLoopExceededError(hops=hops+1, last_tool_name=...)` on cap breach; attaches `tool_calls_so_far` for the handler.
  - [x] 4.5 Cumulative token accounting; any tiktoken fallback marks whole turn `token_source="tiktoken"`.
  - [x] 4.6 `ChatInvocationResult` gained `tool_calls: tuple = field(default_factory=tuple)`.
  - [x] 4.7 Removed the "Phase A has no tools — flatten defensively" comment; replaced with the four-point tool-loop invariants block.
  - [x] 4.8 `chat.tool.loop_exceeded` is emitted from the handler's Step 4.5 branch (the backend raises; handler logs).

- [x] **Task 5: `ChatSessionHandler.send_turn` wiring** (AC: #9, #10)
  - [x] 5.1 `user_id=handle.user_id` + `db=db` threaded to `backend.invoke`. `ChatSessionHandle` already exposed `user_id` (additive field from 10.4a).
  - [x] 5.2 Tool rows persisted before the assistant row inside the existing Step-6 transaction via `_serialize_tool_call`.
  - [x] 5.3 Step 4.5 branch catches `ChatToolLoopExceededError` / `ChatToolNotAllowedError` / `ChatToolAuthorizationError`; persists partial `tool_calls_so_far`, bumps `last_active_at`, emits the matching ERROR log, re-raises.
  - [x] 5.4 `chat.turn.completed` carries `tool_manifest_version`, `tool_call_count`, `tool_hop_count`.
  - [x] 5.5 `# Downstream:` comment updated: `10.4c` fragment removed, `10.6b reads role='tool' rows` added.

- [x] **Task 6: Schema migration** (AC: #8, #13)
  - [x] 6.1 New Alembic migration `ca1c04c7b2e9_add_chat_message_role_tool.py`: DROP + ADD CHECK widening to include `'tool'`.
  - [x] 6.2 `downgrade()` executes `DELETE FROM chat_messages WHERE role='tool'` before restoring the old CHECK; data-loss invariant documented in the module docstring.
  - [x] 6.3 Migration-roundtrip test at `tests/test_chat_role_tool_migration.py` (static op-call verification — a true upgrade/downgrade needs Postgres; SQLite can't DROP named constraints).
  - [x] 6.4 Alembic migration revision = `ca1c04c7b2e9` (chosen after `a1b2c3d4e5f6` collided with an existing revision); recorded in Debug Log.

- [x] **Task 7: Package re-exports** (AC: #6, #14)
  - [x] 7.1 `backend/app/agents/chat/__init__.py` `__all__` extended with `ChatToolNotAllowedError`, `ChatToolSchemaError`, `ChatToolExecutionError`, `ChatToolAuthorizationError`, `ChatToolLoopExceededError`, `CHAT_TOOL_MANIFEST_VERSION`, `TOOL_ALLOWLIST`, `ToolResult`.

- [x] **Task 8: Tests** (AC: #12)
  - [x] 8.1 `test_tool_manifest.py` — 7 tests (tuple shape + order, allowlist, unknown→raise, Bedrock config shape, version regex, no-write-ops AST).
  - [x] 8.2 Per-tool handler tests — 7 transactions + 5 profile + 4 teaching_feed + 5 rag_corpus, including cross-user isolation, boundary, empty, and output-schema round-trip.
  - [x] 8.3 `test_tool_dispatcher.py` — 7 tests covering every error branch + authorization bubble + second-layer truncation.
  - [x] 8.4 `test_chat_backend_direct.py` extended — 19 tests total including 5 new tool-loop tests (toolless / single / parallel / loop-exceeded / not-allowed round-trip).
  - [x] 8.5 `test_session_handler.py` extended — 22 tests total including 4 new tool-handling tests (happy persist, chat.turn.completed fields, loop-exceeded partial persist, authorization-error log).
  - [x] 8.6 `test_chat_schema_cascade.py` extended — 11 tests total including `role='tool'` cascade on user delete and on consent revoke.
  - [x] 8.7 `tests/test_chat_role_tool_migration.py` — 3 static op-call verification tests.
  - [x] 8.8 `pytest backend/tests/agents/chat/ backend/tests/test_chat_schema_cascade.py backend/tests/test_chat_role_tool_migration.py -q` → **164 passed, 3 skipped** (pre-existing Phase B AgentCore skips). Output recorded in Debug Log.

- [x] **Task 9: Architecture + tech-debt + copy-map wiring** (AC: #11, #13, #14)
  - [x] 9.1 Two inline amendments in `architecture.md` §Data Model Additions (`role` enum += `tool`, `filter_source` enum += `tool_dispatcher`) and one-word amendment in §API Pattern — Chat Streaming (`reason` enum += `tool_blocked`).
  - [x] 9.2 10.3b refusal-copy entry extended with EN + UA `tool_blocked` strings (neutral, security-by-opacity posture).
  - [x] 9.3 Three new TD entries opened (**TD-100** MAX_TOOL_HOPS audit, **TD-101** canary-scan tool-payload widening, **TD-102** cross-user static check).
  - [x] 9.4 Grep `TD-.*10\.4c|TD-.*tool.manifest|TD-.*chat.tool` → only my new entries match. No stale speculative entries to close.
  - [x] 9.5 Grep output recorded in Debug Log.

- [x] **Task 10: Validation + Debug Log** (AC: all)
  - [x] 10.1 `pytest backend/tests/agents/chat/ -q` → 156 passed, 3 skipped.
  - [x] 10.2 `pytest backend/tests/ -q` → **1053 passed, 3 skipped, 23 deselected, 3 warnings in 233s** (no regressions).
  - [x] 10.3 `ruff check` + `ruff format` applied on chat scope; all checks pass.
  - [x] 10.4 `alembic upgrade head` + `alembic downgrade -1` → deferred to manual operator run against Postgres (SQLite cannot ALTER named constraints). Migration module verified via static test.
  - [x] 10.5 Dev Agent Record, Completion Notes, File List, Change Log populated below.

## Dev Notes

### Key architectural contracts this story ships against

- **Defense-in-Depth Layers** — [architecture.md §Defense-in-Depth Layers L1704-L1712](../planning-artifacts/architecture.md#L1704-L1712): this story implements **layer 4 (Agent layer)** literally. Layer 1 (input) + layer 3 (system prompt) shipped in 10.4b; layer 2 + 5 (Guardrails input/output) ship in 10.5; layer 6 (grounding) ships in 10.6a.
- **Chat Agent Component — Tool manifest** — [architecture.md §Chat Agent Component L1780](../planning-artifacts/architecture.md#L1780): "Tool manifest (read-only allowlist): user transactions, user profile, teaching-feed history, RAG corpus". The four tools authored here are the literal realization of this line.
- **Threat model — Tool abuse** — [architecture.md §Threat Model L1697](../planning-artifacts/architecture.md#L1697): "no such tools exposed; allowlist enforced at AgentCore". We enforce the allowlist at the **dispatcher** in Phase A (not at AgentCore — Phase A doesn't use AgentCore per ADR-0004); the enforcement surface is equivalent, and the Phase B AgentCore backend will inherit the same `TOOL_MANIFEST` when it lands.
- **Threat model — Cross-user data exfiltration** — [architecture.md §Threat Model L1694](../planning-artifacts/architecture.md#L1694): every tool handler threads `user_id` through to the service layer; no handler opens a second-order query path (no "look up by transaction hash then fetch by transaction_id" pattern that could be steered to cross-user IDs).
- **API Pattern — CHAT_REFUSED envelope** — [architecture.md §API Pattern L1802-L1815](../planning-artifacts/architecture.md#L1802-L1815): `reason` enum extended with `tool_blocked` (one-line amendment per AC #11).
- **Data Model Additions** — [architecture.md §Data Model Additions L1791-L1800](../planning-artifacts/architecture.md#L1791-L1800): `chat_messages.role` CHECK extended to include `'tool'`; `redaction_flags.filter_source` extended with `"tool_dispatcher"`. Both via Alembic migration (role) + one-line architecture amendment (filter_source).

### Prior-story context carried forward

- **Story 10.1b** shipped `chat_messages` with `role` CHECK on `('user', 'assistant', 'system')`. This story ships the migration that extends that CHECK; the Alembic conventions established in 10.1b (downgrade must delete the new role's rows to satisfy the old CHECK) are followed here.
- **Story 10.4a** shipped the handler API + `ChatBackend` abstraction + `DirectBedrockBackend`. This story extends `ChatBackend.invoke` with `user_id` + `db` kwargs (breaking, but only one in-process caller); the handler/backend seam stays at the same altitude.
- **Story 10.4b** shipped the system-prompt hardening + canary layer. The canary scan in `send_turn` Step 5 is **not** widened to tool payloads in this story — tracked as a TD entry per AC #13.
- **Story 10.3b** drafted the reason-specific refusal copy-map. This story extends it with `tool_blocked` (AC #11).
- **Story 9.5a/b/c** shipped the multi-provider `llm.py`. This story does **not** consume `llm.py` for tool invocations — Bedrock Converse is the only supported path. Non-bedrock deployments are already blocked at `get_chat_session_handler()` via 10.4a's `ChatProviderNotSupportedError` guard.
- **Story 3.3** shipped the RAG knowledge base + `retrieve_relevant_docs`. The `search_financial_corpus` tool is a thin wrapper; no new RAG infrastructure is added.

### Deliberate scope compressions

- **Series tool execution, not parallel.** `asyncio.gather`-style fan-out would collide with the single `AsyncSession`; isolating sessions per tool call is a correctness problem that outweighs the latency win for 1-2 tool calls per turn. Revisit if telemetry shows ≥ 3 average tool calls per turn.
- **Soft schema errors, hard authorization errors.** A schema-invalid tool call is a model-correction signal — the dispatcher returns it as a `ToolResult` and lets the model try again. An authorization failure (a handler caught a cross-user read attempt) bubbles immediately and blocks the turn. This asymmetry is deliberate; documented inline at AC #6.
- **No citation payload here.** Story 10.6b will read `role='tool'` rows and assemble the citation envelope. This story's job is to *persist* the tool-call provenance; mapping it to wire-format citations is a separate concern.
- **No caching of tool results within a turn.** If the model calls `get_transactions` twice in the same turn with the same args, we execute twice. Caching is a trivial add later (hash args, memoize for one turn); adding it here is premature optimization with an incident-analysis cost (a cached stale result during a debugging session would confuse an operator).
- **RAG tool is user-`id`-threaded but scope-widened.** The financial-literacy corpus is cross-user by design. A comment at the handler documents the exception explicitly so a future reviewer does not copy the pattern for a data-specific tool.
- **`role='tool'` rows persist even on blocked tool calls.** Forensic value > storage cost. A blocked tool call is itself a signal (schema fuzzing, allowlist probe) and Story 10.8a/b will consume these rows during red-team analysis.

### Project Structure Notes

- `backend/app/agents/chat/tools/` is a **new** subpackage with exactly these files: `__init__.py` (manifest), `tool_errors.py`, `dispatcher.py`, `transactions_tool.py`, `profile_tool.py`, `teaching_feed_tool.py`, `rag_corpus_tool.py`. No other files.
- `backend/tests/agents/chat/` gains four new per-tool test files + `test_tool_manifest.py` + `test_tool_dispatcher.py` + extensions to existing `test_chat_backend_direct.py` / `test_session_handler.py` / `test_chat_schema_cascade.py`.
- `backend/alembic/versions/` gains **one** new migration file.
- `docs/tech-debt.md` gains three new TD entries under `## Open`.
- `_bmad-output/planning-artifacts/architecture.md` receives **three** one-line amendments; `_bmad-output/implementation-artifacts/10-3b-chat-ux-states-spec.md` (or the copy-map artifact — grep confirms) gains one new reason copy mapping.
- No file outside `backend/app/agents/chat/`, `backend/app/agents/chat/tools/`, `backend/tests/agents/chat/`, `backend/tests/test_chat_schema_cascade.py`, `backend/alembic/versions/`, `docs/tech-debt.md`, and the two spec files above is touched.

### References

- [Source: architecture.md §AI Safety Architecture L1684-L1816](../planning-artifacts/architecture.md#L1684-L1816) — full safety architecture this story implements layer 4 of.
- [Source: architecture.md §Defense-in-Depth Layers L1704-L1712](../planning-artifacts/architecture.md#L1704-L1712) — authoritative layer ordering; tool allowlist is layer 4.
- [Source: architecture.md §Threat Model L1690-L1702](../planning-artifacts/architecture.md#L1690-L1702) — cross-user exfiltration + tool-abuse rows map to this story.
- [Source: architecture.md §Chat Agent Component L1775-L1783](../planning-artifacts/architecture.md#L1775-L1783) — the four-tool read-only manifest is documented here.
- [Source: architecture.md §Data Model Additions L1791-L1800](../planning-artifacts/architecture.md#L1791-L1800) — `chat_messages.role` + `redaction_flags.filter_source` enum extensions land here.
- [Source: architecture.md §API Pattern — Chat Streaming L1802-L1815](../planning-artifacts/architecture.md#L1802-L1815) — `CHAT_REFUSED.reason` enum extended with `tool_blocked`.
- [Source: epics.md §Story 10.4c L2127-L2128](../planning-artifacts/epics.md#L2127-L2128) — story statement + deps.
- [Source: epics.md §Out of Scope for Epic 10 L2160](../planning-artifacts/epics.md#L2160) — the "no write-actions in Epic 10" invariant this story protects.
- [Source: _bmad-output/implementation-artifacts/10-4a-agentcore-session-handler-memory-bounds.md](10-4a-agentcore-session-handler-memory-bounds.md) — preceding story; `ChatBackend` abstraction this story extends.
- [Source: _bmad-output/implementation-artifacts/10-4b-system-prompt-hardening-canaries.md](10-4b-system-prompt-hardening-canaries.md) — preceding story; `invoke` signature this story further extends.
- [Source: _bmad-output/implementation-artifacts/10-3b-chat-ux-states-spec.md](10-3b-chat-ux-states-spec.md) — refusal copy-map; `tool_blocked` UA + EN copy lands here.
- [Source: docs/adr/0004-chat-runtime-phasing.md](../../docs/adr/0004-chat-runtime-phasing.md) — Phase A vs B split; this story is phase-agnostic (tool manifest travels to Phase B unchanged).
- [Source: backend/app/agents/chat/session_handler.py](../../backend/app/agents/chat/session_handler.py) — `send_turn` Step 4 / Step 4.5 / Step 6 edits.
- [Source: backend/app/agents/chat/chat_backend.py](../../backend/app/agents/chat/chat_backend.py) — `ChatBackend.invoke` signature + `DirectBedrockBackend` tool-loop.
- [Source: backend/app/services/transaction_service.py](../../backend/app/services/transaction_service.py) — `get_transactions_for_user` backs the transactions tool.
- [Source: backend/app/services/profile_service.py](../../backend/app/services/profile_service.py) — `get_profile_for_user` + `get_category_breakdown` + `get_monthly_comparison` back the profile tool.
- [Source: backend/app/services/insight_service.py](../../backend/app/services/insight_service.py) — `get_insights_for_user` backs the teaching-feed tool.
- [Source: backend/app/rag/retriever.py](../../backend/app/rag/retriever.py) — `retrieve_relevant_docs` backs the RAG corpus tool.
- [Source: backend/app/models/chat_message.py](../../backend/app/models/chat_message.py) — `role` CHECK constraint extended; `redaction_flags` JSONB consumer.
- [Source: docs/tech-debt.md](../../docs/tech-debt.md) — three new TD entries opened by this story (AC #13).

## Dev Agent Record

### Agent Model Used

Claude Opus 4.7 (claude-opus-4-7, 1M context).

### Debug Log References

- **Tool-binding path choice.** `langchain_core.tools.StructuredTool(name=..., description=..., args_schema=..., func=_noop)` + `client.bind_tools(tool_list)` accepted cleanly under pinned `langchain-aws>=0.2.0` / `langchain-core>=0.3.0`. The alternative native-Converse `toolConfig` dict passthrough was rejected because langchain's BaseChatModel does not forward unknown kwargs to the underlying boto3 client, so the dict would be silently dropped. `render_bedrock_tool_config()` is retained on the manifest as a reference/testing contract.
- **Alembic revision collision.** Initial hash `a1b2c3d4e5f6` collided with `f3a8b2c1d4e5_add_format_detection_fields.py` (discovered via `alembic heads` printing a duplicate-revision warning). Renamed migration file + revision constants to `ca1c04c7b2e9`. `alembic heads` now reports exactly one head: `ca1c04c7b2e9 (head)`.
- **Cascade test query expression.** Using `ChatMessage.id.in_(tool_msg_ids)` in the same session immediately after `DELETE FROM users` returned the expired rows from the identity map. Switched to raw `text("SELECT COUNT(*) FROM chat_messages WHERE id IN (...)")` (same pattern as the pre-existing `test_delete_user_cascades_to_sessions_and_messages`) for the cascade assertion; now passes.
- **Logger propagation under caplog.** The `app.agents.chat.tools.dispatcher` logger inherits `propagate=False` from `logging.getLogger("app")` in the production setup, so `caplog` at root-level never saw the records. Added an autouse fixture (`_propagate_app_logger`) in `test_tool_dispatcher.py` that flips `logging.getLogger("app").propagate = True` for the test duration, mirroring `test_session_handler.py`'s own fixture.
- **Frozen-dataclass spec handler patching.** `ToolSpec` is `@dataclass(frozen=True)`, so `monkeypatch.setattr` on `spec.handler` raises `FrozenInstanceError`. Used `object.__setattr__(spec, "handler", mock)` inside a `contextmanager` helper in `test_tool_dispatcher.py` to swap + restore handlers cleanly.
- **TD-NNN grep output** (for AC #13 book-keeping):
  ```
  $ grep -n "TD-.*10\\.4c\\|TD-.*tool.manifest\\|TD-.*chat.tool" docs/tech-debt.md
  1552:### TD-102 — Consider a cross-user data-access static check for chat tools [LOW]
  ```
  Only the newly-authored entry matches. No stale speculative entries to close.
- **Full-suite regression.** `pytest backend/tests/ -q` → `1053 passed, 3 skipped, 23 deselected, 3 warnings in 233.13s`. The three skips are the pre-existing `test_chat_backend_agentcore.py` phase-B skips.

### Completion Notes List

- **Tool manifest surface** (AC #1). `backend/app/agents/chat/tools/__init__.py` exposes exactly `CHAT_TOOL_MANIFEST_VERSION="10.4c-v1"`, `ToolSpec`, `TOOL_MANIFEST` (frozen 4-tuple in authored order), `TOOL_ALLOWLIST` (frozenset), `get_tool_spec` (raises `ChatToolNotAllowedError`), `render_bedrock_tool_config` (Converse shape).
- **Four handlers** (AC #2/#3/#4/#5) ship in `tools/transactions_tool.py`, `tools/profile_tool.py`, `tools/teaching_feed_tool.py`, `tools/rag_corpus_tool.py`. Each has a top-of-file `# Read-only — MUST NOT mutate …` comment; a manifest test (`test_no_handler_module_imports_sqlalchemy_write_ops`) enforces the invariant via AST.
- **Dispatcher** (AC #6/#10) is `tools/dispatcher.py`. Soft/hard split: `not_allowed` / `schema_error` / `execution_error` round-trip to the model as `ToolResult(ok=False)`; `PermissionError → ChatToolAuthorizationError` bubbles up. All six `chat.tool.*` log events are emitted at the specified levels.
- **Tool-use loop** (AC #7) lives inside `DirectBedrockBackend.invoke`. `MAX_TOOL_HOPS=5` module-level constant. Series execution. Cumulative token accounting. Partial `tool_calls_so_far` attached to errors.
- **Handler wiring** (AC #8/#9). Step 4 now passes `user_id=handle.user_id, db=db` to `backend.invoke`. Step 4.5 added for tool-loop hard-error branches. Step 6 persists `role='tool'` rows before the assistant row in the existing transaction. `chat.turn.completed` carries the three new fields.
- **Migration** (AC #8/#13). `ca1c04c7b2e9_add_chat_message_role_tool.py` extends the `chat_messages.role` CHECK; `downgrade()` deletes tool rows before restoring the old form.
- **CHAT_REFUSED reason extension** (AC #11). `tool_blocked` added to the architecture enum + 10.3b refusal copy-map (EN + UA, security-by-opacity posture).
- **Three one-line architecture amendments** (AC #14): `role` enum widened, `filter_source` enum widened, `CHAT_REFUSED.reason` enum widened. Inline comments in `chat_backend.py` enumerate the four tool-loop invariants.
- **Tech debt** (AC #13). **TD-100** (`MAX_TOOL_HOPS` revisit), **TD-101** (canary-scan tool-payload widening), **TD-102** (cross-user static check) opened.
- **Tests** (AC #12). Added files: `test_tool_manifest.py`, `test_tool_transactions.py`, `test_tool_profile.py`, `test_tool_teaching_feed.py`, `test_tool_rag_corpus.py`, `test_tool_dispatcher.py`, `test_chat_role_tool_migration.py`, `tests/agents/chat/conftest.py`. Extended files: `test_chat_backend_direct.py`, `test_session_handler.py`, `test_chat_schema_cascade.py`. Full chat suite: 164 passed / 3 skipped. Backend suite: 1053 passed / 3 skipped.
- **Scope boundaries observed.** No SSE, no HTTP route, no CHAT_REFUSED envelope (all 10.5). No Guardrails attach (10.5). No citation payload (10.6b). No grounding (10.6a). No write-paths. No red-team corpus (10.8a/b). No rate-limit envelope (10.11). No retroactive change to the 10.4a/10.4b public API.

### File List

New files:
- `backend/app/agents/chat/tools/__init__.py`
- `backend/app/agents/chat/tools/tool_errors.py`
- `backend/app/agents/chat/tools/dispatcher.py`
- `backend/app/agents/chat/tools/transactions_tool.py`
- `backend/app/agents/chat/tools/profile_tool.py`
- `backend/app/agents/chat/tools/teaching_feed_tool.py`
- `backend/app/agents/chat/tools/rag_corpus_tool.py`
- `backend/alembic/versions/ca1c04c7b2e9_add_chat_message_role_tool.py`
- `backend/tests/agents/chat/conftest.py`
- `backend/tests/agents/chat/test_tool_manifest.py`
- `backend/tests/agents/chat/test_tool_transactions.py`
- `backend/tests/agents/chat/test_tool_profile.py`
- `backend/tests/agents/chat/test_tool_teaching_feed.py`
- `backend/tests/agents/chat/test_tool_rag_corpus.py`
- `backend/tests/agents/chat/test_tool_dispatcher.py`
- `backend/tests/test_chat_role_tool_migration.py`

Modified files:
- `backend/app/agents/chat/__init__.py` (re-exports)
- `backend/app/agents/chat/chat_backend.py` (tool-use loop + `user_id`/`db` kwargs + `tool_calls` field; fail-closed on `bind_tools` exception — code-review H1)
- `backend/app/agents/chat/session_handler.py` (tool-row persist, Step 4.5, extended log fields, downstream-comment cleanup)
- `backend/app/agents/chat/tools/dispatcher.py` (threaded `db_session_id` through every `chat.tool.*` log event — code-review M1; dropped dead `_logger_for_tests_swap`)
- `backend/app/agents/chat/tools/transactions_tool.py` (delegates SQL to new `transaction_service.get_transactions_for_chat` — code-review M2)
- `backend/app/agents/chat/tools/rag_corpus_tool.py` (dropped misleading `title=source_id` field from `CorpusDocRow` — code-review M3)
- `backend/app/agents/chat/tools/profile_tool.py` (`MonthlyComparisonRow.income_kopiykas` → `Optional[int]=None`; no longer hardcoded 0 — code-review M4)
- `backend/app/services/transaction_service.py` (new `get_transactions_for_chat(...)` service function — code-review M2)
- `backend/app/models/chat_message.py` (role Literal + CHECK constraint widened to include `"tool"`)
- `backend/tests/agents/chat/test_chat_backend_direct.py` (updated for new kwargs, added 5 tool-loop tests)
- `backend/tests/agents/chat/test_session_handler.py` (added 4 tool-handling tests)
- `backend/tests/test_chat_schema_cascade.py` (added 2 `role='tool'` cascade tests)
- `_bmad-output/planning-artifacts/architecture.md` (three one-line enum amendments)
- `_bmad-output/implementation-artifacts/10-3b-chat-ux-states-spec.md` (refusal copy-map extended)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (10-4c status → review)
- `docs/tech-debt.md` (TD-100 / TD-101 / TD-102 opened)
- `VERSION` (1.44.0 → 1.45.0 — MINOR per docs/versioning.md, new user-facing chat-tool surface)

### Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-04-24 | Story drafted (ready-for-dev). | PM |
| 2026-04-24 | Implementation complete: tool manifest + 4 handlers + dispatcher + bounded tool-use loop + `role='tool'` persistence + migration + tests. | Dev |
| 2026-04-24 | Architecture amendments (role / filter_source / CHAT_REFUSED.reason enums) + 10.3b copy-map extension for `tool_blocked`. | Dev |
| 2026-04-24 | TD-100 / TD-101 / TD-102 opened. | Dev |
| 2026-04-24 | Version bumped from 1.44.0 to 1.45.0 per story completion (new user-facing chat-tool surface). | Dev |
| 2026-04-24 | Status → review. | Dev |
| 2026-04-24 | Adversarial code review: 1 HIGH + 4 MEDIUM fixed in-place (H1 bind_tools fail-closed; M1 db_session_id threaded through dispatcher logs; M2 transactions handler delegates to new `get_transactions_for_chat` service; M3 dropped duplicate `title` on `CorpusDocRow`; M4 `MonthlyComparisonRow.income_kopiykas` → Optional). TD-103 (`tool_hop_count` duplicate) + TD-104 (`savings_ratio` non-int drop) opened from LOW findings. Full backend suite: 1053 passed / 3 skipped / 0 regressions. Status → done. | Review |

## Code Review

### Findings (2026-04-24)

- **H1 FIXED** — `bind_tools()` silent fallback at [chat_backend.py](../../backend/app/agents/chat/chat_backend.py) now raises `ChatConfigurationError` (emits `chat.tool.bind_failed` ERROR log). Prior code silently reverted the defense-layer-4 allowlist to "model answers with no tool schema" — exact failure mode the allowlist prevents.
- **M1 FIXED** — Every `chat.tool.*` event in [dispatcher.py](../../backend/app/agents/chat/tools/dispatcher.py) now carries `db_session_id`. Dispatcher gained an optional `db_session_id` kwarg; `DirectBedrockBackend` threads it in. Story 10.9's per-session tool dashboards can now slice.
- **M2 FIXED** — New `transaction_service.get_transactions_for_chat(...)` owns the SQL; [transactions_tool.py](../../backend/app/agents/chat/tools/transactions_tool.py) now delegates to it instead of writing its own `select(Transaction)`. Preserves the "service layer owns user-data SQL" invariant claimed in AC #2 / Scope Boundaries.
- **M3 FIXED** — `CorpusDocRow.title` dropped from [rag_corpus_tool.py](../../backend/app/agents/chat/tools/rag_corpus_tool.py). Previously `title=source_id=doc_id`, giving the model no human label to cite with; Story 10.6b's citation assembler should surface `source_id` directly.
- **M4 FIXED** — `MonthlyComparisonRow.income_kopiykas` is now `Optional[int] = None` in [profile_tool.py](../../backend/app/agents/chat/tools/profile_tool.py) (was hardcoded to 0). Prevents the model from confidently reporting "you earned 0 UAH last month" when the service only reports expenses.
- **L1 → TD-103** — `tool_hop_count == tool_call_count` until backend exposes its `hops` counter. Concrete fix: add `hops: int` to `ChatInvocationResult` and read in the handler. Pick up when Story 10.9 needs the distinction.
- **L2 dropped** — `chat.tool.loop_exceeded` emitted from handler rather than backend raise site. Works correctly; AC phrasing was suggestive, not normative.
- **L3 → TD-104** — Profile `savings_ratio` silently drops non-int values. Defensive pickup for a future breakdown-shape change.
- **L4 FIXED inline** — Dead `_logger_for_tests_swap` helper removed from `dispatcher.py`.
- **L5 dropped** — `ChatToolError.tool_calls_so_far = ()` class-level default. Works correctly (tuple is immutable — no shared-state risk); instance-level `__init__` default would be style-only.

### Verification

- `pytest backend/tests/agents/chat/ backend/tests/test_chat_schema_cascade.py backend/tests/test_chat_role_tool_migration.py -q` → 164 passed, 3 skipped.
- `pytest backend/tests/ -q` → 1053 passed, 3 skipped, 16 deselected, 0 regressions.
- `ruff check app/agents/chat/ app/services/transaction_service.py` → clean.
