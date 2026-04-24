# Future Ideas & Deferred Items

**Created:** 2026-04-11
**Owner:** Oleh
**Purpose:** Single entry point for "come back to this later" items scattered across the project. This is an index — authoritative details live in the linked documents.

---

## How this file works

- **Sections 1–3** are pointers to existing backlogs. Don't duplicate content there; update it at the source.
- **Section 4** captures items that were only mentioned inline in a story, retro, or YAML comment and had no home.
- When an item is picked up, move it into a sprint/epic or delete it here with a one-line note.

---

## 1. Product roadmap (authoritative: PRD)

See [prd.md](./prd.md) — sections **Growth Features (Post-MVP Fast Follow)**, **Vision (V2/V3)**, **Explicitly Deferred from MVP**, and **Post-MVP Features** (Phase 1.5 / 2 / 3).

High-level shape (do not edit here — edit in PRD):
- **Phase 1.5** — Pattern Detection Agent ✅ Epic 8, Triage Agent ✅ Epic 8, Subscription Detection ✅ Epic 8, Email notifications (→ Phase 2), Feedback Layer 2 ✅ Epic 7 (Stories 7.5/7.6)
- **Phase 2** — Freemium payments, forecasts, chat interface, correction feedback loop, developer feedback dashboard, RAG corpus auto-flagging
- **Phase 3** — Savings/passive-income education, receipt scanning, family mode, gamification, bank API partnerships, EE expansion, mobile native

Additional backlog items kept in [epics.md](./epics.md) → section **Backlog — Post-MVP Enhancement Ideas**:
- Enhanced financial literacy level assessment (onboarding quiz vs. heuristic — relates to FR17)
- Periodic knowledge quizzes for learning reinforcement (mobile push-driven)

---

## 2. Design thinking backlog (authoritative: design-backlog.md)

See [design-backlog.md](./design-backlog.md). All three items are parked for a design-thinking session after MVP:

- **DS-1** — 'Other' category smart handling (threshold + re-categorization pass + user clarification UX)
- **DS-2** — Locale switching → insight regeneration (dual-language vs. lazy vs. next-upload)
- **DS-3** — AI quality control & observability (prompt eval, RAG validation, pipeline metrics, regression detection)

Source: Epic 3 retrospective, 2026-04-07.

---

## 3. Epic 3 retrospective action items (authoritative: epic-3-retro-2026-04-07.md)

See [epic-3-retro-2026-04-07.md](../implementation-artifacts/epic-3-retro-2026-04-07.md) — section **Action Items**.

Status against current sprint:
- Items 1–4 (Critical/High) → addressed by Stories 4.1, 4.2, 4.3, and architecture doc sync. Verify before closing.
- Items 5, 6 → moved to design-backlog (see Section 2).
- Item 7 (Bedrock migration) → see Section 4.

---

## 4. Scattered items with no other home

Items below were mentioned inline in a single story, YAML comment, or review note. They are collected here so they don't get lost.

### 4.1 Infrastructure / platform

**Bedrock migration of LLM clients** ✅ _Promoted to Epic 9 (2026-04-18)_
- **Source:** [sprint-status.yaml](../implementation-artifacts/sprint-status.yaml) lines 78–99, Epic 3 retro Item #7
- **Status:** Promoted to epics.md → Epic 9 (AI Infra Readiness). Scope evolved: `llm.py` becomes multi-provider (Anthropic / OpenAI / Bedrock configurable via `LLM_PROVIDER` env var — not a swap). Embedding migration decoupled and now data-driven via RAG evaluation harness (Story 9.1/9.3). AgentCore + Bedrock regional availability validated by blocking spike (Story 9.4). See PRD "AI-Specific Security" + architecture "Bedrock Migration & AgentCore Architecture" sections.

**AWS AgentCore adoption** ✅ _Promoted to Epic 10 (2026-04-18)_
- **Source:** [sprint-status.yaml](../implementation-artifacts/sprint-status.yaml) lines 101–118
- **Status:** Promoted to epics.md → Epic 10 (Chat-with-Finances + AI Safety). Depends on Epic 9. Read-only agent scope; write-path tools deferred to Phase 2 follow-up for separate safety review. Guardrails + red-team corpus CI gate baked into the epic.

**PostgreSQL Row-Level Security (tenant isolation layer 3)**
- **Source:** [1-5-protected-routes-tenant-isolation.md](../implementation-artifacts/1-5-protected-routes-tenant-isolation.md) line 76
- **Context:** Current defense is Cognito JWT (layer 1) + FastAPI dependency injection (layer 2). RLS was explicitly deferred to a future hardening story per architecture recommendation.
- **Trigger to revisit:** Hardening pass before production launch, or any compliance/audit milestone.

