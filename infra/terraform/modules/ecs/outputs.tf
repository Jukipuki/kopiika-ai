output "cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "cluster_arn" {
  value = aws_ecs_cluster.main.arn
}

output "service_name" {
  value = aws_ecs_service.worker.name
}

output "task_definition_arn" {
  value = aws_ecs_task_definition.worker.arn
}

# Story 9.7 / TD-086 — ARN of the GitHub OIDC Bedrock CI role.
# After terraform apply, paste this value into the GitHub repo secret
# `AWS_ROLE_TO_ASSUME`, then flip LLM_PROVIDER_MATRIX_PROVIDERS in
# .github/workflows/ci-backend-provider-matrix.yml to include bedrock.
output "github_bedrock_ci_role_arn" {
  description = "ARN of the GitHub OIDC Bedrock CI role (null if not enabled)."
  value       = try(aws_iam_role.github_bedrock_ci[0].arn, null)
}
