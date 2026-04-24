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
  description = "ARN for the Bedrock AgentCore runtime. Wildcard default is a Phase A placeholder (Story 10.4a ships direct-Bedrock chat per ADR-0004). Phase B story 10.4a-runtime swaps this to a concrete ARN."
  type        = string
  default     = "arn:aws:bedrock-agentcore:eu-central-1:*:runtime/*"
}
