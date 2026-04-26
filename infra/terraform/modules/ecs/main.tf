locals {
  name_prefix = "${var.project_name}-${var.environment}"

  # Secrets injected as env vars at container start. ECS uses the EXECUTION
  # role (not task role) to fetch these. JSON-key extraction syntax:
  # `<secret-arn>:<json-key>::` (the trailing `::` are version-stage and
  # version-id, both blank → AWSCURRENT).
  app_env_secrets = [
    { name = "DATABASE_URL", valueFrom = "${var.secrets_arns["database"]}:connection_string::" },
    { name = "REDIS_URL", valueFrom = "${var.secrets_arns["redis"]}:connection_url::" },
    { name = "COGNITO_USER_POOL_ID", valueFrom = "${var.secrets_arns["cognito"]}:user_pool_id::" },
    { name = "COGNITO_APP_CLIENT_ID", valueFrom = "${var.secrets_arns["cognito"]}:app_client_id::" },
    { name = "COGNITO_BACKEND_CLIENT_ID", valueFrom = "${var.secrets_arns["cognito"]}:backend_client_id::" },
    { name = "COGNITO_BACKEND_CLIENT_SECRET", valueFrom = "${var.secrets_arns["cognito"]}:backend_client_secret::" },
    { name = "S3_UPLOADS_BUCKET", valueFrom = "${var.secrets_arns["s3"]}:bucket_name::" },
    # llm-api-keys is operator-bootstrapped (lifecycle.ignore_changes).
    # Required by app/rag/embeddings.py + LLM provider clients. If a key
    # is missing from the secret JSON, ECS task launch will fail with
    # ResourceInitializationError — re-seed via secrets-bootstrap.md.
    { name = "OPENAI_API_KEY", valueFrom = "${var.secrets_arns["llm_api_keys"]}:OPENAI_API_KEY::" },
    { name = "ANTHROPIC_API_KEY", valueFrom = "${var.secrets_arns["llm_api_keys"]}:ANTHROPIC_API_KEY::" },
  ]

  # Plain env vars (not from secrets). ENV gates the local-Fernet vs KMS
  # branch in app/core/crypto.py — must be "prod" in production.
  app_env_plain = [
    { name = "ENVIRONMENT", value = var.environment },
    { name = "ENV", value = var.environment },
    { name = "AWS_SECRETS_PREFIX", value = "${var.project_name}/${var.environment}" },
    { name = "AWS_REGION", value = var.aws_region },
    # Bedrock IAM is wired (var.bedrock_invocation_arns) — no third-party
    # API credits needed. Anthropic direct API (LLM_PROVIDER=anthropic)
    # remains available as a fallback if ANTHROPIC_API_KEY is set, useful
    # for local dev outside AWS.
    { name = "LLM_PROVIDER", value = "bedrock" },
  ]
}

# ECS Cluster
resource "aws_ecs_cluster" "main" {
  name = "${local.name_prefix}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = {
    Name = "${local.name_prefix}-cluster"
  }
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "worker" {
  name              = "/ecs/${local.name_prefix}-worker"
  retention_in_days = 30

  tags = {
    Name = "${local.name_prefix}-worker-logs"
  }
}

# ECS Task Execution Role
data "aws_iam_policy_document" "ecs_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ecs_execution" {
  name               = "${local.name_prefix}-ecs-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json

  tags = {
    Name = "${local.name_prefix}-ecs-execution"
  }
}

resource "aws_iam_role_policy_attachment" "ecs_execution" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Inline policy granting the EXECUTION role access to fetch secret values
# at task-launch (for the `secrets` field on container definitions, used to
# inject DATABASE_URL / REDIS_URL / COGNITO_* / S3_UPLOADS_BUCKET as env
# vars at container start). The AWS-managed AmazonECSTaskExecutionRolePolicy
# does NOT include secretsmanager:GetSecretValue or kms:Decrypt.
data "aws_iam_policy_document" "ecs_execution_secrets" {
  statement {
    sid       = "GetSecretsForEnvInjection"
    effect    = "Allow"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = values(var.secrets_arns)
  }

  statement {
    sid       = "DecryptSecretsCMK"
    effect    = "Allow"
    actions   = ["kms:Decrypt"]
    resources = var.kms_key_arns
  }
}

