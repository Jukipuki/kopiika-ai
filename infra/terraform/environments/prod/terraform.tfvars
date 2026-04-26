environment        = "prod"
aws_region         = "eu-central-1"
availability_zones = ["eu-central-1a", "eu-central-1b"]

# RDS
rds_instance_class          = "db.t4g.small"
rds_allocated_storage       = 100
rds_backup_retention_period = 30

# ElastiCache
elasticache_node_type = "cache.t4g.micro"

# App Runner
app_runner_cpu           = "1024"
app_runner_memory        = "2048"
app_runner_min_instances = 1
app_runner_max_instances = 4

# ECS
ecs_cpu           = 512
ecs_memory        = 1024
ecs_desired_count = 1

# Cognito
cognito_access_token_validity  = 15
cognito_refresh_token_validity = 30

# SES
ses_sender_email = ""

# Observability (Story 11.9)
enable_observability_alarms = true
observability_sns_topic_arn = ""

# Bedrock IAM plumbing (Story 9.7)
# Account 573562677570 per Story 9.4 decision doc. List must include both the
# eu-central-1 inference-profile ARNs pinned in backend/app/agents/models.yaml
# AND the eu-north-1 foundation-model ARNs those profiles physically route to —
# cross-region inference requires both in the same IAM statement (docs/decisions/
# agentcore-bedrock-region-availability-2026-04.md:47).
bedrock_invocation_arns = [
  # eu-central-1 inference profiles (source-of-truth: models.yaml)
  "arn:aws:bedrock:eu-central-1:573562677570:inference-profile/eu.anthropic.claude-haiku-4-5-20251001-v1:0",
  "arn:aws:bedrock:eu-central-1:573562677570:inference-profile/eu.anthropic.claude-sonnet-4-6",
  "arn:aws:bedrock:eu-central-1:573562677570:inference-profile/eu.amazon.nova-micro-v1:0",
  # Foundation-model backing ARNs in any EU region. The Story 9.4 decision
  # doc originally pinned eu-north-1 only, but Bedrock has expanded the EU
  # inference-profile fanout to additional regions (observed: eu-west-3 in
  # 2026-04). The wildcard matches all current and future EU backing
  # regions; the model-name suffix keeps the grant scoped to the three
  # families we actually use. No account-id in foundation-model ARNs.
  "arn:aws:bedrock:eu-*::foundation-model/anthropic.claude-haiku-4-5-20251001-v1:0",
  "arn:aws:bedrock:eu-*::foundation-model/anthropic.claude-sonnet-4-6-v1:0",
  "arn:aws:bedrock:eu-*::foundation-model/amazon.nova-micro-v1:0",
]

# Story 10.2 Guardrail is now module-owned (module.bedrock_guardrail). ARN
# flows to module.ecs at plan time; no tfvars override needed.

# Chat runtime phasing (ADR-0004). Story 10.4a ships Phase A — direct Bedrock
# via llm.py, no AgentCore runtime. Phase B (story 10.4a-runtime) provisions
# the runtime module and flips this to the concrete ARN.
# agentcore_runtime_arn = "arn:aws:bedrock-agentcore:eu-central-1:573562677570:runtime/<id>"

# GitHub OIDC trust scope — required so role trust policies bind to this
# repo's workflow tokens. Without it the `sub` claim becomes "repo::ref:..."
# and AssumeRoleWithWebIdentity always denies.
github_repo = "Jukipuki/kopiika-ai"

# TD-086 — enable the GitHub OIDC Bedrock CI role only in prod.
github_bedrock_ci_enabled = true

# Security baseline (Phase C hardening, 2026-04-25)
security_alarm_email       = "ogumennyj@gmail.com"
monthly_budget_usd         = 100
bedrock_monthly_budget_usd = 30

# Bootstrap image tag — operator pushes :bootstrap once before first apply,
# then CI deploys point services to :sha-<sha>. ECR is IMMUTABLE so no :latest.
image_tag = "bootstrap"

# Custom domain (Squarespace registered, manual DNS). After first apply, run
# `terraform output api_acm_validation_records` and `api_app_runner_dns_records`
# and paste both sets into Squarespace DNS. See docs/runbooks/domain-setup.md.
api_custom_domain = "api.kopiika.coach"

# Origins allowed to make browser API + S3 calls. Add each Vercel deployment
# URL the frontend lives under (vercel.app default + the custom apex once
# attached). localhost stays for dev.
frontend_origins = [
  "https://kopiika.coach",
  "https://kopiika.vercel.app",
  "http://localhost:3000",
]
