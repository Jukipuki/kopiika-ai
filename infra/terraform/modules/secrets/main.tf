locals {
  prefix      = "${var.project_name}/${var.environment}"
  name_prefix = "${var.project_name}-${var.environment}"
}

# Per-env KMS CMK for all Secrets Manager material.
# Single key (not per-secret) — the blast-radius is identical (any one secret
# compromise implies the role with kms:Decrypt has access to all of them anyway)
# and a single key keeps the key-policy review surface manageable.
resource "aws_kms_key" "secrets" {
  description             = "${local.name_prefix} Secrets Manager CMK"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = {
    Name = "${local.name_prefix}-secrets"
  }
}

resource "aws_kms_alias" "secrets" {
  name          = "alias/${local.name_prefix}-secrets"
  target_key_id = aws_kms_key.secrets.key_id
}

resource "aws_secretsmanager_secret" "database" {
  name       = "${local.prefix}/database"
  kms_key_id = aws_kms_key.secrets.arn

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
  name       = "${local.prefix}/redis"
  kms_key_id = aws_kms_key.secrets.arn

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
  name       = "${local.prefix}/cognito"
  kms_key_id = aws_kms_key.secrets.arn

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
  name       = "${local.prefix}/s3"
  kms_key_id = aws_kms_key.secrets.arn

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
  name       = "${local.prefix}/ses"
  kms_key_id = aws_kms_key.secrets.arn

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
  name       = "${local.prefix}/llm-api-keys"
  kms_key_id = aws_kms_key.secrets.arn

  tags = {
    Name = "${local.prefix}/llm-api-keys"
  }
}

resource "aws_secretsmanager_secret_version" "llm_api_keys" {
  secret_id     = aws_secretsmanager_secret.llm_api_keys.id
  secret_string = jsonencode({})

  # DO NOT REMOVE — operators seed real API keys via the secrets-bootstrap
  # runbook (`aws secretsmanager put-secret-value`). Without this guard,
  # every `terraform apply` overwrites secret_string back to `{}` and
  # silently breaks every LLM-backed code path. Same pattern as the
  # chat_canaries secret below.
  lifecycle {
    ignore_changes = [secret_string]
  }
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
  name       = "${local.prefix}/chat-canaries"
  kms_key_id = aws_kms_key.secrets.arn

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
  # production prompt-leak detection. The same guard is applied to
  # llm_api_keys above for the same reason.
  lifecycle {
    ignore_changes = [secret_string]
  }
}
