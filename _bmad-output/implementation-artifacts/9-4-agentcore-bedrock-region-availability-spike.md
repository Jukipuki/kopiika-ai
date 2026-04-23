# Story 9.4: AgentCore + Bedrock Region Availability Spike (Decision Gate)

Status: done
Created: 2026-04-23
Epic: 9 — AI Infra Readiness (Bedrock Provider, RAG Eval Harness, Embedding Decision)

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **tech lead planning Epic 10 (Chat-with-Finances)**,
I want AWS Bedrock Claude-on-Bedrock model availability (haiku-class + sonnet-class, invoke-tested with a "ping" prompt) and the Bedrock AgentCore runtime availability **validated in `eu-central-1`** (with a documented fallback path — cross-region inference profile vs region pivot — chosen and signed off when the primary region fails), captured as a committed decision doc under `docs/decisions/` plus a pinned `backend/app/agents/models.yaml` (new file; consumed by Story 9.5a/9.5b) carrying the exact Bedrock model IDs/ARNs the project will use in prod,
so that Story 9.5b ("Add Bedrock Provider Path") and Epic 10's scope-lock (AgentCore session handler, Guardrails, chat UI) inherit a non-speculative region + model choice — and a future auditor (or future-you) can reconstruct *why* a given region + model was picked from `git log`, not from a lost Slack thread.

## Acceptance Criteria

1. **Given** the architecture's Region Strategy ([architecture.md#Region Strategy](../_bmad-output/planning-artifacts/architecture.md) lines 1602–1610) declares `eu-central-1` as primary with three outcomes (proceed / cross-region inference profile / region pivot) **When** this spike concludes **Then** a decision doc lands at `docs/decisions/agentcore-bedrock-region-availability-2026-04.md` (new file; create `docs/decisions/` directory if it does not already exist from Story 9.3's decision doc — no `index.md` required) whose final line is **exactly one of** three forms (no hedging, no fourth variant):
   - `**Outcome: proceed on eu-central-1**` — all required models + AgentCore are available and invoke-tested in `eu-central-1`
   - `**Outcome: proceed on eu-central-1 with cross-region inference profile for <model-id-list>**` — AgentCore is available in `eu-central-1` but one or more required Claude models must be invoked via an inference profile routing to another region; the named region is recorded and a data-residency ADR stub is linked per AC #7
   - `**Outcome: pivot to <region>**` — AgentCore is not available in `eu-central-1`; the spike selects an alternate AWS region (expected candidates: `us-east-1`, `eu-west-1`) with rationale covering latency, cost, and data-residency trade-offs, and flags the cross-epic infra impact (ECS/RDS do NOT pivot — only Bedrock + AgentCore calls route to the new region)

