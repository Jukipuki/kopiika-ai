---
stepsCompleted:
  - step-01-validate-prerequisites
  - step-02-design-epics
  - step-03-create-stories
  - step-04-final-validation
  - phase-1.5-epics-and-stories
status: complete
completedAt: '2026-04-05'
lastExtended: '2026-04-15'
inputDocuments:
  - prd.md
  - architecture.md
  - ux-design-specification.md
  - design-thinking-2026-04-05.md
---

# kopiika-ai - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for kopiika-ai, decomposing the requirements from the PRD, UX Design, and Architecture into implementable stories.

## Requirements Inventory

### Functional Requirements

FR1: Users can upload bank statement files (CSV, PDF) via drag-and-drop or file picker
FR2: System can auto-detect the bank format of an uploaded statement (Monobank, PrivatBank, other)
FR3: System can parse Monobank CSV files including handling Windows-1251 encoding, semicolon delimiters, and embedded newlines
FR4: System can parse additional bank CSV formats where column structure is recognizable
FR5: System can validate uploaded files before processing (file type, size, format structure) and return actionable error messages
FR6: System can partially process statements where some transactions are unrecognizable, providing value from what it can parse
FR7: Users can upload multiple statements (covering different time periods) to build cumulative history
FR8: System can extract and structure raw transactions from parsed bank statements (Ingestion Agent)
FR9: System can classify transactions into spending categories using AI and MCC codes (Categorization Agent)
FR10: System can generate personalized financial education content based on categorized transaction data using RAG over a financial literacy knowledge base (Education Agent)
FR11: System can generate education content in the user's selected language (Ukrainian or English)
FR12: System can process a typical monthly statement (200-500 transactions) through the full pipeline asynchronously
FR13: Users can view real-time progress of pipeline processing via SSE streaming
FR14: Users can view a card-based Teaching Feed displaying AI-generated financial insights
FR15: Each insight card displays a headline fact with progressive disclosure education layers (headline > "why this matters" > deep-dive)
FR16: Users can expand and collapse education layers on each insight card
FR17: System can adapt education content depth based on the user's detected financial literacy level
FR18: Users can view insights from current and previous uploads in a unified feed
FR19: Teaching Feed supports cursor-based pagination for browsing insights
FR20: System can build and maintain a persistent financial profile from all uploaded statements
FR21: System can calculate and display a Financial Health Score (0-100) based on cumulative data
FR22: Users can view how their Financial Health Score changes over time across uploads
FR23: System can detect and display month-over-month spending changes when multiple periods are available
FR24: System can display spending breakdowns by category from cumulative data
FR25: Users can create an account with email and password
FR26: Users can log in and log out securely
FR27: System can protect all application routes, requiring authentication
FR28: Users can only access their own financial data (tenant isolation)
FR29: Users can select their preferred language (Ukrainian or English)
FR30: Users can view and manage their account settings
FR31: Users can delete all their data with a single action (account, transactions, embeddings, profile, Financial Health Score)
FR32: System can display a clear data privacy explanation during onboarding
FR33: System can obtain explicit user consent for AI processing of financial data at signup
FR34: System can encrypt all stored financial data at rest
FR35: Users can view what data the system has stored about them
FR36: System can display a financial advice disclaimer ("insights and education, not financial advice")
FR37: System can detect unrecognized file formats and suggest corrective actions to the user
FR38: System can flag uncategorized transactions and display them separately for user awareness
FR39: System can recover gracefully from pipeline processing failures without data loss
FR40: System can display user-friendly error messages (not technical errors) for all failure scenarios
FR41: System can produce structured logs with correlation IDs (job_id, user_id) across all pipeline agents
FR42: System can track and log pipeline processing times per agent
FR43: System can track and log upload success/failure rates and error types
FR44: Operator can query job status and pipeline health via database queries
FR45: System can track implicit card interaction signals per Teaching Feed card: time_on_card_ms, education_expanded, education_depth_reached, swipe_direction, card_position_in_feed
FR46: System can aggregate implicit signals into a per-card engagement score (0-100) using a weighted formula
FR47: Users can rate any Teaching Feed card with thumbs up or thumbs down; vote state persists and is visible when returning to the card
FR48: Users can report an issue on any Teaching Feed card via an in-context mechanism (flag icon in card overflow menu) with category selection (Bug, Incorrect info, Confusing, Other) and optional free-text field
FR49: Feedback data (votes, reports, free-text) is included in the user's data export (FR35) and one-click deletion (FR31)
FR50: On thumbs-down, system presents a compact slide-up panel with 4 preset reason chips: "Not relevant to me", "Already knew this", "Seems incorrect", "Hard to understand" — dismissible, one-tap selection
FR51: On thumbs-up, system presents an optional follow-up (triggered 1 in 10 occurrences) with preset chips: "Learned something", "Actionable", "Well explained"
FR52: System can display milestone feedback cards at the end of the Teaching Feed: after 3rd upload (one-time), after significant Financial Health Score change (+/- 5 points)
FR53: Milestone feedback cards use the same card component and gestures as education cards — swipeable, skippable, no new UI pattern
FR54: System can enforce feedback card frequency caps: max 1 feedback card per session, max 1 per month, milestone cards never repeat once dismissed
FR55: System can auto-flag RAG topic clusters with >30% thumbs-down rate when a minimum of 10 votes has been reached on the cluster

### Phase 1.5 Requirements (Pipeline Completion)

FR56: System can detect recurring charges from transaction history and identify subscription services based on billing cadence (monthly ± 3 days, annual ± 7 days) and amount consistency (within 5% tolerance)
FR57: System can identify month-over-month spending trends and anomalies per category (% delta and UAH delta) when two or more months of data are available
FR58: System can score each insight or pattern finding by financial severity (critical / warning / info) based on UAH impact relative to the user's monthly income
FR59: Teaching Feed displays insight cards sorted by triage severity (critical first, then warning, then info); each card carries a severity badge with colour, icon, and text label
FR60: System can generate subscription alert cards showing service name, monthly cost, billing frequency, and inactivity status
FR61: Users can reset their password via a forgot-password email flow (Cognito ForgotPassword / ConfirmForgotPassword)
FR62: Statement parsers support expanded currency codes (CHF, JPY, CZK, TRY) with unknown currencies flagged as warnings rather than silently defaulted to UAH
FR63: After pipeline completion, system returns an upload summary payload (detected bank name, transaction count, date range, total insights) displayed to the user before they navigate to the Teaching Feed

### NonFunctional Requirements

NFR1: Page load (authenticated) < 3 seconds on 3G mobile networks
NFR2: Teaching Feed card render < 500ms after data fetch
NFR3: Financial Health Score calculation < 2 seconds
NFR4: Full pipeline processing (3 agents) < 60 seconds for 200-500 transactions (async with SSE progress)
NFR5: API response < 500ms for read operations
NFR6: File upload acknowledgment < 2 seconds (HTTP 202 returned)
NFR7: Support 100 concurrent users at MVP
NFR8: JWT access tokens < 15 minutes expiry, with refresh token rotation
NFR9: Session timeout after 30 minutes of inactivity
NFR10: Rate limiting — max 10 login attempts per IP per 15 minutes; max 20 file uploads per user per hour
NFR11: All uploaded file content treated as untrusted; sanitized before AI pipeline processing
NFR12: Automated vulnerability scanning for Python and Node.js dependencies
NFR13: Support 500 registered users at MVP, scalable to 10,000
NFR14: Support 5 concurrent uploads being processed at MVP, scalable to 50
NFR15: Support up to 10,000 transactions stored per user (~2 years)
NFR16: RAG knowledge base supports 50-100 documents at MVP, scalable to 500+
NFR17: Support 10x user growth with < 20% performance degradation by adding horizontal resources
NFR18: WCAG 2.1 AA compliance baseline for all UI components
NFR19: Keyboard navigable — all interactive elements reachable and operable via keyboard
NFR20: Screen reader compatible — semantic HTML, ARIA labels for severity indicators and progressive disclosure
NFR21: Color independence — severity conveyed through icons and text labels, not color alone
NFR22: Minimum color contrast 4.5:1 for normal text, 3:1 for large text
NFR23: Visible focus indicators on all interactive elements
NFR24: Support browser zoom up to 200% without horizontal scrolling
NFR25: 99.5% availability for core functionality (upload, Teaching Feed, authentication)
NFR26: Zero data loss for uploaded financial data — PostgreSQL WAL + regular backups
NFR27: Failed pipeline jobs can be retried without re-upload; checkpoint state preserved per agent
NFR28: Graceful degradation — if Education Agent (RAG) fails, display categorized data without education layers
NFR29: Daily automated database backups with 30-day retention
NFR30: LLM API calls retry with exponential backoff; circuit breaker after 3 consecutive failures
NFR31: Monobank CSV parsing graceful degradation on format changes; partial parsing supported

### Phase 2 NFRs (Epic 9 + Epic 10)

NFR32: `llm.py` remains multi-provider (Anthropic / OpenAI / Bedrock); switching providers MUST require only an `LLM_PROVIDER` env var change, no code change (Epic 9)
NFR33: RAG evaluation harness runs in CI with baseline metrics stored as a reference; any future embedding / retrieval change is measured against baseline before merge (Epic 9)
NFR34: 100% of chat turns pass through AWS Bedrock Guardrails (input + output); bypass is a P0 regression (Epic 10)
NFR35: Red-team corpus pass rate ≥ 95% before any chat / agent / prompt change merges to main; CI gate blocks merge on regression (Epic 10)
NFR36: Red-team corpus covers OWASP LLM Top-10 (prompt injection, data leakage, unauthorized tool use) + Ukrainian-language adversarial prompts + known jailbreak patterns; reviewed and expanded quarterly (Epic 10)
NFR37: Zero cross-user PII leakage in chat responses (measured by red-team probes + output-filter audits) (Epic 10)
NFR38: Grounding rate ≥ 90% for data-specific claims, measured by LLM-as-judge sampled evaluation in the RAG harness (Epic 10)
NFR39: Principled refusals MUST NOT leak filter rationale or internal state; verified by corpus review (Epic 10)
NFR40: Bedrock `InvokeModel` calls retry with exponential backoff; Guardrails outage degrades to refusal, never unfiltered output (Epic 9/10)
NFR41: AgentCore sessions are per-user-per-session isolated; session deletion cascades with account deletion (FR31 / FR70); runtime cost monitored via CloudWatch cost-allocation tags (Epic 10)
NFR42: Embedding-model selection is data-driven — migration only if a candidate clearly beats the current baseline on Ukrainian + English retrieval quality in the RAG harness (Epic 9)
NFR43: Chat rate limits — max 60 messages per user per hour; max 10 concurrent sessions per user; per-user daily token cap enforced in `llm.py` and chat rate-limit envelope (Epic 10)
NFR44: Safety observability — CloudWatch metrics for Guardrails block rate, grounding-block rate, refusal rate, per-user token spend, chat latency, and `CanaryLeaked` count; alarms per thresholds in architecture § Observability & Alarms (Epic 10)

### Additional Requirements

**From Architecture — Starter Template & Project Scaffolding:**
- Folder-based monorepo: `frontend/` (Next.js 16.1 via create-next-app) + `backend/` (custom FastAPI scaffold)
- Frontend initialized with: TypeScript, Tailwind CSS 4.x, ESLint, App Router, Turbopack
- Backend initialized with: Python 3.12, FastAPI, Uvicorn, SQLModel, Alembic, Celery, Redis, LangGraph, pgvector, uv package manager
- Shared OpenAPI-generated TypeScript client (@hey-api/openapi-ts) for frontend-backend type safety

**From Architecture — Infrastructure & Deployment:**
- Frontend hosted on Vercel (optimized for Next.js)
- Backend API on AWS App Runner (auto-scaling, scales to zero)
- Celery workers on AWS ECS Fargate (persistent containers for AI pipeline)
- Amazon RDS PostgreSQL with pgvector extension
- Amazon ElastiCache (Redis) for Celery broker and caching
- Amazon S3 for uploaded file storage (per-user prefixed keys, server-side encryption)
- Amazon Cognito for user authentication (JWT issuance)
- Amazon SES for email notifications
- GitHub Actions for CI/CD
- AWS Secrets Manager for API keys and credentials
- docker-compose.yml for local dev (PostgreSQL + Redis)
- Three environments: dev / staging / production

**From Architecture — Implementation Patterns:**
- Database naming: snake_case tables (plural), snake_case columns, UUID v4 primary keys
- API naming: camelCase JSON via Pydantic alias_generator=to_camel
- Frontend naming: PascalCase.tsx components, camelCase variables
- Backend naming: snake_case.py modules, snake_case variables
- Money stored as integers (kopiykas), dates as ISO 8601 UTC
- Structured JSON logging with correlation IDs (job_id, user_id)
- Error response format: `{"error": {"code": "...", "message": "...", "details": {...}}}`
- Custom exception handlers in FastAPI — never expose stack traces in production
- LangGraph pipeline: each agent node with try/except, partial results preserved via checkpointing
- Celery tasks: max_retries=3 with exponential backoff, dead letter queue for permanent failures
- Frontend: TanStack Query for all API data fetching, error boundaries per feature
- Validation layers: React Hook Form + Zod (client), Pydantic v2 (server), SQLModel + DB constraints (database)
- ESLint + Prettier (frontend), Ruff + Black (backend) enforced in CI

**From Architecture — Implementation Sequence:**
1. Project scaffolding (monorepo, create-next-app, FastAPI init)
2. AWS infrastructure provisioning (RDS, ElastiCache, Cognito, S3)
3. Authentication flow (Cognito + NextAuth.js + FastAPI middleware)
4. Database models + migrations (SQLModel + Alembic)
5. File upload + async processing (S3 + Celery + Redis)
6. AI pipeline (LangGraph agents, sequential)
7. RAG system (pgvector + BGE-M3 embeddings)
8. Teaching Feed UI (shadcn/ui cards + TanStack Query + SSE)
9. Freemium tier gating
10. Payment integration (Fondy + LemonSqueezy)

**From Architecture — Cross-Component Dependencies:**
- Auth (Cognito) must be in place before any API endpoint works
- Database schema must be stable before AI pipeline can persist results
- Redis must be running before Celery workers or caching works
- OpenAPI spec must be generated before frontend API client can be built
- BGE-M3 embeddings service must be running before Education Agent can do RAG retrieval

**From Architecture — Database Migration:**
- Alembic migrations run as a pre-deployment step in CI/CD pipeline
- `alembic upgrade head` executed before new API version starts
- Never auto-migrate in app startup

**From UX Design — Interaction & Animation Requirements:**
- Card stack as primary navigation pattern (swipe gestures on mobile, arrow keys/click on desktop)
- Progressive card appearance with fade/slide animation as AI agents complete processing
- Framer Motion for card stack gestures (swipe physics, spring animations) and micro-interactions
- Health Score ring: Apple Fitness-inspired circular SVG/Canvas with animated transitions
- All animations must respect `prefers-reduced-motion` media query
- Health Score ring animation can be disabled — displays as static number
- Persistent "+" upload button (FAB) — always accessible for upload
- Mobile-informed responsive design (touch-optimized, thumb-reachable, portrait-oriented)

**From UX Design — Visual Design Requirements:**
- shadcn/ui component library (Radix UI primitives, copied into project)
- Tailwind CSS 4.x with dark mode support (dark: prefix)
- Triage severity color coding: red/yellow/green with icon and text fallback
- Base font size 16px, line heights 1.5+ for body text
- Color contrast: WCAG AA compliance for all text-on-background combinations

**From UX Design — Tone & Personality:**
- Lighthearted, warm error states ("Our AI tripped over your spreadsheet")
- Friendly loading messages ("Crunching your numbers...")
- Financial advice disclaimer integrated into onboarding flow
- Curiosity-provoking insight headlines with progressive disclosure

**From Architecture — Compliance Audit Trail:**
- Financial data access events must be logged with user ID, timestamp, action type, and resource accessed
- Distinct from operational logging (Story 6.4) — serves GDPR accountability and potential regulatory audit requirements
- Implemented via middleware-level logging (`core/audit.py`) on all data access endpoints (transactions, insights, profile, feedback)
- Stored in structured audit log format

**From Architecture — Feedback System Integration:**
- Feedback data model: `card_feedback` table (votes + issue reports), `feedback_responses` table (milestone responses), `card_interactions` extensions (implicit signals)
- Feedback API endpoints: POST/PATCH/GET on `/api/v1/feedback/cards/{cardId}/*`, POST `/api/v1/feedback/milestone`
- Frontend components: `CardFeedbackBar.tsx`, `FollowUpPanel.tsx`, `ReportIssueForm.tsx`, `MilestoneFeedbackCard.tsx`
- Feedback data included in cascading delete and data export flows (FR49)

### FR Coverage Map

