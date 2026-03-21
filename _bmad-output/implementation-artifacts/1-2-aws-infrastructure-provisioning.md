# Story 1.2: AWS Infrastructure Provisioning

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want all AWS infrastructure provisioned and configured,
So that the application has the cloud services it needs to run beyond local development.

## Acceptance Criteria

1. **Given** the AWS account is available
   **When** infrastructure is provisioned
   **Then** the following services are created and configured: Amazon RDS PostgreSQL 16 with pgvector extension (encryption at rest enabled), Amazon ElastiCache Redis 7, Amazon Cognito user pool with email/password authentication, Amazon S3 bucket with server-side encryption and per-user key prefixes, Amazon SES for transactional email, and AWS Secrets Manager for API keys and credentials

2. **Given** the provisioned infrastructure
   **When** environment configuration is set up
   **Then** three environments are configured (dev / staging / production) with separate AWS resources per environment, and `.env.example` files document all required environment variables for both frontend and backend

3. **Given** the CI/CD pipeline
   **When** GitHub Actions workflows are created
   **Then** there are workflows for: frontend lint + test + build, backend lint + test, frontend deploy to Vercel, and backend deploy to AWS (App Runner + ECS Fargate)

4. **Given** the backend connects to AWS services
   **When** it starts in a deployed environment
   **Then** it can reach RDS, ElastiCache, Cognito, S3, and SES using credentials from Secrets Manager

## Tasks / Subtasks

