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

# Story 10.4b — chat canary tokens for prompt-leak detection.
#
# All three envs (dev, staging, prod) provision this secret. Secrets Manager
# cost is near-zero per secret and having dev hit the real code path lets us
# find loader bugs before prod ever sees them. This differs from Story 10.2's
# prod-only Guardrail posture for that reason.
#
# Values are seeded with placeholders satisfying AC #2's 24-char minimum so
# module import succeeds; operators rotate real values via the Story 10.9
# runbook (`aws secretsmanager put-secret-value`). Real canaries must never
# live in Terraform state plaintext — this follows the `llm_api_keys` precedent.
resource "aws_secretsmanager_secret" "chat_canaries" {
  name = "${local.prefix}/chat-canaries"

  tags = {
    Name = "${local.prefix}/chat-canaries"
  }
}

resource "aws_secretsmanager_secret_version" "chat_canaries" {
  secret_id = aws_secretsmanager_secret.chat_canaries.id
  secret_string = jsonencode({
    canary_a = "REPLACE_ME_VIA_ROTATION_RUNBOOK_AB"
    canary_b = "REPLACE_ME_VIA_ROTATION_RUNBOOK_CD"
    canary_c = "REPLACE_ME_VIA_ROTATION_RUNBOOK_EF"
  })

  # DO NOT REMOVE — without this, every terraform apply would overwrite
  # operator-rotated canaries back to the placeholders, silently breaking
  # production prompt-leak detection. TD tracks adding the same guard to
  # llm_api_keys (see docs/tech-debt.md).
  lifecycle {
    ignore_changes = [secret_string]
  }
}