**Server-side enforcement of AI-processing consent**
- **Source:** [5-2-privacy-explanation-consent-during-onboarding.md](../implementation-artifacts/5-2-privacy-explanation-consent-during-onboarding.md) "Questions / Clarifications for PO" Q#1, confirmed by PO 2026-04-11
- **Context:** Story 5.2 implements the onboarding consent UX and persists an append-only `user_consents` record, but the consent gate is **client-side only** (`ConsentGuard` in the frontend). An authenticated user could technically bypass the gate by calling `/api/v1/transactions`, `/api/v1/uploads`, `/api/v1/insights`, etc. directly with a valid Cognito JWT. This is an informed-consent UX gap, not an authentication gap — acceptable for MVP, not acceptable before production/compliance launch.
- **Scope when triggered:** Add a `require_consent(consent_type='ai_processing')` FastAPI dependency that checks for a current-version row in `user_consents` for the authenticated user. Apply to every endpoint that reads/writes financial data (transactions, uploads, insights, profile, health_score, feedback). Return `403 Forbidden` with a machine-readable error code (`CONSENT_REQUIRED`) so the frontend can detect it and redirect to `/onboarding/privacy` even if the client-side guard is bypassed or out of sync.
- **Trigger to revisit:** Compliance hardening pass before production launch. **Implement alongside Story 5.6 (Compliance Audit Trail)** — they share an injection point (cross-cutting dependency on every financial-data endpoint) and should be designed as one middleware layer to avoid double instrumentation.
- **Prerequisite:** Story 5.2 must be done (provides the `user_consents` table and `CURRENT_CONSENT_VERSION` constant this work depends on).

### 4.2 Auth & account

**Forgot-password flow** ✅ _Promoted to Story 1.8 (2026-04-15)_
- **Source:** [1-4-user-login-logout-session-management.md](../implementation-artifacts/1-4-user-login-logout-session-management.md) line 100
- **Status:** Promoted to epics.md → Story 1.8. See FR61.
- **Scope:** Cognito `ForgotPassword` / `ConfirmForgotPassword` wiring + page + tests.

**Privacy explanation copy — legal review before launch**
- **Source:** [5-2-privacy-explanation-consent-during-onboarding.md](../implementation-artifacts/5-2-privacy-explanation-consent-during-onboarding.md) "Questions / Clarifications for PO" Q#4, confirmed by PO 2026-04-11
- **Context:** Story 5.2 ships with **dev-agent-drafted** English + Ukrainian copy for the `/onboarding/privacy` screen (four sections: what data is collected, how AI processes it, where it's stored, who has access). This is explicit placeholder-quality text — sufficient for MVP and internal testing, NOT sufficient for public launch or any jurisdiction with meaningful consent requirements (GDPR, UK DPA, Ukraine's Law on Personal Data Protection).
- **Scope when triggered:** Replace the `onboarding.privacy.*` keys in `frontend/messages/en.json` and `frontend/messages/uk.json` with legally-reviewed copy. Optionally engage Ukrainian-speaking legal counsel for the UK translation (not just a mechanical translation — legal terminology differs). When the new copy lands, **bump `CURRENT_CONSENT_VERSION`** in both `backend/app/core/consent.py` and `frontend/src/features/onboarding/consent-version.ts` — this forces every existing user through the onboarding screen on their next login to re-consent to the updated wording. That's the version system working as designed, not a bug.
- **Trigger to revisit:** Before public launch, OR before any regulated-market rollout, OR when legal counsel is engaged for the launch readiness review — whichever comes first.
- **Prerequisite:** Story 5.2 done (provides the i18n keys, the `CURRENT_CONSENT_VERSION` constant, and the version-bump machinery).

### 4.3 Parsing

**Expand CURRENCY_MAP in Monobank / PrivatBank / Generic parsers** ✅ _Promoted to Story 2.9 (2026-04-15)_
- **Source:** [2-4-additional-bank-format-parser.md](../implementation-artifacts/2-4-additional-bank-format-parser.md) line 75 (`[AI-Review][FUTURE]`)
- **Status:** Promoted to epics.md → Story 2.9. See FR62. Decision: unknown currencies flagged as warnings + stored with raw code, not silently defaulted to UAH.
- **Scope:** Add CHF, JPY, CZK, TRY and other common currencies users are likely to see.

**Exclude cancelled/refunded payments**
- **Context:** There are cases when some transaction were cancelled/refunded afterwards. Currently, we count debit transaction as spending, and a following cancellation - a an income. This is not correct, and will inflate totals. Instead, we need need to spot such transactions and exclude them from any calculations. This must be done in scope a single statement file (easy), and when cancellation appeared in a following uploaded period (not so easy, probably will require a recalculation of previous periods or different, more granular data model).

### 4.4 AI pipeline quality

