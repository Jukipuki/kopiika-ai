# AgentCore + Bedrock Region Availability — 2026-04

- **Story:** 9.4 (Epic 9 — AI Infra Readiness)
- **Date:** 2026-04-23
- **Primary region probed:** `eu-central-1`
- **Account:** AWS `573562677570` (caller: IAM user, redacted per AC #6)

## Context

Architecture ([architecture.md#Region Strategy](../../_bmad-output/planning-artifacts/architecture.md) lines 1602–1610) declares `eu-central-1` as the primary region with three pre-enumerated outcomes: (1) proceed on `eu-central-1`, (2) proceed with cross-region inference profile (DPO/Legal ADR required), (3) pivot to another AWS region. Epic 9's preamble ([epics.md](../../_bmad-output/planning-artifacts/epics.md)) pins Story 9.4 as the decision gate that unblocks Story 9.5b (add Bedrock provider path), Story 9.7 (Bedrock IAM + observability), and Story 10.4a (AgentCore session handler). This doc captures the invoke-tested ground truth so that `git log` — not a Slack thread — records *why* the pinned region + model IDs were chosen.

## Tested Inventory

| Tier | Candidate modelId / profile | Region | Direct or inference-profile | Result | Latency (ms) |
|---|---|---|---|---|---|
| Haiku-class | `eu.anthropic.claude-haiku-4-5-20251001-v1:0` (profile ARN: `arn:aws:bedrock:eu-central-1:573562677570:inference-profile/eu.anthropic.claude-haiku-4-5-20251001-v1:0`, routes to `eu-north-1`) | `eu-central-1` | inference-profile **required** | HTTP 200, body `"OK"` | 2719 |
| Sonnet-class | `eu.anthropic.claude-sonnet-4-6` (profile ARN: `arn:aws:bedrock:eu-central-1:573562677570:inference-profile/eu.anthropic.claude-sonnet-4-6`, routes to `eu-north-1`) | `eu-central-1` | inference-profile **required** | HTTP 200, body `"OK"` | 3002 |

All other active Claude models in `eu-central-1` (Opus 4.5/4.6/4.7, Sonnet 4.5) are also `INFERENCE_PROFILE`-only. `global.*` profile variants exist for all tiers but were rejected in favour of `eu.*` variants because the latter keep payloads inside the EU (route to `eu-north-1` / Stockholm). Full JSON capture: [`./agentcore-bedrock-region-availability-2026-04/invoke-tests.json`](./agentcore-bedrock-region-availability-2026-04/invoke-tests.json).

## AgentCore Availability

- `boto3.client("bedrock-agentcore-control", region_name="eu-central-1").list_agent_runtimes(maxResults=1)` → **HTTP 200**, body `{"agentRuntimes": []}`. Endpoint: `https://bedrock-agentcore-control.eu-central-1.amazonaws.com`.
- Secondary probe: `list_memories(maxResults=1)` → HTTP 200, body `{"memories": []}`.
- Data-plane service `bedrock-agentcore` endpoint (`https://bedrock-agentcore.eu-central-1.amazonaws.com`) resolves; data-plane operations are out of scope for this availability probe (they require an active agent runtime).
- No allowlist / preview-gating errors observed. No `EndpointConnectionError`. No `UnrecognizedClientException`.
- AWS CLI v2 binary does **not** yet expose the `bedrock-agentcore` subcommand (2026-04 state). The boto3 SDK (1.42.73) does. This CLI-SDK gap is the expected shape for newer services and is **not** a regional-absence signal — per this story's Dev Notes, the SDK call is ground truth. Tracked in `docs/tech-debt.md` as TD-081 for visibility.
- Public documentation cross-check: `https://docs.aws.amazon.com/general/latest/gr/bedrock.html` and the AgentCore regional availability page list `eu-central-1` among supported regions as of 2026-04-23.

## Outcome

**Outcome: proceed on eu-central-1 with cross-region inference profile for eu.anthropic.claude-haiku-4-5-20251001-v1:0, eu.anthropic.claude-sonnet-4-6**

## Rationale

- **Both required Claude tiers are available and invoke-tested** in `eu-central-1` — not a pivot scenario.
- **`ON_DEMAND` is unavailable for all active Claude models** in `eu-central-1` (AWS rollout pattern as of 2026-04). Inference profile is the only code path; this is the expected reality, not a regression.
- **`eu.*` profiles chosen over `global.*`** because the former physically route to `eu-north-1` (Stockholm — EU) while the latter can route anywhere including `us-*`. GDPR-weaker `global.*` profiles rejected.
- **AgentCore (`bedrock-agentcore-control`) is fully available** in `eu-central-1` with no allowlist requirement — unblocks Epic 10's session handler (Story 10.4a) without a region pivot.
- **Latencies (≈2.7s Haiku / ≈3.0s Sonnet) are acceptable** for batch agents (Celery) and within the range for interactive chat first-token-to-user budget in Epic 10.
- **Cross-region inference creates a data-residency exposure** (payload leaves `eu-central-1` during invoke) that architecture.md line 1610 flags as requiring DPO + Legal sign-off. ADR-0003 ([`docs/adr/0003-cross-region-inference-data-residency.md`](../adr/0003-cross-region-inference-data-residency.md)) is filed as **Proposed** to capture that review; Story 9.5b's cross-region wiring is blocked on it flipping to Accepted.
- **ECS / RDS stay in `eu-central-1`** — only outbound Bedrock invoke + AgentCore traffic touches the inference profile routing. Terraform footprint unchanged.

## Impact on downstream stories

- **Story 9.5b (Add Bedrock Provider Path):** Pin `ChatBedrock(model_id="…inference-profile/eu.anthropic.claude-haiku-4-5-20251001-v1:0")` for agent default/cheap and `…inference-profile/eu.anthropic.claude-sonnet-4-6` for chat default. Exact strings already in [`backend/app/agents/models.yaml`](../../backend/app/agents/models.yaml). Blocked on ADR-0003 acceptance before shipping.
- **Story 9.7 (Bedrock IAM + Observability):** ECS task role `bedrock:InvokeModel` scope must cover both the `eu-central-1` inference-profile ARNs *and* the underlying `eu-north-1` foundation-model ARNs that the profiles route to (AWS requires both in the policy statement for cross-region inference profiles). No multi-region VPC endpoints needed; the client remains in `eu-central-1`.
- **Story 10.4a (AgentCore Session Handler):** Target `bedrock-agentcore` / `bedrock-agentcore-control` in `eu-central-1` (endpoints listed above). No region pivot; scope-lock inherits the primary-region assumption.

## Re-run instructions

Run from repo root with `AWS_PROFILE` resolving to a user with minimum permissions `bedrock:InvokeModel`, `bedrock:ListFoundationModels`, `bedrock:ListInferenceProfiles`, `bedrock-agentcore:List*` / `bedrock-agentcore-control:List*`.

```bash
# Step 1 — caller identity (redacted: only account id retained)
aws sts get-caller-identity --profile=<profile>

# Step 2 — enumerate active Anthropic models in eu-central-1
aws bedrock list-foundation-models --profile=<profile> --region eu-central-1 \
  --by-provider Anthropic \
  --query 'modelSummaries[?modelLifecycle.status==`ACTIVE`].[modelId,inferenceTypesSupported]' \
  --output table

# Step 3 — enumerate Claude inference profiles (prefer eu.* over global.*)
aws bedrock list-inference-profiles --profile=<profile> --region eu-central-1 \
  # NB: filter uses 'laude' (lowercase c-laude) to match both 'Claude' and 'claude' without a case-insensitive flag.
  --query 'inferenceProfileSummaries[?contains(inferenceProfileName,`laude`)].[inferenceProfileId,inferenceProfileArn,models[0].modelArn]' \
  --output table

# Step 4 — invoke-test Haiku (adapt the ARN from Step 3)
cat > /tmp/body.json <<'EOF'
{"anthropic_version":"bedrock-2023-05-31","max_tokens":16,"messages":[{"role":"user","content":"ping — reply with the word OK"}]}
EOF
time aws bedrock-runtime invoke-model --profile=<profile> --region eu-central-1 \
  --model-id arn:aws:bedrock:eu-central-1:<acct>:inference-profile/eu.anthropic.claude-haiku-4-5-20251001-v1:0 \
  --body file:///tmp/body.json --cli-binary-format raw-in-base64-out \
  /tmp/haiku-response.json && cat /tmp/haiku-response.json

# Step 5 — invoke-test Sonnet (same shape, different ARN)
time aws bedrock-runtime invoke-model --profile=<profile> --region eu-central-1 \
  --model-id arn:aws:bedrock:eu-central-1:<acct>:inference-profile/eu.anthropic.claude-sonnet-4-6 \
  --body file:///tmp/body.json --cli-binary-format raw-in-base64-out \
  /tmp/sonnet-response.json && cat /tmp/sonnet-response.json

# Step 6 — AgentCore availability (boto3 — AWS CLI does not yet bind bedrock-agentcore)
uv run python -c "
import boto3, json
c = boto3.Session(profile_name='<profile>', region_name='eu-central-1').client('bedrock-agentcore-control')
r = c.list_agent_runtimes(maxResults=1)
print(r['ResponseMetadata']['HTTPStatusCode'], {k:v for k,v in r.items() if k!='ResponseMetadata'})
"
```

Baseline pass count at spike start: **861 passed, 11 deselected** (from `cd backend && uv run pytest tests/ -q`). Story 9.2 closeout reported `861 passed, 10 deselected` — one extra deselected test has been added on `main` between the two stories (unrelated to this spike). End-of-story count must match this 861/11 baseline.

> **Re-run cadence:** Re-validate this inventory before Epic 10 scope-lock if > 30 days have passed since this story's commit. Bedrock regional availability and inference-profile shapes change frequently; do not let this decision doc go stale unnoticed.
