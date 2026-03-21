output "secret_arns" {
  description = "Map of secret ARNs"
  value = {
    database     = aws_secretsmanager_secret.database.arn
    redis        = aws_secretsmanager_secret.redis.arn
    cognito      = aws_secretsmanager_secret.cognito.arn
    s3           = aws_secretsmanager_secret.s3.arn
    ses          = aws_secretsmanager_secret.ses.arn
    llm_api_keys = aws_secretsmanager_secret.llm_api_keys.arn
  }
}
