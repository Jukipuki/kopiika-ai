variable "project_name" {
  description = "Project name prefix (used in guardrail + alarm names)."
  type        = string
}

variable "environment" {
  description = "Deployment environment (dev / staging / prod)."
  type        = string
}

variable "observability_sns_topic_arn" {
  description = "SNS topic ARN for the block-rate alarm action. Empty string = alarm visible only in console."
  type        = string
  default     = ""
}
