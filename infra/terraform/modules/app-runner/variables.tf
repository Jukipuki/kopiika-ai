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
# Wildcard default until Story 10.4a provisions a concrete AgentCore runtime;
# per-env tfvars narrow it to the concrete ARN at 10.4a time.
variable "agentcore_runtime_arn" {
  description = "ARN for the Bedrock AgentCore runtime (Story 10.4a). Wildcard default until 10.4a provisions a concrete runtime."
  type        = string
  default     = "arn:aws:bedrock-agentcore:eu-central-1:*:runtime/*"
}
