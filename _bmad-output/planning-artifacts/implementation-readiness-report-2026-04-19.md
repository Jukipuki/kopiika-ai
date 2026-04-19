---
workflow: check-implementation-readiness
date: 2026-04-19
project: kopiika-ai
stepsCompleted:
  - step-01-document-discovery
  - step-02-prd-analysis
  - step-03-epic-coverage-validation
  - step-04-ux-alignment
  - step-05-epic-quality-review
  - step-06-final-assessment
inputs:
  prd: _bmad-output/planning-artifacts/prd.md
  architecture: _bmad-output/planning-artifacts/architecture.md
  epics: _bmad-output/planning-artifacts/epics.md
  ux: _bmad-output/planning-artifacts/ux-design-specification.md
  sprint_change_proposal: _bmad-output/planning-artifacts/sprint-change-proposal-2026-04-18.md
---

# Implementation Readiness Assessment Report

**Date:** 2026-04-19
**Project:** kopiika-ai

## 1. Document Inventory

### PRD
- **Whole:** [prd.md](prd.md) — 61.7 KB, last modified 2026-04-18

### Architecture
- **Whole:** [architecture.md](architecture.md) — 111.3 KB, last modified 2026-04-19 (refined post sprint-change-proposal)

### Epics & Stories
- **Whole:** [epics.md](epics.md) — 109.6 KB, last modified 2026-04-18

### UX Design
- **Whole:** [ux-design-specification.md](ux-design-specification.md) — 100.6 KB, last modified 2026-04-18

### Supporting Artifacts
- [sprint-change-proposal-2026-04-18.md](sprint-change-proposal-2026-04-18.md) — approved MAJOR change; drives Epic 9 + 10 scope reviewed here
- [future-ideas.md](future-ideas.md) — updated 2026-04-18 (Bedrock/AgentCore promoted)
- [docs/tech-debt.md](../../docs/tech-debt.md) — TD register (TD-001 … TD-040); TD-039/TD-040 newly added via this review

### Issues Found
- **Duplicates:** None — all four core documents exist in a single whole-file format, no sharded folders present.
- **Missing:** None — PRD, Architecture, Epics, UX all present.

**Discovery result: ✅ Clean inventory, ready for analysis.**

---

## 2. PRD Analysis

### Functional Requirements

**Statement Upload & Data Ingestion**
- **FR1:** Users can upload bank statement files (CSV, PDF) via drag-and-drop or file picker
- **FR2:** System can auto-detect the bank format of an uploaded statement (Monobank, PrivatBank, other)
- **FR3:** System can parse Monobank CSV files including handling Windows-1251 encoding, semicolon delimiters, and embedded newlines
- **FR4:** System can parse additional bank CSV formats where column structure is recognizable
- **FR5:** System can validate uploaded files before processing (file type, size, format structure) and return actionable error messages
- **FR6:** System can partially process statements where some transactions are unrecognizable, providing value from what it can parse
- **FR7:** Users can upload multiple statements (covering different time periods) to build cumulative history

**AI Processing Pipeline**
- **FR8:** System can extract and structure raw transactions from parsed bank statements (Ingestion Agent)
- **FR9:** System can classify transactions into spending categories using AI and MCC codes (Categorization Agent)
- **FR10:** System can generate personalized financial education content based on categorized transaction data using RAG over a financial literacy knowledge base (Education Agent)
- **FR11:** System can generate education content in the user's selected language (Ukrainian or English)
- **FR12:** System can process a typical monthly statement (200-500 transactions) through the full pipeline asynchronously
- **FR13:** Users can view real-time progress of pipeline processing via SSE streaming

**Teaching Feed & Insights**
- **FR14:** Users can view a card-based Teaching Feed displaying AI-generated financial insights
- **FR15:** Each insight card displays a headline fact with progressive disclosure education layers (headline → "why this matters" → deep-dive)
- **FR16:** Users can expand and collapse education layers on each insight card
- **FR17:** System can adapt education content depth based on the user's detected financial literacy level
- **FR18:** Users can view insights from current and previous uploads in a unified feed
- **FR19:** Teaching Feed supports cursor-based pagination for browsing insights

**Cumulative Financial Profile**
- **FR20:** System can build and maintain a persistent financial profile from all uploaded statements
- **FR21:** System can calculate and display a Financial Health Score (0-100) based on cumulative data
- **FR22:** Users can view how their Financial Health Score changes over time across uploads
- **FR23:** System can detect and display month-over-month spending changes when multiple periods are available
- **FR24:** System can display spending breakdowns by category from cumulative data

**User Management & Authentication**
- **FR25:** Users can create an account with email and password
- **FR26:** Users can log in and log out securely
- **FR27:** System can protect all application routes, requiring authentication
- **FR28:** Users can only access their own financial data (tenant isolation)
- **FR29:** Users can select their preferred language (Ukrainian or English)
- **FR30:** Users can view and manage their account settings

**Data Privacy & Trust**
- **FR31:** Users can delete all their data with a single action (account, transactions, embeddings, profile, Financial Health Score)
- **FR32:** System can display a clear data privacy explanation during onboarding
- **FR33:** System can obtain explicit user consent for AI processing of financial data at signup
- **FR34:** System can encrypt all stored financial data at rest
- **FR35:** Users can view what data the system has stored about them
- **FR36:** System can display a financial advice disclaimer ("insights and education, not financial advice")

**Error Handling & Recovery**
- **FR37:** System can detect unrecognized file formats and suggest corrective actions to the user
- **FR38:** System can flag uncategorized transactions and display them separately for user awareness
- **FR39:** System can recover gracefully from pipeline processing failures without data loss
- **FR40:** System can display user-friendly error messages (not technical errors) for all failure scenarios

**Operational Monitoring (MVP)**
- **FR41:** System can produce structured logs with correlation IDs (job_id, user_id) across all pipeline agents
- **FR42:** System can track and log pipeline processing times per agent
- **FR43:** System can track and log upload success/failure rates and error types
- **FR44:** Operator can query job status and pipeline health via database queries

**User Feedback — Layers 0-1 (MVP)**
- **FR45:** System can track implicit card interaction signals per Teaching Feed card: time_on_card_ms, education_expanded, education_depth_reached, swipe_direction, card_position_in_feed
- **FR46:** System can aggregate implicit signals into a per-card engagement score (0-100) using a weighted formula
- **FR47:** Users can rate any Teaching Feed card with thumbs up or thumbs down; vote state persists and is visible when returning to the card
- **FR48:** Users can report an issue on any Teaching Feed card via an in-context mechanism (flag icon in card overflow menu) with category selection and optional free-text field
- **FR49:** Feedback data (votes, reports, free-text) is included in the user's data export (FR35) and one-click deletion (FR31)

**User Feedback — Layer 2 (Phase 1.5)**
- **FR50:** On thumbs-down, system presents a compact slide-up panel with 4 preset reason chips: "Not relevant to me", "Already knew this", "Seems incorrect", "Hard to understand"
- **FR51:** On thumbs-up, system presents an optional follow-up (1 in 10 occurrences) with preset chips: "Learned something", "Actionable", "Well explained"

