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

**Bedrock migration of LLM clients**
- **Source:** [sprint-status.yaml](../implementation-artifacts/sprint-status.yaml) lines 78–99, Epic 3 retro Item #7
- **Decision:** Deferred until the chat-with-finances epic. Direct Anthropic/OpenAI works today; GDPR argument alone is weak; AgentCore (which requires Bedrock) is the real driver.
- **Trigger to revisit:** Any conversational/chat-with-finances feature enters planning.
- **Scope when triggered:** swap `ChatAnthropic` / `ChatOpenAI` for `ChatBedrock` in `backend/app/agents/llm.py` (single file); pick a Bedrock-hosted fallback (gpt-4o-mini is not on Bedrock); replace `text-embedding-3-small` with Titan Text Embeddings V2 (1536 → 1024 dims, re-seed RAG, new Alembic migration for pgvector column + HNSW index); add `bedrock:InvokeModel` IAM to Celery ECS task role; verify claude-haiku availability in eu-central-1 (may need cross-region inference profile).

**AWS AgentCore adoption**
- **Source:** [sprint-status.yaml](../implementation-artifacts/sprint-status.yaml) lines 101–118
- **Decision:** Not for Epic 3 batch agents. AgentCore solves stateful, multi-turn session agents; Epic 3 is batch LangGraph via Celery.
- **Trigger to revisit:** A genuinely interactive feature — "chat with your finances", proactive coach, multi-step advisor with cross-session memory.
- **Prerequisites:** Bedrock migration done first; agents rewritten as session handlers; Celery orchestration replaced by event-driven invocations. Adds runtime cost on top of tokens. High refactor — only justified for real interactive agent features.

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

---

## Not tracked here

- **Idea for a separate product — Smart Training Coach:** lives at [brainstorming/parked-idea-smart-training-coach.md](../brainstorming/parked-idea-smart-training-coach.md). Unrelated to kopiika-ai; kept there intentionally.
- **Code-level `TODO` / `FIXME` comments:** not inventoried here. If any matter beyond their immediate file, promote them into this doc explicitly.
