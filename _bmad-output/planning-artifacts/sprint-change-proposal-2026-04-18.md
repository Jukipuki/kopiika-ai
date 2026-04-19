# Sprint Change Proposal — Chat-with-Finances: Bedrock Confirmation + AI Safety Layer

**Date:** 2026-04-18
**Author:** Oleh (facilitated by Correct Course workflow)
**Change classification:** MAJOR
**Routing:** PM + Architect + PO + Dev Team

---

## 1. Issue Summary

The **chat-with-finances** feature is in active planning, which flips two previously deferred decisions to "in-plan" and exposes a gap in PRD/architecture coverage.

**What changed:**
- **Bedrock migration is confirmed** — AgentCore (required for stateful conversational agents) is the real driver. See memory: `project_bedrock_migration.md`, `project_agentcore_decision.md`.
- **New AI safety requirements emerged** — AWS Bedrock Guardrails, prompt-injection/jailbreak mitigations, meaningful AI safety tests (red-team corpus + CI gate).

**What was missing:**
- PRD treats "natural language chat interface" as a single Phase 2 bullet — no threat model, no FRs, no NFRs, no consent scoping for conversational AI.
- Architecture's `AI-Specific Security` section ([prd.md:311-316](prd.md#L311-L316)) covers only batch CSV/PDF ingest; it does not address direct prompt injection, jailbreak resistance, system-prompt extraction, tool-use scoping, Guardrails, or safety observability.
- Architecture mentions Bedrock migration only as a "future enhancement" gap ([architecture.md:1522,1575](architecture.md#L1522)) with no concrete plan.
- No epic existed for chat or for Bedrock/AgentCore infra readiness.

**Discovery context:** Proactive — not triggered by a specific story failure. Surfaced during roadmap planning for Phase 2.

**Evidence:**
- [prd.md:163,516](prd.md#L163) — chat as one-line bullet; no requirements.
- [prd.md:311-316](prd.md#L311-L316) — AI security scoped to batch pipeline only.
- [architecture.md:1522,1575](architecture.md#L1522) — Bedrock migration listed as future/gap.
- [future-ideas.md:62-71](future-ideas.md#L62-L71) — Bedrock + AgentCore both deferred "until chat-with-finances."
- No `Guardrails`, `jailbreak`, `prompt injection` mentions anywhere in PRD/architecture (grep-verified).

---

## 2. Impact Analysis

### 2.1 Epic Impact

| Epic | Impact |
|---|---|
| Epics 1–8 (MVP + Phase 1.5) | **No change.** All unaffected; no rework needed. |
| **Epic 9 (NEW)** — AI Infra Readiness | Multi-provider `llm.py`, RAG evaluation harness, embedding decision gate, AgentCore region spike, IAM plumbing, optional Celery→Step Functions evaluation. |
| **Epic 10 (NEW)** — Chat-with-Finances + AI Safety | AgentCore session agent, Bedrock Guardrails, safety test harness (CI gate), chat UX, `chat_processing` consent, streaming API, grounding + citations, safety observability. Depends on Epic 9. **Does NOT depend on payments** (ships ungated; subscription gate deferred to a post-epic follow-up). |
| Epic 3 / 8 (regression) | Regression coverage added in Story 9.5 — agents must pass on all three providers (Anthropic / OpenAI / Bedrock). No scope change. |
| Epic 5 (Privacy/Consent) | No scope change; new `chat_processing` consent is introduced via Story 10.1 inside Epic 10. |

Epic 9 precedes Epic 10 (Bedrock + IAM + region validation are prerequisites).

### 2.2 Story Impact

No existing story changes. All impact is additive: 8 new stories in Epic 9, 11 new stories in Epic 10, plus 1 follow-up story (chat subscription gate) tracked separately.

### 2.3 Artifact Conflicts

| Artifact | Change type | Proposal # |
|---|---|---|
| [prd.md](prd.md) — Growth Features | Expand chat bullet | #1 |
| [prd.md](prd.md) — Phase 2 roadmap | Expand chat + add Epic 9/10 + voice + agent-edits | #2, #12b |
| [prd.md](prd.md) — AI-Specific Security | Rewrite (MVP baseline + chat section) | #3 |
| [prd.md](prd.md) — Functional Requirements | Add chat FR block (FR56+) | #4 |
| [prd.md](prd.md) — Non-Functional Requirements | Add AI-Safety NFR section + chat rate limits + multi-provider NFR | #5 |
| [prd.md](prd.md) — Risk Mitigations tables | Add 12 new risk rows (domain + technical) | #6 |
| [prd.md](prd.md) — Integration table | Replace stale BGE-M3 row; add Bedrock/Guardrails/AgentCore | #7 |
| [prd.md](prd.md) — Consent management | Separate `chat_processing` consent | #8 |
| [architecture.md](architecture.md) — Gap Analysis #1 | Update embedding-model decision | #9 |
| [architecture.md](architecture.md) — NEW sections | Bedrock Migration & AgentCore; AI Safety Architecture | #9 |
| [architecture.md](architecture.md) — Future Enhancements | Remove promoted items; remove MamayLM item | #10 |
| [epics.md](epics.md) — NEW Epic 9 | 8 stories | #11 |
| [epics.md](epics.md) — NEW Epic 10 | 11 stories | #12 |
| [future-ideas.md](future-ideas.md) | Mark Bedrock + AgentCore as promoted | #13 |
| [sprint-status.yaml](../implementation-artifacts/sprint-status.yaml) | Add Epic 9 + 10 entries | #14 |
| [ux-design-specification.md](ux-design-specification.md) | Add chat-screen placeholder (full spec in Story 10.11) | #15 |

### 2.4 Technical Impact

**New infrastructure:**
- AWS Bedrock model access (Claude haiku/sonnet) + Bedrock Guardrails definition + AgentCore runtime.
- IAM policies on Celery ECS task role: `bedrock:InvokeModel`, `bedrock:ApplyGuardrail`, `bedrock-agentcore:*`.
- CloudWatch cost-allocation tags (`feature=chat`, `epic=10`).
- New pgvector migration possible — conditional on Story 9.3 embedding-model decision.

**New data model:** `chat_sessions`, `chat_messages` tables (cascade delete aligned with FR31/FR62).

**New code surface:**
- `backend/app/agents/llm.py` — multi-provider (add Bedrock, keep Anthropic/OpenAI).
- New Chat Agent module on AgentCore (session handler, tool allowlist, Guardrails wrapper).
- `backend/tests/ai_safety/` — red-team corpus + runner + CI gate.
- New SSE endpoint for chat streaming.
- Frontend chat feature (conversation UI, composer, streaming, citations, refusal, consent prompt).

**Regression surface:** Epic 3 + 8 agents must pass on all three providers (Story 9.5). RAG eval harness (Story 9.1) becomes CI-runnable baseline for any future embedding/retrieval change.

---

## 3. Recommended Approach

**Path selected:** Option 1 — **Direct Adjustment** with a light Option 3 touch (phased AI-safety note in PRD).

| Criterion | Assessment |
|---|---|
| Effort | High, but fully additive — 0 rework of existing epics |
| Risk | Medium — mitigated by Story 9.3 (embedding decision gate) and Story 9.4 (region availability blocking spike) |
| Timeline | Sequential: Epic 9 → Epic 10. Epic 9 is ~2-3 sprints; Epic 10 is ~3-4 sprints |
| Stakeholder alignment | Strong — Bedrock + AgentCore were always the trigger for this feature; safety gap is being closed proactively |
| Maintainability | Strong — multi-provider `llm.py` + RAG eval harness + red-team corpus + safety observability all compound beyond chat |

**Why not Option 2 (Rollback):** Nothing to roll back; Epics 1-8 are untouched.

**Why not Option 3 (MVP Review):** MVP is explicitly unaffected. Chat is Phase 2, always was. Light Option 3 note: acknowledge in PRD that AI safety is phased — basic input sanitization today, full Guardrails + red-team corpus when chat lands (captured in Proposal #3).

### Key Decisions Locked

1. **Two-epic split** — Epic 9 (infra) + Epic 10 (feature + safety). De-risks infra; keeps scope focused.
2. **`llm.py` multi-provider, not swap** — Add Bedrock alongside Anthropic/OpenAI; env-driven.
3. **Embedding migration decoupled from LLM migration** — Embeddings affect ingestion + query time only; decision is data-driven via RAG eval harness, not assumed.
4. **Embedding candidates for comparison:** OpenAI 3-small (baseline), 3-large, Titan v2, Cohere multilingual-v3. Staying on 3-small is a valid outcome.
5. **AgentCore region availability is a blocking spike** before Epic 10 scope-locks.
6. **Celery → Step Functions evaluation is optional** — time-boxed spike, recommendation only, default is stay on Celery.
7. **Separate `chat_processing` consent** — narrower blast radius, cleaner deletion semantics than bumping `ai_processing`.
8. **Chat ships ungated for demo/validation.** Subscription gate added as follow-up story after payments land.
9. **Voice I/O and agent write-actions** → Phase 2 follow-ups to Epic 10, NOT in Epic 10 scope (write-actions require separate safety review).
10. **Read-only Chat Agent** in Epic 10 — minimizes tool attack surface.

---

## 4. Detailed Change Proposals

All 15 (+ 12b) proposals are documented in the workflow conversation transcript. Each has explicit OLD/NEW text and rationale. Summary index:

### PRD ([prd.md](prd.md))
- **#1** — Expand chat in Growth Features section
- **#2** — Expand chat + add Epic 9/10 in Phase 2 roadmap
- **#12b** — Add voice I/O + agent-edits as Phase 2 follow-ups to Epic 10
- **#3** — Rewrite AI-Specific Security (MVP baseline + chat defense-in-depth)
- **#4** — Add chat FR block (FR56+) + `chat_processing` consent FR
- **#5** — Add AI Safety NFR section + chat rate limits + multi-provider NFR
- **#6** — Add 12 risk rows across Domain + Technical risk tables
- **#7** — Integration table: replace BGE-M3; add Bedrock/Guardrails/AgentCore
- **#8** — Consent management: introduce `chat_processing`

### Architecture ([architecture.md](architecture.md))
- **#9** — Update Gap #1; add "Bedrock Migration & AgentCore Architecture"; add "AI Safety Architecture"
- **#10** — Mark promoted items in Future Enhancements; remove MamayLM item

### Epics ([epics.md](epics.md))
- **#11** — NEW Epic 9 (AI Infra Readiness) with 8 stories
- **#12** — NEW Epic 10 (Chat-with-Finances + AI Safety) with 11 stories

### Secondary
- **#13** — [future-ideas.md](future-ideas.md): mark Bedrock + AgentCore as promoted
- **#14** — [sprint-status.yaml](../implementation-artifacts/sprint-status.yaml): add Epic 9 + 10 entries
- **#15** — [ux-design-specification.md](ux-design-specification.md): chat-screen placeholder (full spec in Story 10.11)

---

## 5. Implementation Handoff

### Change scope classification: MAJOR

- Affects PRD, architecture, UX spec, epics list, sprint status.
- Introduces 2 new epics, 19 new stories, new infrastructure, new security requirements.

### Handoff Plan

| Recipient | Responsibility | Deliverable |
|---|---|---|
| **Product Manager** | Approve PRD edits (Proposals #1-8, #12b) | Updated [prd.md](prd.md) |
| **Solution Architect** | Approve architecture edits (Proposals #9, #10); write detailed Bedrock + AI Safety sections | Updated [architecture.md](architecture.md) |
| **Product Owner** | Approve Epic 9/10 definitions + story breakdown (Proposals #11, #12); update [sprint-status.yaml](../implementation-artifacts/sprint-status.yaml) (Proposal #14) | Epics in backlog, ready for SM to create stories |
| **Scrum Master / Dev Team** | Execute Epic 9 stories first; Epic 9 Story 9.4 region spike is a blocking gate before Epic 10 commits | Stories 9.1-9.8, then 10.1-10.11 |
| **UX** | Update UX placeholder (Proposal #15); produce full chat UX spec as Story 10.11 inside Epic 10 | Updated [ux-design-specification.md](ux-design-specification.md) |

### Success Criteria

**For this change proposal:**
- [x] All 15 proposals approved by user (Oleh)
- [ ] PRD, architecture, epics, future-ideas, sprint-status, UX spec updated to reflect approved proposals
- [ ] Epic 9 + 10 visible in `sprint-status.yaml` with `backlog` status

**For Epic 9 (infra readiness):**
- `llm.py` multi-provider; Epic 3/8 regression passes on Anthropic / OpenAI / Bedrock
- RAG evaluation harness in CI with baseline metrics
- Embedding decision committed (either "stay" or "migrate to X")
- AgentCore + Bedrock availability confirmed in eu-central-1 (or region pivot planned)
- IAM + CloudWatch tags in place

**For Epic 10 (chat + safety):**
- Users can chat in UA + EN, grounded in their data, streaming responses with citations
- 100% of chat turns pass Bedrock Guardrails
- Red-team corpus pass rate ≥ 95% as CI gate
- Separate `chat_processing` consent; chat history fully deletable
- Safety observability + alarms operational

### Risk Register (Top 3)

| Risk | Mitigation |
|---|---|
| AgentCore unavailable in eu-central-1 | Story 9.4 blocking spike; cross-region inference profile or region pivot as fallbacks |
| Red-team corpus incomplete at launch | Seed from OWASP LLM Top-10 + published jailbreak datasets + UA adversarial prompts; quarterly review; internal bug-bounty-style review before Epic 10 ships |
| Embedding model change degrades RAG quality | Story 9.1 harness sets baseline BEFORE any migration; Story 9.3 is data-driven decision gate; staying on OpenAI 3-small is a valid outcome |

---

## 6. Approval

**Status:** ✅ **Approved by Oleh on 2026-04-18**

### Applied changes

All 15 (+ 12b) proposals applied to the following artifacts:

- [prd.md](prd.md) — Proposals #1, #2, #12b, #3, #8, #6, #4, #5, #7
- [architecture.md](architecture.md) — Proposals #9, #10 (Gap #1 update; Bedrock Migration & AgentCore Architecture section; AI Safety Architecture section; Future Enhancements cleanup)
- [epics.md](epics.md) — Proposals #11 (Epic 9: 8 stories), #12 (Epic 10: 11 stories)
- [future-ideas.md](future-ideas.md) — Proposal #13 (Bedrock + AgentCore marked as promoted)
- [sprint-status.yaml](../implementation-artifacts/sprint-status.yaml) — Proposal #14 (Epic 9 + 10 entries)
- [ux-design-specification.md](ux-design-specification.md) — Proposal #15 (chat-screen placeholder)

### Notes on FR numbering

Chat FRs were assigned **FR64–FR72**. FR56–FR63 were intentionally skipped to avoid collision with FR61/FR62/FR63 reserved by pending PRD-sync updates for promoted Stories 1.8 (forgot-password), 2.9 (currency expansion), and 2.8 (upload redirect) per [future-ideas.md:87,101,127](future-ideas.md#L87).
