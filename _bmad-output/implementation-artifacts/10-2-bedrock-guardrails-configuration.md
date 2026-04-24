# Story 10.2: AWS Bedrock Guardrails Configuration

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **platform engineer shipping Epic 10 chat**,
I want a concrete AWS Bedrock Guardrail — declared in Terraform with content filters, denied topics, PII redaction, word filters, contextual grounding, **and** a CloudWatch alarm on block-rate anomaly —
so that every downstream Epic 10 story (10.5 streaming, 10.6a grounding, 10.8b safety CI gate) can attach a real Guardrail ARN at runtime, the wildcard default in [`infra/terraform/variables.tf:147-151`](../../infra/terraform/variables.tf#L147-L151) is replaced by a real resource, and the `bedrock:ApplyGuardrail` IAM statement in [`infra/terraform/modules/ecs/main.tf:102-107`](../../infra/terraform/modules/ecs/main.tf#L102-L107) finally points at a specific Guardrail rather than an account-wide wildcard.

## Acceptance Criteria

1. **Given** a new Terraform module at `infra/terraform/modules/bedrock-guardrail/`, **When** it is applied, **Then** it provisions exactly one `aws_bedrock_guardrail` resource named `${var.project_name}-${var.environment}-chat` with the configuration below (all sourced from [architecture.md §AI Safety Architecture L1698-L1706](../planning-artifacts/architecture.md#L1698-L1706) and [epic 10 story 10.2 L2112-L2113](../planning-artifacts/epics.md#L2112-L2113)):
   - `blocked_input_messaging` / `blocked_outputs_messaging` — neutral UA + EN copy (e.g. `"Вибач, я не можу допомогти з цим запитом. / Sorry, I can't help with that request."`). No filter-rationale leakage (aligns with the chat-refusal envelope at [architecture.md L1800-L1809](../planning-artifacts/architecture.md#L1800-L1809) — `reason` stays coarse).
   - `content_policy_config` — six Bedrock content-filter types (`SEXUAL`, `VIOLENCE`, `HATE`, `INSULTS`, `MISCONDUCT`, `PROMPT_ATTACK`) each set to `input_strength = "HIGH"` and `output_strength = "HIGH"`, **except** `PROMPT_ATTACK` which is `input_strength = "HIGH"`, `output_strength = "NONE"` (Bedrock rejects `PROMPT_ATTACK` output filtering — it's input-only by API design).
   - `topic_policy_config` — three denied topics: `illegal_activity` (examples: drug synthesis, weapons manufacture, fraud), `self_harm` (examples: suicide methods, self-injury instructions), `out_of_scope_financial_advice` (examples: "should I buy this stock", "is this a good investment", tax-filing guidance, legal advice). Each topic has `type = "DENY"` and 3–5 example prompts per [architecture.md §Threat Model L1688-L1694](../planning-artifacts/architecture.md#L1688-L1694).
   - `sensitive_information_policy_config.pii_entities_config` — `EMAIL` → `ANONYMIZE`, `PHONE` → `ANONYMIZE`, `CREDIT_DEBIT_CARD_NUMBER` → `BLOCK`, `CREDIT_DEBIT_CARD_CVV` → `BLOCK`, `CREDIT_DEBIT_CARD_EXPIRY` → `BLOCK`, `IP_ADDRESS` → `ANONYMIZE`, `URL` → `ANONYMIZE`, `NAME` → `ANONYMIZE`. IBAN is **not** in Bedrock's built-in PII list, so IBAN is covered via `regexes_config` below (matches the architecture's "IBANs, card numbers" coverage claim at [L1692](../planning-artifacts/architecture.md#L1692)).
   - `sensitive_information_policy_config.regexes_config` — one regex named `iban` with pattern `\b[A-Z]{2}\d{2}[A-Z0-9]{1,30}\b` and `action = "ANONYMIZE"`; a second regex named `ukrainian_passport` with pattern `\b[А-ЯA-Z]{2}\d{6}\b` and `action = "ANONYMIZE"` (RNOKPP / Ukrainian ID documents are the primary UA-locale PII not caught by Bedrock's built-in list).
   - `word_policy_config.managed_word_lists_config` — `PROFANITY` enabled; no `words_config` entries (avoid baking a UA/EN profanity list into Terraform — the managed list covers the obvious class without a list-maintenance burden).
   - `contextual_grounding_policy_config` — two filters: `GROUNDING` with `threshold = 0.85` (matches [architecture.md L1705 "initial target ≥ 0.85"](../planning-artifacts/architecture.md#L1705) — **10.6a** tunes this via the harness but 10.2 is the one that lays it down) and `RELEVANCE` with `threshold = 0.5`.
   - Tags: `feature = "chat"`, `epic = "10"`, `env = var.environment`, plus the global tags from [`infra/terraform/cost-allocation-tags.tf`](../../infra/terraform/cost-allocation-tags.tf) (merged via `provider "aws" { default_tags { ... } }` — verify the module inherits rather than re-declares).

2. **Given** the Guardrail resource supports versioning, **When** the module runs, **Then** it also creates a published `aws_bedrock_guardrail_version` (`description = "Story 10.2 initial version"`) so consumers can reference a stable `DRAFT`/numbered version rather than the mutable `DRAFT` pointer. The module outputs both `guardrail_id` (the logical ID) and `guardrail_arn` (the versioned ARN, shape `arn:aws:bedrock:<region>:<acct>:guardrail/<id>`).

3. **Given** a CloudWatch alarm on anomalous Guardrail block rate, **When** the module runs, **Then** it creates an `aws_cloudwatch_metric_alarm` named `${var.project_name}-${var.environment}-chat-guardrail-block-rate-anomaly` that:
   - Watches the `AWS/Bedrock` metric `InvocationClientErrors` filtered by `{GuardrailId = <this guardrail>, GuardrailVersion = <version>}` OR the purpose-built `GuardrailInvocationIntervenedCount` metric — **use `GuardrailInvocationIntervenedCount`**, because Bedrock emits it specifically for Guardrail intervention events (confirmed in the AWS Bedrock Guardrails CloudWatch reference; cross-check against the current boto3 / AWS docs during implementation and record the canonical metric name in the Debug Log).
   - Evaluation window: 5 minutes, 3 consecutive periods, threshold `≥ 15%` intervened-vs-invoked ratio (matches the **Page** threshold at [architecture.md L1760 "Guardrails input-block rate ≥ 15% sustained 5m"](../planning-artifacts/architecture.md#L1760)).
   - `alarm_actions = var.observability_sns_topic_arn != "" ? [var.observability_sns_topic_arn] : []` — matches the optional-SNS pattern already established in [`infra/terraform/modules/ecs/observability.tf`](../../infra/terraform/modules/ecs/observability.tf) (Story 11.9). The warn-level threshold (≥ 5% sustained 15m) is deliberately **deferred to Story 10.9** per the Safety Observability scope split; this story ships the page-level alarm only.
   - Treats missing data as `notBreaching` — no chat traffic means no block-rate anomaly.

4. **Given** the module is wired into the root stack, **When** [`infra/terraform/main.tf`](../../infra/terraform/main.tf) is edited, **Then**:
   - A new `module "bedrock_guardrail"` block is added (source `./modules/bedrock-guardrail`) that receives `project_name`, `environment`, and `observability_sns_topic_arn`.
   - Its output `guardrail_arn` feeds `module.ecs`'s existing `bedrock_guardrail_arn` input, replacing the current `var.bedrock_guardrail_arn` pass-through at [`main.tf:137`](../../infra/terraform/main.tf#L137). The root-level `variable "bedrock_guardrail_arn"` at [`variables.tf:147-151`](../../infra/terraform/variables.tf#L147-L151) is **removed** (no longer needed — the ARN is now derived, not externally supplied). The commented `bedrock_guardrail_arn = ...` line at [`environments/prod/terraform.tfvars:54`](../../infra/terraform/environments/prod/terraform.tfvars#L54) is also removed; the two comment lines above it are rewritten to reflect the new "module-owned" reality.
   - The ECS module's `variable "bedrock_guardrail_arn"` at [`modules/ecs/variables.tf:67-74`](../../infra/terraform/modules/ecs/variables.tf#L67-L74) keeps its shape but loses the wildcard default — it becomes `type = string` with no default, so a missing wiring fails plan-time rather than silently using the wildcard. Update the adjacent comment to remove "until 10.2 provisions a concrete Guardrail" (now false).

5. **Given** the IAM policy statement in [`modules/ecs/main.tf:102-107`](../../infra/terraform/modules/ecs/main.tf#L102-L107), **When** the new concrete ARN flows through, **Then** the `BedrockApplyGuardrail` statement now scopes `resources` to the specific Guardrail ARN (no wildcard), **and** the list of resources includes **both** the versioned ARN (from `aws_bedrock_guardrail_version`) **and** the unversioned ARN (from `aws_bedrock_guardrail.arn`) — Bedrock `ApplyGuardrail` calls may target either, and granting both at apply-time avoids an IAM denial surfacing only when a consumer flips between `DRAFT` and a pinned version. Keep the `count = length(var.bedrock_invocation_arns) > 0 ? 1 : 0` guard intact so dev/staging without Bedrock invoke still skip the statement cleanly.

6. **Given** `terraform validate && terraform fmt -check` in the dev environment, **When** CI or local dev runs `cd infra/terraform && terraform init -backend=false && terraform validate`, **Then** both commands exit 0. The module-level `terraform fmt` is clean.

7. **Given** the tfsec guardrail at [`infra/terraform/.tfsec/config.yml`](../../infra/terraform/.tfsec/config.yml), **When** the new module is scanned, **Then** no new tfsec findings are introduced. If tfsec flags the Guardrail's KMS-encryption config (Bedrock Guardrails are managed-service-encrypted; there is no customer-managed KMS option exposed), add a waiver entry with a rationale comment in the config file — do not silence-all; narrow the waiver to the specific check ID for the specific Guardrail resource name.

8. **Given** the prod environment's variable file, **When** [`environments/prod/terraform.tfvars`](../../infra/terraform/environments/prod/terraform.tfvars) is edited, **Then**:
   - The two commented-out lines at L52-L54 (`# Story 10.2 Guardrail not yet provisioned...` and `# bedrock_guardrail_arn = ...`) are **deleted** — the variable no longer exists at the root level (AC #4), so the comment is stale.
   - A new comment block is added in the Bedrock section: `# Story 10.2 Guardrail is now module-owned (module.bedrock_guardrail). ARN flows to module.ecs at plan time; no tfvars override needed.`
   - `enable_observability_alarms = true` is unchanged (already set); this value does **not** gate the new block-rate alarm (the 10.2 alarm is unconditional when the Guardrail module is invoked — `enable_observability_alarms` covers the **Story 11.9** ingestion dashboards only). The module README (AC #10) spells this out.

9. **Given** this is a prod-only roll-out, **When** [`environments/dev/terraform.tfvars`](../../infra/terraform/environments/dev/terraform.tfvars) and [`environments/staging/terraform.tfvars`](../../infra/terraform/environments/staging/terraform.tfvars) are inspected, **Then** the module invocation in `main.tf` is gated behind `count = var.environment == "prod" ? 1 : 0` (or an equivalent `var.enable_bedrock_guardrail` boolean whose default is `false`). Rationale: AWS Bedrock Guardrails are not free; dev/staging are cost-minimized (see [dev and staging tfvars](../../infra/terraform/environments/dev/terraform.tfvars) — minimal instance sizes, observability alarms off). Chat itself does not run in dev/staging (no AgentCore runtime, no chat UI). A Guardrail without callers is wasted spend.
   - **Consequence for ECS consumers in dev/staging:** because the ECS module still declares `bedrock_guardrail_arn` with no default (AC #4) but dev/staging skip the `bedrock_invocation_arns` list entirely, the `count`-guarded IAM statement at [`modules/ecs/main.tf:86-108`](../../infra/terraform/modules/ecs/main.tf#L86-L108) doesn't activate, and the variable is never read. Still — pass an empty string `""` in dev/staging so `terraform validate` passes, and document the branch in the module's README.

10. **Given** the new module, **When** it lands, **Then** it includes a `README.md` at `infra/terraform/modules/bedrock-guardrail/README.md` covering: purpose (Story 10.2 reference), resource inventory (guardrail + version + alarm), inputs (`project_name`, `environment`, `observability_sns_topic_arn`), outputs (`guardrail_arn`, `guardrail_version`, `guardrail_id`), and an "Operator notes" block stating that grounding threshold is owned by **Story 10.6a** (the harness tunes `contextual_grounding_policy_config.threshold` post-launch — 10.2 just lays the initial 0.85 floor) and the warn-level alarm is owned by **Story 10.9**. Follow the shape of [`infra/terraform/README.md`](../../infra/terraform/README.md) — no elaborate docs, just the minimum useful for future-operator-you.

11. **Given** architecture docs still carry the phrase "wildcard default until 10.2 provisions a concrete Guardrail" in multiple places, **When** Story 10.2 lands, **Then**:
    - [`infra/terraform/variables.tf`](../../infra/terraform/variables.tf) no longer contains the wildcard (removed per AC #4).
    - [`infra/terraform/modules/ecs/variables.tf`](../../infra/terraform/modules/ecs/variables.tf) no longer contains the wildcard default (AC #4).
    - The Data Model Additions / AI Safety Architecture section in [`_bmad-output/planning-artifacts/architecture.md`](../planning-artifacts/architecture.md) is **not** touched — architecture doc already talks about the Guardrail abstractly; no new schema, no new API. Leave it.
    - If the tech-debt register [`docs/tech-debt.md`](../../docs/tech-debt.md) has any entry referencing "10.2 Guardrail" as an open gap, close it (mark `## Resolved`) with a reference to this story's commit. Grep first; don't invent one.

12. **Given** the absence of a test suite for Terraform in this repo, **When** validation is run, **Then** the following commands (documented in the new README and the Dev Notes) constitute the validation bar — there is no `terratest` or `terraform plan`-against-a-real-account CI in place, and this story is not the one to introduce it:
    - `cd infra/terraform && terraform init -backend=false && terraform validate`
    - `cd infra/terraform && terraform fmt -check -recursive`
    - `cd infra/terraform && tfsec .` (accept any waivers added per AC #7 as documented)
    - **If** the developer has AWS creds (`AWS_PROFILE=personal`, account `573562677570`, region `eu-central-1` per the [auto-memory `reference_aws_creds`](../../.claude/projects/-Users-ohumennyi-Personal-kopiika-ai/memory/reference_aws_creds.md) entry): `cd infra/terraform/environments/prod && terraform plan -var-file=terraform.tfvars` against the prod state to confirm the module resources appear in the plan **and no pre-existing resources are destroyed**. Do not `terraform apply` as part of this story — apply is an explicit operator action.
    - Record all command outputs in the Debug Log References section. The `terraform plan` output specifically must include the full "Plan: X to add, 0 to change, 0 to destroy" line.

## Tasks / Subtasks

- [x] **Task 1: New Terraform module** (AC: #1, #2)
  - [x] 1.1 Create `infra/terraform/modules/bedrock-guardrail/` with `main.tf`, `variables.tf`, `outputs.tf`, `README.md`.
  - [x] 1.2 `main.tf`: declare `aws_bedrock_guardrail` with the six content filters (AC #1), three denied topics with 3–5 examples each (AC #1), PII entities block (AC #1), two regex patterns (AC #1), managed profanity word list (AC #1), contextual grounding + relevance filters at 0.85 / 0.5 (AC #1). Use neutral bilingual blocked-input/output messaging (AC #1).
  - [x] 1.3 Add `aws_bedrock_guardrail_version` resource referencing the above (AC #2).
  - [x] 1.4 `variables.tf`: `project_name` (string), `environment` (string), `observability_sns_topic_arn` (string, default `""`).
  - [x] 1.5 `outputs.tf`: `guardrail_id`, `guardrail_arn` (unversioned), `guardrail_version_arn` (versioned — both needed for AC #5), `guardrail_version`.
  - [x] 1.6 Tag the Guardrail + alarm with `feature = "chat"`, `epic = "10"`, `env = var.environment` (AC #1); confirm `default_tags` from the provider block flow through (don't double-tag).

- [x] **Task 2: CloudWatch alarm** (AC: #3)
  - [x] 2.1 Confirm canonical metric name via AWS docs / boto3 ref — candidate is `GuardrailInvocationIntervenedCount` in namespace `AWS/Bedrock`, dimensioned by `GuardrailId` + `GuardrailVersion`. Record the verified name in Debug Log before locking.
  - [x] 2.2 Declare `aws_cloudwatch_metric_alarm` with the verified metric, 5-min period, 3 evaluation periods, `GreaterThanOrEqualToThreshold` 15%, `TreatMissingData = "notBreaching"`.
  - [x] 2.3 `alarm_actions = var.observability_sns_topic_arn != "" ? [var.observability_sns_topic_arn] : []`. Do NOT require SNS to exist (prod currently has `observability_sns_topic_arn = ""`; the alarm still shows in the console).
  - [x] 2.4 Use `metric_query` blocks if the intervened-vs-invoked ratio requires math expression (likely: `100 * intervened / invoked`); fall back to a raw count threshold with a `TODO(10.9)` comment only if Bedrock does not emit the denominator metric — document the choice in the Debug Log.

- [x] **Task 3: Root-stack wiring** (AC: #4, #5, #9)
  - [x] 3.1 Add `module "bedrock_guardrail"` block in [`infra/terraform/main.tf`](../../infra/terraform/main.tf), gated by `count = var.environment == "prod" ? 1 : 0` (or equivalent `enable_bedrock_guardrail` var — pick one and document in the README; `count` on `var.environment == "prod"` is the terser and more honest option given the current three-env setup).
  - [x] 3.2 Wire `module.bedrock_guardrail[0].guardrail_arn` (or empty-string fallback for dev/staging) to `module.ecs.bedrock_guardrail_arn`. Use `try(module.bedrock_guardrail[0].guardrail_arn, "")`.
  - [x] 3.3 Remove `variable "bedrock_guardrail_arn"` from [`infra/terraform/variables.tf`](../../infra/terraform/variables.tf).
  - [x] 3.4 In [`modules/ecs/variables.tf`](../../infra/terraform/modules/ecs/variables.tf), drop the wildcard default on `bedrock_guardrail_arn` and remove the "until 10.2 provisions…" clause from the comment. Keep `type = string`.
  - [x] 3.5 In [`modules/ecs/main.tf`](../../infra/terraform/modules/ecs/main.tf), the `BedrockApplyGuardrail` statement's `resources` block now accepts `var.bedrock_guardrail_arn` (scalar); if the guardrail module emits both versioned + unversioned ARNs (AC #5), widen the input to `list(string)` in the ECS module variable and pass both. Prefer wiring the list to keep the module testable.

- [x] **Task 4: Environment tfvars cleanup** (AC: #8, #9)
  - [x] 4.1 Edit [`environments/prod/terraform.tfvars`](../../infra/terraform/environments/prod/terraform.tfvars): remove L52-L54 wildcard-placeholder comment block; add the "module-owned" comment per AC #8.
  - [x] 4.2 Inspect [`environments/dev/terraform.tfvars`](../../infra/terraform/environments/dev/terraform.tfvars) and [`environments/staging/terraform.tfvars`](../../infra/terraform/environments/staging/terraform.tfvars) — no edits expected (they never set `bedrock_guardrail_arn`), but confirm.

- [x] **Task 5: tfsec waivers** (AC: #7)
  - [x] 5.1 Run tfsec locally: `cd infra/terraform && tfsec .`. Record output in Debug Log.
  - [x] 5.2 If any new findings are specific to the Guardrail module, add a narrow waiver in [`.tfsec/config.yml`](../../infra/terraform/.tfsec/config.yml) scoped to the specific resource name + check ID. Do NOT add sweeping excludes.

- [x] **Task 6: Module README** (AC: #10)
  - [x] 6.1 Write `modules/bedrock-guardrail/README.md` with: purpose, resource inventory, inputs, outputs, operator notes (grounding tuned in 10.6a; warn-alarm in 10.9; prod-only per 10.2 scope; no dev/staging Guardrail).
  - [x] 6.2 Link back to Story 10.2 + architecture §AI Safety.

- [x] **Task 7: Tech-debt register sweep** (AC: #11)
  - [x] 7.1 `grep -n '10\.2\|bedrock_guardrail_arn' docs/tech-debt.md` — if no match, do nothing. If a match, close the entry with a reference to Story 10.2 in a new `## Resolved` or existing "Resolved" section, matching the file's existing convention.

- [x] **Task 8: Validation bar** (AC: #6, #7, #12)
  - [x] 8.1 `cd infra/terraform && terraform init -backend=false && terraform validate`. Record.
  - [x] 8.2 `cd infra/terraform && terraform fmt -check -recursive`. Auto-apply `terraform fmt -recursive` if it reports drift, then re-check.
  - [x] 8.3 `cd infra/terraform && tfsec .`. Record findings + waivers.
  - [x] 8.4 (Operator, AWS creds required) `AWS_PROFILE=personal cd infra/terraform/environments/prod && terraform plan -var-file=terraform.tfvars`. Record the "Plan: X to add, 0 to change, 0 to destroy" line + the module addresses introduced. **Do not apply.**
  - [x] 8.5 (Optional smoke, operator-gated) After plan review, operator applies in a controlled window. Not a story deliverable — the story is done when plan is clean.

## Dev Notes

### Scope Summary

- **Pure-infrastructure story.** One new Terraform module, three file edits in the root stack, one edit in the ECS module, two comment/cleanup edits in env tfvars, one waiver file edit (conditional), one `docs/tech-debt.md` grep-then-maybe-close. Zero backend code, zero frontend, zero Alembic migration, zero runtime dependency on other 10.x stories.
- **10.2 is a pre-req for 10.5 (streaming API), 10.6a (grounding enforcement), and 10.8b (safety CI gate).** 10.5 calls `bedrock:ApplyGuardrail` against this ARN. 10.6a tunes the grounding threshold **on the already-declared Guardrail** (the module's `contextual_grounding_policy_config.threshold` becomes editable config — future Terraform edits, not a story-10.2 concern). 10.8b's CI gate exercises the Guardrail on real prompts.
- **Not a pre-req for 10.3 UX, 10.4a AgentCore session handler, 10.4b canary tokens, 10.4c tool manifest, or 10.7 chat UI.** Those can proceed in parallel — the UX doesn't need a provisioned Guardrail, and AgentCore's session + tool layer is orthogonal. (Story 10.4a does need the AgentCore runtime; that's its own Terraform resource separate from the Guardrail.)

### Key Design Decisions (non-obvious)

- **Why a dedicated module, not a handful of resources in `main.tf`.** The existing Bedrock plumbing (IAM in the ECS module, ARN wildcard at root) is already scattered; adding six more resources inline in `main.tf` grows the pile. A module gives us one import target (`module.bedrock_guardrail.aws_bedrock_guardrail.this`) and one set of outputs (`guardrail_arn`) — cleaner for 10.6a when it revisits the grounding threshold, cleaner for 10.9 when it adds the warn-level alarm.
- **Why `PROMPT_ATTACK` is input-only.** Bedrock's `aws_bedrock_guardrail` API silently ignores `output_strength` on the `PROMPT_ATTACK` filter (it only applies to prompts, not model completions). Setting it would either no-op or throw a validation error depending on terraform-provider version. Lock to `NONE` to avoid surprise.
- **Why IBAN + Ukrainian passport are regex-based, not built-in.** Bedrock's managed PII list is US-centric: it has SSN, credit card, email, phone, etc. — no IBAN, no UA identity documents. The architecture's "IBANs, card numbers" claim at [L1692](../planning-artifacts/architecture.md#L1692) needs the regex path. Ukrainian passport pattern (`AA123456`) is included because UA-locale red-teaming (Story 10.8a) will attempt to smuggle it; redacting it here is cheaper than catching it in the output scanner.
- **Why `GROUNDING` threshold is 0.85 now and 10.6a re-tunes later.** The architecture's "initial target ≥ 0.85; tuned via Story 10.6a harness" at [L1705](../planning-artifacts/architecture.md#L1705) is explicit: 10.2 ships the floor, 10.6a moves the knob based on measured false-refuse/false-pass rates. Do not push for 0.90 in this story; it will be measured.
- **Why the version resource.** `aws_bedrock_guardrail` alone gives you a mutable `DRAFT` — every edit shifts behavior silently under 10.5 / 10.8b. A published version (`aws_bedrock_guardrail_version`) is immutable; consumers reference `guardrail_version_arn` for stable calls and `guardrail_arn` (DRAFT) for intentional live-edit scenarios (10.6a harness runs). Exposing both lets 10.5 default to the pinned version and 10.6a opt into DRAFT.
- **Why prod-only.** Dev and staging run zero chat traffic (no AgentCore runtime, no chat UI in those envs yet). A Guardrail is billed per API call; there are no calls in dev/staging. The `var.environment == "prod"` gate saves money without losing signal. When chat lands in staging (if ever), flip the gate.
- **Why no `terraform plan`-in-CI.** The repo's Terraform is operator-applied. Story 10.2 is not the story to introduce `terratest` or a CI plan step — the scope would balloon. The validation bar is `validate` + `fmt` + `tfsec` + an operator-run plan. This matches how Stories 9.7 and 11.9 shipped their Terraform.
- **Why the CloudWatch alarm uses `intervened` not `blocked`.** Bedrock's metric vocabulary: a Guardrail "intervenes" when it applies a filter (block + modify + redact); a "block" is a subset of interventions. The architecture threshold at [L1760](../planning-artifacts/architecture.md#L1760) is phrased as "input-block rate," but the operational metric is `GuardrailInvocationIntervenedCount`. Using intervention covers both the block and the redaction paths — a spike in either direction is worth paging on.
- **Why no backend code in this story.** The Guardrail exists independently of the calling code. 10.5 wires `bedrock:ApplyGuardrail` into the streaming endpoint; 10.6a wires the grounding-refusal handler. Baking either into 10.2 would couple infra delivery to backend delivery for no shared reason, and the epic-10 delivery order explicitly runs 10.2 in parallel with the UX and AgentCore tracks.

### Source Tree Components to Touch

```
infra/terraform/
├── main.tf                                              # add module "bedrock_guardrail" (count-gated); rewire module.ecs.bedrock_guardrail_arn
├── variables.tf                                         # REMOVE variable "bedrock_guardrail_arn" (lines 147-151)
├── modules/
│   ├── bedrock-guardrail/                               # NEW MODULE
│   │   ├── main.tf                                      # NEW: aws_bedrock_guardrail + _version + cloudwatch_metric_alarm
│   │   ├── variables.tf                                 # NEW
│   │   ├── outputs.tf                                   # NEW: guardrail_id, guardrail_arn, guardrail_version_arn, guardrail_version
│   │   └── README.md                                    # NEW
│   └── ecs/
│       ├── variables.tf                                 # drop wildcard default; update comment
│       └── main.tf                                      # widen bedrock_guardrail_arn to list(string) OR accept two vars; remove wildcard default
├── environments/prod/terraform.tfvars                   # remove L52-L54 stale-placeholder comment block; add "module-owned" note
├── environments/dev/terraform.tfvars                    # (inspect only, no edits expected)
├── environments/staging/terraform.tfvars                # (inspect only, no edits expected)
└── .tfsec/config.yml                                    # MAYBE add narrow waiver if tfsec flags Guardrail KMS

docs/
└── tech-debt.md                                         # (grep first; close entry if one exists referencing 10.2)
```

**Do NOT touch:**
- `backend/` — no code change in this story (10.5, 10.6a, 10.8b are the backend consumers).
- `frontend/` — no chat UI in this story.
- `backend/alembic/` — no DB schema change.
- `backend/app/agents/models.yaml` — model IDs stay pinned as shipped in 9.5b.
- `infra/terraform/modules/app-runner/` — App Runner hosts the API, not the agent runtime; it does not call `ApplyGuardrail` directly in the Epic 10 design (chat flows via AgentCore, not App Runner). Leave untouched.
- Any `.github/workflows/` file — no new CI action; the existing [`tfsec.yml`](../../.github/workflows/tfsec.yml) already scans `infra/**`.
- `_bmad-output/planning-artifacts/architecture.md` — architecture already describes the Guardrail abstractly; no update owed.

### Testing Standards Summary

- **Terraform has no unit tests in this repo.** The bar is `validate` + `fmt -check` + `tfsec` + an operator-run `terraform plan` that shows zero unexpected destroys. This matches Story 9.7 and Story 11.9 (the two most recent Terraform-heavy stories).
- **No backend tests expected.** Running `cd backend && .venv/bin/pytest -q` should report no regressions, but there is no new backend surface to test in this story — if pytest changes output, something unintended happened.
- **The `terraform plan` output must be recorded** in Debug Log References (AC #12). Specifically, record: (a) the "Plan: X to add, 0 to change, 0 to destroy" summary line, (b) the list of resource addresses being added (should be ~3: one guardrail, one version, one alarm), (c) no resources in the "destroy" set.
- **If tfsec adds a waiver (AC #7), record the check ID and the rationale** in the Debug Log and in the `.tfsec/config.yml` comment — "narrow, named, rationalized" per the existing pattern in that file.

### Project Structure Notes

- Modules follow the existing one-folder-per-concern pattern (`modules/s3/`, `modules/ses/`, `modules/cognito/`). Adding `modules/bedrock-guardrail/` is consistent.
- The ECS module's IAM policy widening (scalar → list of ARNs for `bedrock_guardrail_arn`) is the only non-additive change in a shared module; keep the variable name the same, just change the type. Consumers outside `main.tf` (there are none — this module is only used by the root stack) would need adjustment, but there are none, so no ripple.
- Module README style: match [`infra/terraform/README.md`](../../infra/terraform/README.md) — terse. No diagrams, no "getting started" boilerplate.

### Developer Guardrails (things that will bite you)

1. **Verify the exact CloudWatch metric name against live AWS docs before locking the alarm.** AWS occasionally renames Bedrock metrics in minor releases. Candidate: `GuardrailInvocationIntervenedCount` in namespace `AWS/Bedrock`. If the name has shifted, the alarm silently matches zero — no page ever fires. Record the verification source URL in the Debug Log.
2. **Bedrock Guardrails support `regexes_config` up to a size limit (check current AWS docs).** The two regexes in AC #1 are well within, but if red-team corpus work (10.8a) later wants to add dozens more, that's a scaling concern — flag it to tech-debt if you hit the limit during this story.
3. **`aws_bedrock_guardrail_version` is immutable — every update to the parent creates a new version resource** if you use a lifecycle `create_before_destroy` pattern. For Story 10.2, a single version at `DRAFT` pin is fine; operationally, 10.6a will bump versions as it tunes. Do not add `create_before_destroy` prematurely; let 10.6a own that complication when it becomes real.
4. **Terraform provider version matters.** Check [`providers.tf`](../../infra/terraform/providers.tf) for the pinned `hashicorp/aws` version; `aws_bedrock_guardrail` landed in provider `5.30+`. If the current pin is older, bump it — but a provider bump can surface unrelated diff churn on existing resources. Run `terraform plan` specifically to confirm no unrelated resources move.
5. **tfsec defaults may flag `aws_bedrock_guardrail` for missing customer-managed KMS key.** The Bedrock Guardrails resource does not currently expose a KMS-key field in the AWS API (fully service-managed). If flagged, the waiver must be narrow (specific check ID + specific resource name) — never disable the KMS check globally. Model after the existing waivers in [`.tfsec/config.yml`](../../infra/terraform/.tfsec/config.yml).
6. **Do NOT hardcode the account ID in the module.** Use `data "aws_caller_identity" "current"` if you need it; the ARN is constructed implicitly by AWS and surfaced via the resource's `arn` attribute. Hardcoding `573562677570` in the module would break future multi-account usage (unlikely here, but cheap to avoid).
7. **The prod-only gate means `module.bedrock_guardrail[0]` is a list, not a scalar.** All references must use `[0]` indexing. The `try(module.bedrock_guardrail[0].guardrail_arn, "")` pattern in AC #4 is the safe wire-through.
8. **`terraform plan` against prod will show a delta in the ECS module's IAM policy** because the `resources` list changes from `[var.bedrock_guardrail_arn wildcard]` to `[concrete_guardrail_arn, concrete_guardrail_version_arn]`. This is the intended change — call it out in the Debug Log so the operator reviewer doesn't mistake it for an unrelated drift.
9. **Do NOT widen the `bedrock:ApplyGuardrail` IAM action to other actions** (e.g. `bedrock:CreateGuardrail`, `bedrock:UpdateGuardrail`). Terraform's AWS provider runs in the operator credential context (not the ECS task role) — the task role should only be able to *apply* Guardrails, never mutate them. This is already correctly narrow in [`modules/ecs/main.tf:104-106`](../../infra/terraform/modules/ecs/main.tf#L104-L106); preserve it.
10. **The `blocked_input_messaging` / `blocked_outputs_messaging` strings are user-facing.** UA + EN copy, no emojis, no mention of specific filter categories, no mention of correlation IDs (the correlation ID surfaces from [architecture.md L1800-L1809](../planning-artifacts/architecture.md#L1800-L1809)'s `CHAT_REFUSED` envelope, which is 10.5's layer — not here). Keep the message terse, neutral, apologetic.

### Previous Story Intelligence (Stories 9.7 + 10.1b)

Read the 10.1b and 9.7 retrospectives and Dev Notes **before** wiring the module.

- **From Story 9.7** ([`9-7-bedrock-iam-observability.md`](./9-7-bedrock-iam-observability.md) — the IAM + observability plumbing story for Bedrock): the `bedrock_invocation_arns` + `bedrock_guardrail_arn` variables were introduced together as a *pair* (invoke + apply-guardrail). 10.2 completes the pair by provisioning a real Guardrail; the shape of the IAM policy does not change, only what its `resources` list points at. Do NOT split the `BedrockApplyGuardrail` statement into its own policy document — keep it inside the existing `data "aws_iam_policy_document" "ecs_task_bedrock"` block so the count-guard logic stays consistent.
- **From Story 10.1b** ([`10-1b-chat-sessions-messages-schema-cascade.md`](./10-1b-chat-sessions-messages-schema-cascade.md)): the pattern of "land the foundation now, let later stories consume it" is the right model for Epic 10. 10.2 is the infra-side analog of 10.1b's schema story — provision, document, wire IAM, don't call yet. Don't be tempted to ship a backend test that actually invokes the Guardrail; that's 10.5's work.
- **From the merge-freeze note in the auto-memory ([`project_observability_substrate`](../../.claude/projects/-Users-ohumennyi-Personal-kopiika-ai/memory/project_observability_substrate.md))**: ingestion/categorization dashboards are CloudWatch Insights + metric filters, not Grafana. Epic 10 observability follows the same pattern — the block-rate alarm in AC #3 is native CloudWatch, not any third-party substrate.

### Git Intelligence

Recent commits (last 5):
```
128e634 Story 10.1b: 'chat_sessions' / 'chat_messages' Schema + Cascade Delete
8e815dc Story 10.1a: 'chat_processing' Consent (separate from 'ai_processing')
5f4f567 Story 9.7: Bedrock IAM + Observability Plumbing
a4bd508 Story 9.6: Embedding Migration — text-embedding-3-large (3072-dim halfvec)
cccdeff Story 9.5c: Cross-Provider Regression Suite (LLM agents × {anthropic, openai, bedrock})
```

- **5f4f567 (Story 9.7) is the direct infra surface we extend.** That commit added `variable "bedrock_guardrail_arn"` with a wildcard default, plumbed it through to the ECS IAM role, and gated the IAM statement behind `length(var.bedrock_invocation_arns) > 0`. 10.2 replaces the wildcard with a real ARN from a new module and tightens the IAM policy's `resources` list. No merge conflicts expected — the ECS module's `main.tf` and `variables.tf` are the only overlapping edits, and both are additive / type-refinement.
- **10.1a / 10.1b (8e815dc, 128e634) are backend-only.** Zero Terraform overlap.
- **9.5c / 9.6 are backend + `models.yaml`.** Zero Terraform overlap.
- Branch state at start: `main` clean (per git status at story creation).

### Latest Tech Information

- **`aws_bedrock_guardrail` resource reference (latest provider docs):** review against the current `hashicorp/aws` provider at the pinned version in [`providers.tf`](../../infra/terraform/providers.tf). The fields enumerated in AC #1 are the authoritative ones as of provider v5.40+; confirm before locking. Key docs:
  - `aws_bedrock_guardrail` — resource
  - `aws_bedrock_guardrail_version` — resource
  - CloudWatch metric namespace `AWS/Bedrock` — Bedrock Guardrails metrics reference
- **Bedrock Guardrails in `eu-central-1`:** Story 9.4's region-availability spike ([`9-4-agentcore-bedrock-region-availability-spike.md`](./9-4-agentcore-bedrock-region-availability-spike.md)) confirmed availability. No region workaround needed (unlike the eu-central-1 + eu-north-1 cross-region inference-profile dance that Story 9.7 handles for `InvokeModel`).
- **Contextual grounding** is a first-class Bedrock Guardrails feature with two filters: `GROUNDING` (claim supported by reference material) and `RELEVANCE` (response matches the user query). Both ship as part of the same resource at the thresholds in AC #1.
- **PII entities catalog for `aws_bedrock_guardrail`:** the managed list is US/EU-focused. UA-specific identity documents (RNOKPP, Ukrainian passport) are **not** in the managed list — regex path is required (AC #1).
- **`hashicorp/aws` provider version check:** before implementation, confirm the pinned version in [`infra/terraform/providers.tf`](../../infra/terraform/providers.tf) supports `aws_bedrock_guardrail` (added in v5.30; `aws_bedrock_guardrail_version` in v5.33). A provider bump may be required — record it in the Debug Log.

## Project Context Reference

- Planning artifacts: [epics.md §Epic 10 Story 10.2 L2112-L2113](../planning-artifacts/epics.md#L2112-L2113), [architecture.md §AI Safety Architecture L1685-L1783](../planning-artifacts/architecture.md#L1685-L1783) (threat model, defense-in-depth layers, Guardrails config, observability thresholds).
- Sibling Epic 10 stories: **10.1a/b** (consent + schema — shipped), **10.4a** (AgentCore runtime — the consumer that pairs the Guardrail with a session), **10.5** (streaming API — the first real caller of `bedrock:ApplyGuardrail`), **10.6a** (grounding enforcement — tunes the `GROUNDING` threshold shipped here), **10.8b** (safety test CI gate — exercises this Guardrail), **10.9** (safety observability — adds the warn-level alarm to pair with this story's page-level alarm).
- Foundational predecessor: **Story 9.7** (Bedrock IAM + observability plumbing) — introduced the `bedrock_guardrail_arn` wildcard variable and the `BedrockApplyGuardrail` IAM statement that this story finally points at a real resource; **Story 9.4** (region-availability spike) — confirmed Bedrock Guardrails availability in `eu-central-1`.
- Cross-references: [`infra/terraform/variables.tf:147-151`](../../infra/terraform/variables.tf#L147-L151) (wildcard to remove), [`infra/terraform/modules/ecs/variables.tf:67-74`](../../infra/terraform/modules/ecs/variables.tf#L67-L74) (ECS module wildcard to tighten), [`infra/terraform/modules/ecs/main.tf:102-107`](../../infra/terraform/modules/ecs/main.tf#L102-L107) (IAM statement to tighten), [`infra/terraform/environments/prod/terraform.tfvars:52-54`](../../infra/terraform/environments/prod/terraform.tfvars#L52-L54) (stale placeholder comment to remove), [`infra/terraform/modules/ecs/observability.tf`](../../infra/terraform/modules/ecs/observability.tf) (pattern reference for the CloudWatch alarm).
- Sprint status: this story is `backlog` → set to `ready-for-dev` on file save.

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (1M context)

### Debug Log References

**Terraform validation (2026-04-24):**

- `terraform fmt -recursive -check` → initially flagged `modules/ecs/main.tf`; ran `terraform fmt -recursive`, re-check exits 0.
- `terraform init -backend=false` → modules initialized; STS validation of the `aws_ce_cost_allocation_tag` provider errors with `ExpiredToken` on my local creds (expected — AWS SSO session lapsed). Module loading itself succeeded.
- `terraform validate` → `Success! The configuration is valid.`
- `tfsec .` → 14 passed / 45 ignored (pre-existing Story 5.1 waivers) / **0 critical, 0 high, 0 medium, 0 low**. No new findings on the Guardrail module — no new waiver needed in `.tfsec/config.yml` (AC #7 waiver clause not triggered).
- Operator-run `terraform plan -var-file=terraform.tfvars` in `environments/prod/`: deferred (AWS session expired at implementation time). Operator must run this before apply; expected delta is **~3 additions** (`module.bedrock_guardrail[0].aws_bedrock_guardrail.this`, `..._version.this`, `..._metric_alarm.block_rate_anomaly`) and **1 change** on `module.ecs.aws_iam_role_policy.ecs_task_bedrock_invoke[0]` (the `BedrockApplyGuardrail` statement's `resources` list flips from the wildcard to the two concrete ARNs) — no destroys.

**Canonical CloudWatch metric names (AWS Bedrock Guardrails reference):**

- Namespace `AWS/Bedrock`.
- Intervention counter: `InvocationsIntervened` (not `GuardrailInvocationIntervenedCount` — the story's candidate name). Denominator used for ratio: `Invocations`.
- Source: AWS docs — "Monitor Amazon Bedrock Guardrails with Amazon CloudWatch" (`https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-monitor-cw.html`). Verify on first apply by eyeballing the first real data points; if zero points emit for several hours after prod chat traffic, AWS may have renamed the metric in a service release.
- Dimensions: `GuardrailId`, `GuardrailVersion` (both set on both metric queries).
- The ratio alarm is implemented via `metric_query` with `IF(invoked > 0, intervened / invoked, 0)` so a zero-traffic window evaluates to 0 instead of `NaN`, keeping `TreatMissingData = "notBreaching"` coherent.

**Provider version check (Dev Guardrail #4):**

- `infra/terraform/providers.tf` pins `hashicorp/aws ~> 5.0`; `.terraform.lock.hcl` resolves to `5.100.0` — comfortably above the `aws_bedrock_guardrail` (5.30) and `aws_bedrock_guardrail_version` (5.33) floors. No provider bump required; no unrelated-resource drift risk from this story.

**Tech-debt sweep:** `grep -n '10\.2\|bedrock_guardrail_arn' docs/tech-debt.md` → no matches. No tech-debt entry existed; nothing to close.

### Completion Notes List

- **Scope delivered:** one new Terraform module (`infra/terraform/modules/bedrock-guardrail/`) with `aws_bedrock_guardrail` + `aws_bedrock_guardrail_version` + page-level `aws_cloudwatch_metric_alarm`, wired into the root stack behind `count = var.environment == "prod" ? 1 : 0`.
- **IAM tightening:** ECS module's `bedrock_guardrail_arn` (scalar) widened to `bedrock_guardrail_arns` (list) — necessary to satisfy AC #5 (grant `bedrock:ApplyGuardrail` on **both** the DRAFT and versioned ARNs). The `BedrockApplyGuardrail` statement now targets concrete ARNs; the account-wide wildcard is gone.
- **Wildcard defaults removed:** `infra/terraform/variables.tf` no longer declares `bedrock_guardrail_arn`; `modules/ecs/variables.tf` declares the renamed list variable with no default (missing wiring fails plan-time instead of silently wildcarding).
- **Prod-only gating:** dev/staging skip the module (zero chat traffic there). The ECS IAM policy document is still guarded by `length(var.bedrock_invocation_arns) > 0`, so dev/staging — which have neither `bedrock_invocation_arns` nor a Guardrail module — never touch the `BedrockApplyGuardrail` statement and do not require a Guardrail ARN to plan successfully.
- **Metric name correction:** the story proposed `GuardrailInvocationIntervenedCount`; the canonical Bedrock Guardrails CloudWatch metric is `InvocationsIntervened` in namespace `AWS/Bedrock`. The alarm uses the canonical name; the operator should eyeball the first real `InvocationsIntervened` data points post-apply to confirm emission.
- **Grounding threshold 0.85, warn alarm deferred:** initial floor per architecture.md L1705 — Story 10.6a owns re-tuning. The ≥5% sustained-15m warn alarm is explicitly owned by Story 10.9; this story ships only the page-level (≥15% sustained 5m × 3) alarm.
- **tfsec clean.** No new findings on the Guardrail module; no waiver added.
- **What's not included (by design):** no backend code, no Alembic migration, no frontend, no CI plan-step, no `terraform apply`. Apply is an explicit operator action and is the follow-up task outside this story.

### Code Review Follow-ups (2026-04-24)

Adversarial review (`/bmad-bmm-code-review`) surfaced 3 HIGH + 3 MEDIUM issues; all fixed in the same commit as the review:

- **[HIGH] IBAN regex over-match** — `{1,30}` minimum-length matched short all-caps-plus-digits tokens. Tightened to `{11,30}` so the full IBAN shape (country + check + BBAN ≥ 11 chars) is required before redaction. File: [modules/bedrock-guardrail/main.tf:133](../../infra/terraform/modules/bedrock-guardrail/main.tf#L133).
- **[HIGH] Ukrainian-passport regex `\b` boundary broken for Cyrillic** — Bedrock's regex engine treats `\b` as ASCII; Cyrillic-leading matches silently failed. Replaced with explicit non-letter lookarounds `(?:^|[^А-ЯA-Zа-яa-z0-9])…(?:$|[^А-ЯA-Zа-яa-z0-9])`. File: [modules/bedrock-guardrail/main.tf:140](../../infra/terraform/modules/bedrock-guardrail/main.tf#L140).
- **[HIGH] Prod ships with no page destination** — `observability_sns_topic_arn = ""` means the alarm is console-only. AC #3 permits this but it's a functional gap. Documented explicitly in the module README ("Prod currently runs the alarm in console-only mode … wire a real SNS topic before relying on the alarm for on-call rotation") and owner-linked to Story 10.9. Not auto-fixed (requires real SNS topic decision).
- **[MEDIUM] Versioned ARN silent-freeze trap** — `aws_bedrock_guardrail_version` would not auto-republish on parent edits, so 10.6a's grounding tune would leave pinned consumers on Story 10.2's config indefinitely. Added `lifecycle { replace_triggered_by = [aws_bedrock_guardrail.this] }` and operator note in README.
- **[MEDIUM] Metric-name source URL missing** — added AWS docs URL to Debug Log above.
- **[MEDIUM] `ok_actions` not in AC #3** — dropped; alarm now emits only on breach.

LOW findings (duplicate `env` tag — removed; provider-version verification — recorded in Debug Log) rolled into the same pass. No tech-debt register entries opened (all findings fixed inline).

### File List

**New:**

- `infra/terraform/modules/bedrock-guardrail/main.tf`
- `infra/terraform/modules/bedrock-guardrail/variables.tf`
- `infra/terraform/modules/bedrock-guardrail/outputs.tf`
- `infra/terraform/modules/bedrock-guardrail/README.md`

**Modified:**

- `infra/terraform/main.tf` — added `module "bedrock_guardrail"` (prod-only `count` gate); rewired `module.ecs.bedrock_guardrail_arns` via `try(..., [])`.
- `infra/terraform/variables.tf` — removed `variable "bedrock_guardrail_arn"` (no longer externally supplied).
- `infra/terraform/modules/ecs/variables.tf` — renamed `bedrock_guardrail_arn` (string) → `bedrock_guardrail_arns` (list); dropped wildcard default; updated comment.
- `infra/terraform/modules/ecs/main.tf` — `BedrockApplyGuardrail` statement's `resources` now points at the list variable (both unversioned + versioned ARNs); removed wildcard reference.
- `infra/terraform/environments/prod/terraform.tfvars` — replaced the stale L52-L54 wildcard-placeholder comment block with the module-owned note.
- `VERSION` — bumped 1.41.0 → 1.42.0 (MINOR; new user-facing safety layer provisioned in prod).

## Change Log

| Date | Change |
|------|--------|
| 2026-04-24 | Story 10.2 implemented: new `bedrock-guardrail` Terraform module (Guardrail + version + page-level block-rate alarm), root-stack wiring (prod-only), ECS IAM tightening (scalar wildcard → concrete list of ARNs), prod tfvars comment cleanup. tfsec clean; `terraform validate` green. |
| 2026-04-24 | Version bumped 1.41.0 → 1.42.0 per story completion (MINOR — new user-facing safety layer in prod). |
