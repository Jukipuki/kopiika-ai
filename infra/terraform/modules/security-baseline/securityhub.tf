# Security Hub aggregates findings from GuardDuty + Inspector + Config rules
# against industry standards. Subscribed to AWS Foundational Security Best
# Practices + CIS AWS Foundations Benchmark v1.4.

resource "aws_securityhub_account" "main" {
  enable_default_standards = false
}

# AWS Foundational Security Best Practices — broadest coverage, recommended baseline.
resource "aws_securityhub_standards_subscription" "aws_foundational" {
  standards_arn = "arn:${data.aws_partition.current.partition}:securityhub:${var.aws_region}::standards/aws-foundational-security-best-practices/v/1.0.0"
  depends_on    = [aws_securityhub_account.main]
}

# CIS AWS Foundations Benchmark v1.4.0 — regulator-friendly checklist.
resource "aws_securityhub_standards_subscription" "cis" {
  standards_arn = "arn:${data.aws_partition.current.partition}:securityhub:${var.aws_region}::standards/cis-aws-foundations-benchmark/v/1.4.0"
  depends_on    = [aws_securityhub_account.main]
}