**User Feedback — Layer 3 (Phase 2)**
- **FR52:** System can display milestone feedback cards at the end of the Teaching Feed: after 3rd upload (one-time), after significant Financial Health Score change (+/- 5 points)
- **FR53:** Milestone feedback cards use the same card component and gestures as education cards — swipeable, skippable, no new UI pattern
- **FR54:** System can enforce feedback card frequency caps: max 1 feedback card per session, max 1 per month, milestone cards never repeat once dismissed
- **FR55:** System can auto-flag RAG topic clusters with >30% thumbs-down rate when a minimum of 10 votes has been reached on the cluster

**Reserved numbering gap — FR56–FR63**
Intentionally reserved (per sprint-change-proposal note) for pending PRD-sync updates from promoted Stories 1.8 (forgot-password), 2.9 (currency expansion), 2.8 (upload redirect). Not allocated in the current PRD text.

**Chat-with-Finances (Phase 2, Epic 10)**
- **FR64:** Users can open a conversational chat interface to ask questions about their own financial data in natural language (Ukrainian or English)
- **FR65:** Chat responses stream token-by-token to the UI
- **FR66:** Chat maintains cross-session memory per user (conversation history survives sign-out/sign-in within retention window)
- **FR67:** Chat responses are grounded in the user's own data and the RAG financial literacy corpus — no speculative claims
- **FR68:** Chat responses include citations back to the underlying data when making data-specific claims
- **FR69:** System can refuse out-of-scope, unsafe, or guardrail-blocked requests with a neutral message that does not leak filter rationale
- **FR70:** Users can delete their chat history; deletion cascades with account deletion (FR31 applies)
- **FR71:** System can obtain a separate explicit `chat_processing` consent on first chat use — distinct from `ai_processing`; chat blocked until granted
- **FR72:** Chat is ungated at initial launch; subscription gate added in follow-up story once payments land

**Total FRs:** 64 allocated (FR1–FR55, FR64–FR72). FR56–FR63 reserved.

### Non-Functional Requirements

**Performance** (7 targets)
- NFR-P1: Page load < 3s on 3G (mobile-first Ukrainian users)
- NFR-P2: Teaching Feed card render < 500ms after data fetch
- NFR-P3: Financial Health Score calculation < 2s
- NFR-P4: Full 3-agent pipeline < 60s for 200–500 transactions (async; SSE-gated)
- NFR-P5: API response < 500ms for read operations
- NFR-P6: File upload HTTP 202 acknowledgment < 2s
- NFR-P7: Support 100 concurrent users at MVP

**Security** (7 targets)
- NFR-S1: JWT access tokens < 15 min with refresh rotation
- NFR-S2: Session timeout after 30 min inactivity
- NFR-S3: Rate limiting — 10 login attempts/IP/15min; 20 uploads/user/hour
- NFR-S4: All uploaded file content treated untrusted; sanitized before AI pipeline
- NFR-S5: Automated dependency vulnerability scanning (Python + Node)
- NFR-S6: **Chat rate limiting (Epic 10)** — 60 msg/user/hour; 10 concurrent sessions/user; abuse alarms
- NFR-S7: `llm.py` MUST remain multi-provider (Anthropic / OpenAI / Bedrock); provider swap is env-var-only, no code change

**AI Safety (Epic 10 onward)** — NEW (7 targets)
- NFR-AI1: 100% of chat turns pass through Bedrock Guardrails (input + output); bypass = P0 regression
- NFR-AI2: Red-team corpus pass rate ≥ 95% as CI gate; blocks merges on regression
- NFR-AI3: Red-team corpus coverage — OWASP LLM Top-10 + UA adversarial + known jailbreaks; quarterly review
- NFR-AI4: Zero cross-user PII leakage in chat responses
- NFR-AI5: Grounding rate ≥ 90% (LLM-as-judge sampled in RAG harness)
- NFR-AI6: Principled refusals do not leak filter rationale
- NFR-AI7: Safety observability — CloudWatch metrics (block rate, refusal rate, token spend) + alarms on ≥ 3σ anomalies

**Scalability** (MVP → Growth targets)
- NFR-SC1: Registered users — 500 MVP → 10,000 growth
- NFR-SC2: Concurrent uploads processing — 5 MVP → 50 growth
- NFR-SC3: Transactions/user — 10,000 MVP → 50,000 growth
- NFR-SC4: RAG KB docs — 50–100 MVP → 500+ growth
- NFR-SC5: pgvector embeddings — 50,000 MVP → 500,000 growth
- NFR-SC6: 10x user growth absorbed with < 20% perf degradation by horizontal scaling (Celery workers, RDS read replicas)
- NFR-SC7: pgvector sufficient up to ~1M vectors; documented migration path to Qdrant beyond

**Accessibility** (7 targets)
- NFR-A1: WCAG 2.1 AA baseline for all UI
- NFR-A2: Full keyboard navigation on all interactive elements
- NFR-A3: Screen-reader semantic HTML + ARIA labels (triage severity, progressive disclosure)
- NFR-A4: Color independence — severity conveyed with icons + text, not color alone
- NFR-A5: Min contrast 4.5:1 normal text / 3:1 large text
- NFR-A6: Visible focus indicators on all interactive elements
- NFR-A7: Browser zoom up to 200% without horizontal scroll

**Integration** (8 integrations)
- NFR-I1: Monobank CSV import — graceful degradation on format changes; partial parsing supported
- NFR-I2: Monobank API (future Phase 2+) — architecture not to preclude
- NFR-I3: Fondy payments — idempotent, 3-retry tolerance
- NFR-I4: LemonSqueezy payments — same as Fondy
- NFR-I5: LLM API multi-provider (Anthropic / OpenAI / Bedrock) — retry with backoff; circuit breaker after 3 failures; `LLM_PROVIDER` env-var driven; no-code-change swap
- NFR-I6: **Bedrock Guardrails (Epic 10)** — 100% of chat turns gated; Guardrails outage degrades to refusal, never unfiltered
- NFR-I7: **Bedrock AgentCore (Epic 10)** — per-user-per-session isolation; runtime cost monitored via cost-allocation tags
- NFR-I8: Embedding model — OpenAI 3-small today; candidates 3-large / Titan v2 / Cohere multilingual-v3; decision gate in Story 9.3

**Reliability** (5 targets)
- NFR-R1: Uptime 99.5% for core (upload, feed, auth)
- NFR-R2: Zero data loss for uploaded financial data — WAL + regular backups
- NFR-R3: Failed pipeline jobs retryable without re-upload; per-agent checkpoint state
- NFR-R4: Graceful degradation — if Education/RAG fails, serve categorized data without education layers
- NFR-R5: Daily automated DB backups with 30-day retention

### Additional Requirements & Constraints

**Compliance & Regulatory**
- Ukrainian Data Protection Law No 2297-VI baseline; build-to-GDPR posture
- Right to erasure covers raw transactions + categorized data + vector embeddings + cumulative profile + Health Score history + feedback data
- Data minimization; `ai_processing` consent at signup; separate `chat_processing` consent for Epic 10
- Financial advice disclaimer; DPIA before public launch
- PCI-DSS not in scope (card data handled by Fondy / LemonSqueezy)

