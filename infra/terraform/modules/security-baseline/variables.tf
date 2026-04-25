variable "project_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "aws_region" {
  type = string
}

variable "alarm_email" {
  description = "Email address subscribed to the security alarm SNS topic. Empty = no subscription created (alarms still fire to console)."
  type        = string
  default     = ""
}

variable "monthly_budget_usd" {
  description = "Total account monthly budget. Triggers an alarm at 80% actual + 100% forecast."
  type        = number
  default     = 100
}

variable "bedrock_monthly_budget_usd" {
  description = "Bedrock-specific monthly budget. Defense-in-depth against the github_bedrock_ci OIDC role being abused for cost-attack. 80% actual / 100% forecast thresholds."
  type        = number
  default     = 30
}
