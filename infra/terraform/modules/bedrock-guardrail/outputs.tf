output "guardrail_id" {
  description = "Logical ID of the prod chat Bedrock Guardrail (used as the GuardrailId CloudWatch dimension)."
  value       = aws_bedrock_guardrail.this["chat"].guardrail_id
}

output "guardrail_arn" {
  description = "Unversioned prod chat guardrail ARN (points at DRAFT). Consumers intentionally riding live edits (e.g. Story 10.6a harness) reference this."
  value       = aws_bedrock_guardrail.this["chat"].guardrail_arn
}

output "guardrail_version" {
  description = "Published immutable version number (e.g. \"1\") for the prod chat guardrail. Bumps whenever the guardrail is re-published."
  value       = aws_bedrock_guardrail_version.this["chat"].version
}

output "guardrail_version_arn" {
  description = "Versioned prod chat guardrail ARN (unversioned ARN suffixed with the published version). Production consumers (Story 10.5) pin this for stable behaviour."
  value       = "${aws_bedrock_guardrail.this["chat"].guardrail_arn}:${aws_bedrock_guardrail_version.this["chat"].version}"
}

output "guardrail_arns" {
  description = "Both unversioned and versioned ARNs for the prod chat guardrail, as a list. Used by the ECS module IAM policy so bedrock:ApplyGuardrail can target either."
  value = [
    aws_bedrock_guardrail.this["chat"].guardrail_arn,
    "${aws_bedrock_guardrail.this["chat"].guardrail_arn}:${aws_bedrock_guardrail_version.this["chat"].version}",
  ]
}

# ── Story 10.8b safety variant ────────────────────────────────────────────
# Separate Guardrail with identical config but no CloudWatch alarm. The
# safety harness (backend/tests/ai_safety/test_red_team_runner.py) attaches
# this ARN via the BEDROCK_GUARDRAIL_ARN_SAFETY repo var so synthetic
# adversarial traffic does not pollute the prod block-rate page (per
# architecture.md §Observability & Alarms L1761-L1774).

output "safety_guardrail_id" {
  description = "Logical ID of the safety-runner Bedrock Guardrail (Story 10.8b)."
  value       = aws_bedrock_guardrail.this["safety"].guardrail_id
}

output "safety_guardrail_arn" {
  description = "Unversioned safety-runner guardrail ARN. Set as repo var BEDROCK_GUARDRAIL_ARN_SAFETY."
  value       = aws_bedrock_guardrail.this["safety"].guardrail_arn
}

output "safety_guardrail_version" {
  description = "Published version number for the safety-runner guardrail."
  value       = aws_bedrock_guardrail_version.this["safety"].version
}

output "safety_guardrail_version_arn" {
  description = "Versioned safety-runner guardrail ARN."
  value       = "${aws_bedrock_guardrail.this["safety"].guardrail_arn}:${aws_bedrock_guardrail_version.this["safety"].version}"
}

output "safety_guardrail_arns" {
  description = "Both unversioned and versioned ARNs for the safety-runner guardrail. Used by the safety-test IAM role so bedrock:ApplyGuardrail can target either."
  value = [
    aws_bedrock_guardrail.this["safety"].guardrail_arn,
    "${aws_bedrock_guardrail.this["safety"].guardrail_arn}:${aws_bedrock_guardrail_version.this["safety"].version}",
  ]
}
