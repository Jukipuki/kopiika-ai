output "guardrail_id" {
  description = "Logical ID of the Bedrock Guardrail (used as the GuardrailId CloudWatch dimension)."
  value       = aws_bedrock_guardrail.this.guardrail_id
}

output "guardrail_arn" {
  description = "Unversioned guardrail ARN (points at DRAFT). Consumers intentionally riding live edits (e.g. Story 10.6a harness) reference this."
  value       = aws_bedrock_guardrail.this.guardrail_arn
}

output "guardrail_version" {
  description = "Published immutable version number (e.g. \"1\"). Bumps whenever the guardrail is re-published."
  value       = aws_bedrock_guardrail_version.this.version
}

output "guardrail_version_arn" {
  description = "Versioned guardrail ARN (unversioned ARN suffixed with the published version). Production consumers (Story 10.5) pin this for stable behaviour."
  value       = "${aws_bedrock_guardrail.this.guardrail_arn}:${aws_bedrock_guardrail_version.this.version}"
}

output "guardrail_arns" {
  description = "Both unversioned and versioned ARNs, as a list. Used by the ECS module IAM policy so bedrock:ApplyGuardrail can target either."
  value = [
    aws_bedrock_guardrail.this.guardrail_arn,
    "${aws_bedrock_guardrail.this.guardrail_arn}:${aws_bedrock_guardrail_version.this.version}",
  ]
}
