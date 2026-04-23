locals {
  name_prefix = "${var.project_name}-${var.environment}"
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
    sid       = "BedrockApplyGuardrail"
    effect    = "Allow"
    actions   = ["bedrock:ApplyGuardrail"]
    resources = [var.bedrock_guardrail_arn]
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
      image     = "${var.ecr_repository_url}:latest"
      essential = true

      command = [
        "celery", "-A", "app.tasks.celery_app", "worker", "--loglevel=info"
      ]

      environment = [
        {
          name  = "ENVIRONMENT"
          value = var.environment
        },
        {
          name  = "AWS_SECRETS_PREFIX"
          value = "${var.project_name}/${var.environment}"
        },
        # Story 9.7 — explicit region for boto3's bedrock-runtime client.
        # ECS task-metadata region works today but is ambiguous when code calls
        # boto3.client("bedrock-runtime") with no region_name kwarg.
        {
          name  = "AWS_REGION"
          value = var.aws_region
        },
      ]

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
      image     = "${var.ecr_repository_url}:beat-latest"
      essential = true

      command = [
        "celery", "-A", "app.tasks.celery_app", "beat", "--loglevel=info"
      ]

      environment = [
        {
          name  = "ENVIRONMENT"
          value = var.environment
        },
        {
          name  = "AWS_SECRETS_PREFIX"
          value = "${var.project_name}/${var.environment}"
        },
        # Story 9.7 — explicit region for boto3's bedrock-runtime client.
        # ECS task-metadata region works today but is ambiguous when code calls
        # boto3.client("bedrock-runtime") with no region_name kwarg.
        {
          name  = "AWS_REGION"
          value = var.aws_region
        },
      ]

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

  tags = {
    Name = "${local.name_prefix}-beat"
  }
}