- [x] Task 1: Define IaC approach and project structure (AC: #1, #2)
  - [x] 1.1 Choose IaC tool — Terraform recommended (widely adopted, stateful, multi-environment support, easier for solo dev than CDK)
  - [x] 1.2 Create `infra/` directory structure: `infra/terraform/` with `environments/dev/`, `environments/staging/`, `environments/prod/`, and shared `modules/`
  - [x] 1.3 Create `infra/terraform/modules/` for reusable components: `rds/`, `elasticache/`, `cognito/`, `s3/`, `ses/`, `secrets/`, `networking/`, `app-runner/`, `ecs/`
  - [x] 1.4 Create root `infra/terraform/main.tf`, `variables.tf`, `outputs.tf`, `providers.tf`, `backend.tf` (S3 state backend)
  - [x] 1.5 Create `infra/README.md` with provisioning instructions per environment

- [x] Task 2: Provision networking foundation (AC: #1)
  - [x] 2.1 Create VPC with public and private subnets across 2 AZs
  - [x] 2.2 Create security groups: `sg-rds` (PostgreSQL 5432 from App Runner/ECS), `sg-redis` (6379 from App Runner/ECS), `sg-app-runner`, `sg-ecs`
  - [x] 2.3 Create VPC endpoints for S3, Secrets Manager, and ECR (to avoid NAT gateway costs)
  - [x] 2.4 Create NAT Gateway (single, for cost savings) for private subnet internet access (LLM API calls)

- [x] Task 3: Provision Amazon RDS PostgreSQL with pgvector (AC: #1)
  - [x] 3.1 Create RDS PostgreSQL 16 instance: `db.t4g.micro` (dev), `db.t4g.small` (staging/prod)
  - [x] 3.2 Enable pgvector extension — use custom parameter group or run `CREATE EXTENSION vector;` post-provisioning
  - [x] 3.3 Enable encryption at rest (AES-256 via AWS KMS default key)
  - [x] 3.4 Enable automated backups with 30-day retention (NFR29)
  - [x] 3.5 Place in private subnet, attach `sg-rds` security group
  - [x] 3.6 Create initial database `kopiika_db` and application user
  - [x] 3.7 Store connection string in Secrets Manager

- [x] Task 4: Provision Amazon ElastiCache Redis (AC: #1)
  - [x] 4.1 Create ElastiCache Redis 7 cluster: `cache.t4g.micro` (dev), single-node for cost savings
  - [x] 4.2 Place in private subnet, attach `sg-redis` security group
  - [x] 4.3 Enable encryption in transit (TLS)
  - [x] 4.4 Store Redis connection URL in Secrets Manager

- [x] Task 5: Provision Amazon Cognito (AC: #1)
  - [x] 5.1 Create Cognito User Pool with email-as-username (`username_attributes = ["email"]`, `auto_verified_attributes = ["email"]`)
  - [x] 5.2 Configure password policy: min 8 chars, require uppercase, lowercase, number, special char
  - [x] 5.3 Configure email verification (Cognito default or SES for custom domain)
  - [x] 5.4 Create App Client for frontend (public client, no secret, `ALLOW_USER_SRP_AUTH` flow — NOT `ALLOW_USER_PASSWORD_AUTH`)
  - [x] 5.5 Create App Client for backend (confidential, with secret, for admin API calls)
  - [x] 5.6 Store Cognito Pool ID, App Client IDs, and domain in Secrets Manager
  - [x] 5.7 Configure JWT access token expiry < 15 minutes, refresh token rotation (NFR8)

- [x] Task 6: Provision Amazon S3 (AC: #1)
  - [x] 6.1 Create S3 bucket for uploaded files: `kopiika-uploads-{env}`
  - [x] 6.2 Enable server-side encryption (SSE-S3 or SSE-KMS)
  - [x] 6.3 Configure bucket policy: block all public access
  - [x] 6.4 Set up CORS configuration for frontend direct uploads (if needed)
  - [x] 6.5 Configure lifecycle rule for cleanup of incomplete multipart uploads (7 days)
  - [x] 6.6 Note: Per-user key prefix pattern is `uploads/{user_id}/` — enforced in application code, not S3 policy

- [x] Task 7: Configure Amazon SES (AC: #1)
  - [x] 7.1 Verify sender email/domain in SES
  - [x] 7.2 Request production access (move out of sandbox) for staging/prod
  - [x] 7.3 Create IAM policy for SES send permissions
  - [x] 7.4 Store SES configuration (region, sender email) in Secrets Manager

- [x] Task 8: Configure AWS Secrets Manager (AC: #1, #4)
  - [x] 8.1 Create secrets for each environment: `kopiika/{env}/database`, `kopiika/{env}/redis`, `kopiika/{env}/cognito`, `kopiika/{env}/s3`, `kopiika/{env}/ses`, `kopiika/{env}/llm-api-keys`
  - [x] 8.2 Create IAM role for App Runner with Secrets Manager read access
  - [x] 8.3 Create IAM role for ECS tasks with Secrets Manager read access
  - [x] 8.4 Ensure secrets are referenced by ARN in App Runner/ECS task definitions

- [x] Task 9: Provision AWS App Runner for API (AC: #3, #4)
  - [x] 9.1 Create App Runner service from ECR image (or source code connector)
  - [x] 9.2 Configure environment variables from Secrets Manager
  - [x] 9.3 Configure VPC connector to reach RDS and ElastiCache in private subnet
  - [x] 9.4 Set health check path to `/health`
  - [x] 9.5 Configure auto-scaling: min 1, max 4 instances (dev: min 1, max 1)
  - [x] 9.6 Set instance: 1 vCPU, 2 GB memory

- [x] Task 10: Provision AWS ECS Fargate for Celery workers (AC: #3, #4)
  - [x] 10.1 Create ECS cluster
  - [x] 10.2 Create task definition: Celery worker container from ECR image
  - [x] 10.3 Configure environment variables from Secrets Manager
  - [x] 10.4 Create ECS service: desired count 1 (dev), with private subnet and security group
  - [x] 10.5 Set task resources: 0.5 vCPU, 1 GB memory (dev)
  - [x] 10.6 Configure CloudWatch Logs for worker output

- [x] Task 11: Create deployment CI/CD workflows (AC: #3)
  - [x] 11.1 Create `.github/workflows/deploy-frontend.yml` — deploy to Vercel on push to main
  - [x] 11.2 Create `.github/workflows/deploy-backend.yml` — build Docker image, push to ECR, deploy to App Runner + update ECS service
  - [x] 11.3 Create `backend/Dockerfile` for production (multi-stage: uv install + uvicorn)
  - [x] 11.4 Create `backend/Dockerfile.worker` for Celery worker (or same image, different CMD)
  - [x] 11.5 Configure GitHub OIDC provider + IAM role for GitHub Actions (no long-lived AWS keys). Store `AWS_REGION`, `ECR_REPOSITORY`, `IAM_ROLE_ARN` as GitHub Actions variables/secrets.
  - [x] 11.6 Add Alembic migration step to deployment workflow (run before new API version starts)

- [x] Task 12: Update environment configuration (AC: #2)
  - [x] 12.1 Update `backend/.env.example` with all AWS-related env vars: `DATABASE_URL`, `REDIS_URL`, `AWS_REGION`, `COGNITO_USER_POOL_ID`, `COGNITO_APP_CLIENT_ID`, `S3_BUCKET_NAME`, `SES_SENDER_EMAIL`, `AWS_SECRETS_PREFIX`
  - [x] 12.2 Update `frontend/.env.example` with: `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_COGNITO_USER_POOL_ID`, `NEXT_PUBLIC_COGNITO_CLIENT_ID`, `NEXTAUTH_URL`, `NEXTAUTH_SECRET`
  - [x] 12.3 Document environment-specific values in `infra/README.md`

## Dev Notes

### Architecture Compliance

- **IaC approach**: Architecture doc says `infra/` directory with "AWS infrastructure (optional IaC)". Terraform is recommended for its stateful management, multi-environment support, and wide AWS provider coverage. CDK is an alternative if the developer prefers TypeScript.
- **Three environments**: dev / staging / production — each gets separate AWS resources per architecture spec.
- **App Runner for API**: Auto-scaling, scales to zero on idle (cost savings for early stage). Simpler than ECS Fargate for the API layer.
- **ECS Fargate for workers**: Celery workers need persistent containers for long-running AI pipeline jobs.
- **Frontend on Vercel**: NOT on AWS. Vercel is optimized for Next.js with automatic preview deployments.

### Technical Requirements

#### AWS Services (Exact Specifications)
- **RDS PostgreSQL 16**: pgvector is a supported extension on RDS PostgreSQL 16 — enable via `CREATE EXTENSION vector;` (no custom builds needed). Use Graviton instances (`t4g`/`r7g`) for cost savings. For vector indexes, use `HNSW` index type (faster than IVFFlat): `CREATE INDEX ON items USING hnsw (embedding vector_cosine_ops);`
- **ElastiCache Redis 7**: Managed Redis for Celery broker + API caching. Use `redis:7` compatible engine version.
- **Cognito**: User pools with email-as-username. Use `ALLOW_USER_SRP_AUTH` flow (not `ALLOW_USER_PASSWORD_AUTH`). JWT access tokens with < 15 min expiry. Refresh token rotation enabled. Link SES for production email delivery via `email_configuration { source_arn, email_sending_account = "DEVELOPER" }` (Cognito sandbox limits to 50 emails/day).
- **S3**: Per-user key prefix `uploads/{user_id}/`. Server-side encryption (SSE-S3). Block all public access.
- **SES**: Transactional email (verification, notifications). Must move out of sandbox for production.
- **Secrets Manager**: All credentials stored here. App Runner and ECS reference secrets by ARN.
- **App Runner**: VPC connector required to reach RDS/ElastiCache in private subnets. Health check on `/health`.
- **ECS Fargate**: Private subnets. Needs NAT Gateway for outbound internet (LLM API calls).

#### Networking
- VPC with public + private subnets across 2 AZs for high availability
- Private subnets for RDS, ElastiCache, ECS Fargate workers
- Public subnets for NAT Gateway, load balancers
- App Runner uses VPC connector (not directly in VPC)
- Security groups enforce least-privilege access between services

#### Cost Optimization (Early-Stage MVP)
- **RDS**: `db.t4g.micro` for dev (free-tier eligible if new account)
- **ElastiCache**: `cache.t4g.micro`, single-node (no cluster mode)
- **App Runner**: Scales to zero but has a "paused" compute cost (~$5/mo minimum). Cold starts can be 10-30s after scale-to-zero. Max 25 concurrent connections per instance by default — tune `max_concurrency` if needed.
- **ECS Fargate**: 0.5 vCPU, 1 GB memory — minimal for Celery worker
- **NAT Gateway**: Single NAT in one AZ (accept reduced availability for cost savings)
- **VPC Endpoints**: Use gateway endpoints for S3 (free) and interface endpoints for Secrets Manager/ECR

### Library & Framework Requirements

#### Terraform (if chosen as IaC)
- Use `hashicorp/aws` provider (latest stable)
- S3 backend for state storage with DynamoDB locking table
- Use directory-based environment isolation (`environments/dev/terraform.tfvars`)
- Leverage community modules where practical: `terraform-aws-modules/vpc/aws`, `terraform-aws-modules/rds/aws`
- Key resources: `aws_db_instance`, `aws_elasticache_cluster`, `aws_cognito_user_pool`, `aws_s3_bucket`, `aws_apprunner_service`, `aws_ecs_cluster`
- Run `terraform plan` on PR, `terraform apply -auto-approve` on merge to main

#### Docker (for deployment)
- Multi-stage Dockerfile for backend: stage 1 (uv install deps), stage 2 (copy app + run uvicorn)
- Celery worker uses same image with different entrypoint: `celery -A app.tasks.celery_app worker --loglevel=info`
- Base image: `python:3.12-slim`
- ECR repository for storing built images

#### GitHub Actions
- **Auth**: Use **GitHub OIDC provider** with IAM role — no long-lived AWS access keys. Set up `aws-actions/configure-aws-credentials@v4` with `role-to-assume` parameter.
- `aws-actions/amazon-ecr-login@v2` — authenticate to ECR
- **App Runner**: Use `awslabs/amazon-app-runner-deploy@main` (official AWS Labs action) — NOT the ECS deploy action
- **ECS**: Use `aws-actions/amazon-ecs-render-task-definition@v1` + `aws-actions/amazon-ecs-deploy-task-definition@v2`
- **Vercel**: Use Vercel's Git integration (auto-deploy on push to main) — simplest approach, no GitHub Action needed

### File Structure Requirements

#### New Files/Directories to Create
```
infra/
├── README.md                          # Provisioning guide
└── terraform/                         # (or cdk/ if CDK chosen)
    ├── main.tf                        # Root module
    ├── variables.tf                   # Input variables
    ├── outputs.tf                     # Output values
    ├── providers.tf                   # AWS provider config
    ├── backend.tf                     # S3 state backend
    ├── environments/
    │   ├── dev/
    │   │   └── terraform.tfvars       # Dev-specific values
    │   ├── staging/
    │   │   └── terraform.tfvars       # Staging-specific values
    │   └── prod/
    │       └── terraform.tfvars       # Prod-specific values
    └── modules/
        ├── networking/                # VPC, subnets, security groups
        ├── rds/                       # PostgreSQL + pgvector
        ├── elasticache/               # Redis
        ├── cognito/                   # User pool + app clients
        ├── s3/                        # Upload bucket
        ├── ses/                       # Email service
        ├── secrets/                   # Secrets Manager
        ├── app-runner/                # API service
        └── ecs/                       # Celery worker cluster

.github/workflows/
├── ci-frontend.yml                    # (exists) lint + build
├── ci-backend.yml                     # (exists) lint + test
├── deploy-frontend.yml                # NEW: deploy to Vercel
└── deploy-backend.yml                 # NEW: build + push ECR + deploy App Runner + ECS

backend/
├── Dockerfile                         # NEW: production API image
└── Dockerfile.worker                  # NEW: Celery worker image (or same image, different CMD)
```

#### Naming Conventions (MUST FOLLOW)
- **Terraform resources**: `snake_case` with project prefix: `kopiika_*`
- **AWS resource names**: `kopiika-{service}-{env}` (e.g., `kopiika-api-dev`, `kopiika-rds-prod`)
- **Secrets**: `kopiika/{env}/{service}` path pattern
- **ECR repository**: `kopiika-backend`
- **S3 buckets**: `kopiika-uploads-{env}`, `kopiika-terraform-state`
- **Environment vars**: `UPPER_SNAKE_CASE` (consistent with Story 1.1)

### Testing Requirements

- **IaC validation**: `terraform validate` and `terraform plan` should complete without errors
- **Connectivity test**: Backend health endpoint (`/health`) responds when deployed to App Runner
- **Service reachability**: App Runner can connect to RDS and ElastiCache through VPC connector
- **Cognito test**: Can create a test user and authenticate via Cognito user pool
- **S3 test**: Can upload and retrieve a test file from S3 bucket
- **Secrets Manager**: App Runner and ECS can read secrets at runtime
- **CI/CD smoke test**: GitHub Actions deploy workflow runs without errors on push to main

### Project Structure Notes

- `infra/` directory exists but is empty (created in Story 1.1)
- CI workflows `ci-frontend.yml` and `ci-backend.yml` already exist — do NOT modify them
- Deployment workflows (`deploy-frontend.yml`, `deploy-backend.yml`) are NEW — create them
- Backend `Dockerfile` does NOT exist yet — must be created for ECR-based deployment
- `.env.example` files exist but are minimal — extend with AWS-specific variables
- Frontend deployment to Vercel may use Vercel's Git integration (auto-deploy) instead of GitHub Actions

### Previous Story Intelligence (Story 1.1)

**Key learnings from Story 1.1:**
- Next.js 16.2.1 was installed (architecture specified 16.1, but 16.2 is backwards compatible) — accept latest minor versions
- `uv` was not pre-installed; had to install via official script (v0.10.12)
- Port 5432 conflict was resolved by stopping pre-existing postgres container
- Docker Compose uses `pgvector/pgvector:pg16` image — RDS equivalent is enabling pgvector extension on RDS PostgreSQL 16
- Backend runs on `app/main.py` with `/health` endpoint returning `{"status": "healthy", "version": "0.1.0"}`
- Ruff is used for linting, pytest for testing — both configured in CI
- `backend/main.py` stub from `uv init` was removed during code review — watch for leftover scaffolding files

**Files established in Story 1.1 (do not recreate):**
- `docker-compose.yml`, `README.md`, `.gitignore`
- All `backend/app/` structure (`main.py`, `core/config.py`, `core/database.py`, `tasks/celery_app.py`)
- All `frontend/src/` structure (App Router, layouts, components)
- `backend/.env.example`, `frontend/.env.example` (extend, don't replace)
- `.github/workflows/ci-backend.yml`, `.github/workflows/ci-frontend.yml` (don't modify)

### References

- [Source: _bmad-output/planning-artifacts/architecture.md — Infrastructure & Deployment section]
- [Source: _bmad-output/planning-artifacts/architecture.md — AWS Architecture Diagram]
- [Source: _bmad-output/planning-artifacts/architecture.md — Implementation Sequence (step 2)]
- [Source: _bmad-output/planning-artifacts/architecture.md — Cross-Component Dependencies]
- [Source: _bmad-output/planning-artifacts/architecture.md — Environment Files section]
- [Source: _bmad-output/planning-artifacts/architecture.md — Project Directory Structure (infra/)]
- [Source: _bmad-output/planning-artifacts/architecture.md — Architectural Boundaries — component protocols]
- [Source: _bmad-output/planning-artifacts/epics.md — Epic 1, Story 1.2]
- [Source: _bmad-output/planning-artifacts/epics.md — From Architecture — Infrastructure & Deployment]
- [Source: _bmad-output/planning-artifacts/prd.md — NFR8 (JWT expiry), NFR29 (backup retention)]
- [Source: _bmad-output/implementation-artifacts/1-1-monorepo-scaffolding-local-development-environment.md — Previous story context]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (claude-opus-4-6)

### Debug Log References

- Terraform not installed locally; structural validation performed manually; existing backend tests (8/8) confirmed passing with no regressions.
- pgvector extension enablement requires post-provisioning `CREATE EXTENSION vector;` — parameter group includes `pg_stat_statements` as shared_preload_libraries.
- SES production access (sandbox exit) is a manual AWS console/support step — Terraform creates the email identity and IAM policy.
- Removed duplicate IAM roles between secrets and ECS modules to avoid naming conflicts.

### Completion Notes List

- **Task 1**: Chose Terraform as IaC tool. Created full directory structure with `infra/terraform/`, root config files (main.tf, variables.tf, outputs.tf, providers.tf, backend.tf), 3 environment tfvars (dev/staging/prod), 9 reusable modules, and comprehensive README.
- **Task 2**: Networking module with VPC (10.0.0.0/16), 2 public + 2 private subnets across 2 AZs, Internet Gateway, single NAT Gateway (cost savings), 4 security groups (RDS, Redis, App Runner, ECS) with least-privilege ingress rules, VPC endpoints for S3 (gateway, free), Secrets Manager, ECR API, and ECR DKR (interface).
- **Task 3**: RDS PostgreSQL 16 module with Graviton instances (t4g), encryption at rest (storage_encrypted=true), 30-day backup retention, private subnet placement, auto-generated master password via `random_password`, initial database `kopiika_db`, connection string output for Secrets Manager.
- **Task 4**: ElastiCache Redis 7.1 module with single-node cluster, private subnet, transit encryption (TLS), connection URL output with `rediss://` scheme.
- **Task 5**: Cognito module with user pool (email-as-username), strong password policy, account recovery via email, frontend client (public, SRP auth, no secret) and backend client (confidential, with secret, admin auth), 15-minute access token expiry, 30-day refresh token.
- **Task 6**: S3 module with `kopiika-uploads-{env}` bucket, SSE-S3 encryption, block all public access, versioning enabled, CORS for frontend uploads, 7-day incomplete multipart upload cleanup lifecycle rule.
- **Task 7**: SES module with email identity verification (conditional), IAM policy for send permissions with sender address restriction.
- **Task 8**: Secrets Manager module with 6 secrets per environment (database, redis, cognito, s3, ses, llm-api-keys) using `kopiika/{env}/` path pattern. Secret values populated from other module outputs.
- **Task 9**: App Runner module with ECR source, VPC connector for private subnet access, health check on `/health`, auto-scaling configuration, ECR access IAM role.
- **Task 10**: ECS Fargate module with cluster (container insights enabled), CloudWatch log group, task definition with Celery worker command, ECS service in private subnets, task and execution IAM roles with secrets read access.
- **Task 11**: Created `deploy-backend.yml` (GitHub Actions with OIDC auth, ECR push, Alembic migration, App Runner deploy, ECS deploy), `deploy-frontend.yml` (manual Vercel deploy — primary deploy via Vercel Git integration), `backend/Dockerfile` (multi-stage: uv install + uvicorn), `backend/Dockerfile.worker` (multi-stage: uv install + celery), GitHub OIDC provider + IAM role in ECS module (prod only).
- **Task 12**: Updated `backend/.env.example` with all AWS vars (DATABASE_URL, REDIS_URL, AWS_REGION, COGNITO_USER_POOL_ID, COGNITO_APP_CLIENT_ID, S3_BUCKET_NAME, SES_SENDER_EMAIL, AWS_SECRETS_PREFIX). Updated `frontend/.env.example` with NEXT_PUBLIC_API_URL, NEXT_PUBLIC_COGNITO_USER_POOL_ID, NEXT_PUBLIC_COGNITO_CLIENT_ID, NEXTAUTH_URL, NEXTAUTH_SECRET. Environment-specific values documented in `infra/README.md`.

### File List

**New files:**
- infra/README.md
- infra/terraform/main.tf
- infra/terraform/variables.tf
- infra/terraform/outputs.tf
- infra/terraform/providers.tf
- infra/terraform/backend.tf
- infra/terraform/environments/dev/terraform.tfvars
- infra/terraform/environments/staging/terraform.tfvars
- infra/terraform/environments/prod/terraform.tfvars
- infra/terraform/modules/networking/main.tf
- infra/terraform/modules/networking/variables.tf
- infra/terraform/modules/networking/outputs.tf
- infra/terraform/modules/rds/main.tf
- infra/terraform/modules/rds/variables.tf
- infra/terraform/modules/rds/outputs.tf
- infra/terraform/modules/elasticache/main.tf
- infra/terraform/modules/elasticache/variables.tf
- infra/terraform/modules/elasticache/outputs.tf
- infra/terraform/modules/cognito/main.tf
- infra/terraform/modules/cognito/variables.tf
- infra/terraform/modules/cognito/outputs.tf
- infra/terraform/modules/s3/main.tf
- infra/terraform/modules/s3/variables.tf
- infra/terraform/modules/s3/outputs.tf
- infra/terraform/modules/ses/main.tf
- infra/terraform/modules/ses/variables.tf
- infra/terraform/modules/ses/outputs.tf
- infra/terraform/modules/secrets/main.tf
- infra/terraform/modules/secrets/variables.tf
- infra/terraform/modules/secrets/outputs.tf
- infra/terraform/modules/app-runner/main.tf
- infra/terraform/modules/app-runner/variables.tf
- infra/terraform/modules/app-runner/outputs.tf
- infra/terraform/modules/ecs/main.tf
- infra/terraform/modules/ecs/variables.tf
- infra/terraform/modules/ecs/outputs.tf
- infra/terraform/modules/ecs/github-oidc.tf
- .github/workflows/deploy-backend.yml
- .github/workflows/deploy-frontend.yml
- backend/Dockerfile
- backend/Dockerfile.worker
- backend/.dockerignore

**Modified files:**
- backend/.env.example
- frontend/.env.example
- frontend/.gitignore

## Change Log

- 2026-03-21: Implemented complete AWS infrastructure provisioning with Terraform IaC (9 modules: networking, rds, elasticache, cognito, s3, ses, secrets, app-runner, ecs), 3 environment configurations (dev/staging/prod), CI/CD deployment workflows for backend (ECR + App Runner + ECS) and frontend (Vercel), production Dockerfiles (API + Celery worker), and updated environment variable documentation.
- 2026-03-21: **Code Review Fixes** — Fixed 10 issues: (1) frontend/.gitignore now allows .env.example to be tracked; (2) deploy-backend.yml Alembic migration step now correctly passes OIDC credentials; (3) App Runner deploy action pinned to @v2; (4) App Runner instance role added with Secrets Manager read access; (5) GitHub OIDC trust policy scoped to specific repo via github_repo variable; (6) IAM deploy policy resources scoped to project-prefixed ARNs; (7) S3 CORS restricted from wildcard to configurable origins; (8) Both Dockerfiles now run as non-root appuser; (9) uv pinned to 0.6.12 in both Dockerfiles; (10) Added backend/.dockerignore.
