# ADR-0003: Cross-Region Inference Profile Data Residency for Bedrock Claude Models

- **Status:** Proposed
- **Date:** 2026-04-23
- **Deciders (pending):** DPO + Legal — TBD
- **Related:** Epic 9 (AI Infra Readiness), Story 9.4 decision doc `docs/decisions/agentcore-bedrock-region-availability-2026-04.md`, Story 9.5b (add Bedrock provider path — **blocked on this ADR flipping to accepted**), [architecture.md line 1610](../../_bmad-output/planning-artifacts/architecture.md#L1610)

## Context

Story 9.4's invoke-test spike confirmed that all active Claude models available in our primary region `eu-central-1` (Frankfurt) are `INFERENCE_PROFILE`-only — none are directly invocable via `ON_DEMAND` throughput. The project uses two tiers:

- **Haiku-class** (chat fast path / batch agents): `eu.anthropic.claude-haiku-4-5-20251001-v1:0` — inference profile hosted in `eu-central-1`, **routes physically to `eu-north-1` (Stockholm)**.
- **Sonnet-class** (chat reasoning tier): `eu.anthropic.claude-sonnet-4-6` — inference profile hosted in `eu-central-1`, **routes physically to `eu-north-1` (Stockholm)**.

Consequently, although the AWS IAM + service boundary stays in `eu-central-1` and the AgentCore + ECS + RDS footprint stays in `eu-central-1`, the **prompt + completion payloads physically leave `eu-central-1` and are processed in `eu-north-1`**. Both regions are EU AWS regions under the same GDPR regime, but architecture.md line 1610 requires a Data-residency review for any cross-region inference traffic before it ships to production.

The alternative — `global.*` inference profiles — would route to any AWS region including `us-*`, which is a significantly weaker data-residency posture. We explicitly rejected `global.*` in favour of `eu.*`.

## Decision (proposed)

Accept cross-region inference within the EU (`eu-central-1` → `eu-north-1`) for both Haiku and Sonnet tiers. The Status field (Proposed / Accepted) gates whether this decision is live; the three review criteria below are the sign-off checklist that flips the Status.

## Review Criteria (from architecture.md line 1610)

- [ ] **C1 — Data-category inventory:** User financial transaction data (transaction descriptions, amounts, categorization outputs, Teaching Feed prompts, Chat-with-Finances messages) will cross the `eu-central-1` → `eu-north-1` boundary. Confirm this data set is permitted to transit to Sweden under the current privacy notice and Ukrainian/EU user expectations.
- [ ] **C2 — Sub-processor disclosure:** AWS `eu-north-1` must be listed in the project's sub-processor register if a register exists, or added before ship if one is being created for Epic 10.
- [ ] **C3 — Retention + logging:** Confirm AWS Bedrock's retention policy for cross-region inference traffic (0-day logging by default unless model-invocation-logging is explicitly enabled on the account) matches our retention commitments, and that no logging destination outside the EU is implicitly enabled.

## Consequences

- **If accepted:** Story 9.5b wires `ChatBedrock(model_id="arn:aws:bedrock:eu-central-1:...:inference-profile/eu.anthropic.claude-...")` in `backend/app/agents/llm.py`. No Terraform region change required.
- **If rejected:** Two options — (a) pivot Bedrock calls to `us-east-1` with `global.*` profiles (worse residency, defeats the purpose) or (b) stay on direct Anthropic API (current state) and defer Bedrock migration past Epic 10. Option (b) is the safer fallback; Story 9.5b would be re-scoped accordingly.
- **Status:** This ADR is **Proposed**, not Accepted. Story 9.5b's cross-region inference path is **blocked** on this flipping to Accepted. Update `_bmad-output/implementation-artifacts/sprint-status.yaml` when the status changes.

## Owner / Next Action

**DPO + Legal — TBD.** Once reviewers are identified, replace "TBD" with their names and dates against each of C1/C2/C3 as they are signed off. When all three are checked, flip `Status: Proposed` → `Status: Accepted` and unblock Story 9.5b.

## References

- Story 9.4 decision doc: [`docs/decisions/agentcore-bedrock-region-availability-2026-04.md`](../decisions/agentcore-bedrock-region-availability-2026-04.md)
- Invoke-test evidence: [`docs/decisions/agentcore-bedrock-region-availability-2026-04/invoke-tests.json`](../decisions/agentcore-bedrock-region-availability-2026-04/invoke-tests.json)
- Architecture Region Strategy: [architecture.md#Region Strategy](../../_bmad-output/planning-artifacts/architecture.md)
- Sprint status Story 9.5b entry: [`_bmad-output/implementation-artifacts/sprint-status.yaml`](../../_bmad-output/implementation-artifacts/sprint-status.yaml)
