locals {
  name_prefix = "${var.project_name}-${var.environment}"

  # Mirrors modules/ecs/main.tf locals.app_env_secrets — same JSON-key
  # extraction syntax. App Runner injects these via the instance role.
  app_env_secrets = {
    DATABASE_URL                  = "${var.secrets_arns["database"]}:connection_string::"
    REDIS_URL                     = "${var.secrets_arns["redis"]}:connection_url::"
    COGNITO_USER_POOL_ID          = "${var.secrets_arns["cognito"]}:user_pool_id::"
    COGNITO_APP_CLIENT_ID         = "${var.secrets_arns["cognito"]}:app_client_id::"
    COGNITO_BACKEND_CLIENT_ID     = "${var.secrets_arns["cognito"]}:backend_client_id::"
    COGNITO_BACKEND_CLIENT_SECRET = "${var.secrets_arns["cognito"]}:backend_client_secret::"
    S3_UPLOADS_BUCKET             = "${var.secrets_arns["s3"]}:bucket_name::"
  }
}

# Instance role for App Runner (runtime permissions: Secrets Manager, S3, SES, etc.)
data "aws_iam_policy_document" "apprunner_instance_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["tasks.apprunner.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "apprunner_instance" {
  name               = "${local.name_prefix}-apprunner-instance"
  assume_role_policy = data.aws_iam_policy_document.apprunner_instance_assume.json

  tags = {
    Name = "${local.name_prefix}-apprunner-instance"
  }
}

data "aws_iam_policy_document" "apprunner_secrets_read" {
  statement {
    effect = "Allow"
    actions = [
      "secretsmanager:GetSecretValue",
    ]
    # Story 10.4b extends the existing secrets-read statement with the chat
    # canaries ARN. Scoped exact-ARN (never wildcard) — App Runner needs it,
    # ECS/Celery does not. One statement is easier to review than two.
    resources = concat(values(var.secrets_arns), [var.chat_canaries_secret_arn])
  }
}

resource "aws_iam_role_policy" "apprunner_secrets" {
  name   = "secrets-read"
  role   = aws_iam_role.apprunner_instance.id
  policy = data.aws_iam_policy_document.apprunner_secrets_read.json
}

# kms:Decrypt + GenerateDataKey on the per-service CMKs that wrap Secrets
# Manager material and S3 uploads. Required because CMK-backed secret reads
# and KMS-encrypted S3 PutObject/GetObject both call kms:* under the hood.
data "aws_iam_policy_document" "apprunner_kms" {
  count = length(var.kms_key_arns) > 0 ? 1 : 0

  statement {
    sid    = "DecryptDataPlaneCMKs"
    effect = "Allow"
    actions = [
      "kms:Decrypt",
      "kms:GenerateDataKey",
      "kms:DescribeKey",
    ]
    resources = var.kms_key_arns
  }
}

resource "aws_iam_role_policy" "apprunner_kms" {
  count  = length(var.kms_key_arns) > 0 ? 1 : 0
  name   = "kms-decrypt"
  role   = aws_iam_role.apprunner_instance.id
  policy = data.aws_iam_policy_document.apprunner_kms[0].json
}

# SES send policy attachment. Empty arn (when ses_sender_email is unset)
# fail-closes: no attachment, so direct ses:SendEmail from FastAPI is denied.
resource "aws_iam_role_policy_attachment" "apprunner_ses" {
  count      = var.ses_send_policy_arn != "" ? 1 : 0
  role       = aws_iam_role.apprunner_instance.name
  policy_arn = var.ses_send_policy_arn
}

# Story 9.7 — AgentCore invoke for the App Runner instance role.
#
# Architecture.md says "FastAPI ECS task role" at line 1628 — but FastAPI runs
# on App Runner today, so the grant attaches to the App Runner instance role
# (apprunner_instance), not an ECS role. If a future migration moves FastAPI to
# ECS, the grant moves with it.
#
# 3-action minimum per architecture.md:1630; epics.md's broader `*` is compressed
# shorthand. Story 10.4a adds a fourth action (e.g. PutMemory) via a minor edit
# to this same statement if/when needed.
#
# No bedrock:InvokeModel on this role — chat uses AgentCore's server-side
# invocation, batch uses bedrock:InvokeModel from the Celery role.
# Gated on a concrete (non-wildcard) runtime ARN so dev/staging — which carry
# the wildcard default from variables.tf — don't ship a live agentcore invoke
# grant. Once Story 10.4a sets a concrete ARN in per-env tfvars, the policy
# attaches automatically. Symmetrical with the ECS bedrock_invoke policy's
# "empty list = skip" pattern at modules/ecs/main.tf.
locals {
  agentcore_policy_enabled = can(regex(":runtime/[A-Za-z0-9_-]+$", var.agentcore_runtime_arn))
}

