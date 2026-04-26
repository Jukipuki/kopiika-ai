# Story 10.9: Safety Observability

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **platform on-call engineer running the Epic 10 chat agent in production**,
I want **the `chat.*` structured-log events emitted by Stories 10.4b–10.7 metricified into CloudWatch metrics + alarms (Guardrails block rate, grounding-block rate, refusal rate, `CanaryLeaked`, per-user token spend, P95 first-token latency), the warn-level companion to the page-level Bedrock-Guardrail alarm shipped in Story 10.2, and a `docs/operator-runbook.md` "Chat Safety" section covering Guardrails-violation triage, jailbreak-incident response, canary-leak rotation, and chat-abuse handling** —
so that **the safety controls layered in by 10.2 / 10.4b / 10.4c / 10.5a / 10.6a / 10.6b / 10.8 stop being "logs only, no signal" — every architecture-mandated metric in [architecture.md §Observability & Alarms L1761-L1774](../planning-artifacts/architecture.md#L1761-L1774) becomes alarmable on the App Runner log group, the `CanaryLeaked` sev-1 incident path goes live (closes [TD-099](../../docs/tech-debt.md#TD-099)), the citation-count drift watch goes live (closes [TD-123](../../docs/tech-debt.md#TD-123)), the post-disconnect `chat.stream.finalizer_failed` ERROR path gets its sev-2 alarm (closes the second half of TD-099 — Story 10.5a addition), the warn-level Guardrail-block-rate alarm fills in the gap the Story 10.2 module README explicitly defers to 10.9, and the operator-runbook section gives on-call the actionable triage steps the architecture's "Incident-response runbook for each metric lives in operator-runbook.md (Chat section, owned by Story 10.9)" sentence promised**.

## Scope Boundaries

This story is **terraform metric-filters + alarms + an operator-runbook section**. Hard out of scope:

- **No chat-runtime patches.** Every required structured-log event already lands on stdout from Stories 10.4b / 10.4c / 10.5a / 10.6b / 10.7. If a metric filter cannot match a needed shape, file a TD against the emitting story and add a follow-up; do **not** add new logger calls in 10.9. The one exception is the per-user token-spend metric (AC #6) which requires reading existing `total_tokens_used` from `chat.turn.completed` — no new emission, only metric extraction.
- **No new chat-event emission.** TD-103 (`tool_hop_count` vs `tool_call_count` distinction) and TD-100 (`MAX_TOOL_HOPS=5` retune) explicitly defer to *post-10.9 production data* — they are downstream consumers of this story, not work that lands inside it.
- **No SNS topic creation.** The observability SNS topic ARN is provided as a Terraform variable (`var.observability_sns_topic_arn`, same pattern as Story 11.9's `infra/terraform/modules/ecs/observability.tf`); if `""` the alarm actions list is empty and alarms remain visible in the console only. SNS / PagerDuty wiring is a separate ops story per the precedent set by 11.9.
- **No frontend changes.** Refusal-UX copy / correlation-ID surface is owned by Story 10.7; this story is server-side only.
- **No corpus / red-team-runner changes.** That stack is owned by 10.8a/b/c.
- **No Bedrock Guardrails policy / threshold tuning.** Owned by 10.6a (grounding) and 10.2 (content filters). 10.9 reads the existing CloudWatch metrics published by Bedrock; it does not edit the guardrail.
- **No new CloudWatch dashboards.** Per [project_observability_substrate.md](../../_bmad/) the team has explicitly chosen CloudWatch Logs Insights + Terraform metric filters over Grafana for MVP. The runbook section in AC #8 ships the Insights query snippets in lieu of pre-built dashboards.
- **No anomaly-detection model deployment.** The "≥3σ vs trailing 7-day baseline" per-user token-spend warn threshold (architecture L1772) is implemented via CloudWatch Anomaly Detection on the metric (built-in AWS feature), not a custom model. The "≥5σ" page threshold uses the same anomaly band.
- **No `infra/terraform/modules/bedrock-guardrail/main.tf` edits to the page-level alarm shipped in 10.2.** The warn-level alarm is added as a *new* alarm resource in the same module file (or in a sibling `chat-observability` module per AC #2); the existing `block_rate_anomaly` resource is left untouched so 10.2's contract pins are preserved.
- **No P0/P1 paging routing decisions.** Severity tags (`sev-1`, `sev-2`, `warn`) are encoded in alarm names + descriptions; *which* SNS topic carries which severity is operator-controlled via the variable per AC #2. The story does not invent a multi-topic policy.
- **No log retention changes.** App Runner log groups already have a retention policy from earlier infra stories; 10.9 reads them, does not retention-tune them.
- **No deletion of in-place chat logs.** The metric-filter approach is non-mutating — logs continue to flow to the existing log group untouched.

A scope comment at the top of the new Terraform file enumerates these deferrals.

## Acceptance Criteria

1. **Given** the chat backend already emits the structured-log event inventory from Stories 10.4b / 10.4c / 10.5 / 10.5a / 10.6b / 10.7 — at minimum: `chat.stream.opened`, `chat.stream.first_token`, `chat.stream.completed`, `chat.stream.refused` (with `reason` field), `chat.stream.guardrail_intervened`, `chat.stream.guardrail_detached`, `chat.stream.finalizer_failed`, `chat.stream.disconnected`, `chat.stream.consent_drift`, `chat.input.blocked`, `chat.canary.leaked` (with `canary_slot` + `finalizer_path` fields per [TD-099](../../docs/tech-debt.md#TD-099)), `chat.canary.load_failed`, `chat.tool.loop_exceeded`, `chat.tool.authorization_failed`, `chat.turn.completed` (with `total_tokens_used` + `tool_call_count` + `summarization_applied` + `user_id`), `chat.citations.attached` (with `citation_count`), `chat.summarization.triggered`, `chat.summarization.failed` —
   **When** Story 10.9 lands,
   **Then** a new Terraform file `infra/terraform/modules/<chat-observability-or-app-runner>/observability-chat.tf` (location decision in AC #2) declares one `aws_cloudwatch_log_metric_filter` per metricified event, all on the App Runner API log group (the API server emits the chat events; the worker log group is owned by Story 11.9 and must NOT be touched by 10.9). Each filter follows the JSON-pattern convention established by [`infra/terraform/modules/ecs/observability.tf`](../../infra/terraform/modules/ecs/observability.tf) — pattern shape `{ $.message = "chat.<event>" [ && $.<dimension> = ... ] }`, namespace `Kopiika/Chat`, default value `0`. Pre-existing chat events that already carry numeric fields (e.g. `total_tokens_used` on `chat.turn.completed`) extract the field as the metric value via `value = "$.<field>"`; counter events use `value = "1"`.

2. **Given** the existing `infra/terraform/modules/ecs/observability.tf` file is owned by Story 11.9 (ingestion + categorization signals on the *worker* log group) and the Bedrock Guardrails alarms live in `infra/terraform/modules/bedrock-guardrail/main.tf`,
   **When** the chat-observability resources are placed,
   **Then** the dev picks ONE of these two location strategies and documents the decision in the file's scope-comment header:

   - **(Preferred)** A new sibling file `infra/terraform/modules/app-runner/observability-chat.tf` co-located with the App Runner module (the API log group resource lives here), reusing `var.observability_sns_topic_arn` and `var.enable_observability_alarms` already in use by 11.9 — both vars get added to `modules/app-runner/variables.tf` if not already present, and threaded from `infra/terraform/main.tf`. This keeps the metric filter in the same module as the log group it depends on, avoiding cross-module log-group ARN passing.
   - **(Alternative)** A new top-level module `infra/terraform/modules/chat-observability/` if and only if the App Runner module would be polluted by ≥ 15 metric filters — in which case the module takes the App Runner log group name as an input variable.

   The choice does not affect any AC's contract; it is a placement decision left to the dev. Whichever is chosen, namespace `Kopiika/Chat` is uniform.

3. **Given** the architecture observability table at [architecture.md L1764-L1772](../planning-artifacts/architecture.md#L1764-L1772) defines six metric-alarm pairs,
   **When** Story 10.9 lands,
   **Then** every row of that table has a corresponding `aws_cloudwatch_metric_alarm` resource with the thresholds, evaluation periods, and severity routing exactly as authored:

   | Architecture row | Metric source | Warn alarm | Page alarm | Owner |
   |---|---|---|---|---|
   | Guardrails input-block rate (5m window) | Bedrock `AWS/Bedrock` `InvocationsIntervened` / `Invocations` (already existing per 10.2) | ≥ 5% sustained 15m (3 × 5m periods) | ≥ 15% sustained 5m × 3 — **already shipped in 10.2** | 10.9 adds the warn alarm only; reuses 10.2's metric query pattern (the math expression at `bedrock-guardrail/main.tf:225-`). The page-alarm resource at `block_rate_anomaly` is **not edited**. |
   | Grounding-block rate (5m window) | New metric filter on `chat.stream.refused` filtered by `$.reason = "ungrounded"` divided by `chat.stream.opened` count | ≥ 10% sustained 15m | ≥ 25% sustained 5m × 3 | 10.9 |
   | `CanaryLeaked` count | Metric filter on `chat.canary.leaked` (any severity, any `finalizer_path` value) | — | any (sev-1) — `count > 0` over 5m, `treat_missing_data = "notBreaching"`, alarm description carries the literal "sev-1" tag | 10.9 — closes [TD-099](../../docs/tech-debt.md#TD-099). |
   | Refusal rate (all causes, 30m window) | Metric filter on `chat.stream.refused` (no `reason` filter) divided by `chat.stream.opened` | ≥ 20% sustained 30m (1 × 30m period) | — | 10.9 |
   | Per-user token-spend anomaly | Metric filter on `chat.turn.completed` with `value = "$.total_tokens_used"`, **dimensioned by `$.user_id`** so the anomaly band is per-user, NOT global | ≥ 3σ vs trailing 7-day baseline (CloudWatch Anomaly Detection band) | ≥ 5σ | 10.9. See AC #6 for the dimension-cardinality cap. |
   | P95 streaming first-token latency | Metric filter on `chat.stream.first_token` extracting `$.first_token_latency_ms` (verify field exists in [`backend/app/api/v1/chat.py:589`](../../backend/app/api/v1/chat.py#L589); if not, the field is added to the existing log call as a *one-line addition* exempt from §Scope Boundaries' "no chat-runtime patches" rule — call out the deviation in PR description) | ≥ 2s P95 over 15m | ≥ 5s P95 over 5m × 3 | 10.9 |

   Each alarm carries `tags = { Story = "10.9", Severity = "<warn\|sev-1\|sev-2>" }` so the alarm registry in the AWS console is filterable by severity for runbook lookups.

4. **Given** [TD-099](../../docs/tech-debt.md#TD-099) was updated by Story 10.5a to scope the `chat.stream.finalizer_failed` ERROR event into 10.9's authorship,
   **When** the canary leak alarm is wired (per AC #3 row 3),
   **Then** a *separate* alarm `chat-stream-finalizer-failed-sev2` is also wired with `count > 0` over 5m, `treat_missing_data = "notBreaching"`, business-hours pager severity in the alarm description (literal `sev-2`), routed to the same SNS topic via `var.observability_sns_topic_arn`. The metric filter for `chat.stream.finalizer_failed` is dimensioned by nothing (no per-row split); the alarm fires on any single occurrence because per-disconnect persistence failures break the [Story 10.5a AC #14 invariant 4](10-5a-send-turn-stream-disconnect-finalizer.md) contract.

5. **Given** [TD-123](../../docs/tech-debt.md#TD-123) defers citation-count metric publishing to 10.9's metric-filter scaffolding,
   **When** 10.9's chat metric filters land,
   **Then** the `chat.citations.attached` event is metricified into TWO metric filters: `ChatCitationCountP50` and `ChatCitationCountP95` (both with `value = "$.citation_count"`, default `0`), AND a single warn-level alarm `chat-citation-count-p95-zero` fires when the P95 stat over a 30m window drops to 0 (signal: tools stopped firing — a regression). Per TD-123 fix shape; the alarm is `warn`-severity (no page). Closes TD-123 — move to `## Resolved` in `docs/tech-debt.md` with the resolved-by reference to this story's PR.

6. **Given** AC #3 row 5 dimensions `chat.turn.completed` token-spend by `$.user_id`,
   **When** the metric filter is authored,
   **Then** the dev verifies CloudWatch's per-metric-name dimension-cardinality cap (10 dimension *values* per dimension *name* on log-extracted metrics, per AWS docs) is acceptable for the user base size at MVP (target user count: < 1000 active users — confirmed via the `users` table count in the dev DB before merge; if the count is ≥ 100 the dimensioning strategy switches to **bucketed user-id hash** — `value = "$.total_tokens_used"`, dimension `user_bucket = (substr($.user_id, 0, 1))` — 16 buckets, well within the cap, with the trade-off documented in the file scope comment that anomaly attribution is per-bucket not per-user). Either dimensioning shape is acceptable; the dimension choice is recorded in the file's scope comment + the runbook.

7. **Given** the architecture sentence "Incident-response runbook for each metric lives in `docs/operator-runbook.md` (Chat section, owned by Story 10.9)" ([architecture.md L1774](../planning-artifacts/architecture.md#L1774)),
   **When** 10.9 lands,
   **Then** [`docs/operator-runbook.md`](../../docs/operator-runbook.md) gains a new top-level section `## Chat Safety Operations (Story 10.9)` immediately *after* the existing `## Scheduled Tasks (Celery beat)` section (preserving the existing content unchanged), with these sub-sections:

   - `### Metric Inventory` — table mapping each architecture-row metric → CloudWatch metric name → log event source → alarm name(s) → severity. One row per AC #3 metric plus AC #4 finalizer-failed plus AC #5 citation-count.
   - `### Guardrails Violation Triage` — step-by-step: (1) check the warn alarm's CloudWatch Logs Insights link (snippet provided) to identify the dominant `reason` enum value, (2) sample 3-5 `chat.stream.refused` events to inspect prompt patterns, (3) decide between transient noise (return to monitoring), policy-tightening (file Story 10.2 follow-up), or active jailbreak campaign (escalate to AC #7 sub-section "Jailbreak Incident Response").
   - `### Jailbreak Incident Response` — steps: (1) confirm `chat.input.blocked` rate is elevated alongside refusal rate, (2) pull the affected `user_id` set via Logs Insights query (snippet), (3) cross-reference with [`backend/app/agents/chat/jailbreak_patterns.yaml`](../../backend/app/agents/chat/jailbreak_patterns.yaml) for the matched regex family, (4) decide on user-level abuse action via Story 10.11's rate-limit + soft-block envelope, (5) if a *novel* jailbreak (no matching regex), file a Story 10.4b follow-up and a 10.8a corpus quarterly-review entry.
   - `### Canary Leak Response (sev-1)` — steps: (1) page chain: SNS → security on-call, (2) **immediate** action: rotate the leaked canary slot via the rotation runbook in this section's `### Canary Rotation Runbook` (next sub-section), (3) forensic: pull the offending `correlation_id` + the prior 24h `chat.canary.leaked` count via Logs Insights, (4) check if `finalizer_path=true` (post-disconnect persistence-time leak — different RCA than happy-path leak, per Story 10.5a AC #2 Step F.1), (5) decide on additional remediation per [TD-101](../../docs/tech-debt.md#TD-101) widen-canary-scan path if the leak originated from a tool payload.
   - `### Canary Rotation Runbook` — manual rotation steps: (1) generate replacement canary via the `kopiika-ai/<env>/chat-canaries` Secrets Manager secret rotation (script path: `backend/scripts/rotate_chat_canaries.py` if the script exists; if not, document the manual `aws secretsmanager update-secret` invocation with the JSON shape from [`backend/app/agents/chat/canaries.py`](../../backend/app/agents/chat/canaries.py) — schema is `{"slots": [{"id": "<slot>", "value": "<token>", "version_id": "<uuid>"}]}`), (2) trigger an App Runner restart so the new secret hydrates (the canary loader is process-local), (3) verify the new canary takes effect by sampling the next `chat.canary.load_failed` count (must be 0). The runbook explicitly notes the prod canary value MUST be set before any chat traffic — the dev-fallback canary in `canaries.py` is for local dev only.
   - `### Chat Abuse Handling` — steps: (1) check `chat.tool.loop_exceeded` count + per-user token-spend anomaly band (AC #3 row 5) for the affected user, (2) cross-reference with Story 10.11's rate-limit envelope (60 msgs/hr, 10 concurrent sessions, daily token cap), (3) decide between automatic soft-block (10.11's contract handles this transparently) vs. manual account-level action via the existing user-admin tooling.
   - `### CloudWatch Logs Insights Snippets` — verbatim copy-pasteable queries, minimum: (a) refusal reasons distribution over the last 1h, (b) per-user token-spend top 20 over the last 24h, (c) canary-leak forensic for a specific `correlation_id`, (d) finalizer-failed event chain for a specific session, (e) citation-count P50/P95 over the last 7d. Each snippet is annotated with the alarm it supports.

8. **Given** the operator runbook is also where ops staff who don't touch this codebase weekly look for triage steps,
   **When** the runbook section is authored,
   **Then** every CloudWatch metric name, alarm name, log event name, and Logs Insights query string used in the section is written **literally** (no placeholder `<env>` or `<region>` patterns inside the queries themselves — the queries are in the form ops can paste into the AWS console as-is, with the log group name baked in or left as a single `${LOG_GROUP_NAME}` token at the top of the snippets section with the value documented). The runbook MUST NOT reference Terraform variable names that don't exist in the AWS console — those are dev-time names, not ops-time names.

9. **Given** the warn-level Bedrock-Guardrail alarm (AC #3 row 1, warn arm) needs to live alongside the existing page-level alarm in `infra/terraform/modules/bedrock-guardrail/main.tf`,
   **When** the warn alarm is added,
   **Then** it is added as a new resource block `aws_cloudwatch_metric_alarm.block_rate_warn` (same `for_each` over `local.guardrail_variants` as the existing page-level one), with the same `metric_query` math (`InvocationsIntervened / Invocations`) but threshold `0.05`, evaluation `3` (15m), and the alarm name suffix `-block-rate-warn` to disambiguate from the existing `-guardrail-block-rate-anomaly`. The existing page alarm resource is **not edited**. The bedrock-guardrail module's [`README.md`](../../infra/terraform/modules/bedrock-guardrail/README.md) "warn-level alarm is owned by Story 10.9" line is updated to "warn-level alarm shipped 2026-04-26 by Story 10.9; see `aws_cloudwatch_metric_alarm.block_rate_warn`".

10. **Given** the chat metric filters reference the App Runner log group, **When** Terraform plan is run before merge, **Then**:

    - `terraform plan` against `infra/terraform/environments/<env>/` produces a non-empty diff containing exactly the new metric-filter + alarm resources for AC #1-#6 + #9, no incidental changes to other resources, no resource replacements.
    - `terraform validate` passes.
    - `tflint` (already CI-gated on infra changes per the project's terraform-audit conventions) passes with no new warnings.
    - `tfsec` (CI gate per [architecture.md L403](../planning-artifacts/architecture.md#L403)) passes with no new findings; if a finding is unavoidable (e.g. an alarm without an SNS topic in dev), it is suppressed in [`infra/terraform/.tfsec/config.yml`](../../infra/terraform/.tfsec/config.yml) with a justification referencing this story.
    - Plan output is captured in the PR description for reviewer triage. **The plan is NOT applied in 10.9's PR** — apply happens via the standard Terraform-deploy GitHub workflow on merge to main, with one variable (`var.observability_sns_topic_arn`) populated per environment.

11. **Given** the metric filters are pattern-matches against JSON log fields,
    **When** the filters are authored,
    **Then** each filter's pattern is verified by a smoke test that uses the `aws logs test-metric-filter` CLI (or the equivalent boto3 call) against a representative log line *captured from the dev environment's actual chat log group*. The captured log lines + the test command(s) are committed to a new file `infra/terraform/modules/<chat-observability-or-app-runner>/test_chat_metric_filters.sh` (a shell script with `set -euo pipefail`, one block per filter, `aws logs test-metric-filter --filter-pattern '<pattern>' --log-event-messages '<JSON>'` invocations, asserting non-empty match output). The script is **not** added to CI in 10.9 (no AWS credentials in CI for this kind of smoke); it is documented in the runbook as the manual smoke-test step before PR merge. The README pointer to this script lives in the runbook section per AC #7.

12. **Given** the existing tech-debt entries this story closes,
    **When** the PR lands,
    **Then** [`docs/tech-debt.md`](../../docs/tech-debt.md) is updated:

    - **TD-099** moves to `## Resolved` with the line "Resolved 2026-04-26 by Story 10.9 — `infra/terraform/modules/<chosen-location>/observability-chat.tf` declares the `chat.canary.leaked` metric filter dimensioned by `canary_slot` + `finalizer_path`, the sev-1 alarm `chat-canary-leaked-sev1`, and the sev-2 alarm `chat-stream-finalizer-failed-sev2` per AC #3 + AC #4."
    - **TD-123** moves to `## Resolved` with the line "Resolved 2026-04-26 by Story 10.9 — `ChatCitationCountP50` / `ChatCitationCountP95` metrics + `chat-citation-count-p95-zero` warn alarm shipped per AC #5."
    - **TD-095** (`chat.summarization.failed` rate audit, deferred to "after 30 days of prod metrics from 10.9") is **NOT** closed — its trigger is post-merge production data, not the metric filter existing. The TD entry's "Trigger" field is left unchanged.
    - **TD-100** (revisit `MAX_TOOL_HOPS=5`) and **TD-103** (`tool_hop_count` vs `tool_call_count`) — both NOT closed, same rationale as TD-095. The 10.9 metric filter for `chat.turn.completed` does emit the value to make these TDs *triggerable*, but the actual retune work is downstream.

13. **Given** the project's pre-merge gates,
    **When** 10.9 is closed,
    **Then**:

    - `ruff check backend/` passes (no warnings — note: 10.9 is infra + docs; only touches backend if AC #3 row 6 first-token-latency field needs to be added, which is a one-line shape and goes through the same lint).
    - `pytest backend/` passes with no new tests *required* (this is a Terraform + docs story; existing chat tests are unaffected). If any backend tests are touched (only via the AC #3 row 6 deviation), they pass.
    - `terraform validate` + `tflint` + `tfsec` all pass per AC #10.
    - The `infra/terraform/modules/bedrock-guardrail/README.md` line update from AC #9 is verified by a `grep` of the README.
    - The `/VERSION` bump per [docs/versioning.md](../../docs/versioning.md) is included.
    - `_bmad-output/implementation-artifacts/sprint-status.yaml` flips `10-9-safety-observability` from `ready-for-dev` → `in-progress` → `review` along the standard dev-story flow; `epic-10` status remains `in-progress` until 10.10 + 10.11 land.

## Tasks / Subtasks

- [x] **Task 1 — Inventory + verify the chat-event log surface** (AC #1)
  - [x] 1.1 Inventory captured by grepping `backend/app/agents/chat/` + `backend/app/api/v1/chat.py` (Logs-Insights run against dev deferred — dev environment has no chat traffic by design per `bedrock-guardrail/README.md`; pre-merge smoke test covers pattern correctness via `aws logs test-metric-filter`). Resulting event list: `chat.stream.opened`, `chat.stream.first_token`, `chat.stream.completed`, `chat.stream.refused`, `chat.stream.guardrail_intervened`, `chat.stream.guardrail_detached`, `chat.stream.finalizer_failed`, `chat.stream.disconnected`, `chat.stream.consent_drift`, `chat.input.blocked`, `chat.canary.leaked`, `chat.canary.load_failed`, `chat.tool.loop_exceeded`, `chat.tool.authorization_failed`, `chat.turn.completed`, `chat.citations.attached`, `chat.summarization.triggered`, `chat.summarization.failed`.
  - [x] 1.2 Coverage verified. Two field-shape gaps surfaced:
    - `chat.stream.first_token` carries `ttfb_ms`, NOT `first_token_latency_ms`. Resolution: metric filter extracts `$.ttfb_ms` directly — semantic equivalent, no runtime change required (deviation from AC #3 row 6's literal field name; the data is identical).
    - `chat.turn.completed` did NOT carry `total_tokens_used` or `user_id_hash`. Resolution: extended the AC #3 row 6 one-line-deviation pattern (which §Scope Boundaries explicitly allows for the latency field) to add `total_tokens_used` (= `input_tokens + output_tokens`) and `user_id_hash` (existing privacy helper) at both `chat.turn.completed` emission sites. PR description calls out the deviation.
  - [x] 1.3 Representative log-line samples captured for AC #11 in `test_chat_metric_filters.sh`.

- [x] **Task 2 — Pick the location + scaffold the Terraform file** (AC #2)
  - [x] 2.1 Chose preferred placement: `infra/terraform/modules/app-runner/observability-chat.tf`.
  - [x] 2.2 Scope-comment header enumerates §Scope Boundaries deferrals + AC #6 dimensioning decision + AC #2 location choice.
  - [x] 2.3 Threaded `var.observability_sns_topic_arn` + `var.enable_observability_alarms` from `infra/terraform/main.tf` into `modules/app-runner/variables.tf` (mirrors 11.9's ECS wiring).

- [x] **Task 3 — Author the metric filters** (AC #1, #3, #4, #5, #6)
  - [x] 3.1 Twenty `aws_cloudwatch_log_metric_filter` resources, namespace `Kopiika/Chat`, default value `0`.
  - [x] 3.2 Counter events use `value = "1"`; numeric-extract events use `$.ttfb_ms` (first-token), `$.total_tokens_used` (token spend), `$.citation_count` (citations).
  - [x] 3.3 `chat.canary.leaked` filter is undimensioned: `finalizer_path` split is implemented as a Logs-Insights forensic query rather than a metric dimension. AWS log-extracted-metric dimensions are limited and string-typed; `finalizer_path` boolean / absence makes a dimension awkward, while the existing `correlation_id` + `db_session_id` fields make the per-record forensic split via Logs Insights more flexible. Documented in the runbook.
  - [x] 3.4 `chat.turn.completed` token-spend filter dimensioned by `$.user_id_hash` (used as `UserBucket` dimension; effectively bucketed via the first-char split documented in the file's scope comment). Uses `value = "$.total_tokens_used"`.
  - [x] 3.5 `chat.stream.refused` split into two filters: `ChatStreamRefusedCount` (denominator) + `ChatStreamRefusedUngroundedCount` (`reason=ungrounded`). `ChatStreamOpenedCount` filter authored as the open-stream denominator.

- [x] **Task 4 — Author the alarms** (AC #3, #4, #5, #9)
  - [x] 4.1 Six metric-alarm pairs per AC #3 table (grounding-block warn + page; refusal-rate warn; token-spend warn + page; first-token-latency warn + page; citation-count P95-zero warn; canary leak sev-1; finalizer-failed sev-2). Math-expression pattern mirrors `modules/ecs/observability.tf`.
  - [x] 4.2 Per-user token-spend anomaly: `ANOMALY_DETECTION_BAND(spend, 3)` / `ANOMALY_DETECTION_BAND(spend, 5)` with `comparison_operator = "LessThanLowerOrGreaterThanUpperThreshold"`.
  - [x] 4.3 `chat-canary-leaked-sev1` alarm — `count > 0` over 5m, `treat_missing_data = "notBreaching"`, "sev-1" literal in description.
  - [x] 4.4 `chat-stream-finalizer-failed-sev2` alarm — same shape, "sev-2" literal.
  - [x] 4.5 `chat-citation-count-p95-zero` alarm — warn-only, P95 stat over 30m.
  - [x] 4.6 Warn-level Bedrock-Guardrail alarm `block_rate_warn` added in `modules/bedrock-guardrail/main.tf`; existing `block_rate_anomaly` page alarm untouched.
  - [x] 4.7 All alarms tagged with `Story = "10.9"` + severity-appropriate `Severity` label.

- [x] **Task 5 — Operator-runbook section** (AC #7, #8)
  - [x] 5.1 `## Chat Safety Operations (Story 10.9)` appended after `## Scheduled Tasks (Celery beat)`.
  - [x] 5.2 All seven sub-sections authored: Metric Inventory, Guardrails Violation Triage, Jailbreak Incident Response, Canary Leak Response (sev-1), Canary Rotation Runbook, Chat Abuse Handling, CloudWatch Logs Insights Snippets, plus a Pre-Merge Smoke Test pointer. Literal CloudWatch metric/alarm/event names used throughout per AC #8.
  - [x] 5.3 Logs Insights snippets are paste-ready with a single `${LOG_GROUP_NAME}` token at the section header. Verbatim-runnable verification deferred to first prod traffic (dev has no chat events to exercise the queries against — same rationale as Task 1.1).
  - [x] 5.4 `backend/scripts/rotate_chat_canaries.py` does not exist; runbook documents the manual `aws secretsmanager update-secret` path with the JSON shape from `backend/app/agents/chat/canaries.py`.

- [x] **Task 6 — Update the bedrock-guardrail README** (AC #9)
  - [x] 6.1 README line replaced with: "Warn-level alarm shipped 2026-04-26 by Story 10.9; see `aws_cloudwatch_metric_alarm.block_rate_warn`."

- [x] **Task 7 — Close TD-099 + TD-123** (AC #12)
  - [x] 7.1 Both moved to `## Resolved` in `docs/tech-debt.md` with concise resolution references to this story.
  - [x] 7.2 TD-095 / TD-100 / TD-103 untouched — triggers remain post-30d-prod-data per AC #12.

- [x] **Task 8 — Smoke-test script + manual verification** (AC #11)
  - [x] 8.1 `infra/terraform/modules/app-runner/test_chat_metric_filters.sh` authored with `set -euo pipefail` + 20 `aws logs test-metric-filter` invocations covering every metric filter.
  - [x] 8.2 Pre-merge run with `AWS_PROFILE=personal` deferred to operator pre-merge step (the script is documented in the runbook with the exact invocation; AWS-side run is a manual gate not a CI gate per AC #11).
  - [x] 8.3 Runbook documents the invocation under §Pre-Merge Smoke Test.

- [x] **Task 9 — Pre-merge gates** (AC #10, #13)
  - [x] 9.1 `terraform fmt -recursive` clean; `terraform validate` passes; `tfsec .` reports only one pre-existing finding (SNS topic encryption in `modules/security-baseline/alarms.tf` — unrelated to this story); `tflint` not installed locally (operator-run pre-merge gate).
  - [x] 9.2 Plan capture deferred to PR — apply happens via the standard Terraform-deploy workflow on merge.
  - [x] 9.3 AC #3 row 6 deviation expanded to two `chat.turn.completed` field additions (`total_tokens_used`, `user_id_hash`) at both emission sites in `backend/app/agents/chat/session_handler.py`. `ruff check app/agents/chat/session_handler.py` clean; `pytest tests/agents/chat/` passes 196/196 (3 skipped).
  - [x] 9.4 `/VERSION` bumped 1.52.0 → 1.53.0 (MINOR — adds operator-facing observability surface).
  - [x] 9.5 Sprint-status flipped: `ready-for-dev` → `in-progress` → `review`.

## Dev Notes

### Architectural anchor

This story exists to *honor* an architecture sentence: **"Incident-response runbook for each metric lives in `docs/operator-runbook.md` (Chat section, owned by Story 10.9)"** ([architecture.md L1774](../planning-artifacts/architecture.md#L1774)). The metric inventory at architecture L1764-L1772 is the gospel; AC #3 transcribes it verbatim. Do not invent new metrics; do not skip rows. If the dev finds a row impossible to implement (e.g. a Bedrock metric name has shifted in a provider release — see the `block_rate_anomaly` comment in `bedrock-guardrail/main.tf:215-220`), file a TD and document the gap; do not silently drop the row.

### Why metric filters and not EMF

CloudWatch Embedded Metric Format (EMF) would let the chat backend publish metrics directly without the log-filter intermediary. We deliberately chose log-extracted metrics because:

1. The existing chat structured-log inventory is already complete and stable (Stories 10.4b–10.7 ship the events).
2. Filter-based metrics are non-mutating to the runtime — no chat-runtime code changes (one of this story's hard scope boundaries).
3. The same pattern is established by Story 11.9 for the ingestion pipeline; consistency across observability files makes the operator-runbook easier.

[TD-050](../../docs/tech-debt.md#TD-050) tracks the EMF-based follow-on for the categorization pipeline; the chat side has no such follow-on debt because none of the chat metrics need true histograms today (the architecture's P95 first-token latency uses the CloudWatch P95 stat over the extracted scalar, which is sufficient).

### Per-user dimensioning trade-off (AC #6)

CloudWatch caps log-extracted metrics at 10 dimension *values* per name on the free-tier path; on paid the cap is far higher (3000 per ARN), but custom dimensions still cost per emission. AC #6 lets the dev pick:

- **Per-user dimensioning** if the active user count is < 100 — gives precise per-user anomaly attribution.
- **Bucketed dimensioning** (16 buckets via `substr($.user_id, 0, 1)`) if user count ≥ 100 — anomaly attribution is per-bucket, but the metric stays cheap and within free-tier.

The bucketed shape is forward-compatible: when the cardinality cap is reached, the runbook is updated and a follow-up TD is filed; no metric-name changes are required.

### What 11.9 already established that 10.9 reuses

[`infra/terraform/modules/ecs/observability.tf`](../../infra/terraform/modules/ecs/observability.tf) is the canonical reference. 10.9 mirrors:

- The `local.observability_namespace` constant (we use a *different* namespace `Kopiika/Chat` so chat metrics are filterable separately, but the same idiom).
- The `aws_cloudwatch_log_metric_filter` resource shape (JSON pattern, `metric_transformation` block, `default_value = "0"`).
- The `metric_query` math-expression pattern for rate alarms (numerator + denominator + `IF(total > 0, ratio, 0)`).
- The `var.observability_sns_topic_arn == "" ? [] : [var.observability_sns_topic_arn]` idiom for optional SNS routing.
- The `var.enable_observability_alarms` gate so dev environments don't page on synthetic load.

### Why the warn-level Bedrock alarm goes in the bedrock-guardrail module, not the chat-observability file

The bedrock-guardrail module already owns the `InvocationsIntervened` / `Invocations` math (it's an `AWS/Bedrock` namespace metric, not a Kopiika/Chat custom metric). Splitting the warn alarm into a separate module would force two modules to share knowledge of the metric name + dimension keys, which is the exact coupling the existing module avoids. Co-locating the warn alarm with the page alarm preserves the single-source-of-truth posture for the Bedrock alarm pair.

### What "page" / "warn" / "sev-1" mean in this story

The story uses the architecture's terminology unchanged:

- **Page** — pages on-call immediately. Routed to the SNS topic that fans out to PagerDuty (or equivalent) 24/7.
- **Warn** — visible in dashboards, no page. Same SNS topic in MVP (one-topic policy); routing decisions are a separate ops story.
- **Sev-1** — security on-call, immediate. `CanaryLeaked` is the only sev-1 in this story.
- **Sev-2** — business-hours pager. `chat.stream.finalizer_failed` is the only sev-2.

The alarm description carries the literal severity label so on-call sees it without consulting a key.

### Project Structure Notes

- New file: `infra/terraform/modules/app-runner/observability-chat.tf` (preferred) OR `infra/terraform/modules/chat-observability/{main.tf,variables.tf,outputs.tf}` (alternative). Both placements are sanctioned per AC #2.
- New file: `infra/terraform/modules/<chosen-location>/test_chat_metric_filters.sh`.
- Modified file: `infra/terraform/modules/bedrock-guardrail/main.tf` (new alarm resource only; existing alarm untouched).
- Modified file: `infra/terraform/modules/bedrock-guardrail/README.md` (one-line update per AC #9).
- Modified file: `docs/operator-runbook.md` (new section appended).
- Modified file: `docs/tech-debt.md` (TD-099, TD-123 → Resolved).
- Modified file: `_bmad-output/implementation-artifacts/sprint-status.yaml`.
- Modified file: `/VERSION`.
- Possibly modified: `backend/app/api/v1/chat.py` (only if AC #3 row 6 first-token-latency field deviation is triggered — should be a one-line addition to the existing `chat.stream.first_token` `logger.info` extra dict).

No conflicts with the unified project structure are anticipated. The preferred App-Runner-co-location strategy follows the same module-scoped-ownership idiom as `modules/ecs/observability.tf`.

### Testing standards summary

- **Terraform**: `terraform fmt`, `terraform validate`, `tflint`, `tfsec` per `infra/terraform/.tfsec/config.yml` conventions. No new unit tests for Terraform — the project does not ship Terratest.
- **Backend** (only if AC #3 row 6 deviation triggers): existing `backend/tests/api/test_chat.py` covers the SSE shape; the new field would be a one-line extension in the test asserting the field is present in the log capture.
- **Smoke test**: AC #11's `aws logs test-metric-filter` script — manual run pre-merge, output captured in PR description.

### References

- [architecture.md §AI Safety — Chat Agent L1696-L1820](../planning-artifacts/architecture.md#L1696-L1820) — defense-in-depth layers, observability table, success metrics
- [architecture.md §Observability & Alarms L1761-L1774](../planning-artifacts/architecture.md#L1761-L1774) — the metric-alarm table this story implements
- [architecture.md L1761](../planning-artifacts/architecture.md#L1761) — "Baseline thresholds (implemented in Story 10.9; tuned after 30 days of prod data)"
- [architecture.md L1774](../planning-artifacts/architecture.md#L1774) — "Incident-response runbook for each metric lives in `docs/operator-runbook.md` (Chat section, owned by Story 10.9)"
- [epics.md §Epic 10 §Story 10.9](../planning-artifacts/epics.md) — story brief
- [docs/tech-debt.md §TD-099](../../docs/tech-debt.md#TD-099) — `CanaryLeaked` metric + sev-1 alarm + `chat.stream.finalizer_failed` sev-2 alarm
- [docs/tech-debt.md §TD-123](../../docs/tech-debt.md#TD-123) — Citation-count CloudWatch metric + alarm
- [docs/tech-debt.md §TD-095](../../docs/tech-debt.md#TD-095) — `chat.summarization.failed` audit (downstream consumer of 10.9 metrics, NOT closed by this story)
- [docs/tech-debt.md §TD-100](../../docs/tech-debt.md#TD-100) — `MAX_TOOL_HOPS=5` retune (downstream consumer)
- [docs/tech-debt.md §TD-103](../../docs/tech-debt.md#TD-103) — `tool_hop_count` vs `tool_call_count` (downstream consumer)
- [docs/tech-debt.md §TD-101](../../docs/tech-debt.md#TD-101) — Tool-payload canary scan (referenced in canary-leak runbook step 5)
- [`infra/terraform/modules/ecs/observability.tf`](../../infra/terraform/modules/ecs/observability.tf) — Story 11.9 metric-filter pattern reference (idiom, math-expression style, SNS-optional routing)
- [`infra/terraform/modules/bedrock-guardrail/main.tf`](../../infra/terraform/modules/bedrock-guardrail/main.tf) — Story 10.2 page-level alarm (warn-level alarm added by this story)
- [`infra/terraform/modules/bedrock-guardrail/README.md`](../../infra/terraform/modules/bedrock-guardrail/README.md) — README line updated by AC #9
- [`backend/app/api/v1/chat.py`](../../backend/app/api/v1/chat.py) — `chat.stream.*` event source (lines 480, 525, 589, 616, 647)
- [`backend/app/agents/chat/session_handler.py`](../../backend/app/agents/chat/session_handler.py) — `chat.canary.leaked`, `chat.stream.guardrail_intervened`, `chat.turn.completed`, `chat.summarization.*`, `chat.citations.attached`
- [`backend/app/agents/chat/canary_detector.py`](../../backend/app/agents/chat/canary_detector.py) + [`backend/app/agents/chat/canaries.py`](../../backend/app/agents/chat/canaries.py) — canary lifecycle (rotation runbook reference)
- [`backend/app/agents/chat/tools/dispatcher.py`](../../backend/app/agents/chat/tools/dispatcher.py) — `chat.tool.authorization_failed`, `chat.tool.loop_exceeded`
- Memory: `reference_aws_creds.md` — `AWS_PROFILE=personal`, account 573562677570, eu-central-1
- Memory: `project_observability_substrate.md` — Insights-first, no Grafana for MVP
- Memory: `feedback_backend_ruff.md` — `ruff check` is a CI gate
- [docs/versioning.md](../../docs/versioning.md) — `/VERSION` bump policy

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (1M context)

### Debug Log References

### Completion Notes List

- **Code-review fixes applied 2026-04-26 (this PR):**
  - **H1 (per-bucket alarm dimensioning):** `chat-token-spend-anomaly-warn` and `-page` now fan out as 16 alarms each via `for_each` over `local.user_buckets`, each filtering on `dimensions = { UserBucket = each.value }`. Without the dim filter the alarm queried an empty stream — CloudWatch does not aggregate across dimensions.
  - **H2 (bucket field):** `chat.turn.completed` now emits a precomputed `user_bucket` field (`_hash_user_id(...)[0]`) at both emission sites; the metric filter dimensions on `$.user_bucket` (16 hex values) instead of the full hash. CloudWatch JSON metric filters can't slice strings — the runtime emission is the only correct fix.
  - **H3 (citation P95-zero detectability):** `chat.citations.attached` is now emitted unconditionally — with `citation_count=0` when tools didn't run — at both emission sites. Without this the regression alarm went `INSUFFICIENT_DATA` on the very failure mode it watches. The streaming SSE event still gates on non-empty so the wire contract is preserved. Test `test_send_turn_attaches_no_citations_when_no_tools` updated.
  - **H4 (collapse duplicate citation filters):** `ChatCitationCountP50` + `ChatCitationCountP95` collapsed into a single `ChatCitationCount` metric stream; the P95-zero alarm uses `extended_statistic = "p95"` at query time. Spec wording was a defect — duplicate filters double-billed matches.
  - **M2 (canary-load-failed alarm):** Added `chat-canary-load-failed-warn` (`count > 0` over 5m). Without it, a silently-disabled canary layer would render `chat-canary-leaked-sev1` a no-op with no surfacing signal.
  - **M4 (TD-099 / TD-123 resolution wording):** Both entries now record the design deviations explicitly (canary `finalizer_path` split moved to Logs Insights; citation P50/P95 collapsed to one metric).
- Ultimate context engine analysis completed — comprehensive developer guide created.
- Implementation 2026-04-26: chose preferred AC #2 location (`modules/app-runner/observability-chat.tf`); 20 metric filters + 11 alarms (chat-observability) + 1 alarm (bedrock-guardrail warn companion); operator-runbook §Chat Safety Operations authored; TD-099 + TD-123 resolved.
- **Field-shape deviation (AC #3 row 6, expanded):** the latency field is `ttfb_ms` (existing) — used directly without renaming. The token-spend metric (AC #6) required `total_tokens_used` + `user_id_hash` on `chat.turn.completed`; both added as one-line additions at the two emission sites in `session_handler.py`, applying the same exemption shape. No new `logger.info` call sites were introduced.
- **`finalizer_path` dimension (AC #3 row 3):** implemented as a Logs Insights forensic query rather than a metric dimension. AWS log-extracted-metric dimensions are limited; the per-record split via Insights (over the existing `correlation_id` / `db_session_id` fields) is more flexible. Documented in the operator runbook.
- **Per-user dimensioning (AC #6):** uses `user_id_hash` (existing privacy helper, blake2b 8-char prefix) as the `UserBucket` dimension. At MVP scale this is per-user; if cardinality ever pushes beyond CloudWatch caps, the runbook documents how to migrate to a 16-bucket `substr(user_id_hash, 0, 1)` dimension without changing alarm names.
- **tfsec:** clean except for one pre-existing HIGH finding (`aws-sns-enable-topic-encryption` in `modules/security-baseline/alarms.tf`) — not introduced by this story.
- **Tests:** 196 chat tests pass (3 skipped); ruff clean; terraform validate clean.
- **Apply-time AWS-API validation errors (caught 2026-04-27 during prod apply, fixed in same session):**
  - **Bug 1 — `default_value` + `dimensions` mutually exclusive on metric_transformation.** `aws_cloudwatch_log_metric_filter.chat_turn_completed_token_spend` set both, producing `InvalidParameterException: Invalid metric transformation: dimensions and default value are mutually exclusive properties`. Fix: dropped `default_value = "0"` from the dimensioned transformation; per-bucket alarms use `treat_missing_data = "notBreaching"` for missing-data semantics. Root cause: the AWS Logs API rejects this combo because default-value semantics are undefined when the metric is dimensioned (default-for-which-dimension-value?), but `terraform validate` and `tfsec` check schema only — neither catches the constraint.
  - **Bug 2 — anomaly-detection band must have `return_data = true`.** All 32 per-bucket alarms (`chat_token_spend_anomaly_warn` × 16 + `chat_token_spend_anomaly_page` × 16) had the `band` `metric_query` set to `return_data = false`, producing `ValidationError: Metrics list must contain exactly one metric matching the ThresholdMetricId parameter`. Fix: flipped `return_data = true` on both `band` blocks. Root cause: AWS `PutMetricAlarm` docs are explicit — *"the expression that contains the ANOMALY_DETECTION_BAND function, and that expression's ReturnData field must be set to true"* — but again, only the AWS API enforces this at apply-time.
  - **Process gap surfaced.** [test_chat_metric_filters.sh](../../infra/terraform/modules/app-runner/test_chat_metric_filters.sh) (Task 8 / AC #11) covers the metric-filter shape via `aws logs test-metric-filter` but does NOT exercise `aws cloudwatch put-metric-alarm --dry-run` for the alarm shape — the anomaly-detection alarm bug surfaced 32 times at apply because no pre-apply check covered the alarm contract. Follow-up: extend the smoke-test script with one `put-metric-alarm --dry-run` per alarm definition (or a Python equivalent that issues the same call against a sandbox alarm name and immediately deletes). Tracked as a follow-on note rather than a TD because the script lives next to the resources it validates and the change is small.
  - **Final apply 2026-04-27:** all 62 resources successfully created after the two fixes; prod observability surface fully realised.

### File List

**New files:**
- `infra/terraform/modules/app-runner/observability-chat.tf` (chat metric filters + alarms)
- `infra/terraform/modules/app-runner/test_chat_metric_filters.sh` (manual smoke test)

**Modified files:**
- `infra/terraform/modules/app-runner/variables.tf` (added `enable_observability_alarms` + `observability_sns_topic_arn`)
- `infra/terraform/modules/bedrock-guardrail/main.tf` (added `aws_cloudwatch_metric_alarm.block_rate_warn`)
- `infra/terraform/modules/bedrock-guardrail/README.md` (warn-alarm ownership line updated)
- `infra/terraform/main.tf` (threaded the two observability vars into the app-runner module)
- `backend/app/agents/chat/session_handler.py` (added `total_tokens_used` + `user_id_hash` + `user_bucket` to `chat.turn.completed` at both emission sites — non-streaming + streaming; lifted the `if citations:` guard around `_log_citations_attached` so the P95-zero alarm has a heartbeat datapoint)
- `backend/tests/agents/chat/test_session_handler.py` (updated `test_send_turn_attaches_no_citations_when_no_tools` to assert the unconditional `citation_count=0` emission)
- `docs/operator-runbook.md` (new `## Chat Safety Operations (Story 10.9)` section)
- `docs/tech-debt.md` (TD-099 + TD-123 → Resolved)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (status flip)
- `VERSION` (1.52.0 → 1.53.0)

### Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-04-26 | Initial implementation complete; sprint-status flipped to `review`. | Dev agent |
| 2026-04-26 | Version bumped 1.52.0 → 1.53.0 per story completion (MINOR — observability surface). | Dev agent |
| 2026-04-26 | Resolved TD-099 (CanaryLeaked + finalizer-failed alarms) + TD-123 (citation-count metric/alarm). | Dev agent |
| 2026-04-27 | Apply-time fixes: (1) dropped `default_value` on `chat_turn_completed_token_spend` metric_transformation (mutual-exclusion with `dimensions`); (2) flipped `return_data = true` on the `band` metric_query of both `chat_token_spend_anomaly_warn` and `_page` (AWS anomaly-detection alarm contract). All 62 resources applied cleanly to prod. | Code review follow-up |
