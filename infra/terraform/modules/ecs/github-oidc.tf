# GitHub OIDC Provider for GitHub Actions
# This allows GitHub Actions to assume IAM roles without long-lived credentials.

data "aws_iam_openid_connect_provider" "github" {
  count = var.environment == "prod" ? 1 : 0
  url   = "https://token.actions.githubusercontent.com"
}

resource "aws_iam_openid_connect_provider" "github" {
  count = var.environment == "prod" ? 1 : 0
  url   = "https://token.actions.githubusercontent.com"

  client_id_list = ["sts.amazonaws.com"]

  thumbprint_list = [
    "6938fd4d98bab03faadb97b34396831e3780aea1",
    "1c58a3a8518e8759bf075b76b750d4f2df264fcd",
  ]

  tags = {
    Name = "${local.name_prefix}-github-oidc"
  }
}

# IAM role for GitHub Actions deployment
data "aws_iam_policy_document" "github_actions_assume" {
  count = var.environment == "prod" ? 1 : 0

  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github[0].arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_repo}:ref:refs/heads/main"]
    }
  }
}

resource "aws_iam_role" "github_actions" {
  count              = var.environment == "prod" ? 1 : 0
  name               = "${local.name_prefix}-github-actions"
  assume_role_policy = data.aws_iam_policy_document.github_actions_assume[0].json

  tags = {
    Name = "${local.name_prefix}-github-actions"
  }
}

data "aws_iam_policy_document" "github_actions_deploy" {
  count = var.environment == "prod" ? 1 : 0

  statement {
    sid    = "ECRAuth"
    effect = "Allow"
    actions = [
      "ecr:GetAuthorizationToken",
    ]
    resources = ["*"]
  }

  statement {
    sid    = "ECRPush"
    effect = "Allow"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:GetDownloadUrlForLayer",
      "ecr:BatchGetImage",
      "ecr:PutImage",
      "ecr:InitiateLayerUpload",
      "ecr:UploadLayerPart",
      "ecr:CompleteLayerUpload",
    ]
    resources = ["arn:aws:ecr:*:*:repository/${var.project_name}-*"]
  }

  statement {
    sid    = "AppRunnerDeploy"
    effect = "Allow"
    actions = [
      "apprunner:UpdateService",
      "apprunner:DescribeService",
    ]
    resources = ["arn:aws:apprunner:*:*:service/${var.project_name}-*"]
  }

  statement {
    sid    = "ECSDeploy"
    effect = "Allow"
    actions = [
      "ecs:UpdateService",
      "ecs:DescribeServices",
      "ecs:DescribeTaskDefinition",
      "ecs:RegisterTaskDefinition",
    ]
    resources = ["*"]
  }

  statement {
    sid    = "PassRole"
    effect = "Allow"
    actions = [
      "iam:PassRole",
    ]
    resources = ["arn:aws:iam::*:role/${var.project_name}-*"]
  }
}

resource "aws_iam_role_policy" "github_actions_deploy" {
  count  = var.environment == "prod" ? 1 : 0
  name   = "deploy"
  role   = aws_iam_role.github_actions[0].id
  policy = data.aws_iam_policy_document.github_actions_deploy[0].json
}

# -----------------------------------------------------------------------------
# Story 9.7 / TD-086 — GitHub OIDC role for the cross-provider CI matrix.
#
# .github/workflows/ci-backend-provider-matrix.yml runs on both push and
# pull_request, so the trust policy accepts both main-branch pushes AND PR
# token subjects. The deploy role above is main-only because it mutates
# production infra; this role is read-only bedrock:InvokeModel and is
# deliberately PR-reachable so PRs can exercise the Bedrock column. Harden
# further via a GitHub environment protection rule if this ever becomes a
# concern (noted in the story's Dev Notes).
#
# count is gated by var.github_bedrock_ci_enabled so dev/staging don't
# provision it. Prod tfvars sets it to true. Note that the underlying OIDC
# provider resource at `aws_iam_openid_connect_provider.github` is itself
# gated to prod, so enabling this flag outside prod will fail to plan — the
# gate is effectively "prod + opt-in".
# -----------------------------------------------------------------------------

data "aws_iam_policy_document" "github_bedrock_ci_assume" {
  count = var.github_bedrock_ci_enabled ? 1 : 0

  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github[0].arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values = [
        "repo:${var.github_repo}:ref:refs/heads/main",
        "repo:${var.github_repo}:pull_request",
      ]
    }
  }
}

resource "aws_iam_role" "github_bedrock_ci" {
  count              = var.github_bedrock_ci_enabled ? 1 : 0
  name               = "${local.name_prefix}-github-bedrock-ci"
  assume_role_policy = data.aws_iam_policy_document.github_bedrock_ci_assume[0].json
}

data "aws_iam_policy_document" "github_bedrock_ci" {
  count = var.github_bedrock_ci_enabled ? 1 : 0

  statement {
    sid    = "BedrockCIInvoke"
    effect = "Allow"
    actions = [
      "bedrock:InvokeModel",
      "bedrock:InvokeModelWithResponseStream",
    ]
    # Tighter than TD-086's fix-shape (which said just `eu.*`): the
    # foundation-model wildcards are locked to anthropic.* / amazon.nova-* so
    # future vendor additions in eu-north-1 don't silently gain CI invoke.
    resources = [
      "arn:aws:bedrock:eu-central-1:*:inference-profile/eu.*",
      "arn:aws:bedrock:eu-north-1::foundation-model/anthropic.*",
      "arn:aws:bedrock:eu-north-1::foundation-model/amazon.nova-*",
    ]
  }
}

resource "aws_iam_role_policy" "github_bedrock_ci" {
  count  = var.github_bedrock_ci_enabled ? 1 : 0
  name   = "bedrock-ci-invoke"
  role   = aws_iam_role.github_bedrock_ci[0].id
  policy = data.aws_iam_policy_document.github_bedrock_ci[0].json
}
