# `bedrock-guardrail` — Epic 10 chat safety guardrail

Story 10.2. Provisions the AWS Bedrock Guardrail consumed by Epic 10 chat
stories (10.5 streaming API, 10.6a grounding harness, 10.8b safety CI gate).

## Resource inventory

- `aws_bedrock_guardrail.this` — six content filters, three denied topics, PII
  redaction (managed list + IBAN + Ukrainian-passport regexes), managed
  profanity word filter, contextual grounding (0.85) + relevance (0.5).
- `aws_bedrock_guardrail_version.this` — initial published version, immutable.
  Story 10.6a will republish as it tunes grounding thresholds.
- `aws_cloudwatch_metric_alarm.block_rate_anomaly` — page-level alarm on
  intervened / invoked ratio ≥ 15% sustained over 5m × 3 periods.

## Inputs

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `project_name` | string | — | Prefix used in resource names. |
| `environment` | string | — | Deployment environment (`dev` / `staging` / `prod`). |
| `observability_sns_topic_arn` | string | `""` | SNS topic for the block-rate alarm action. Empty = console-only. |

## Outputs

| Name | Description |
|------|-------------|
| `guardrail_id` | Logical ID (used as the `GuardrailId` CloudWatch dimension). |
| `guardrail_arn` | Unversioned ARN → DRAFT. |
| `guardrail_version` | Published version number. |
| `guardrail_version_arn` | `${guardrail_arn}:${guardrail_version}`. |
| `guardrail_arns` | List of both ARNs — passed to ECS module IAM policy. |

## Operator notes

- **Grounding threshold (0.85) is owned by Story 10.6a.** This module lays the
  initial floor; 10.6a's eval harness moves the knob based on measured
  false-refuse / false-pass rates. Do not re-tune here without coordinating
  with 10.6a.
- **Warn-level alarm shipped 2026-04-26 by Story 10.9; see
  `aws_cloudwatch_metric_alarm.block_rate_warn`.** Threshold ≥ 5%
  sustained over 15m (3 × 5m periods); same `metric_query` math as the
  page-level `block_rate_anomaly`. Lands alongside the chat-observability
  metric filters in `infra/terraform/modules/app-runner/observability-chat.tf`.
- **Prod currently runs the alarm in console-only mode.**
  `observability_sns_topic_arn` in [`environments/prod/terraform.tfvars`](../../environments/prod/terraform.tfvars)
  is `""`, so breaches show in CloudWatch but no one is paged. Wire a real
  SNS topic before relying on the alarm for on-call rotation (owner: Story 10.9).
- **Versioned ARN auto-republishes on parent edits.** The
  `aws_bedrock_guardrail_version` has a
  `lifecycle { replace_triggered_by = [aws_bedrock_guardrail.this] }` so that
  every mutation of the parent guardrail (Story 10.6a grounding tune, future
  filter adjustments) forces a new published version. Consumers pinning
  `guardrail_version_arn` therefore pick up new behavior on the next apply
  instead of silently freezing at Story 10.2's initial config.
- **`enable_observability_alarms` does NOT gate this module's alarm.** That
  variable covers Story 11.9's ingestion signals. The Guardrail block-rate
  alarm is unconditional whenever this module is invoked.
- **Prod-only invocation.** The root-stack module block is gated behind
  `count = var.environment == "prod" ? 1 : 0`. Dev and staging run no chat
  traffic (no AgentCore runtime, no chat UI), so a Guardrail there would be
  pure spend. Flip the gate if chat ever lands in staging.
- **`PROMPT_ATTACK` output strength is `NONE` by Bedrock API design.** The
  filter only applies to prompts, not model completions.
- **IBAN + Ukrainian passport are regex-based.** Bedrock's managed PII list is
  US/EU-focused; UA-locale identity documents are not covered.

## References

- Story: `_bmad-output/implementation-artifacts/10-2-bedrock-guardrails-configuration.md`
- Architecture: `_bmad-output/planning-artifacts/architecture.md` §AI Safety
  Architecture (L1685–L1783).
- Validation bar: `terraform validate` + `terraform fmt -check` + `tfsec .` +
  operator-run `terraform plan` (no `terratest` / CI plan in this repo).