| FR | Epic | Description |
|---|---|---|
| FR1 | Epic 2 | Upload bank statements via drag-and-drop or file picker |
| FR2 | Epic 2 | Auto-detect bank format |
| FR3 | Epic 2 | Parse Monobank CSV (Windows-1251, semicolons, embedded newlines) |
| FR4 | Epic 2 | Parse additional bank CSV formats |
| FR5 | Epic 2 | Validate uploaded files and return actionable errors |
| FR6 | Epic 2 | Partially process unrecognizable transactions |
| FR7 | Epic 2 | Upload multiple statements for cumulative history |
| FR8 | Epic 2 | Extract and structure transactions (Ingestion Agent) |
| FR9 | Epic 3 | Classify transactions into categories (Categorization Agent) |
| FR10 | Epic 3 | Generate education content via RAG (Education Agent) |
| FR11 | Epic 3 | Generate education in Ukrainian or English |
| FR12 | Epic 2 | Process 200-500 transactions asynchronously |
| FR13 | Epic 2 | Real-time pipeline progress via SSE |
| FR14 | Epic 3 | Card-based Teaching Feed |
| FR15 | Epic 3 | Progressive disclosure education layers |
| FR16 | Epic 3 | Expand/collapse education layers |
| FR17 | Epic 3 | Adapt education depth to literacy level |
| FR18 | Epic 3 | Unified feed across uploads |
| FR19 | Epic 3 | Cursor-based pagination |
| FR20 | Epic 4 | Persistent financial profile |
| FR21 | Epic 4 | Financial Health Score (0-100) |
| FR22 | Epic 4 | Health Score changes over time |
| FR23 | Epic 4 | Month-over-month spending changes |
| FR24 | Epic 4 | Spending breakdowns by category |
| FR25 | Epic 1 | Create account with email/password |
| FR26 | Epic 1 | Log in and log out |
| FR27 | Epic 1 | Protected application routes |
| FR28 | Epic 1 | Tenant isolation |
| FR29 | Epic 1 | Language selection (Ukrainian/English) |
| FR30 | Epic 1 | Account settings |
| FR31 | Epic 5 | Delete all data with single action |
| FR32 | Epic 5 | Privacy explanation during onboarding |
| FR33 | Epic 5 | Consent for AI processing |
| FR34 | Epic 5 | Encrypt financial data at rest |
| FR35 | Epic 5 | View stored data |
| FR36 | Epic 5 | Financial advice disclaimer |
| FR37 | Epic 6 | Detect unrecognized formats with suggestions |
| FR38 | Epic 6 | Flag uncategorized transactions |
| FR39 | Epic 6 | Recover from pipeline failures |
| FR40 | Epic 6 | User-friendly error messages |
| FR41 | Epic 6 | Structured logs with correlation IDs |
| FR42 | Epic 6 | Pipeline processing time tracking |
| FR43 | Epic 6 | Upload success/failure rate tracking |
| FR44 | Epic 6 | Operator job/health queries |
| FR45 | Epic 7 | Track implicit card interaction signals (time, expansion, depth, velocity) |
| FR46 | Epic 7 | Aggregate implicit signals into per-card engagement score |
| FR47 | Epic 7 | Thumbs up/down on Teaching Feed cards |
| FR48 | Epic 7 | Report-an-issue via flag icon in card overflow menu |
| FR49 | Epic 7 | Feedback data in data export and one-click deletion |
| FR50 | Epic 7 | Thumbs-down follow-up panel with reason chips |
| FR51 | Epic 7 | Occasional thumbs-up follow-up (1 in 10) |
| FR52 | Epic 7 | Milestone feedback cards at end of feed |
| FR53 | Epic 7 | Milestone cards use same card component/gestures |
| FR54 | Epic 7 | Feedback card frequency caps |
| FR55 | Epic 7 | Auto-flag RAG topic clusters with high thumbs-down rate |
| FR56 | Epic 8 | Detect recurring charges and classify subscription services |
| FR57 | Epic 8 | Identify month-over-month spending trends and anomalies |
| FR58 | Epic 8 | Score insights by financial severity (critical/warning/info) |
| FR59 | Epic 8 | Teaching Feed sorted by triage severity with severity badges |
| FR60 | Epic 8 | Generate subscription alert cards with cost and inactivity status |
| FR61 | Epic 1 | Forgot-password flow via Cognito email reset |
| FR62 | Epic 2 | Expanded CURRENCY_MAP (CHF, JPY, CZK, TRY) with unknown-currency flagging |
| FR63 | Epic 2 | Upload summary payload (bank, tx count, date range) shown before Teaching Feed redirect |
| FR64 | Epic 10 | Conversational chat interface grounded in the user's own financial data (UA + EN) |
| FR65 | Epic 10 | Chat responses stream token-by-token via SSE |
| FR66 | Epic 10 | View / resume / delete chat history across sessions; no cross-session context carry-over (TD-040) |
| FR67 | Epic 10 | Grounded responses (no speculative claims; ungrounded claims refused, not regenerated) |
| FR68 | Epic 10 | Citations back to underlying transactions / profile / RAG corpus for data-specific claims |
| FR69 | Epic 10 | Principled refusal — neutral message, no filter-rationale leakage |
| FR70 | Epic 10 | Chat-history deletion; cascades with account deletion (FR31) |
| FR71 | Epic 10 | Separate `chat_processing` consent (distinct from `ai_processing`); chat blocked until granted |
| FR72 | Epic 10 | Chat ships ungated; subscription gate deferred to payments-epic follow-up (TD-041) |
| FR73 | Epic 11 | Classify every transaction on a `transaction_kind` axis (spending/income/savings/transfer) alongside category (ADR-0001) |
| FR74 | Epic 11 | Expanded category taxonomy (`savings`, `transfers_p2p`) with kind-category compatibility enforced at persistence |
| FR75 | Epic 11 | Low-confidence transaction review queue with resolve/dismiss actions and categorization overrides |
| FR76 | Epic 11 | Partial-import on parse with per-row rejection reasons and mojibake flagging surfaced in upload UX |
| FR77 | Epic 11 | AI-assisted schema detection for unknown bank formats with fingerprint cache and operator-editable registry (ADR-0002) |

## Epic List

### Epic 1: Project Foundation & User Authentication
Users can register, log in, reset their password, manage their account settings, select language, and securely access the application. This is the foundational epic — everything else builds on it. Includes project scaffolding, infrastructure setup, and the complete auth flow.
**FRs covered:** FR25, FR26, FR27, FR28, FR29, FR30, FR61

### Epic 2: Statement Upload & Data Ingestion
Users can upload bank statements and have them validated, parsed, and structured — with real-time progress feedback and an upload summary before entering the Teaching Feed.
**FRs covered:** FR1, FR2, FR3, FR4, FR5, FR6, FR7, FR8, FR12, FR13, FR62, FR63

### Epic 3: AI-Powered Financial Insights & Teaching Feed
Users can view a card-based Teaching Feed with AI-generated, education-first financial insights. This epic builds the categorization agent, education agent (RAG), and the full Teaching Feed UI with progressive disclosure and progressive card appearance.
**FRs covered:** FR9, FR10, FR11, FR14, FR15, FR16, FR17, FR18, FR19

### Epic 4: Cumulative Financial Profile & Health Score
Users can build a persistent financial profile across multiple uploads, see a Financial Health Score, track changes over time, and view spending breakdowns and trends.
**FRs covered:** FR20, FR21, FR22, FR23, FR24

### Epic 5: Data Privacy, Trust & Consent
Users can understand how their data is used, consent to AI processing, view stored data, delete all their data, and see appropriate disclaimers — building the trust foundation for a financial product. Includes compliance audit trail middleware for GDPR accountability.
**FRs covered:** FR31, FR32, FR33, FR34, FR35, FR36

### Epic 6: Error Handling, Recovery & Operational Monitoring
The system handles errors gracefully with user-friendly messages, recovers from pipeline failures, flags uncategorized transactions, and provides operational observability for the team.
**FRs covered:** FR37, FR38, FR39, FR40, FR41, FR42, FR43, FR44

### Epic 7: User Feedback System
Users can provide feedback on Teaching Feed content through implicit behavioral signals, explicit thumbs up/down, issue reporting, and milestone-triggered feedback cards — enabling continuous improvement of RAG education quality without interrupting the user experience. Phased: Layers 0-1 (MVP), Layer 2 (Phase 1.5), Layer 3 (Phase 2).
**FRs covered:** FR45, FR46, FR47, FR48, FR49, FR50, FR51, FR52, FR53, FR54, FR55
**Dependencies:** Epic 3 (Teaching Feed cards), Epic 4 (Health Score for FR52), Epic 5 (data export/deletion for FR49)

### Epic 8: Pattern Detection, Triage & Subscription Detection
The 5-agent pipeline is complete. Users see insights ranked by financial severity (red/yellow/green), active subscriptions are surfaced with inactivity alerts, and month-over-month spending trends and anomalies are detected automatically.
**FRs covered:** FR56, FR57, FR58, FR59, FR60
**Dependencies:** Epic 2 (Ingestion Agent output), Epic 3 (Education Agent, Teaching Feed cards, insight severity field)

### Epic 9: AI Infra Readiness (Bedrock Provider, RAG Eval Harness, Embedding Decision)
Prepares the AI layer for Phase 2 conversational features: multi-provider `llm.py` (Bedrock + existing Anthropic/OpenAI), RAG evaluation harness as regression gate, embedding-model decision spike, AgentCore + Bedrock region validation, IAM/observability plumbing. No user-facing FRs — infrastructure prerequisite for Epic 10.
**FRs covered:** None (infra epic)
**NFRs covered:** NFR32, NFR33, NFR40, NFR42 (see NFR list below)
**Dependencies:** Epic 8
**Blocks:** Epic 10

### Epic 10: Chat-with-Finances (AgentCore + AI Safety)
Users can converse with an AI agent grounded in their own financial data, with defense-in-depth AI safety: Bedrock Guardrails, prompt-injection/jailbreak defenses, tool-use scoping, and a red-team safety test suite as a CI gate.
**FRs covered:** FR64, FR65, FR66, FR67, FR68, FR69, FR70, FR71, FR72
**NFRs covered:** NFR34, NFR35, NFR36, NFR37, NFR38, NFR39, NFR41 (see NFR list below)
**Dependencies:** Epic 9 (especially 9.4 region gate, 9.5 multi-provider llm.py, 9.7 IAM)

### Epic 11: Ingestion & Categorization Hardening
Structural fixes to the parsing and categorization pipeline identified in the April 2026 incident analysis: `transaction_kind` as a first-class field (enabling Savings Ratio and eliminating abs()-on-income bug class), expanded categories (`savings`, `transfers_p2p`), enriched LLM prompt (description + signed amount + MCC + direction), golden-set accuracy gate, AI-assisted schema detection for unknown bank formats, post-parse validation layer, encoding detection, and a low-confidence review queue.
**FRs covered:** FR73, FR74, FR75, FR76, FR77
**ADRs:** ADR-0001 (transaction kind first-class), ADR-0002 (AI-assisted schema detection)
**Tech spec:** `tech-spec-ingestion-categorization.md`
**Dependencies:** Epic 2 (ingestion pipeline), Epic 3 (categorization agent)
**Cross-epic consumer:** Story 4.9 (Savings Ratio wiring) in Epic 4

### Epic 12: Testing & Quality Harnesses
Cross-cutting quality harnesses for aspects of product quality not owned by a single feature epic. Starting scope focuses on *insight-output* quality (surfaced by Epic 11 UAT — see Story 11.11), phased as: **tier 1** deterministic golden-fixture assertions (Story 12.1), **tier 2** LLM-as-judge scoring on qualitative axes (Story 12.2), **tier 3** human-label calibration of the judge (Story 12.3). Phase 2 of this epic — scheduled after Epics 9 and 10 land — will revisit scope to cover gaps those epics expose (likely candidates: end-to-end pipeline regression, cross-agent composition tests, adversarial fixture expansion).
**Scope boundary — this epic does NOT own:** categorization golden-set (owned by Epic 11 Story 11.1), RAG retrieval eval (owned by Epic 9 Story 9.3), chat jailbreak red-team corpus (owned by Epic 10), per-agent unit tests (owned by each feature epic). Epic 12 fills gaps and owns cross-cutting harnesses only.
**FRs covered:** none directly — this is a quality-assurance epic. Implicitly strengthens FR10, FR14, FR59 (insight-quality guarantees) and NFR Reliability (regression prevention via CI gates).
**Dependencies:** Story 11.11 (provides the flagship regression fixture for Story 12.1). Phase 2 revisit depends on completion of Epics 9 and 10.

## Epic 1: Project Foundation & User Authentication

Users can register, log in, reset their password, manage their account settings, select language, and securely access the application. This is the foundational epic — everything else builds on it. Includes project scaffolding, infrastructure setup, and the complete auth flow.

### Story 1.1: Monorepo Scaffolding & Local Development Environment

As a **developer**,
I want a monorepo with Next.js frontend and FastAPI backend scaffolded with local dev infrastructure,
So that I have a working development environment to build features on.

**Acceptance Criteria:**

**Given** a fresh clone of the repository
**When** I run `docker-compose up -d` and start both frontend and backend
**Then** PostgreSQL (with pgvector) and Redis are running locally, the Next.js dev server serves on port 3000, and the FastAPI server serves on port 8000

**Given** the frontend project
**When** I inspect the configuration
**Then** it uses TypeScript, Tailwind CSS 4.x, ESLint, App Router, and Turbopack as specified in Architecture

**Given** the backend project
**When** I inspect the configuration
**Then** it uses Python 3.12, FastAPI, Uvicorn, SQLModel, Alembic, Celery, Redis, and uv as package manager

**Given** both projects running
**When** the frontend calls the backend health endpoint
**Then** a successful JSON response is returned confirming cross-service communication works

### Story 1.2: AWS Infrastructure Provisioning

As a **developer**,
I want all AWS infrastructure provisioned and configured,
So that the application has the cloud services it needs to run beyond local development.

**Acceptance Criteria:**

**Given** the AWS account is available
**When** infrastructure is provisioned
**Then** the following services are created and configured: Amazon RDS PostgreSQL 16 with pgvector extension (encryption at rest enabled), Amazon ElastiCache Redis 7, Amazon Cognito user pool with email/password authentication, Amazon S3 bucket with server-side encryption and per-user key prefixes, Amazon SES for transactional email, and AWS Secrets Manager for API keys and credentials

**Given** the provisioned infrastructure
**When** environment configuration is set up
**Then** three environments are configured (dev / staging / production) with separate AWS resources per environment, and `.env.example` files document all required environment variables for both frontend and backend

**Given** the CI/CD pipeline
**When** GitHub Actions workflows are created
**Then** there are workflows for: frontend lint + test + build, backend lint + test, frontend deploy to Vercel, and backend deploy to AWS (App Runner + ECS Fargate)

**Given** the backend connects to AWS services
**When** it starts in a deployed environment
**Then** it can reach RDS, ElastiCache, Cognito, S3, and SES using credentials from Secrets Manager

### Story 1.3: AWS Cognito Integration & User Registration

As a **user**,
I want to create an account with my email and password,
So that I can securely access the application.

**Acceptance Criteria:**

**Given** I am on the registration page
**When** I enter a valid email and a password meeting complexity requirements
**Then** an account is created in AWS Cognito and I receive a verification email

**Given** I have received a verification email
**When** I click the verification link or enter the code
**Then** my account is verified and I can proceed to log in

**Given** I enter an email that is already registered
**When** I attempt to register
**Then** I see a user-friendly error message indicating the email is in use

**Given** I enter a weak password
**When** I attempt to register
**Then** I see validation feedback about password requirements before submission (React Hook Form + Zod)

### Story 1.4: User Login, Logout & Session Management

As a **user**,
I want to log in and log out securely with proper session management,
So that my financial data is protected.

**Acceptance Criteria:**

**Given** I have a verified account
**When** I enter correct email and password
**Then** I am authenticated via Cognito, receive JWT tokens (access < 15 min, refresh with rotation), and am redirected to the main app

**Given** I am logged in
**When** I click logout
**Then** my session is terminated, tokens are invalidated, and I am redirected to the login page

**Given** I am logged in and inactive for 30 minutes
**When** the session timeout triggers
**Then** I am automatically logged out and prompted to re-authenticate

**Given** an IP address has attempted 10 failed logins in 15 minutes
**When** another login attempt is made from that IP
**Then** the attempt is rate-limited and a retry-after message is shown

### Story 1.5: Protected Routes & Tenant Isolation

As a **user**,
I want all application routes protected and my data isolated from other users,
So that only I can access my financial information.

**Acceptance Criteria:**

**Given** I am not authenticated
**When** I try to access any protected route (frontend or API)
**Then** I am redirected to the login page (frontend) or receive a 401 response (API)

**Given** I am authenticated as User A
**When** I make API requests
**Then** all database queries are automatically scoped to my user_id via dependency injection

**Given** I am authenticated as User A
**When** I attempt to access User B's data via direct API manipulation
**Then** I receive a 403 Forbidden response and the attempt is logged

**Given** the backend creates the initial database schema
**When** Alembic migration runs
**Then** the users table is created with UUID v4 primary keys and all required fields (email, cognito_sub, preferred_language, created_at, updated_at)

### Story 1.6: Language Selection (Ukrainian & English)

As a **user**,
I want to select my preferred language (Ukrainian or English),
So that I can use the application in my native language.

**Acceptance Criteria:**

**Given** I am on the registration or settings page
**When** I select Ukrainian or English as my preferred language
**Then** my preference is saved to my user profile

**Given** I have a language preference set
**When** I navigate the application
**Then** all UI text is displayed in my selected language using next-intl

**Given** I change my language preference in settings
**When** I save the change
**Then** the UI immediately switches to the new language without page reload

**Given** a new user has not set a language preference
**When** they first load the application
**Then** the language defaults to Ukrainian (primary market)

### Story 1.7: Account Settings Page

As a **user**,
I want to view and manage my account settings,
So that I can control my profile and preferences.

**Acceptance Criteria:**

**Given** I am authenticated
**When** I navigate to the settings page
**Then** I see my email, preferred language, and account creation date

**Given** I am on the settings page
**When** I change my language preference and save
**Then** the change is persisted to the backend and reflected in the UI

