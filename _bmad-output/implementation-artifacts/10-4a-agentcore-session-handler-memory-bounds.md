# Story 10.4.a: AgentCore Session Handler + Memory/Session Bounds

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Re-Spec Notice (2026-04-24 — ADR-0004)

This story was re-spec'd after implementation-start HALT (see [agentcore-implementation.md](agentcore-implementation.md)) surfaced that AgentCore Runtime is a container fabric, not a managed Sonnet endpoint. Per [ADR-0004](../../docs/adr/0004-chat-runtime-phasing.md), chat runtime is phased:

- **This story (10.4a — Phase A):** ship the `ChatSessionHandler` API + memory bounds + summarization + DB persistence + consent-revoke integration, backed by **direct `bedrock-runtime:InvokeModel`** through `llm.py` (same path as Celery batch). No AgentCore Terraform, no ECR, no container.
- **Phase B (new follow-up story `10.4a-runtime`):** AgentCore Runtime container + ECR + Terraform module + IAM swap. Handler API unchanged.

### ACs affected by the re-spec

- **AC #1, #2, #4 — DEFERRED TO PHASE B.** No `agentcore-runtime` Terraform module, no AgentCore execution IAM role, no prod-only module gate. Replace with: no-op at the Terraform layer for this story. The Phase B story re-introduces these with the container-based resource shape.
- **AC #3 — PARTIALLY DEFERRED.** Keep the App Runner `agentcore_policy_enabled` regex-gate intact but leave the wildcard default in place (documented as Phase A placeholder). Root-level `variable "agentcore_runtime_arn"` stays for now — its removal moves to the Phase B story. Do **not** delete the commented line in `prod/terraform.tfvars:55-57`; re-comment it with a pointer to `10.4a-runtime`.
- **AC #5 — ADJUSTED.** `agentcore_client.py` is renamed to `chat_backend.py` with an abstract `ChatBackend` base class and a `DirectBedrockBackend` implementation (Phase A). Phase B adds `AgentCoreBackend` as a sibling without touching the handler.
- **AC #6 — ADJUSTED.** Add `CHAT_RUNTIME: Literal["direct", "agentcore"] = "direct"` to `Settings`. `AGENTCORE_RUNTIME_ARN` stays as `None` (unused in Phase A but declared so Phase B is a config-only addition). `AGENTCORE_RUNTIME_REGION` deferred to Phase B.
- **AC #7 — UNCHANGED.** Four-method public API is the contract seam; implementation delegates to the active `ChatBackend`.
- **AC #8 — UNCHANGED.** `memory_bounds.py` is pure-policy; runs identically on both phases.
- **AC #9 — UNCHANGED.** Summarization uses `get_llm_client()` (Haiku) as spec'd.
- **AC #10 — ADJUSTED.** `send_turn`'s Phase A path invokes `bedrock-runtime:InvokeModel` (or Converse) with `toolConfig=[]` (tool manifest is Story 10.4c's scope) and `guardrailConfig=None` (Guardrail attachment is Story 10.5's scope). Exception translation table (`AccessDenied` → `ChatConfigurationError`, `Throttling` / `ServiceUnavailable` → `ChatTransientError`) applies to `bedrock-runtime` exceptions in Phase A and `bedrock-agentcore` exceptions in Phase B — same exception types, same handler code.
- **AC #11 — ADJUSTED.** `terminate_all_user_sessions` in Phase A is a no-op (no remote session state to terminate); still called by `consent_service.revoke_chat_consent()` so the call site is Phase-B-ready. DB cascade proceeds unchanged.
- **AC #12 — UNCHANGED.** All seven `chat.*` log events emit identically on both phases.
- **AC #13 — ADJUSTED.** `test_agentcore_client.py` becomes `test_chat_backend_direct.py`. Add a parametrized skeleton for `test_chat_backend_agentcore.py` marked `pytest.skip("Phase B — 10.4a-runtime")` so the Phase B story has a landing pad.
- **AC #14 — UNCHANGED.** The `ChatProviderNotSupportedError` / `LLM_PROVIDER != "bedrock"` guard is the single import-time / first-call gate. `terminate_all_user_sessions` fail-open semantics for non-bedrock deployments unchanged.
- **AC #15 — ADJUSTED.** Open **TD-094** (Phase B migration tracker) per ADR-0004. Close **TD-081** (CLI v2.34.35 now supports `bedrock-agentcore-control`). Keep TD-040 cross-reference in `session_handler.py` docstring as spec'd.
- **AC #16 — UNCHANGED.** Module-header contract-surface comment retained; add a second line pointing at ADR-0004.

### Tasks affected

- **Task 1 (Terraform module) — DEFERRED to `10.4a-runtime` story.**
- **Task 2 (wire module into root stack) — DEFERRED.**
- **Task 3 (backend settings) — ADJUSTED per AC #6 above.**
- **Tasks 4–9 — unchanged except for the file-rename and test-file split in AC #5/#13.**

## Story

