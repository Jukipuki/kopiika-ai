output "vpc_id" {
  description = "ID of the VPC"
  value       = module.networking.vpc_id
}

output "rds_endpoint" {
  description = "RDS instance endpoint"
  value       = module.rds.endpoint
  sensitive   = true
}

output "redis_endpoint" {
  description = "ElastiCache Redis endpoint"
  value       = module.elasticache.endpoint
  sensitive   = true
}

output "cognito_user_pool_id" {
  description = "Cognito User Pool ID"
  value       = module.cognito.user_pool_id
}

output "cognito_app_client_id" {
  description = "Cognito App Client ID (frontend)"
  value       = module.cognito.app_client_id
}

output "s3_bucket_name" {
  description = "S3 uploads bucket name"
  value       = module.s3.bucket_name
}

output "ecr_repository_url" {
  description = "ECR repository URL"
  value       = aws_ecr_repository.backend.repository_url
}

output "app_runner_service_url" {
  description = "App Runner service URL"
  value       = module.app_runner.service_url
}

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = module.ecs.cluster_name
}

output "github_bedrock_ci_role_arn" {
  description = "ARN of the GitHub OIDC Bedrock CI role (Story 9.7 / TD-086). Paste into repo secret AWS_ROLE_TO_ASSUME to unblock the cross-provider matrix Bedrock column."
  value       = module.ecs.github_bedrock_ci_role_arn
}
