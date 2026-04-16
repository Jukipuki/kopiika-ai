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
