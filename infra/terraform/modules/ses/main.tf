locals {
  name_prefix = "${var.project_name}-${var.environment}"
  has_sender  = var.sender_email != ""
}

# Verify sender email identity
resource "aws_ses_email_identity" "sender" {
  count = local.has_sender ? 1 : 0
  email = var.sender_email
}

# IAM policy for SES send permissions
data "aws_iam_policy_document" "ses_send" {
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
      values   = local.has_sender ? [var.sender_email] : ["*"]
    }
  }
}

resource "aws_iam_policy" "ses_send" {
  name   = "${local.name_prefix}-ses-send"
  policy = data.aws_iam_policy_document.ses_send.json

  tags = {
    Name = "${local.name_prefix}-ses-send"
  }
}