**Finer-grained literacy level detection via engagement tracking**
- **Source:** [3-8-adaptive-education-depth.md](../implementation-artifacts/3-8-adaptive-education-depth.md) line 100
- **Context:** Current literacy-level heuristic uses upload count + time-since-first-upload as a proxy. The epics originally mentioned "expanded deep-dive layers" as an engagement signal, but no analytics/event table exists.
- **Scope:** Add engagement event tracking (card expand, time on card, thumbs signal) and fold into literacy-level detection for finer resolution.
- **Related:** overlaps with PRD Growth Feature "Enhanced financial literacy level assessment" — pick whichever approach wins.

**AI to parse unknown banking statements**
- **Context** Can we use AI, to find out which bank statement were uploaded and to parse it correctly? What degree of confidence could we achieve? Can it somehow be enhanced from the app side, while using frontier models (can't train/fine-tune them)?

### 4.5 Card / UX content

**Key metric prompt refinement (conciseness)** ✅ _Promoted to Story 3.9 (2026-04-15)_
- **Source:** Epic 3 retro Challenge #7
- **Status:** Promoted to epics.md → Story 3.9. Prompt constraint: key_metric max 60 chars, single numeric figure, no compound expressions.
- **Context:** Some generated key metric values are too dense (e.g., `"₴87,582.04 (25.9% of total) vs. ₴213,238.50 finance allocation"`). Partially addressed by Story 4.2 visual-hierarchy fix, but the *content* density is an Education Agent prompt concern.

**Knowledge card decline mechanism**
- **Context** At the moments, cards stays after each upload. We need add a possibility to mark them as put to archive. This can be done based on uploads: on new upload - move old cards to archive, to focus on a fresh data results. Also, this can be tied to thumbs signals (4.4 AI pipeline quality, mentio0ned above): user press thumb up/down and we move this cards to archive. UX note: it must be clearly visible and intuitive where cards have been moved and how to access the archived card for re-review

**Redirect to cards after upload** ✅ _Promoted to Story 2.8 (2026-04-15)_
- **Status:** Promoted to epics.md → Story 2.8. See FR63. Full SSE progress view before redirect + upload summary card (tx count, bank name, date range, insight count) → user-triggered navigation to Teaching Feed.
- **Context** Still, after upload, I got redirected to cards instantly. I want to see the full flow of agents processing, then - redirrect to cards. Also, I want to see info about upload: number of transactions, discovered bank name etc. Currently this is not visible because of the instant redirrect to cards

**Relative cards (should work on naming:))**
- **Context** On a new upload, we can check with a previous sugestion
* When we see repeated pattern we can highlight it, like: 
  * Restaraunt spending takes large part of food budget on first upload
  * We see the same issue on a 2nd (3rd and so on) - we mention, not just the fact, but that this is repeatable occurence
  * Sometimes it might be false positive and user thinks that this is ok. Then, we might tied this to thumbs signals (4.4 AI pipeline quality, mentio0ned above): thumb down, means user doesn't find it useful or a problem for him - do not highlight
* Same can be done for an improvement, like:
  * Restaraunt spending takes large part of food budget on first upload
  * On a 2nd and 3rd uploads - issue is gone, we should highlight the improvemnt, whis is the result of our advice and steps towards it by the user
* In general, this will allow to convert plain cards with information into cards showing trends and provide user with a valuable feedback

### 4.6 AI Security

**Statement files AI processing**
- **Context** Indirect injection in statement files. Valid?

### 4.7 Chat capabilities (post-Epic 10)

**Chart generation in chat — three-option ladder**
- **Source:** 2026-04-24 conversation with Architect agent, during the Story 10.4a Phase A re-spec (see [ADR-0004](../../docs/adr/0004-chat-runtime-phasing.md)).
- **Context:** A natural chat feature for a personal-finance assistant is "show me my eating-out spend over the last 6 months as a chart" — i.e. Claude composes a query against the user's transactions and returns a chart. Three implementation options, ordered by effort + risk:
  1. **Vega-Lite / chart-spec tool (recommended first cut).** Declare a `render_chart(spec, title, explanation)` tool in Story 10.4c (or a 10.12 follow-up); Claude composes Vega-Lite JSON; the frontend renders with react-vega. Data comes from a separate scoped SQL tool (`query_user_transactions`). Zero server execution. Covers ~90% of finance chart needs (bar/line/area/scatter/pie/heatmap/stacked/small-multiples/rolling averages). Works on Phase A and Phase B identically. Small effort — one frontend lib + two tool definitions.
  2. **Anthropic hosted `code_execution` tool.** First-party Claude Python sandbox (returns stdout + images). Not available on Bedrock Converse at 2026-04 — prod-runtime blocker. Only a local-dev / `LLM_PROVIDER=anthropic` fallback path today. Re-evaluate when Bedrock ships parity.
  3. **Self-hosted code interpreter.** We run a Python sandbox ourselves; Claude emits code against a prepared pandas DataFrame of the user's transactions. Expressive ("correlate weekend vs. weekday eating-out spend and show regression residuals") but non-trivial infrastructure: the blast radius is set by the host (App Runner / container / Lambda), not by the user count, so a sandbox escape reaches the DB + Secrets Manager either way. Needs: outbound network deny, read-only FS + tmpfs, CPU/memory/wall-clock caps, no IAM credentials on the code path, output-size caps. Best implemented as a tool **inside the AgentCore Runtime container** (Phase B-native) — the container gives the isolation boundary for free, turning this from "build a sandbox" into "add a tool to an already-isolated container."
