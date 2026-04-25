locals {
  name_prefix = "${var.project_name}-${var.environment}"
  has_sender  = var.sender_email != ""
}

# Verify sender email identity
resource "aws_ses_email_identity" "sender" {
  count = local.has_sender ? 1 : 0
  email = var.sender_email
}

# IAM policy for SES send permissions.
# Only created when sender_email is set — fail-closed: no policy without a verified sender.
data "aws_iam_policy_document" "ses_send" {
  count = local.has_sender ? 1 : 0

  statement {
    effect = "Allow"
    actions = [
      "ses:SendEmail",
      "ses:SendRawEmail",
    ]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "ses:FromAddress"
      values   = [var.sender_email]
    }
  }
}

resource "aws_iam_policy" "ses_send" {
  count  = local.has_sender ? 1 : 0
  name   = "${local.name_prefix}-ses-send"
  policy = data.aws_iam_policy_document.ses_send[0].json

  tags = {
    Name = "${local.name_prefix}-ses-send"
  }
}

# Cognito's `email_sending_account = "DEVELOPER"` mode calls SES on its own
# service principal (cognito-idp.amazonaws.com), not on any IAM role. The
# permission must therefore be granted via an SES identity policy on the
# verified sender, NOT via the IAM policy above (which is for direct SES
# calls from App Runner / Celery). Without this, signup confirmation emails
# fail with AccessDenied.
data "aws_iam_policy_document" "cognito_ses_send" {
  count = local.has_sender ? 1 : 0

  statement {
    sid     = "AllowCognitoToSendFromVerifiedAddress"
    effect  = "Allow"
    actions = ["ses:SendEmail", "ses:SendRawEmail"]
    principals {
      type        = "Service"
      identifiers = ["cognito-idp.amazonaws.com"]
    }
    resources = [aws_ses_email_identity.sender[0].arn]
  }
}

resource "aws_ses_identity_policy" "cognito" {
  count    = local.has_sender ? 1 : 0
  identity = aws_ses_email_identity.sender[0].arn
  name     = "${local.name_prefix}-cognito"
  policy   = data.aws_iam_policy_document.cognito_ses_send[0].json
}