resource "aws_iam_role_policy" "ecs_execution_secrets" {
  name   = "secrets-env-injection"
  role   = aws_iam_role.ecs_execution.id
  policy = data.aws_iam_policy_document.ecs_execution_secrets.json
}

# ECS Task Role (for Secrets Manager access)
resource "aws_iam_role" "ecs_task" {
  name               = "${local.name_prefix}-ecs-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json

  tags = {
    Name = "${local.name_prefix}-ecs-task"
  }
}

data "aws_iam_policy_document" "ecs_secrets_read" {
  statement {
    effect = "Allow"
    actions = [
      "secretsmanager:GetSecretValue",
    ]
    resources = values(var.secrets_arns)
  }
}

resource "aws_iam_role_policy" "ecs_task_secrets" {
  name   = "secrets-read"
  role   = aws_iam_role.ecs_task.id
  policy = data.aws_iam_policy_document.ecs_secrets_read.json
}

# Read-only kms:Decrypt + DescribeKey on the per-service CMKs that wrap
# Secrets Manager material and S3 uploads. ECS workers (Celery) read both
# (SecretsManager:GetSecretValue + s3:GetObject) but do NOT write —
# upload_service.py:put_object runs on App Runner, not ECS. GenerateDataKey
# is intentionally absent here.
data "aws_iam_policy_document" "ecs_task_kms" {
  count = length(var.kms_key_arns) > 0 ? 1 : 0

  statement {
    sid    = "DecryptDataPlaneCMKs"
    effect = "Allow"
    actions = [
      "kms:Decrypt",
      "kms:DescribeKey",
    ]
    resources = var.kms_key_arns
  }
}

resource "aws_iam_role_policy" "ecs_task_kms" {
  count  = length(var.kms_key_arns) > 0 ? 1 : 0
  name   = "kms-decrypt"
  role   = aws_iam_role.ecs_task.id
  policy = data.aws_iam_policy_document.ecs_task_kms[0].json
}

# S3 read on the uploads bucket. Celery worker (processing_tasks.py)
# calls get_object to download user-uploaded files for parsing. No write
# perms — uploads land via App Runner.
data "aws_iam_policy_document" "ecs_task_s3" {
  count = var.s3_uploads_bucket_arn != "" ? 1 : 0

  statement {
    sid       = "S3UploadsRead"
    effect    = "Allow"
    actions   = ["s3:GetObject"]
    resources = ["${var.s3_uploads_bucket_arn}/*"]
  }
}

resource "aws_iam_role_policy" "ecs_task_s3" {
  count  = var.s3_uploads_bucket_arn != "" ? 1 : 0
  name   = "s3-uploads-read"
  role   = aws_iam_role.ecs_task.id
  policy = data.aws_iam_policy_document.ecs_task_s3[0].json
}

# Story 9.7 — Bedrock invoke + Guardrail for the Celery task role.
# Principal is aws_iam_role.ecs_task (NOT ecs_execution) — boto3 inside the
# container sees only the task role via the ECS credentials endpoint. The
# `count` guard keeps dev/staging (which leave bedrock_invocation_arns empty)
# from attaching an empty policy.
data "aws_iam_policy_document" "ecs_task_bedrock" {
  count = length(var.bedrock_invocation_arns) > 0 ? 1 : 0

  statement {
    sid    = "BedrockInvokeModel"
    effect = "Allow"
    actions = [
      "bedrock:InvokeModel",
      "bedrock:InvokeModelWithResponseStream",
    ]
    # Must include BOTH the eu-central-1 inference profiles AND the eu-north-1
    # foundation-model ARNs the profiles physically route to — cross-region
    # inference requires both per the Story 9.4 decision doc.
    resources = var.bedrock_invocation_arns
  }

  statement {
    sid     = "BedrockApplyGuardrail"
    effect  = "Allow"
    actions = ["bedrock:ApplyGuardrail"]
    # Both unversioned (DRAFT) and versioned ARNs — consumers may target either
    # (Story 10.2 AC #5). Empty list is not possible here: the enclosing
    # count guard keeps dev/staging out of this branch entirely.
    resources = var.bedrock_guardrail_arns
  }
}

