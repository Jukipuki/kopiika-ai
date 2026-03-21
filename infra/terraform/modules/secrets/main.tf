locals {
  prefix = "${var.project_name}/${var.environment}"
}

resource "aws_secretsmanager_secret" "database" {
  name = "${local.prefix}/database"

  tags = {
    Name = "${local.prefix}/database"
  }
}

resource "aws_secretsmanager_secret_version" "database" {
  secret_id = aws_secretsmanager_secret.database.id
  secret_string = jsonencode({
    connection_string = var.rds_connection_string
  })
}

resource "aws_secretsmanager_secret" "redis" {
  name = "${local.prefix}/redis"

  tags = {
    Name = "${local.prefix}/redis"
  }
}

resource "aws_secretsmanager_secret_version" "redis" {
  secret_id = aws_secretsmanager_secret.redis.id
  secret_string = jsonencode({
    connection_url = var.redis_connection_url
  })
}

resource "aws_secretsmanager_secret" "cognito" {
  name = "${local.prefix}/cognito"

  tags = {
    Name = "${local.prefix}/cognito"
  }
}

resource "aws_secretsmanager_secret_version" "cognito" {
  secret_id = aws_secretsmanager_secret.cognito.id
  secret_string = jsonencode({
    user_pool_id          = var.cognito_user_pool_id
    app_client_id         = var.cognito_app_client_id
    backend_client_id     = var.cognito_backend_client_id
    backend_client_secret = var.cognito_backend_client_secret
  })
}

resource "aws_secretsmanager_secret" "s3" {
  name = "${local.prefix}/s3"

  tags = {
    Name = "${local.prefix}/s3"
  }
}

resource "aws_secretsmanager_secret_version" "s3" {
  secret_id = aws_secretsmanager_secret.s3.id
  secret_string = jsonencode({
    bucket_name = var.s3_bucket_name
    region      = var.aws_region
  })
}

resource "aws_secretsmanager_secret" "ses" {
  name = "${local.prefix}/ses"

  tags = {
    Name = "${local.prefix}/ses"
  }
}

resource "aws_secretsmanager_secret_version" "ses" {
  secret_id = aws_secretsmanager_secret.ses.id
  secret_string = jsonencode({
    sender_email = var.ses_sender_email
    region       = var.aws_region
  })
}

resource "aws_secretsmanager_secret" "llm_api_keys" {
  name = "${local.prefix}/llm-api-keys"

  tags = {
    Name = "${local.prefix}/llm-api-keys"
  }
}

resource "aws_secretsmanager_secret_version" "llm_api_keys" {
  secret_id     = aws_secretsmanager_secret.llm_api_keys.id
  secret_string = jsonencode({})
}