**Given** I am on the settings page
**When** I view it on mobile (< 768px width)
**Then** the layout is responsive, touch-optimized, and all controls are thumb-reachable

**Given** the settings page is rendered
**When** I inspect the UI
**Then** all components use shadcn/ui primitives with proper WCAG 2.1 AA compliance (contrast, focus indicators, keyboard navigation)

### Story 1.8: Forgot-Password Flow

As a **user**,
I want to reset my password via email when I've forgotten it,
So that I can regain access to my account without contacting support.

**Acceptance Criteria:**

**Given** I am on the login page
**When** I click the "Forgot password?" link
**Then** I am taken to `/forgot-password` which has an email input field; the link is already wired in the login page markup (the missing page referenced in Story 1.4)

**Given** I am on the `/forgot-password` page and enter my registered email
**When** I submit the form
**Then** Cognito `InitiateForgotPassword` is called, a password reset email with a verification code is sent, and I see a confirmation message: "Check your email for a reset code"

**Given** I enter an email that is not registered
**When** I submit the forgot-password form
**Then** I see the same confirmation message (no email enumeration — the response never reveals whether the address exists)

**Given** I have received the reset email with a verification code
**When** I visit `/forgot-password/confirm`, enter the verification code, and provide a new password meeting Cognito complexity requirements
**Then** Cognito `ConfirmForgotPassword` is called, my password is updated, and I am redirected to `/login` with a success banner "Password updated — please log in"

**Given** I submit the confirmation form with an expired or invalid reset code
**When** Cognito returns an error
**Then** I see a user-friendly message: "Reset code is invalid or has expired. Please request a new one." with a link back to `/forgot-password`

**Given** the `/forgot-password` and `/forgot-password/confirm` pages
**When** rendered on mobile
**Then** all inputs and buttons are touch-optimized and thumb-reachable with visible focus indicators (WCAG 2.1 AA)

## Epic 2: Statement Upload & Data Ingestion

Users can upload bank statements and have them validated, parsed, and structured — with real-time progress feedback and an upload summary before entering the Teaching Feed.

### Story 2.1: File Upload UI & S3 Storage

As a **user**,
I want to upload bank statement files via drag-and-drop or file picker,
So that I can get my financial data into the system.

**Acceptance Criteria:**

**Given** I am authenticated and on the main app screen
**When** I tap the persistent "+" floating action button
**Then** a file picker opens allowing me to select CSV or PDF files from my device

**Given** I am on a desktop browser
**When** I drag a CSV or PDF file onto the upload zone
**Then** the file is accepted via drag-and-drop with visual feedback

**Given** I select a valid file
**When** the upload begins
**Then** the file is sent to the backend API, stored in S3 with a per-user prefixed key, and I receive acknowledgment within 2 seconds (HTTP 202 + jobId)

**Given** the upload API endpoint
**When** a user has already uploaded 20 files in the last hour
**Then** the request is rate-limited and a friendly message explains the limit

**Given** the backend receives an upload
**When** it creates the processing job record
**Then** the `uploads` and `processing_jobs` tables are created via Alembic migration with proper foreign keys to the users table

### Story 2.2: File Validation & Format Detection

As a **user**,
I want the system to validate my uploaded files and auto-detect the bank format,
So that I get immediate feedback if something is wrong.

**Acceptance Criteria:**

**Given** I upload a file
**When** the backend receives it
**Then** it validates MIME type (CSV or PDF), file size (within limits), and basic format structure before queuing for processing

**Given** I upload an unsupported file type (e.g., .xlsx, .jpg)
**When** validation runs
**Then** I see a user-friendly error message: specific to the issue (wrong format, too large, etc.) with suggested corrective actions

**Given** I upload a CSV file
**When** the system analyzes the header row and structure
**Then** it auto-detects the bank format (Monobank, PrivatBank, or unknown) without requiring manual bank selection

**Given** all uploaded file content
**When** it enters the system
**Then** it is treated as untrusted and sanitized before any further processing

### Story 2.3: Monobank CSV Parser

As a **user**,
I want the system to correctly parse my Monobank CSV bank statements,
So that all my transactions are accurately extracted.

**Acceptance Criteria:**

**Given** a Monobank CSV file with Windows-1251 encoding
**When** the parser processes it
**Then** the encoding is correctly detected and handled, producing valid UTF-8 transaction data

**Given** a Monobank CSV with semicolon delimiters and embedded newlines in description fields
**When** the parser processes it
**Then** all fields are correctly split respecting quoted fields with embedded newlines

**Given** a Monobank CSV with 200-500 transactions
**When** the parser extracts transaction data
**Then** each transaction has: date, description, MCC code, amount (stored as integer kopiykas), and balance — stored in a `transactions` table created via Alembic migration

**Given** a CSV where some rows have unexpected or missing fields
**When** the parser encounters them
**Then** it processes all recognizable rows and flags unrecognizable ones, providing partial results rather than failing entirely

### Story 2.4: Additional Bank Format Parser

As a **user**,
I want the system to parse CSV files from other Ukrainian banks,
So that I'm not limited to only Monobank.

**Acceptance Criteria:**

**Given** a CSV file detected as non-Monobank
**When** the parser analyzes the column structure
**Then** it attempts to recognize common patterns (date, amount, description columns) and extract transactions

**Given** a CSV with a recognizable but different column layout (e.g., PrivatBank)
**When** the parser processes it
**Then** transactions are extracted and normalized to the same internal format as Monobank transactions

**Given** a CSV file with a completely unrecognizable format
**When** parsing fails
**Then** the user sees a friendly error suggesting the file format is not yet supported, with instructions on supported formats

### Story 2.5: Async Pipeline Processing with Celery

As a **user**,
I want my uploaded statements processed asynchronously,
So that I don't have to wait on a loading screen.

**Acceptance Criteria:**

**Given** a file has been uploaded and validated
**When** the processing job is queued
**Then** a Celery task is created and dispatched to a worker via Redis broker

**Given** the Celery worker picks up a task
**When** it runs the Ingestion Agent (LangGraph node)
**Then** raw parsed transactions are extracted, structured, and persisted to PostgreSQL

**Given** a processing job for 200-500 transactions
**When** the full ingestion pipeline runs
**Then** it completes within 60 seconds

**Given** a Celery task fails due to a transient error
**When** the retry mechanism activates
**Then** it retries up to 3 times with exponential backoff before marking as failed, preserving any partial results via checkpointing

### Story 2.6: Real-Time Processing Progress via SSE

As a **user**,
I want to see real-time progress of my statement processing,
So that I know the system is working and how long to wait.

**Acceptance Criteria:**

**Given** I have uploaded a file and received a jobId
**When** I stay on the app screen
**Then** the frontend opens an SSE connection to `GET /api/v1/jobs/{id}/stream`

**Given** the pipeline is processing
**When** each pipeline step completes
**Then** the Celery worker updates Redis with progress, and an SSE event is pushed to the frontend with step name and percentage

**Given** the pipeline completes successfully
**When** the `job-complete` SSE event fires
**Then** the frontend receives `{"jobId": "uuid", "status": "completed", "totalInsights": N}` and transitions to showing results

**Given** the pipeline fails
**When** the `job-failed` SSE event fires
**Then** the frontend shows a user-friendly error message (not technical details) with a retry option

**Given** the SSE connection drops
**When** the frontend reconnects
**Then** it receives the current state and resumes progress display without duplicate events

### Story 2.7: Multiple Statement Uploads & Cumulative History

As a **user**,
I want to upload multiple statements from different time periods,
So that I can build a richer picture of my finances over time.

**Acceptance Criteria:**

**Given** I have already uploaded one statement
**When** I upload another statement covering a different time period
**Then** the new transactions are added to my account without overwriting previous data

**Given** I upload a statement with overlapping date ranges
**When** the system processes it
**Then** duplicate transactions are detected (by date + amount + description) and not re-inserted

**Given** I have uploaded multiple statements
**When** I view my data
**Then** all transactions from all uploads are available in a unified dataset linked to my user account

### Story 2.8: Upload Completion UX & Summary

As a **user**,
I want to see the full pipeline processing progress and an upload summary before being taken to the Teaching Feed,
So that I know what was processed and feel confident in the results before viewing insights.

**Acceptance Criteria:**

**Given** I have uploaded a statement file and received a `jobId`
**When** the frontend opens the SSE stream
**Then** I see a pipeline progress view (not the Teaching Feed) showing each agent step completing in sequence — the frontend does NOT automatically redirect to the Teaching Feed on upload

**Given** the pipeline is running and SSE `pipeline-progress` events arrive
**When** each agent step completes
**Then** the progress view shows step name, a human-readable message (from Story 4.1 `message` field), and a visual progress indicator; steps shown include Ingestion, Categorization, Pattern Detection (Phase 1.5 placeholder: skipped gracefully if not yet active), Triage, Education

**Given** the pipeline completes and a `job-complete` SSE event is received
**When** the completion payload is processed
**Then** the frontend displays an upload summary card showing: detected bank name (`bankName`), total transactions parsed (`transactionCount`), statement date range (`dateRange`), and total insight cards generated (`totalInsights`), with a "View Insights" call-to-action button

**Given** the `job-complete` SSE payload
**When** it is returned from the backend
**Then** it includes the fields: `bankName` (string, bank detected by format parser), `transactionCount` (integer), `dateRange` (object with ISO date `start` and `end`), `totalInsights` (integer) — the backend populates these from the completed pipeline state

**Given** the user reads the upload summary
**When** they click "View Insights"
**Then** they are navigated to the Teaching Feed (`/cards` or equivalent route)

**Given** the pipeline fails before completion
**When** the `job-failed` SSE event fires
**Then** the progress view shows a user-friendly error message with a retry option (existing behaviour from Story 2.6) — the summary card is not shown

### Story 2.9: Expand CURRENCY_MAP

As a **developer**,
I want all bank statement parsers to support a wider range of currencies,
So that users with multi-currency accounts don't silently lose or miscategorize transaction data.

**Acceptance Criteria:**

**Given** a Monobank CSV containing transactions in CHF, JPY, CZK, or TRY
**When** the Monobank parser processes it
**Then** the currency is correctly identified, stored with the transaction record using the ISO 4217 currency code, and displayed with the correct symbol

**Given** a PrivatBank or generic bank CSV with CHF, JPY, CZK, or TRY transactions
**When** the respective parser processes it
**Then** the currency is correctly identified and stored (not defaulted to UAH)

**Given** a transaction in a currency not present in the updated CURRENCY_MAP
**When** the parser encounters it
**Then** the transaction is stored with the raw currency code preserved, flagged with a `currency_unknown` warning log, and included in the uncategorized transaction report (FR38) — it is never silently converted to UAH

**Given** the updated CURRENCY_MAP
**When** it is reviewed
**Then** it includes at minimum: UAH, USD, EUR, GBP, PLN, CHF, JPY, CZK, TRY — each mapped to its ISO 4217 code and display symbol

**Given** existing stored transactions that previously used the "default to UAH" fallback
**When** this change is deployed
**Then** no existing transaction records are modified — the new behaviour applies only to future uploads

## Epic 3: AI-Powered Financial Insights & Teaching Feed

Users can view a card-based Teaching Feed with AI-generated, education-first financial insights. This epic builds the categorization agent, education agent (RAG), and the full Teaching Feed UI with progressive disclosure and progressive card appearance.

### Story 3.1: Transaction Categorization Agent

As a **user**,
I want my transactions automatically categorized into spending categories,
So that I can understand where my money goes.

**Acceptance Criteria:**

**Given** the Ingestion Agent has extracted structured transactions
**When** the Categorization Agent (LangGraph node) processes them
**Then** each transaction is classified into a spending category using MCC codes and LLM-based analysis

**Given** a transaction with a clear MCC code (e.g., 5411 = Grocery Stores)
**When** categorization runs
**Then** the MCC code is used as the primary signal, with LLM refining the category based on description context

**Given** a transaction with no MCC code or an ambiguous one
**When** the LLM categorizes it
**Then** a category is assigned with a confidence score, and low-confidence categorizations are flagged

**Given** a batch of 200-500 transactions
**When** the Categorization Agent completes
**Then** categorized transactions are persisted to PostgreSQL with category, confidence score, and the pipeline state is checkpointed

**Given** the LLM API call fails
**When** the retry mechanism activates
**Then** it retries with exponential backoff (2s, 4s, 8s), falls back to secondary LLM if primary fails, and logs token usage for cost tracking

### Story 3.2: RAG Financial Literacy Corpus Creation

As a **user**,
I want the system to have a curated financial education knowledge base,
So that the AI can teach me about personal finance using quality, relevant content.

**Acceptance Criteria:**

**Given** the RAG system needs source material
**When** the corpus is prepared
**Then** 20-30 core financial literacy documents are created covering key personal finance concepts: budgeting, savings, debt management, subscription tracking, spending categories, emergency funds, investment basics, and Ukrainian-specific financial topics (hryvnia, Monobank ecosystem, Ukrainian tax basics)

**Given** the target audience includes Ukrainian users
**When** the corpus documents are written
**Then** each document exists in both Ukrainian and English versions, using natural language appropriate for the target literacy levels (beginner to intermediate)

**Given** the corpus documents
**When** they are structured
**Then** each document has: a clear topic title, key concepts section, practical examples with realistic Ukrainian financial scenarios (amounts in UAH), and actionable takeaways

**Given** the corpus is complete
**When** it is reviewed
**Then** content is factually accurate, avoids financial advice (education only), and is stored in a structured format ready for embedding (markdown files in a designated `backend/data/rag-corpus/` directory)

### Story 3.3: RAG Knowledge Base & Education Agent

As a **user**,
I want to receive personalized financial education based on my spending data,
So that I learn about my finances, not just see numbers.

**Acceptance Criteria:**

**Given** the RAG knowledge base
**When** it is initialized
**Then** 20-30 core financial literacy concepts are embedded using BGE-M3 multilingual embeddings and stored in pgvector (creating the `embeddings` table via Alembic migration)

**Given** categorized transaction data for a user
**When** the Education Agent (LangGraph node) runs
**Then** it retrieves relevant financial education content via RAG and generates personalized insight cards combining the user's data with educational context

**Given** a user with language preference set to Ukrainian
**When** the Education Agent generates content
**Then** the content is generated in Ukrainian using bilingual LLM prompts

**Given** a user with language preference set to English
**When** the Education Agent generates content
**Then** the content is generated in English

**Given** the RAG retrieval or Education Agent fails
**When** graceful degradation activates
**Then** the system displays categorized data without education layers rather than showing nothing (NFR28)

### Story 3.4: Teaching Feed API & Data Model

As a **user**,
I want a backend API that serves my financial insights,
So that the frontend can display them efficiently.

**Acceptance Criteria:**

**Given** the Education Agent has generated insight cards
**When** they are stored
**Then** an `insights` table is created via Alembic migration with fields: id (UUID), user_id (FK), headline, key_metric, why_it_matters, deep_dive, severity (triage level), category, created_at

**Given** I request my Teaching Feed
**When** I call `GET /api/v1/insights`
**Then** I receive insight cards sorted by triage severity (highest impact first), with cursor-based pagination

**Given** I have insights from multiple uploads
**When** I request the Teaching Feed
**Then** all insights across uploads are available in a unified feed

**Given** the API response
**When** it serializes insight data
**Then** JSON fields use camelCase (via Pydantic alias_generator), amounts are in kopiykas (integers), and dates are ISO 8601 UTC

### Story 3.5: Teaching Feed Card UI & Progressive Disclosure

As a **user**,
I want to view financial insights as cards with expandable education layers,
So that I can quickly scan headlines and dive deeper when interested.

**Acceptance Criteria:**

**Given** I am on the Teaching Feed screen
**When** insights are loaded
**Then** I see a card-based feed with each card showing: triage severity indicator (color + icon + text), headline fact, and key metric

**Given** I view an insight card
**When** I tap/click to expand it
**Then** the "why this matters" layer is revealed with a smooth animation

**Given** I have expanded the first layer
**When** I tap/click to expand further
**Then** the "deep-dive" education layer is revealed with progressive disclosure

**Given** I have expanded layers
**When** I tap/click to collapse
**Then** layers collapse smoothly back to the headline view

**Given** the Teaching Feed is rendered
**When** I inspect the UI
**Then** cards use shadcn/ui Card primitives, severity colors have icon+text fallback (not color alone), and all elements meet WCAG 2.1 AA compliance

**Given** the feed data is fetched
**When** TanStack Query manages the request
**Then** loading states show skeleton cards (shadcn/ui Skeleton) and errors are caught by the feature error boundary

### Story 3.6: Card Stack Navigation & Gestures

As a **user**,
I want to navigate insights using swipe gestures on mobile and keyboard/click on desktop,
So that browsing feels natural and responsive on any device.

**Acceptance Criteria:**

**Given** I am on mobile viewing the Teaching Feed
**When** I swipe left or right
**Then** I navigate between insight cards with physical-feeling spring animations (Framer Motion)

**Given** I am on desktop viewing the Teaching Feed
**When** I press arrow keys or click navigation controls
**Then** I navigate between cards with smooth transitions

**Given** the card stack
**When** animations play
**Then** they respect the `prefers-reduced-motion` media query — reduced motion users see instant transitions

**Given** the Teaching Feed on mobile
**When** I interact with cards
**Then** all touch targets are thumb-reachable and the layout is optimized for portrait orientation

### Story 3.7: Progressive Card Appearance & SSE Integration

As a **user**,
I want to see insight cards appear progressively as the AI pipeline processes my data,
So that I experience an engaging, real-time reveal rather than a static loading screen.