**Risk Mitigations (Domain + Technical + Market + Resource)**
Twelve technical + market + resource risk rows. Notable Epic 9/10 additions already present:
- Bedrock/AgentCore region availability (eu-central-1) — Story 9.4 blocking spike
- AgentCore runtime cost exceeds budget — cost tags + token spend monitoring + abuse limits
- Titan/Cohere embedding quality on Ukrainian content — Story 9.1 harness-gated
- Red-team corpus incomplete at launch — OWASP + published datasets + quarterly review
- Chat as unexpected PII/regulatory hot-spot — separate `chat_processing` consent + retention + cascade delete
- Celery→Step Functions migration overreach — time-boxed recommendation-only spike (9.8)
- Prompt injection / jailbreak in chat — Guardrails + hardening + CI gate + canaries
- LLM tool misuse in chat — AgentCore allowlist
- Conversation-history leakage across sessions/users — per-user-per-session isolation + cascade + audit

**Tech-stack commitments**
- Frontend: Next.js (App Router, SPA), React Query, Vercel AI SDK
- Backend: FastAPI, LangGraph, Celery + Redis, PostgreSQL + pgvector
- Embeddings: OpenAI text-embedding-3-small today (Epic 9 re-evaluates)
- LLM: multi-provider `llm.py` (Anthropic / OpenAI / Bedrock); Epic 10 targets Bedrock + AgentCore
- Auth: AWS Cognito + JWT; RLS as defense-in-depth
- Payments: Fondy (UA) + LemonSqueezy (international)

### PRD Completeness Assessment

**Strengths**
- FRs cover all stated user journeys (Anya / Viktor / Dmytro / Error Recovery / Admin) with clear traceability to journey-revealed capabilities.
- NFR targets are measurable and phased by epic (MVP vs Epic 10 addendum). AI Safety NFRs are concrete (≥ 95% corpus pass, ≥ 90% grounding, 100% Guardrails coverage).
- Epic 9/10 additions are internally consistent with the sprint-change-proposal: new FRs (64–72), new AI Safety NFR block, expanded Integration table, and new risk rows all line up.
- Retention, deletion, and consent scoping are explicit — the `chat_processing` vs `ai_processing` separation is PRD-level, not implementation-level.

**Gaps / Watch-items for later steps**
- **FR56–FR63 reservation is fragile.** The PRD does not currently show these numbers as "reserved" inline — it jumps from FR55 to FR64. Only the sprint-change-proposal document explains the gap. A reader of the PRD alone might think it's an error. Worth a one-line inline note in the PRD's Chat-with-Finances section.
- **No FR covers the RAG evaluation harness (Story 9.1 / 9.2).** Harness is in the architecture + epics, but there's no PRD-level requirement mandating its existence. It's NFR-shaped (quality/regression), not FR-shaped — consider whether an explicit NFR under AI Safety or Reliability is warranted.
- **No FR covers `llm.py` multi-provider directly** — it lives in NFR-S7 and NFR-I5 only. Fine, but verify Epic 9 stories map to the NFR (not a phantom FR).
- **FR66 "cross-session memory" scope semantics** — PRD says memory "survives sign-out/sign-in within retention window." Architecture (as refined this session) says this is satisfied by *history* (resumable transcript), NOT by cross-session *context carry-over* (persistent memory tracked as TD-040). This is a subtle PRD↔Architecture alignment risk — the PRD wording reads like cross-session memory persistence. Flag for Step 3 coverage check.
- **Consent drift handling (active sessions during version bump)** — covered in architecture but not in PRD FRs. PRD's FR71 says chat is blocked until consent granted; silent on what happens when consent version bumps mid-session. Minor — the architecture commits a policy, but PRD should at minimum reference it.
- **Voice I/O and chat write-actions** — listed as Phase 2 follow-ups in PRD scope section; no FRs allocated (correctly deferred).
- **Subscription gate follow-up (FR72)** — no FR number reserved for the gate; tracked as narrative "follow-up story once payments land." Acceptable while payments epic is itself unscoped, but fragile.

**Overall: PRD is materially complete and internally consistent.** The four watch-items above are coverage-alignment risks to verify in Step 3 (Epic Coverage Validation), not structural PRD defects.

---

## 3. Epic Coverage Validation

### Epics document structure

The epics document includes its own self-contained Requirements Inventory (FR1–FR63 + NFR1–NFR31) followed by a "FR Coverage Map" table mapping each FR to an Epic, and per-Epic "**FRs covered:**" summaries. This is a strong traceability contract — but the contract was not updated for Epic 9/10.

### Coverage Matrix

