variable "project_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "cors_allowed_origins" {
  description = "List of allowed origins for CORS"
  type        = list(string)
  default     = []
}
