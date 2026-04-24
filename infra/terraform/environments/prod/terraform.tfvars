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
  # eu-north-1 foundation-model backing ARNs (no account ID in the path)
  "arn:aws:bedrock:eu-north-1::foundation-model/anthropic.claude-haiku-4-5-20251001-v1:0",
  "arn:aws:bedrock:eu-north-1::foundation-model/anthropic.claude-sonnet-4-6-v1:0",
  "arn:aws:bedrock:eu-north-1::foundation-model/amazon.nova-micro-v1:0",
]

# Story 10.2 Guardrail is now module-owned (module.bedrock_guardrail). ARN
# flows to module.ecs at plan time; no tfvars override needed.

# Story 10.4a AgentCore runtime not yet provisioned; wildcard default carried
# from variables.tf. Flip to concrete ARN when 10.4a lands.
# agentcore_runtime_arn = "arn:aws:bedrock-agentcore:eu-central-1:573562677570:runtime/<id>"

# TD-086 — enable the GitHub OIDC Bedrock CI role only in prod.
github_bedrock_ci_enabled = true