| FR # | PRD-side | Epics FR Coverage Map | Per-epic summary | Story-level traceability | Status |
|---|---|---|---|---|---|
| FR1–FR8 | ✅ | ✅ Epic 2 | ✅ Epic 2 | ✅ Stories 2.1–2.5 | ✓ Covered |
| FR9–FR11 | ✅ | ✅ Epic 3 | ✅ Epic 3 | ✅ Stories 3.1, 3.2, 3.3 | ✓ Covered |
| FR12–FR13 | ✅ | ✅ Epic 2 | ✅ Epic 2 | ✅ Stories 2.5, 2.6 | ✓ Covered |
| FR14–FR19 | ✅ | ✅ Epic 3 | ✅ Epic 3 | ✅ Stories 3.4–3.8 | ✓ Covered |
| FR20–FR24 | ✅ | ✅ Epic 4 | ✅ Epic 4 | ✅ Stories 4.4–4.8 | ✓ Covered |
| FR25–FR30 | ✅ | ✅ Epic 1 | ✅ Epic 1 | ✅ Stories 1.1–1.7 | ✓ Covered |
| FR31–FR36 | ✅ | ✅ Epic 5 | ✅ Epic 5 | ✅ Stories 5.1–5.6 | ✓ Covered |
| FR37–FR40 | ✅ | ✅ Epic 6 | ✅ Epic 6 | ✅ Stories 6.1–6.3 | ✓ Covered |
| FR41–FR44 | ✅ | ✅ Epic 6 | ✅ Epic 6 | ✅ Stories 6.4–6.6 | ✓ Covered |
| FR45–FR49 | ✅ | ✅ Epic 7 | ✅ Epic 7 | ✅ Stories 7.1–7.4 | ✓ Covered |
| FR50–FR51 | ✅ | ✅ Epic 7 | ✅ Epic 7 | ✅ Stories 7.5–7.6 | ✓ Covered |
| FR52–FR55 | ✅ | ✅ Epic 7 | ✅ Epic 7 | ✅ Stories 7.7–7.8 | ✓ Covered |
| **FR56** | ❌ **missing in PRD** | ✅ Epic 8 | ✅ Epic 8 | ✅ Story 8.2 | ⚠ **PRD SYNC GAP** |
| **FR57** | ❌ **missing in PRD** | ✅ Epic 8 | ✅ Epic 8 | ✅ Story 8.1 | ⚠ **PRD SYNC GAP** |
| **FR58** | ❌ **missing in PRD** | ✅ Epic 8 | ✅ Epic 8 | ✅ Story 8.3 | ⚠ **PRD SYNC GAP** |
| **FR59** | ❌ **missing in PRD** | ✅ Epic 8 | ✅ Epic 8 | ✅ Story 8.4 | ⚠ **PRD SYNC GAP** |
| **FR60** | ❌ **missing in PRD** | ✅ Epic 8 | ✅ Epic 8 | ✅ Story 8.2 | ⚠ **PRD SYNC GAP** |
| **FR61** | ❌ **missing in PRD** | ✅ Epic 1 | ✅ Epic 1 | ✅ Story 1.8 (shipped) | ⚠ **PRD SYNC GAP** |
| **FR62** | ❌ **missing in PRD** | ✅ Epic 2 | ✅ Epic 2 | ✅ Story 2.9 (shipped) | ⚠ **PRD SYNC GAP** |
| **FR63** | ❌ **missing in PRD** | ✅ Epic 2 | ✅ Epic 2 | ✅ Story 2.8 (shipped) | ⚠ **PRD SYNC GAP** |
| **FR64** (chat open) | ✅ | ❌ not in map | ❌ no summary on Epic 10 | ✅ Stories 10.4, 10.6 | ⚠ **Epic 10 TRACE GAP** |
| **FR65** (streaming) | ✅ | ❌ not in map | ❌ no summary | ✅ Story 10.4 | ⚠ **Epic 10 TRACE GAP** |
| **FR66** (cross-session memory) | ✅ | ❌ not in map | ❌ no summary | ⚠ Story 10.3 (ambiguous — see below) | ⚠ **SEMANTIC CONFLICT** |
| **FR67** (grounding) | ✅ | ❌ not in map | ❌ no summary | ✅ Story 10.5 | ⚠ **Epic 10 TRACE GAP** |
| **FR68** (citations) | ✅ | ❌ not in map | ❌ no summary | ✅ Story 10.5 | ⚠ **Epic 10 TRACE GAP** |
| **FR69** (principled refusal) | ✅ | ❌ not in map | ❌ no summary | ✅ Story 10.4 | ⚠ **Epic 10 TRACE GAP** |
| **FR70** (chat history deletion) | ✅ | ❌ not in map | ❌ no summary | ✅ Story 10.1 (cascade) + 10.9 (view/delete) | ⚠ **Epic 10 TRACE GAP** |
| **FR71** (`chat_processing` consent) | ✅ | ❌ not in map | ❌ no summary | ✅ Story 10.1 | ⚠ **Epic 10 TRACE GAP** |
| **FR72** (ungated launch; follow-up gate) | ✅ | ❌ not in map | ❌ no summary | ❌ **no explicit story** — narrative only (Epic 10 "Does NOT depend on payments") | ⚠ **UNTRACKED** |

### Epic 9 (AI Infra Readiness)

Epic 9 is deliberately **NFR-/infra-shaped** — no new PRD FRs. Its success criteria map to existing NFRs (multi-provider abstraction, RAG harness as regression gate, region validation, IAM). This is legitimate — not every epic needs an FR. However, the PRD's Non-Functional Requirements section adds new NFR-shaped requirements (Chat rate limiting, `llm.py` multi-provider, full AI Safety block) that are **not mirrored** in the Epics-document NFR list (which still stops at NFR31). See NFR gap below.

### NFR Coverage Gap

| PRD NFR | Epics NFR list | Gap |
|---|---|---|
| NFR-S6 (chat rate limiting) | ❌ | Missing — covered by Epic 10 Stories 10.3/10.10 narratively |
| NFR-S7 (`llm.py` multi-provider, env-driven) | ❌ | Missing — covered by Epic 9 Story 9.5 narratively |
| NFR-AI1..AI7 (AI Safety block: 100% Guardrails, ≥95% corpus pass, OWASP coverage, zero PII, ≥90% grounding, refusal correctness, safety observability) | ❌ | Missing — covered by Epic 10 narratively (Stories 10.2, 10.5, 10.7, 10.8) |
| NFR-I6 (Bedrock Guardrails SDK) | ❌ | Missing — covered by Epic 10 Story 10.2 |
| NFR-I7 (Bedrock AgentCore SDK) | ❌ | Missing — covered by Epic 10 Story 10.3 |
| NFR-I8 (embedding-model decision gate) | ❌ | Missing — covered by Epic 9 Story 9.3 |

Epics NFR list should be extended to NFR32+ to capture the above for traceability. Implementation is covered via stories; **the gap is purely in the traceability documentation.**

### Missing Requirements — Detail

#### ⚠ Critical: FR56–FR63 missing from PRD

**What:** The PRD's Functional Requirements section ends at FR55 and resumes at FR64. FR56–FR63 are allocated in the Epics document (and some are already shipped — Stories 1.8, 2.8, 2.9 per git log) but never back-filled into the PRD.

**Impact:** PRD no longer reflects the shipped product. Any reader of the PRD alone sees a numbering gap with no explanation (the reservation rationale lives only in the sprint-change-proposal footnote). Traceability audits will flag this. New contributors joining from the PRD may assume those FRs are out-of-scope.

**Recommendation:** Add a new "Phase 1.5 Requirements" subsection to the PRD's Functional Requirements section, mirroring the Epics doc entries for FR56–FR63. This is a clerical sync, not a scope decision.

#### ⚠ Critical: Epic 10 not in FR Coverage Map

**What:** FR64–FR72 are in the PRD; the Epics document's FR Coverage Map table stops at FR63. Epic 10's section shows a Goal, Success Criteria, and Stories, but no `**FRs covered:**` summary line (unlike Epics 1–8).

**Impact:** Same class of traceability audit failure. A reviewer cross-checking PRD ↔ Epics via the coverage table will see Chat FRs as unmapped. Story-level traceability is implicit and good, but the aggregate coverage map is incomplete.

**Recommendation:** Extend the FR Coverage Map table with FR64–FR72 → Epic 10 rows, and add `**FRs covered:** FR64, FR65, FR66, FR67, FR68, FR69, FR70, FR71, FR72` to the Epic 10 section header. Purely clerical.

#### ⚠ Semantic: FR66 wording vs. Epic 10 scope

**What:** FR66 reads: *"Chat maintains cross-session memory per user (conversation history survives sign-out/sign-in within retention window)."* Architecture (as refined this session) says persistent per-user context carry-over is **not** in Epic 10 — it's TD-040. Epic 10 ships durable *history* (viewable, resumable transcripts), not cross-session memory semantics. Story 10.3 talks about AgentCore "stateful multi-turn" which is *within* a session; Story 10.9 covers history view/delete.

**Impact:** FR66's wording reads broader than what Epic 10 delivers. A user reading the PRD literally will expect the agent to "remember" them across sessions. What they get is resumable transcripts and no derived memory. This is a user-expectations bug in FR66, not a coverage gap.

