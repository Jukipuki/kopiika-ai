output "sender_identity_arn" {
  value = length(aws_ses_email_identity.sender) > 0 ? aws_ses_email_identity.sender[0].arn : ""
}

output "ses_send_policy_arn" {
  value = length(aws_iam_policy.ses_send) > 0 ? aws_iam_policy.ses_send[0].arn : ""
}
