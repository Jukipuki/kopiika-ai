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
  type    = string
  default = "1024"
}

variable "memory" {
  type    = string
  default = "2048"
}

variable "min_instances" {
  type    = number
  default = 1
}

variable "max_instances" {
  type    = number
  default = 4
}

variable "vpc_id" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "app_runner_security_group_id" {
  type = string
}

variable "secrets_arns" {
  description = "Map of secret ARNs from secrets module"
  type        = map(string)
}

# Story 9.7 — AgentCore invoke scope for the App Runner instance role.
# Wildcard default is a Phase A placeholder (Story 10.4a ships direct-Bedrock
# chat per ADR-0004 — no AgentCore Runtime yet). Phase B story 10.4a-runtime
# provisions the runtime + swaps this to a concrete ARN; until then the
# agentcore_policy_enabled regex gate in main.tf skips the live invoke grant.
# Story 10.4b — chat canaries secret ARN (scoped GetSecretValue grant for the
# chat prompt-leak detector's canary token loader).
variable "chat_canaries_secret_arn" {
  description = "ARN of the chat canaries secret. Set by root main.tf from module.secrets.chat_canaries_secret_arn. Scoped exact-ARN grant keeps ECS (Celery) out of the chat canary read surface."
  type        = string
}

variable "agentcore_runtime_arn" {
  description = "ARN for the Bedrock AgentCore runtime. Empty default fail-closes the IAM policy via the agentcore_policy_enabled regex gate."
  type        = string
  default     = ""
}

variable "kms_key_arns" {
  description = "List of KMS CMK ARNs the App Runner instance role needs Decrypt/GenerateDataKey on (secrets, s3 uploads)."
  type        = list(string)
  default     = []
}

variable "image_tag" {
  description = "ECR image tag for App Runner to bootstrap with. ECR repo is IMMUTABLE so :latest is unavailable; first deploy pushes a concrete tag (e.g. 'bootstrap'), CI updates the service to :sha-<sha> on subsequent releases. lifecycle.ignore_changes prevents Terraform from reverting CI updates."
  type        = string
  default     = "bootstrap"
}

variable "custom_domain" {
  description = "Custom domain for the App Runner API (e.g. api.kopiika.coach). Empty = no domain (default *.awsapprunner.com URL still works). DNS validation + final CNAME target are output for manual pasting into Squarespace DNS."
  type        = string
  default     = ""
}

variable "ses_send_policy_arn" {
  description = "ARN of the SES send policy from modules/ses (empty when ses_sender_email is unset). Attached to the instance role so backend code can call SES directly."
  type        = string
  default     = ""
}

variable "cors_origins" {
  description = "List of origins FastAPI's CORS middleware allows. Must include the live frontend URL(s); browser preflights from origins not in this list are rejected."
  type        = list(string)
  default     = ["http://localhost:3000"]
}

variable "cognito_user_pool_arn" {
  description = "ARN of the Cognito user pool the App Runner backend authenticates against. Required for AdminInitiateAuth/AdminUserGlobalSignOut/AdminDeleteUser. Empty = skip the policy entirely (admin auth flows will fail)."
  type        = string
  default     = ""
}

variable "s3_uploads_bucket_arn" {
  description = "ARN of the S3 uploads bucket. Required for backend put_object/get_object/delete_object calls. Empty = skip the policy."
  type        = string
  default     = ""
}

# Story 10.9 — Chat safety observability (metric filters + alarms on the
# App Runner application log group). Mirrors the variable shape used by
# Story 11.9's ECS module.
variable "enable_observability_alarms" {
  description = "Create the Story 10.9 chat-safety CloudWatch alarms. Metric filters are unconditional (free); alarms gate behind this flag so dev environments don't page on synthetic load."
  type        = bool
  default     = false
}

variable "observability_sns_topic_arn" {
  description = "SNS topic ARN for chat-safety alarm actions. Empty = alarms remain console-visible only (no SNS fan-out)."
  type        = string
  default     = ""
}