**Recommendation (user / PO decision):**
- **Option A (prefer)** — Amend FR66: *"Users can view, resume, and delete their chat history across sessions within the retention window; persistent per-user context carry-over between sessions is deferred (TD-040)."* Consistent with architecture + Epic 10 stories.
- **Option B** — Leave FR66 as-is and add a cross-session memory story to Epic 10. Much larger scope increase; every AI-safety layer needs extension per TD-040.

#### ⚠ Minor: FR72 has no explicit story

**What:** FR72 says "chat is ungated at initial launch; a subscription gate is added in a follow-up story once freemium payments integration lands." Epic 10's "Out of Scope" section matches this but no story exists.

**Impact:** Low. The "ungated" behavior is the default-absence-of-gate — not something that needs a story. The future gate is explicitly tracked as a post-epic follow-up. Acceptable if tracked as tech debt or a placeholder story.

**Recommendation:** Add a placeholder story or TD entry ("TD-041 — Chat subscription gate pending payments epic") so the follow-up isn't lost.

### Coverage Statistics

| Metric | Value |
|---|---|
| Total PRD FRs | **64** (FR1–FR55, FR64–FR72) |
| Total Epics-doc FRs | **63** (FR1–FR63; FR64–FR72 *de facto* covered via Epic 10 stories but not in the Coverage Map table) |
| FRs fully traced (PRD + Coverage Map + per-Epic summary + Story) | **55** (FR1–FR55) |
| FRs shipped but missing from PRD | **8** (FR56–FR63) |
| FRs present in PRD but missing from Epics Coverage Map | **9** (FR64–FR72) |
| FRs with semantic conflict | **1** (FR66) |
| FRs without explicit story | **1** (FR72) |
| **Effective end-to-end coverage** | **~86%** (55 of 64 fully traced) |

Important caveat: the ~14% "coverage gap" is **almost entirely traceability-documentation drift, not missing implementation.** Stories covering FR56–FR72 all exist (several are shipped). The fix is documentation sync, not new scope.

### Summary of Coverage Findings

1. **Purely clerical sync** (no scope impact): PRD needs FR56–FR63 back-filled; Epics needs FR64–FR72 added to Coverage Map + Epic 10 summary; Epics NFR list needs extension for AI Safety NFRs.
2. **Semantic decision needed** (FR66 wording vs. delivered scope): PO to choose amend-FR vs. add-story.
3. **Minor tracking** (FR72 follow-up): a placeholder story or TD entry.

**No functional FR is missing an implementation path.** The Epic 9 + 10 architecture refinements applied earlier this session already cover the underlying work; the report above reflects *documentation* readiness, not *implementation* readiness.

---

## 4. UX Alignment Assessment

### UX Document Status

**Found.** [ux-design-specification.md](ux-design-specification.md) — 100.6 KB, last modified 2026-04-18. Comprehensive spec covering executive summary, user experience pillars, design system (shadcn/ui + Tailwind 4.x), emotional design, UX pattern analysis, visual design foundation, four user journeys, component strategy, consistency patterns (buttons, feedback, forms, navigation, modals, empty states, animations, data display), responsive design + accessibility, implementation guidelines. Includes a Chat-with-Finances placeholder section [ux-design-specification.md:1563-1581](ux-design-specification.md) deferring full spec to Epic 10 Story 10.11.

### UX ↔ PRD Alignment

**Coverage for MVP and Phase 1.5:** Strong.

| PRD area | UX coverage | Status |
|---|---|---|
| User journeys (Anya / Viktor / Dmytro / Error Recovery) | 4 dedicated journey flows | ✅ Aligned |
| Teaching Feed card stack (FR14–FR19) | Card stack navigation, progressive disclosure, progressive appearance | ✅ Aligned |
| Upload UX (FR1–FR7) | Drag-and-drop + file picker, trust-first messaging | ✅ Aligned |
| Health Score (FR21–FR22) | Apple-Fitness-inspired ring, animated transitions, static fallback | ✅ Aligned |
| Triage severity colors (FR58–FR59) | Red/yellow/green + icons + text (color-independence) | ✅ Aligned |
| Bilingual (FR11, FR29) | UA + EN throughout; language selector | ✅ Aligned |
| Feedback (FR45–FR55) | CardFeedbackBar, FollowUpPanel, ReportIssueForm, MilestoneFeedbackCard components specified | ✅ Aligned |
| Privacy / consent UX (FR32, FR36) | Onboarding consent flow + disclaimer | ✅ Aligned |
| Error handling (FR37, FR40) | Lighthearted warm error copy, actionable guidance | ✅ Aligned |

**Gaps:**
- **Chat UX (FR64–FR72)** — placeholder only; full spec deferred to Story 10.11. This is the architecturally-correct pattern (avoid premature UX spec before AgentCore region validation is complete), but it means FR64–FR72 currently lack UX traceability. Story 10.11's outputs will close the gap.

### UX ↔ Architecture Alignment

**Tech-stack consistency:** Aligned — UX spec calls out shadcn/ui, Tailwind 4.x, Framer Motion, `prefers-reduced-motion`, Next.js App Router. Architecture's tech decisions table matches.

**Performance / responsiveness:** Aligned — UX mobile-first + touch-optimized specs match architecture NFRs (mobile 3G, Lighthouse > 80, < 500ms card render).

**Accessibility:** Aligned — UX spec has a dedicated Responsive Design & Accessibility section, explicit WCAG 2.1 AA, keyboard nav, screen-reader semantic HTML, color-independence rule. Matches architecture and PRD NFRs.

**Streaming / SSE:** Aligned — UX calls out progressive card appearance tied to SSE events; architecture commits to SSE as the streaming pattern.

**Gaps introduced by this session's architecture refinements (not yet reflected in UX placeholder):**

| Architecture element (AI Safety § refined 2026-04-19) | UX placeholder status | Recommendation |
|---|---|---|
| `correlation_id` in `CHAT_REFUSED` envelope (for support triage) | ❌ Placeholder doesn't mention | Add bullet to 10.11 scope: "Refusal UI surfaces correlation ID for support reference (copy-to-clipboard affordance)" |
| `reason` enum: `guardrail_blocked` / `ungrounded` / `rate_limited` / `prompt_leak_detected` | ❌ Treated as a single "principled refusal" | Add bullet: "Reason-specific refusal copy (e.g., rate-limited → retry guidance; ungrounded → clarify-your-question prompt), all principled — no filter-rationale leakage" |
| Consent version bump mid-session policy (active sessions continue; new sessions re-prompt) | ❌ Only "first-use" consent prompt covered | Add bullet: "Re-consent prompt flow when `chat_processing` version bumps; active session continues; new session gated" |
| Memory & Session Bounds (20 turns / 8k tokens with server-side summarization) | ❌ Not mentioned | Add optional bullet: "Visualization of conversation summarization when turn cap reached (optional — decide in 10.11)" |
| Canary-leak refusal (`reason=prompt_leak_detected`) surface | ❌ Not mentioned | Covered by the `reason` enum bullet above |

