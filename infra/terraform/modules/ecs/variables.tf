variable "project_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "ecr_repository_url" {
  type = string
}

variable "cpu" {
  type    = number
  default = 512
}

variable "memory" {
  type    = number
  default = 1024
}

variable "desired_count" {
  type    = number
  default = 1
}

variable "vpc_id" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "ecs_security_group_id" {
  type = string
}

variable "secrets_arns" {
  description = "Map of secret ARNs from secrets module"
  type        = map(string)
}

variable "aws_region" {
  type = string
}

variable "github_repo" {
  description = "GitHub repository in format 'owner/repo' for OIDC trust policy"
  type        = string
  default     = ""
}

# Story 9.7 — Bedrock IAM plumbing (Celery ECS task role).
# `bedrock_invocation_arns` is the flat list of resource ARNs the Celery role can
# InvokeModel against. Per the Story 9.4 decision doc it MUST contain both the
# eu-central-1 inference-profile ARNs AND the eu-north-1 foundation-model ARNs
# the profiles route to — cross-region inference requires both. Empty default
# means no statement is attached (safe no-op for dev), populated by prod tfvars.
variable "bedrock_invocation_arns" {
  description = "Flat list of Bedrock inference-profile + foundation-model ARNs the Celery task role may InvokeModel against. Empty = skip policy."
  type        = list(string)
  default     = []
}

# `bedrock_guardrail_arn` carries the Story 10.2 Guardrail identifier. Account-
# scoped wildcard default narrows to a concrete ARN when 10.2 lands (set via
# per-env tfvars, no HCL edit needed).
variable "bedrock_guardrail_arn" {
  description = "ARN for the Bedrock Guardrail resource (Story 10.2). Wildcard default until 10.2 provisions a concrete Guardrail."
  type        = string
  default     = "arn:aws:bedrock:eu-central-1:*:guardrail/*"
}

# `github_bedrock_ci_enabled` gates the TD-086 CI role. Prod flips true; dev/
# staging stay false so they don't provision the role unnecessarily.
variable "github_bedrock_ci_enabled" {
  description = "Whether to provision the GitHub OIDC Bedrock CI role (TD-086)."
  type        = bool
  default     = false
}

# Story 11.9 — observability toggles.
variable "enable_observability_alarms" {
  description = "Create CloudWatch alarms for categorization/parser signals. Disabled in dev by default to avoid noise on a single-developer workload."
  type        = bool
  default     = false
}

variable "observability_sns_topic_arn" {
  description = "SNS topic ARN for observability alarm actions. Empty string = no action (alarms visible in AWS console only)."
  type        = string
  default     = ""
}
