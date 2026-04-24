# ADR-0004: Chat Runtime Phasing — Direct Bedrock First, AgentCore Runtime Second

- **Status:** Accepted
- **Date:** 2026-04-24
- **Deciders:** Oleh (Architect role) — solo-founder decision; DPO/Legal review not required (no data-residency change, all traffic stays on the `eu-central-1` → `eu-north-1` path already accepted by ADR-0003)
- **Related:** Epic 10 (Chat), Story 10.4a (AgentCore Session Handler — re-spec required by this ADR), Story 9.4 decision doc `docs/decisions/agentcore-bedrock-region-availability-2026-04.md`, [architecture.md §AgentCore Deployment Model L1628-L1635](../../_bmad-output/planning-artifacts/architecture.md#L1628-L1635), [architecture.md §IAM & Infrastructure L1644-L1647](../../_bmad-output/planning-artifacts/architecture.md#L1644-L1647)

## Context

Story 10.4a was authored against the mental model "AgentCore = a managed Sonnet endpoint you pass a runtime ID to." During the start of Story 10.4a implementation, the AWS Bedrock AgentCore Control API was probed (AWS CLI v2.34.35, boto3 1.42.73) and the actual shape of the service was confirmed:

- `aws_bedrockagentcore_runtime` is **not yet** a first-party Terraform resource (hashicorp/aws 5.100.0).
- `bedrock-agentcore-control:create-agent-runtime` requires `--agent-runtime-artifact` (a `containerConfiguration.containerUri` or `codeConfiguration.s3` tagged union) and a `--role-arn` + `--network-configuration`. There is **no** `--foundation-model` / `--model-arn` parameter.
- AgentCore Runtime is a **container fabric** (Lambda-like): you build a container image containing the agent loop (model invocations, tool calls, memory, session state) and AgentCore hosts it. The model call happens inside the container, not inside AgentCore's control plane.

The "managed Sonnet endpoint" mental model actually describes **Bedrock Agents** (`aws_bedrockagent_agent`), a separate AWS product positioned for no-code agent authoring with action groups + managed session memory.

Story 10.4a as written is not implementable against the real AgentCore API. Three options were evaluated:

1. **Pivot to Bedrock Agents** — matches the story's mental model, but imposes Bedrock Agents' prescriptive shape (action groups, managed memory, prompt overrides) that conflicts with Epic 10's contracts: explicit 20-turn/8k-token memory bound with server-side summarization (architecture.md L1717-L1721), custom tool manifest (Story 10.4c), SSE streaming envelope (Story 10.5), contextual-grounding tuning (Story 10.6a). Rejected as a retreat that the next four stories would spend time working around.
2. **Ship AgentCore Runtime properly** — container package + Dockerfile + ECR + build-and-push CI + container IAM role + AgentCore runtime Terraform module + handler loop code, all in one story. Rejected as too large for a single story; would triple 10.4a's scope and delay Epic 10 by weeks.
3. **Direct `bedrock:InvokeModel` behind the handler API (Phase A), with AgentCore Runtime as Phase B** — the session handler's 4-method public API (`create_session`, `send_turn`, `terminate_session`, `terminate_all_user_sessions`) is the contract seam; the implementation swaps underneath.

## Decision

**Phase the chat runtime.** Ship the Epic 10 conversational feature in two phases behind a stable handler API.

### Phase A (Story 10.4a, re-spec'd)

- Backend `ChatSessionHandler` in [backend/app/agents/chat/session_handler.py](../../backend/app/agents/chat/session_handler.py) implements the 4-method public API unchanged from the original AC #7.
- Model calls route through direct `bedrock-runtime:InvokeModel` / `InvokeModelWithResponseStream` (via [backend/app/agents/llm.py](../../backend/app/agents/llm.py), same path Celery batch agents use).
- Conversation history is DB-owned in `chat_messages` (already designed that way in Story 10.1b + 10.4a AC #9 — AgentCore would have been a cache, not the source of truth).
- Memory bounds + summarization (`memory_bounds.py`, AC #8–#9) land exactly as spec'd — triggered by the handler in Python before each model call.
- Bedrock Guardrails (Story 10.2) are invoked via `bedrock:ApplyGuardrail` + inline `guardrailConfig` on the Converse call. Identical to the AgentCore path.
- Tool use (Story 10.4c) uses Claude's native tool-use via Bedrock Converse `toolConfig`; the handler executes tool calls against existing services (`transaction_service`, education KB from Story 3.3, etc.).
- Streaming (Story 10.5) uses `InvokeModelWithResponseStream` bridged to SSE in FastAPI.
- No AgentCore Terraform module, no ECR repo, no container build pipeline.
- Config surface: `settings.CHAT_RUNTIME: Literal["direct", "agentcore"] = "direct"` — the switch that Phase B flips.

### Phase B (new story — provisionally 10.4a-runtime, scheduled after Story 10.5 streams ship)

- New Terraform module `infra/terraform/modules/agentcore-runtime/` — either native resource (if AWS provider has shipped one by then) or `null_resource` wrapping the `bedrock-agentcore-control` CLI.
- New Python package `backend/agentcore_container/` with Dockerfile — hosts the handler loop inside an AgentCore container image.
- New ECR repo + build-and-push CI job.
- Container IAM role (`bedrock-agentcore.amazonaws.com` principal) with `bedrock:InvokeModel` + `bedrock:ApplyGuardrail` scoped exactly as Story 10.4a's original AC #2.
- FastAPI App Runner instance role gains `bedrock-agentcore:InvokeAgentRuntime` on the runtime ARN; **loses** `bedrock:InvokeModel` for chat (batch Celery keeps it).
- `CHAT_RUNTIME="agentcore"` in prod; handler code path selects between the two implementations at `get_chat_session_handler()` factory time. No public-API change.
- Migration validation: Story 10.5's SSE contract, Story 10.4c's tool manifest, and Story 10.8b's safety harness must pass against both `CHAT_RUNTIME="direct"` and `CHAT_RUNTIME="agentcore"` before Phase B is rolled out to prod.

## Rationale (feature-by-feature)

| Concern | Phase A mechanism | Phase B mechanism | Epic 10 impact |
|---|---|---|---|
| 20-turn / 8k-token memory bound | Handler queries `chat_messages`; `memory_bounds.py` enforces; summarization via Haiku in `llm.py` before next InvokeModel | Same logic inside AgentCore container; AgentCore's session-state cache is an optimization | None — DB is source of truth on both paths |
| Server-side summarization | Haiku via `get_llm_client()` before invoke; summary persisted as `role='system'` `ChatMessage` | Same | None |
| Bedrock Guardrails (input + output, grounding ≥ 0.85) | `bedrock:ApplyGuardrail` + Converse `guardrailConfig` | Same (Guardrails is a separate service) | None |
| Tool use (read-only tools on user's own data) | Claude tool-use via Bedrock Converse `toolConfig`; handler loop executes tool calls against existing services | Same loop inside container; AgentCore tool manifest is a presentation/declarative layer on the same primitive | None — 10.4c's tool catalog is unchanged |
| SSE streaming | `InvokeModelWithResponseStream` → SSE bridge in FastAPI | `InvokeAgentRuntime` with streaming → same SSE bridge | None — browser-facing envelope unchanged |
| RAG over education corpus | Existing Epic 3 KB service called as a tool | Same | None |
| Consent revoke cascade (FR70/FR71) | `terminate_all_user_sessions` is a no-op for `direct` (no remote session state); DB cascade handles everything | Calls `bedrock-agentcore:DeleteSession` then DB cascade | Handler API stable; caller in `consent_service.revoke_chat_consent()` unchanged |
| Per-session isolation | `session_id` column on every `chat_messages` row — SQL-level guarantee | AgentCore `sessionId` + SQL column | None — SQL is authoritative either way |
| Cross-session / long-term memory | Not implemented — TD-040 | Could use AgentCore Memory strategies | Out of scope for Epic 10; TD-040 unchanged by this ADR |
| Cost | Model tokens only (+ tiny Bedrock invoke overhead) | Model tokens + AgentCore invocation surcharge + ECR storage | Phase A is cheaper until Phase B ships |
| Observability | Bedrock model-level CloudWatch metrics + structlog `chat.*` events (AC #12) | Above + AgentCore runtime-level metrics (container cold-starts, concurrency) | Story 10.9 queries extend in Phase B |

## Consequences

### Accepted

- Epic 10 ships on a realistic timeline. 10.4b (prompt hardening), 10.4c (tool manifest), 10.5 (SSE), 10.6a (grounding), 10.7/10.10 (UI + history/deletion), 10.8 (safety harness), 10.9 (observability), 10.11 (rate limits) all author against the stable handler API and are unaffected by the Phase A vs B split.
- The architectural invariant "chat runs on AgentCore" becomes a **target state** with a documented interim phase, not a day-one mandate. The section amendments in architecture.md make this explicit; `git log` + this ADR prevent a future reviewer from "fixing" Phase A back to an AgentCore-only path prematurely.
- App Runner instance role gains `bedrock:InvokeModel` during Phase A for the chat path; the scope is the exact same chat inference profile Celery already uses (`chat_default.bedrock` in `models.yaml`). No new model ARN surface.
- Story 10.4a's Terraform AgentCore module + its execution IAM role move to Phase B (not shipped in 10.4a).

### Risks + mitigations

- **Risk:** Phase A entrenches and Phase B never ships. **Mitigation:** TD-094 (this ADR's migration tracker) is opened with a concrete trigger: "after Story 10.5 ships streams AND (Story 10.9's first 30 days of prod chat observability are reviewed)". Phase B is a committed follow-up, not an aspiration.
- **Risk:** Phase B migration is harder than expected because Phase A code paths leak AgentCore-unfriendly assumptions. **Mitigation:** the handler API is the seam; AC #7's 4-method contract does not reference `bedrock-runtime` or `bedrock-agentcore` primitives — those live behind a `ChatBackend` abstraction at the `session_handler.py` boundary. Story 10.4a's re-spec mandates the same import-time guard for both backends so Phase B is a backend swap, not a handler rewrite.
- **Risk:** Phase A's direct-invoke cost model grows large enough that the AgentCore container's idle cost is no longer a worse trade. **Mitigation:** CloudWatch `feature=chat` cost anomaly detection (architecture.md §Cost Controls L1653-L1661) is already in place; Phase B's trigger includes a cost-signal gate in TD-094.

### Rejected

- **Bedrock Agents (`aws_bedrockagent_agent`) pivot** — see Context. Prescriptive shape conflicts with explicit Epic 10 contracts.
- **Ship AgentCore Runtime in a single 10.4a** — see Context. Too large; would delay Epic 10 materially.
- **Defer chat past Epic 10 entirely** — rejected; chat is the primary user-facing deliverable of Epic 10.

## References

- Story 10.4a (re-spec'd per this ADR): [_bmad-output/implementation-artifacts/10-4a-agentcore-session-handler-memory-bounds.md](../../_bmad-output/implementation-artifacts/10-4a-agentcore-session-handler-memory-bounds.md)
- HALT report that surfaced the API mismatch: [_bmad-output/implementation-artifacts/agentcore-implementation.md](../../_bmad-output/implementation-artifacts/agentcore-implementation.md)
- Story 9.4 decision doc (region + inference profiles + AgentCore availability): [`docs/decisions/agentcore-bedrock-region-availability-2026-04.md`](../decisions/agentcore-bedrock-region-availability-2026-04.md)
- ADR-0003 (cross-region inference — data-residency basis, unchanged by this ADR): [0003-cross-region-inference-data-residency.md](0003-cross-region-inference-data-residency.md)
- Tech-debt register: [docs/tech-debt.md](../tech-debt.md) — **TD-094** (Phase B migration tracker, new), **TD-081** (close — CLI v2.34.35 now supports `bedrock-agentcore`), **TD-040** (cross-session memory, unchanged)