These are minor placeholder-scope additions that keep Story 10.11 aligned with the newly-refined architecture. Not blocking.

### Warnings

1. **Chat UX spec is deferred to Story 10.11 inside Epic 10.** This is correct — Bedrock/AgentCore region validation (Story 9.4) precedes any UX commitment. But it creates a sequencing dependency: Story 10.11 must be scoped to complete *before* Stories 10.4/10.6 (chat streaming + UI shell) can lock their implementation.
2. **UX placeholder scope list is slightly behind the architecture.** Five minor items (table above) should be added to the placeholder so Story 10.11's author doesn't miss them. Purely clerical.

### Summary

**UX is well-aligned with PRD and Architecture for MVP + Phase 1.5.** For Epic 10:
- Placeholder correctly defers full spec to Story 10.11.
- Architecture refinements from 2026-04-19 (correlation ID, reason enum, consent drift, session bounds) should be folded back into the placeholder scope list.
- No structural misalignment; only clerical drift.

---

## 5. Epic Quality Review

### Cross-Epic Dependency Graph

| Epic | Depends on | Blocks | Forward-reference violations? |
|---|---|---|---|
| 1. Foundation & Auth | — | 2–10 | ✅ None |
| 2. Upload & Ingestion | 1 | 3, 4, 5, 6, 8 | ✅ None |
| 3. Teaching Feed | 1, 2 | 4, 7, 8 | ✅ None |
| 4. Health Score | 1, 2, 3 | 7 (FR52 milestone) | ✅ None |
| 5. Privacy & Consent | 1, 2 | 7 (FR49 export/delete) | ✅ None |
| 6. Errors & Ops | 2, 3 | — | ✅ None |
| 7. Feedback | 3, 4, 5 | — | ✅ None (explicit) |
| 8. Pattern / Triage / Subscription | 3 | — | ✅ None |
| 9. AI Infra Readiness | 8 | 10 | ✅ None |
| 10. Chat-with-Finances | 9 (esp. 9.4, 9.5, 9.7) | — | ✅ None |

**Cross-epic dependencies are clean** — no forward references, correct topological order.

### User-Value Check

| Epic | Framing | Verdict |
|---|---|---|
| 1–8 | All user-centric (Epic 6 dual user/operator) | ✅ |
| 9 | "AI Infra Readiness" | ⚠ **Technical/infra epic** — no direct user value |
| 10 | "Chat-with-Finances" | ✅ |

**Epic 9 is a technical/infra epic.** Per strict best-practices rules, this is a red flag. Counter-argument: Epic 9 is *explicitly framed* as an Epic 10 prerequisite — grouping infra work here is pragmatic (otherwise Epic 10 balloons). Status, goal, and dependencies make the role explicit. **Acceptable exception**, not a defect — but worth flagging so the pattern isn't replicated casually.

### Story Pattern Consistency (Epics 1–8 vs. 9–10)

**Epics 1–8** — every story follows high-quality pattern:
- User-story framing: *"As a [role], I want [X], so that [Y]."*
- Given/When/Then acceptance criteria, multiple per story, testable + specific
- Example: [Story 1.3](epics.md) — full framing + 4 BDD ACs

**Epics 9–10** — stories are **one-line stubs**, NOT elaborated:
- No user-story framing, no Given/When/Then ACs
- Format: `**9.X — Name**` + 1–3 sentences of scope
- Example: *"9.5 — llm.py Multi-Provider ... Refactor llm.py to route by LLM_PROVIDER env var..."*

**Verdict:** A **major quality inconsistency** — but arguably legitimate backlog-state pattern (Epic 9/10 explicitly **Status: Backlog**, sprint-change-proposal hands off to SM for story creation). **Risk:** If a dev picks up a Story 9.X / 10.X as-is today, there are no ACs. Epic 9/10 are **not story-level sprint-ready** yet. SM must elaborate to match the Epics 1–8 pattern.

### Story-Sizing — Mini-Epic Risk

Several Epic 9/10 stubs are likely to split during elaboration:

| Stub | Split risk | Why |
|---|---|---|
| 9.5 — llm.py Multi-Provider | High | Refactor + Bedrock client + regression suite across 3 providers × Epic 3 + 8 agents |
| 10.3 — Chat Agent Skeleton | High | AgentCore session handler + prompt hardening + tool manifest + rate-limit envelope |
| 10.7 — AI Safety Test Harness | Medium | Corpus creation + runner + CI integration + ≥ 5 categories |
| 10.11 — UX Spec Update for Chat | Medium | Full chat UX spec (layout + composer + streaming + citations + refusals + consent + deletion + mobile + UA/EN + WCAG) |

Final story count will **likely exceed 8 + 11 = 19**.

### 🔴 Critical Finding: Story-Order vs. Delivery-Order in Epic 10

**Issue:** Story 10.11 (UX Spec Update) is numbered **last** in Epic 10, but the UX spec is a **prerequisite** for Story 10.6 (Chat UI). If delivered in number order, Story 10.6 lands before 10.11 exists → the Chat UI is implemented without a formal UX spec, working only from the 18-line placeholder + architecture section.

**Impact:** Undersignals UX design effort. Developer makes UX decisions that should have been design decisions. Accessibility + UA/EN edge cases at risk. Rework likely when 10.11 lands.

**Recommendation:** Renumber 10.11 to land earlier (e.g., before 10.4 / 10.6) OR add an explicit "numbering ≠ delivery order; 10.11 is a prerequisite to 10.4 / 10.6" note in Epic 10's header.

### Acceptance Criteria Quality (Epics 1–8 spot-check)

Spot-checked Stories 1.1, 1.3, 5.1, 8.3: all BDD-formatted, specific, testable, covering happy-path + error conditions. No vague ACs. ✅

### Database/Entity Creation Timing

Spot-checked: tables created when first needed, in the introducing story:
- `user_consents` → Story 5.2
- `audit_logs` → Story 5.6
- `card_feedback` → Story 7.2
- `pattern_findings`, `detected_subscriptions` → Stories 8.1 / 8.2
- `chat_sessions` / `chat_messages` → Story 10.1

Pattern is textbook correct. ✅

### Starter-Template Check (Greenfield)

PRD classifies project as greenfield. Story 1.1 is the initial-setup story creating the Next.js + FastAPI monorepo with PostgreSQL/Redis docker-compose. ✅

### Quality Assessment Summary

#### 🔴 Critical Violations

1. **Epic 10 Story 10.11 sequencing** — UX spec is numbered last but prerequisite for Story 10.6. Renumber or annotate.

#### 🟠 Major Issues

1. **Epic 9 and Epic 10 stories are stubs.** No user-story framing, no Given/When/Then ACs. Must be elaborated by SM before entering any sprint.
2. **Several Epic 9/10 stubs are likely mini-epics** (9.5, 10.3, 10.7, 10.11). Expect final story count to exceed 19.
3. **Epic 10 missing `**FRs covered:**` summary line** (repeat of Step 3 finding).
4. **Epics NFR list ends at NFR31** — PRD's new AI Safety NFR block (NFR-AI1..7 + related) has no mirror. Extend to NFR32+.

