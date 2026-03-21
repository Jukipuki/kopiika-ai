variable "project_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "ses_sender_arn" {
  description = "ARN of the verified SES sender identity"
  type        = string
  default     = ""
}

variable "access_token_validity" {
  description = "Access token validity in minutes"
  type        = number
  default     = 15
}

variable "refresh_token_validity" {
  description = "Refresh token validity in days"
  type        = number
  default     = 30
}