data "aws_iam_policy_document" "apprunner_agentcore" {
  count = local.agentcore_policy_enabled ? 1 : 0

  statement {
    sid    = "BedrockAgentCoreInvoke"
    effect = "Allow"
    actions = [
      "bedrock-agentcore:InvokeAgentRuntime",
      "bedrock-agentcore:GetSession",
      "bedrock-agentcore:DeleteSession",
    ]
    resources = [var.agentcore_runtime_arn]
  }
}

resource "aws_iam_role_policy" "apprunner_agentcore" {
  count  = local.agentcore_policy_enabled ? 1 : 0
  name   = "agentcore-invoke"
  role   = aws_iam_role.apprunner_instance.id
  policy = data.aws_iam_policy_document.apprunner_agentcore[0].json
}

# ECR access role for App Runner
data "aws_iam_policy_document" "apprunner_ecr_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["build.apprunner.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "apprunner_ecr" {
  name               = "${local.name_prefix}-apprunner-ecr"
  assume_role_policy = data.aws_iam_policy_document.apprunner_ecr_assume.json

  tags = {
    Name = "${local.name_prefix}-apprunner-ecr"
  }
}

resource "aws_iam_role_policy_attachment" "apprunner_ecr" {
  role       = aws_iam_role.apprunner_ecr.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess"
}

# VPC Connector
resource "aws_apprunner_vpc_connector" "main" {
  vpc_connector_name = "${local.name_prefix}-vpc-connector"
  subnets            = var.private_subnet_ids
  security_groups    = [var.app_runner_security_group_id]

  tags = {
    Name = "${local.name_prefix}-vpc-connector"
  }
}

# App Runner Service
resource "aws_apprunner_service" "api" {
  service_name = "${local.name_prefix}-api"

  instance_configuration {
    cpu               = var.cpu
    memory            = var.memory
    instance_role_arn = aws_iam_role.apprunner_instance.arn
  }

  source_configuration {
    authentication_configuration {
      access_role_arn = aws_iam_role.apprunner_ecr.arn
    }

    image_repository {
      image_identifier      = "${var.ecr_repository_url}:${var.image_tag}"
      image_repository_type = "ECR"

      image_configuration {
        port = "8000"
        runtime_environment_variables = {
          ENVIRONMENT        = var.environment
          ENV                = var.environment
          AWS_SECRETS_PREFIX = "${var.project_name}/${var.environment}"
        }
        runtime_environment_secrets = local.app_env_secrets
      }
    }

    auto_deployments_enabled = false
  }

  health_check_configuration {
    protocol            = "HTTP"
    path                = "/health"
    interval            = 10
    timeout             = 5
    healthy_threshold   = 1
    unhealthy_threshold = 5
  }

  network_configuration {
    egress_configuration {
      egress_type       = "VPC"
      vpc_connector_arn = aws_apprunner_vpc_connector.main.arn
    }
  }

  auto_scaling_configuration_arn = aws_apprunner_auto_scaling_configuration_version.main.arn

  # CI deploys (manual release workflow, Phase D) update image_identifier to
  # :sha-<sha> via aws apprunner update-service. Without this lifecycle rule,
  # the next terraform apply would revert the service back to var.image_tag.
  lifecycle {
    ignore_changes = [
      source_configuration[0].image_repository[0].image_identifier,
    ]
  }

  tags = {
    Name = "${local.name_prefix}-api"
  }
}

resource "aws_apprunner_auto_scaling_configuration_version" "main" {
  auto_scaling_configuration_name = "${local.name_prefix}-autoscale"

  min_size        = var.min_instances
  max_size        = var.max_instances
  max_concurrency = 25

  tags = {
    Name = "${local.name_prefix}-autoscale"
  }
}