**Acceptance Criteria:**

**Given** I have just uploaded a statement
**When** the pipeline is processing
**Then** cards fade/slide in one by one as each AI agent completes its work (basic categorization insights appear first, then deeper education cards)

**Given** the SSE stream is active
**When** new insights are generated by the pipeline
**Then** the frontend receives them via SSE events and appends new cards to the feed with animation

**Given** progressive loading is happening
**When** the UI displays the feed
**Then** a subtle animation indicates more cards may be coming ("AI is still thinking...")

**Given** loading messages are displayed
**When** the user reads them
**Then** they see lighthearted copy ("Crunching your numbers...", "Finding patterns in your spending...")

### Story 3.8: Adaptive Education Depth

As a **user**,
I want the education content adapted to my financial literacy level,
So that I get content that's challenging but not overwhelming.

**Acceptance Criteria:**

**Given** a new user with no prior uploads
**When** the Education Agent generates content
**Then** it defaults to beginner-level explanations with more foundational concepts

**Given** a user who has uploaded multiple statements over time
**When** the Education Agent detects engagement patterns (expanded deep-dive layers, multiple uploads)
**Then** it adjusts content depth to intermediate level with more nuanced insights

**Given** the user's detected literacy level
**When** insight cards are generated
**Then** the headline, "why this matters", and deep-dive layers each reflect the appropriate depth

**Given** the cursor-based pagination
**When** I scroll through the Teaching Feed
**Then** additional pages of insights load seamlessly without full page refresh

### Story 3.9: Key Metric Prompt Refinement

As a **user**,
I want insight card key metrics to be concise and immediately readable,
So that I can grasp the key number at a glance without parsing a dense compound string.

**Acceptance Criteria:**

**Given** the Education Agent LLM prompt for insight generation
**When** it is updated
**Then** it contains an explicit constraint on the `key_metric` field: "key_metric must be a single, human-readable value — a formatted number with currency/unit and at most one short comparator. Maximum 60 characters. Do not combine multiple numeric figures or percentages and absolutes in the same value."

**Given** the Education Agent generates an insight card
**When** it produces the `key_metric` field
**Then** the value is a single, readable figure such as "₴1,200/month", "34% more than last month", or "+2,100 UAH vs. October" — not a compound expression like "₴87,582.04 (25.9% of total) vs. ₴213,238.50 finance allocation"

**Given** a sample of 10 newly generated insight cards (from test data or staging)
**When** evaluated against the constraint
**Then** ≥ 90% of `key_metric` values are ≤ 60 characters and contain no more than one numeric figure

**Given** existing insight cards already stored in the database
**When** this change is deployed
**Then** existing cards are not retroactively regenerated — the refinement applies only to insights generated from future uploads

**Given** the updated prompts are applied
**When** a Ukrainian-language user uploads a statement
**Then** Ukrainian-language `key_metric` values are equally concise (the constraint applies to both languages)

## Epic 4: Cumulative Financial Profile & Health Score

Users can build a persistent financial profile across multiple uploads, see a Financial Health Score, track changes over time, and view spending breakdowns and trends.

### Story 4.1: SSE Progress Message Decoupling

As a **developer**,
I want the backend to own human-readable progress messages sent via SSE pipeline-progress events,
So that adding new pipeline steps requires zero frontend changes.

**Source:** Epic 3 Retrospective — Critical Action Item #1

**Acceptance Criteria:**

**Given** the backend sends a `pipeline-progress` SSE event
**When** any pipeline step emits progress
**Then** the event payload includes a `message` field with a human-readable string (e.g., "Categorizing your transactions...", "Generating financial insights...")

**Given** the frontend `ProgressiveLoadingState` component receives a `pipeline-progress` event
**When** it renders the progress state
**Then** it displays `data.message` directly instead of mapping `data.step` to hardcoded copy strings

**Given** a new pipeline step is added in a future epic
**When** it emits `pipeline-progress` events with a `message` field
**Then** the frontend displays the message without any code changes to `ProgressiveLoadingState.tsx`

**Given** the SSE progress events
**When** they include both `message` and `step` fields
**Then** the `step` field is retained for programmatic use (progress bar percentage, analytics) while `message` is used for display

### Story 4.2: Card Visual Hierarchy Fix

As a **user**,
I want the Teaching Feed card headline to be visually dominant over the key metric,
So that I understand the context before seeing the number.

**Source:** Epic 3 Retrospective — High Action Item #2

**Acceptance Criteria:**

**Given** an insight card with both a headline and a key metric
**When** the card renders in `InsightCard.tsx`
**Then** the headline is styled as the primary element (larger font, bold) and the key metric is styled as supporting (smaller, secondary color)

**Given** the Education Agent generates a key metric
**When** the metric value is produced
**Then** it is concise (under 30 characters) — no compound expressions like "₴87,582.04 (25.9% of total) vs. ₴213,238.50 finance allocation"

**Given** the updated card styling
**When** viewed on mobile and desktop
**Then** the visual hierarchy is consistent and meets WCAG 2.1 AA contrast requirements

### Story 4.3: Redirect Timing & Progressive Loading State Verification

As a **developer**,
I want to verify that the redirect to Teaching Feed and `ProgressiveLoadingState` activation work correctly,
So that users see accurate progress when the pipeline is running.

**Source:** Epic 3 Retrospective — High Action Item #3

**Acceptance Criteria:**

**Given** a user triggers the pipeline (uploads a statement)
**When** they are redirected to the Teaching Feed
**Then** `ProgressiveLoadingState` activates and shows progress messages from the SSE stream

**Given** the `isStreaming` flag in `useFeedSSE`
**When** traced through `FeedContainer`
**Then** the flag correctly reflects whether an SSE stream is active (true while pipeline runs, false when complete)

**Given** the pipeline completes
**When** `ProgressiveLoadingState` receives the completion event
**Then** it transitions smoothly to the card display without a flash or jarring state change

**Given** the investigation reveals a bug in the redirect timing or streaming state
**When** the bug is identified
**Then** a fix is implemented and verified with tests

### Story 4.4: Persistent Financial Profile

As a **user**,
I want the system to build and maintain a financial profile from all my uploaded statements,
So that I have a comprehensive view of my financial situation.

**Acceptance Criteria:**

**Given** a user has uploaded one or more statements
**When** the pipeline completes processing
**Then** a financial profile is created or updated, aggregating data across all uploads (creating a `financial_profiles` table via Alembic migration with user_id FK, total_income, total_expenses, category_totals JSON, period_start, period_end, updated_at)

**Given** a user uploads a new statement
**When** the new transactions are processed
**Then** the financial profile is recalculated to include the new data without losing previous aggregations

**Given** the financial profile API endpoint `GET /api/v1/profile`
**When** an authenticated user requests their profile
**Then** they receive aggregated financial data scoped to their user_id with camelCase JSON serialization

### Story 4.5: Financial Health Score Calculation & Display

As a **user**,
I want to see a Financial Health Score (0-100) based on my cumulative data,
So that I have a quick indicator of my overall financial wellness.

**Acceptance Criteria:**

**Given** a user has a financial profile with sufficient data
**When** the Health Score is calculated
**Then** a score from 0-100 is computed based on spending patterns, savings ratio, and category distribution, completing within 2 seconds (NFR3)

**Given** the Health Score is calculated
**When** the user views their profile page
**Then** the score is displayed as an Apple Fitness-inspired circular ring (SVG/Canvas) with animated gradient transitions between score zones

**Given** a user with `prefers-reduced-motion` enabled
**When** the Health Score ring renders
**Then** the animation is disabled and the score displays as a static number with the ring at its final position

**Given** the Health Score is stored
**When** it is persisted
**Then** a `financial_health_scores` table is created via Alembic migration with id (UUID), user_id (FK), score (integer), calculated_at, and snapshot data

### Story 4.6: Health Score History & Trends

As a **user**,
I want to see how my Financial Health Score changes over time,
So that I can track my financial progress.

**Acceptance Criteria:**

**Given** a user has multiple Health Score records (from multiple uploads over time)
**When** they view the Health Score section
**Then** a trend visualization shows score history with dates

**Given** the trend data
**When** it is displayed
**Then** the visualization is responsive on mobile and desktop, using accessible colors with text/icon fallbacks

**Given** a user with only one upload
**When** they view Health Score history
**Then** they see their current score with a message encouraging more uploads to see trends ("Upload more months to track your progress")

### Story 4.7: Month-over-Month Spending Comparison

As a **user**,
I want to see how my spending changes month over month,
So that I can identify improving or worsening trends.

**Acceptance Criteria:**

**Given** a user has uploaded statements covering at least two different months
**When** the system compares the periods
**Then** month-over-month changes are calculated and displayed per category (e.g., "Groceries: +12% vs last month")

**Given** month-over-month data is available
**When** it is displayed on the profile page
**Then** increases are shown with up-arrow indicators and decreases with down-arrow indicators, using color + icon + text (not color alone)

**Given** a user has data for only one month
**When** they view the comparison section
**Then** they see a friendly message ("Upload another month to see spending trends") instead of empty charts

### Story 4.8: Category Spending Breakdown

As a **user**,
I want to see my spending broken down by category from all my cumulative data,
So that I understand my spending distribution.

**Acceptance Criteria:**

**Given** a user has categorized transactions from one or more uploads
**When** they view the spending breakdown section
**Then** they see a visual breakdown of spending by category (e.g., bar chart or donut chart) with amounts in the user's local currency format

**Given** the category breakdown
**When** it is displayed
**Then** categories are sorted by amount (highest first), amounts are displayed in hryvnias (converted from kopiykas), and the visualization meets WCAG 2.1 AA standards

**Given** the spending breakdown on mobile
**When** the user views it
**Then** the layout is responsive, touch-friendly, and legible in portrait orientation

**Given** the profile page components
**When** data is fetching
**Then** TanStack Query manages all requests with proper loading skeletons and error boundaries

### Story 4.9: Savings Ratio wired to `transaction_kind`

As a **user**,
I want my Financial Health Score's Savings Ratio component to reflect what I actually save each month,
So that the score becomes a trustworthy signal of my financial health rather than a constant zero.

**Context:** The Savings Ratio component currently renders `0/100` for every user because the categorization pipeline has no reliable way to distinguish capital retention (savings) from consumption (spending). Epic 11 introduces `transaction_kind` as a first-class field (ADR-0001). This story is the downstream wiring — the Savings Ratio calculator reads `transaction_kind` directly instead of inferring it from category heuristics.

**Depends on:** Story 11.2 (schema migration) and Story 11.3 (enriched prompt emits `transaction_kind`)

**Acceptance Criteria:**

**Given** a user has categorized transactions for a period with at least one `transaction_kind = savings` entry and at least one `transaction_kind = income` entry
**When** the Savings Ratio is computed for that period
**Then** the ratio equals `sum(abs(amount) where kind='savings') / sum(abs(amount) where kind='income')`, clamped to `[0.0, 1.0]`, and rendered as a 0–100 integer in the Health Score panel

**Given** a user has no `transaction_kind = income` entries in the period
**When** the Savings Ratio is computed
**Then** the Savings Ratio sub-score is `null` and the UI displays "Not enough data yet" rather than `0/100`

**Given** a user has `transaction_kind = income` entries but no `transaction_kind = savings` entries
**When** the Savings Ratio is computed
**Then** the sub-score is `0/100` and the UI indicates this is a real zero (not a "no data" state)

**Given** Epic 11 Story 11.2 has landed and transactions have `transaction_kind` populated
**When** the Savings Ratio calculator runs
**Then** it reads `transaction_kind` directly from transactions; it does NOT infer kind from category labels, amount signs, or MCC

**Given** a Health Score integration test fixture containing a deposit top-up and a salary inflow
**When** the Health Score is computed
**Then** Savings Ratio reports a non-zero value that matches the expected `savings/income` ratio to within 1% (tolerance accounts for rounding)

**Given** a user who was onboarded before Epic 11 and has no categorized historical data with `transaction_kind`
**When** they view the Health Score
**Then** the Savings Ratio sub-score displays "Not enough data yet" — greenfield assumption applies (no backfill scope in this story)

---

### Story 4.10: Profile aggregates respect `transaction_kind` (diversity / regularity / coverage fix)

As a **user**,
I want my Category Diversity, Expense Regularity, and Income Coverage sub-scores to ignore savings and transfer transactions,
So that a single deposit top-up or between-account transfer doesn't wreck the rest of my Health Score.