#### 🟡 Minor Concerns

1. **Epic 9 is a technical/infra epic.** Acceptable pragmatic exception; pattern should be used sparingly.
2. **FR72 (subscription gate)** has no story; add a TD entry or placeholder story.
3. **Consent drift / version-bump re-prompt** has no explicit story coverage — fold into Story 10.1 elaboration.
4. **Epic 10 out-of-scope** excludes "New RAG corpus content creation" — acceptable, but chat effectiveness depends partly on corpus coverage of chat-style questions; flag for Phase 2 retrospective.

### Best-Practices Compliance Checklist

| Check | Epics 1–8 | Epic 9 | Epic 10 |
|---|---|---|---|
| Epic delivers user value | ✅ | ⚠ infra exception | ✅ |
| Epic functions independently (given upstream) | ✅ | ✅ | ✅ |
| Stories appropriately sized | ✅ | ⚠ stubs; mini-epic risk | ⚠ stubs; mini-epic risk |
| No forward dependencies (cross-epic) | ✅ | ✅ | ✅ |
| No forward dependencies (within-epic) | ✅ | ✅ | 🔴 **10.6 needs 10.11** |
| Database tables created when needed | ✅ | n/a | ✅ |
| Clear acceptance criteria | ✅ | ❌ stubs lack ACs | ❌ stubs lack ACs |
| Traceability to FRs maintained | ✅ | n/a (infra) | ⚠ missing in Coverage Map |

---

## 6. Summary and Recommendations

### Overall Readiness Status

**Epics 1–8: READY FOR IMPLEMENTATION** — several already shipped (per git log: Stories 7.9, 8.1, 8.2, 8.3, 8.4). PRD, architecture, UX, and stories all aligned; ACs are BDD-formatted and testable.

**Epics 9–10: BACKLOG — NOT YET STORY-LEVEL READY.** The architecture is now complete and cohesive (refined 2026-04-19 in this session); success criteria are clear; dependencies are correctly sequenced. But the stories themselves are one-line stubs with no user-story framing and no Given/When/Then ACs. SM must elaborate them to the quality of Epics 1–8 before any story enters a sprint. Several stubs will likely split into 2–3 stories during elaboration.

**Overall:** **NEEDS WORK (documentation-level).** The implementation path is sound — no scope is missing, no FR lacks a home, no forward dependencies exist across epics. The remediation surface is traceability drift plus Epic 9/10 story elaboration.

### Issues by Severity

#### 🔴 Critical Issues (Blocking)

1. **Story 10.11 sequencing** ([epics.md:1987](epics.md)) — UX Spec is numbered last but is a prerequisite for Story 10.6 (Chat UI). Either renumber to land before 10.4/10.6, OR add an explicit "numbering ≠ delivery-order" note in Epic 10's header. **This is the one genuine blocker** — all other issues are clerical or backlog-elaboration work.

#### 🟠 Major Issues (Address Before Starting Epic 9/10)

1. **PRD missing FR56–FR63** — 8 allocated FRs never back-filled into PRD. Epics doc has them; some already shipped (Stories 1.8, 2.8, 2.9 per git log). Fix: add a Phase 1.5 Requirements subsection to PRD.
2. **Epics FR Coverage Map missing FR64–FR72 + Epic 9/10 rows** — Coverage Map table stops at FR63; Epic 10 has no `**FRs covered:**` summary line. Fix: extend Coverage Map table and add summary lines to Epic 9 (NFR-only note) + Epic 10 (FR64–FR72).
3. **Epics NFR list ends at NFR31** — PRD's new AI Safety NFR block (≥ 95% red-team pass rate, 100% Guardrails coverage, ≥ 90% grounding, chat rate limits, multi-provider abstraction, Bedrock SDK integrations, embedding decision gate) is unmirrored in the Epics-doc NFR list. Fix: extend to NFR32+.
4. **Epic 9/10 stories are stubs.** No user-story framing, no Given/When/Then ACs. SM must elaborate before pulling into any sprint. Several stubs (9.5, 10.3, 10.7, 10.11) are mini-epics likely to split.
5. **FR66 semantic conflict** — PRD wording says "cross-session memory"; architecture + Epic 10 deliver durable history only (cross-session *context carry-over* is TD-040). **User / PO decision required**:
   - Option A (preferred) — amend FR66 to "durable history" wording
   - Option B — add a cross-session memory story to Epic 10 (much larger scope increase)

#### 🟡 Minor Concerns (Opportunistic)

1. **UX placeholder scope list** is behind the architecture — 5 bullets to add for Story 10.11 author (correlation ID in refusals, reason-specific refusal copy, consent-version-bump re-prompt, session-summarization UX, canary-leak surface).
2. **Epic 9 is an infra epic** — acceptable pragmatic exception (explicitly framed as Epic 10 prerequisite); don't replicate casually.
3. **FR72 (subscription gate follow-up)** has no story or TD entry. Add a placeholder to avoid losing the follow-up.
4. **Consent drift / version-bump re-prompt flow** — architecture commits a policy but no explicit story. Fold into Story 10.1 elaboration.
5. **Chat-specific RAG corpus content** — Epic 10 out-of-scope excludes this; flag for Phase 2 retrospective since chat effectiveness partly depends on it.

### Recommended Next Steps (Ordered)

1. **[Critical — fix before Epic 10 planning]** Resolve Story 10.11 sequencing. Renumber to 10.2.5 or 10.3 (ideally before 10.4 and 10.6), OR add the "numbering ≠ delivery-order" annotation. 10-minute edit.
2. **[Major — clerical sync, ~1 hour]**
   - Back-fill FR56–FR63 into PRD's Functional Requirements section (source: Epics doc's own Phase 1.5 Requirements block).
   - Extend Epics FR Coverage Map with FR64–FR72 rows; add `**FRs covered:**` summary to Epic 10.
   - Extend Epics NFR list to NFR32+ capturing the PRD's AI Safety NFR block, chat rate limits, and multi-provider/Bedrock integration NFRs.
3. **[Major — user/PO decision]** Decide FR66 wording: amend to "durable history across sessions" (Option A, preferred, aligns with architecture + TD-040) or add a cross-session memory story (Option B, significant scope expansion). Takes 5 minutes once a call is made.
4. **[Major — SM work, probably 1–2 sprints of elaboration]** SM elaborates Epic 9 and Epic 10 story stubs to the quality of Epics 1–8 (user-story framing, Given/When/Then ACs). Expect 9.5 / 10.3 / 10.7 / 10.11 to split into 2–3 stories each — the final Epic 9 + 10 may carry 25–30 stories total, not 19. This is normal and healthy.
5. **[Major — gated by Story 9.4]** Story 9.4 (AgentCore + Bedrock region availability spike) **must complete before Epic 10 scope-lock**. Region validation outcome determines whether the data-residency ADR is needed (for cross-region inference profiles) and may trigger a pivot. This is already in the sprint-change-proposal handoff plan.
6. **[Minor — cleanup]**
   - Fold the 5 UX placeholder scope additions into ux-design-specification.md's Chat-with-Finances section so Story 10.11's author has a complete brief.
   - Add a TD entry or placeholder story for FR72 (subscription gate follow-up).
   - Ensure Story 10.1 elaboration covers the consent-version-bump re-prompt flow.