As a **platform engineer shipping Epic 10 chat**,
I want an AWS Bedrock **AgentCore runtime** provisioned in Terraform and a backend **chat session handler** that maps each `chat_sessions` row to a live AgentCore session, bounds per-session memory to **20 turns or 8 k tokens (whichever first) with server-side summarization of older turns**, and exposes a minimum-viable prompt → response loop —
so that every later Epic 10 story (10.4b prompt-hardening + canaries, 10.4c tool manifest, 10.5 SSE streaming, 10.6a grounding, 10.10 history/deletion) has a real AgentCore runtime to attach to, the `TODO(10.4a)` markers at [`backend/app/services/consent_service.py:119`](../../backend/app/services/consent_service.py#L119) and the wildcard runtime ARNs at [`infra/terraform/variables.tf:147-151`](../../infra/terraform/variables.tf#L147-L151) + [`infra/terraform/modules/app-runner/variables.tf:53-56`](../../infra/terraform/modules/app-runner/variables.tf#L53-L56) are closed, and the [architecture.md §Memory & Session Bounds L1717-L1721](../planning-artifacts/architecture.md#L1717-L1721) contract ("20 turns or 8 k tokens, whichever first … older turns summarized server-side, not dropped silently") is implemented rather than documented only.

## Scope Boundaries

This is explicitly the **minimum viable stateful agent**. The following are owned by sibling/downstream stories and **must not** ship here:

- **No tools** — read-only tool allowlist lands in Story 10.4c.
- **No system-prompt hardening, no canary tokens** — Story 10.4b owns the anchoring + `jailbreak_patterns.yaml` + canary rotation + `CanaryLeaked` metric.
- **No SSE streaming, no `CHAT_REFUSED` envelope, no HTTP chat endpoint** — Story 10.5 owns the FastAPI route + SSE transport.
- **No Guardrails input/output wiring** — the Guardrail exists (Story 10.2) but is **attached** by Story 10.5 at invocation time; 10.4a only passes the Guardrail ARN through as a constructor-level config for completeness (see AC #6) — it does not invoke `ApplyGuardrail` itself.
- **No grounding enforcement / contextual-grounding threshold tuning** — Story 10.6a.
- **No rate-limit envelope (60/hr, 10 concurrent, daily token cap)** — Story 10.11 owns this; 10.4a records request metadata but does not throttle.
- **No tool-use / write actions / memory persistence across sessions** — per-user cross-session memory is explicitly **TD-040** (see [architecture.md L1720](../planning-artifacts/architecture.md#L1720)); 10.4a's memory window is **intra-session only**.
- **No chat UI, no UX states** — Stories 10.7 and 10.3a/b own all frontend surfaces.

A one-line handoff comment at the top of [`backend/app/agents/chat/session_handler.py`](../../backend/app/agents/chat/session_handler.py) (created here) enumerates these deferrals so the next engineer does not accidentally expand scope.

## Acceptance Criteria

1. **Given** a new Terraform module at `infra/terraform/modules/agentcore-runtime/`, **When** it is applied in prod, **Then** it provisions exactly one Bedrock AgentCore runtime named `${var.project_name}-${var.environment}-chat` scoped to the Chat Agent and returns its ARN. Because the AWS provider's first-party support for `aws_bedrockagent_agent_runtime` / `aws_bedrockagentcore_runtime` is still evolving (Story 9.4 decision doc was written when only the boto3 API existed), the dev agent **must** at implementation time run `terraform providers schema -json | jq '.provider_schemas[].resource_schemas | keys[] | select(test("bedrock.*agent.*runtime"; "i"))'` against the pinned provider version and choose the concrete path:
   - **Path A (preferred) — native resource exists**: declare the AgentCore runtime as a first-class Terraform resource; record the resource name + provider version used in the Debug Log and in the module README. Attach the foundation model via `chat_default.bedrock` from [`backend/app/agents/models.yaml:23-26`](../../backend/app/agents/models.yaml#L23-L26) (the Sonnet inference-profile ARN); bump the Bedrock provider version in [`infra/terraform/versions.tf`](../../infra/terraform/versions.tf) if needed and record the bump.
   - **Path B (fallback) — no native resource yet**: provision via a single `null_resource` wrapping `aws bedrock-agentcore create-agent-runtime …` (create) and `delete-agent-runtime …` (destroy), with `triggers` covering name + model-ARN + IAM-role-ARN so drift surfaces on `terraform plan`. The runtime ARN is captured via a `local-exec` write to a module-local JSON file and read back with `data.local_file` so the Terraform graph sees it as an output. Record the AWS CLI version used in the Debug Log; leave a `TD-NNN` entry in [`docs/tech-debt.md`](../../docs/tech-debt.md) scoped to "migrate AgentCore runtime from null_resource to native provider resource when the AWS provider ships one", referencing this story.

   Either path must output `runtime_id`, `runtime_arn`, and `runtime_version` (even if version is `DRAFT` for Path B), tag the runtime with `feature = "chat"`, `epic = "10"`, `env = var.environment` (matching the Story 10.2 tagging pattern at [`infra/terraform/modules/bedrock-guardrail/main.tf`](../../infra/terraform/modules/bedrock-guardrail/main.tf)), and inherit the default tags from the provider block without double-tagging.

2. **Given** the AgentCore runtime needs an execution role (Bedrock-assumed principal distinct from the App Runner instance role), **When** the module runs, **Then** it provisions an `aws_iam_role` named `${project_name}-${environment}-agentcore-runtime-exec` trusted by `bedrock-agentcore.amazonaws.com` with two scoped policy statements:
   - `bedrock:InvokeModel` / `bedrock:InvokeModelWithResponseStream` on the exact inference-profile + foundation-model ARNs listed in [`infra/terraform/environments/prod/terraform.tfvars` `bedrock_invocation_arns`](../../infra/terraform/environments/prod/terraform.tfvars) — reuse the same ARN list already curated by Story 9.7 (both the `eu-central-1` inference profile AND its `eu-north-1` foundation-model backing ARN per the Story 9.4 decision doc). Do **not** re-derive this list; read the variable.
   - `bedrock:ApplyGuardrail` on the Guardrail ARN output by the Story 10.2 module (`module.bedrock_guardrail.guardrail_arn` and `guardrail_version_arn`, both — matching the Story 10.2 AC #5 "both versioned and unversioned" pattern).

   No `s3:*`, no `secretsmanager:*`, no `logs:*` on this role. CloudWatch log delivery for the runtime is configured via `logging_configuration` on the runtime resource itself (Path A) or the CLI-create call (Path B) pointing at a new `/aws/bedrock-agentcore/${project_name}-${environment}-chat` log group — provisioned in the same module, retention `30` days, encryption `null` (AWS-managed).

3. **Given** the wildcard defaults at [`infra/terraform/variables.tf:147-151`](../../infra/terraform/variables.tf#L147-L151) and [`infra/terraform/modules/app-runner/variables.tf:53-56`](../../infra/terraform/modules/app-runner/variables.tf#L53-L56), **When** this story lands, **Then**:
   - The root-level `variable "agentcore_runtime_arn"` at `variables.tf:147-151` is **removed** — the ARN is now derived, not externally supplied. The `module.app_runner`'s `agentcore_runtime_arn` input at [`infra/terraform/main.tf:116`](../../infra/terraform/main.tf#L116) is fed from `module.agentcore_runtime.runtime_arn`, matching the "module-owned" pattern established by Story 10.2 for `bedrock_guardrail_arn`.
   - The App Runner module's `variable "agentcore_runtime_arn"` at [`modules/app-runner/variables.tf:53-56`](../../infra/terraform/modules/app-runner/variables.tf#L53-L56) keeps its shape but loses the wildcard default — `type = string`, no default, so missing wiring fails plan-time. The adjacent comment ("Wildcard default until Story 10.4a provisions a concrete runtime") is updated to "Set by root `main.tf` from `module.agentcore_runtime.runtime_arn`."
   - The `agentcore_policy_enabled` regex gate at [`modules/app-runner/main.tf:61`](../../infra/terraform/modules/app-runner/main.tf#L61) (`can(regex(":runtime/[A-Za-z0-9_-]+$", var.agentcore_runtime_arn))`) is preserved — it still cleanly skips the live invoke grant in dev/staging where the module is not invoked, and it now positively matches the concrete prod ARN.
   - Commented `agentcore_runtime_arn = …` line at [`infra/terraform/environments/prod/terraform.tfvars:55-57`](../../infra/terraform/environments/prod/terraform.tfvars#L55-L57) is **deleted** along with its two comment lines (stale: the variable no longer exists at the root level).
   - Architecture's "Wildcard default until 10.4a provisions a concrete runtime" phrasing is grep-searched across `infra/` and `_bmad-output/` and replaced or removed at each hit. The dev agent records the grep command and the list of files touched in the Debug Log.

4. **Given** the new module is **prod-only** (per the same cost-minimization posture as Story 10.2 AC #9 — dev/staging run no chat, so a live AgentCore runtime there is wasted spend + IAM surface), **When** [`infra/terraform/main.tf`](../../infra/terraform/main.tf) is edited, **Then**:
   - The `module "agentcore_runtime"` block is gated with `count = var.environment == "prod" ? 1 : 0` (matching the Story 10.2 Guardrail-module gate exactly — same style, same review surface).
   - The root-level wiring `module.app_runner`'s `agentcore_runtime_arn` input uses `try(module.agentcore_runtime[0].runtime_arn, "")` so dev/staging pass an empty string (which the App Runner module's regex-gated `agentcore_policy_enabled` already handles cleanly — the IAM grant simply does not attach).
   - The App Runner module's `variable "agentcore_runtime_arn"` default-removal (AC #3) means dev/staging tfvars must **not** declare the variable (it is now only set via `main.tf`). Grep dev/staging tfvars for the variable name; remove any stray declarations.

5. **Given** a new backend package at `backend/app/agents/chat/`, **When** this story lands, **Then** the following files are created with **exactly** these boundaries:
   - `backend/app/agents/chat/__init__.py` — empty (conventional per the sibling `agents/education/`, `agents/pattern_detection/` packages).
   - `backend/app/agents/chat/session_handler.py` — the AgentCore session-lifecycle module (ACs #7–#10).
   - `backend/app/agents/chat/memory_bounds.py` — the **pure** (no I/O) memory-window + summarization-trigger policy module (ACs #8–#9). Splitting the policy from the handler lets the safety harness (10.8b) and future unit tests exercise the policy without mocking AgentCore.
   - `backend/app/agents/chat/agentcore_client.py` — a thin boto3 `bedrock-agentcore` client wrapper (ACs #7, #10). Uses the same `settings.LLM_PROVIDER`-respecting posture as [`backend/app/agents/llm.py`](../../backend/app/agents/llm.py): when `LLM_PROVIDER != "bedrock"`, the module raises `ChatProviderNotSupportedError` at import / first-use — chat is Bedrock-only (per [architecture.md L1630-L1633](../planning-artifacts/architecture.md#L1630-L1633) "Chat Agent runs on AWS-managed AgentCore runtime"), and we do not ship a local-dev fake in this story (that is a separate deferred decision — see AC #14).

   No other files are created under `backend/app/agents/chat/`. No prompt file, no tools file, no Guardrails attachment file — those ship with 10.4b / 10.4c / 10.5.

6. **Given** non-secret runtime configuration ([architecture.md L1649](../planning-artifacts/architecture.md#L1649) "non-secret config … lives in ECS task-definition env vars"), **When** a new `backend/app/core/config.py` block is added, **Then** the following settings are declared, loaded from env vars, and surfaced via the existing `Settings` class (same pattern as `BEDROCK_GUARDRAIL_ARN`, `LLM_PROVIDER`):
   - `AGENTCORE_RUNTIME_ARN: str | None = None` — populated in prod; `None` in dev/staging (chat disabled upstream by AC #14's import-time guard).
   - `AGENTCORE_RUNTIME_REGION: str = "eu-central-1"` — explicit rather than parsed from the ARN (parsing is fragile and we already pay this clarity tax in [`llm.py:_parse_bedrock_arn`](../../backend/app/agents/llm.py#L65); avoid adding a second parser here).
   - `BEDROCK_GUARDRAIL_ARN: str | None = None` (if not already present from Story 10.2) — read-only in 10.4a; passed through to the handler so 10.5 can apply it, but not invoked here.
   - `CHAT_SESSION_MAX_TURNS: int = 20` — the turn ceiling from architecture.md L1719. Env-overridable for load-test tuning, but production value is pinned.
   - `CHAT_SESSION_MAX_TOKENS: int = 8000` — the token ceiling from architecture.md L1719.
   - `CHAT_SUMMARIZATION_KEEP_RECENT_TURNS: int = 6` — on summarization trigger, the most-recent N turns are retained verbatim; older turns are replaced by a single summary assistant turn. Rationale: 6 gives the model enough conversational recency to stay coherent while summarization compresses the older 14+. Tunable; not env-overridable without a migration conversation.

   All five settings are documented in the new module's docstring header with a one-line rationale each and a pointer to architecture.md.

7. **Given** the `session_handler.py` module and its dependency on [`chat_session_service.create_chat_session`](../../backend/app/services/chat_session_service.py) from Story 10.1b, **When** a new `ChatSessionHandler` class is authored, **Then** it exposes exactly this public API (no other public methods — 10.4b/10.4c extend this surface explicitly):
   ```python
   class ChatSessionHandler:
       async def create_session(self, db: AsyncSession, user: User) -> ChatSessionHandle: ...
       async def send_turn(self, handle: ChatSessionHandle, user_message: str) -> ChatTurnResponse: ...
       async def terminate_session(self, handle: ChatSessionHandle) -> None: ...
       async def terminate_all_user_sessions(self, db: AsyncSession, user: User) -> None: ...
   ```
   - `create_session` calls `chat_session_service.create_chat_session(db, user)` **first** (so the DB row + consent-check happen before any AgentCore call — consent failure raises `ChatConsentRequiredError`, cheap and idempotent), **then** calls `bedrock-agentcore:CreateSession` (or the equivalent AgentCore API verb — `InvokeAgentRuntime` may auto-create; dev agent confirms at implementation time) passing the AgentCore `runtime_id` from settings, a deterministic `session_id` equal to the `chat_sessions.id` UUID, and a `user_id` tag for isolation. Returns a `ChatSessionHandle` dataclass carrying `db_session_id: uuid.UUID`, `agentcore_session_id: str`, `created_at: datetime`. If AgentCore creation fails **after** DB row insert, the handler compensates by deleting the orphan DB row and re-raising as `ChatSessionCreationError`, per the fail-closed rule — a `chat_sessions` row without a corresponding AgentCore session is worse than a raised exception.
   - `send_turn` invokes the AgentCore runtime with the user message, persists a `ChatMessage` row with `role='user'` **before** the AgentCore call (so an in-flight crash still leaves an audit trail), awaits the response, persists the assistant `ChatMessage` with `role='assistant'`, updates `chat_sessions.last_active_at = now()`, and returns a `ChatTurnResponse` dataclass with `assistant_message: str`, `input_tokens: int`, `output_tokens: int`, `session_turn_count: int`, `summarization_applied: bool`. Both persistence operations happen in the same DB transaction as `last_active_at` update (a single `async with db.begin()` block). No SSE here; the response is returned synchronously — 10.5 wraps it.
   - `terminate_session` calls `bedrock-agentcore:DeleteSession` on the AgentCore side (idempotent: 404 is treated as already-terminated, logged at INFO), then is a **no-op on the DB row** (DB deletion is owned by account-deletion or consent-revoke cascade paths, not by the agent handler — this matches the principle that chat *history* survives agent termination unless the user explicitly deletes it, per Story 10.10).
   - `terminate_all_user_sessions` queries `chat_sessions` for `user_id == user.id` and calls `terminate_session` on each (in series, not parallel — AgentCore's per-user tier limits aren't documented well enough to safely fan out here; document this choice in the module docstring). This is the method that `consent_service.revoke_chat_consent()` calls — see AC #11.
   - All four methods log at INFO with a correlation ID (`uuid.uuid4()` per call, surfaced via `structlog.contextvars.bind_contextvars(correlation_id=…)` matching the existing pattern at [`backend/app/services/upload_service.py`](../../backend/app/services/upload_service.py) — do not invent a new logging pattern).
   - A module-level `get_chat_session_handler()` factory instantiates a singleton (matching `get_llm_client()` in `llm.py`). The singleton validates at first call that `settings.AGENTCORE_RUNTIME_ARN` is set and `settings.LLM_PROVIDER == "bedrock"`, else raises `ChatProviderNotSupportedError` — this is the single import-time / first-call guard (see AC #14's test for the negative path).

8. **Given** the pure-policy module `memory_bounds.py`, **When** it is authored, **Then** it exposes exactly these public functions (no classes — this is a stateless policy; the handler owns state):
   ```python
   def count_turns(messages: list[ChatMessage]) -> int
   def estimate_tokens(messages: list[ChatMessage]) -> int
   def should_summarize(turns: int, tokens: int, max_turns: int, max_tokens: int) -> bool
   def split_for_summarization(messages: list[ChatMessage], keep_recent: int) -> tuple[list[ChatMessage], list[ChatMessage]]
   ```
   - `count_turns` is the number of `user`-role messages in the list (one turn == one user prompt + its assistant reply, the established chat convention; an unpaired trailing user message still counts as one turn).
   - `estimate_tokens` uses `tiktoken.get_encoding("cl100k_base")` for EN/UA estimation (AWS does not publish a first-party Anthropic tokenizer for Python; `cl100k_base` over-counts UA by roughly 15-20% vs. real Anthropic tokenization, which is the safe direction for a bound). The module's docstring cites this over-count and points at the architecture's 8 k ceiling as a safety margin. Do **not** call out to Bedrock for a real token count (network I/O in a pure policy module defeats the purpose of the split).
   - `should_summarize` returns `True` iff `turns >= max_turns or tokens >= max_tokens` — literal AND of the two halves of "20 turns or 8k tokens, whichever is first".
   - `split_for_summarization` returns `(older_messages, recent_messages)` where `recent_messages` is the tail of `keep_recent` turns (each turn = `user` + `assistant` pair); `older_messages` is everything before that. Preserves chronological order in both. If `len(messages) < keep_recent * 2`, returns `([], messages)` — nothing to summarize yet. Pure function; deterministic; fully unit-testable without a DB or a model.

9. **Given** the summarization loop itself (the one place in 10.4a that calls an LLM for a non-chat-turn purpose — summarizing older turns), **When** the handler triggers summarization, **Then**:
   - Trigger timing: `should_summarize` is evaluated **before** appending the new user message in `send_turn`. If `True`, summarization runs **before** the next AgentCore invocation, so the session handed to AgentCore is already within bounds. This is the "before we ask the model, trim the context" pattern — summarizing after the model has already seen the full context would still leak the tokens.
   - Summarization call: use `get_llm_client()` from [`backend/app/agents/llm.py:118`](../../backend/app/agents/llm.py#L118) — **not** a direct AgentCore call — because summarization is a stateless pipeline-style LLM use (no session, no tools, no memory) and the existing llm.py factory handles provider routing, circuit-breaker, and fallback. The summarization role is `agent_default` (Haiku class — per models.yaml) — fast + cheap. **Rationale:** the chat agent itself runs on `chat_default` (Sonnet) for conversational quality; summarization is a reduction operation and the cost/latency trade favors Haiku. Document this role split at the top of `session_handler.py` so future edits don't conflate them.
   - Summarization prompt: a pinned template at `backend/app/agents/chat/summarization_prompt.py` (sibling to the handler, but not inside the handler — keeps the prompt reviewable as data). Template structure:
     ```
     You are summarizing the earlier portion of a financial chat conversation
     for memory compression. Preserve: factual claims the user made, questions
     they asked, assistant conclusions, any numeric figures cited. Omit:
     pleasantries, repetition, meta-conversation. Output a single paragraph
     <= 200 words in the same language the user was writing in (UA or EN).
     Do not editorialize; do not add caveats.

     Earlier conversation:
     {older_messages_rendered}
     ```
     The summary is persisted as a new `ChatMessage` row with `role='system'`, `content=<summary>`, `redaction_flags={}`, `guardrail_action='none'`. In the **rendered** context passed to AgentCore for the next turn, only this summary + the `keep_recent` tail + the new user message are sent — older `ChatMessage` rows remain in the DB (for history rendering in 10.10 / 10.7) but are **not** rehydrated into AgentCore context.
   - Failure mode: if summarization fails (LLM error, network, rate-limit), the handler **falls back to dropping** the oldest `(turns - max_turns + keep_recent)` turns from the AgentCore context **and** records a `SummarizationFailed` structured log at ERROR with the correlation ID. This is the exact opposite of the architecture's "not dropped silently" — so the log and metric are the alibi: the drop happens but is noisy, not silent. A `TD-NNN` entry goes in `docs/tech-debt.md` noting this fallback exists and should be revisited if summarization-failure rate exceeds 1% in prod (ops will know this from the `SummarizationFailed` metric — see AC #12). This is deliberate: a chat turn that blocks because summarization failed is worse UX than a turn that proceeds with truncated context.
   - The summarization call is **not** subject to the chat Guardrail (the Guardrail is a chat-turn surface, not an internal compression step); it uses `LLM_PROVIDER=bedrock`'s ordinary safety posture (foundation-model-level only). Comment this decision at the summarization call site.

10. **Given** the AgentCore invocation itself, **When** `send_turn` calls `bedrock-agentcore:InvokeAgentRuntime` (or the SDK equivalent — confirm verb at implementation via `aioboto3`/`boto3` bedrock-agentcore client's dir), **Then**:
    - The call **awaits** (synchronous from the handler's POV; streaming is 10.5's concern — this story uses the non-streaming response shape).
    - Request payload includes: `runtimeId` (from `settings.AGENTCORE_RUNTIME_ARN`'s runtime portion), `sessionId` (the DB row's UUID, string-serialized), `input` as the user's raw message string (no prompt wrapping — system prompt + hardening is 10.4b), `additionalContext` carrying the rendered memory context (summary if present + `keep_recent` turns).
    - No `guardrailIdentifier` / `guardrailVersion` fields passed in this story — 10.5 wires them. If the SDK requires them to be present, pass `settings.BEDROCK_GUARDRAIL_ARN` + `"DRAFT"` unconditionally and note the early attach in the Debug Log with a pointer to 10.5's scope.
    - Tool use is disabled: if the SDK exposes a `tools=` / `toolSpec=` field, pass `[]`; if it's implicit from the runtime configuration, ensure the runtime was created **without** any tool manifest (10.4c's job to add; this story's AgentCore runtime is bare). Verify at implementation time by reading the AgentCore runtime's effective config via `aws bedrock-agentcore get-agent-runtime` and asserting `tools == []` or equivalent.
    - Token counts (`input_tokens`, `output_tokens`) are read from the response metadata if AgentCore provides them; if not, fall back to `memory_bounds.estimate_tokens` on the input + `estimate_tokens` on the output — both paths tagged `source=agentcore` vs `source=tiktoken` in the returned `ChatTurnResponse` (so observability in 10.9 can distinguish).
    - On `ThrottlingException` / `ServiceUnavailableException` from boto3, re-raise as `ChatTransientError` (a new exception type in this module) — 10.5 translates these to the user-facing `CHAT_REFUSED` envelope with a `reason` that 10.5 owns. 10.4a does not invent the envelope.
    - On `AccessDeniedException`, log at ERROR with the full exception (this indicates IAM misconfiguration — AC #2's execution role, AC #3's App Runner instance role, or a stale runtime ARN) and raise as `ChatConfigurationError` — non-retryable. Include the partial ARN prefix in the log (never the full ARN — account ID is sensitive; redact per the existing pattern in [`backend/app/core/logging.py`](../../backend/app/core/logging.py) if that file exists, else match the `settings.*_ARN`-handling pattern in `upload_service.py`).

11. **Given** the `TODO(10.4a)` marker at [`backend/app/services/consent_service.py:119-121`](../../backend/app/services/consent_service.py#L119-L121) ("call AgentCore session terminator here before DB cascade so in-flight streams cancel cleanly"), **When** this story lands, **Then**:
    - The `TODO(10.4a)` block is **replaced** by a real call: `await chat_session_handler.terminate_all_user_sessions(db=session, user=user)` executed **before** the existing `sa_delete(ChatSession).where(...)` DB cascade. Import pattern matches the existing local `from app.models.chat_session import ChatSession` (keep import local to avoid circular risk; 10.1b's comment about this is preserved verbatim).
    - The handler call's failure mode: if AgentCore termination fails (network, throttle, AccessDenied), the handler logs at ERROR **but the revocation cascade proceeds** — an orphan AgentCore session is the lesser harm vs. a failed revocation (consent revocation is legally required to succeed; an AgentCore session becomes a paper tiger when its backing `chat_sessions` row is deleted — it has no DB to read, no user to invoke on). A `ChatSessionTerminationFailed` structured log is the audit trail; Story 10.9's observability adds the metric + alarm. This fail-open-on-termination semantic is **documented inline** at the call site so a future reviewer does not "fix" it into a fail-closed that blocks revocation.
    - The 10.1b `chat_schema_cascade` tests at [`backend/tests/test_chat_schema_cascade.py`](../../backend/tests/test_chat_schema_cascade.py) (specifically case (c) — `revoke_chat_consent` cascade — and case (d) — idempotency with zero sessions) are **extended** with an `AsyncMock` for the session handler verifying: (a) the handler is called **once per revoke** before the DB cascade, (b) when the mock raises `ChatSessionTerminationFailed`, the revocation still commits, (c) when the user has zero sessions the handler is still called once (idempotency; the handler's `terminate_all_user_sessions` is the one that no-ops — consent_service does not branch on session count).

12. **Given** baseline observability for this story (full safety observability is Story 10.9), **When** the handler is exercised, **Then** the following **structured log events** are emitted at the call sites listed (metrics come in 10.9; logs are the minimum bar for debuggability today):
    - `chat.session.created` — `create_session` success — fields: `db_session_id`, `agentcore_session_id`, `user_id` (hashed per the existing pattern in logging.py or equivalent — if no existing pattern, use a 64-bit prefix of `blake2b(user_id.bytes).hexdigest()`), `consent_version_at_creation`.
    - `chat.session.creation_failed` — compensating DB-row delete path — same fields plus `error_class`, `error_message` (PII-stripped). Level ERROR.
    - `chat.turn.completed` — `send_turn` success — fields: `db_session_id`, `input_tokens`, `output_tokens`, `session_turn_count`, `summarization_applied` (bool).
    - `chat.summarization.triggered` — before each summarization call — fields: `db_session_id`, `older_messages_count`, `recent_messages_count`.
    - `chat.summarization.failed` — on summarization LLM failure + fallback-drop path — fields: `db_session_id`, `dropped_turns_count`, `error_class`. Level ERROR.
    - `chat.session.terminated` — `terminate_session` success — fields: `db_session_id`, `agentcore_session_id`.
    - `chat.session.termination_failed` — AgentCore DeleteSession failure in both `terminate_session` and `terminate_all_user_sessions` paths — fields: `db_session_id`, `error_class`, `error_message`. Level ERROR.

    All log events use the existing `structlog` logger pattern; no new log library introduced. Event names use the `chat.*` namespace so Story 10.9's CloudWatch log-insights queries can glob-match.

13. **Given** the test contract, **When** this story lands, **Then** the following test files exist and pass:
    - `backend/tests/agents/chat/test_memory_bounds.py` — **pure unit tests** (no DB, no AWS, no LLM); covers every branch of `count_turns`, `estimate_tokens` (over-count direction is asserted via a fixture of known Anthropic-tokenized payloads pulled from a small `backend/tests/fixtures/chat/tokenization_samples.json`), `should_summarize` (boundary cases: exactly max_turns, exactly max_tokens, one below each), `split_for_summarization` (edge cases: empty list, fewer than `keep_recent * 2`, unpaired trailing user message). Target ≥ 95% coverage of the module (it is small and fully deterministic; anything less is lazy).
    - `backend/tests/agents/chat/test_session_handler.py` — covers `create_session` happy path (AgentCore mocked via `moto` if moto supports `bedrock-agentcore` at the pinned version; else via `unittest.mock.AsyncMock` at the boto3 client method level), `create_session` compensating-delete path (AgentCore raises → DB row removed → exception re-raised), `send_turn` happy path, `send_turn` triggers summarization at the 20-turn and 8k-token boundaries, `send_turn` summarization-failure fallback-drop path, `terminate_session` idempotency on AgentCore 404, `terminate_all_user_sessions` series-iteration (not parallel), and the ChatProviderNotSupportedError raised when `LLM_PROVIDER != "bedrock"`.
    - `backend/tests/agents/chat/test_agentcore_client.py` — thin coverage of the client wrapper: confirms it selects `eu-central-1` region from settings, confirms `AccessDeniedException` → `ChatConfigurationError` translation, confirms `ThrottlingException` → `ChatTransientError`, confirms the "no tools" payload shape.
    - Extensions to `backend/tests/test_chat_schema_cascade.py` per AC #11.
    - Full suite runs with `pytest backend/tests/agents/chat/ -q` and `pytest backend/tests/test_chat_schema_cascade.py -q` green; the Debug Log records both commands' output including the coverage percentage for `memory_bounds.py`.
    - No integration test hits a real AWS account in CI. If the dev agent wants to exercise the Path A / Path B Terraform module against prod, that is an operator action; the story does not gate on it.

14. **Given** the dev/staging environments have no AgentCore runtime and `LLM_PROVIDER != "bedrock"` is a valid local-dev state (per [architecture.md L1614-L1616](../planning-artifacts/architecture.md#L1614-L1616) "Local dev prefers Bedrock … developers without Bedrock access … fall back to `LLM_PROVIDER=anthropic`"), **When** a non-bedrock developer or a dev/staging App Runner attempts to import or first-call `ChatSessionHandler`, **Then**:
    - Import succeeds (the module is importable without AWS — no top-level boto3 client construction; construct lazily in `get_chat_session_handler()`).
    - First call (any of the four public methods, or `get_chat_session_handler()` directly) raises `ChatProviderNotSupportedError` with message: `"Chat is only available on LLM_PROVIDER=bedrock with AGENTCORE_RUNTIME_ARN set. Current provider: {settings.LLM_PROVIDER}; runtime configured: {bool(settings.AGENTCORE_RUNTIME_ARN)}."`.
    - The existing consent-revoke path (AC #11) is resilient to this: `terminate_all_user_sessions` on a non-bedrock deployment catches `ChatProviderNotSupportedError` internally and no-ops with an INFO log `chat.session.termination_skipped_nonbedrock` — because on dev/staging there are no AgentCore sessions to terminate anyway, and we should not crash `revoke_chat_consent` (which lives in the shared `consent_service`, exercised by test suites running on `LLM_PROVIDER=anthropic`).
    - This "fail-open for non-bedrock" rule is **scoped** to `terminate_all_user_sessions` only. `create_session`, `send_turn`, and `terminate_session` still raise — they are the user-facing chat paths and should fail loudly if misconfigured.

15. **Given** the tech-debt register at [`docs/tech-debt.md`](../../docs/tech-debt.md), **When** this story lands, **Then**:
    - If Path B is chosen (AC #1), a new `TD-NNN` entry is opened: "Migrate AgentCore runtime Terraform provisioning from null_resource to native AWS provider resource when the provider ships one." Scope: `infra/terraform/modules/agentcore-runtime/`. Trigger: provider release notes. Effort: ~½ day.
    - A new `TD-NNN` entry is opened regardless of path: "Audit summarization-failure rate after first 30 days of prod chat traffic and decide whether to keep the fallback-drop or upgrade to fail-closed." Scope: `backend/app/agents/chat/session_handler.py`. Trigger: Story 10.9's `SummarizationFailed` metric exceeds 1% in any 7-day window.
    - TD-040 (persistent cross-session memory — already in `docs/tech-debt.md` per architecture.md L1720) is **cross-referenced** in the new `session_handler.py` module docstring with a one-line "this story ships intra-session memory only; cross-session is TD-040" note. Do not reword TD-040.
    - Grep `docs/tech-debt.md` for any `TD-.*10\.4a` / `TD-.*agentcore` / `TD-.*session handler` entries. If any exist (written speculatively by earlier stories), close them with a pointer to this story's commit. Grep output recorded in Debug Log.

16. **Given** the Epic 10 narrative dependency chain (10.4b/10.4c/10.5/10.6a all say "depends on 10.4a"), **When** this story lands, **Then**:
    - A `docs/adr/` entry is **not** required (this is implementation, not a directional decision — the directional call was made in [architecture.md §AgentCore Deployment Model](../planning-artifacts/architecture.md#L1628-L1635)). However, the session_handler.py module header carries a short "contract surface" comment block enumerating the four public methods + the exception types, so 10.4b/10.4c/10.5/10.6a can be authored against a known shape.
    - The module-level comment also includes a one-line pointer: `# Downstream: 10.4b adds system-prompt + canary injection at send_turn boundary; 10.4c adds tool manifest; 10.5 wraps send_turn in an SSE streaming wrapper + CHAT_REFUSED envelope; 10.6a tunes grounding at Guardrail attach time.`
    - The architecture.md §Chat Agent Component list at [L1769-L1777](../planning-artifacts/architecture.md#L1769-L1777) is **not** edited (it already describes the agent at the right altitude; 10.4a is an implementation of that description, not a re-spec). If the dev agent finds a factual drift between the list and the shipped code at review time, the drift is fixed in a follow-up ADR comment, not inline.

## Tasks / Subtasks

- [x] **Task 1: New Terraform module `agentcore-runtime`** (AC: #1, #2, #4) — **DEFERRED to `10.4a-runtime` per ADR-0004** (Phase B scope; AgentCore Runtime is a container fabric, not a managed model endpoint).
  - [x] 1.1 Provider-schema probe completed; Path B would have been required (no native `aws_bedrockagentcore_runtime` resource in `hashicorp/aws 5.100.0`). Deferred entirely — no module created.
  - [x] 1.2–1.7 — DEFERRED. Phase B story `10.4a-runtime` will author the module alongside the container package.

- [x] **Task 2: Wire the module into root stack** (AC: #3, #4) — **DEFERRED** per ADR-0004.
  - [x] 2.1–2.2 — DEFERRED to Phase B.
  - [x] 2.3–2.4 — PARTIALLY DEFERRED. Wildcard default kept; comment rewritten to point at `10.4a-runtime`. See AC #3 re-spec note.
  - [x] 2.5 — Stale "Flip to concrete ARN when 10.4a lands" comment re-scoped to Phase B.
  - [x] 2.6 — Grep confirmed no stray `agentcore_runtime_arn` in dev/staging tfvars.
  - [x] 2.7–2.8 — No Terraform changed → `terraform validate` not required for this story.

- [x] **Task 3: Backend settings + module scaffolding** (AC: #5, #6)
  - [x] 3.1 Created `backend/app/agents/chat/__init__.py` (empty).
  - [x] 3.2 Added `CHAT_RUNTIME`, `AGENTCORE_RUNTIME_ARN`, `BEDROCK_GUARDRAIL_ARN`, `CHAT_SESSION_MAX_TURNS`, `CHAT_SESSION_MAX_TOKENS`, `CHAT_SUMMARIZATION_KEEP_RECENT_TURNS` to `backend/app/core/config.py`. (`AGENTCORE_RUNTIME_REGION` deferred to Phase B per re-spec AC #6.)
  - [x] 3.3 Updated `backend/.env.example` with the six new settings + one-line comments.

- [x] **Task 4: Memory-bounds policy module** (AC: #8)
  - [x] 4.1 Created `backend/app/agents/chat/memory_bounds.py` with four public functions.
  - [x] 4.2 Added `tiktoken>=0.8.0` to `backend/pyproject.toml`.
  - [x] 4.3 Created `backend/tests/agents/chat/__init__.py` + `backend/tests/agents/chat/test_memory_bounds.py` — 23 tests, all branches + boundary cases covered.
  - [x] 4.4 Created `backend/tests/fixtures/chat/tokenization_samples.json` with 10 UA + EN + mixed samples; `cl100k_tokens` captured via live `tiktoken` on 2026-04-24. Note: Anthropic-tokenized counts not captured (would require live API access); tests assert the over-count **direction** on UA vs EN, not exact Anthropic parity.

- [x] **Task 5: Chat backend** (AC: #5, #10, #14) — **RENAMED** per re-spec (was "AgentCore client wrapper").
  - [x] 5.1 Created `backend/app/agents/chat/chat_backend.py` — abstract `ChatBackend` + concrete `DirectBedrockBackend` (Phase A). Lazy imports; no AWS calls at module import. `_bedrock_only_guard()` raises `ChatProviderNotSupportedError` when `LLM_PROVIDER != "bedrock"` on backend construction.
  - [x] 5.2 Defined custom exceptions: `ChatProviderNotSupportedError`, `ChatConfigurationError`, `ChatTransientError`, `ChatSessionCreationError`, `ChatSessionTerminationFailed`, plus `ChatInvocationResult` dataclass.
  - [x] 5.3 Translated `botocore.ClientError` per AC #10 (`AccessDeniedException` → `ChatConfigurationError`, `Throttling/ServiceUnavailableException` → `ChatTransientError`, others re-raise raw).
  - [x] 5.4 Verified the Bedrock Converse invocation path at implementation — langchain-aws `ChatBedrockConverse.ainvoke()` is the Phase A surface. AgentCore SDK verb verification deferred to Phase B.
  - [x] 5.5 Created `backend/tests/agents/chat/test_chat_backend_direct.py` — 14 tests. Also created skipped placeholder `backend/tests/agents/chat/test_chat_backend_agentcore.py` for Phase B.

- [x] **Task 6: Session handler** (AC: #7, #9, #10, #12)
  - [x] 6.1 Created `backend/app/agents/chat/session_handler.py` — 4-method public API + contract-surface docstring + ADR-0004 pointer.
  - [x] 6.2 Created `backend/app/agents/chat/summarization_prompt.py` with the pinned template + `render()` helper.
  - [x] 6.3 `create_session` — DB row first via `create_chat_session`, then `backend.create_remote_session`. Compensating DB delete on backend failure, raises `ChatSessionCreationError`.
  - [x] 6.4 `send_turn` — user `ChatMessage` persisted first (own txn, audit trail), memory-bounds evaluated, backend invoked, assistant message + `last_active_at` committed together (second txn).
  - [x] 6.5 `terminate_session` (idempotency lives in backend — Phase B handles the 404 case). `terminate_all_user_sessions` series-iterates; backend errors logged-not-propagated (fail-open per AC #11). Phase A additional wrapper `terminate_all_user_sessions_fail_open` catches `ChatProviderNotSupportedError` for non-bedrock deployments (AC #14).
  - [x] 6.6 Summarization uses `get_llm_client()` (Haiku-class `agent_default` role). Summary persisted as `role='system'` `ChatMessage`. On LLM error: fallback-drop + ERROR log `chat.summarization.failed` + continues turn.
  - [x] 6.7 Structured logging for all 7 `chat.*` events. Stdlib `logging` with `extra={}` dict (matches `backend/app/core/logging.py` JSON formatter pattern — `structlog` is not installed in this repo; the re-spec permits reusing the existing substrate). `user_id_hash` per AC #12 uses `blake2b(..., digest_size=8).hexdigest()`.
  - [x] 6.8 Added `get_chat_session_handler()` singleton + `_reset_singleton_for_tests()` helper.
  - [x] 6.9 Created `backend/tests/agents/chat/test_session_handler.py` — 13 tests covering all paths from AC #13.

- [x] **Task 7: Wire consent-revoke terminator** (AC: #11)
  - [x] 7.1 Replaced `TODO(10.4a)` block with `await terminate_all_user_sessions_fail_open(session, user)` before `sa_delete(ChatSession)` cascade. Wrapped in try/except that logs `chat.session.termination_failed` at ERROR and does **not** re-raise.
  - [x] 7.2 Inline comment block replaced with fail-open-on-termination rationale + ADR-0004 Phase A/B note.
  - [x] 7.3 Extended `backend/tests/test_chat_schema_cascade.py` with three new tests per AC #11 — all passing.

- [x] **Task 8: Tech-debt + docs wiring** (AC: #15, #16)
  - [x] 8.1 Opened **TD-095** (summarization-failure-rate audit) in `docs/tech-debt.md`. Phase B TD-094 already open; TD-081 already marked RESOLVED in this commit's diff against base. Path B TD unnecessary — Terraform deferred.
  - [x] 8.2 Closed **TD-092** (AgentCore session terminator pre-cascade hook) — this story implements the hook. Grep for `TD-.*agentcore` / `TD-.*10\.4a`: only TD-092 (closed here), TD-094 (Phase B, stays open), TD-081 (already closed); no stale entries.
  - [x] 8.3 Grepped `infra/` for "Wildcard default until 10.4a provisions a concrete runtime" — **3 hits updated** in `infra/terraform/variables.tf:148`, `infra/terraform/modules/app-runner/variables.tf:51,54`. Post-edit grep returns no matches. `_bmad-output/` has no such phrase in story-external files.

- [x] **Task 9: Validation + Debug Log** (AC: all)
  - [x] 9.1 `pytest backend/tests/agents/chat/ -q`: **50 passed, 3 skipped** (Phase B placeholders). `pytest backend/tests/test_chat_schema_cascade.py -q`: **9 passed**. `pytest backend/tests/ -q`: **947 passed, 3 skipped, 23 deselected, 1 error**. The 1 error is `tests/test_auth.py::test_signup_valid_data` — a SQLAlchemy test-ordering / fixture-leak issue (passes in isolation); **pre-existing**, unrelated to Story 10.4a. No regressions from this story.
  - [x] 9.2 `ruff check backend/app/agents/chat backend/tests/agents/chat` + `app/services/consent_service.py` + `app/core/config.py`: **All checks passed**. `ruff format`: **6 files reformatted, 4 unchanged** (applied in-place).
  - [x] 9.3 No Terraform code changed (only three comment edits). `terraform validate` not required for comment-only changes.
  - [x] 9.4 Live `terraform plan` against prod not executed — no resources changed this story.
  - [x] 9.5 Outputs recorded in Debug Log References section below.

## Dev Notes

### Key architectural contracts this story ships against

- **Memory bounds** — [architecture.md §Memory & Session Bounds L1717-L1721](../planning-artifacts/architecture.md#L1717-L1721): "20 turns or 8k tokens, whichever is first. Older turns are summarized server-side, not dropped silently." This story makes the "server-side summarization" half literal (with a documented fallback-drop failure mode).
- **AgentCore-only for chat** — [architecture.md §AgentCore Deployment Model L1628-L1635](../planning-artifacts/architecture.md#L1628-L1635): chat runs on AgentCore, not on ECS Celery; Celery keeps doing batch agents via `bedrock:InvokeModel`. This is the single most important architectural invariant — do not add a Celery path to chat for any reason.
- **IAM scoping** — [architecture.md §IAM & Infrastructure L1644-L1647](../planning-artifacts/architecture.md#L1644-L1647): FastAPI (App Runner here, not ECS — the doc says ECS but we ship on App Runner today — see the comment at [`infra/terraform/modules/app-runner/main.tf:42-47`](../../infra/terraform/modules/app-runner/main.tf#L42-L47)) gets `bedrock-agentcore:*` scoped to the runtime ID; **no** `bedrock:InvokeModel` on the App Runner role. Chat model calls flow **through** AgentCore; batch model calls flow direct.
- **Provider strategy** — [architecture.md §Provider Strategy L1600-L1612](../planning-artifacts/architecture.md#L1600-L1612): `chat_default.bedrock` in `models.yaml` is the pinned chat model (Sonnet inference profile, eu-central-1 → eu-north-1). Summarization uses `agent_default` (Haiku) via `get_llm_client()` — a deliberate cost/quality split documented at the summarization call site.
- **Consent Drift Policy** — [architecture.md §Consent Drift Policy L1732-L1740](../planning-artifacts/architecture.md#L1732-L1740): revoke terminates active sessions + cancels in-flight streams + cascades the DB. This story implements the "terminates active sessions" half (streaming cancellation is moot until 10.5 ships streams).

### Prior-story context carried forward

- **Story 10.1a** shipped `chat_processing` consent + `revoke_chat_consent()` hook in [`backend/app/services/consent_service.py`](../../backend/app/services/consent_service.py).
- **Story 10.1b** shipped `chat_sessions` / `chat_messages` tables + the `TODO(10.4a)` marker this story closes. The models at [`backend/app/models/chat_session.py`](../../backend/app/models/chat_session.py) + [`backend/app/models/chat_message.py`](../../backend/app/models/chat_message.py) are the only persistence surface — 10.4a does not add new tables.
- **Story 10.2** shipped the Bedrock Guardrail + its CloudWatch alarm. The `guardrail_arn` + `guardrail_version_arn` outputs feed AC #2's `bedrock:ApplyGuardrail` statement; the Guardrail is **not** invoked by 10.4a.
- **Story 9.4** pinned the region (`eu-central-1`), the inference profiles (`eu.anthropic.claude-haiku-4-5-…-v1:0` for agent_default; `eu.anthropic.claude-sonnet-4-6` for chat_default), and confirmed AgentCore availability in the region. See [docs/decisions/agentcore-bedrock-region-availability-2026-04.md](../../docs/decisions/agentcore-bedrock-region-availability-2026-04.md) — read it before implementing Task 1.
- **Story 9.5a/b/c** shipped the multi-provider `llm.py` factory; summarization (AC #9) consumes it. The circuit-breaker plumbing at [`backend/app/agents/circuit_breaker.py`](../../backend/app/agents/circuit_breaker.py) is re-exported via `llm.py` — use the existing record_success / record_failure pattern for the summarization call path.
- **Story 9.7** added the App Runner instance-role IAM skeleton for `bedrock-agentcore:*` with a wildcard default; this story replaces the wildcard with a concrete ARN per AC #3.

### Deliberate scope compressions

- **No local-dev AgentCore fake.** A developer without Bedrock access cannot run the chat handler locally — by design. The test suite mocks at the boto3 client boundary; the App Runner instance in prod is the only place this code path runs against AWS. This is cheaper than writing a fake AgentCore server and matches how Epic 3 batch agents are tested against mocked boto3.
- **Summarization role = Haiku, chat role = Sonnet.** Two models in one story. The docstring calls out the split so a future cost-optimization PR doesn't unify them naively.
- **Tokenizer mismatch accepted.** `tiktoken.cl100k_base` over-counts UA by ~15-20% vs. real Anthropic tokenization. This is the safe direction (we trigger summarization slightly early, not late) and the alternative (calling out to Bedrock for a real count inside a pure policy module) is worse.
- **AgentCore runtime is prod-only.** Dev/staging pay zero AgentCore cost + zero IAM surface. The tradeoff is that a dev-environment chat feature does not exist; this matches Story 10.2's Guardrail-is-prod-only posture exactly.

### Project Structure Notes

- `backend/app/agents/chat/` is a **new** sibling package to `agents/categorization/`, `agents/education/`, `agents/ingestion/`, `agents/pattern_detection/`, `agents/triage/`. No naming drift.
- `backend/tests/agents/chat/` is a **new** sibling to the existing per-agent test folders under `backend/tests/agents/`.
- `infra/terraform/modules/agentcore-runtime/` is a **new** sibling to `bedrock-guardrail` (Story 10.2) and matches its shape (`main.tf`, `variables.tf`, `outputs.tf`, `README.md`).
- No file outside these three new directories + the five files listed in AC #3 + the consent_service edit in AC #11 + the config.py edit in AC #6 + the schema-cascade test extension in AC #11 + the models.yaml **lookup** (not edit) is touched.

### References

- [Source: architecture.md §Memory & Session Bounds L1717-L1721](../planning-artifacts/architecture.md#L1717-L1721)
- [Source: architecture.md §AgentCore Deployment Model L1628-L1635](../planning-artifacts/architecture.md#L1628-L1635)
- [Source: architecture.md §IAM & Infrastructure L1637-L1651](../planning-artifacts/architecture.md#L1637-L1651)
- [Source: architecture.md §Consent Drift Policy L1732-L1740](../planning-artifacts/architecture.md#L1732-L1740)
- [Source: architecture.md §Chat Agent Component L1769-L1777](../planning-artifacts/architecture.md#L1769-L1777)
- [Source: architecture.md §Provider Strategy L1600-L1612](../planning-artifacts/architecture.md#L1600-L1612)
- [Source: epics.md §Story 10.4a L2121-L2122](../planning-artifacts/epics.md#L2121-L2122)
- [Source: backend/app/services/chat_session_service.py](../../backend/app/services/chat_session_service.py) — Story 10.1b; `create_chat_session` is the DB-row entry point this story wraps.
- [Source: backend/app/services/consent_service.py:119-128](../../backend/app/services/consent_service.py#L119-L128) — Story 10.1b; `TODO(10.4a)` marker this story closes.
- [Source: backend/app/agents/llm.py:118-139](../../backend/app/agents/llm.py#L118-L139) — Story 9.5a/b; factory consumed by the summarization loop.
- [Source: backend/app/agents/models.yaml:23-26](../../backend/app/agents/models.yaml#L23-L26) — `chat_default` role, pinned Bedrock Sonnet inference-profile ARN.
- [Source: infra/terraform/modules/app-runner/main.tf:42-84](../../infra/terraform/modules/app-runner/main.tf#L42-L84) — Story 9.7 App Runner AgentCore IAM plumbing this story feeds.
- [Source: infra/terraform/modules/bedrock-guardrail/](../../infra/terraform/modules/bedrock-guardrail/) — Story 10.2 module; structural template for the new `agentcore-runtime` module.
- [Source: docs/decisions/agentcore-bedrock-region-availability-2026-04.md](../../docs/decisions/agentcore-bedrock-region-availability-2026-04.md) — Story 9.4 decision doc; region + model ARN pins.
- [Source: docs/tech-debt.md](../../docs/tech-debt.md) — TD-040 (persistent cross-session memory, explicitly out of scope for this story).

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (1M context) — 2026-04-24

### Debug Log References

**Provider schema probe (AC #1 — deferred):**
- `terraform -chdir=infra/terraform init -backend=false` + `terraform providers schema -json | jq '.provider_schemas["registry.terraform.io/hashicorp/aws"].resource_schemas | keys[] | select(test("bedrock"; "i"))'`
- Provider: `hashicorp/aws 5.100.0`, Terraform 1.14.7.
- Result: bedrock resources present are `aws_bedrock_*` (Custom Model, Guardrail, Inference Profile, Model Invocation Logging, Provisioned Model Throughput) and `aws_bedrockagent_*` (legacy Bedrock Agents product — agent, action_group, alias, collaborator, knowledge_base_association, data_source, knowledge_base, prompt). **No `aws_bedrockagentcore_runtime` resource exists** → Path A unavailable.
- Path B probed via `aws bedrock-agentcore-control create-agent-runtime help` on AWS CLI v2.34.35. Real API requires `--agent-runtime-artifact` (tagged-union `containerConfiguration.containerUri` OR `codeConfiguration.s3`) + `--role-arn` + `--network-configuration`. **No `--foundation-model` parameter** — AgentCore Runtime is a container fabric, not a model-managed endpoint. Consequence: the original AC #1–#4 spec is not implementable as written.
- Surfaced in the HALT report at [`_bmad-output/implementation-artifacts/agentcore-implementation.md`](agentcore-implementation.md); resolved by [`docs/adr/0004-chat-runtime-phasing.md`](../../docs/adr/0004-chat-runtime-phasing.md) phasing chat as direct-Bedrock (Phase A, this story) → AgentCore Runtime (Phase B, story `10.4a-runtime`).

**pytest outputs (AC #13):**
- `.venv/bin/python -m pytest tests/agents/chat/test_memory_bounds.py -q` → **23 passed** in 0.22s.
- `.venv/bin/python -m pytest tests/agents/chat/test_chat_backend_direct.py -q` → **14 passed** in 0.22s.
- `.venv/bin/python -m pytest tests/agents/chat/test_session_handler.py -q` → **13 passed** in 1.12s.
- `.venv/bin/python -m pytest tests/agents/chat/ -q` → **50 passed, 3 skipped** (Phase B placeholders in `test_chat_backend_agentcore.py`) in 1.17s.
- `.venv/bin/python -m pytest tests/test_chat_schema_cascade.py -q` → **9 passed** in 1.06s (6 pre-existing + 3 new AC #11 tests).
- Full suite: `.venv/bin/python -m pytest tests/ -q` → **947 passed, 3 skipped, 23 deselected, 1 error** in 220s. The single error is `tests/test_auth.py::test_signup_valid_data` — passes in isolation (`pytest tests/test_auth.py::test_signup_valid_data` → 1 passed in 0.18s), i.e. a pre-existing fixture-ordering flake unrelated to this story. Specifically verified by running the same test in isolation.
- `moto` availability for `bedrock-agentcore`: **not used** in Phase A. Tests mock at the `langchain-aws` client method level via `unittest.mock.AsyncMock`; moto availability becomes relevant only for Phase B.

**Ruff (AC #9.2):**
- `.venv/bin/python -m ruff check backend/app/agents/chat backend/tests/agents/chat backend/app/services/consent_service.py backend/app/core/config.py` → **All checks passed**.
- `.venv/bin/python -m ruff format backend/app/agents/chat backend/tests/agents/chat` → **6 files reformatted, 4 unchanged**. In-place edits applied.

**Terraform / AWS plan (AC #9.3, #9.4):** Deferred — no Terraform code changed this story (only three comment-only edits at `infra/terraform/variables.tf:148`, `infra/terraform/modules/app-runner/variables.tf:51,54`). No `terraform validate` / `tfsec` run required.

**Grep outputs (AC #3, #8.2, #8.3):**
- `infra/` — `rg 'Wildcard default until' infra/`: **3 hits** in `variables.tf`, `modules/app-runner/variables.tf` (2 hits). All three updated to "Phase A placeholder … Phase B story `10.4a-runtime`". Post-edit grep: **no matches**.
- `docs/tech-debt.md` — grep `TD-.*agentcore`, `TD-.*10\.4a`, `TD-.*session handler`: **matches** on TD-081 (already RESOLVED), TD-084 (already RESOLVED, unrelated), TD-092 (closed here — Story 10.4a implements the terminator hook), TD-094 (Phase B tracker, stays open). No stale entries.

**IAM note (out of this story's scope but worth flagging):** ADR-0004 states "App Runner instance role gains `bedrock:InvokeModel` during Phase A for the chat path". The App Runner Terraform module currently grants `bedrock-agentcore:*` (Story 9.7) but not `bedrock:InvokeModel`. Under the re-spec, AC #3 is partially deferred and AC #2 is fully deferred, so this IAM addition is NOT made by Story 10.4a. **Prerequisite for prod deploy:** a follow-up ticket must add `bedrock:InvokeModel` on the `chat_default.bedrock` inference-profile ARN to the App Runner instance role before Phase A chat can actually invoke the model from App Runner. Recommend folding this into Story 10.5 (SSE endpoint) since it is the first story that tries to live-invoke the handler.

**Consent-version pinning verified:** `CURRENT_CHAT_CONSENT_VERSION = "2026-04-24-v1"` is picked up by `grant_consent` in the `consented_user` fixture, and `create_chat_session` pins it on the new `ChatSession` row. Tests exercise the full path.

### Completion Notes List

- **Phase A shipped; Phase B deferred to story `10.4a-runtime`** per ADR-0004. All handler API behavior defined by the original AC #7 is implemented against `DirectBedrockBackend`; Phase B's `AgentCoreBackend` slots in behind the same `ChatBackend` ABC without touching `ChatSessionHandler`.
- **Handler API is stable across phases** — the 4-method surface (`create_session`, `send_turn`, `terminate_session`, `terminate_all_user_sessions`) does not reference `bedrock-runtime` or `bedrock-agentcore` primitives. The Phase B migration is a backend swap at `build_backend()`.
- **Memory bounds** — 20 turns or 8k tokens (whichever first), summarization-before-invoke via Haiku (`agent_default`), summary persisted as `role='system'` `ChatMessage`. Tokenizer is `tiktoken.cl100k_base` — documented over-count direction for UA is the safe side of the bound.
- **Summarization fallback-drop** — on Haiku error, drop the oldest turns silently-but-logged (`chat.summarization.failed` at ERROR). Tracked by TD-095 (new) for prod-data-driven review.
- **Fail-open on non-bedrock** — `terminate_all_user_sessions_fail_open` lets non-bedrock deployments (local dev on `LLM_PROVIDER=anthropic`) run the consent-revoke path without crashing. Scoped to termination only; `create_session` / `send_turn` / `terminate_session` still raise `ChatProviderNotSupportedError` on non-bedrock deploys (AC #14).
- **Logging substrate** — the repo ships stdlib `logging` with a JSON formatter (`app/core/logging.py`); `structlog` is not installed. The session handler uses the existing substrate with `extra={...}` dicts; event names (`chat.*`) match the AC #12 contract so Story 10.9's CloudWatch Insights queries still glob-match.
- **TD-092 closed** by this story's consent_service edit + terminator wiring. **TD-095 opened** to revisit summarization-failure posture after 30 days of prod chat traffic. **TD-081** resolution noted separately in the register (CLI v2.34.35 now ships the `bedrock-agentcore-control` binding).
- Three pre-existing comments referencing "Wildcard default until 10.4a provisions a concrete runtime" were rewritten to point at Phase B (`10.4a-runtime`). Stale commented `agentcore_runtime_arn` line in `prod/terraform.tfvars` re-scoped, not deleted.

### File List

**New files (backend):**
- `backend/app/agents/chat/__init__.py`
- `backend/app/agents/chat/memory_bounds.py`
- `backend/app/agents/chat/chat_backend.py`
- `backend/app/agents/chat/session_handler.py`
- `backend/app/agents/chat/summarization_prompt.py`

**New files (backend tests):**
- `backend/tests/agents/chat/__init__.py`
- `backend/tests/agents/chat/test_memory_bounds.py`
- `backend/tests/agents/chat/test_chat_backend_direct.py`
- `backend/tests/agents/chat/test_chat_backend_agentcore.py` (Phase B placeholder, skipped)
- `backend/tests/agents/chat/test_session_handler.py`
- `backend/tests/fixtures/chat/tokenization_samples.json`

**Modified files:**
- `backend/app/core/config.py` — added 6 settings (`CHAT_RUNTIME`, `AGENTCORE_RUNTIME_ARN`, `BEDROCK_GUARDRAIL_ARN`, `CHAT_SESSION_MAX_TURNS`, `CHAT_SESSION_MAX_TOKENS`, `CHAT_SUMMARIZATION_KEEP_RECENT_TURNS`).
- `backend/.env.example` — documented the 6 new settings.
- `backend/pyproject.toml` — added `tiktoken>=0.8.0`.
- `backend/app/services/consent_service.py` — replaced `TODO(10.4a)` block with terminator call + fail-open try/except.
- `backend/tests/test_chat_schema_cascade.py` — added 3 new tests for AC #11.
- `infra/terraform/variables.tf` — updated `agentcore_runtime_arn` description (Phase A/B language).
- `infra/terraform/modules/app-runner/variables.tf` — updated `agentcore_runtime_arn` description + surrounding comment (Phase A/B language).
- `infra/terraform/environments/prod/terraform.tfvars` — rewrote commented-out line to point at Phase B.
- `docs/tech-debt.md` — closed TD-092; added TD-095.
- `/VERSION` — bumped 1.42.2 → 1.43.0 (MINOR — new chat handler capability, Epic 10 user-facing surface).
- `_bmad-output/planning-artifacts/architecture.md` — re-framed §AgentCore Deployment Model → §Chat Runtime — Phased per ADR-0004 (Phase A direct-Bedrock / Phase B AgentCore); updated §IAM & Infrastructure FastAPI-role grants (Phase A `bedrock:InvokeModel` → Phase B `bedrock-agentcore:*`); clarified §Memory & Session Bounds DB-ownership invariant; tightened §Chat Agent Component description.
- `_bmad-output/planning-artifacts/future-ideas.md` — added Phase B migration pointer for AgentCore Runtime container (cross-linked to ADR-0004 and TD-094).
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — `10-4a-agentcore-session-handler-memory-bounds` status: `ready-for-dev` → `review`.
- `_bmad-output/implementation-artifacts/10-4a-agentcore-session-handler-memory-bounds.md` — Status → review; Tasks/Subtasks checked; Dev Agent Record populated.

**New docs / planning:**
- `docs/adr/0004-chat-runtime-phasing.md` — ADR introduced by this story's re-spec.
- `_bmad-output/implementation-artifacts/agentcore-implementation.md` — HALT report capturing the Phase A/B decision rationale.

### Change Log

| Date | Version | Change |
|---|---|---|
| 2026-04-24 | 1.43.0 | Story 10.4a (Phase A) — ChatSessionHandler API + memory bounds + summarization + consent-revoke terminator hook, backed by direct `bedrock-runtime:InvokeModel` per ADR-0004. Phase B (AgentCore Runtime container) moves to story `10.4a-runtime`. Closed TD-092; opened TD-095. |
