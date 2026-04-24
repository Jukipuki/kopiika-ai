locals {
  name_prefix = "${var.project_name}-${var.environment}"
}

# --- Networking ---
module "networking" {
  source = "./modules/networking"

  project_name       = var.project_name
  environment        = var.environment
  vpc_cidr           = var.vpc_cidr
  availability_zones = var.availability_zones
}

# --- RDS PostgreSQL with pgvector ---
module "rds" {
  source = "./modules/rds"

  project_name            = var.project_name
  environment             = var.environment
  vpc_id                  = module.networking.vpc_id
  private_subnet_ids      = module.networking.private_subnet_ids
  rds_security_group_id   = module.networking.rds_security_group_id
  instance_class          = var.rds_instance_class
  allocated_storage       = var.rds_allocated_storage
  backup_retention_period = var.rds_backup_retention_period
}

# --- ElastiCache Redis ---
module "elasticache" {
  source = "./modules/elasticache"

  project_name            = var.project_name
  environment             = var.environment
  private_subnet_ids      = module.networking.private_subnet_ids
  redis_security_group_id = module.networking.redis_security_group_id
  node_type               = var.elasticache_node_type
}

# --- Cognito ---
module "cognito" {
  source = "./modules/cognito"

  project_name           = var.project_name
  environment            = var.environment
  ses_sender_arn         = module.ses.sender_identity_arn
  access_token_validity  = var.cognito_access_token_validity
  refresh_token_validity = var.cognito_refresh_token_validity
}

# --- S3 ---
module "s3" {
  source = "./modules/s3"

  project_name = var.project_name
  environment  = var.environment
}

# --- SES ---
module "ses" {
  source = "./modules/ses"

  project_name = var.project_name
  environment  = var.environment
  sender_email = var.ses_sender_email
}

# --- Secrets Manager ---
module "secrets" {
  source = "./modules/secrets"

  project_name                  = var.project_name
  environment                   = var.environment
  rds_connection_string         = module.rds.connection_string
  redis_connection_url          = module.elasticache.connection_url
  cognito_user_pool_id          = module.cognito.user_pool_id
  cognito_app_client_id         = module.cognito.app_client_id
  cognito_backend_client_id     = module.cognito.backend_client_id
  cognito_backend_client_secret = module.cognito.backend_client_secret
  s3_bucket_name                = module.s3.bucket_name
  ses_sender_email              = var.ses_sender_email
  aws_region                    = var.aws_region
}

# --- ECR Repository ---
resource "aws_ecr_repository" "backend" {
  name                 = var.ecr_repository_name
  image_tag_mutability = "MUTABLE"
  force_delete         = var.environment == "dev"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }
}

# --- App Runner ---
module "app_runner" {
  source = "./modules/app-runner"

  project_name                 = var.project_name
  environment                  = var.environment
  ecr_repository_url           = aws_ecr_repository.backend.repository_url
  cpu                          = var.app_runner_cpu
  memory                       = var.app_runner_memory
  min_instances                = var.app_runner_min_instances
  max_instances                = var.app_runner_max_instances
  vpc_id                       = module.networking.vpc_id
  private_subnet_ids           = module.networking.private_subnet_ids
  app_runner_security_group_id = module.networking.app_runner_security_group_id
  secrets_arns                 = module.secrets.secret_arns

  agentcore_runtime_arn = var.agentcore_runtime_arn
}

# --- Bedrock Guardrail (Story 10.2) ---
# Prod-only: dev/staging run zero chat traffic (no AgentCore runtime, no chat
# UI in those envs), so a Guardrail would be pure spend. Flip the gate if
# chat ever lands in staging.
module "bedrock_guardrail" {
  source = "./modules/bedrock-guardrail"
  count  = var.environment == "prod" ? 1 : 0

  project_name                = var.project_name
  environment                 = var.environment
  observability_sns_topic_arn = var.observability_sns_topic_arn
}

# --- ECS Fargate ---
module "ecs" {
  source = "./modules/ecs"

  project_name          = var.project_name
  environment           = var.environment
  ecr_repository_url    = aws_ecr_repository.backend.repository_url
  cpu                   = var.ecs_cpu
  memory                = var.ecs_memory
  desired_count         = var.ecs_desired_count
  vpc_id                = module.networking.vpc_id
  private_subnet_ids    = module.networking.private_subnet_ids
  ecs_security_group_id = module.networking.ecs_security_group_id
  secrets_arns          = module.secrets.secret_arns
  aws_region            = var.aws_region
  github_repo           = var.github_repo

  bedrock_invocation_arns   = var.bedrock_invocation_arns
  bedrock_guardrail_arns    = try(module.bedrock_guardrail[0].guardrail_arns, [])
  github_bedrock_ci_enabled = var.github_bedrock_ci_enabled

  enable_observability_alarms = var.enable_observability_alarms
  observability_sns_topic_arn = var.observability_sns_topic_arn
}
