# Bedrock Provider Smoke Test — 2026-04-23

## Context

- **Story 9.5b** ([9-5b-add-bedrock-provider-path.md](../../_bmad-output/implementation-artifacts/9-5b-add-bedrock-provider-path.md)) wires `langchain_aws.ChatBedrockConverse` into [backend/app/agents/llm.py](../../backend/app/agents/llm.py)'s factory, completing the seam Story 9.5a opened.
- Bedrock ARNs (`eu.anthropic.claude-haiku-4-5-20251001-v1:0`, `eu.anthropic.claude-sonnet-4-6`) were pinned in [backend/app/agents/models.yaml](../../backend/app/agents/models.yaml) by **Story 9.4** — see [agentcore-bedrock-region-availability-2026-04.md](./agentcore-bedrock-region-availability-2026-04.md).
- **ADR-0003** ([docs/adr/0003-cross-region-inference-data-residency.md](../adr/0003-cross-region-inference-data-residency.md)) governs cross-region inference data residency; its status is **Proposed** at time of writing.

## Tested Inventory

| Tier | Role | modelId / ARN | Region | Direct vs Inference-Profile | Result | Latency ms |
|------|------|---------------|--------|-----------------------------|--------|-----------:|
| Primary | `agent_default.bedrock` | `eu.anthropic.claude-haiku-4-5-20251001-v1:0` | eu-central-1 | Inference-Profile | ✅ HTTP 200 | 4829 |
| Primary | `chat_default.bedrock` | `eu.anthropic.claude-sonnet-4-6` (bare, no `-v*:0`) | eu-central-1 | Inference-Profile | ✅ HTTP 200 | 3139 |
| Fallback | `agent_fallback.bedrock` | `eu.amazon.nova-micro-v1:0` | eu-central-1 | Inference-Profile | ✅ HTTP 200 | 1849 |

Raw capture: [smoke-tests.json](./bedrock-provider-smoke-2026-04/smoke-tests.json). All three calls returned `OK` (`max_tokens=16`), exercising both body envelopes (Anthropic messages-v1 for Claude; Bedrock Converse for Nova).

## Fallback Model Decision

**Chosen:** Amazon Nova Micro (`eu.amazon.nova-micro-v1:0`) for `agent_fallback.bedrock`.

- **EU-scoped.** `aws bedrock list-inference-profiles --region eu-central-1` returned both `eu.amazon.nova-micro-v1:0` and `eu.amazon.nova-lite-v1:0`. No `global.*` profile was needed — data residency stays inside the EU partition, consistent with ADR-0003's `eu.*` rationale.
- **Cheapest tier available.** Nova Micro is the cheapest Bedrock-hosted text model in the inventory (Nova Micro < Nova Lite < Nova Pro < Claude Haiku-3.5). On circuit-breaker trip, this fallback is meant to be a cost-bounded "best-effort" path, not quality-equivalent to Haiku 4.5 primary — same tier philosophy as `gpt-4o-mini` for the Anthropic-primary fallback.
- **Different provider family than primary.** Haiku 4.5 primary fails → Nova Micro fallback. A same-provider retry (Haiku 3.5) would not diversify failure modes; Nova routes through an entirely separate Bedrock request envelope (Converse API body shape) and model family (Amazon vs Anthropic).
- **Not Haiku 3.5.** `eu.anthropic.claude-haiku-3-5-20241022-v1:0` was available as a fallback candidate per AC #2, but it sits in the same tier/cost class as Haiku 4.5 primary — a degraded fallback that's still Anthropic-family. Nova Micro wins on diversification + cost.
- **Known gamble.** Nova Micro's smaller context window may be short for some Epic 3/8 categorization prompts under real load. Tracked as **TD-085** — revisit if the first real pre-prod circuit-breaker trip produces truncated outputs.

## Re-run instructions

Requires AWS creds with `bedrock:InvokeModel` on the three ARNs above (local dev pattern only — Story 9.7 owns the ECS task-role IAM). Redacted caller identity for this run: account `573562677570`.

```bash
# Haiku 4.5 primary
aws bedrock-runtime invoke-model \
  --profile personal --region eu-central-1 \
  --model-id "arn:aws:bedrock:eu-central-1:573562677570:inference-profile/eu.anthropic.claude-haiku-4-5-20251001-v1:0" \
  --body '{"anthropic_version":"bedrock-2023-05-31","max_tokens":16,"messages":[{"role":"user","content":"ping — reply with the word OK"}]}' \
  --cli-binary-format raw-in-base64-out /tmp/sp95b-haiku.json

# Sonnet 4.6 (bare ARN — no -v*:0 suffix)
aws bedrock-runtime invoke-model \
  --profile personal --region eu-central-1 \
  --model-id "arn:aws:bedrock:eu-central-1:573562677570:inference-profile/eu.anthropic.claude-sonnet-4-6" \
  --body '{"anthropic_version":"bedrock-2023-05-31","max_tokens":16,"messages":[{"role":"user","content":"ping"}]}' \
  --cli-binary-format raw-in-base64-out /tmp/sp95b-sonnet.json

# Nova Micro fallback — Bedrock Converse API (different envelope)
aws bedrock-runtime converse \
  --profile personal --region eu-central-1 \
  --model-id "arn:aws:bedrock:eu-central-1:573562677570:inference-profile/eu.amazon.nova-micro-v1:0" \
  --messages '[{"role":"user","content":[{"text":"ping"}]}]' \
  --inference-config '{"maxTokens":16}'
```

TD-084 (missing `-v*:0` on `chat_default.bedrock`) is **resolved — not-a-bug**: bare inference-profile ARNs are accepted by Bedrock's invoke-model endpoint.

## Status note

**This story ships the code path but does not flip any deployed environment — production activation remains blocked on ADR-0003 acceptance and Story 9.7 (ECS task-role IAM).** The default `LLM_PROVIDER=anthropic` is unchanged in [backend/.env.example](../../backend/.env.example) and all deployment configs. A future operator setting `LLM_PROVIDER=bedrock` in a non-prod environment gets a real client instead of the former `NotImplementedError`, but production runtime traffic stays direct-Anthropic until both gates clear.
