---
stepsCompleted:
  - 1
  - 2
  - 3
  - 4
  - 5
  - 6
  - 7
  - 8
workflowType: 'architecture'
lastStep: 8
status: 'complete'
completedAt: '2026-03-16'
lastEdited: '2026-04-05'
editHistory:
  - date: '2026-04-05'
    changes: 'Integrated User Feedback System architecture (4-layer design from design-thinking session). Added feedback data model (card_feedback, feedback_responses, card_interactions extensions), feedback API endpoints, frontend/backend components, updated structure and mapping for FR45-FR55. Addressed compliance audit trail warning.'
    inputDocuments:
      - design-thinking-2026-04-05.md
      - validation-report-2026-04-05.md
inputDocuments:
  - product-brief-kopiika-ai-2026-03-15.md
  - prd.md
  - ux-design-specification.md
  - market-smart-financial-intelligence-research-2026-03-15.md
  - rag-vs-finetuning-ukrainian-financial-research-2026-03-15.md
  - vector-store-options-financial-rag-research-2026-03-15.md
  - monobank-csv-ukrainian-bank-parsing-research-2026-03-15.md
  - integration-patterns-rag-multi-agent-pipeline-research-2026-03-15.md
  - api-design-data-format-integration-research-2026-03-15.md
  - technical-ai-financial-data-pipeline-research-2026-03-15.md
  - design-thinking-2026-04-05.md
  - validation-report-2026-04-05.md
documentCounts:
  briefs: 1
  prd: 1
  uxDesign: 1
  research: 7
  designThinking: 1
  validationReports: 1
  projectDocs: 0
  projectContext: 0
workflowType: 'architecture'
project_name: 'kopiika-ai'
user_name: 'Oleh'
date: '2026-03-16'
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements:**

The PRD defines 11 core V1 features organized into four architectural domains:

1. **Data Ingestion Domain** — Statement upload & parsing (CSV/PDF), Monobank format primary, flexible parser architecture for other banks. Auto-detect bank format where possible.

2. **AI Processing Domain** — 5-agent sequential pipeline via LangGraph:
   - Ingestion Agent: Parse uploaded statements, extract/structure transactions
   - Categorization Agent: AI-powered classification with user correction learning
   - Pattern Detection Agent: Trends, anomalies, recurring charges, subscription detection, month-over-month comparisons
   - Triage Agent: Severity-ranked prioritization by financial impact
   - Education Agent: RAG-powered plain-language explanations personalized to user data and literacy level

3. **User-Facing Domain** — Teaching Feed (card-based insight UI with triage severity + progressive disclosure education), Cumulative Financial Profile with Financial Health Score (0-100), subscription detection display, basic predictive forecasts, pre-built data queries, email notifications

4. **Business Domain** — User authentication & data persistence, freemium model (free: top 3 insights + basic education; premium: 99-149 UAH/month for full features), bilingual support (Ukrainian + English)

**Non-Functional Requirements:**

| NFR | Requirement | Architectural Impact |
|---|---|---|
| **Security** | AES-256 at rest, TLS 1.3 in transit, tenant isolation, GDPR-aligned | Encryption layer, RLS in PostgreSQL, audit logging infrastructure |
| **Privacy** | One-click data deletion (including embeddings), consent management | Cascading delete across all data stores, consent tracking system |
| **Performance** | >80% first-upload completion rate, 5-15 min session sweet spot | Async pipeline with SSE progress, fast initial parsing feedback |
| **Bilingual** | Ukrainian + English UI, AI insights, and education content | i18n framework, cross-lingual RAG embeddings, locale-aware formatting |
| **Reliability** | Pipeline must handle failures gracefully per-agent | LangGraph checkpointing, retry logic, partial result delivery |
| **Scalability** | Support growing user base month-over-month (Phase 2 target) | Async job queue, stateless API, database connection pooling |
| **Compliance** | Ukrainian Data Protection Law, bank secrecy, AI explainability | Audit trails, data processing records, explainable AI outputs |
| **Data Integrity** | Financial data accuracy is critical — no data loss or corruption | ACID transactions, raw data preservation, idempotent processing |

**Scale & Complexity:**

- Primary domain: Full-stack AI web application
- Complexity level: **High** — multi-agent AI pipeline, RAG system, bilingual support, financial data security, freemium model, cumulative intelligence
- Estimated architectural components: ~12-15 major components (frontend app, API layer, auth service, file processing, 5 AI agents, RAG/vector store, job queue, notification service, payment integration, database layer)

### Technical Constraints & Dependencies

| Constraint | Detail | Impact |
|---|---|---|
| **Monobank CSV format** | Windows-1251 encoding, semicolon delimiter, comma decimals, possible embedded newlines | Robust parser with encoding detection, format normalization |
| **Monobank API rate limit** | 1 request per 60 seconds, max 31 days per request, 500 tx per response | Background queue with enforced delays for historical sync |
| **No Stripe in Ukraine** | Must use Fondy (domestic) or LemonSqueezy (international) for payments | Dual payment gateway integration, more complex subscription management |
| **Ukrainian as low-resource language** | Limited fine-tuning data for Ukrainian financial domain | RAG-first approach using multilingual embeddings (OpenAI text-embedding-3-small), defer fine-tuning |
| **LLM API dependency** | Core pipeline depends on external LLM APIs (Claude/GPT) | Error handling, fallback strategies, cost management, rate limiting |
| **Greenfield project** | No existing codebase or infrastructure | Freedom in technology choices, but all infrastructure must be provisioned |

### Cross-Cutting Concerns Identified

1. **Authentication & Authorization** — Spans every API endpoint, file upload, AI pipeline access, and payment flows. JWT + RBAC with strict user-scoped data access.

2. **Bilingual Internationalization** — Affects UI strings, AI-generated content, RAG knowledge base, date/currency formatting (dd.MM.yyyy, comma decimals, UAH kopiykas), and error messages.

3. **Async Job Management** — File processing, AI pipeline execution, email notifications, and Monobank API sync all require background job infrastructure with progress tracking.

4. **Error Handling & Resilience** — 5 sequential AI agents means 5 potential failure points. Each must handle failures gracefully with checkpointing and partial result strategies.

5. **Audit Logging** — Financial data processing requires comprehensive audit trails across ingestion, AI processing, user actions, and data access for compliance.

6. **Freemium Tier Gating** — Feature access controls must be enforced consistently across API endpoints, AI pipeline depth, and UI display.

7. **Data Encryption & Privacy** — Encryption at rest and in transit, with cascading deletion capability across transactions, derived insights, embeddings, and user profiles.

8. **Observability** — Pipeline processing metrics, LLM API latency/cost tracking, error rates, and user engagement metrics needed from day one for a data-driven product.

9. **Compliance Audit Trail** — Financial data access events must be logged with user ID, timestamp, action type, and resource accessed. Distinct from operational logging — serves GDPR accountability and potential regulatory audit requirements. Implemented via middleware-level logging on all data access endpoints (transactions, insights, profile, feedback), stored in structured audit log format.

## Starter Template Evaluation

### Primary Technology Domain

