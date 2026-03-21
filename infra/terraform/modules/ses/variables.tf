variable "project_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "sender_email" {
  description = "Email address to verify for sending"
  type        = string
  default     = ""
}
