output "user_pool_id" {
  value = aws_cognito_user_pool.main.id
}

output "user_pool_arn" {
  value = aws_cognito_user_pool.main.arn
}

output "app_client_id" {
  value = aws_cognito_user_pool_client.frontend.id
}

output "backend_client_id" {
  value = aws_cognito_user_pool_client.backend.id
}

output "backend_client_secret" {
  value     = aws_cognito_user_pool_client.backend.client_secret
  sensitive = true
}