7. **[Nice-to-have]** Consider adding an explicit NFR for the RAG evaluation harness (infrastructure / regression gate) and `llm.py` multi-provider invariant, so Epic 9's infra deliverables have first-class NFR traceability rather than living only in narrative success-criteria.

### Ship-Readiness Gates

Before Epic 10 commits (in priority order):

- [ ] Story 9.4 region validation result known (pass / fail / pivot-needed)
- [ ] Data-residency ADR signed off if cross-region inference required
- [ ] Story 10.11 renumbered or annotated — **blocks Epic 10 story sequencing**
- [ ] Epic 9 + 10 stubs elaborated to Epics 1–8 quality bar
- [ ] PRD / Epics doc clerical sync complete (FR56–63, FR64–72 in Coverage Map, NFR32+)
- [ ] FR66 wording decision locked (PO)
- [ ] UX placeholder scope aligned with architecture refinements

### Final Note

This assessment identified **11 issues** across **3 categories** (1 critical, 5 major, 5 minor).

- **Implementation readiness for MVP + Phase 1.5 (Epics 1–8):** ✅ Ready. Work is either shipping or in-flight on well-formed stories.
- **Implementation readiness for Phase 2 (Epics 9–10):** ⚠ Architecture + scope are sound, but stories need elaboration before dev can start. One genuine blocker (Story 10.11 sequencing) plus clerical sync work; the rest is normal backlog-to-sprint elaboration.

The underlying product planning is strong. **No hidden scope**, **no forward dependencies**, **no structural misalignment**. The findings above are the healthy residue of a fast-moving sprint change proposal — surface them, clean them up, and the Epic 9 → Epic 10 sequence can proceed on a firm footing.

**Assessor:** Winston (Architect) facilitating Implementation Readiness workflow
**Date:** 2026-04-19
**Prior related work (same session):** Bedrock Migration + AI Safety Architecture refinements applied to [architecture.md](architecture.md); TD-039 + TD-040 added to [../../docs/tech-debt.md](../../docs/tech-debt.md).

---

## 7. Remediation Applied (2026-04-19)

All critical + major findings except the SM-elaboration work were addressed in-session. Changes below.

### 🔴 Critical — resolved

| Finding | Action |
|---|---|
| Story 10.11 sequencing (UX Spec numbered last but prerequisite for Chat UI) | **Renumbered.** UX Spec moved to 10.3; old 10.3–10.10 each shifted +1. Delivery-order = numbering. Cross-references in architecture.md updated (Stories 10.3 → 10.4, 10.5 → 10.6, 10.7 → 10.8, 10.8 → 10.9, 10.10 → 10.11). Explanatory note added to Epic 10 story list. |

### 🟠 Major — resolved

| Finding | Action |
|---|---|
| PRD missing FR56–FR63 | **Back-filled.** New "Phase 1.5 — Pipeline Completion & Promoted Story Back-fills" subsection in [prd.md](prd.md) Functional Requirements. Wording sourced from the Epics doc's own Phase 1.5 Requirements block. |
| FR66 semantic conflict (cross-session memory wording vs. delivered scope) | **Amended (Option A).** FR66 now reads "durable history across sessions" with explicit reference to TD-040 for persistent cross-session memory. Aligns PRD ↔ Architecture ↔ Epic 10 Story 10.10. |
| Epics FR Coverage Map missing FR64–FR72 | **Extended.** 9 new rows added to the coverage map; Epic 10 section now has `**FRs covered:** FR64…FR72` summary line. |
| Epic 9 missing coverage summary | **Added.** `**FRs covered:** None (infra epic)` + `**NFRs covered:**` lines added to Epic 9 header and Epic List entry. |
| Epics NFR list ends at NFR31 (missing AI Safety / chat / Bedrock NFRs) | **Extended to NFR44.** New "Phase 2 NFRs (Epic 9 + Epic 10)" block with NFR32 (multi-provider), NFR33 (RAG harness), NFR34 (Guardrails 100%), NFR35 (red-team ≥ 95%), NFR36 (OWASP + UA corpus), NFR37 (zero PII leakage), NFR38 (grounding ≥ 90%), NFR39 (refusal correctness), NFR40 (Bedrock reliability), NFR41 (AgentCore isolation), NFR42 (embedding decision gate), NFR43 (chat rate limits), NFR44 (safety observability). Epic 9/10 headers cite the specific NFRs they cover. |

### 🟡 Minor — resolved

| Finding | Action |
|---|---|
| UX placeholder scope list behind architecture | **5 bullets added** to ux-design-specification.md Chat-with-Finances placeholder: consent-version-bump re-prompt, reason-specific refusal copy, correlation-ID display, session-summarization UX (optional), canary-leak surface (folded into reason enum). |
| FR72 subscription gate follow-up untracked | **Added TD-041** in tech-debt register — reminder to scope a chat subscription gate story when the payments epic lands. FR72 wording and Epic 10 header updated to reference TD-041. |
| Consent-drift policy has no story coverage | **Folded into Story 10.1** scope — consent-version-bump re-prompt flow now explicit in the story stub. |

### Files modified in remediation

| File | Changes |
|---|---|
| [prd.md](prd.md) | FR56–FR63 back-filled; FR66 amended (Option A) |
| [epics.md](epics.md) | Epic 10 stories renumbered (UX Spec → 10.3); Epic 9 + Epic 10 FR/NFR coverage summaries added; FR Coverage Map extended to FR72; NFR list extended to NFR44 |
| [architecture.md](architecture.md) | Story 10.X references updated to new numbering (5 edits) |
| [ux-design-specification.md](ux-design-specification.md) | Story reference updated to 10.3; 5 architecture-alignment bullets added to scope |
| [../../docs/tech-debt.md](../../docs/tech-debt.md) | TD-041 added |

### Remaining open items (still require work)

| Item | Owner | Note |
|---|---|---|
| SM elaboration of Epic 9/10 stubs (Given/When/Then ACs, user-story framing) | SM | 1–2 sprints of work; expect final story count 25–30 after splits |
| Story 9.4 region-availability spike | Dev | Blocks Epic 10 scope-lock |
| Data-residency ADR (conditional on Story 9.4 outcome) | DPO + Legal | Blocks cross-region inference |
| Chat subscription-gate story | PO | Deferred to payments-epic planning (tracked as TD-041) |

### Post-remediation readiness status

**Epics 1–8:** ✅ Ready for implementation (unchanged)
**Epic 9:** ✅ Documentation-ready; stories need SM elaboration before sprint
**Epic 10:** ✅ Documentation-ready; stories need SM elaboration + 9.4 region gate before scope-lock

The planning artifact chain is now internally coherent and complete. PRD ↔ Architecture ↔ Epics ↔ UX ↔ Tech-debt register all reference each other consistently. **All findings from this assessment except the SM-elaboration workload are closed.**



