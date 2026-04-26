variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "eu-central-1"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod."
  }
}

variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "kopiika"
}

# Networking
variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "List of availability zones"
  type        = list(string)
  default     = ["eu-central-1a", "eu-central-1b"]
}

# RDS
variable "rds_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t4g.micro"
}

variable "rds_allocated_storage" {
  description = "RDS allocated storage in GB"
  type        = number
  default     = 20
}

variable "rds_backup_retention_period" {
  description = "Number of days to retain automated backups"
  type        = number
  default     = 30
}

# ElastiCache
variable "elasticache_node_type" {
  description = "ElastiCache node type"
  type        = string
  default     = "cache.t4g.micro"
}

# App Runner
variable "app_runner_cpu" {
  description = "App Runner instance CPU (in vCPU units)"
  type        = string
  default     = "1024"
}

variable "app_runner_memory" {
  description = "App Runner instance memory (in MB)"
  type        = string
  default     = "2048"
}

variable "app_runner_min_instances" {
  description = "Minimum number of App Runner instances"
  type        = number
  default     = 1
}

variable "app_runner_max_instances" {
  description = "Maximum number of App Runner instances"
  type        = number
  default     = 4
}

# ECS
variable "ecs_cpu" {
  description = "ECS task CPU (in CPU units)"
  type        = number
  default     = 512
}

variable "ecs_memory" {
  description = "ECS task memory (in MB)"
  type        = number
  default     = 1024
}

variable "ecs_desired_count" {
  description = "Desired number of ECS tasks"
  type        = number
  default     = 1
}

# ECR
variable "ecr_repository_name" {
  description = "ECR repository name for backend images"
  type        = string
  default     = "kopiika-backend"
}

# Cognito
variable "cognito_access_token_validity" {
  description = "Access token validity in minutes"
  type        = number
  default     = 15
}

variable "cognito_refresh_token_validity" {
  description = "Refresh token validity in days"
  type        = number
  default     = 30
}

# GitHub
variable "github_repo" {
  description = "GitHub repository in format 'owner/repo' for OIDC trust policy"
  type        = string
  default     = ""
}

# SES
variable "ses_sender_email" {
  description = "Verified sender email for SES"
  type        = string
  default     = ""
}

# Bedrock IAM plumbing (Story 9.7)
variable "bedrock_invocation_arns" {
  description = "Flat list of Bedrock inference-profile + foundation-model ARNs the Celery task role may InvokeModel against. Must include both eu-central-1 inference profiles AND their eu-north-1 foundation-model backing ARNs per Story 9.4 decision doc."
  type        = list(string)
  default     = []
}

variable "agentcore_runtime_arn" {
  description = "ARN for the Bedrock AgentCore runtime. Empty default fail-closes the App Runner AgentCore IAM policy (no wildcard footgun). Phase B story 10.4a-runtime provisions a concrete runtime + sets this in tfvars."
  type        = string
  default     = ""
}

variable "github_bedrock_ci_enabled" {
  description = "Whether to provision the GitHub OIDC Bedrock CI role (TD-086). Prod: true; dev/staging: false."
  type        = bool
  default     = false
}

# Observability (Story 11.9)
variable "enable_observability_alarms" {
  description = "Create CloudWatch alarms for categorization/parser signals. Defaults to false (set true in prod/staging tfvars)."
  type        = bool
  default     = false
}

variable "observability_sns_topic_arn" {
  description = "SNS topic ARN for observability alarm actions. Empty = no alarm action wired."
  type        = string
  default     = ""
}

# Security baseline (CloudTrail / GuardDuty / Security Hub / CIS alarms / Budgets)
variable "security_alarm_email" {
  description = "Email subscribed to the security-baseline SNS topic (CIS alarms + AWS Budgets). Empty = no email subscription (alarms still visible in console)."
  type        = string
  default     = ""
}

variable "monthly_budget_usd" {
  description = "AWS Budgets monthly total. 80% actual + 100% forecast trigger notifications."
  type        = number
  default     = 100
}

variable "bedrock_monthly_budget_usd" {
  description = "AWS Budgets monthly cap on Bedrock spend specifically. Defense-in-depth against the github_bedrock_ci OIDC role being abused."
  type        = number
  default     = 30
}

variable "image_tag" {
  description = "Bootstrap ECR image tag for App Runner / ECS at first apply. ECR repo is IMMUTABLE so :latest is unavailable; CI deploys point services to :sha-<sha> via update-service / register-task-definition. lifecycle.ignore_changes prevents Terraform from reverting CI updates."
  type        = string
  default     = "bootstrap"
}

variable "api_custom_domain" {
  description = "Custom domain for the App Runner API (e.g. api.kopiika.coach). Empty = use the default awsapprunner.com URL. DNS records to set in Squarespace are emitted as outputs."
  type        = string
  default     = ""
}

variable "frontend_origins" {
  description = "Origins allowed by the FastAPI CORS middleware AND by the S3 uploads bucket CORS rule. Must include every URL from which a browser will make API/upload requests (Vercel preview URLs, custom domain, localhost for dev)."
  type        = list(string)
  default     = ["http://localhost:3000"]
}
