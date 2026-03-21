variable "project_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "rds_connection_string" {
  type      = string
  sensitive = true
}

variable "redis_connection_url" {
  type      = string
  sensitive = true
}

variable "cognito_user_pool_id" {
  type = string
}

variable "cognito_app_client_id" {
  type = string
}

variable "cognito_backend_client_id" {
  type = string
}

variable "cognito_backend_client_secret" {
  type      = string
  sensitive = true
}

variable "s3_bucket_name" {
  type = string
}

variable "ses_sender_email" {
  type = string
}

variable "aws_region" {
  type = string
}