resource "aws_iam_role_policy" "ecs_task_bedrock_invoke" {
  count  = length(var.bedrock_invocation_arns) > 0 ? 1 : 0
  name   = "bedrock-invoke"
  role   = aws_iam_role.ecs_task.id
  policy = data.aws_iam_policy_document.ecs_task_bedrock[0].json
}

# Task Definition
resource "aws_ecs_task_definition" "worker" {
  family                   = "${local.name_prefix}-worker"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name      = "worker"
      image     = "${var.ecr_repository_url}:${var.image_tag}"
      essential = true

      command = [
        "celery", "-A", "app.tasks.celery_app", "worker", "--loglevel=info"
      ]

      environment = local.app_env_plain
      secrets     = local.app_env_secrets

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.worker.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "worker"
        }
      }
    }
  ])

  tags = {
    Name = "${local.name_prefix}-worker"
  }
}

# ECS Service
resource "aws_ecs_service" "worker" {
  name            = "${local.name_prefix}-worker"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.worker.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [var.ecs_security_group_id]
    assign_public_ip = false
  }

  # CI deploys (manual release workflow, Phase D) register a new task-def
  # revision per :sha-<sha> image and update the service to it. Without this
  # rule, the next terraform apply would revert to the TF-managed revision.
  lifecycle {
    ignore_changes = [task_definition]
  }

  tags = {
    Name = "${local.name_prefix}-worker"
  }
}

# -----------------------------------------------------------------------------
# Celery beat scheduler (Story 7.9 / TD-026)
#
# Runs a separate ECS service whose container is commanded `celery ... beat`.
# Beat publishes scheduled messages (see backend/app/tasks/celery_app.py
# `beat_schedule`); the worker consumes them. They MUST be separate processes.
#
# desired_count is hardcoded to 1 — two beat replicas connected to the same
# broker will each fire every scheduled task at every cadence, multiplying every
# job. If HA beat ever becomes necessary, switch the scheduler store to
# `celery-redbeat` (Redis-backed, leader election) first.
# -----------------------------------------------------------------------------

resource "aws_cloudwatch_log_group" "beat" {
  name              = "/ecs/${local.name_prefix}-beat"
  retention_in_days = 30

  tags = {
    Name = "${local.name_prefix}-beat-logs"
  }
}

resource "aws_ecs_task_definition" "beat" {
  family                   = "${local.name_prefix}-beat"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name = "beat"
      # Bootstrap tag only — the deploy workflow renders a task-def revision
      # pinned to :beat-${sha} on every push, so the effective running image
      # is the most recent build, not :beat-latest. See
      # .github/workflows/deploy-backend.yml → "Render beat task definition".
      image     = "${var.ecr_repository_url}:beat-${var.image_tag}"
      essential = true

      command = [
        "celery", "-A", "app.tasks.celery_app", "beat", "--loglevel=info"
      ]

      environment = local.app_env_plain
      secrets     = local.app_env_secrets

      # Liveness: verifies the celery app still imports. Catches the
      # "container is there but broken" class of failure; does NOT prove beat
      # is actually publishing scheduled messages (see operator-runbook.md
      # "Verifying beat is running" for the end-to-end check).
      healthCheck = {
        command     = ["CMD-SHELL", "python -c 'from app.tasks.celery_app import celery_app'"]
        interval    = 60
        timeout     = 10
        retries     = 3
        startPeriod = 30
      }

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.beat.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "beat"
        }
      }
    }
  ])

  tags = {
    Name = "${local.name_prefix}-beat"
  }
}

resource "aws_ecs_service" "beat" {
  name            = "${local.name_prefix}-beat"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.beat.arn
  desired_count   = 1 # MUST stay 1 — duplicate beat replicas multi-fire every scheduled task
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [var.ecs_security_group_id]
    assign_public_ip = false
  }

  lifecycle {
    ignore_changes = [task_definition]
  }

  tags = {
    Name = "${local.name_prefix}-beat"
  }
}