**Dual-stack full-stack AI web application:**
- Frontend: Next.js 16.1 (TypeScript) — latest stable, Turbopack default bundler
- Backend: FastAPI (Python) — with LangGraph, Celery, pgvector
- Monorepo: Simple folder-based structure (no Turborepo/Nx — they can't orchestrate Python)
- Auth: AWS Cognito (JWT validation on both sides)
- Deployment: AWS-first

### Starter Options Considered

**Frontend Starters:**

| Option | Verdict | Rationale |
|---|---|---|
| **`create-next-app`** (official) | **Selected** | Next.js 16.1 defaults: TypeScript, Tailwind CSS, ESLint, App Router, Turbopack. Clean, minimal, well-maintained |
| T3 Stack (`create-t3-app`) | Rejected | Bundles tRPC + Prisma — we need REST/GraphQL to FastAPI, not tRPC. Prisma is JS-only, our DB is Python-side |
| Vercel AI SDK template | Considered | Good AI streaming support, but too opinionated about backend — we have our own FastAPI |

**Backend Starters:**

| Option | Verdict | Rationale |
|---|---|---|
| **Custom FastAPI structure** | **Selected** | No existing template includes LangGraph + Celery + pgvector + Cognito. Better to scaffold a clean structure than fight a template |
| `full-stack-fastapi-template` (official) | Rejected | Bundles React frontend (we use Next.js), Docker-first (we want simple initially), and its auth is self-built JWT (we want Cognito) |
| `fastapi-alembic-sqlmodel-async` | Reference | Good patterns for SQLModel + Alembic async — we'll borrow patterns but not use as-is |

**Monorepo Approach:**

| Option | Verdict | Rationale |
|---|---|---|
| **Simple folder-based monorepo** | **Selected** | `frontend/` + `backend/` in one repo. Each has its own tooling. Simple, no overhead |
| Turborepo | Rejected | JS/TS only — cannot orchestrate Python builds, linting, or testing. Adds complexity without value for our dual-language setup |
| Nx | Rejected | Can support Python via plugins, but over-engineered for a project with 2 apps and no shared JS packages |

### Selected Approach: Folder-Based Monorepo with Separate Starters

**Rationale:** The project's dual-language nature (TypeScript + Python) means no single starter covers both sides. A simple monorepo with `create-next-app` for frontend and a custom FastAPI scaffold for backend gives us clean foundations without fighting against template opinions.

**Monorepo Structure:**

```
kopiika-ai/
├── frontend/                  # Next.js 16.1 (TypeScript)
│   ├── src/
│   │   ├── app/              # App Router pages
│   │   ├── components/       # React components
│   │   ├── lib/              # Utilities, API client
│   │   └── i18n/             # Ukrainian/English translations
│   ├── public/
│   ├── next.config.ts
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   └── package.json
│
├── backend/                   # FastAPI (Python)
│   ├── app/
│   │   ├── api/              # Route handlers
│   │   ├── agents/           # LangGraph agent definitions
│   │   │   ├── ingestion/
│   │   │   ├── categorization/
│   │   │   ├── pattern_detection/
│   │   │   ├── triage/
│   │   │   └── education/
│   │   ├── core/             # Config, security, deps
│   │   ├── models/           # SQLModel data models
│   │   ├── services/         # Business logic
│   │   ├── tasks/            # Celery task definitions
│   │   └── rag/              # RAG pipeline, embeddings
│   ├── alembic/              # Database migrations
│   ├── tests/
│   ├── pyproject.toml
│   └── alembic.ini
│
├── shared/                    # OpenAPI-generated types (optional)
│   └── api-client/           # Auto-generated TS client from FastAPI OpenAPI spec
│
├── .github/                   # GitHub Actions CI/CD
├── docker-compose.yml         # Local dev: PostgreSQL + Redis
└── README.md
```

**Initialization Commands:**

```bash
# Frontend: Next.js 16.1 with defaults
npx create-next-app@latest frontend --typescript --tailwind --eslint --app --turbopack

# Backend: Python project with uv (modern Python package manager)
mkdir -p backend && cd backend
uv init --python 3.12
# Then add dependencies: fastapi, uvicorn, sqlmodel, alembic, celery, redis,
# langchain, langgraph, pgvector, boto3 (for Cognito)
```

### Architectural Decisions Provided by Starters

**Frontend (create-next-app):**

| Decision | Value |
|---|---|
| Language & Runtime | TypeScript 5.x, Node.js |
| Framework | Next.js 16.1 with App Router |
| Bundler | Turbopack (default in v16) |
| Styling | Tailwind CSS 4.x |
| Linting | ESLint with Next.js config |
| Routing | File-based App Router |
| Rendering | Server Components by default, with "use cache" directives |

**Backend (Custom FastAPI scaffold):**

| Decision | Value |
|---|---|
| Language & Runtime | Python 3.12 |
| Framework | FastAPI with Uvicorn |
| ORM | SQLModel (SQLAlchemy + Pydantic) |
| Migrations | Alembic |
| Task Queue | Celery + Redis |
| AI Pipeline | LangGraph |
| Vector Store | pgvector (via SQLModel/SQLAlchemy) |
| Package Manager | uv |
| Auth | AWS Cognito JWT validation (fastapi-cloudauth or manual) |

**Cross-Stack Integration:**

| Decision | Value |
|---|---|
| API Contract | FastAPI auto-generates OpenAPI spec; frontend consumes via generated TypeScript client (@hey-api/openapi-ts) |
| Auth Flow | Cognito User Pool -> NextAuth.js (frontend) -> JWT validation (backend) |
| Streaming | SSE from FastAPI -> Vercel AI SDK hooks (frontend) |
| Local Dev | docker-compose for PostgreSQL + Redis; frontend and backend run separately |

**Note:** Project initialization using these commands should be the first implementation story.

## Core Architectural Decisions

### Decision Priority Analysis

**Critical Decisions (Block Implementation):**
- Data architecture (PostgreSQL + pgvector, SQLModel, raw data preservation)
- Authentication (AWS Cognito, custom UI, JWT validation)
- API pattern (REST-only for MVP)
- AI pipeline orchestration (LangGraph sequential with Celery workers)

**Important Decisions (Shape Architecture):**
- Frontend state management (TanStack Query + React Context)
- Component library (shadcn/ui)
- i18n approach (next-intl)
- Caching strategy (Redis multi-purpose)
- AWS compute architecture

**Deferred Decisions (Post-MVP):**
- GraphQL (evaluate if REST becomes limiting for Teaching Feed queries)
- CDN/edge caching for AI-generated insights
- Advanced monitoring/APM tooling
- Multi-region deployment

### Data Architecture

| Decision | Choice | Version | Rationale |
|---|---|---|---|
| **Primary Database** | PostgreSQL + pgvector | PostgreSQL 16.x, pgvector 0.8.x | ACID compliance for financial data, pgvector for RAG embeddings in same DB, RLS for tenant isolation |
| **ORM** | SQLModel | Latest (SQLAlchemy 2.x + Pydantic v2) | Type-safe models shared between API validation and DB, async support, native FastAPI integration |
| **Migrations** | Alembic | Latest | Standard for SQLAlchemy/SQLModel, supports auto-generation from model changes |
| **Caching** | Redis (multi-purpose) | Redis 7.x | Already required for Celery broker; also used for API response caching, job status tracking, and SSE progress. Write-once AI insights cached aggressively |
| **Raw Data Preservation** | Dual storage: raw JSONB + normalized model | — | Raw Monobank data stored untouched in JSONB for audit/compliance. Normalized into structured transaction model for AI pipeline processing |
| **File Storage** | Amazon S3 | — | Uploaded CSV/PDF files stored in S3 with per-user prefix. Processed then referenced by job ID |
| **Vector Embeddings** | pgvector with OpenAI text-embedding-3-small (1536 dimensions) | text-embedding-3-small | Bilingual Ukrainian/English embeddings in same vector space. HNSW index for fast ANN search. Co-located with relational data for single-query joins |

**Feedback Data Model (FR45-FR55):**

The feedback system uses a layered data approach matching the 4-layer feedback design. Layers 0-1 are MVP, Layer 2 is Phase 1.5, Layer 3 is Phase 2.

**Layer 0 — Implicit Signal Extensions (extend existing `card_interactions` table):**

| Column | Type | Purpose |
|---|---|---|
| `time_on_card_ms` | `integer` | Milliseconds card was visible/focused |
| `education_expanded` | `boolean` | Whether user expanded education layer |
| `education_depth_reached` | `smallint` | Deepest education level opened (0-3) |
| `swipe_direction` | `varchar(10)` | Direction of swipe gesture (left/right/up) |
| `card_position_in_feed` | `smallint` | Card's position in the feed at time of interaction |
| `engagement_score` | `smallint` | Aggregated score 0-100, computed from weighted formula on write |

**Layer 1 — Explicit Card Feedback (`card_feedback` table):**

| Column | Type | Constraints | Purpose |
|---|---|---|---|
| `id` | `UUID` | PK, default `gen_random_uuid()` | Primary key |
| `user_id` | `UUID` | FK → `users.id`, NOT NULL | User who gave feedback |
| `card_id` | `UUID` | FK → `insights.id`, NOT NULL | Card that was rated |
| `card_type` | `varchar(50)` | NOT NULL | Insight card type (spendingInsight, subscriptionAlert, etc.) |
| `vote` | `varchar(10)` | CHECK IN ('up', 'down'), nullable | Thumbs up or down (null if only issue report) |
| `reason_chip` | `varchar(50)` | nullable | Selected reason from follow-up panel (Layer 2) |
| `free_text` | `text` | nullable, max 500 chars | Optional free-text feedback |
| `feedback_source` | `varchar(20)` | NOT NULL, default 'card_vote' | 'card_vote' or 'issue_report' |
| `issue_category` | `varchar(30)` | nullable | For issue reports: 'bug', 'incorrect_info', 'confusing', 'other' |
| `created_at` | `timestamptz` | NOT NULL, default now() | When feedback was submitted |

Indexes: `idx_card_feedback_user_id`, `idx_card_feedback_card_id`, `idx_card_feedback_card_type_vote` (for aggregation queries).
Unique constraint: `uq_card_feedback_user_card_vote` on `(user_id, card_id, feedback_source)` — one vote and one issue report per user per card.

**Layer 3 — Milestone Feedback Responses (`feedback_responses` table):**

| Column | Type | Constraints | Purpose |
|---|---|---|---|
| `id` | `UUID` | PK, default `gen_random_uuid()` | Primary key |
| `user_id` | `UUID` | FK → `users.id`, NOT NULL | User who responded |
| `feedback_card_type` | `varchar(50)` | NOT NULL | 'milestone_3rd_upload', 'health_score_change', 'quarterly_nps' |
| `response_value` | `varchar(50)` | NOT NULL | Emoji face, yes/no, or NPS 1-10 score |
| `free_text` | `text` | nullable, max 500 chars | Optional elaboration |
| `created_at` | `timestamptz` | NOT NULL, default now() | When response was submitted |

Index: `idx_feedback_responses_user_id`.
Unique constraint: `uq_feedback_responses_user_type` on `(user_id, feedback_card_type)` — milestone cards never repeat.

**Feedback Frequency Caps (enforced in application layer, tracked in `user_preferences` or Redis):**
- Max 1 feedback card per session
- Max 1 feedback card per month
- Milestone cards: dismissed = never shown again (tracked via `feedback_responses` existence)

**RAG Corpus Auto-Flagging (operational, Layer 1 data):**
- Aggregate thumbs-down rate per topic cluster (derived from `card_type` + categorization tags)
- Auto-flag when: >30% thumbs-down AND minimum 10 votes on cluster
- Stored as a materialized view or periodic batch query — no real-time requirement

**Privacy & Deletion (FR49):**
- `card_feedback` and `feedback_responses` rows are included in cascading delete on user account deletion (FK cascade)
- Feedback data included in user data export (FR35)
- Free-text feedback visible to user in "view my stored data" flow

**Affects:** All backend components, AI pipeline, RAG system, feedback service

### Authentication & Security

| Decision | Choice | Version | Rationale |
|---|---|---|---|
| **Identity Provider** | AWS Cognito User Pools | — | AWS-native, managed user lifecycle, supports email/password + social login. JWT issuance built-in |
| **Frontend Auth** | Custom UI + Cognito API (via NextAuth.js CognitoProvider) | NextAuth.js latest | Full design control over onboarding experience. Seamless Teaching Feed first impression. NextAuth handles token management |
| **Backend Auth** | JWT validation middleware | fastapi-cloudauth or manual boto3 | Every FastAPI endpoint validates Cognito JWT. Extracts user_id for data scoping |
| **Authorization** | RBAC + PostgreSQL RLS | — | User role (free/premium) checked via FastAPI dependency. RLS as defense-in-depth — users can only query their own rows |
| **Data Encryption** | AES-256 at rest, TLS 1.3 in transit | — | Every storage layer (RDS, S3, ElastiCache, Secrets Manager, ECR) encrypted with AWS-managed KMS keys. See **Encryption at Rest** section below for the full compliance table and operator runbook |
| **API Security** | CORS whitelist, rate limiting, input validation | — | CORS restricted to frontend domain. Rate limiting via Redis token bucket. Pydantic validation on all inputs |

**Auth Flow:**
```
User -> Next.js (Custom Login UI) -> Cognito User Pool -> JWT issued
     -> Next.js stores JWT (NextAuth.js session)
     -> API requests include JWT in Authorization header
     -> FastAPI middleware validates JWT, extracts user_id
     -> PostgreSQL RLS enforces row-level access
```

**Affects:** Every API endpoint, file upload, AI pipeline access, payment flows

### Encryption at Rest

_Compliance reference for Epic 5 (Data Privacy, Trust & Consent). Added by Story 5.1._

Every storage layer that holds financial data, secrets, or container images is encrypted at rest with an AWS-managed KMS CMK (`aws/<service>`). Customer-managed keys are **intentionally not used** — AWS-managed keys rotate yearly automatically, require no key policy maintenance, and add no per-key cost. Revisit this decision if a compliance auditor ever requires customer control of the key material.

**Compliance table:**

| Layer | Resource | Encrypted | Key | Terraform location |
|---|---|---|---|---|
| Primary database | `aws_db_instance.main` (PostgreSQL 16) | ✅ AES-256 | `aws/rds` | [modules/rds/main.tf:52](../../infra/terraform/modules/rds/main.tf#L52) `storage_encrypted = true` |
| RDS automated backups & snapshots | RDS backup subsystem | ✅ AES-256 (inherited) | `aws/rds` | Inherited from parent instance — no explicit config needed |
| Financial data (transactions, profile, health score history, pgvector embeddings) | Stored inside PostgreSQL | ✅ AES-256 (transparent) | `aws/rds` | Same as primary database — no application-level encryption |
| S3 uploads bucket | `aws_s3_bucket.uploads` | ✅ SSE-S3 AES-256 + S3 Bucket Keys | `aws/s3` | [modules/s3/main.tf:13-22](../../infra/terraform/modules/s3/main.tf#L13-L22) |
| S3 bucket policy | `aws_s3_bucket_policy.uploads` | ✅ denies non-AES256 PutObject + insecure transport | n/a | [modules/s3/main.tf](../../infra/terraform/modules/s3/main.tf) `DenyNonAES256Encryption` / `DenyInsecureTransport` |
| ElastiCache Redis (Celery broker, SSE, cached responses) | `aws_elasticache_replication_group.main` | ✅ AES-256 at rest + TLS in transit | `aws/elasticache` | [modules/elasticache/main.tf](../../infra/terraform/modules/elasticache/main.tf) `at_rest_encryption_enabled = true` |
| Secrets Manager (database, redis, cognito, s3, ses, llm-api-keys) | `aws_secretsmanager_secret.*` | ✅ AES-256 | `aws/secretsmanager` (default) | [modules/secrets/main.tf](../../infra/terraform/modules/secrets/main.tf) — no explicit `kms_key_id`, relies on default |
| ECR backend image repo | `aws_ecr_repository.backend` | ✅ AES-256 | `aws/ecr` | [main.tf:95-97](../../infra/terraform/main.tf#L95-L97) `encryption_type = "AES256"` |

**Why `aws_elasticache_replication_group` instead of `aws_elasticache_cluster`:** `at_rest_encryption_enabled` is only available on the replication-group resource in the AWS Terraform provider. The cluster is still single-node (`num_cache_clusters = 1`, no failover, no multi-AZ) — semantically identical to the prior `aws_elasticache_cluster` but now supports at-rest encryption.

**Static-analysis guardrail:** [`.github/workflows/tfsec.yml`](../../.github/workflows/tfsec.yml) runs [tfsec](https://aquasecurity.github.io/tfsec) on every PR touching `infra/**`. Waivers (with rationale) live in [`infra/terraform/.tfsec/config.yml`](../../infra/terraform/.tfsec/config.yml). This prevents regressions to the encryption posture above.

**Operator runbook — on-demand verification:**

```bash
# RDS instance storage encryption
aws rds describe-db-instances \
  --query 'DBInstances[?DBInstanceIdentifier==`kopiika-ai-dev-rds`].{id:DBInstanceIdentifier,enc:StorageEncrypted,key:KmsKeyId}'

# RDS automated snapshots inherit encryption
aws rds describe-db-snapshots \
  --db-instance-identifier kopiika-ai-dev-rds \
  --query 'DBSnapshots[].{id:DBSnapshotIdentifier,enc:Encrypted}'

# S3 default bucket encryption
aws s3api get-bucket-encryption --bucket kopiika-ai-uploads-dev

# S3 bucket policy (should contain DenyNonAES256Encryption + DenyInsecureTransport)
aws s3api get-bucket-policy --bucket kopiika-ai-uploads-dev --query Policy --output text | jq .

# ElastiCache at-rest + in-transit encryption
aws elasticache describe-replication-groups \
  --replication-group-id kopiika-ai-dev-redis \
  --query 'ReplicationGroups[].{id:ReplicationGroupId,rest:AtRestEncryptionEnabled,transit:TransitEncryptionEnabled}'

# Secrets Manager (any one secret — all six use the same default key)
aws secretsmanager describe-secret --secret-id kopiika-ai/dev/database --query KmsKeyId

# ECR repository encryption
aws ecr describe-repositories --repository-names kopiika-ai-backend \
  --query 'repositories[].{name:repositoryName,enc:encryptionConfiguration}'
```

**Key rotation:** All keys above are AWS-managed, which rotate automatically on a yearly cadence. No operator action required. If a compliance review later demands customer-managed keys, create per-service `aws_kms_key` resources and reference them via `kms_key_id` in the consuming resources — no application code changes needed.

**Related Epic 5 stories:** 5.2 (consent UI), 5.3 (financial-advice disclaimer), 5.4 (view-my-stored-data), 5.5 (delete-all-my-data). This story establishes the ground truth that later stories rely on when explaining data handling to users.

### Consent Management

_Compliance reference for Epic 5 (Data Privacy, Trust & Consent). Added by Story 5.2._

Authenticated users cannot reach any dashboard route until they have granted the current privacy-explanation consent. The system is built around one append-only table, a version-gated re-consent mechanism, and a client-side guard that redirects non-consented sessions into a dedicated onboarding screen.

**Storage — `user_consents` table** ([migration a7b9c1d2e3f4](../../backend/alembic/versions/a7b9c1d2e3f4_create_user_consents_table.py), [model](../../backend/app/models/consent.py)):

| Column | Type | Notes |
|---|---|---|
| `id` | UUID (PK) | `gen_random_uuid()` default |
| `user_id` | UUID (FK → `users.id`, `ON DELETE CASCADE`) | Cascade is intentional — Story 5.5 (delete-my-data) removes consents with the user |
| `consent_type` | text (indexed) | Currently `"ai_processing"`. A constant namespace so future consents (marketing, analytics) can share the same table |
| `version` | text (indexed) | `YYYY-MM-DD-vN` date-prefixed content version (see below) |
| `granted_at` | timestamptz | `now()` default — immutable audit record |
| `locale` | text | `uk` or `en` — the language the user read the privacy text in |
| `ip` / `user_agent` | text, nullable | Best-effort forensic metadata |

A composite index `(user_id, consent_type, version)` backs the hot lookup from `get_current_consent_status` and the `POST /consent` idempotency check.

**Append-only semantics:** we never update or delete rows in `user_consents`. A user who re-grants the same version gets a second row — which is fine, because `hasCurrentConsent` is computed as "does *any* row match `(user_id, consent_type, CURRENT_CONSENT_VERSION)`?". This gives us a full audit trail at the cost of O(consent_events) rows per user, which is negligible.

**Version-gated re-consent — `CURRENT_CONSENT_VERSION`:**

The single source of truth lives in [backend/app/core/consent.py](../../backend/app/core/consent.py) and is mirrored in [frontend/src/features/onboarding/consent-version.ts](../../frontend/src/features/onboarding/consent-version.ts). The format is `YYYY-MM-DD-vN` (e.g. `2026-04-11-v1`) — date-prefixed to stay legible in audit logs and migration filenames.

Bumping this constant forces every authenticated user back through the onboarding gate on their next page load. That is intentional and powerful, so the rule is:

- **Bump only on material changes** — new data flows, new processors, new data categories, new storage locations, new sharing relationships.
- **Do NOT bump on cosmetic edits** — typo fixes, copy polish, translation improvements. Those are covered by the existing consent.

**Procedure to bump:**
1. Edit the privacy text in `frontend/messages/en.json` and `frontend/messages/uk.json` under `onboarding.privacy.*`.
2. Bump `CURRENT_CONSENT_VERSION` in **both** `backend/app/core/consent.py` and `frontend/src/features/onboarding/consent-version.ts` in the **same commit**.
3. CI runs [`.github/workflows/consent-version-sync.yml`](../../.github/workflows/consent-version-sync.yml) on any PR touching either file and fails the build if the two drift out of sync. This prevents the class of bug where the frontend posts an old version string and the backend 422s every user out of onboarding.

**Frontend gate — `ConsentGuard`:**

[frontend/src/lib/auth/consent-guard.tsx](../../frontend/src/lib/auth/consent-guard.tsx) wraps `children` inside the `(dashboard)` layout. It:
- Short-circuits on `/<locale>/onboarding/...` routes to prevent a redirect loop (the onboarding route has its own scoped layout with no `ConsentGuard`).
- Uses TanStack Query with `staleTime: Infinity` and key `["consent", "ai_processing"]`. After `POST /consent` succeeds, `PrivacyExplanationScreen` invalidates this key so the next navigation re-reads fresh state.
- On `hasCurrentConsent === false`, redirects via `router.replace('/<locale>/onboarding/privacy')` and renders `null` during the pending redirect to prevent dashboard chrome from flashing.
- On pending query, renders a dashboard skeleton — no FOUC, no exposed chrome.

The parent dashboard layout ([frontend/src/app/[locale]/(dashboard)/layout.tsx](../../frontend/src/app/[locale]/(dashboard)/layout.tsx)) additionally suppresses its header and upload FAB when `pathname.startsWith('/<locale>/onboarding')`, so a not-yet-consented user sees zero main-app chrome.

**Known gap — client-side enforcement only.** `ConsentGuard` is advisory. A sophisticated client could bypass the guard and call authenticated APIs directly while consent is absent. The MVP accepts this risk because:
- The privacy-sensitive flow is the upload pipeline, and the upload UI is behind the guard.
- No API endpoint currently side-effects on data the user hasn't already uploaded.
- Closing the gap requires a FastAPI dependency (`require_current_consent`) on every mutating route, which is straightforward to add once another Epic 5 story surfaces the need. See [planning-artifacts/future-ideas.md](./future-ideas.md) §4.1.

**Related stories:** 5.1 (encryption at rest — underlying compliance posture), 5.5 (delete-my-data — uses the `ON DELETE CASCADE` on `user_consents.user_id`), 5.6 (view-my-stored-data — surfaces the consent history to the user).

### API & Communication Patterns

| Decision | Choice | Version | Rationale |
|---|---|---|---|
| **API Style** | REST only (MVP) | — | Simpler to build and cache. Teaching Feed card type variation handled via union response type. GraphQL evaluated post-MVP if needed |
| **API Documentation** | Auto-generated OpenAPI spec from FastAPI | OpenAPI 3.1 | FastAPI generates spec automatically. Frontend consumes via @hey-api/openapi-ts generated TypeScript client |
| **Streaming** | SSE (Server-Sent Events) | — | Pipeline progress and LLM-generated education content streamed via FastAPI StreamingResponse. Frontend consumes with Vercel AI SDK hooks |
| **Error Handling** | Consistent JSON error format | — | All errors return `{"error": {"code": "ERROR_CODE", "message": "...", "details": {...}}}`. HTTP status codes follow REST conventions |
| **API Versioning** | URL prefix `/api/v1/` | — | Simple, explicit versioning. Allows future `/api/v2/` without breaking existing clients |
| **File Upload** | Async: upload returns job_id (HTTP 202), SSE for progress | — | Never process AI workloads synchronously. Immediate acknowledgment, background processing via Celery |

**Affects:** Frontend-backend contract, developer experience, client SDK generation

### Frontend Architecture

| Decision | Choice | Version | Rationale |
|---|---|---|---|
| **Framework** | Next.js with App Router | 16.1 | Latest stable. Turbopack default bundler. Server Components with "use cache" directives |
| **State Management (Server)** | TanStack Query | v5.90.x | Industry standard for server state in React. Handles caching, invalidation, optimistic updates for API data |
| **State Management (Client)** | React Context | Built-in | Auth state (Cognito session) and locale (uk/en) via context providers. No additional dependency needed |
| **Component Library** | shadcn/ui | CLI v4 (March 2026) | Copy-paste components with full ownership. Built on unified radix-ui package. Design system presets for consistent Teaching Feed cards |
| **Styling** | Tailwind CSS | 4.x (via create-next-app) | Utility-first, pairs with shadcn/ui. Responsive design for mobile-first web app |
| **i18n** | next-intl | v4.8.x | Best App Router + Server Components support. Note: Next.js 16 renamed `middleware.ts` to `proxy.ts` — next-intl config must use `proxy.ts` |
| **API Client** | Generated from OpenAPI spec | @hey-api/openapi-ts latest | Type-safe API calls auto-generated from FastAPI's OpenAPI spec. Eliminates manual type sync |
| **AI Streaming** | Vercel AI SDK | Latest | `useCompletion` hook for SSE consumption. Handles streaming LLM responses in Teaching Feed education layers |

**Affects:** All frontend components, UX performance, developer experience

### Infrastructure & Deployment

| Decision | Choice | Rationale |
|---|---|---|
| **Frontend Hosting** | Vercel | Optimized for Next.js. Best DX, automatic preview deployments, edge network. Simpler than AWS Amplify for Next.js |
| **API Compute** | AWS App Runner | Fully managed, auto-scaling, scales to zero on idle (cost savings for early stage). Simpler than ECS Fargate for the API layer |
| **Worker Compute** | AWS ECS Fargate | Celery workers need persistent containers for long-running AI pipeline jobs. Fargate provides this without managing servers |
| **Database** | Amazon RDS PostgreSQL (+ pgvector extension) | Managed PostgreSQL with automated backups, encryption at rest, pgvector support |
| **Cache/Queue** | Amazon ElastiCache (Redis) | Managed Redis for Celery broker, API caching, and job status tracking |
| **File Storage** | Amazon S3 | Uploaded CSV/PDF files. Per-user prefixed keys. Server-side encryption |
| **Auth** | Amazon Cognito | User pools with email/password. JWT issuance. Managed user lifecycle |
| **Email** | Amazon SES | Upload reminders, notification emails. Cost-effective, high deliverability |
| **CI/CD** | GitHub Actions | Standard choice. Runs tests, builds frontend/backend, deploys to Vercel + AWS |
| **Environments** | dev / staging / production | Separate AWS resources per environment. Vercel preview deployments for frontend PRs |
| **Secrets** | AWS Secrets Manager | API keys, database credentials, Cognito config. Referenced by App Runner and ECS tasks |

**AWS Architecture Diagram:**
```
                    [Vercel]
                    Next.js 16.1
                        |
                   HTTPS (REST API)
                        |
                [AWS App Runner]
                   FastAPI API
                   /    |    \
                  /     |     \
    [Cognito]  [S3]  [ElastiCache]  [RDS PostgreSQL]
    User Pool  Files   Redis         + pgvector
                        |
                [ECS Fargate]
                Celery Workers
                (LangGraph Pipeline)
                        |
                   [LLM APIs]
                 Claude / GPT
```

### Decision Impact Analysis

**Implementation Sequence:**
1. Project scaffolding (monorepo, create-next-app, FastAPI init)
2. AWS infrastructure provisioning (RDS, ElastiCache, Cognito, S3)
3. Authentication flow (Cognito + NextAuth.js + FastAPI middleware)
4. Database models + migrations (SQLModel + Alembic)
5. File upload + async processing (S3 + Celery + Redis)
6. AI pipeline (LangGraph agents, sequential)
7. RAG system (pgvector + OpenAI text-embedding-3-small embeddings)
8. Teaching Feed UI (shadcn/ui cards + TanStack Query + SSE)
9. Freemium tier gating
10. Payment integration (Fondy + LemonSqueezy)

**Cross-Component Dependencies:**
- Auth (Cognito) must be in place before any API endpoint works
- Database schema must be stable before AI pipeline can persist results
- Redis must be running before Celery workers or caching works
- OpenAPI spec must be generated before frontend API client can be built
- OpenAI text-embedding-3-small embeddings service must be running before Education Agent can do RAG retrieval

## Implementation Patterns & Consistency Rules

### Pattern Categories Defined

**Critical Conflict Points Identified:** 25+ areas where AI agents could make different choices, organized into 5 categories below.

### Naming Patterns

**Database Naming Conventions:**

| Element | Convention | Example |
|---|---|---|
| Tables | `snake_case`, plural | `users`, `transactions`, `financial_health_scores` |
| Columns | `snake_case` | `user_id`, `created_at`, `health_score` |
| Primary keys | `id` (UUID v4) | `id UUID PRIMARY KEY DEFAULT gen_random_uuid()` |
| Foreign keys | `{referenced_table_singular}_id` | `user_id`, `transaction_id` |
| Indexes | `idx_{table}_{columns}` | `idx_transactions_user_id`, `idx_transactions_timestamp` |
| Constraints | `{type}_{table}_{columns}` | `uq_users_email`, `fk_transactions_user_id` |
| Enums | `snake_case` | `triage_severity`, `subscription_status` |

**API Naming Conventions:**

| Element | Convention | Example |
|---|---|---|
| Endpoints | `kebab-case`, plural nouns | `/api/v1/transactions`, `/api/v1/insights` |
| JSON fields | `camelCase` (Pydantic `alias_generator=to_camel`) | `userId`, `createdAt`, `healthScore` |
| Query params | `camelCase` | `?startDate=2026-01-01&pageSize=20` |
| Path params | `camelCase` | `/api/v1/transactions/{transactionId}` |
| Headers | Standard HTTP conventions | `Authorization`, `Content-Type`, `X-Request-Id` |
| SSE event names | `kebab-case` | `pipeline-progress`, `insight-ready`, `job-complete` |

**Code Naming Conventions:**

| Element | Frontend (TypeScript) | Backend (Python) |
|---|---|---|
| Files (components) | `PascalCase.tsx` — `InsightCard.tsx` | n/a |
| Files (utilities) | `kebab-case.ts` — `api-client.ts` | `snake_case.py` — `monobank_parser.py` |
| Files (routes) | `kebab-case/page.tsx` (App Router) | n/a |
| Functions | `camelCase` — `fetchInsights()` | `snake_case` — `process_transactions()` |
| Variables | `camelCase` — `userId` | `snake_case` — `user_id` |
| Constants | `UPPER_SNAKE_CASE` — `MAX_UPLOAD_SIZE` | `UPPER_SNAKE_CASE` — `MAX_UPLOAD_SIZE` |
| Classes/Types | `PascalCase` — `InsightCard` | `PascalCase` — `TransactionModel` |
| React components | `PascalCase` — `<TeachingFeed />` | n/a |
| Celery tasks | n/a | `snake_case` — `process_upload_task` |
| LangGraph nodes | n/a | `snake_case` — `categorization_node` |
| Environment vars | `UPPER_SNAKE_CASE` prefixed | `NEXT_PUBLIC_API_URL`, `DATABASE_URL` |

### Structure Patterns

**Frontend Organization (Hybrid — shared UI + feature folders):**

```
frontend/src/
├── app/                        # Next.js App Router pages
│   ├── (auth)/                 # Auth route group (login, signup)
│   ├── (dashboard)/            # Protected route group
│   │   ├── feed/page.tsx       # Teaching Feed page
│   │   ├── upload/page.tsx     # Upload page
│   │   └── profile/page.tsx    # Profile page
│   ├── layout.tsx              # Root layout (providers)
│   └── proxy.ts                # next-intl proxy (was middleware.ts in Next.js 15)
├── components/
│   ├── ui/                     # shadcn/ui base components (Button, Card, Dialog, etc.)
│   └── layout/                 # Shared layout components (Header, Sidebar, Footer)
├── features/                   # Domain feature modules
│   ├── teaching-feed/          # Teaching Feed feature
│   │   ├── components/         # Feature-specific components (includes feedback UI)
│   │   ├── hooks/              # Feature-specific hooks (includes feedback hooks)
│   │   └── types.ts            # Feature-specific types (includes feedback types)
│   ├── upload/                 # File upload feature
│   ├── auth/                   # Auth feature (Cognito flows)
│   ├── profile/                # User profile feature
│   └── insights/               # Insights/analytics feature
├── lib/                        # Shared utilities
│   ├── api/                    # Generated API client + config
│   ├── auth/                   # NextAuth.js config + Cognito
│   └── utils.ts                # General helpers
├── i18n/                       # Translations
│   ├── messages/
│   │   ├── en.json
│   │   └── uk.json
│   └── config.ts
└── types/                      # Shared TypeScript types
```

**Backend Organization (Domain-aligned modules):**

```
backend/app/
├── api/                        # Route handlers (thin layer)
│   ├── v1/
│   │   ├── auth.py             # Auth endpoints
│   │   ├── uploads.py          # File upload endpoints
│   │   ├── transactions.py     # Transaction query endpoints
│   │   ├── insights.py         # Teaching Feed / insights endpoints
│   │   ├── feedback.py         # Card feedback, issue reports, milestone responses (FR45-FR55)
│   │   ├── profile.py          # User profile endpoints
│   │   └── jobs.py             # Job status + SSE streaming
│   └── deps.py                 # Shared dependencies (auth, db session)
├── agents/                     # LangGraph agent definitions
│   ├── pipeline.py             # Main pipeline graph definition
│   ├── state.py                # Shared pipeline state TypedDict
│   ├── ingestion/
│   │   ├── node.py             # Ingestion agent node
│   │   └── parsers/            # Bank-specific parsers
│   │       ├── base.py         # Abstract parser interface
│   │       └── monobank.py     # Monobank CSV parser
│   ├── categorization/
│   │   └── node.py
│   ├── pattern_detection/
│   │   └── node.py
│   ├── triage/
│   │   └── node.py
│   └── education/
│       ├── node.py
│       └── prompts.py          # Education prompt templates
├── core/                       # Application core
│   ├── config.py               # Settings (Pydantic BaseSettings)
│   ├── security.py             # Cognito JWT validation
│   ├── database.py             # SQLModel engine + session factory
│   └── exceptions.py           # Custom exception classes
├── models/                     # SQLModel data models
│   ├── user.py
│   ├── transaction.py
│   ├── insight.py
│   ├── job.py
│   ├── financial_profile.py
│   └── feedback.py             # CardFeedback, FeedbackResponse models (FR45-FR55)
├── services/                   # Business logic layer
│   ├── upload_service.py
│   ├── transaction_service.py
│   ├── insight_service.py
│   ├── feedback_service.py     # Card feedback, implicit signals, milestone responses, RAG flagging (FR45-FR55)
│   └── subscription_service.py
├── tasks/                      # Celery task definitions
│   ├── celery_app.py           # Celery app configuration
│   ├── pipeline_tasks.py       # AI pipeline processing tasks
│   └── notification_tasks.py   # Email notification tasks
├── rag/                        # RAG pipeline components
│   ├── embeddings.py           # OpenAI text-embedding-3-small generation
│   ├── retriever.py            # pgvector retrieval logic
│   └── knowledge_base.py       # Knowledge base management
└── main.py                     # FastAPI app entry point
```

**Test Organization:**

| Stack | Convention | Example |
|---|---|---|
| Frontend | Co-located with source | `features/teaching-feed/components/InsightCard.test.tsx` |
| Frontend E2E | Dedicated folder | `frontend/e2e/upload-flow.spec.ts` |
| Backend | Separate `tests/` mirroring `app/` | `backend/tests/api/v1/test_uploads.py` |
| Backend integration | Subfolder | `backend/tests/integration/test_pipeline.py` |

### Format Patterns

**API Response Formats:**

```typescript
// Single resource
GET /api/v1/transactions/{id}
→ { "id": "uuid", "amount": -95000, "description": "...", ... }

// Collection with pagination (cursor-based)
GET /api/v1/transactions?cursor=abc&pageSize=20
→ { "items": [...], "total": 245, "nextCursor": "def", "hasMore": true }

// Teaching Feed / Insights (union type cards)
GET /api/v1/insights?cursor=abc
→ { "items": [
    { "type": "spendingInsight", "severity": "warning", ... },
    { "type": "subscriptionAlert", "severity": "critical", ... },
    { "type": "savingTip", "severity": "info", ... }
  ], "nextCursor": "def", "hasMore": true }

// Job status
GET /api/v1/jobs/{id}
→ { "id": "uuid", "status": "processing", "step": "categorization", "progress": 30 }

// Error response (all errors)
→ { "error": { "code": "PARSE_ERROR", "message": "Human-readable message", "details": {...} } }

// File upload (async)
POST /api/v1/uploads → 202 Accepted
→ { "jobId": "uuid", "statusUrl": "/api/v1/jobs/{jobId}" }

// Card feedback — thumbs vote (Layer 1)
POST /api/v1/feedback/cards/{cardId}/vote
← { "vote": "up" }
→ 201 { "id": "uuid", "cardId": "uuid", "vote": "up", "createdAt": "..." }

// Card feedback — update with reason chip (Layer 2, after thumbs-down)
PATCH /api/v1/feedback/{feedbackId}
← { "reasonChip": "not_relevant" }
→ 200 { "id": "uuid", "reasonChip": "not_relevant" }

// Card feedback — issue report (Layer 1)
POST /api/v1/feedback/cards/{cardId}/report
← { "issueCategory": "incorrect_info", "freeText": "Amount seems wrong" }
→ 201 { "id": "uuid", "cardId": "uuid", "issueCategory": "incorrect_info" }

// Card interaction implicit signals (Layer 0, batched)
POST /api/v1/cards/interactions
← { "interactions": [{ "cardId": "uuid", "timeOnCardMs": 4500, "educationExpanded": true, "educationDepthReached": 2, "swipeDirection": "left", "cardPositionInFeed": 3 }] }
→ 204 No Content

// Milestone feedback response (Layer 3)
POST /api/v1/feedback/milestone
← { "feedbackCardType": "milestone_3rd_upload", "responseValue": "happy", "freeText": "Love it!" }
→ 201 { "id": "uuid", "feedbackCardType": "milestone_3rd_upload" }

// Get user's feedback for a card (to show persisted vote state)
GET /api/v1/feedback/cards/{cardId}
→ 200 { "vote": "up", "reasonChip": null, "createdAt": "..." }
→ 404 (no feedback yet)
```

**HTTP Status Code Usage:**

| Code | Usage |
|---|---|
| `200` | Successful GET, PUT, PATCH |
| `201` | Successful POST creating a resource |
| `202` | Accepted for async processing (file upload) |
| `204` | Successful DELETE |
| `400` | Validation error, malformed request |
| `401` | Missing or invalid JWT |
| `403` | Valid JWT but insufficient permissions (wrong tier) |
| `404` | Resource not found |
| `409` | Conflict (duplicate upload, etc.) |
| `422` | Unprocessable entity (Pydantic validation) |
| `429` | Rate limited |
| `500` | Internal server error |

**Data Format Rules:**

| Format | Convention | Example |
|---|---|---|
| Dates in API | ISO 8601 UTC | `"2026-03-16T14:30:00Z"` |
| Dates in DB | `timestamptz` | Timezone-aware PostgreSQL type |
| Dates in UI | User locale | Ukrainian: `16.03.2026 14:30` |
| Money in API | Integer (kopiykas) | `-95000` (= -950.00 UAH) |
| Money in UI | Formatted with locale | `-950,00 ₴` |
| IDs | UUID v4 string | `"550e8400-e29b-41d4-a716-446655440000"` |
| Booleans | `true`/`false` | Never `1`/`0` or `"true"` |
| Nulls | Explicit `null` | Never omit field; return `null` if empty |
| Currency codes | ISO 4217 numeric | `980` (UAH), `840` (USD) |
| Language codes | ISO 639-1 | `"uk"`, `"en"` |

### Communication Patterns

**SSE Event Structure:**

```
event: pipeline-progress
data: {"jobId": "uuid", "step": "categorization", "progress": 30, "message": "Categorizing 245 transactions..."}

event: insight-ready
data: {"jobId": "uuid", "insightId": "uuid", "type": "spendingInsight"}

event: job-complete
data: {"jobId": "uuid", "status": "completed", "totalInsights": 12}

event: job-failed
data: {"jobId": "uuid", "status": "failed", "error": {"code": "LLM_ERROR", "message": "..."}}
```

**Celery Task Naming:**

| Convention | Example |
|---|---|
| Module path dot notation | `app.tasks.pipeline_tasks.run_financial_pipeline` |
| Task function name | `snake_case` — `run_financial_pipeline`, `send_upload_reminder` |

**Logging Format:**

```python
# Backend: structured JSON logging
{"timestamp": "2026-03-16T14:30:00Z", "level": "INFO", "service": "api",
 "user_id": "uuid", "job_id": "uuid", "message": "Pipeline step completed",
 "step": "categorization", "duration_ms": 1234}
```

| Level | Usage |
|---|---|
| `DEBUG` | Detailed diagnostic (SQL queries, LLM prompts) |
| `INFO` | Normal operations (pipeline step completed, upload received) |
| `WARNING` | Recoverable issues (LLM retry, low confidence categorization) |
| `ERROR` | Failed operations (pipeline failure, auth failure) |
| `CRITICAL` | System-level failures (DB connection lost, Redis down) |

### Process Patterns

**Error Handling:**

| Layer | Pattern |
|---|---|
| **FastAPI routes** | Custom exception handlers map to consistent JSON error format. Never expose stack traces in production |
| **LangGraph pipeline** | Each agent node wrapped in try/except. Failures logged and recorded in pipeline state. Partial results preserved via checkpointing |
| **Celery tasks** | `max_retries=3` with exponential backoff for transient failures (LLM API timeouts). Dead letter queue for permanent failures |
| **Frontend** | TanStack Query `onError` callbacks. Error boundaries per feature. User-friendly error messages from i18n, not raw API errors |
| **LLM calls** | Retry with exponential backoff (2s, 4s, 8s). Fallback to secondary LLM provider if primary fails. Log token usage for cost tracking |

**Loading State Patterns:**

| Context | Pattern |
|---|---|
| **Page loads** | Next.js `loading.tsx` with skeleton components (shadcn/ui Skeleton) |
| **API data** | TanStack Query `isLoading` / `isPending` states per query |
| **File upload** | Immediate optimistic UI ("Uploading...") + SSE progress stream |
| **AI pipeline** | Multi-step progress bar with step names: Parsing → Categorizing → Detecting Patterns → Analyzing → Generating Insights |
| **Streaming text** | Vercel AI SDK handles token-by-token rendering for education content |

**Validation Patterns:**

| Layer | Tool | Responsibility |
|---|---|---|
| **Frontend forms** | React Hook Form + Zod | Client-side validation for immediate feedback |
| **API input** | Pydantic v2 models | Server-side validation — authoritative, never trust client |
| **File upload** | Custom validator | MIME type, file size, header row format check (sync, before queuing) |
| **Database** | SQLModel + DB constraints | Final defense — NOT NULL, UNIQUE, CHECK constraints |

### Enforcement Guidelines

**All AI Agents MUST:**

1. Follow the naming conventions table for the language they're working in (camelCase for TS, snake_case for Python, camelCase for API JSON)
2. Place files in the correct location per the structure patterns above
3. Use the standard error response format `{"error": {"code": "...", "message": "...", "details": {...}}}` for all error responses
4. Return money as integers (kopiykas) and dates as ISO 8601 UTC in API responses
5. Use UUID v4 for all entity IDs
6. Add structured JSON logging for all significant operations
7. Never expose internal errors to the frontend — map to user-friendly error codes
8. Use TanStack Query for all API data fetching on the frontend (no raw `fetch` in components)
9. Scope all database queries to the authenticated `user_id` (enforced via dependency injection + RLS)

**Pattern Verification:**
- ESLint + Prettier enforces frontend naming and formatting
- Ruff + Black enforces backend Python formatting
- Pydantic `alias_generator=to_camel` ensures camelCase API output
- Generated OpenAPI client ensures frontend-backend type alignment
- CI pipeline runs linting checks on every PR

## Project Structure & Boundaries

### Complete Project Directory Structure

```
kopiika-ai/
│
├── .github/
│   ├── workflows/
│   │   ├── ci-frontend.yml          # Frontend lint, test, build
│   │   ├── ci-backend.yml           # Backend lint, test
│   │   ├── deploy-frontend.yml      # Deploy to Vercel
│   │   └── deploy-backend.yml       # Deploy to AWS (App Runner + ECS)
│   └── CODEOWNERS
│
├── frontend/                         # Next.js 16.1 (TypeScript)
│   ├── src/
│   │   ├── app/
│   │   │   ├── globals.css
│   │   │   ├── layout.tsx            # Root layout: providers (QueryClient, NextIntl, NextAuth)
│   │   │   ├── proxy.ts             # next-intl proxy (Next.js 16 convention)
│   │   │   ├── not-found.tsx
│   │   │   ├── error.tsx            # Global error boundary
│   │   │   ├── loading.tsx          # Global loading skeleton
│   │   │   │
│   │   │   ├── [locale]/            # i18n locale prefix (uk, en)
│   │   │   │   ├── layout.tsx       # Locale layout
│   │   │   │   ├── page.tsx         # Landing / marketing page
│   │   │   │   │
│   │   │   │   ├── (auth)/          # Auth route group (no layout chrome)
│   │   │   │   │   ├── login/page.tsx
│   │   │   │   │   ├── signup/page.tsx
│   │   │   │   │   └── forgot-password/page.tsx
│   │   │   │   │
│   │   │   │   └── (dashboard)/     # Protected route group (with sidebar/header)
│   │   │   │       ├── layout.tsx   # Dashboard layout (auth guard, nav)
│   │   │   │       ├── feed/
│   │   │   │       │   ├── page.tsx          # Teaching Feed main page
│   │   │   │       │   └── loading.tsx       # Feed skeleton loader
│   │   │   │       ├── upload/
│   │   │   │       │   └── page.tsx          # Upload page with drag-drop
│   │   │   │       ├── history/
│   │   │   │       │   └── page.tsx          # Upload history / past analyses
│   │   │   │       ├── profile/
│   │   │   │       │   └── page.tsx          # User profile + Financial Health Score
│   │   │   │       └── settings/
│   │   │   │           └── page.tsx          # Notification prefs, language, subscription
│   │   │   │
│   │   │   └── api/                 # Next.js API routes (auth callbacks only)
│   │   │       └── auth/
│   │   │           └── [...nextauth]/route.ts
│   │   │
│   │   ├── components/
│   │   │   ├── ui/                  # shadcn/ui base components
│   │   │   │   ├── button.tsx
│   │   │   │   ├── card.tsx
│   │   │   │   ├── dialog.tsx
│   │   │   │   ├── dropdown-menu.tsx
│   │   │   │   ├── input.tsx
│   │   │   │   ├── progress.tsx
│   │   │   │   ├── skeleton.tsx
│   │   │   │   ├── badge.tsx
│   │   │   │   ├── tabs.tsx
│   │   │   │   └── tooltip.tsx
│   │   │   └── layout/
│   │   │       ├── Header.tsx
│   │   │       ├── Sidebar.tsx
│   │   │       ├── Footer.tsx
│   │   │       └── LocaleSwitcher.tsx
│   │   │
│   │   ├── features/
│   │   │   ├── teaching-feed/
│   │   │   │   ├── components/
│   │   │   │   │   ├── FeedContainer.tsx         # Feed list with infinite scroll
│   │   │   │   │   ├── InsightCard.tsx           # Base card with severity badge
│   │   │   │   │   ├── SpendingInsightCard.tsx   # Spending pattern card
│   │   │   │   │   ├── SubscriptionAlertCard.tsx # Subscription detection card
│   │   │   │   │   ├── SavingTipCard.tsx         # Saving recommendation card
│   │   │   │   │   ├── ForecastCard.tsx          # Predictive forecast card
│   │   │   │   │   ├── EducationLayer.tsx        # Progressive disclosure education
│   │   │   │   │   ├── TriageBadge.tsx           # Severity badge (red/yellow/green)
│   │   │   │   │   ├── CardFeedbackBar.tsx       # Thumbs up/down + flag icon (Layer 1, FR47-FR48)
│   │   │   │   │   ├── FollowUpPanel.tsx         # Slide-up reason chips on thumbs-down (Layer 2, FR50-FR51)
│   │   │   │   │   ├── ReportIssueForm.tsx       # In-context issue report form (Layer 1, FR48)
│   │   │   │   │   └── MilestoneFeedbackCard.tsx # Feedback cards in the feed (Layer 3, FR52-FR54)
│   │   │   │   ├── hooks/
│   │   │   │   │   ├── use-teaching-feed.ts      # TanStack Query hook for feed
│   │   │   │   │   ├── use-education-stream.ts   # SSE hook for streaming education
│   │   │   │   │   ├── use-card-feedback.ts      # TanStack mutation for votes + queries for persisted state (FR47)
│   │   │   │   │   └── use-card-interactions.ts  # Implicit signal tracking: time, expansion, velocity (FR45-FR46)
│   │   │   │   └── types.ts
│   │   │   │
│   │   │   ├── upload/
│   │   │   │   ├── components/
│   │   │   │   │   ├── UploadDropzone.tsx        # Drag-drop file upload
│   │   │   │   │   ├── UploadProgress.tsx        # Pipeline progress tracker
│   │   │   │   │   └── FileFormatGuide.tsx       # Help text for supported formats
│   │   │   │   ├── hooks/
│   │   │   │   │   ├── use-upload.ts             # Upload mutation + progress SSE
│   │   │   │   │   └── use-job-status.ts         # Job polling/SSE hook
│   │   │   │   └── types.ts
│   │   │   │
│   │   │   ├── auth/
│   │   │   │   ├── components/
│   │   │   │   │   ├── LoginForm.tsx
│   │   │   │   │   ├── SignupForm.tsx
│   │   │   │   │   └── ForgotPasswordForm.tsx
│   │   │   │   └── hooks/
│   │   │   │       └── use-auth.ts               # Auth state + Cognito helpers
│   │   │   │
│   │   │   ├── profile/
│   │   │   │   ├── components/
│   │   │   │   │   ├── FinancialHealthScore.tsx  # Score visualization (0-100)
│   │   │   │   │   ├── SpendingBreakdown.tsx     # Category breakdown
│   │   │   │   │   └── TrendChart.tsx            # Historical trend chart
│   │   │   │   └── hooks/
│   │   │   │       └── use-profile.ts
│   │   │   │
│   │   │   ├── queries/
│   │   │   │   ├── components/
│   │   │   │   │   ├── QuerySelector.tsx         # Pre-built query selector
│   │   │   │   │   └── QueryResult.tsx           # Query result display
│   │   │   │   └── hooks/
│   │   │   │       └── use-query.ts
│   │   │   │
│   │   │   └── settings/
│   │   │       ├── components/
│   │   │       │   ├── NotificationPrefs.tsx
│   │   │       │   ├── LanguageSelector.tsx
│   │   │       │   ├── SubscriptionManager.tsx
│   │   │       │   └── DataDeletion.tsx          # One-click data deletion
│   │   │       └── hooks/
│   │   │           └── use-settings.ts
│   │   │
│   │   ├── lib/
│   │   │   ├── api/
│   │   │   │   ├── client.ts                # Generated API client config
│   │   │   │   └── generated/               # @hey-api/openapi-ts output
│   │   │   ├── auth/
│   │   │   │   ├── next-auth-config.ts      # NextAuth.js + Cognito config
│   │   │   │   └── auth-guard.tsx           # Route protection component
│   │   │   ├── providers/
│   │   │   │   ├── query-provider.tsx       # TanStack Query provider
│   │   │   │   └── intl-provider.tsx        # next-intl provider
│   │   │   ├── utils.ts                     # cn() helper, formatters
│   │   │   └── format/
│   │   │       ├── currency.ts              # UAH formatting (kopiykas → ₴)
│   │   │       └── date.ts                  # Locale-aware date formatting
│   │   │
│   │   ├── i18n/
│   │   │   ├── messages/
│   │   │   │   ├── en.json
│   │   │   │   └── uk.json
│   │   │   ├── config.ts                    # Supported locales, default locale
│   │   │   └── request.ts                   # next-intl request config
│   │   │
│   │   └── types/
│   │       ├── api.ts                       # Re-exported generated API types
│   │       └── common.ts                    # Shared frontend types
│   │
│   ├── e2e/                                 # Playwright E2E tests
│   │   ├── upload-flow.spec.ts
│   │   ├── feed-interaction.spec.ts
│   │   └── auth-flow.spec.ts
│   │
│   ├── public/
│   │   ├── favicon.ico
│   │   └── images/
│   │
│   ├── next.config.ts
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   ├── components.json                      # shadcn/ui config
│   ├── package.json
│   ├── .env.local                           # Local dev env vars
│   └── .env.example
│
├── backend/                                  # FastAPI (Python 3.12)
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                          # FastAPI app entry point
│   │   │
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── deps.py                      # Shared deps (get_db, get_current_user)
│   │   │   └── v1/
│   │   │       ├── __init__.py
│   │   │       ├── router.py                # v1 API router aggregator
│   │   │       ├── auth.py                  # POST /signup, /login callbacks
│   │   │       ├── uploads.py               # POST /uploads, GET /uploads
│   │   │       ├── transactions.py          # GET /transactions, /transactions/{id}
│   │   │       ├── insights.py              # GET /insights, /insights/{id}
│   │   │       ├── feedback.py             # POST /feedback/cards/{id}/vote, /report, /milestone; POST /cards/interactions (FR45-FR55)
│   │   │       ├── profile.py               # GET/PUT /profile, /health-score
│   │   │       ├── jobs.py                  # GET /jobs/{id}, /jobs/{id}/stream (SSE)
│   │   │       ├── queries.py               # POST /queries (pre-built data queries)
│   │   │       └── settings.py              # GET/PUT /settings (notifications, prefs)
│   │   │
│   │   ├── agents/
│   │   │   ├── __init__.py
│   │   │   ├── pipeline.py                  # Main StateGraph definition
│   │   │   ├── state.py                     # FinancialPipelineState TypedDict
│   │   │   ├── ingestion/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── node.py                  # Ingestion agent node
│   │   │   │   └── parsers/
│   │   │   │       ├── __init__.py
│   │   │   │       ├── base.py              # AbstractParser interface
│   │   │   │       ├── monobank.py          # Monobank CSV parser
│   │   │   │       └── privatbank.py        # PrivatBank XLS parser (future)
│   │   │   ├── categorization/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── node.py                  # Categorization agent node
│   │   │   │   └── mcc_mapping.py           # MCC code → category mapping
│   │   │   ├── pattern_detection/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── node.py                  # Pattern detection agent node
│   │   │   │   └── detectors/
│   │   │   │       ├── recurring.py         # Subscription/recurring charge detection
│   │   │   │       ├── trends.py            # Month-over-month trend analysis
│   │   │   │       └── anomalies.py         # Anomaly detection
│   │   │   ├── triage/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── node.py                  # Triage agent node
│   │   │   │   └── severity.py              # Severity scoring logic
│   │   │   └── education/
│   │   │       ├── __init__.py
│   │   │       ├── node.py                  # Education agent node (RAG)
│   │   │       └── prompts.py               # LLM prompt templates (UK + EN)
│   │   │
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py                    # Pydantic BaseSettings (env vars)
│   │   │   ├── security.py                  # Cognito JWT validation
│   │   │   ├── database.py                  # Async SQLModel engine + session
│   │   │   ├── exceptions.py                # Custom exceptions + handlers
│   │   │   ├── logging.py                   # Structured JSON logging setup
│   │   │   ├── audit.py                     # Compliance audit trail middleware — logs financial data access events (user_id, timestamp, action, resource)
│   │   │   └── redis.py                     # Redis connection factory
│   │   │
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── user.py                      # User, UserPreferences
│   │   │   ├── transaction.py               # Transaction, RawTransaction
│   │   │   ├── insight.py                   # Insight (union: spending, subscription, etc.)
│   │   │   ├── job.py                       # ProcessingJob
│   │   │   ├── financial_profile.py         # FinancialProfile, HealthScore
│   │   │   ├── feedback.py                  # CardFeedback, FeedbackResponse, CardInteraction extensions (FR45-FR55)
│   │   │   └── subscription.py              # UserSubscription (freemium tier)
│   │   │
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── upload_service.py            # File validation, S3 storage, job creation
│   │   │   ├── transaction_service.py       # Transaction CRUD, user-scoped queries
│   │   │   ├── insight_service.py           # Insight retrieval, feed pagination
│   │   │   ├── feedback_service.py          # Card votes, issue reports, implicit signals, milestone responses, RAG flagging (FR45-FR55)
│   │   │   ├── profile_service.py           # Health score calculation, profile updates
│   │   │   ├── subscription_service.py      # Tier checking, payment webhook handling
│   │   │   └── notification_service.py      # Email sending via SES
│   │   │
│   │   ├── tasks/
│   │   │   ├── __init__.py
│   │   │   ├── celery_app.py                # Celery configuration (Redis broker)
│   │   │   ├── pipeline_tasks.py            # run_financial_pipeline task
│   │   │   └── notification_tasks.py        # send_upload_reminder, send_insight_ready
│   │   │
│   │   └── rag/
│   │       ├── __init__.py
│   │       ├── embeddings.py                # OpenAI text-embedding-3-small generation
│   │       ├── retriever.py                 # pgvector similarity search
│   │       └── knowledge_base.py            # KB document management
│   │
│   ├── data/
│   │   └── rag-corpus/                      # Financial education content (seed data)
│   │       ├── en/                          # English documents
│   │       │   ├── budgeting.md
│   │       │   ├── saving_strategies.md
│   │       │   └── ...
│   │       └── uk/                          # Ukrainian documents
│   │           ├── budgeting.md
│   │           ├── saving_strategies.md
│   │           └── ...
│   │
│   ├── alembic/
│   │   ├── env.py
│   │   ├── versions/                        # Migration files
│   │   └── script.py.mako
│   ├── alembic.ini
│   │
│   ├── tests/
│   │   ├── conftest.py                      # Fixtures: test DB, test client, mock user
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── test_uploads.py
│   │   │       ├── test_transactions.py
│   │   │       ├── test_insights.py
│   │   │       ├── test_feedback.py         # Card feedback, issue reports, milestone responses
│   │   │       └── test_auth.py
│   │   ├── agents/
│   │   │   ├── test_ingestion.py
│   │   │   ├── test_categorization.py
│   │   │   ├── test_pattern_detection.py
│   │   │   ├── test_triage.py
│   │   │   └── test_education.py
│   │   ├── services/
│   │   │   ├── test_upload_service.py
│   │   │   ├── test_feedback_service.py     # Feedback aggregation, engagement scoring, RAG flagging
│   │   │   └── test_transaction_service.py
│   │   └── integration/
│   │       ├── test_pipeline_e2e.py         # Full pipeline integration test
│   │       └── test_rag_retrieval.py
│   │
│   ├── pyproject.toml                       # uv project config + dependencies
│   ├── .python-version                      # 3.12
│   ├── .env                                 # Local dev env vars
│   └── .env.example
│
├── shared/                                   # Cross-stack shared artifacts
│   └── openapi/
│       └── generate-client.sh               # Script to regenerate TS client from OpenAPI
│
├── infra/                                    # AWS infrastructure (optional IaC)
│   └── README.md                            # Infrastructure setup documentation
│
├── docker-compose.yml                        # Local dev: PostgreSQL + Redis
├── .gitignore
├── .editorconfig
└── README.md
```

### Architectural Boundaries

**API Boundaries:**

```
Frontend (Vercel)  ←→  FastAPI API (App Runner)  ←→  PostgreSQL (RDS)
                            ↕                           ↕
                       Celery Workers (ECS)        pgvector (same RDS)
                            ↕
                       LLM APIs (external)
```

| Boundary | Protocol | Auth | Data Format |
|---|---|---|---|
| Frontend → FastAPI | HTTPS REST | Cognito JWT in `Authorization` header | JSON (camelCase) |
| FastAPI → PostgreSQL | TCP (SQLModel async) | Connection string + RLS | SQL / SQLModel objects |
| FastAPI → Redis | TCP | Connection string | JSON strings |
| FastAPI → S3 | HTTPS (boto3) | IAM role | Binary (file upload) |
| FastAPI → Celery | Redis broker | Internal (same VPC) | Serialized task args |
| Celery → LLM APIs | HTTPS | API key | JSON |
| Celery → PostgreSQL | TCP (SQLModel async) | Connection string + RLS | SQL |
| FastAPI → Frontend (SSE) | HTTPS (text/event-stream) | Cognito JWT | JSON event payloads |
| Cognito → Frontend | HTTPS (OAuth2) | Client ID/Secret | JWT tokens |

**Component Boundaries (Backend):**

| Layer | Responsibility | Depends On | Never Depends On |
|---|---|---|---|
| `api/` | HTTP handling, request validation, response serialization (includes feedback endpoints) | `services/`, `core/`, `models/` | `agents/`, `tasks/`, `rag/` |
| `services/` | Business logic, orchestration | `models/`, `core/` | `api/`, `agents/` |
| `agents/` | LangGraph pipeline nodes, AI logic | `models/`, `core/`, `rag/`, `services/` | `api/` |
| `tasks/` | Celery task definitions, async job execution | `agents/`, `services/`, `core/` | `api/` |
| `models/` | SQLModel data models, schema definitions | `core/` (database engine only) | Everything else |
| `core/` | Config, security, DB engine, exceptions | Nothing (leaf dependency) | Everything |
| `rag/` | Embeddings, retrieval, knowledge base | `core/`, `models/` | `api/`, `agents/` |

**Component Boundaries (Frontend):**

| Layer | Responsibility | Depends On | Never Depends On |
|---|---|---|---|
| `app/` (routes) | Page composition, layout | `features/`, `components/`, `lib/` | — |
| `features/` | Domain logic, feature-specific components/hooks | `components/ui/`, `lib/`, `types/` | Other features (isolated) |
| `components/ui/` | Reusable UI primitives (shadcn) | Tailwind CSS only | `features/`, `lib/api/` |
| `components/layout/` | App shell (header, sidebar) | `components/ui/`, `lib/auth/` | `features/` |
| `lib/api/` | Generated API client | — (auto-generated) | — |
| `lib/auth/` | Auth config, guards | NextAuth.js, Cognito | `features/` |

### Requirements to Structure Mapping

**PRD Feature → Directory Mapping:**

| PRD Feature | Frontend Location | Backend Location |
|---|---|---|
| **Statement Upload & Parsing** | `features/upload/` | `api/v1/uploads.py`, `agents/ingestion/`, `services/upload_service.py` |
| **Multi-Agent AI Pipeline** | `features/upload/` (progress UI) | `agents/`, `tasks/pipeline_tasks.py`, `agents/pipeline.py` |
| **Teaching Feed** | `features/teaching-feed/` | `api/v1/insights.py`, `services/insight_service.py` |
| **Cumulative Financial Profile** | `features/profile/` | `api/v1/profile.py`, `services/profile_service.py`, `models/financial_profile.py` |
| **Subscription Detection** | `features/teaching-feed/` (card type) | `agents/pattern_detection/detectors/recurring.py` |
| **Basic Predictive Forecasts** | `features/teaching-feed/` (card type) | `agents/pattern_detection/detectors/trends.py` |
| **Pre-built Data Queries** | `features/queries/` | `api/v1/queries.py` |
| **Bilingual Support** | `i18n/`, `lib/format/` | `agents/education/prompts.py`, `data/rag-corpus/{en,uk}/` |
| **Email Notifications** | `features/settings/` (prefs UI) | `tasks/notification_tasks.py`, `services/notification_service.py` |
| **Freemium Model** | `features/settings/` (subscription UI) | `api/deps.py` (tier guard), `services/subscription_service.py` |
| **User Auth** | `features/auth/`, `lib/auth/` | `api/v1/auth.py`, `core/security.py` |
| **User Feedback — Layer 0 (FR45-FR46)** | `features/teaching-feed/hooks/use-card-interactions.ts` | `api/v1/feedback.py`, `services/feedback_service.py`, `models/feedback.py` (card_interactions extensions) |
| **User Feedback — Layer 1 (FR47-FR49)** | `features/teaching-feed/components/CardFeedbackBar.tsx`, `ReportIssueForm.tsx`, `hooks/use-card-feedback.ts` | `api/v1/feedback.py`, `services/feedback_service.py`, `models/feedback.py` (card_feedback table) |
| **User Feedback — Layer 2 (FR50-FR51)** | `features/teaching-feed/components/FollowUpPanel.tsx` | `api/v1/feedback.py` (PATCH reason chip) |
| **User Feedback — Layer 3 (FR52-FR55)** | `features/teaching-feed/components/MilestoneFeedbackCard.tsx` | `api/v1/feedback.py`, `services/feedback_service.py`, `models/feedback.py` (feedback_responses table) |

**Cross-Cutting Concerns → Location:**

| Concern | Frontend | Backend |
|---|---|---|
| **Authentication** | `lib/auth/`, `app/api/auth/` | `core/security.py`, `api/deps.py` |
| **i18n** | `i18n/`, `proxy.ts` | `agents/education/prompts.py` (LLM language param) |
| **Error handling** | `app/error.tsx`, feature error boundaries | `core/exceptions.py`, `main.py` (exception handlers) |
| **Logging** | Browser console (dev) | `core/logging.py` (structured JSON) |
| **Tier gating** | Feature-level conditional rendering | `api/deps.py` (FastAPI dependency) |
| **User feedback** | `features/teaching-feed/` (feedback components + hooks) | `api/v1/feedback.py`, `services/feedback_service.py`, `models/feedback.py` |

### Integration Points

**Internal Communication:**

| From | To | Mechanism | Trigger |
|---|---|---|---|
| `api/uploads.py` | `tasks/pipeline_tasks.py` | Celery `apply_async()` | File upload received |
| `tasks/pipeline_tasks.py` | `agents/pipeline.py` | Direct function call | Task picked up by worker |
| `agents/education/node.py` | `rag/retriever.py` | Direct function call | Education agent activated |
| `api/jobs.py` | Redis | `hget/hset` | Job status poll / SSE stream |
| `tasks/pipeline_tasks.py` | Redis | `hset` | Pipeline progress update |
| `api/v1/feedback.py` | `services/feedback_service.py` | Direct function call | Card vote, issue report, milestone response, implicit signal batch |
| `services/feedback_service.py` | PostgreSQL | SQLModel async | Store feedback, compute engagement scores, check frequency caps |
| Frontend `use-card-interactions.ts` | `api/v1/feedback.py` | HTTPS REST (batched POST) | Implicit signals sent on card leave/swipe |
| Frontend `use-card-feedback.ts` | `api/v1/feedback.py` | HTTPS REST | Thumbs vote, issue report, get persisted vote state |

**External Integrations:**

| Integration | Backend Location | Protocol |
|---|---|---|
| **LLM APIs (Claude/GPT)** | `agents/*/node.py` | HTTPS, API key auth |
| **AWS Cognito** | `core/security.py` | JWKS endpoint for JWT validation |
| **AWS S3** | `services/upload_service.py` | boto3 SDK |
| **AWS SES** | `services/notification_service.py` | boto3 SDK |
| **Fondy (payments)** | `services/subscription_service.py` | Webhook + REST API |
| **LemonSqueezy** | `services/subscription_service.py` | Webhook + REST API |
| **Monobank API** | `agents/ingestion/parsers/monobank.py` | REST API (future: webhook) |

**Data Flow (Upload → Insights):**

```
1. User uploads CSV → Frontend UploadDropzone
2. Frontend POST /api/v1/uploads → FastAPI validates file, stores to S3
3. FastAPI creates ProcessingJob, queues Celery task → HTTP 202 + jobId
4. Frontend opens SSE stream GET /api/v1/jobs/{id}/stream
5. Celery worker picks up task, runs LangGraph pipeline:
   a. Ingestion Node: Parse CSV (Windows-1251) → structured transactions
   b. Categorization Node: MCC + LLM → categorized transactions
   c. Pattern Detection Node: Recurring, trends, anomalies
   d. Triage Node: Severity scoring → ranked findings
   e. Education Node: RAG retrieval + LLM generation → insight cards
6. Each node updates Redis with progress → SSE pushes to frontend
7. Pipeline complete: insights stored in PostgreSQL
8. Frontend receives job-complete event, fetches Teaching Feed
```

**Data Flow (Feedback Loop — Layers 0-2):**

```
1. User views a Teaching Feed card
2. Frontend use-card-interactions hook starts tracking: time_on_card_ms, education_expanded, depth_reached
3. On card leave/swipe: frontend batches implicit signals → POST /api/v1/cards/interactions
4. Backend feedback_service computes engagement_score, stores in card_interactions
5. (Optional) User taps thumbs-up/down → POST /api/v1/feedback/cards/{id}/vote
6. Backend stores vote in card_feedback table, returns feedback ID
7. (On thumbs-down) Frontend shows FollowUpPanel with reason chips
8. User selects chip → PATCH /api/v1/feedback/{id} with reason_chip
9. (On issue report) User taps flag → ReportIssueForm → POST /api/v1/feedback/cards/{id}/report
10. Periodic batch: feedback_service aggregates thumbs-down rates per topic cluster
11. Clusters exceeding >30% thumbs-down (min 10 votes) → auto-flagged for RAG corpus review
```

### Development Workflow

**Local Development:**

```bash
# Terminal 1: Start infrastructure
docker-compose up -d  # PostgreSQL + Redis

# Terminal 2: Start backend
cd backend && uv run uvicorn app.main:app --reload --port 8000

# Terminal 3: Start Celery worker
cd backend && uv run celery -A app.tasks.celery_app worker --loglevel=info

# Terminal 4: Start frontend
cd frontend && npm run dev  # Next.js on port 3000
```

**docker-compose.yml services:**

| Service | Image | Ports | Purpose |
|---|---|---|---|
| `postgres` | `pgvector/pgvector:pg16` | `5432:5432` | PostgreSQL + pgvector |
| `redis` | `redis:7-alpine` | `6379:6379` | Celery broker + caching |

**Environment Files:**

| File | Location | Contents |
|---|---|---|
| `frontend/.env.local` | Frontend | `NEXT_PUBLIC_API_URL`, Cognito client ID, NextAuth secret |
| `backend/.env` | Backend | `DATABASE_URL`, `REDIS_URL`, Cognito pool ID, AWS credentials, LLM API keys |
| `*.env.example` | Both | Template with all vars (no secrets) |

## Architecture Validation Results

### Coherence Validation ✅

**Decision Compatibility:**

All technology choices work together without conflicts:
- Next.js 16.1 (TypeScript) ↔ FastAPI (Python) communicate via REST + generated OpenAPI client — no version conflicts
- SQLModel (SQLAlchemy 2.x + Pydantic v2) is fully compatible with FastAPI's native Pydantic v2 integration
- pgvector 0.8.x works within PostgreSQL 16.x via RDS — OpenAI text-embedding-3-small 1536-dimension vectors are within pgvector's capabilities
- Celery + Redis 7.x is a proven combination; ElastiCache supports the required Redis version
- TanStack Query v5 + Next.js 16.1 App Router are compatible — TanStack Query has full RSC support
- shadcn/ui CLI v4 + Tailwind CSS 4.x + unified radix-ui package are designed to work together
- next-intl v4.8.x supports Next.js 16's `proxy.ts` convention (documented in patterns)
- AWS App Runner + ECS Fargate + RDS + ElastiCache + Cognito + S3 + SES are all within the same AWS ecosystem with IAM-based access

**Pattern Consistency:**

- Naming conventions are consistently defined across all three layers: snake_case (Python/DB) → camelCase (API JSON via Pydantic alias_generator) → camelCase (TypeScript)
- The cross-lingual naming bridge (Pydantic `alias_generator=to_camel`) eliminates the most common source of naming conflicts in dual-stack projects
- File naming follows language conventions: PascalCase.tsx for components, snake_case.py for Python modules, kebab-case for routes
- SSE event names (kebab-case) are consistent with API endpoint naming

**Structure Alignment:**

- Project structure directly supports the 5-agent pipeline architecture with dedicated `agents/` subdirectories per agent
- Feature-folder organization in frontend maps 1:1 to PRD features (teaching-feed including feedback UI, upload, auth, profile, queries, settings)
- Backend layer separation (api → services → agents → models → core) enforces clean dependency directions
- The `shared/openapi/` directory supports the OpenAPI-generated client workflow

### Requirements Coverage Validation ✅

**Feature Coverage:**

| PRD Feature | Architecture Support | Status |
|---|---|---|
| Statement Upload & Parsing | S3 storage + Celery async + Ingestion Agent + Monobank parser | ✅ Fully covered |
| Multi-Agent AI Pipeline | LangGraph StateGraph, 5 agent nodes, Celery workers on ECS Fargate | ✅ Fully covered |
| Teaching Feed | REST API with union-type cards, cursor pagination, severity triage, SSE streaming | ✅ Fully covered |
| User Feedback — Layer 0 (FR45-FR46) | card_interactions extensions (time, expansion, depth, velocity), engagement_score computation | ✅ Fully covered |
| User Feedback — Layer 1 (FR47-FR49) | card_feedback table, thumbs up/down UI, issue reports, privacy/deletion integration | ✅ Fully covered |
| User Feedback — Layer 2 (FR50-FR51) | FollowUpPanel with reason chips on thumbs-down, occasional thumbs-up follow-up | ✅ Fully covered |
| User Feedback — Layer 3 (FR52-FR55) | feedback_responses table, MilestoneFeedbackCard, frequency caps, RAG auto-flagging | ✅ Fully covered |
| Cumulative Financial Profile | Dedicated model + service + API endpoint + profile feature folder | ✅ Fully covered |
| Subscription Detection | Pattern Detection Agent + recurring charge detector | ✅ Fully covered |
| Basic Predictive Forecasts | Pattern Detection Agent + trends detector | ✅ Fully covered |
| Pre-built Data Queries | Dedicated queries API endpoint + frontend feature folder | ✅ Fully covered |
| Bilingual Support | next-intl (UI) + OpenAI text-embedding-3-small cross-lingual embeddings (RAG) + bilingual prompts + locale formatting | ✅ Fully covered |
| Email Notifications | SES + Celery notification tasks + settings UI | ✅ Fully covered |
| Freemium Model | Subscription model + tier-gating dependency + Fondy/LemonSqueezy integration | ✅ Fully covered |
| User Auth & Data Persistence | Cognito + NextAuth.js + JWT middleware + RLS + cascading delete | ✅ Fully covered |

**Non-Functional Requirements Coverage:**

| NFR | Architectural Support | Status |
|---|---|---|
| Security (AES-256, TLS 1.3, tenant isolation) | RDS encryption, HTTPS everywhere, RLS, Cognito JWT | ✅ Covered |
| Privacy (one-click deletion, consent) | Cascading delete across all stores, DataDeletion component | ✅ Covered |
| Performance (>80% first-upload completion) | Async pipeline with SSE progress, fast parsing feedback | ✅ Covered |
| Bilingual | next-intl, OpenAI text-embedding-3-small, bilingual RAG content, locale formatting | ✅ Covered |
| Reliability (graceful agent failures) | LangGraph checkpointing, Celery retries, partial results | ✅ Covered |
| Scalability | ECS Fargate auto-scaling, App Runner scale-to-zero, connection pooling | ✅ Covered |
| Compliance (Ukrainian DPL, audit) | Structured JSON logging, raw data preservation, audit trails, compliance audit trail for financial data access events (middleware-level) | ✅ Covered |
| Data Integrity | ACID transactions, dual storage (raw JSONB + normalized), DB constraints | ✅ Covered |

### Implementation Readiness Validation ✅

**Decision Completeness:**

- All critical technology choices include specific version numbers
- Implementation patterns cover 25+ conflict points across 5 categories
- Enforcement guidelines provide 9 explicit rules for AI agents
- Pattern verification tooling is specified (ESLint, Ruff, Pydantic aliases, CI checks)

**Structure Completeness:**

- Complete directory structure with every file and its purpose annotated
- Component boundaries defined with explicit "Depends On" / "Never Depends On" tables for both frontend and backend
- Integration points mapped for both internal (Celery, Redis, direct calls) and external (LLM APIs, Cognito, S3, SES, Fondy, LemonSqueezy)
- Requirements-to-structure mapping table links every PRD feature to specific directories

**Pattern Completeness:**

- Naming conventions comprehensive across DB, API, and code layers
- Communication patterns (SSE events, Celery tasks, logging) fully specified
- Process patterns (error handling, loading states, validation) documented per layer
- Data format rules (dates, money, IDs, nulls, currency codes) explicitly standardized

### Gap Analysis Results

**Gaps Identified & Resolutions:**

| # | Gap | Priority | Resolution |
|---|---|---|---|
| 1 | **Embedding model hosting** — resolved for MVP; re-evaluated in Epic 9 | Resolved | **MVP decision:** OpenAI text-embedding-3-small via OpenAI API (1536 dimensions). **Phase 2 re-evaluation (Epic 9 Story 9.3):** RAG evaluation harness benchmarks 3-small vs 3-large vs Titan v2 vs Cohere multilingual-v3. Decision gate — migrate only if a candidate clearly wins on the Ukrainian + English retrieval benchmark. Embeddings are decoupled from LLM-provider migration; staying on OpenAI is a valid outcome. See Bedrock Migration & AgentCore Architecture section below. |
| 2 | **LLM provider** not explicitly chosen — Claude vs GPT vs both | Critical | **Recommended:** Claude (Anthropic) as primary LLM for all 5 agents. GPT-4o as fallback provider. Provider abstraction via LangChain's LLM interface allows easy switching |
| 3 | **Database migration workflow** not detailed — who runs migrations, when | Important | **Recommended:** Alembic migrations run as a pre-deployment step in CI/CD pipeline. `alembic upgrade head` executed before new API version starts. Never auto-migrate in app startup |
| 4 | **APM/monitoring tooling** deferred but observability is a day-one NFR | Nice-to-have | **Recommended:** Start with structured JSON logging to CloudWatch (free with AWS). Add Sentry for error tracking in MVP. Evaluate Datadog/New Relic post-MVP |

### Architecture Completeness Checklist

**✅ Requirements Analysis**

- [x] Project context thoroughly analyzed (11 features, 4 domains, 8 NFRs)
- [x] Scale and complexity assessed (High — 12-15 major components)
- [x] Technical constraints identified (6 constraints with impact analysis)
- [x] Cross-cutting concerns mapped (8 concerns)

**✅ Architectural Decisions**

- [x] Critical decisions documented with versions (PostgreSQL 16, pgvector 0.8, Redis 7, Next.js 16.1, etc.)
- [x] Technology stack fully specified (frontend, backend, infra, auth, payments)
- [x] Integration patterns defined (REST, SSE, Celery, OpenAPI client generation)
- [x] Performance considerations addressed (async pipeline, SSE progress, cursor pagination)

**✅ Implementation Patterns**

- [x] Naming conventions established (DB, API, code — all three layers)
- [x] Structure patterns defined (frontend feature folders, backend domain modules)
- [x] Communication patterns specified (SSE events, Celery tasks, logging)
- [x] Process patterns documented (error handling, loading states, validation)

**✅ Project Structure**

- [x] Complete directory structure defined (every file annotated)
- [x] Component boundaries established (dependency tables for frontend + backend)
- [x] Integration points mapped (internal + external, 12 boundary definitions)
- [x] Requirements to structure mapping complete (11 features → directories)

### Architecture Readiness Assessment

**Overall Status:** READY FOR IMPLEMENTATION

**Confidence Level:** High — all 11 PRD features have clear architectural support, all NFRs are addressed, and implementation patterns are comprehensive enough to guide AI agents consistently.

**Key Strengths:**

1. **Comprehensive cross-language bridge** — Pydantic alias_generator eliminates the #1 source of dual-stack naming conflicts
2. **Clear layer boundaries** — Explicit "Never Depends On" rules prevent circular dependencies
3. **Financial data integrity** — Dual storage (raw JSONB + normalized) preserves audit trail while enabling AI processing
4. **Async-first design** — Upload → Celery → SSE pattern prevents blocking on expensive AI operations
5. **Bilingual by design** — OpenAI text-embedding-3-small cross-lingual embeddings + next-intl + bilingual prompts baked into architecture from day one
6. **Security depth** — Three-layer auth (Cognito JWT → FastAPI middleware → PostgreSQL RLS) with encryption at rest and in transit

**Areas for Future Enhancement:**

1. GraphQL evaluation post-MVP if Teaching Feed queries become complex
2. ~~Migration to AWS Bedrock (embeddings + LLM) when chat-with-finances epic requires AgentCore~~ — **Promoted to Epic 9 (AI Infra Readiness) and Epic 10 (Chat-with-Finances + AI Safety). See "Bedrock Migration & AgentCore Architecture" and "AI Safety Architecture" sections below.**
3. CDN/edge caching for AI-generated insights that don't change frequently
4. Multi-region deployment for latency optimization
5. Advanced APM (Datadog/New Relic) for production observability

## Bedrock Migration & AgentCore Architecture (Phase 2)

This section replaces the prior "migration deferred" note. Scope is driven by Epic 9 (infra readiness) and Epic 10 (chat + AI safety).

### Provider Strategy — Multi-Provider, Env-Driven

[backend/app/agents/llm.py](../../backend/app/agents/llm.py) remains the single LLM abstraction point. It becomes multi-provider, selected via `LLM_PROVIDER` env var:

- `anthropic` — direct Anthropic API (kept for local-dev fallback and cost comparison; preserved by Story 9.5a's refactor and added alongside Bedrock in Story 9.5b)
- `openai` — direct OpenAI API (kept for regression parity; not a prod runtime target)
- `bedrock` — AWS Bedrock (Claude on Bedrock; **prod runtime target**; required for AgentCore and Guardrails)

**Pinned model IDs** live in `backend/app/agents/models.yaml` (created in Story 9.5a), versioned in git. The file maps a logical role (e.g. `agent_default`, `agent_cheap`, `chat_default`) to a provider-qualified model ID, so agent code never hardcodes a model. Exact Bedrock model ARNs for `eu-central-1` are confirmed by Story 9.4 before Story 9.5b pins them; updates go through ordinary PR review.

**Runtime failover policy (MVP): none.** `LLM_PROVIDER` is static per deployment. Provider outages surface as pipeline / chat failures (user-visible retry in chat; existing retry/backoff in Celery for batch). Cross-provider runtime failover is rejected for MVP because it doubles the error surface and complicates observability — revisit only if availability SLOs (see *Observability & Alarms* in AI Safety section) are breached in prod. Tracked as **TD-039** in the tech-debt register.

Switching providers requires an env flip + redeploy, not a code change. The regression suite at `backend/tests/agents/providers/` (Story 9.5c) runs Epic 3 + 8 agents on all three providers and is the source of truth for provider equivalence.

### Local-Dev Provider Policy

Local dev **prefers Bedrock** when developer AWS credentials + region access are available — matches prod behavior and catches provider-specific regressions earliest. Developers without Bedrock access (onboarding, offline, sandbox) fall back to `LLM_PROVIDER=anthropic` with their own API key. CI exercises all three providers via Story 9.5c's regression job. Staging and prod pin `LLM_PROVIDER=bedrock`.

### Region Strategy

Primary region: `eu-central-1` (aligns with existing infra + GDPR posture). **Epic 9 Story 9.4 is a blocking spike** — validates Bedrock model availability (Claude haiku/sonnet class) and AgentCore availability in eu-central-1. Outcomes:

- If available → proceed
- If model gap only → cross-region inference profile (e.g., invoke via us-east-1 with a formal data-residency review — see below)
- If AgentCore unavailable → either wait, or pivot region with cost/latency/residency trade-off analysis

**Data-residency review for cross-region inference.** Owner: DPO + Legal (not Dev Team). Criteria: (1) whether the inference payload contains raw user PII or only pseudonymized/aggregated content; (2) whether the target region offers an equivalent data-protection regime or a lawful transfer mechanism (SCC, adequacy); (3) retention and logging posture at the model endpoint. Decision logged as an ADR under `docs/adr/` and referenced from this section. No cross-region inference traffic ships before the ADR is signed off.

### AgentCore Deployment Model

The Chat Agent runs on **AWS-managed AgentCore runtime**, not on ECS Celery workers. Rationale: session state, multi-turn memory, and tool orchestration are AgentCore's native primitives; reimplementing them on Celery is non-trivial and throws away the main reason Epic 10 pulled the Bedrock migration forward. Boundary:

- **Celery ECS workers** — batch agents (Epics 3/8), invoked via `llm.py` → Bedrock `InvokeModel`
- **AgentCore runtime (AWS-managed)** — Chat Agent only; invoked via `bedrock-agentcore:*` from FastAPI handlers

VPC attachment, IAM, and observability plumbing for AgentCore are provisioned in Stories 9.7 and 10.4a.

### IAM & Infrastructure

**Celery ECS task role** (batch agents):

- `bedrock:InvokeModel` on allowlisted model ARNs (sourced from `models.yaml`)
- `bedrock:ApplyGuardrail` on the configured Guardrail ID

**FastAPI ECS task role** (new scope for chat):

- `bedrock-agentcore:InvokeAgent` / `GetSession` / `DeleteSession` scoped to the Chat Agent's AgentCore identifier
- No direct `bedrock:InvokeModel` — chat model calls flow through AgentCore

**Config surface:** Non-secret config (model ARNs, region, Guardrail ID, AgentCore runtime ID) lives in ECS task-definition env vars, managed via Terraform. Provider API keys continue to use the existing `kopiika-ai/<env>/llm-api-keys` Secrets Manager entry.

CloudWatch cost-allocation tags on all Bedrock / AgentCore resources: `feature=chat`, `epic=10`, `env=<env>`.

### Cost Controls

Tags alone are visibility, not control. Minimum cost guardrails for Phase 2:

- **AWS Budgets** — monthly budget per `feature` tag (chat, batch) with 50 / 80 / 100% alerts routed to email + Slack. Defined in Terraform, reviewed on PR.
- **Per-user daily token cap** — enforced in `llm.py` for batch agents (tokens/user/day) and in the Chat Agent's rate-limit envelope (see *Rate Limits* in AI Safety section). Exceeding the cap triggers a principled refusal (`CHAT_REFUSED` with `reason=rate_limited`), not a silent throttle.
- **CloudWatch anomaly detection** on `feature=chat` cost metric — ≥ 3σ over trailing 7-day baseline → page on-call. Tuned after first 30 days of prod data.

Advanced cost governance (org-level cost dashboards, per-tenant chargeback) is tracked as tech debt.

### Embedding Model — Decision Deferred

Embeddings are decoupled from LLM migration (they run at ingestion + query time, not inside agent execution). No re-seed until the RAG eval harness (Story 9.1) has a baseline on current OpenAI 3-small, and Story 9.3 compares candidates. If the winner differs from 3-small, Story 9.6 runs the Alembic migration (pgvector dim change, HNSW rebuild, re-seed).

### Pipeline Orchestration — Celery vs Step Functions (Optional Evaluation)

Epic 9 Story 9.8 is a time-boxed evaluation spike comparing the current Celery+Redis broker architecture with AWS Step Functions or AWS Batch for the Epic 3/8 pipeline (categorize → pattern detection → triage → education → write). Outcome is a recommendation doc only — any actual migration requires separate approval and a dedicated epic. Default: stay on Celery.

### Related Artifacts

- Epic 9 (Stories 9.1–9.8): [epics.md](epics.md)
- Sprint change proposal: [sprint-change-proposal-2026-04-18.md](sprint-change-proposal-2026-04-18.md)
- Tech-debt register: [../../docs/tech-debt.md](../../docs/tech-debt.md) — **TD-039** (runtime failover), advanced cost governance, cross-region inference ADR
- AI Safety Architecture (below) — consumes the provider, IAM, and cost plumbing defined here

## AI Safety Architecture (Epic 10)

**Scope — phased.** Applies Epic 10 onward (conversational AI). Batch-pipeline AI security lives in the earlier Security section and is unchanged by Phase 2; this section supersedes it for the Chat Agent and any future conversational surface.

### Threat Model

Attacker profile: authenticated user (self or via account takeover) interacting through chat. Defense prioritizes the following attacker goals, each mapped to the layers below:

| Attacker goal | Primary defenses |
|---|---|
| Cross-user data exfiltration via prompt manipulation | Agent layer (tool allowlist + user-scoped data access), System-prompt layer, Guardrails output |
| System-prompt / policy extraction | System-prompt layer (anchoring, canaries), Guardrails output, *Canary Detection* loop |
| Unsafe or out-of-scope advice (illegal activity, self-harm, unauthorized financial-advice scope) | Guardrails input + output (denied topics) |
| Tool abuse (write, admin, network, filesystem) | Agent layer — no such tools exposed; allowlist enforced at AgentCore |
| PII leakage in output | Guardrails output PII redaction; output scan |
| Cost exhaustion / denial-of-wallet | *Rate Limits*, per-user token caps, cost observability (see Bedrock section) |
| Refusal bypass via jailbreak / role-play / translation | Input blocklist, Guardrails, system-prompt anchoring, safety harness as regression gate |

Trust boundary: everything the user sends is hostile input; everything the model emits is untrusted output until Guardrails + grounding have cleared it.

### Defense-in-Depth Layers

1. **Input layer** — Validator (length caps, character-class allowlist, known-jailbreak-pattern blocklist) runs before agent invocation. Blocklist lives at `backend/app/agents/chat/jailbreak_patterns.yaml`, PR-reviewed, covered by the safety harness.
2. **Guardrails layer (input)** — AWS Bedrock Guardrails: content filters, denied topics (illegal activity, self-harm, unauthorized financial-advice scope), PII redaction, word filters.
3. **System-prompt layer** — Role isolation ("You are a read-only advisor..."), instruction anchoring, canary tokens to detect extraction attempts (see *Canary Detection*).
4. **Agent layer** — AgentCore tool allowlist enforced at runtime; tools scoped to the authenticated user's data only; no filesystem / network / admin / write tools exposed. Session isolation is AgentCore-native (per-user session IDs).
5. **Guardrails layer (output)** — Output content filters, PII redaction, contextual grounding checks.
6. **Grounding enforcement** — Bedrock Guardrails contextual-grounding threshold (initial target ≥ 0.85; tuned via Story 10.6a harness). Ungrounded data-specific claims are **blocked, not regenerated** — the Chat Agent returns a principled refusal (`CHAT_REFUSED` with `reason=ungrounded`). Regenerating through the filter has historically laundered hallucinations past grounding checks; we intentionally avoid that pattern.
7. **Observability layer** — CloudWatch metrics + alarms (thresholds in *Observability & Alarms*).

### Canary Detection

Canary tokens are high-entropy strings injected into the system prompt and rotated monthly via Secrets Manager (`kopiika-ai/<env>/chat-canaries`). Every model output passes a regex scan before streaming to the client. Any canary match:

- Blocks the turn (`CHAT_REFUSED` with `reason=prompt_leak_detected`)
- Emits the `CanaryLeaked` CloudWatch metric
- Pages on-call via the severity-1 security alarm path
- Triggers a post-incident corpus update in Story 10.8a

### Memory & Session Bounds

- **Per-session context window:** 20 turns or 8k tokens, whichever is first. Older turns are summarized server-side, not dropped silently.
- **Per-user cross-session memory:** not implemented in Epic 10. Each session starts fresh. Persistent per-user memory is tracked as **TD-040** — FR66 is satisfied by durable chat *history* (viewable, resumable, deletable), not by cross-session *context carry-over*.
- **Concurrency:** 10 concurrent sessions per user (matches *Rate Limits*).

### Rate Limits

Single source of truth for chat throttling — implemented in Story 10.11 (rate-limit envelope previously co-listed under 10.4 was consolidated into 10.11 to remove the duplication):

- **60 messages per hour per user** (soft-block with retry guidance)
- **10 concurrent sessions per user** (soft-block)
- **Per-user daily token cap** — see Bedrock *Cost Controls*; exceeding returns `CHAT_REFUSED` with `reason=rate_limited`
- **Global per-IP cap** at the API-gateway layer (reuses existing limit) — abuse scenario only

### Consent Drift Policy

`chat_sessions.consent_version_at_creation` captures the `chat_processing` consent version that authorized the session. Policy:

- **Active sessions continue under their captured version** (in-flight conversations aren't interrupted mid-turn by a consent bump).
- **New sessions require the current version** — frontend gate re-prompts if the user's consent is stale.
- **Consent revoke** terminates active sessions, cancels in-flight streaming turns, and triggers the deletion cascade (`chat_sessions` → `chat_messages`) per FR70 / FR71.

### Safety Test Harness — CI Gate

`backend/tests/ai_safety/` contains the red-team prompt corpus:

- OWASP LLM Top-10 mapped (prompt injection, data leakage, unauthorized tool use, etc.)
- Known jailbreak patterns (DAN-style, role-play bypass, translation-based)
- Ukrainian-language adversarial prompts
- Canary-token extraction attempts
- Cross-user data probes

Runner invokes the Chat Agent with each prompt and validates refusal / block / grounding behavior. **CI gate: ≥ 95% pass rate required for any merge touching agent code, prompts, tools, or Guardrails config.** Corpus reviewed and expanded quarterly.

### Observability & Alarms

Baseline thresholds (implemented in Story 10.9; tuned after 30 days of prod data):

| Metric | Warn | Page |
|---|---|---|
| Guardrails input-block rate (5-min window) | ≥ 5% sustained 15m | ≥ 15% sustained 5m |
| Grounding-block rate (5-min window) | ≥ 10% sustained 15m | ≥ 25% sustained 5m |
| `CanaryLeaked` count | — | any (sev-1) |
| Refusal rate (all causes, 30m window) | ≥ 20% | — |
| Per-user token-spend anomaly | ≥ 3σ vs trailing 7-day | ≥ 5σ |
| P95 streaming first-token latency | ≥ 2s | ≥ 5s |

Incident-response runbook for each metric lives in [../../docs/operator-runbook.md](../../docs/operator-runbook.md) (Chat section, owned by Story 10.9).

### Chat Agent Component

New component alongside the existing batch agents (see [backend/app/agents/](../../backend/app/agents/) for the authoritative list):

- Session handler on AgentCore (stateful, multi-turn, per-user session isolation)
- Tool manifest (read-only allowlist): user transactions, user profile, teaching-feed history, RAG corpus
- Memory policy: per *Memory & Session Bounds* above; retention aligned with `chat_processing` consent
- Guardrails attachment: input + output, with grounding threshold configured
- Rate-limit envelope: per *Rate Limits* above

### Success Metrics (SLO)

- 100% of chat turns traverse Bedrock Guardrails (input + output)
- Red-team corpus pass rate ≥ 95% (CI gate)
- Grounding rate ≥ 90% measured by LLM-as-judge in the RAG harness (Story 10.6a)

### Data Model Additions

New tables (Alembic migration in Epic 10):

- `chat_sessions` — `id` UUID PK, `user_id` UUID FK (cascade delete), `created_at` timestamptz, `last_active_at` timestamptz, `consent_version_at_creation` text
- `chat_messages` — `id` UUID PK, `session_id` UUID FK (cascade delete), `role` enum(`user` | `assistant` | `system`), `content` text, `redaction_flags` JSONB (shape: `{"pii_types": ["email" | "iban" | "card" | ...], "filter_source": "input" | "output"}`), `guardrail_action` enum(`none` | `blocked` | `modified`), `created_at` timestamptz

Deletion cascade aligned with FR31 + FR70: account deletion → `chat_sessions` deletion → `chat_messages` deletion.

Operational indexes: `chat_sessions(user_id, last_active_at desc)` for session list; `chat_messages(session_id, created_at)` for transcript render; partial index on `chat_messages(guardrail_action) WHERE guardrail_action != 'none'` for safety-monitoring queries.

### API Pattern — Chat Streaming

Chat uses server-sent events (SSE) for token streaming, consistent with the existing SSE pattern for pipeline progress. Error envelope on Guardrails block, grounding refusal, or rate-limit:

```json
{
  "error": "CHAT_REFUSED",
  "reason": "guardrail_blocked | ungrounded | rate_limited | prompt_leak_detected",
  "correlation_id": "<uuid>",
  "retry_after_seconds": null
}
```

`correlation_id` surfaces in the frontend refusal UX so support can triage an incident without the user knowing the internal rationale. `reason` is intentionally coarse — no leakage of specific filter matches.

### Related Artifacts

- Epic 10 (Stories 10.1–10.11): [epics.md](epics.md)
- Bedrock Migration & AgentCore section (above) — provider, cost, IAM plumbing consumed here
- Sprint change proposal: [sprint-change-proposal-2026-04-18.md](sprint-change-proposal-2026-04-18.md)
- Tech-debt register: [../../docs/tech-debt.md](../../docs/tech-debt.md) — **TD-040** (persistent cross-session memory), **TD-039** (runtime failover)
- Operator runbook: [../../docs/operator-runbook.md](../../docs/operator-runbook.md) — Chat section

### Implementation Handoff

**AI Agent Guidelines:**

- Follow all architectural decisions exactly as documented — versions, naming conventions, file locations
- Use implementation patterns consistently across all components
- Respect project structure and component boundaries (check "Never Depends On" tables)
- Refer to this document for all architectural questions — it is the single source of truth
- When in doubt about a pattern, check the Enforcement Guidelines section

**First Implementation Priority:**

1. Initialize monorepo: `create-next-app` for frontend, `uv init` for backend
2. Set up `docker-compose.yml` with PostgreSQL (pgvector) + Redis
3. Implement Cognito auth flow (frontend + backend)
4. Create database models + initial Alembic migration
5. Build file upload endpoint with S3 storage + Celery task queuing
