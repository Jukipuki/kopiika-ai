# GitHub OIDC Provider for GitHub Actions.
# Allows GitHub Actions to assume IAM roles without long-lived credentials.
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
      values = [
        # build-image.yml — OIDC token from a push to main, no environment.
        "repo:${var.github_repo}:ref:refs/heads/main",
        # deploy-backend.yml — workflow_dispatch with `environment: production`,
        # which switches the sub claim format. Required-reviewer protection on
        # the `production` GitHub Environment is the actual gate.
        "repo:${var.github_repo}:environment:production",
      ]
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
      "ecr:DescribeImages",
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
      "apprunner:ListOperations",
    ]
    resources = ["arn:aws:apprunner:*:*:service/${var.project_name}-*/*"]
  }

  # apprunner:ListServices does not support resource-level scoping (AWS
  # requires "*"). Used by deploy-backend.yml to resolve the service ARN
  # by name; can be removed if the operator instead stores the resolved
  # ARN as vars.APP_RUNNER_SERVICE_ARN after first apply.
  statement {
    sid       = "AppRunnerListServices"
    effect    = "Allow"
    actions   = ["apprunner:ListServices"]
    resources = ["*"]
  }

  statement {
    sid    = "ECSDeployScoped"
    effect = "Allow"
    actions = [
      "ecs:UpdateService",
      "ecs:DescribeServices",
    ]
    resources = [
      "arn:aws:ecs:*:*:service/${var.project_name}-*/*",
    ]
  }

  # RegisterTaskDefinition + DescribeTaskDefinition can only be * because AWS
  # does not support resource-level scoping on those actions. Acceptable: the
  # scoped UpdateService above is the choke point for using a malicious task def.
  statement {
    sid    = "ECSTaskDefRegister"
    effect = "Allow"
    actions = [
      "ecs:DescribeTaskDefinition",
      "ecs:RegisterTaskDefinition",
    ]
    resources = ["*"]
  }

  # ecs:TagResource is required by RegisterTaskDefinition when the task-def
  # carries tags (which ours do — Name + Project + Environment + ManagedBy).
  # Scoped to the project's task-def family.
  statement {
    sid    = "ECSTagTaskDefs"
    effect = "Allow"
    actions = [
      "ecs:TagResource",
      "ecs:UntagResource",
    ]
    resources = ["arn:aws:ecs:*:*:task-definition/${var.project_name}-*"]
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
# Trust scope is the GitHub Environment "bedrock-ci". That environment is
# configured in GitHub with required reviewers (you) so an arbitrary PR
# can no longer assume this role and burn Bedrock budget; an approval is
# required before the workflow can request the OIDC token with the
# environment claim. See the workflow at
# .github/workflows/ci-backend-provider-matrix.yml — it must set
# `environment: bedrock-ci` on any job that assumes this role.
#
# Defense-in-depth: the AWS Budgets alarm in security-baseline caps Bedrock
# spend account-wide, so even a misconfigured environment can't run away.
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
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values = [
        "repo:${var.github_repo}:environment:bedrock-ci",
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

# -----------------------------------------------------------------------------
# Story 10.8b / TD-131 — GitHub OIDC role for the safety harness CI gate.
#
# Trust scope is the existing GitHub Environment "bedrock-ci" so the
# required-reviewer approval gate is reused (no second environment to
# configure). The role grants:
#   - bedrock:InvokeModel + InvokeModelWithResponseStream against the
#     standard Bedrock inference profiles + foundation models the chat
#     agent uses (mirrors github_bedrock_ci);
#   - bedrock:ApplyGuardrail against the SAFETY guardrail ARNs only
#     (separate from the prod guardrail so synthetic adversarial traffic
#     does not inflate prod block-rate alarms);
#   - secretsmanager:GetSecretValue on the chat_canaries secret only,
#     so the runner can resolve <CANARY_*> placeholders against the
#     production canary set at run-time.
#
# Defense-in-depth: the AWS Budgets alarm in security-baseline caps Bedrock
# spend account-wide; the per-PR runner adds ~$0.50–$1.00 of inference at
# Haiku tier so the gate stays well below the cap.
# -----------------------------------------------------------------------------

data "aws_iam_policy_document" "github_safety_test_assume" {
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
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values = [
        "repo:${var.github_repo}:environment:bedrock-ci",
      ]
    }
  }
}

resource "aws_iam_role" "github_safety_test" {
  count              = var.github_bedrock_ci_enabled ? 1 : 0
  name               = "${local.name_prefix}-github-safety-test"
  assume_role_policy = data.aws_iam_policy_document.github_safety_test_assume[0].json
}

data "aws_iam_policy_document" "github_safety_test" {
  count = var.github_bedrock_ci_enabled ? 1 : 0

  statement {
    sid    = "SafetyHarnessInvoke"
    effect = "Allow"
    actions = [
      "bedrock:InvokeModel",
      "bedrock:InvokeModelWithResponseStream",
    ]
    resources = [
      "arn:aws:bedrock:eu-central-1:*:inference-profile/eu.*",
      "arn:aws:bedrock:eu-north-1::foundation-model/anthropic.*",
      "arn:aws:bedrock:eu-north-1::foundation-model/amazon.nova-*",
    ]
  }

  # Apply the SAFETY guardrail only — prod ARN deliberately excluded so the
  # runner can never accidentally inflate prod block-rate metrics.
  dynamic "statement" {
    for_each = length(var.safety_guardrail_arns) > 0 ? [1] : []
    content {
      sid       = "SafetyHarnessApplyGuardrail"
      effect    = "Allow"
      actions   = ["bedrock:ApplyGuardrail"]
      resources = var.safety_guardrail_arns
    }
  }

  # Read-only access to the chat_canaries secret so the runner resolves the
  # <CANARY_*> placeholders against the live canary set.
  dynamic "statement" {
    for_each = var.chat_canaries_secret_arn != "" ? [1] : []
    content {
      sid       = "SafetyHarnessReadCanaries"
      effect    = "Allow"
      actions   = ["secretsmanager:GetSecretValue"]
      resources = [var.chat_canaries_secret_arn]
    }
  }
}

resource "aws_iam_role_policy" "github_safety_test" {
  count  = var.github_bedrock_ci_enabled ? 1 : 0
  name   = "safety-harness"
  role   = aws_iam_role.github_safety_test[0].id
  policy = data.aws_iam_policy_document.github_safety_test[0].json
}