- **Sequencing recommendation:** Ship Option 1 when Story 10.4c lands (or in a 10.12 follow-up). Watch how users actually phrase chart requests for 30+ real prompts. Only after Phase B ships (AgentCore Runtime container — see TD-094) should we re-evaluate Option 3; the infrastructure cost drops by an order of magnitude at that point. Option 2 is a "check back when Bedrock catches up" item, not a planned path.
- **Trigger to revisit:** After Option 1 ships and Epic 10 enters steady-state usage; OR when Bedrock Converse adds first-party code-execution parity with Anthropic's direct API; OR when Phase B (AgentCore Runtime) ships.

**Chat-driven category corrections (propose-only writes)**
- **Source:** 2026-04-24 conversation with Architect agent, Epic 10 scope review. Related: architecture.md §Chat Agent Component "read-only allowlist" posture; threat-model row "Tool abuse (write, admin, network, filesystem)".
- **Context:** Flagged-for-review transactions are the highest-intent correction surface in the product — the user is already in fix-it mode. Letting them correct conversationally ("change the coffee one to food, and the three grocery runs to groceries") is materially better than clicking each Teaching Feed card. But moving chat out of the read-only boundary looks scary until you notice the write can be staged.
- **Architecture — propose-only, not write:** Chat gets one new tool in the 10.4c manifest:
  - `propose_category_change(transaction_id, new_category, reason)` — **backend implementation does not touch the DB.** Returns a structured proposal payload.
  - Frontend renders an inline confirm card: "Recategorize X from A → B? [Confirm] [Cancel]".
  - User's `[Confirm]` click triggers the actual mutation via the **existing** categorization-correction endpoint (same one Teaching Feed cards use — reuses its authorization, validation, audit trail). Chat introduces zero new DB write paths.
  - Result: prompt-injection worst case is a spurious proposal card the user declines, not a state change. Cross-user mutation is blocked by the existing endpoint's per-row authorization. Audit trail gains `chat_session_id` + `chat_turn_id` columns for traceability.
- **Three-tier scope expansion (each its own decision):**
  1. **Tier 1 (recommended first slice):** propose-only, scoped to transactions in `flagged_for_review` status, `category` field only, closed category enum. Narrowest possible surface.
  2. **Tier 2:** propose-only on **any** transaction's category. Broader but same mechanism. Requires re-reviewing the injection corpus against a larger blast surface.
  3. **Tier 3:** structural edits — splits, merges, deletes, bulk operations. Each is a separate decision with its own safety review. Not implied by tiers 1–2.
- **Safety harness additions (Story 10.8b-level):** indirect injection in transaction descriptions attempting to fabricate proposals for non-flagged transactions; assert backend filter rejects. Injection attempting to propose category values outside the enum; assert validation rejects. Injection attempting to cite another user's transaction_id; assert per-row authorization rejects.
- **Architecture doc update when implemented:** §Chat Agent Component "read-only allowlist" becomes "read-only + propose-only (user-confirmed writes)" with pointer to the implementing story. Not an ADR-level decision — the propose-only pattern is mechanically small.
- **Sequencing recommendation:** Ship as a post-Epic-10 follow-up story (provisionally 10.13 — "Chat-driven category corrections for flagged-for-review transactions"). Wait until 10.4c's tool manifest is stable and 10.8b's red-team corpus has an established baseline, so the new tool lands with existing guardrails rather than co-developing them. Phase A / Phase B split is irrelevant — this is tool-manifest + UI work, identical on both runtimes.
- **Trigger to revisit:** After Epic 10 ships read-only chat AND 30 days of prod usage shows genuine pull for conversational corrections (thumbs-down patterns on flagged-review card UI, explicit user requests). Skip if read-only chat proves sufficient.

---

## Not tracked here

- **Idea for a separate product — Smart Training Coach:** lives at [brainstorming/parked-idea-smart-training-coach.md](../brainstorming/parked-idea-smart-training-coach.md). Unrelated to kopiika-ai; kept there intentionally.
- **Code-level `TODO` / `FIXME` comments:** not inventoried here. If any matter beyond their immediate file, promote them into this doc explicitly.
