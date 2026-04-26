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

# Story 10.8b / TD-131 — safety-runner CI role + Guardrail ARN. After
# `terraform apply`, paste the role ARN into repo `vars.AWS_IAM_ROLE_ARN_SAFETY_TEST`
# and the safety guardrail ARN into `vars.BEDROCK_GUARDRAIL_ARN_SAFETY`, then
# `bless` the first baseline locally per docs/tech-debt.md TD-131.
output "github_safety_test_role_arn" {
  description = "ARN of the GitHub OIDC safety-runner role (TD-131). Paste into repo var AWS_IAM_ROLE_ARN_SAFETY_TEST."
  value       = module.ecs.github_safety_test_role_arn
}

output "safety_guardrail_arn" {
  description = "Unversioned ARN of the safety-runner Bedrock Guardrail (Story 10.8b). Paste into repo var BEDROCK_GUARDRAIL_ARN_SAFETY."
  value       = try(module.bedrock_guardrail[0].safety_guardrail_arn, null)
}

output "safety_guardrail_version_arn" {
  description = "Versioned ARN of the safety-runner Bedrock Guardrail. Use this if you want to pin a published version (the runner currently uses the unversioned/DRAFT ARN)."
  value       = try(module.bedrock_guardrail[0].safety_guardrail_version_arn, null)
}

# --- Custom domain DNS records (paste into Squarespace) ---
output "api_custom_domain" {
  description = "Configured API custom domain (empty if not set)."
  value       = module.app_runner.custom_domain
}

output "api_app_runner_dns_records" {
  description = "App Runner-issued DNS targets for the custom domain. `dns_target` is the CNAME you point your custom domain at; `certificate_records` are the validation CNAMEs App Runner needs to issue + renew its internal ACM cert. Paste both into Squarespace DNS — see docs/runbooks/domain-setup.md."
  value       = module.app_runner.app_runner_dns_records
}