**Context:** Story 4.9 wired Savings Ratio to read `transaction_kind` inside `_compute_breakdown`, but the underlying `FinancialProfile` aggregates that the other three components read — `total_income`, `total_expenses`, `category_totals` — still partition by amount sign in [backend/app/services/profile_service.py:210-218](backend/app/services/profile_service.py#L210-L218). This means a `kind='savings'` outflow (e.g. a −50 000 deposit top-up) is counted as a giant single-category expense, which (1) collapses Category Diversity to a single-category floor, (2) inflates the variance that drives Expense Regularity downward, and (3) inflates `avg_monthly_expense` while simultaneously deflating `net_savings = total_income + total_expenses`, crushing Income Coverage toward 0. Same applies to `kind='transfer'` rows. Surfaced in Story 4.9 post-review testing (2026-04-22).

**Depends on:** Story 4.9 (Savings Ratio — landed), Story 11.2 (`transaction_kind` field — landed)

**Acceptance Criteria:**

**Given** a user has transactions with `transaction_kind` in `('savings', 'transfer')` in the profile's period
**When** `build_or_update_profile` computes `total_expenses` and `category_totals`
**Then** those transactions are excluded from both aggregates — `total_expenses` reflects only `kind='spending'` outflows, and `category_totals` contains only `kind='spending'` rows.

**Given** a user has transactions with `transaction_kind='income'` that happen to have a negative amount (data correction edge case)
**When** `build_or_update_profile` computes `total_income`
**Then** `total_income` is the sum of `abs(amount)` over `kind='income'` rows — it reads kind, not sign, matching Story 4.9's contract for Savings Ratio.

**Given** a user has one `kind='spending'` transaction per category (e.g. groceries, transport, utilities) and one large `kind='savings'` transaction
**When** the Health Score is computed
**Then** Category Diversity is computed over the spending categories only, Expense Regularity variance is computed over the spending-category totals only, and Income Coverage's `avg_monthly_expense` uses only the spending outflows — the savings transaction influences Savings Ratio (Story 4.9) and nothing else.

**Given** a user whose `total_income` (kind-based) exceeds their total `kind='spending'` outflows
**When** Income Coverage is computed
**Then** `net_savings = total_income − total_spending_abs` is positive and `months_covered = net_savings / avg_monthly_spending` yields a non-zero score, regardless of whether the user also has `kind='savings'` or `kind='transfer'` transactions in the period.

**Given** a legacy user whose transactions all default to `kind='spending'` (pre-Epic-11)
**When** `build_or_update_profile` runs
**Then** behavior is identical to today — the aggregates match the old sign-based partition because every row is `kind='spending'`. No migration or backfill required (greenfield assumption applies, matching Story 4.9 AC #6).

**Given** the existing `get_category_breakdown` endpoint ([profile_service.py:31-70](backend/app/services/profile_service.py#L31-L70)) reads `category_totals` from the profile
**When** that endpoint runs after this story lands
**Then** the returned breakdown contains only `kind='spending'` categories — savings/transfer rows no longer appear as spending categories in the UI (this is the intended user-visible side effect; any test that asserted on savings-kind amounts appearing in category breakdown must be updated).

**Given** a user has the same underlying transactions before and after this change, with `transaction_kind` correctly populated
**When** `calculate_health_score` runs via the Celery pipeline
**Then** a new `FinancialHealthScore` row is persisted with Savings Ratio unchanged from Story 4.9 behavior, and Category Diversity / Expense Regularity / Income Coverage reflecting only spending-kind activity (they may increase — that is the point).

---

## Epic 5: Data Privacy, Trust & Consent

Users can understand how their data is used, consent to AI processing, view stored data, delete all their data, and see appropriate disclaimers — building the trust foundation for a financial product.

### Story 5.1: Data Encryption at Rest

As a **user**,
I want all my financial data encrypted at rest,
So that my sensitive information is protected even if storage is compromised.

**Acceptance Criteria:**

**Given** the AWS RDS PostgreSQL instance
**When** it is configured
**Then** encryption at rest is enabled using AES-256 (AWS KMS managed keys)

**Given** uploaded files stored in S3
**When** they are persisted
**Then** server-side encryption (SSE-S3 or SSE-KMS) is enabled on the bucket

**Given** any financial data (transactions, profiles, health scores, embeddings)
**When** it is stored in the database
**Then** it is encrypted at the storage layer transparently — no application-level encryption changes needed

### Story 5.2: Privacy Explanation & Consent During Onboarding

As a **user**,
I want to see a clear explanation of how my data is used and give explicit consent for AI processing,
So that I can make an informed decision before sharing my financial data.

**Acceptance Criteria:**

**Given** I am a new user completing registration
**When** I reach the onboarding flow
**Then** I see a clear, plain-language data privacy explanation covering: what data is collected, how AI processes it, where it's stored, and who has access

**Given** the privacy explanation screen
**When** I read it
**Then** explicit consent for AI processing of financial data is required via a checkbox before I can proceed

**Given** I do not check the consent checkbox
**When** I try to proceed
**Then** I cannot continue to the main app — consent is mandatory

**Given** the consent is given
**When** it is recorded
**Then** the consent timestamp and version are stored in the user's record for audit purposes

**Given** the onboarding privacy screen
**When** it renders
**Then** the tone is warm and reassuring (not legalese), matching the product's personality

### Story 5.3: Financial Advice Disclaimer

As a **user**,
I want to see a clear disclaimer that this product provides education and insights, not financial advice,
So that I understand the nature of the service.

**Acceptance Criteria:**

**Given** I am going through onboarding
**When** I reach the appropriate step
**Then** I see a financial advice disclaimer: "This product provides financial insights and education, not financial advice"

**Given** the Teaching Feed screen
**When** I view insight cards
**Then** a subtle but visible disclaimer is accessible (e.g., info icon or footer text) reminding users this is education, not advice

**Given** the disclaimer
**When** it is displayed
**Then** it is available in both Ukrainian and English matching the user's language preference

### Story 5.4: View My Stored Data

As a **user**,
I want to view what data the system has stored about me,
So that I have transparency and control over my information.

**Acceptance Criteria:**

**Given** I am authenticated
**When** I navigate to a "My Data" section in settings
**Then** I see a summary of all data stored: number of uploads, number of transactions, financial profile data, Health Score history, and consent records

**Given** the data summary page
**When** I view it
**Then** I can see the date ranges of my transaction data, categories detected, and total number of insights generated

**Given** the data summary API endpoint `GET /api/v1/users/me/data-summary`
**When** it responds
**Then** all data is scoped to the authenticated user_id and serialized in camelCase JSON

### Story 5.5: Delete All My Data

As a **user**,
I want to delete all my data with a single action,
So that I can exercise my right to be forgotten.

**Acceptance Criteria:**

**Given** I am on the "My Data" section in settings
**When** I click "Delete All My Data"
**Then** I see a confirmation dialog warning that this action is permanent and irreversible

**Given** I confirm the deletion
**When** the system processes it
**Then** all data is deleted: user account, transactions, uploads (S3 files), embeddings (pgvector), financial profile, Health Score history, insights, and consent records — via cascading delete

**Given** the deletion is complete
**When** the process finishes
**Then** I am logged out and redirected to the landing page with a confirmation message

**Given** another user's data exists in the system
**When** my data is deleted
**Then** no other user's data is affected (tenant isolation preserved)

**Given** a deletion request
**When** it is processed
**Then** the operation is logged for audit purposes (user_id + timestamp only, no personal data retained)

### Story 5.6: Compliance Audit Trail

As an **operator**,
I want all financial data access events logged with user ID, timestamp, action type, and resource for GDPR accountability,
So that the system maintains a compliance audit trail distinct from operational logging.

**Acceptance Criteria:**

**Given** any API request that accesses financial data (transactions, insights, profile, feedback, health scores)
**When** the request is processed
**Then** a compliance audit log entry is recorded with: user_id, timestamp, action_type (read/write/delete), resource_type, resource_id, and request metadata (IP, user agent)

**Given** the audit trail middleware (`core/audit.py`)
**When** it intercepts data access endpoints
**Then** it logs transparently without affecting request performance or response payload

**Given** a user exercises their right to data deletion (Story 5.5)
**When** their data is deleted
**Then** the audit trail retains only anonymized records (user_id replaced with a hash, no personal data) for regulatory compliance

**Given** the audit log entries
**When** an operator queries them
**Then** they can filter by user_id, date range, action_type, and resource_type to reconstruct a complete data access history for any user

**Given** audit log storage
**When** entries are persisted
**Then** they are stored in a structured format (JSON) separate from operational logs, with a retention policy of 2 years minimum

## Epic 6: Error Handling, Recovery & Operational Monitoring

The system handles errors gracefully with user-friendly messages, recovers from pipeline failures, flags uncategorized transactions, and provides operational observability for the team.

### Story 6.1: User-Friendly Error Messages & Error States

As a **user**,
I want to see friendly, helpful error messages when something goes wrong,
So that I'm not confused or alarmed by technical errors.

**Acceptance Criteria:**

**Given** any error occurs in the application
**When** it is displayed to the user
**Then** the message is user-friendly, actionable, and never exposes technical details (stack traces, error codes, internal paths)

**Given** a file format is not recognized
**When** the system detects it
**Then** the user sees a friendly message suggesting corrective actions (e.g., "We don't recognize this file format yet. Try exporting a CSV from your Monobank app")

**Given** the frontend encounters an API error
**When** the error boundary catches it
**Then** each feature area (Teaching Feed, Profile, Upload, Settings) has its own error boundary showing a lighthearted recovery message ("Our AI tripped over your spreadsheet — give it another try?")

**Given** error messages
**When** they are displayed
**Then** they are available in both Ukrainian and English via next-intl, and the tone is warm and humorous (not clinical or alarming)

### Story 6.2: Pipeline Failure Recovery & Retry

As a **user**,
I want the system to recover from pipeline failures without losing my data,
So that I don't have to re-upload my statement when something goes wrong.

**Acceptance Criteria:**

**Given** a pipeline processing job fails mid-execution
**When** the failure is detected
**Then** all partial results are preserved via LangGraph checkpointing — completed agent stages are not re-run

**Given** a failed pipeline job
**When** the user sees the failure notification
**Then** a "Retry" button is available that resumes processing from the last checkpoint without requiring a re-upload

**Given** a Celery task fails due to a transient error (LLM API timeout, network issue)
**When** the retry mechanism activates
**Then** it retries up to 3 times with exponential backoff before marking the job as permanently failed and moving to the dead letter queue

**Given** the LLM API fails 3 consecutive times
**When** the circuit breaker activates
**Then** subsequent requests are short-circuited for a cooldown period, and the user is informed that processing is temporarily unavailable

### Story 6.3: Uncategorized Transaction Flagging

As a **user**,
I want to see which transactions couldn't be categorized,
So that I'm aware of gaps in my financial analysis.

**Acceptance Criteria:**

**Given** the Categorization Agent processes transactions
**When** some transactions cannot be confidently categorized
**Then** they are flagged as "uncategorized" with a low confidence indicator

**Given** uncategorized transactions exist
**When** I view the Teaching Feed or profile
**Then** uncategorized transactions are displayed in a separate section with a friendly explanation ("We couldn't figure out a few of these — they won't affect your overall insights")

**Given** the uncategorized transactions section
**When** I view it
**Then** each transaction shows: date, description, amount, and the reason it couldn't be categorized

### Story 6.4: Structured Logging with Correlation IDs

As an **operator**,
I want structured JSON logs with correlation IDs across all pipeline agents,
So that I can trace and debug issues end-to-end.

**Acceptance Criteria:**

**Given** any backend operation (API request, pipeline step, Celery task)
**When** it executes
**Then** a structured JSON log entry is produced with: timestamp, level, service, user_id, job_id, message, and relevant context fields

**Given** a pipeline processing job
**When** it progresses through multiple agents
**Then** all log entries share the same job_id correlation ID, enabling end-to-end tracing

**Given** log levels
**When** they are used
**Then** they follow the convention: DEBUG (SQL queries, LLM prompts), INFO (pipeline step completed, upload received), WARNING (LLM retry, low confidence), ERROR (pipeline failure, auth failure), CRITICAL (DB connection lost, Redis down)

**Given** production logs
**When** they are emitted
**Then** they never contain sensitive financial data (transaction amounts, descriptions) — only IDs, timestamps, and operation metadata

### Story 6.5: Pipeline Performance & Upload Metrics Tracking

As an **operator**,
I want to track pipeline processing times and upload success/failure rates,
So that I can monitor system health and identify performance issues.

**Acceptance Criteria:**

**Given** a pipeline job completes (success or failure)
**When** the metrics are recorded
**Then** processing time per agent (ingestion, categorization, education) is logged with the job_id

**Given** an upload is received
**When** it is processed (success or failure)
**Then** the result is logged with: upload_id, file_type, file_size, bank_format_detected, success/failure status, error_type (if failed)

**Given** the pipeline metrics data
**When** an operator queries the database
**Then** they can calculate: average processing time per agent, p95 processing time, success/failure rate by time period, and most common error types

### Story 6.6: Operator Job Status & Health Queries

As an **operator**,
I want to query job status and pipeline health via database queries,
So that I can monitor the system without a dedicated dashboard in MVP.

**Acceptance Criteria:**

**Given** the `processing_jobs` table
**When** an operator queries it
**Then** they can see: job status (queued, processing, completed, failed), timestamps (created, started, completed), agent progress, error details, and user_id

**Given** an operator wants to check pipeline health
**When** they run SQL queries against the database
**Then** they can determine: number of jobs by status, average completion time over last 24h, failure rate, and stuck jobs (processing for > 5 minutes)

**Given** the operational data
**When** it is queried
**Then** all job and metric tables have appropriate indexes for efficient querying (status, created_at, user_id)

## Epic 7: User Feedback System

Users can provide feedback on Teaching Feed content through implicit behavioral signals, explicit thumbs up/down, issue reporting, and milestone-triggered feedback cards — enabling continuous improvement of RAG education quality without interrupting the user experience. Phased: Layers 0-1 (MVP), Layer 2 (Phase 1.5), Layer 3 (Phase 2).

### Story 7.1: Implicit Card Interaction Tracking & Engagement Score

As a **developer**,
I want to track implicit card interaction signals and compute a per-card engagement score,
So that the system can measure education content quality without requiring any user action.

**Acceptance Criteria:**

**Given** a user views a Teaching Feed card
**When** they interact with it (view, expand, swipe)
**Then** the following signals are captured: time_on_card_ms, education_expanded (boolean), education_depth_reached (0-2), swipe_direction (left/right/none), card_position_in_feed

**Given** the existing `card_interactions` table from Story 3.8
**When** the schema is extended via Alembic migration
**Then** the new columns are added: time_on_card_ms (integer), education_expanded (boolean), education_depth_reached (smallint), swipe_direction (varchar), card_position_in_feed (smallint)

**Given** implicit signals are collected for a card
**When** the engagement score is computed
**Then** a weighted formula produces a score from 0-100: time_on_card_ms (30%), education_expanded (25%), education_depth_reached (25%), swipe_direction (10%), card_position_in_feed (10%)

**Given** the frontend collects interaction signals
**When** a user navigates away from a card (swipe or leave)
**Then** the signals are batched and sent to `POST /api/v1/cards/interactions` to minimize network requests

**Given** the interaction tracking
**When** it runs on mobile and desktop
**Then** it captures signals without perceptible UI lag or impact on card navigation performance

### Story 7.2: Thumbs Up/Down on Teaching Feed Cards

As a **user**,
I want to rate any Teaching Feed card with thumbs up or thumbs down,
So that I can signal whether an insight was helpful.

**Acceptance Criteria:**

**Given** I am viewing a Teaching Feed card
**When** the card has been visible for 2+ seconds
**Then** two small, muted thumb icons (up/down) appear in the bottom-right of the card

**Given** I tap the thumbs-up or thumbs-down icon
**When** the vote is registered
**Then** the icon fills/highlights, I receive brief haptic feedback (mobile), and the vote is sent to `POST /api/v1/feedback/cards/{cardId}/vote` with `{"vote": "up"}` or `{"vote": "down"}`

**Given** a `card_feedback` table is created via Alembic migration
**When** a vote is stored
**Then** it contains: id (UUID), user_id (FK), card_id (FK), card_type (varchar), vote (up/down), reason_chip (nullable), free_text (nullable), feedback_source ('card_vote'), created_at
**And** a unique constraint on (user_id, card_id, feedback_source) prevents duplicate votes

**Given** I have previously voted on a card
**When** I return to that card
**Then** my vote state is visible (filled icon) via `GET /api/v1/feedback/cards/{cardId}`

**Given** I tap the opposite thumb icon on a card I already voted on
**When** the update is processed
**Then** my vote is changed (not duplicated) and the UI reflects the new state

**Given** the thumbs icons
**When** they render
**Then** they meet WCAG 2.1 AA standards: keyboard accessible, screen reader labeled ("Rate this insight helpful" / "Rate this insight not helpful"), visible focus indicators

### Story 7.3: Issue Reporting on Teaching Feed Cards

As a **user**,
I want to report an issue on any Teaching Feed card via a flag icon,
So that I can flag bugs, incorrect information, or confusing content without leaving the feed.

**Acceptance Criteria:**

**Given** I am viewing a Teaching Feed card
**When** I tap the card's overflow menu (three-dot icon)
**Then** I see a "Report an issue" option with a flag icon

**Given** I tap "Report an issue"
**When** the report form appears
**Then** it displays in-context (not a modal or redirect): a category dropdown (Bug, Incorrect info, Confusing, Other) and an optional free-text field (max 500 characters, collapsed by default)

**Given** I select a category and optionally enter text
**When** I submit the report
**Then** it is sent to `POST /api/v1/feedback/cards/{cardId}/report` with feedback_source='issue_report' and a confirmation is shown briefly ("Thanks for reporting — we'll look into it")

**Given** the unique constraint on (user_id, card_id, feedback_source)
**When** I try to report the same card twice
**Then** I see a message that I've already reported this card

**Given** the report form
**When** it renders on mobile
**Then** it is compact, touch-optimized, and dismissible by tapping outside or swiping down

**Given** the report form fields
**When** they are displayed
**Then** they are available in both Ukrainian and English via next-intl

### Story 7.4: Feedback Data Privacy Integration

As a **user**,
I want my feedback data (votes, reports, free-text) included in my data export and one-click deletion,
So that I have full control over all data the system stores about me.

**Acceptance Criteria:**

**Given** the `card_feedback` table has FK to `users.id`
**When** a user triggers one-click data deletion (Story 5.5)
**Then** all card_feedback rows for that user are deleted via FK cascade

**Given** a user requests their stored data (Story 5.4)
**When** the data summary API responds
**Then** it includes: number of card votes (up/down counts), number of issue reports, and any free-text feedback the user has submitted

**Given** the data export includes free-text feedback
**When** the user views it
**Then** they can see exactly what they wrote, which card it was on, and when

**Given** feedback_responses records exist (from Layer 3 milestone cards, future)
**When** deletion or export is triggered
**Then** feedback_responses rows are also included in cascade delete and data export

### Story 7.5: Thumbs-Down Follow-Up Panel with Reason Chips

As a **user**,
I want to quickly tell the system why I thumbs-downed a card,
So that my feedback is categorized for better education quality improvement.

**Acceptance Criteria:**

**Given** I tap thumbs-down on a Teaching Feed card
**When** 300ms has elapsed after my tap
**Then** a compact slide-up panel appears below the card (not a modal) with 4 preset reason chips: "Not relevant to me", "Already knew this", "Seems incorrect", "Hard to understand"

**Given** the follow-up panel is visible
**When** I tap a reason chip
**Then** the chip selection is sent via `PATCH /api/v1/feedback/{feedbackId}` with `{"reasonChip": "not_relevant"}`, the panel auto-dismisses after 1 second, and no further interaction is required

**Given** the follow-up panel is visible
**When** I tap outside the panel or swipe it down
**Then** it dismisses without recording a reason (the thumbs-down vote still stands)

**Given** I thumbs-down multiple cards in the same session
**When** the follow-up panel trigger logic runs
**Then** the panel appears only on the first thumbs-down of the session to prevent repetition

**Given** the reason chips
**When** they are displayed
**Then** they are available in both Ukrainian and English, compact enough for mobile, and keyboard accessible

### Story 7.6: Occasional Thumbs-Up Follow-Up

As a **user**,
I want to occasionally tell the system what made a card useful,
So that the system learns what works without asking me every time.

**Acceptance Criteria:**

**Given** I tap thumbs-up on a Teaching Feed card
**When** the system determines this is the 1-in-10 trigger occurrence
**Then** a compact slide-up panel appears with 3 preset chips: "Learned something", "Actionable", "Well explained"

**Given** the follow-up panel appears on thumbs-up
**When** I tap a chip or dismiss
**Then** it behaves identically to the thumbs-down panel: chip selection sent via PATCH, auto-dismiss after 1s, dismissible without action

**Given** the 1-in-10 trigger logic
**When** it determines whether to show the follow-up
**Then** the probability is computed client-side (random, not deterministic) so no server round-trip is needed

**Given** the follow-up panel
**When** it renders
**Then** it uses the same component as the thumbs-down follow-up panel (FollowUpPanel.tsx) with different chip labels

### Story 7.7: Milestone Feedback Cards in the Teaching Feed

As a **user**,
I want to see occasional feedback cards at the end of my Teaching Feed at key milestones,
So that I can share how the product is working for me without it feeling like an interruption.

**Acceptance Criteria:**

**Given** I have completed my 3rd upload (one-time milestone)
**When** I view the Teaching Feed
**Then** a milestone feedback card appears at the end of the feed: "How's Kopiika working for you?" with 3 emoji faces (happy/neutral/sad) and an optional text field

**Given** my Financial Health Score has changed significantly (+/- 5 points since last check)
**When** I view the Teaching Feed
**Then** a milestone feedback card appears at the end: "Your score changed! Does this feel accurate?" with Yes/No options and optional text

**Given** a milestone feedback card
**When** I interact with it
**Then** it uses the same card component, swipe gestures, and visual design as education cards — no new UI pattern

**Given** I swipe away or dismiss a milestone feedback card
**When** the dismissal is recorded
**Then** that specific milestone card never appears again (tracked via `feedback_responses` table unique constraint on user_id + feedback_card_type)

**Given** a `feedback_responses` table created via Alembic migration
**When** a response is stored
**Then** it contains: id (UUID), user_id (FK), feedback_card_type ('milestone_3rd_upload' or 'health_score_change'), response_value (varchar), free_text (nullable), created_at

**Given** the feedback card frequency cap logic
**When** determining whether to show a feedback card
**Then** max 1 feedback card per session and max 1 per month are enforced (tracked in application layer via Redis or user_preferences)

**Given** the Health Score change milestone card
**When** it checks for significant change
**Then** it depends on Epic 4's Financial Health Score data — if no Health Score exists yet, this trigger is skipped

### Story 7.8: RAG Topic Cluster Auto-Flagging

As a **developer**,
I want the system to automatically flag RAG topic clusters with high thumbs-down rates,
So that I can prioritize corpus quality improvements without manually reviewing all feedback.

**Acceptance Criteria:**

**Given** card_feedback votes have accumulated on cards within a topic cluster
**When** a cluster reaches a minimum of 10 votes
**Then** the system evaluates the thumbs-down rate for that cluster

**Given** a topic cluster has >30% thumbs-down rate with at least 10 votes
**When** the auto-flagging check runs
**Then** the cluster is flagged for review in a `flagged_topic_clusters` record (or equivalent) with: cluster_id, thumbs_down_rate, total_votes, flagged_at

**Given** the auto-flagging logic
**When** it runs
**Then** it executes as a periodic batch job (via Celery scheduled task or triggered after vote accumulation thresholds), not on every individual vote

**Given** a flagged topic cluster
**When** the developer queries flagged clusters
**Then** they can see: cluster identifier, current thumbs-down rate, total votes, most common reason_chip values, and sample card IDs for review

**Given** the minimum sample size of 10 votes
**When** a cluster has fewer than 10 votes
**Then** it is never flagged regardless of thumbs-down rate, preventing false positives from small samples

### Story 7.9: Celery Beat Scheduler Deployment

As a **developer**,
I want the Celery beat scheduler to run in every environment (local, CI, production),
So that tasks registered in `beat_schedule` (starting with Story 7.8's daily RAG cluster flagging) actually fire on their cadence instead of sitting dormant.

**Acceptance Criteria:**

**Given** the beat scheduler needs its own long-running process
**When** the backend is built for deployment
**Then** a dedicated beat container image is produced whose `CMD` is `celery -A app.tasks.celery_app beat --loglevel=info`, built either from a new `backend/Dockerfile.beat` or from `backend/Dockerfile.worker` parameterised with a build arg

**Given** the GitHub Actions deploy pipeline currently builds only `worker-$SHA` / `worker-latest` images
**When** `.github/workflows/deploy-backend.yml` runs on `main`
**Then** it also builds and pushes a beat image (`beat-$SHA` / `beat-latest`) to the same ECR repository in the same run, gated on the same migration step as the worker

**Given** the ECS cluster provisioned in `infra/terraform/modules/ecs/`
**When** the beat container is deployed
**Then** a separate ECS service (`${project}-${env}-beat`) runs the beat image with `desired_count = 1` (never 2+, as duplicate beat replicas multi-fire every scheduled job), using the existing task/execution IAM roles, private subnets, security group, and CloudWatch log group pattern that the worker uses

**Given** local development parity with production
**When** a developer runs `docker compose up`
**Then** a `beat` service starts alongside `redis` / `postgres` / `worker`, commanded `celery -A app.tasks.celery_app beat --loglevel=info`, depending on `redis`, so scheduled tasks fire locally exactly as they will in prod

**Given** Celery beat needs to persist its last-run state to avoid duplicate firings after restart
**When** the scheduler store is chosen
**Then** the default file-based `celerybeat-schedule` is used on an ephemeral path with an explicit note in `docs/operator-runbook.md` that a single-replica service is required for correctness; if the schedule grows beyond two entries, `celery-redbeat` (Redis-backed) is evaluated as follow-up tech-debt

**Given** the "Scheduled Tasks" section already exists in `docs/operator-runbook.md`
**When** the beat deployment lands
**Then** the **"⚠️ Deployment gap (TD-026)"** subsection is removed/replaced with a "Verifying beat is running" subsection documenting: how to find the beat service in ECS, the CloudWatch log stream to tail, the expected `"Scheduler: Sending due task"` log line cadence, and the manual `celery -A app.tasks.celery_app call …` fallback (kept for ad-hoc re-runs, not routine use)

**Given** the beat container can silently break (bad import, missing module, corrupted venv) without any obvious external signal
**When** the deployment is in place
**Then** the ECS task definition runs a container-level healthcheck that at minimum verifies the Celery app imports cleanly, so ECS replaces a wedged beat container automatically *(narrowed during Story 7.9 code review: the original 24-hour end-to-end broker canary was split out to **TD-028**, which captures the CloudWatch metric-filter + alarm fix shape for the "app up but silently not scheduling" failure class)*

**Given** TD-026 is tracked in `docs/tech-debt.md`
**When** the beat deployment implementation lands on `main`
**Then** the TD-026 entry is moved to a `## Resolved` section with a link to this story, AND the production firing verification (first scheduled `flag_low_quality_clusters` run at 02:00 UTC observed in CloudWatch logs) is explicitly tracked inline in the Resolved entry as a post-deploy follow-up *(narrowed during Story 7.9 code review: the original AC required verification before the move; narrowing allows the register to reflect "implementation complete" at merge time without stalling on post-deploy verification)*

---

## Epic 8: Pattern Detection, Triage & Subscription Detection

The 5-agent pipeline is complete. Users see insights ranked by financial severity (red/yellow/green), active subscriptions are surfaced with inactivity alerts, and month-over-month spending trends and anomalies are detected automatically.

### Story 8.1: Pattern Detection Agent

As a **user**,
I want the system to automatically detect spending patterns, trends, and anomalies in my transactions,
So that I receive insights about financial patterns I would never have spotted manually.

**Acceptance Criteria:**

**Given** the Categorization Agent has completed and persisted categorized transactions for a processing job
**When** the Pattern Detection Agent (LangGraph node at `agents/pattern_detection/node.py`) runs
**Then** it analyzes the transaction set for: month-over-month category spending changes, anomalously large single transactions (outliers by amount within category), and intra-period spending distribution across categories

**Given** two or more months of transaction data are available for the user
**When** the Pattern Detection Agent runs `detectors/trends.py`
**Then** category-level spending changes (% delta and UAH delta) are computed and persisted to a `pattern_findings` table created via Alembic migration (fields: id UUID, user_id FK, upload_id FK, pattern_type ENUM, category, period_start, period_end, baseline_amount_kopiykas, current_amount_kopiykas, change_percent, finding_json JSONB)

**Given** only a single upload's worth of data is available
**When** the Pattern Detection Agent runs
**Then** it generates intra-period findings only (spending distribution, top categories, high single transactions); `change_percent`, `baseline_amount_kopiykas` are null; no month-over-month fields are emitted

**Given** the Pattern Detection Agent is integrated into the 5-agent pipeline
**When** the Celery worker executes the LangGraph pipeline
**Then** the flow is: Ingestion → Categorization → Pattern Detection → Triage → Education; SSE progress emits a `"pattern-detection"` step with its own human-readable message (e.g., "Detecting spending patterns..."); the full pipeline still completes within 60 seconds for 200-500 transactions (NFR4)

**Given** the Pattern Detection Agent throws an unhandled exception
**When** the error handler activates
**Then** the pipeline continues to the Triage and Education steps with whatever findings were produced before the failure — partial findings are acceptable; the job does not fail entirely

### Story 8.2: Subscription Detection

As a **user**,
I want active subscriptions and recurring charges automatically identified from my transactions,
So that I can see exactly what I'm paying for every month and spot any I've forgotten about.

**Acceptance Criteria:**

**Given** the Pattern Detection Agent runs and `detectors/recurring.py` analyzes the transaction set
**When** it identifies subscription candidates
**Then** it groups charges from the same merchant occurring on a regular cadence (monthly ± 3 days, or annual ± 7 days) with consistent amounts (within 5% tolerance for price changes) and flags them as recurring subscriptions

**Given** a detected subscription
**When** it is persisted
**Then** it is stored in a `detected_subscriptions` table created via Alembic migration (fields: id UUID, user_id FK, upload_id FK, merchant_name, estimated_monthly_cost_kopiykas INT, billing_frequency ENUM('monthly','annual'), last_charge_date DATE, is_active BOOL, months_with_no_activity INT)

**Given** a detected subscription has had no matching transaction in the last 35 days (for monthly) or 375 days (for annual)
**When** it is persisted
**Then** `is_active = false` and `months_with_no_activity` is set to the integer number of missed billing cycles

**Given** the Education Agent receives subscription findings from the triage output
**When** it generates insight cards for subscription findings
**Then** it creates cards with `card_type = "subscriptionAlert"` containing: subscription service name, monthly cost, billing frequency, inactivity status; stored in the `insights` table alongside other card types

**Given** the Teaching Feed API `GET /api/v1/insights` serializes cards
**When** a card has `card_type = "subscriptionAlert"`
**Then** the response JSON includes a `subscription` object with fields: `merchantName` (string), `monthlyCostUah` (number), `billingFrequency` ("monthly" | "annual"), `isActive` (boolean), `monthsWithNoActivity` (integer | null)

**Given** a `subscriptionAlert` card is rendered in the Teaching Feed
**When** the user views it
**Then** `SubscriptionAlertCard.tsx` displays: service name as headline, monthly cost as key metric, billing frequency as a label, and — if `isActive = false` — an inactivity badge showing "Inactive X month(s)"

### Story 8.3: Triage Agent & Severity Scoring

As a **user**,
I want my financial insights ranked by severity so I know which ones demand my attention first,
So that I'm not overwhelmed and can focus on what matters most.

**Acceptance Criteria:**

**Given** the Pattern Detection Agent has produced its findings
**When** the Triage Agent (LangGraph node at `agents/triage/node.py`) runs
**Then** it assigns a `severity` level to each finding using scoring logic in `severity.py` based on UAH impact: `critical` — finding affects > 20% of the user's estimated monthly income, or an inactive subscription costs > 500 UAH/month; `warning` — finding affects 5–20% of monthly income, or a spending category increased > 25% month-over-month; `info` — finding affects < 5% of monthly income or is informational

**Given** severity is assigned to all findings
**When** the Education Agent generates insight cards from those findings
**Then** each `insights` record is stored with the `severity` field set to the triage output value (`critical`, `warning`, `info`), filling the field that was already in the schema from Story 3.4

**Given** the user's monthly income estimate is unavailable (first upload, no income transactions detected)
**When** the severity scoring runs
**Then** severity falls back to absolute UAH thresholds: `critical` > 2,000 UAH impact, `warning` 500–2,000 UAH, `info` < 500 UAH

**Given** the Triage Agent fails or produces no output
**When** insights are stored
**Then** all `severity` fields default to `info` — the pipeline never fails or produces null severity values

**Given** the Teaching Feed API `GET /api/v1/insights`
**When** it queries the insights table
**Then** results are sorted server-side by severity: `critical` first, `warning` second, `info` third (replacing the previous sort order which had no severity ranking)

### Story 8.4: Teaching Feed Triage UX

As a **user**,
I want insight cards to display a clear visual severity indicator,
So that I can immediately understand the urgency of each insight without reading its full content.

**Acceptance Criteria:**

**Given** an insight card with `severity = "critical"`
**When** it renders in the Teaching Feed
**Then** a `TriageBadge.tsx` component displays a red badge with a warning icon and "Critical" text label; the card also has a subtle red left-border accent to reinforce urgency at a glance

**Given** an insight card with `severity = "warning"`
**When** it renders
**Then** the `TriageBadge` displays an amber/yellow badge with a caution icon and "Warning" text label

**Given** an insight card with `severity = "info"`
**When** it renders
**Then** the `TriageBadge` displays a teal/green badge with an info icon and "Info" text label (or the badge is omitted entirely to reduce visual noise for low-severity cards — implementation decision)

**Given** a user who cannot distinguish red, yellow, and green by colour
**When** they view the Teaching Feed
**Then** severity is conveyed through both the icon shape AND the text label ("Critical", "Warning", "Info") — not colour alone (NFR21 colour independence compliance)

**Given** a screen reader user navigating the Teaching Feed
**When** their focus enters a severity badge
**Then** it announces as "Severity: Critical", "Severity: Warning", or "Severity: Informational" via `aria-label` on the badge element (NFR20 screen reader compatibility)

**Given** the Teaching Feed is loaded after a completed pipeline
**When** the card list renders
**Then** critical-severity cards appear at the top, followed by warning, followed by info — consistent with the server-side sort order introduced in Story 8.3

**Given** a user with `prefers-reduced-motion` enabled
**When** the Teaching Feed renders
**Then** the severity badges display as static elements — no pulse, glow, or attention animation is applied even if one is added for critical emphasis

---

## Epic 9: AI Infra Readiness (Bedrock Provider, RAG Eval Harness, Embedding Decision)

**Status:** Backlog — Phase 2 prerequisite for Epic 10 (Chat-with-Finances)
**FRs covered:** None (infrastructure epic — success measured against NFRs)
**NFRs covered:** NFR32 (multi-provider abstraction), NFR33 (RAG harness regression gate), NFR40 (Bedrock SDK reliability), NFR42 (embedding decision gate)
**Depends on:** Epic 8 complete
**Blocks:** Epic 10

### Goal

Prepare the AI layer for Phase 2 conversational features. Adds AWS Bedrock as a configurable LLM provider (without removing Anthropic/OpenAI), introduces a RAG evaluation harness to gate embedding-model decisions with data, validates Bedrock + AgentCore regional availability, and provisions IAM/observability plumbing. Optional time-boxed evaluation of Step Functions/AWS Batch as a future orchestration alternative to Celery.

### Success Criteria

- `llm.py` supports Anthropic / OpenAI / Bedrock via `LLM_PROVIDER` env var; Epic 3 & 8 agents pass regression on all three
- RAG evaluation harness runs in CI with baseline metrics on current OpenAI text-embedding-3-small
- Embedding-model decision is either "stay on current" or "migrate to <winner>" — backed by harness results
- AgentCore + Bedrock availability confirmed in eu-central-1 (or a region pivot is planned)
- IAM + CloudWatch cost tags in place for Bedrock / Guardrails / AgentCore resources

### Stories

- **9.1 — RAG Evaluation Harness**
  Offline test suite: retrieval precision@k, LLM-as-judge for answer quality, per-corpus-topic breakdown, UA + EN coverage. Runnable locally + in CI. Baseline run against current OpenAI text-embedding-3-small stored as reference.

- **9.2 — Baseline Current Embeddings Through Harness**
  Run harness against production RAG corpus with current embeddings. Record baseline metrics. Any future embedding change is measured against this.

- **9.3 — Embedding Model Comparison Spike (Decision Gate)**
  Benchmark 4 candidates via harness: OpenAI `text-embedding-3-small` (baseline), `text-embedding-3-large`, Titan Text Embeddings V2, Cohere `embed-multilingual-v3`. Compare UA + EN retrieval quality, cost, latency. Produce recommendation. **Output: either "stay on 3-small" or "migrate to <winner>".**

- **9.4 — AgentCore + Bedrock Region Availability Spike (Decision Gate)**
  Validate Claude-on-Bedrock (haiku, sonnet) + AgentCore availability in eu-central-1. Document fallback: cross-region inference profile vs region pivot. **Blocks Epic 10 scope-lock.**

- **9.5a — `llm.py` Provider-Routing Refactor (Anthropic + OpenAI only)**
  Pure abstraction work: refactor `llm.py` to route by `LLM_PROVIDER` env var. Factory + provider-qualified model IDs in `models.yaml`. **No Bedrock yet** — retains existing Anthropic + OpenAI behavior bit-for-bit. Unblocks parallel work on 9.5b/c. Local dev stays on Anthropic/OpenAI by default.

- **9.5b — Add Bedrock Provider Path + Smoke Test**
  Wire `ChatBedrock` into the provider factory. Pin Bedrock model ARNs (haiku/sonnet) in `models.yaml`. Smoke-test against haiku + sonnet in `eu-central-1` (or fallback region per Story 9.4). Choose + document Bedrock-hosted fallback model (gpt-4o-mini is not on Bedrock). Depends on 9.5a, 9.4, 9.7.

- **9.5c — Cross-Provider Regression Suite (Epic 3 + 11 LLM agents × 3 providers)**
  Build `backend/tests/agents/providers/` matrix runner. Epic 3 (categorization, RAG education) + Epic 11 (AI-assisted schema detection) agents must produce equivalent outputs on Anthropic / OpenAI / Bedrock. CI job exercises all three. Source of truth for provider equivalence. (Epic 8 agents — pattern, subscription, triage — are pure statistical code with zero LLM calls today; excluded from the matrix until an LLM is wired into one of those paths.) Depends on 9.5b.

- **9.6 — Embedding Migration**
  Migrates production embeddings to `text-embedding-3-large` (3072 dims); trigger source: Story 9.3 decision doc (`docs/decisions/embedding-model-comparison-2026-04.md`, 2026-04). Alembic migration must switch `document_embeddings.embedding` to `halfvec(3072)` + `halfvec_cosine_ops` HNSW — pgvector native `vector` HNSW caps at 2000 dims; see TD-079 for the full task breakdown. Re-seed corpus; rebuild HNSW `(m=16, ef_construction=64)`. Zero-downtime cutover plan. Acceptance gate: re-run Story 9.1 harness and confirm metrics match or beat the Story 9.3 spike baseline (`text-embedding-3-large.json`) within judge-noise.

- **9.7 — Bedrock IAM + Observability Plumbing**
  Celery ECS task role: `bedrock:InvokeModel`, `bedrock:ApplyGuardrail`, `bedrock-agentcore:*` (scoped). CloudWatch cost-allocation tags (`feature=chat`, `epic=10`). Terraform + tfsec waivers if needed.

- **9.8 — Pipeline Orchestration Evaluation (Optional, Time-Boxed Spike)**
  Compare current Celery+Redis architecture to AWS Step Functions / AWS Batch for Epic 3/8 pipeline. Output: recommendation doc only — actual migration requires separate approval. **Default outcome: stay on Celery.**

### Out of Scope

- Any chat feature (belongs to Epic 10)
- AgentCore integration beyond availability validation (belongs to Epic 10)
- Guardrails configuration (belongs to Epic 10 — IAM only here)

---

## Epic 10: Chat-with-Finances (AgentCore + AI Safety)

**Status:** Backlog — Phase 2
**FRs covered:** FR64, FR65, FR66, FR67, FR68, FR69, FR70, FR71, FR72
**NFRs covered:** NFR34 (Guardrails coverage), NFR35 (red-team pass rate), NFR36 (OWASP + UA adversarial corpus coverage), NFR37 (zero PII leakage in chat), NFR38 (grounding rate ≥ 90%), NFR39 (refusal correctness), NFR41 (AgentCore SDK reliability + per-user isolation)
**Depends on:** Epic 9 complete (especially 9.4 region gate, 9.5 multi-provider llm.py, 9.7 IAM)
**Does NOT depend on:** Payments/subscription (chat ships ungated; subscription gate tracked in TD-041 as a payments-epic follow-up)

### Goal

Deliver a conversational chat interface grounded in the user's own financial data, built on AWS Bedrock + AgentCore with defense-in-depth AI safety: Bedrock Guardrails, prompt-injection/jailbreak defenses, tool-use scoping, and a red-team safety test suite as a CI gate.

### Success Criteria

- Users can ask natural-language questions about their own transactions, categories, health score, and teaching-feed history (UA + EN)
- Responses stream token-by-token, cite underlying data when making data-specific claims, and refuse out-of-scope/unsafe requests with neutral messaging
- 100% of chat turns pass through Bedrock Guardrails (input + output)
- Red-team corpus pass rate ≥ 95% as a merge-blocking CI gate
- Chat sessions are per-user-isolated; deletion cascades with account deletion
- `chat_processing` consent obtained on first use; revocation disables chat and deletes chat history

### Stories

_Story numbering reflects intended delivery order. The UX spec (Stories 10.3a + 10.3b) is a prerequisite for the Chat UI (Story 10.7); 10.3a (skeleton) must be scope-locked before UI scaffolding begins, 10.3b (states) before refusal/consent/rate-limit UX is finalized. Stories 10.4a–10.6b can proceed in parallel with 10.3._

- **10.1a — `chat_processing` Consent (separate from `ai_processing`)**
  Backend consent record + version field. Frontend gate blocks chat until granted. Consent-version-bump re-prompt flow: active sessions continue under captured version (`chat_sessions.consent_version_at_creation`); new sessions re-prompt. Revoke path defined here; cascade implementation lives in 10.1b.

- **10.1b — `chat_sessions` / `chat_messages` Schema + Cascade Delete**
  Alembic migration: `chat_sessions` (with `consent_version_at_creation`) + `chat_messages` tables. Cascade delete wired to account deletion (FR31) and consent revocation (10.1a). Cascade-delete tests required. Depends on 10.1a for the consent-version field shape.

- **10.2 — AWS Bedrock Guardrails Configuration**
  Guardrail definition in Terraform: input/output content filters, denied topics (illegal, self-harm, out-of-scope financial advice), PII redaction (emails, IBANs, card numbers), word filters, contextual grounding. CloudWatch alarm on block-rate anomaly.

- **10.3a — Chat UX Skeleton (IA + Conversation/Composer/Streaming/Citations Layout)**
  Update ux-design-specification.md with the happy-path chat-screen IA: conversation layout, composer, streaming render pattern, citation chips placement, mobile-first viewport, basic accessibility scaffold. Wireframes + flows. Unblocks Story 10.7 frontend scaffolding.

- **10.3b — Chat UX States Spec (Refusals, Consent, Deletion, Rate-Limit, Edge Cases)**
  Detailed states layered onto the 10.3a skeleton: principled-refusal UX with reason-specific copy + correlation-ID surface, consent first-use prompt + version-bump re-prompt, deletion flow, abuse/rate-limit soft-block UX, optional session-summarization UI, full WCAG 2.1 AA pass, UA + EN copy edge cases. Concurrent with 10.4a–10.6b; prerequisite for finalizing Story 10.7's refusal/consent/rate-limit UX.

- **10.4a — AgentCore Session Handler + Memory/Session Bounds**
  Bring up AgentCore session handler: lifecycle (create/resume/terminate), per-session memory window (20 turns or 8k tokens, whichever first) with server-side summarization of older turns, basic prompt → response loop. Minimum viable stateful agent — no tools, no hardening yet. (Rate-limit envelope is owned by Story 10.11.)

- **10.4b — System-Prompt Hardening + Canary Tokens**
  Role isolation, instruction anchoring, canary token insertion + leak detection wiring. Surfaces `CHAT_REFUSED` with `reason=prompt_leak_detected` when canaries are detected in model output. Depends on 10.4a.

- **10.4c — Tool Manifest (Read-Only Data Tools)**
  Define + implement read-only tool allowlist: transactions, profile, teaching-feed history, RAG corpus retrieval. Schema validation, allowlist enforcement, denial path. **No write-actions** (Phase 2 follow-up). Depends on 10.4a.

- **10.5 — Chat Streaming API + SSE**
  FastAPI endpoint + SSE streaming for token-by-token responses. Error envelope for Guardrails blocks / grounding / rate-limit / canary-leak (`CHAT_REFUSED` with `reason` enum + `correlation_id`). Per-turn Guardrails input + output gating wired in.

- **10.6a — Grounding Enforcement + Harness Measurement**
  Bedrock Guardrails contextual-grounding threshold tuned (initial target ≥ 0.85). Ungrounded data-specific claims blocked, not regenerated, per architecture § AI Safety — Chat Agent returns `CHAT_REFUSED` with `reason=ungrounded`. LLM-as-judge evaluation in the RAG harness (Story 9.1) tracks grounding rate ≥ 90%. Depends on 10.4a + 10.5.

- **10.6b — Citation Payload + Data Refs in API**
  Agent responses include structured citation payload referencing underlying user data (transaction IDs, categories, profile fields, RAG corpus source IDs) when making data-specific claims. API contract for citations defined here; FE chip rendering lives in Story 10.7. Depends on 10.4c.

- **10.7 — Chat UI (Conversation, Composer, Streaming, Refusals)**
  Chat screen in frontend: message list, composer, streaming rendering, citation chips, principled-refusal UX (reason-specific copy + correlation-ID, no leakage of filter rationale). WCAG 2.1 AA. UA + EN. Mobile-first. Consumes the UX spec produced in 10.3.

- **10.8a — Red-Team Corpus Authoring (UA + EN)**
  `backend/tests/ai_safety/corpus/` — author the seed red-team corpus: OWASP LLM Top-10 mapped, known jailbreak patterns, UA-language adversarial prompts, canary-token extraction attempts, cross-user data probes. Versioned + reviewable. Quarterly review cadence documented.

- **10.8b — Safety Test Runner + CI Gate**
  Runner that exercises the 10.8a corpus against the live agent (Guardrails + grounding enforced). Metrics: per-category pass rate, regression deltas. CI gate at ≥ 95% pass rate for any merge touching agent code, prompts, tools, or Guardrails config — merge-blocking. Depends on 10.8a + 10.4 series + 10.5 + 10.6a.

- **10.9 — Safety Observability**
  CloudWatch metrics (Guardrails block rate, grounding-block rate, refusal rate, `CanaryLeaked`, per-user token spend, chat P95 first-token latency). Alarms per architecture § Observability & Alarms thresholds. Operator runbook section (docs/operator-runbook.md): Guardrails violation triage, jailbreak incident response, chat abuse handling.

- **10.10 — Chat History + Deletion**
  Users can view and delete chat sessions/messages. Export path (FR35). Account-deletion cascade verified (FR31 + FR70).

- **10.11 — Abuse & Rate-Limit Enforcement**
  Single source of truth for chat throttling (envelope previously co-listed under Story 10.4 — consolidated here): **60 messages per hour per user** (soft-block with retry guidance), **10 concurrent sessions per user** (soft-block), per-user daily token cap (returns `CHAT_REFUSED` with `reason=rate_limited`), global per-IP cap at API-gateway layer (reuses existing limit). Token-spend anomaly detection + alarms (per architecture § Observability). Soft-block UX wired to the spec from Story 10.3b.

### Out of Scope for Epic 10 (tracked as Phase 2 follow-ups)

- **Voice input/output** — Phase 2 follow-up; separate epic once chat UX validates
- **Chat-based transaction edits/actions** — Phase 2 follow-up; requires separate safety review (write-path tools change the threat model significantly). Epic 10 ships read-only.

### Out of Scope (not tracked)

- Payments / subscription dependency (chat ships ungated; subscription gate is a follow-up story after payments land)
- Proactive chat notifications / push
- Multi-language beyond UA + EN
- New RAG corpus content creation (uses existing corpus)

---

## Epic 11: Ingestion & Categorization Hardening

**Status:** Backlog
**FRs covered:** FR73, FR74, FR75, FR76, FR77
**ADRs:** ADR-0001 (transaction kind first-class), ADR-0002 (AI-assisted schema detection)
**Tech spec:** [tech-spec-ingestion-categorization.md](./tech-spec-ingestion-categorization.md)
**Source analysis:** [parsing-and-categorization-issues.md](../implementation-artifacts/parsing-and-categorization-issues.md)
**Depends on:** Epic 2 (ingestion pipeline), Epic 3 (categorization agent)
**Cross-epic consumer:** Story 4.9 (Savings Ratio wiring)

### Goal

Fix structural weaknesses in the ingestion + categorization pipeline identified in the April 2026 incident analysis. Two independent tracks delivered in parallel:

- **Categorization track (measurement-first):** Introduce `transaction_kind` as a first-class field, extend the category taxonomy (`savings`, `transfers_p2p`), enrich the LLM prompt with MCC + signed amount + direction, and gate further rule-based work behind a golden-set accuracy measurement.
- **Parsing track:** Replace brittle heuristic column detection with AI-assisted schema detection for unknown formats (cached by header fingerprint), add a post-parse validation layer with partial-import semantics, and handle encoding variations.

### Success Criteria

- Categorization accuracy on the golden set ≥ 90% on **both** `category` and `transaction_kind` axes (independently measured)
- Savings Ratio in the Health Score produces non-zero values for users with deposit transactions (validated via Story 4.9)
- New bank formats can be uploaded without a code change; header-fingerprint cache hit rate ≥ 95% after the second upload
- Parse errors surface as structured partial-import warnings rather than silent corruption (validation layer catches all rules in tech spec §5.1)
- `transfer`-kind transactions no longer inflate or hide the `finance` category

### Delivery Order

**Sprint 1 (parallel):**
- Story 11.1 (golden-set harness), Story 11.2 (schema), Story 11.3 (enriched prompt) — categorization track, sequenced
- Story 11.5 (validation), Story 11.6 (encoding) — parsing track, parallel with categorization

**Sprint 2:**
- Story 11.4 (pre-pass rules) — **only if 11.3 measurement < 90%**
- Story 11.7 (AI schema detection + registry)
- Story 11.8 (review queue)

**Sprint 3:**
- Story 11.9 (observability)
- Story 4.9 (Savings Ratio wiring — owned by Epic 4 but enabled here)

### Stories

### Story 11.1: Golden-Set Evaluation Harness for Categorization

As a **developer**,
I want a labeled golden set of real Monobank transactions with a pytest-driven accuracy harness,
So that every categorization pipeline change is measured against a known ground truth before merge.

**Acceptance Criteria:**

**Given** real Monobank statements redacted to remove PII
**When** the golden set is authored
**Then** `backend/tests/fixtures/categorization_golden_set/golden_set.jsonl` contains at least 50 labeled transactions, each with `id`, `description`, `amount_kopiykas`, `mcc`, `expected_category`, `expected_kind`, `edge_case_tag`, and `notes` fields per the schema in tech spec §4.1

**Given** the edge-case coverage checklist in tech spec §4.2
**When** the golden set is reviewed
**Then** every listed edge case category is represented by the minimum number of examples specified (self-transfers ≥ 3, deposit top-up ≥ 3, P2P ≥ 3, salary ≥ 2, refunds ≥ 2, standard spending ≥ 10, MCC 4829 ambiguous ≥ 5, large outliers ≥ 3, mojibake ≥ 2, non-UAH currency ≥ 2)

**Given** the pytest harness at `backend/tests/agents/categorization/test_golden_set.py`
**When** it runs against the current categorization pipeline
**Then** it computes per-axis accuracy (category, kind, joint), writes a JSON run report to `runs/<timestamp>.json`, and asserts `kind_accuracy >= 0.90 AND category_accuracy >= 0.90` — failing either fails CI

**Given** the harness is run immediately after Story 11.1 lands (before Story 11.3)
**When** it executes against the *pre-change* pipeline
**Then** it produces the **baseline** accuracy report that Story 11.3 will be measured against; baseline numbers are captured in the Story 11.3 story file

**Given** the golden set fixture is checked into version control
**When** future pipeline changes are proposed
**Then** a run report diff (previous vs current) is part of the PR review artifact

### Story 11.2: `transaction_kind` Field + Expanded Category Taxonomy

As the **system**,
I want `transaction_kind` stored as a first-class field on every transaction, alongside an expanded category taxonomy,
So that downstream consumers (health score, spending breakdowns, pattern detection) can filter by cash-flow semantics without re-deriving them from ad-hoc rules.

**Acceptance Criteria:**

**Given** the Alembic migration for Epic 11
**When** it runs
**Then** the `transactions` table gains `transaction_kind VARCHAR(16) NOT NULL DEFAULT 'spending' CHECK (transaction_kind IN ('spending','income','savings','transfer'))` per tech spec §2.1

**Given** the categorization module at `backend/app/agents/categorization/mcc_mapping.py`
**When** `VALID_CATEGORIES` is updated
**Then** it includes `savings`, `transfers_p2p`, and `charity` in addition to the existing categories, per tech spec §2.2; MCC 8398 (Charitable and Social Service Organizations) is also added to `MCC_TO_CATEGORY` with value `"charity"`

**Given** a transaction is being persisted with a `(transaction_kind, category)` pair that violates the compatibility matrix in tech spec §2.3
**When** the repository layer validates it
**Then** it raises `ValueError("kind/category mismatch: …")` and the caller must either retry with a valid pair or fall back to `(category='uncategorized', kind=<by-sign>, confidence=0.0)`

**Given** the MCC-pass stage encounters MCC 4829 (Wire Transfer / Money Order)
**When** it runs
**Then** it emits `(category='uncategorized', kind=null, confidence=0.0)` to force the LLM pass to resolve the ambiguity — it does NOT default to `finance`

**Given** any other MCC with a deterministic mapping
**When** the MCC pass runs
**Then** it emits `(category=<mapped>, kind='spending', confidence=0.95)` — all MCC-classifiable merchant categories are consumption outflows

### Story 11.3: Enriched LLM Categorization Prompt (Kind + Category + MCC + Signed Amount)

As the **system**,
I want the LLM categorization prompt to receive signed amounts, MCC, and direction, and to emit both `category` and `transaction_kind` with confidence,
So that categorization accuracy on the golden set meets the 90% threshold for both axes without needing rule-based pre-passes.

**Depends on:** Story 11.1 (baseline measurement), Story 11.2 (schema + VALID_CATEGORIES).

**Acceptance Criteria:**

**Given** the batch prompt builder in `backend/app/agents/categorization/node.py`
**When** it constructs the prompt for a transaction batch
**Then** each transaction line includes: `id`, `description`, **signed amount in UAH** (negative for outflow, positive for inflow), **MCC code** when available, and **direction** (`debit`/`credit`) — per tech spec §3.3

**Given** the prompt template
**When** it is rendered
**Then** it includes the two-axis instruction block defining `transaction_kind` (spending/income/savings/transfer) with explicit rules (transfers_p2p is always spending, savings requires kind=savings, transfers requires kind=transfer) and 3–5 hand-authored few-shot examples covering self-transfer, deposit top-up, P2P to individual, salary inflow, and an ambiguous case

**Given** the LLM response parser
**When** it processes the JSON array response
**Then** it accepts `{"id", "category", "transaction_kind", "confidence"}` per row; missing `transaction_kind` falls back to sign-based default (`kind='spending'` for negative amounts, `kind='income'` for positive); invalid category → `category='other'`; kind/category mismatch → `category='uncategorized'`, `kind=<by-sign>`, `confidence=0.0`

**Given** the golden-set harness from Story 11.1
**When** it runs against this story's pipeline changes
**Then** both `category_accuracy` and `kind_accuracy` meet or exceed `0.90` — if either is below, Story 11.4 (pre-pass rules) is triggered; if both pass, Story 11.4 is deferred to tech-debt

**Given** the run report from the above harness execution
**When** the story is closed
**Then** baseline vs. post-change accuracy is recorded in the story file and linked in the Epic 11 retrospective

**Given** the enriched prompt is finalized
**When** the golden-set harness runs
**Then** it executes the batch against **both** Claude Haiku (current production model) **and** Claude Sonnet, and the run report records per-axis accuracy, median latency, and token cost for each — so the Haiku-vs-Sonnet choice is a measured decision, not a speculative one. Model swap (if any) remains out of scope for this story; decision and follow-up story are captured in the Epic 11 retrospective.

### Story 11.3a: Categorization Accuracy Follow-up — Prompt Disambiguation Rules + MCC Table Extensions

As the **system**,
I want targeted prompt disambiguation rules and a modest MCC-table extension driven by the Story 11.3 golden-set run report,
So that category_accuracy on the golden set clears the 0.90 gate without needing a full description-pattern pre-pass stage (Story 11.4).

**Depends on:** Story 11.3 (baseline + failure cluster analysis).

**Context:** Story 11.3 closed with `category_accuracy = 0.856` (13 misses) vs. the 0.90 gate. The Haiku-vs-Sonnet comparison is decided (Haiku wins on every dimension; see Story 11.3 retrospective). The 13 misses cluster into four teachable patterns, three of which are prompt-fixable and one of which is better addressed by extending the deterministic MCC table. This story is the minimum intervention to close the gap before committing to Story 11.4's full pre-pass rules engine.

**Acceptance Criteria:**

**Given** the batch prompt builder `_build_prompt`
**When** the prompt is constructed
**Then** it includes the three disambiguation rules from tech spec §3.3 verbatim (charity-jar, cash-action narration, FOP+merchant-MCC), appended after the base rules block, with ≥ 1 concrete few-shot example per rule

**Given** `backend/app/agents/categorization/mcc_mapping.py`
**When** the Epic 11 changes are applied
**Then** `MCC_TO_CATEGORY` includes `5200: "shopping"`, `8021: "healthcare"`, `6010: "atm_cash"`; MCCs `4816` and `6012` are explicitly commented as intentionally unmapped per tech spec §2.2

**Given** the golden-set fixture row `gs-074` (City24)
**When** the harness loads it
**Then** `expected_category = "atm_cash"` — relabeled from `finance` because MCC 6010 operator-mediated cash disbursement is functionally identical to ATM withdrawal

**Given** the golden-set harness re-run on Haiku with 11.3a changes
**When** the report is produced
**Then** `category_accuracy >= 0.90` AND `kind_accuracy >= 0.90`; if the gate passes, the `@pytest.mark.xfail` on the Haiku test is removed; the Sonnet test is NOT re-run (decision locked per Story 11.3 retrospective)

**Given** the harness outcome
**When** the story is closed
**Then** TD-042 is either closed (gate passed — move to `## Resolved` in `docs/tech-debt.md`; Story 11.4 stays `backlog` annotated as deferred) OR updated with the specific residual failure cluster (gate missed — Story 11.4 scope narrowed to just those patterns)

**Given** existing unit tests in `test_enriched_prompt.py`
**When** 11.3a lands
**Then** three new tests are added — one per disambiguation rule — asserting the relevant rule text appears in the prompt; all existing tests continue to pass

### Story 11.4: Description-Pattern Pre-Pass (Conditional)

As the **system**,
I want a deterministic description-pattern pre-pass for the transaction types the LLM demonstrably mis-classifies,
So that golden-set accuracy clears the 90% threshold without forever increasing LLM cost or reasoning load.

**This story is TRIGGERED** (TD-042 reopened 2026-04-21). Story 11.3a moved category accuracy toward the gate but post-fix harness runs are unstable at 0.878–0.900 (0.900 was at noise boundary on a 90-row fixture). Two residual failure patterns cannot be closed by prompt iteration alone:
  - **Cash-action narration + food/retail MCC** (gs-051, gs-055) — MCC pass routes these to `groceries` deterministically before the prompt can apply the cash-action disambiguation rule.
  - **Self-transfer with no personal name** (gs-001, gs-002) — description ("Переказ на картку" / "Transfer to card") has no signal distinguishing own-account from P2P; LLM defaults to `transfers_p2p`.

**Scope (narrowed to evidence-based patterns):**

**Acceptance Criteria:**

**Given** the ingestion pipeline stage order
**When** Story 11.4 lands
**Then** a new description-based pre-pass runs **BEFORE** the MCC pass (not between MCC and LLM). This is the architectural fix: cash-action descriptions must override MCC deterministic mapping. Pre-pass is a single function in `backend/app/agents/categorization/node.py` (or a new `pre_pass.py` module), invoked from `categorization_node` at the start of per-transaction classification.

**Given** Pre-pass Rule A — cash-action narration override
**When** a transaction's description matches the case-insensitive pattern `/\b(cash withdrawal|видача готівки|отримання готівки)\b/i` (UA + EN locale coverage)
**Then** the pre-pass emits `(category='atm_cash', kind='spending', confidence=0.95)` and the MCC + LLM stages are skipped for this transaction. Closes gs-051 and gs-055.

**Given** Prompt Rule 4 — self-transfer detection (LIVES IN THE PROMPT, not the pre-pass)
**When** `_build_prompt` is extended
**Then** the prompt includes a new disambiguation rule: "When MCC is 4829 AND the description contains only generic account/card/currency language ('Переказ на картку', 'Transfer to card', 'На гривневий рахунок', 'To USD account', 'З <color> картки', 'From <currency> account', 'Конвертація валют') AND the description does NOT contain a personal full name, a business marker (ФОП/FOP/LIQPAY/TOV/LLC), a fund/charity marker («...»), or a deposit/investment marker ('депозит', 'deposit', 'вклад', 'investment') → transfers/transfer. This is the default for MCC 4829 debits that survive the other rules — NOT transfers_p2p."

**Given** Prompt Rule 4 few-shots
**When** the prompt is rendered
**Then** at least three concrete few-shot examples are added: `"Переказ на картку"` → transfers/transfer, `"З Білої картки"` → transfers/transfer (inbound leg), `"Конвертація UAH → USD"` → transfers/transfer. Closes gs-001 and gs-002.

**Given** the golden-set relabels already committed (gs-016, gs-017: `other/income` → `transfers/transfer`)
**When** the harness runs post-11.4
**Then** the relabeled rows classify correctly under Prompt Rule 4 (both have "ФОП" or "UAH account" markers — self-transfer, not income). Do NOT revert the relabels.

**Given** PE-statement golden rows (gs-091 through gs-094) tagged `edge_case_tag = "pe_statement"`
**When** the harness runs
**Then** the test helper filters `pe_statement`-tagged rows from the main `category_accuracy` / `kind_accuracy` metric (these require Story 11.7 + TD-049 to classify correctly; they should not depress Story 11.4's measurement). A secondary metric `pe_statement_accuracy` may be emitted for tracking but does not gate the story.

**Given** the post-11.4 harness run on Haiku
**When** the gate is evaluated
**Then** both `category_accuracy ≥ 0.92` AND `kind_accuracy ≥ 0.92` on the 86 non-PE rows (90 total − 4 PE rows filtered). Margin above 0.90 is required to account for ±3-row noise on an 86-row fixture. If the gate is not cleared, residual failure patterns are enumerated in the Dev Agent Record and TD-042 updated; do NOT add rules for patterns that are not demonstrated failures.

**Given** rule discipline
**When** additional rules are considered during implementation
**Then** only rules for *demonstrated* failure patterns from the Story 11.3a harness report are added. No speculative rules. Rule count cap: Rule A (pre-pass, cash-action) + Rule 4 (prompt, self-transfer). Additional rules require an explicit failure-cluster reference in the story file.

**Given** TD-042 closure
**When** Story 11.4 reaches done
**Then** TD-042 is moved to `## Resolved` in `docs/tech-debt.md` with the stable-gate measurement recorded (the reopened-2026-04-21 entry, not the earlier resolve).

### Story 11.5: Post-Parse Validation Layer with Partial-Import Semantics

As a **user**,
I want invalid or suspect rows in my uploaded statement to be surfaced as warnings rather than silently imported as corrupt data,
So that I can trust that imported transactions are real and that anything unreliable is flagged for my review.

**Acceptance Criteria:**

**Given** any parser (monobank, privatbank, generic, or AI-schema-detected) returns rows
**When** the validation layer runs per tech spec §5.1
**Then** it applies the rules: date plausibility (`[today - 5y, today + 1d]`), amount presence (non-null, non-zero), amount type (numeric after cleanup), sign convention consistency, description-or-identifier presence, and duplicate-rate threshold (reject wholesale if > 20% identical)

**Given** individual row violations (date out of range, null amount, non-numeric amount, no identifying info)
**When** the validation layer encounters them
**Then** those rows are **rejected** (not persisted) with a `reason` tag; the rest of the upload proceeds

**Given** sign-convention violations on individual rows
**When** the validation layer encounters them
**Then** the row is **flagged with a warning but still persisted** (sign is less likely to be catastrophically wrong than missing amounts)

**Given** the suspicious-duplicate-rate threshold is exceeded
**When** the validation layer runs
**Then** the parser's output is **rejected wholesale** — no rows persisted — and the upload returns a structured error requesting the user re-export or contact support

**Given** a completed (or partially-completed) upload
**When** the ingestion API responds
**Then** the response matches tech spec §5.2: `{upload_id, imported_transaction_count, rejected_rows: [{row_number, reason, raw_row}], warnings: [{row_number, reason}], mojibake_detected, schema_detection_source}`

**Given** the upload completion UI (existing Story 2.8 component)
**When** the response contains `rejected_rows` or `warnings`
**Then** the UI displays a "couldn't process N rows" expandable section listing the row numbers and reasons — the user can continue to the Teaching Feed regardless

### Story 11.6: Encoding Detection with Mojibake Flagging

As a **user uploading a statement with unusual encoding**,
I want the pipeline to auto-detect the file encoding and surface a warning if descriptions look corrupted,
So that merchant names used for categorization aren't silently reduced to garbage strings.

**Acceptance Criteria:**

**Given** a raw uploaded file
**When** ingestion begins
**Then** `charset-normalizer` is invoked on the bytes to detect encoding; the detected encoding and chaos score are logged per tech spec §7

**Given** decoding produces more than 5% U+FFFD replacement characters across transaction description fields
**When** the partial-import response is constructed
**Then** `mojibake_detected: true` is set in the response and the upload is tagged in observability for alerting

**Given** decoding fails under the detected encoding
**When** the pipeline runs
**Then** it falls back to UTF-8 with `errors="replace"` rather than raising an unhandled exception; the upload proceeds with `mojibake_detected: true` flagged

**Given** the detected encoding is UTF-8 with high confidence
**When** ingestion runs
**Then** no warning is emitted and no observability flag is set (happy-path behavior unchanged)

### Story 11.7: AI-Assisted Schema Detection + `bank_format_registry`

As a **user uploading a statement from a bank the system has never seen**,
I want the upload to work without a developer writing a new parser,
So that I can use the product with statements from any reasonable bank export format.

**Acceptance Criteria:**

**Given** an upload arrives with a header row the system hasn't seen before
**When** the ingestion flow runs
**Then** the header row is normalized (NFKC, lowercase, whitespace-collapsed), a SHA-256 fingerprint is computed (tech spec §6.1), and `bank_format_registry` is queried for a matching row

**Given** a fingerprint miss
**When** the AI schema-detection path runs
**Then** the LLM is called with the header row and up to 5 sample data rows; it returns the JSON mapping defined in tech spec §2.4 plus a `confidence` and `bank_hint`; the result is persisted as a new `bank_format_registry` row

**Given** a fingerprint hit with only `detected_mapping` (no override)
**When** the ingestion flow runs
**Then** `detected_mapping` is used to parse; `use_count` is incremented and `last_used_at` updated; no LLM call occurs

**Given** a fingerprint hit with `override_mapping` populated by an operator
**When** the ingestion flow runs
**Then** `override_mapping` takes precedence over `detected_mapping`; no LLM call occurs

**Given** a detected schema produces a partial-import with > 30% of rows rejected by the validation layer
**When** the result is evaluated
**Then** the detection is logged as suspect (`parser.schema_detection` event with a suspect flag), the partial import still proceeds, and the row remains in `bank_format_registry` with its original `detection_confidence` — operator review is needed but not automatic

**Given** known-bank parsers (Monobank, PrivatBank) in `backend/app/agents/ingestion/parsers/`
**When** their fingerprint matches the statement header
**Then** they continue to run as the happy path — no LLM call and no registry interaction for known formats unless the parser fails validation (in which case the AI path is the fallback)

**Given** the AI schema-detection path fails (LLM unreachable, invalid JSON response)
**When** this occurs
**Then** the pipeline falls back to `generic.py`; a `parser.schema_detection` event logs the fallback; validation layer applies normally to the generic parser's output

### Story 11.8: Low-Confidence Categorization Review Queue

As a **user**,
I want transactions the system wasn't confident about categorizing to surface in a review queue,
So that I can correct them and the pipeline stops silently marking them as "uncategorized."

**Acceptance Criteria:**

**Given** a transaction's categorization confidence is below `0.6`
**When** categorization completes
**Then** a `uncategorized_review_queue` row is inserted (per tech spec §2.5) with `suggested_category`, `suggested_kind`, `status='pending'`; the transaction itself is persisted with `category='uncategorized'`

**Given** a transaction's categorization confidence is between `0.6` and `0.85`
**When** categorization completes
**Then** the transaction is auto-applied with its LLM-suggested category/kind, and a soft-flag event is logged (`categorization.confidence_tier` with `tier=soft-flag`); no review queue entry is created

**Given** a transaction's categorization confidence is `0.85` or above
**When** categorization completes
**Then** the transaction is auto-applied silently (no review queue, no soft-flag log)

**Given** the review queue API
**When** a client calls `GET /api/v1/transactions/review-queue?status=pending`
**Then** it returns a paginated list of queue entries with transaction context (description, amount, date), `suggested_category`, `suggested_kind`, and `categorization_confidence`

**Given** a user resolves a queue entry via `POST /api/v1/transactions/review-queue/{id}/resolve` with `{category, kind}`
**When** the API validates the payload
**Then** the `(kind, category)` pair is checked against the compatibility matrix (tech spec §2.3); invalid pairs return 400; valid pairs update the underlying transaction and set `status='resolved'`

**Given** a user dismisses a queue entry via `POST /api/v1/transactions/review-queue/{id}/dismiss`
**When** the API runs
**Then** the entry's `status` becomes `dismissed`, the transaction remains as `uncategorized`, and it no longer appears in `status=pending` listings

**Given** the account settings page
**When** the user views it and there are pending queue entries
**Then** a "Review uncategorized transactions (N)" link is shown; clicking it opens `/settings/review-queue` which lists entries with resolve/dismiss actions per tech spec §8.2

### Story 11.9: Observability Signals for Ingestion & Categorization

As an **operator**,
I want dashboards and alerts for the categorization confidence distribution, schema-detection outcomes, validation rejection rate, and mojibake rate,
So that silent degradation of the ingestion pipeline is detected before users complain.

**Acceptance Criteria:**

**Given** the structured log events defined in tech spec §9
**When** the ingestion and categorization pipelines run
**Then** `categorization.confidence_tier`, `categorization.kind_mismatch`, `parser.schema_detection`, `parser.validation_rejected`, and `parser.mojibake_detected` are emitted with the fields specified (correlation IDs already present per Story 6.4)

**Given** the operator dashboard (existing Grafana deployment per Story 6.5)
**When** new panels are added
**Then** it displays: categorization confidence distribution (histogram), golden-set accuracy trend (last-run value + history), unknown-format detection rate + cache hit rate, validation rejection rate by reason, mojibake rate per upload

**Given** alert rules are configured
**When** thresholds are breached
**Then** the following trigger operator notifications: categorization confidence **median < 0.7 over 24h** (warning), validation rejection rate **> 15% of rows over 24h** (warning); AI-schema-detection fallback to `generic.py` is **info-only, no page**

**Given** the operator runbook (docs/operator-runbook.md)
**When** Story 11.9 lands
**Then** it includes a new section covering: how to read the confidence distribution panel, how to inspect `bank_format_registry` rows and apply `override_mapping`, how to triage a high validation-rejection alert

### Out of Scope for Epic 11

- **Backfill of historical transactions** — greenfield; not needed
- **Operator UI for bank_format_registry overrides** — DB-only for now; full UI deferred to a future story
- **Split transactions** (one transaction → multiple kind events) — revisit only when product need emerges
- **Multi-leg transfer matching** (pairing outbound and inbound legs of the same self-transfer) — an insight-layer concern, not categorization
- **Deletion of `generic.py`** — sunset criteria defined in tech spec, execution is a future story after ≥ 2 quarters of clean AI-detection metrics

---

## Backlog — Post-MVP Enhancement Ideas

### Enhanced Financial Literacy Level Assessment

**Context:** Currently FR17 uses heuristic-based detection of financial literacy level. This is simplistic and may not accurately reflect the user's actual knowledge.

**Proposed improvement:** Replace or supplement the heuristic with either:
1. A short onboarding quiz that assesses the user's financial literacy level
2. Manual level selection by the user (beginner / intermediate / advanced)

**Impact:** More accurate literacy level → better-calibrated education depth in Teaching Feed cards.

**Related:** FR17, Epic 3 (Teaching Feed)

### Periodic Knowledge Quizzes (Learning Reinforcement)

**Context:** The Teaching Feed delivers financial education, but there's no mechanism to reinforce what the user has learned over time.

**Proposed feature:** Periodic quizzes based on previously consumed Teaching Feed content:
- Short daily check-ups (2-3 questions) to reinforce recently learned concepts
- Questions generated from the user's actual Teaching Feed history
- Especially valuable on mobile where push notifications can drive daily engagement

**Impact:** Improved knowledge retention, higher daily engagement/return rate, and a measurable signal of learning progress.

**Related:** Teaching Feed (Epic 3), Mobile native app (Phase 3), Gamification
