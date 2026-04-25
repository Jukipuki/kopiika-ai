# VPC Flow Logs — captures every accepted/rejected flow on the VPC for
# exfiltration / lateral-movement forensics. Destination is CloudWatch
# Logs (queryable via Logs Insights). Retention scales with environment.

# Per-service KMS CMK matching the Phase C pattern: every sensitive store
# (RDS, Redis, Secrets, S3 uploads, ECR, CloudTrail) is wrapped in its own
# CMK. Flow logs contain source/dest IPs + ports — moderate forensic value.
# data.aws_caller_identity.current and data.aws_region.current are declared
# in main.tf alongside the other module-scoped data sources.

resource "aws_kms_key" "flow_logs" {
  description             = "${local.name_prefix} VPC Flow Logs encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  policy                  = data.aws_iam_policy_document.flow_logs_kms.json

  tags = {
    Name = "${local.name_prefix}-vpc-flow"
  }
}

resource "aws_kms_alias" "flow_logs" {
  name          = "alias/${local.name_prefix}-vpc-flow"
  target_key_id = aws_kms_key.flow_logs.key_id
}

# CloudWatch Logs in this region must have kms:Encrypt/Decrypt/ReEncrypt
# granted to the logs.<region>.amazonaws.com service principal, scoped via
# encryption-context to this account's log groups.
data "aws_iam_policy_document" "flow_logs_kms" {
  statement {
    sid    = "EnableRootAccountAdmin"
    effect = "Allow"
    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"]
    }
    actions   = ["kms:*"]
    resources = ["*"]
  }

  statement {
    sid    = "AllowCloudWatchLogsUseOfKey"
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["logs.${data.aws_region.current.name}.amazonaws.com"]
    }
    actions = [
      "kms:Encrypt",
      "kms:Decrypt",
      "kms:ReEncrypt*",
      "kms:GenerateDataKey*",
      "kms:DescribeKey",
    ]
    resources = ["*"]
    condition {
      test     = "ArnEquals"
      variable = "kms:EncryptionContext:aws:logs:arn"
      values   = ["arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:/vpc/${local.name_prefix}-flow"]
    }
  }
}

resource "aws_cloudwatch_log_group" "vpc_flow" {
  name              = "/vpc/${local.name_prefix}-flow"
  retention_in_days = var.environment == "prod" ? 90 : 14
  kms_key_id        = aws_kms_key.flow_logs.arn

  tags = {
    Name = "${local.name_prefix}-vpc-flow"
  }
}

data "aws_iam_policy_document" "vpc_flow_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["vpc-flow-logs.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "vpc_flow" {
  name               = "${local.name_prefix}-vpc-flow"
  assume_role_policy = data.aws_iam_policy_document.vpc_flow_assume.json

  tags = {
    Name = "${local.name_prefix}-vpc-flow"
  }
}

data "aws_iam_policy_document" "vpc_flow_logs" {
  statement {
    effect = "Allow"
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
      "logs:DescribeLogStreams",
    ]
    resources = ["${aws_cloudwatch_log_group.vpc_flow.arn}:*"]
  }
}

resource "aws_iam_role_policy" "vpc_flow" {
  name   = "vpc-flow-logs-write"
  role   = aws_iam_role.vpc_flow.id
  policy = data.aws_iam_policy_document.vpc_flow_logs.json
}

resource "aws_flow_log" "main" {
  iam_role_arn    = aws_iam_role.vpc_flow.arn
  log_destination = aws_cloudwatch_log_group.vpc_flow.arn
  traffic_type    = "ALL"
  vpc_id          = aws_vpc.main.id

  tags = {
    Name = "${local.name_prefix}-vpc-flow"
  }
}