2. **Given** Epic 10 needs both a "fast/cheap" chat turn model and a "deeper reasoning" tier **When** the spike validates availability **Then** it invoke-tests **two model tiers** via `bedrock-runtime:InvokeModel` against the primary region (and fallback regions if applicable): a **Claude Haiku-class** model (current production default — the Anthropic direct path uses `claude-haiku-4-5-20251001` per [backend/app/agents/llm.py:19](../../backend/app/agents/llm.py#L19); find the current Bedrock-hosted Haiku 4.5 model ID — e.g. `anthropic.claude-haiku-4-5-20251001-v1:0` or the current region-inference variant, exact string confirmed at run time) and a **Claude Sonnet-class** model (current: `claude-sonnet-4-6` family; find the Bedrock-hosted equivalent ID). For each tier record: (a) exact `modelId` / inference-profile ARN that worked, (b) region invoked from, (c) timestamp of the test, (d) round-trip latency in ms for a fixed "ping — reply with the word OK" prompt, (e) whether a cross-region inference profile was required. Evidence is a small JSON capture committed at `docs/decisions/agentcore-bedrock-region-availability-2026-04/invoke-tests.json` (per-spike subdirectory — lets the image-heavy AWS console screenshots, if any, sit next to their citation without polluting `docs/decisions/` root)

3. **Given** AgentCore (the `bedrock-agentcore` service, formerly "Bedrock Agents") is required for Epic 10's session handler (Story 10.4a) and its regional availability is the primary Epic-10-blocking unknown **When** the spike validates AgentCore availability **Then** it confirms the `bedrock-agentcore` service endpoint is reachable in the chosen region by at minimum performing a read-only API call (`list-agents` or the current equivalent CLI / SDK call that does NOT require a pre-created agent) and capturing the response status + first kilobyte of response body into `invoke-tests.json`. If the service is in limited preview / requires allowlisting in the chosen region, that is documented in the decision doc with the AWS account team contact path — and that constitutes a "not available" outcome for AC #1 pivot-rule purposes unless allowlist approval is obtained before this story closes

4. **Given** Story 9.5b pins exact Bedrock model identifiers into `backend/app/agents/models.yaml` (per [architecture.md line 1592](../_bmad-output/planning-artifacts/architecture.md#L1592): "Exact Bedrock model ARNs for `eu-central-1` are confirmed by Story 9.4 before Story 9.5b pins them") **When** this spike completes **Then** `backend/app/agents/models.yaml` is created (new file) with the minimum schema Story 9.5a will consume — a YAML map of logical role → provider-qualified model ID — populated with the **Bedrock-qualified** entries for the roles Epic 10 needs at scope-lock time:
   - `agent_default:` → Haiku-class Bedrock model ID / inference-profile ARN from AC #2
   - `agent_cheap:` → same Haiku ID (kept as a separate key so 9.5a/9.5b can swap one without re-touching call sites)
   - `chat_default:` → Sonnet-class Bedrock model ID / inference-profile ARN from AC #2

   The file's top-of-file comment block MUST state: `# Bedrock model IDs pinned by Story 9.4 on <date> against region <region>. # Do not edit without re-running the 9.4 invoke-tests harness (see docs/decisions/agentcore-bedrock-region-availability-2026-04.md).` Non-Bedrock providers (`anthropic:`, `openai:` sub-maps) are NOT populated here — that is Story 9.5a's refactor job; this story only pins the Bedrock column. The file is valid YAML parseable by `yaml.safe_load` and includes a top-level `# yamllint disable rule:line-length` directive only if an ARN genuinely exceeds 120 chars

5. **Given** the architecture's "Data-residency review for cross-region inference" policy ([architecture.md line 1610](../_bmad-output/planning-artifacts/architecture.md#L1610)) requires an ADR signed off by DPO + Legal before cross-region inference traffic ships **When** AC #1's second outcome ("proceed on eu-central-1 with cross-region inference profile") is the chosen outcome **Then** this story produces an ADR stub at `docs/adr/0003-cross-region-inference-data-residency.md` (ADR-0003 — ADR-0001 and ADR-0002 already exist per memory `reference_tech_debt.md` and [docs/adr/](../../docs/adr/) listing) capturing: (1) which model(s) require cross-region inference, (2) the target region, (3) the three review criteria from architecture.md line 1610 as unchecked boxes with a placeholder owner (`DPO + Legal — TBD`), and (4) a "Status: proposed" header. The ADR is **not** merged-as-accepted by this story — it is merged as "proposed" and the cross-region inference path is NOT wired up in Story 9.5b until the ADR flips to "accepted" by the DPO/Legal owners. If AC #1's outcome is "proceed on eu-central-1" (no cross-region inference) OR "pivot to <region>" (single-region deployment), no ADR stub is created — skip AC #5

6. **Given** IAM permissions for the invoke tests are not yet provisioned (Story 9.7 does that for ECS task roles) **When** the developer runs the spike **Then** they use **local AWS credentials** (developer's `AWS_PROFILE` or `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`) with the minimum permissions `bedrock:InvokeModel`, `bedrock:ListFoundationModels`, `bedrock:GetFoundationModel`, and `bedrock-agentcore:List*` / `bedrock-agentcore:Get*` scoped to the invoked models/regions. No Terraform changes, no ECS task-role edits, no Secrets Manager plumbing — this is a **local spike with local credentials** mirroring Story 9.3's pattern ([9-3-embedding-model-comparison-spike.md AC #5](./9-3-embedding-model-comparison-spike.md)). The decision doc records which user/role identity ran the tests (via `aws sts get-caller-identity` output, redacted to account-id only — **no full ARNs with user names committed** per standard least-exposure practice) so a later re-run knows what privilege level it needs

7. **Given** the outcome must be actionable for three downstream stories (9.5b, 9.7, 10.4a) **When** the decision doc is written **Then** it contains — in this order — these sections:
   - **Context** (≤ 10 lines): why this gate exists, pointer to [architecture.md Region Strategy](../_bmad-output/planning-artifacts/architecture.md) + Epic 9 preamble in [epics.md](../_bmad-output/planning-artifacts/epics.md)
   - **Tested Inventory**: table of (model tier, candidate model ID, region attempted, result: ok / unavailable / requires-inference-profile / not-allowlisted, latency ms) — one row per invoke test
   - **AgentCore Availability**: result of the AC #3 read-only call, plus the current public documentation pointer (AWS doc URL) used to confirm regional availability
   - **Outcome**: the exact line from AC #1 (one of three forms)
   - **Rationale**: 3–7 bullets
   - **Impact on downstream stories**: one bullet each for 9.5b (which ARNs to pin), 9.7 (which regions / services the IAM scope must cover), 10.4a (AgentCore endpoint + region for the session handler)
   - **Re-run instructions**: the exact CLI / script invocation used, so a later reviewer can reproduce the inventory. Re-run cadence recommendation: re-validate before Epic 10 scope-lock (if > 30 days have passed since this story's commit) because Bedrock regional availability changes frequently and the decision doc must not go stale unnoticed

8. **Given** downstream work gates on this decision **When** the spike finishes **Then** `_bmad-output/implementation-artifacts/sprint-status.yaml` is updated:
   - `9-4-agentcore-bedrock-region-availability-spike:` flipped from `backlog` to `review` (the implementing dev's normal close-out path; code-review will flip it to `done`)
   - A one-line comment immediately above the Story 9.5b entry (`9-5b-add-bedrock-provider-path:`) naming the chosen region + Haiku ID + Sonnet ID, so the 9.5b story author doesn't have to re-derive them
   - If AC #1's outcome is "pivot to <region>": a one-line comment immediately above the Epic 10 block summarizing the region pivot impact (for the next SP run to absorb)
   - If AC #5's ADR stub was created: a one-line comment pointing 9.5b at `docs/adr/0003-cross-region-inference-data-residency.md` noting that 9.5b's cross-region path is **blocked** on that ADR flipping to "accepted"

9. **Given** this is a measurement-only spike with no production-code change **When** the default test sweep runs (`cd backend && uv run pytest tests/ -q`) **Then** it remains green with the same pass/deselect counts as the most recent green baseline (Story 9.2 closeout: `861 passed, 10 deselected`; confirm the current count at spike start and match it at spike end — if `main` has drifted between this story's start and end, note the new baseline in the decision doc's "Re-run instructions" section and do not absorb drift into the story claim). The `backend/app/agents/models.yaml` file added per AC #4 is YAML only — no Python import of it happens in this story (9.5a adds the loader) — so it has no test impact

10. **Given** `docs/tech-debt.md` tracks deferred work with `TD-NNN` IDs (per memory `reference_tech_debt.md`; highest current ID is TD-068 per [docs/tech-debt.md](../../docs/tech-debt.md)) **When** the spike surfaces any shortcut or deferred item (expected candidates: (a) a model-ID lookup script worth productizing as part of 9.5c's CI job, (b) a cross-region inference profile config worth Terraforming in Story 9.7, (c) a region-availability monitor worth adding as a nightly alarm for future Bedrock regional churn) **Then** each such item gets a `TD-069+` entry in `docs/tech-debt.md` with a one-line pointer back to this story's decision doc. If no shortcuts are taken, no TD entry is added — the register is not padded

## Tasks / Subtasks

- [x] Task 1: Confirm prerequisites and capture baseline state (AC: #6, #9)
  - [x] 1.1 Verify local AWS credentials resolve via `aws sts get-caller-identity` and that the caller has at least `bedrock:ListFoundationModels` in `eu-central-1`: `aws bedrock list-foundation-models --region eu-central-1 --query 'modelSummaries[?providerName==`Anthropic`].[modelId,modelLifecycle.status]' --output table`. Save the redacted caller identity (account ID only) into the decision doc scratch area — NOT to git — for AC #7's "who ran it" note.
  - [x] 1.2 From `backend/`, run `uv run pytest tests/ -q` and record the baseline pass/deselect counts. If they differ from Story 9.2's `861 passed, 10 deselected`, record the current numbers as this story's new baseline. (Do not investigate drift — orthogonal to this spike; if drift is large, escalate and pause.)
  - [x] 1.3 Confirm `docs/decisions/` directory exists (Story 9.3 should have created it when it lands; if not yet merged, create it as part of this story — no `index.md` required; the directory is self-describing). Confirm `docs/adr/` exists and inspect the highest existing ADR number (currently `0002-ai-assisted-schema-detection.md` per [docs/adr/](../../docs/adr/) listing); reserve `0003` for the potential AC #5 ADR — do NOT create the file yet.

- [x] Task 2: Inventory Bedrock Claude models in `eu-central-1` (AC: #2, #3)
  - [x] 2.1 Enumerate Anthropic-provider models available in `eu-central-1`:
    ```
    aws bedrock list-foundation-models --region eu-central-1 \
      --by-provider Anthropic \
      --query 'modelSummaries[].[modelId,modelLifecycle.status,inferenceTypesSupported]' \
      --output table
    ```
    Record the full result in `docs/decisions/agentcore-bedrock-region-availability-2026-04/invoke-tests.json` under key `eu_central_1_anthropic_inventory`.
  - [x] 2.2 From the inventory, identify candidates for:
    - **Haiku-class**: prefer a current Haiku-4.5 ID (matches `backend/app/agents/llm.py:19` — `claude-haiku-4-5-20251001`); fall back to `claude-haiku-3.5-<v>` Bedrock variant if 4.5 is absent in `eu-central-1`, and record the version gap in the decision doc.
    - **Sonnet-class**: prefer a current Sonnet-4.6 ID; fall back to `claude-sonnet-4-<v>` or `3.5-sonnet` if 4.6 is absent, same rules.
  - [x] 2.3 For each candidate, determine whether it's directly invocable (`ON_DEMAND` inference type) OR requires an **inference profile** (common for newer Claude models in `eu-central-1` — `INFERENCE_PROFILE` in `inferenceTypesSupported`, with cross-region inference typically routing through `us-east-1`). For inference-profile candidates, enumerate available profiles:
    ```
    aws bedrock list-inference-profiles --region eu-central-1 \
      --query 'inferenceProfileSummaries[?contains(inferenceProfileName,`claude`)].[inferenceProfileId,inferenceProfileArn,models[0].modelArn]' \
      --output table
    ```
    Record in `invoke-tests.json` under `eu_central_1_inference_profiles`.

- [x] Task 3: Invoke-test Haiku tier (AC: #2, #6)
  - [x] 3.1 Invoke the chosen Haiku candidate with the fixed prompt `"ping — reply with the word OK"`:
    ```
    aws bedrock-runtime invoke-model \
      --region eu-central-1 \
      --model-id <haiku-id-or-inference-profile-arn> \
      --body '{"anthropic_version":"bedrock-2023-05-31","max_tokens":16,"messages":[{"role":"user","content":"ping — reply with the word OK"}]}' \
      --cli-binary-format raw-in-base64-out \
      /tmp/haiku-response.json
    ```
    Capture the response body, HTTP status, and round-trip latency (use `time` on the invocation — record `real` in ms). Store into `invoke-tests.json` under `haiku_invoke_test`.
  - [x] 3.2 If the direct call returns `ValidationException: Invocation of model ID <x> with on-demand throughput isn't supported`, re-run via the inference profile ARN identified in Task 2.3 and record that the profile was required (`inference_profile_required: true`) — this is the trigger for AC #1's second outcome form and AC #5's ADR.
  - [x] 3.3 If the call fails with `AccessDeniedException: You don't have access to the model with the specified model ID`, model access must be enabled in the Bedrock console (Model access tab). Enable it for `anthropic.claude-haiku-*` in `eu-central-1` and retry. Record the enablement step in the decision doc's "Re-run instructions" (future re-runs in a fresh AWS account hit the same wall).

- [x] Task 4: Invoke-test Sonnet tier (AC: #2, #6)
  - [x] 4.1 Repeat Task 3.1 for the Sonnet candidate. Same prompt, same body shape, same latency + status capture into `invoke-tests.json` under `sonnet_invoke_test`. Sonnet is statistically more likely than Haiku to be inference-profile-only in `eu-central-1` at 2026-04 — do not be surprised if Task 3 passes direct and Task 4 requires an inference profile; document each per tier.
  - [x] 4.2 If *neither* tier is directly invocable without an inference profile, that is still a valid "proceed with inference profile" outcome — both model IDs in `models.yaml` will be inference-profile ARNs. This is the most likely 2026-04 reality; note it without alarm.
  - [x] 4.3 If a tier is *completely* unavailable (neither direct nor via inference profile), that pushes AC #1 toward a "pivot to <region>" outcome OR a manual AWS support request — record which and pause for PO/tech-lead decision rather than forcing a region pivot unilaterally.

- [x] Task 5: Verify AgentCore availability in `eu-central-1` (AC: #3)
  - [x] 5.1 Confirm the `bedrock-agentcore` service namespace is reachable in `eu-central-1` via a read-only call:
    ```
    aws bedrock-agentcore list-agents --region eu-central-1 --max-results 1 2>&1 | tee /tmp/agentcore-list.txt
    ```
    (If the CLI binary does not expose `bedrock-agentcore` yet — AgentCore's CLI bindings trail the SDK by weeks at times — use the Python SDK equivalent: `boto3.client("bedrock-agentcore", region_name="eu-central-1").list_agents(maxResults=1)`.)
  - [x] 5.2 Capture the response status and first kilobyte of the response body into `invoke-tests.json` under `agentcore_availability`. Expected shapes:
    - Success (empty list, no agents yet): service is reachable → AgentCore is available in the region.
    - `EndpointConnectionError` / `Could not connect to the endpoint URL`: service is NOT in `eu-central-1` → this triggers AC #1's third outcome (pivot).
    - `AccessDeniedException` with `bedrock-agentcore:ListAgents` message: service IS in the region but IAM isn't scoped — add the permission to the local credential and retry (this is not a pivot trigger).
    - `UnrecognizedClientException` / similar preview-gating error: allowlist needed → document the AWS account-team contact path and treat as "not available" per AC #3 unless allowlist is obtained before story close.
  - [x] 5.3 Cross-check against current AWS documentation: open the AWS regional-services table (https://docs.aws.amazon.com/general/latest/gr/bedrock.html and the AgentCore-specific regions page) and record the documentation state as of the test date into the decision doc's "AgentCore Availability" section. This guards against transient API errors being mistaken for regional absence.

- [x] Task 6: Decide outcome per AC #1 decision tree (AC: #1, #5)
  - [x] 6.1 Apply the outcome rule:
    - **All** invoke tests passed (Tasks 3 + 4 + 5) **and** none required an inference profile → `**Outcome: proceed on eu-central-1**`.
    - Tasks 3 + 4 passed **but** one or both required an inference profile, Task 5 passed → `**Outcome: proceed on eu-central-1 with cross-region inference profile for <model-id-list>**`. AC #5's ADR stub applies.
    - Task 5 failed (AgentCore unavailable or not allowlisted within this story's window) → `**Outcome: pivot to <region>**`. Candidate regions: `us-east-1` (highest Bedrock + AgentCore coverage, weakest GDPR posture), `eu-west-1` (possible AgentCore in 2026; stronger GDPR posture than us-east-1). Select by rerunning Tasks 2–5 abbreviated (list + one invoke per tier + AgentCore list-agents) in the candidate region; commit only the winning region's inventory into `invoke-tests.json` under a top-level `fallback_region_<name>` key.
  - [x] 6.2 If the outcome is "proceed on eu-central-1 with cross-region inference profile", create `docs/adr/0003-cross-region-inference-data-residency.md` per AC #5:
    - Status: `proposed`
    - Body (≤ 40 lines): which model(s), target region, the three criteria from [architecture.md line 1610](../_bmad-output/planning-artifacts/architecture.md#L1610) as unchecked checkboxes, owner `DPO + Legal — TBD`, pointer back to this story's decision doc and to `_bmad-output/implementation-artifacts/sprint-status.yaml` Story 9.5b dependency.
    - Do NOT mark it `accepted` — Story 9.5b's cross-region path is blocked on the human sign-off flipping it.
  - [x] 6.3 If the outcome is "pivot to <region>", add a one-line note to the decision doc's "Rationale" section addressing each of: latency impact on batch agents (Celery → Bedrock call round-trip), cost delta vs `eu-central-1`, data-residency posture (noting that ECS/RDS stay in `eu-central-1` — only the outbound Bedrock + AgentCore traffic crosses), and whether an ADR is needed (probably yes, but lighter scope than AC #5's — one-paragraph note rather than a full ADR stub unless the PO/tech-lead asks otherwise).

- [x] Task 7: Pin the decision into `backend/app/agents/models.yaml` (AC: #4)
  - [x] 7.1 Create `backend/app/agents/models.yaml` with this structure (example assuming "proceed with inference profile for both tiers" outcome — adapt to the actual outcome from Task 6):
    ```yaml
    # Bedrock model IDs pinned by Story 9.4 on 2026-04-23 against region eu-central-1.
    # Do not edit without re-running the 9.4 invoke-tests harness
    # (see docs/decisions/agentcore-bedrock-region-availability-2026-04.md).
    #
    # Story 9.5a's provider-routing refactor consumes this file (logical role -> provider-qualified ID).
    # Story 9.5b fills in the `anthropic:` and `openai:` sub-maps; this story only pins `bedrock:`.
    bedrock:
      agent_default: "<haiku-id-or-inference-profile-arn-from-AC-#2>"
      agent_cheap:   "<same-haiku-id>"
      chat_default:  "<sonnet-id-or-inference-profile-arn-from-AC-#2>"
    ```
  - [x] 7.2 Validate the file parses via `python -c "import yaml; print(yaml.safe_load(open('backend/app/agents/models.yaml')))"` from the repo root (with the backend venv active — per memory `feedback_python_venv.md`, `backend/.venv`). Output must be a nested dict without errors.
  - [x] 7.3 Do NOT wire any Python code to read this file — that is Story 9.5a's refactor job. This story's contribution is the file itself, pinned and committed.

- [x] Task 8: Write the decision doc (AC: #1, #7)
  - [x] 8.1 Create `docs/decisions/agentcore-bedrock-region-availability-2026-04.md` with the exact section order from AC #7 (Context → Tested Inventory → AgentCore Availability → Outcome → Rationale → Impact on downstream stories → Re-run instructions).
  - [x] 8.2 In "Tested Inventory", build a markdown table with columns: `tier | candidate modelId | region | direct or inference-profile | result | latency (ms)`. Two rows (haiku, sonnet) for the primary region; additional rows only if Task 6.1's fallback-region sub-run was needed.
  - [x] 8.3 In "Impact on downstream stories", write exactly three bullets: one pointing Story 9.5b at the pinned IDs in `backend/app/agents/models.yaml`, one pointing Story 9.7 at the IAM scopes that need to cover the chosen region (including the inference-profile ARN region if cross-region), one pointing Story 10.4a at the AgentCore endpoint region for the session handler.
  - [x] 8.4 In "Re-run instructions", paste the Task 1.1, 2.1, 3.1, 4.1, 5.1 commands verbatim with placeholders for any secrets / profile names. Include the re-run cadence recommendation from AC #7 ("re-validate before Epic 10 scope-lock if > 30 days have passed") as a boxed note at the end.

- [x] Task 9: Update downstream tracking (AC: #8, #10)
  - [x] 9.1 Edit `_bmad-output/implementation-artifacts/sprint-status.yaml`:
    - Set `9-4-agentcore-bedrock-region-availability-spike:` to `review`.
    - Add a one-line comment (not YAML data — a `#` comment) immediately above the `9-5b-add-bedrock-provider-path:` line summarizing `# Story 9.4 (<date>): region=<region>, haiku=<id>, sonnet=<id>; see docs/decisions/agentcore-bedrock-region-availability-2026-04.md`.
    - If AC #1's outcome is "pivot": add a one-line `# Story 9.4 region pivot to <region> — Epic 10 scope-lock impact TBD in next SP run` comment above the `# Epic 10:` block header.
    - If AC #5's ADR was created: add a one-line `# Story 9.5b cross-region path blocked on ADR-0003 acceptance` comment above `9-5b-add-bedrock-provider-path:` (in addition to the summary comment).
  - [x] 9.2 If any shortcut was taken during the spike (e.g., hardcoding a preview modelId, skipping an inference-profile permutation, parking a CLI-SDK mismatch for later), append a `TD-069`+ entry to `docs/tech-debt.md` per register conventions — severity `LOW` unless the shortcut materially affects Epic 10's go/no-go, in which case `MEDIUM`. Each entry ends with a pointer back to this story file and the decision doc.
  - [x] 9.3 If no shortcuts were taken, do not add any TD entry. The register is not a changelog.

- [x] Task 10: No-regression verification (AC: #9)
  - [x] 10.1 From `backend/`, run `uv run pytest tests/ -q`. Confirm the pass/deselect counts match Task 1.2's captured baseline. The only files this story adds to the backend tree are `backend/app/agents/models.yaml` (data, not code) — so a regression here would be unrelated to this story. If it appears, escalate.
  - [x] 10.2 Optional: run `uv run ruff check backend/` — this story introduces no Python, so any ruff diff is pre-existing drift (TD-068) and not owned here.
  - [x] 10.3 Commit the full set — decision doc + `invoke-tests.json` capture + `models.yaml` + (optionally) ADR-0003 + `sprint-status.yaml` edit + (optionally) `tech-debt.md` entry — in a single PR titled `Story 9.4: AgentCore + Bedrock region availability spike`.

## Dev Notes

### Scope discipline

This is a **decision-gate spike**, not implementation. The only code-adjacent artifact is `backend/app/agents/models.yaml` (YAML data, not Python). OFF-LIMITS for this story:

- `backend/app/agents/llm.py` — Story 9.5a refactors it; this spike does NOT touch the factory.
- Any Terraform change (ECS task-role IAM, VPC endpoints, Secrets Manager) — Story 9.7 owns that; this spike uses local developer credentials only.
- Any change to `backend/tests/` — no tests are added here; the regression gate (AC #9) is just "default sweep stays green".
- Any ECS, RDS, or region-level infra change — even if AC #1's outcome is "pivot to `<region>`", only Bedrock + AgentCore calls route to the new region; ECS/RDS remain in `eu-central-1` per architecture Phase 1 footprint.

If a task tempts you to wire code paths ("I could just add the ChatBedrock factory call real quick") — stop. That's Story 9.5b's scope. This story's commit diff should be ≤ ~150 lines added (decision doc is the bulk; `models.yaml` is ~15 lines; sprint-status comment is 2–3 lines; optional ADR is ~40 lines).

### Why a YAML file and not a Python constant

`backend/app/agents/models.yaml` is introduced here rather than inside `llm.py` because:

1. It's data that changes independently of code (Bedrock churn — new model versions arrive quarterly, inference-profile ARNs can change when AWS reshapes regional coverage).
2. Story 9.5a's refactor is already scoped to build the loader; this spike should not pre-empt that design by baking the constants into Python.
3. A YAML file is reviewable by someone without Python context (e.g., a security reviewer checking which model ARNs the task role is scoped to).

The file is minimal — Bedrock-column only — because Story 9.5a will expand it with `anthropic:` and `openai:` sub-maps. Over-engineering the schema here (adding validation, types, fallback chains) would collide with 9.5a's design and waste work. Keep it a three-entry map under `bedrock:` and move on.

### Handling the "direct vs inference profile" ambiguity

As of 2026-04, newer Claude models in `eu-central-1` are frequently only accessible through cross-region inference profiles rather than direct on-demand invocation. This is not a bug; it's AWS's rollout pattern for high-demand regions. Signals:

- `inferenceTypesSupported` includes `INFERENCE_PROFILE` but not `ON_DEMAND` → profile required.
- `InvokeModel` with a direct modelId returns `ValidationException: ... on-demand throughput isn't supported` → profile required.
- `list-inference-profiles` returns profiles whose `models[0].modelArn` points to `us-east-1` or another region while the profile itself is `eu-central-1` → that's a cross-region inference profile; treat it as AC #1's second outcome and write the ADR-0003 stub.

Being required to use an inference profile is NOT a "pivot" trigger. It IS an ADR trigger, because the inference traffic crosses region boundaries (the payload physically leaves `eu-central-1`) even though the IAM + service boundary stays in `eu-central-1`. DPO/Legal need to see the data-residency implications before this path ships.

### What "AgentCore availability" actually means

AgentCore in 2026-04 is still a relatively new service. Regional availability changes via AWS release notes and is not always reflected in the AWS CLI binary at the same time as the SDK. Signals:

- `boto3.client("bedrock-agentcore", region_name="eu-central-1").list_agents(maxResults=1)` returns successfully (empty or non-empty list) → service is in the region.
- The same call raises `EndpointConnectionError` → service is NOT in the region; this is the authoritative signal.
- The call raises `AccessDeniedException` specifically naming `bedrock-agentcore:ListAgents` → service IS in the region but local creds need the permission; not a pivot trigger.
- The call raises `UnrecognizedClientException` or a preview-gating error → allowlist required; treat as "not available" for AC #3 unless the allowlist comes through before story close.

Do not rely solely on the AWS public regional-services table — it sometimes lags by weeks. The SDK-level call is ground truth. The table is cross-checked in Task 5.3 as a secondary confirmation only.

### Region pivot is a heavy outcome — bias against it

If Task 5 fails (AgentCore unavailable), the default reaction should be:

1. Retry with explicit allowlist request to AWS account team (1–2 business day turnaround in practice).
2. If allowlisted → outcome is "proceed on eu-central-1" (possibly with inference profile per AC #1).
3. Only if allowlisting is refused or timelines are incompatible with Epic 10 scope-lock deadline → genuine region pivot.

A region pivot has cross-epic blast radius (Epic 10 scope-lock shifts; Story 9.7 IAM changes; batch-agent latency characteristics change; GDPR posture changes). It is correct sometimes, but "pivot" should not be the first reflex after a single failed invoke. The spike's job is to *test* thoroughly; the PO + tech lead own the pivot *decision* if thorough testing confirms unavailability.

### IAM and credential handling

The spike runs with *local developer credentials*. Minimum permissions:

- `bedrock:ListFoundationModels` (list inventory)
- `bedrock:GetFoundationModel` (drill into a specific model's detail if needed)
- `bedrock:InvokeModel` on the two tested model ARNs (wildcard acceptable for the spike; Story 9.7 locks this down for the ECS task role)
- `bedrock:ListInferenceProfiles` (discover cross-region inference profiles)
- `bedrock-agentcore:ListAgents`, `bedrock-agentcore:ListAgentRuntimes` (AgentCore read-only probe)

Do NOT commit these to `iam-policies/` or Terraform — those belong to Story 9.7. A Gist or scratch file is fine; the decision doc just records *which* permissions were needed, not the JSON policy body. The redacted `aws sts get-caller-identity` output goes into the decision doc's "Re-run instructions" section so a successor knows the privilege envelope without seeing the specific developer account.

### Integration points

- Architecture sections consumed: [Region Strategy](../_bmad-output/planning-artifacts/architecture.md) (lines 1602–1610), [AgentCore Deployment Model](../_bmad-output/planning-artifacts/architecture.md) (lines 1612–1619), [IAM & Infrastructure](../_bmad-output/planning-artifacts/architecture.md) (lines 1621–1635).
- Current Anthropic-direct LLM client (shows the Haiku version target for the Bedrock-hosted equivalent): [backend/app/agents/llm.py:18-21](../../backend/app/agents/llm.py#L18-L21).
- Sibling Story 9.3 pattern (a spike of the same shape: inventory → invoke-test → decision doc → sprint-status update): [9-3-embedding-model-comparison-spike.md](./9-3-embedding-model-comparison-spike.md).
- Epic 9 Story list for downstream dependencies (9.5b, 9.7, 10.4a consume this story's output): [epics.md lines 2041–2078](../_bmad-output/planning-artifacts/epics.md).
- Tech-debt register (highest existing TD id + register conventions): [docs/tech-debt.md](../../docs/tech-debt.md).
- ADR directory (ADR-0001 + 0002 exist; reserve 0003 for the conditional AC #5 stub): [docs/adr/](../../docs/adr/).

### Memory / policy references

- `project_agentcore_decision.md` — Epic 3 batch agents do NOT use AgentCore. This story validates AgentCore only for Epic 10's *chat* agent. The validation here has zero impact on existing batch agents; it is forward-looking infrastructure due diligence.
- `project_bedrock_migration.md` — Bedrock LLM migration is still deferred in production runtime. This story pins IDs into `models.yaml` but does NOT switch any code path to Bedrock. Story 9.5b does the actual wiring.
- `reference_tech_debt.md` — TD-069+ for any shortcut taken. Highest existing TD is TD-068 per current register state.
- `feedback_python_venv.md` — all Python commands from `backend/` with `backend/.venv` active.
- `project_observability_substrate.md` — no CloudWatch emission from the spike; numbers live in the decision doc + `invoke-tests.json`.

### Project Structure Notes

- New file: `docs/decisions/agentcore-bedrock-region-availability-2026-04.md` (Story 9.3 also creates `docs/decisions/` — if Story 9.3's PR lands first, the directory already exists; otherwise create it).
- New file: `docs/decisions/agentcore-bedrock-region-availability-2026-04/invoke-tests.json` (per-spike subdirectory for the raw capture).
- New file: `backend/app/agents/models.yaml` (minimum schema; Story 9.5a expands it).
- Conditional new file: `docs/adr/0003-cross-region-inference-data-residency.md` (only if AC #1's outcome is "proceed with cross-region inference profile").
- Modified: `_bmad-output/implementation-artifacts/sprint-status.yaml` (status flip + 1–2 pointer comments per AC #8).
- Conditional modified: `docs/tech-debt.md` (only if a shortcut was taken per AC #10).

No Python imports, no test changes, no Terraform, no CI workflow changes, no frontend changes.

### Testing Standards

- No new tests. Regression gate is `uv run pytest tests/ -q` from `backend/`, matching the Story 9.2 closeout baseline (861 passed, 10 deselected) or the current green-on-main baseline if it has drifted.
- Ruff: no Python introduced, so no ruff concern.
- The only "test" performed is the invoke-test harness (Tasks 3–5) whose capture is committed as JSON evidence alongside the decision doc.

### References

- Epic 9 overview: [epics.md#Epic 9](../_bmad-output/planning-artifacts/epics.md) lines 2021–2078
- Epic 10 dependency statement: [epics.md lines 2086–2087](../_bmad-output/planning-artifacts/epics.md)
- Architecture — Region Strategy: [architecture.md#Region Strategy](../_bmad-output/planning-artifacts/architecture.md) lines 1602–1610
- Architecture — AgentCore Deployment Model: [architecture.md#AgentCore Deployment Model](../_bmad-output/planning-artifacts/architecture.md) lines 1612–1619
- Architecture — IAM & Infrastructure: [architecture.md#IAM & Infrastructure](../_bmad-output/planning-artifacts/architecture.md) lines 1621–1635
- Sibling spike template: [9-3-embedding-model-comparison-spike.md](./9-3-embedding-model-comparison-spike.md)
- Current Anthropic-direct LLM client (Haiku version target): [backend/app/agents/llm.py](../../backend/app/agents/llm.py)
- Tech-debt register: [docs/tech-debt.md](../../docs/tech-debt.md)
- ADR directory: [docs/adr/](../../docs/adr/)

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (1M context)

### Debug Log References

- `/tmp/sp94/haiku-response.json`, `/tmp/sp94/sonnet-response.json` — raw invoke-model response bodies (ephemeral; captured into `docs/decisions/agentcore-bedrock-region-availability-2026-04/invoke-tests.json` for the committed record).
- `/tmp/sp94/agentcore-boto3-2.txt` — boto3 AgentCore probe stdout (`list_agent_runtimes` HTTP 200, `list_memories` HTTP 200).

### Completion Notes List

- **Outcome:** `proceed on eu-central-1 with cross-region inference profile for eu.anthropic.claude-haiku-4-5-20251001-v1:0, eu.anthropic.claude-sonnet-4-6`. Both EU profiles physically route `eu-central-1` → `eu-north-1` (in-EU hop, softer GDPR posture than `global.*`). ADR-0003 filed as **Proposed** per AC #5; Story 9.5b's cross-region path is blocked on DPO + Legal sign-off.
- **AgentCore:** fully available in `eu-central-1`. `bedrock-agentcore-control.list_agent_runtimes(maxResults=1)` → HTTP 200 with empty list; `list_memories` → HTTP 200; data-plane endpoint resolves. No allowlist / preview-gating.
- **CLI-SDK mismatch:** `aws bedrock-agentcore …` is not yet a CLI subcommand (2026-04 awscli 2.x); boto3 1.42.73 binds it correctly. Registered as **TD-081 [LOW]** with a pointer to the decision doc so a future re-run operator is not misled into a false "unavailable" read.
- **Latencies:** Haiku 2719 ms, Sonnet 3002 ms (single invoke each, `max_tokens=16`, "ping — reply with the word OK"). Acceptable for Celery batch; within chat-turn budget for Epic 10 first-token-to-user.
- **Regression:** `cd backend && uv run pytest tests/ -q` → **861 passed, 11 deselected** — matches Task 1.2 baseline exactly. Story 9.2 closeout reported 861/10; +1 deselected arrived on `main` with Story 9.3 (new eval-gated test), noted in the decision doc's Re-run instructions.
- **Version:** bumped 1.33.0 → 1.34.0 (MINOR) following the same convention as sibling spike Story 9.3. Spike output is not directly user-facing but matches the project's "any story = MINOR" default.
- **Scope discipline:** no `backend/app/agents/llm.py` edits, no Terraform, no test changes. `backend/app/agents/models.yaml` (new, data-only) is the sole backend-tree contribution — Story 9.5a will add the Python loader.

### File List

- `docs/decisions/agentcore-bedrock-region-availability-2026-04.md` (new) — decision doc per AC #1, #7.
- `docs/decisions/agentcore-bedrock-region-availability-2026-04/invoke-tests.json` (new) — raw evidence capture per AC #2, #3.
- `docs/adr/0003-cross-region-inference-data-residency.md` (new) — ADR stub `Status: Proposed` per AC #5.
- `backend/app/agents/models.yaml` (new) — Bedrock-column pin per AC #4; parses via `yaml.safe_load`.
- `docs/tech-debt.md` (modified) — added **TD-081** for the awscli bedrock-agentcore binding gap per AC #10.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (modified) — Story 9.4 flipped `ready-for-dev` → `review`; two pointer comments added above `9-5b-add-bedrock-provider-path:` (pinned IDs + ADR-0003 block note) per AC #8.
- `_bmad-output/implementation-artifacts/9-4-agentcore-bedrock-region-availability-spike.md` (modified) — status, checkboxes, Dev Agent Record, File List, Change Log.
- `VERSION` (modified) — `1.33.0` → `1.34.0` per versioning policy.

## Senior Developer Review (AI)

**Reviewer:** Oleh (via Claude code-review workflow)
**Date:** 2026-04-23
**Outcome:** Approved with fixes applied.

### Findings

- **[HIGH] H1** — Decision doc cross-referenced a stale `TD-069` ID while the register entry was actually written as `TD-081`. Fixed inline at [agentcore-bedrock-region-availability-2026-04.md:27](../../docs/decisions/agentcore-bedrock-region-availability-2026-04.md#L27).
- **[MEDIUM] M1** — Git diff bundles Story 9.3's sprint-status flip + TD-079/080 alongside Story 9.4's artifacts. **Withdrawn on review** — expected co-PR shape for sibling Epic 9 spikes landing together.
- **[MEDIUM] M2** — `invoke-tests.json` per-invoke timestamps didn't document whether they marked invocation start or completion. Fixed by adding a `timestamp_semantics` note to the `meta` block.
- **[MEDIUM] M3** — `models.yaml` used `bedrock:` as a top-level wrapper, contradicting AC #4's literal "logical role → provider-qualified model ID" schema. Restructured: role at top level, values prefixed with `bedrock:` scheme. Parses via `yaml.safe_load`; Bedrock is the only provider we evaluate, so the wrapper was unnecessary.
- **[LOW] L1** — Re-run Step 3 JMESPath filter uses `contains(…,`laude`)` as a case-insensitive match trick. Added an inline comment so a future re-run operator doesn't misread it as a typo.
- **[LOW] L2** — ADR-0003 Decision section phrased the decision as conditional; conditionality belongs in the Status field. Reworded.

### Verification

- `python -c "import yaml; yaml.safe_load(open('backend/app/agents/models.yaml'))"` → dict with three role keys, all `bedrock:…` values.
- AC #1 Outcome line preserved verbatim in the decision doc.
- AC #4 schema now aligned: role → provider-qualified ID.
- AC #5 ADR-0003 remains `Status: Proposed`; Story 9.5b cross-region path still blocked on DPO/Legal sign-off.

## Change Log

- 2026-04-23 — Story 9.4 drafted: decision-gate spike validating Claude-on-Bedrock (haiku + sonnet) invoke-testing and AgentCore regional availability in `eu-central-1`. Output is a committed decision doc + `backend/app/agents/models.yaml` with pinned Bedrock model IDs (consumed by Stories 9.5a/9.5b), plus a conditional ADR-0003 stub if cross-region inference is required. No production code change; blocks Epic 10 scope-lock.
- 2026-04-23 — Code review completed. Fixed H1 (TD-069 → TD-081 reference in decision doc), M2 (added `timestamp_semantics` note to invoke-tests.json meta), M3 (restructured `backend/app/agents/models.yaml` to role-at-top-level per AC #4, dropped unnecessary `bedrock:` wrapper), L1 (commented the `laude` JMESPath filter), L2 (tightened ADR-0003 Decision wording). M1 (PR bundles Story 9.3 artifacts) withdrawn on review. Status flipped review → done.
- 2026-04-23 — Story 9.4 implementation complete. Invoke-tests executed against `eu-central-1`: Haiku (`eu.anthropic.claude-haiku-4-5-20251001-v1:0`, 2719 ms) and Sonnet (`eu.anthropic.claude-sonnet-4-6`, 3002 ms) both returned HTTP 200 via EU-scoped inference profiles routing to `eu-north-1`. AgentCore control plane (`list_agent_runtimes`, `list_memories`) returned HTTP 200 — service fully available in `eu-central-1`, no allowlist. **Outcome: proceed on eu-central-1 with cross-region inference profile for eu.anthropic.claude-haiku-4-5-20251001-v1:0, eu.anthropic.claude-sonnet-4-6.** ADR-0003 filed as Proposed; Story 9.5b blocked on DPO/Legal sign-off. TD-081 registered for awscli `bedrock-agentcore` CLI binding gap. Regression: 861 passed, 11 deselected — matches baseline. Version bumped from 1.33.0 to 1.34.0 per story completion.
