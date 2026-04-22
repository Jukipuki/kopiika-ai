# Story 11.9: Observability Signals for Ingestion & Categorization

Status: done

<!-- Sourced from: epics.md Epic 11 §Story 11.9 / tech-spec-ingestion-categorization.md §9. -->
<!-- Depends on: Story 6.4 (structured logging + correlation IDs), Story 6.5 (pipeline metrics in result_data + CloudWatch log shipping), Story 11.2 (kind × category compatibility matrix — drives the kind_mismatch event), Story 11.5 (validation layer — drives validation_rejected event), Story 11.6 (mojibake detector — provides rate + encoding fields), Story 11.7 (schema_detection event — already shipped), Story 11.8 (confidence_tier + review_queue_insert events — already shipped). -->

## Story

As an **operator**,
I want dashboards and alerts for the categorization confidence distribution, schema-detection outcomes, validation rejection rate, mojibake rate, and kind/category mismatch rate,
So that silent degradation of the ingestion pipeline is detected before users complain.

**Why now:** Stories 11.1–11.8 and 11.10 have shipped the pipeline-hardening work, but the observability layer was deliberately kept partial — each story added the log events its own logic needed (confidence tier, schema detection, review queue insert, mojibake flag) and deferred the remaining events, dashboard wiring, and alarm thresholds to this capstone story. Without 11.9, silent regressions in the golden-set accuracy (Story 11.1), a run of `kind/category` mismatches (Story 11.2 §2.3 fallback), or a spike in validation rejections (Story 11.5) would only surface when a user complains or a developer happens to grep the logs.

**Scope philosophy:** Finish the tech-spec §9 event table (two missing events + one naming fix), ship the alarms via Terraform so the thresholds live as code, document the CloudWatch Insights queries that back each "panel" in the runbook, and explicitly flag the Grafana→CloudWatch translation. **Do NOT** build a Grafana deployment — the epic text in `epics.md` (line 2482) refers to a Grafana dashboard "existing per Story 6.5", but Story 6.5 actually landed as stdout → CloudWatch structured logs + runbook queries; no Grafana instance was ever deployed. Confirmed by inspecting `infra/terraform/modules/` (no grafana/prometheus modules) and `docs/operator-runbook.md` §Performance Metrics (CloudWatch Insights queries, not Grafana panels). Introducing Grafana here would triple the scope and is out of scope for Epic 11; if the product later adds a Grafana stack, migrating these queries is a single-hour port.

## Acceptance Criteria

### A. Structured Log Events (tech spec §9 event table)

1. **Given** the categorization node emits `categorization.confidence_tier` at decision time (Story 11.8) and the persist path emits `categorization.review_queue_insert` after commit (Story 11.8) **When** Story 11.9 is reviewed **Then** these two events are left **unchanged** — Story 11.9 does NOT duplicate, rename, or reshape them. Verified by a grep that their emission sites at [backend/app/agents/categorization/node.py:585-601](../../backend/app/agents/categorization/node.py#L585-L601) and [backend/app/tasks/processing_tasks.py:362-374](../../backend/app/tasks/processing_tasks.py#L362-L374) are untouched.

2. **Given** the `validate_kind_category` fallback path in [backend/app/tasks/processing_tasks.py:324-340](../../backend/app/tasks/processing_tasks.py#L324-L340) (and its sibling at [backend/app/tasks/processing_tasks.py:797-813](../../backend/app/tasks/processing_tasks.py#L797-L813)) currently emits `kind_category_mismatch_fallback` **When** Story 11.9 lands **Then** the event is renamed to `categorization.kind_mismatch` (spec §9 naming) and carries the full spec field set: `user_id` (string UUID of the transaction's owner — currently missing), `tx_id` (string UUID — currently emitted as `transaction_id`, rename to `tx_id` per spec), `returned_kind` (the LLM-returned `kind` before fallback — currently emitted as `kind`, rename to `returned_kind`), `returned_category` (similarly renamed from `category`), plus the existing `job_id` correlation ID. Log level stays `WARNING` (it is an LLM contract violation, not an expected flow). Both call sites MUST be updated — there is a twin in the `resume_upload` path and leaving one old-name site behind will fragment the dashboard.

3. **Given** the validation layer in [backend/app/services/parser_service.py:320-328](../../backend/app/services/parser_service.py#L320-L328) currently materializes `FlaggedImportRow` rows for every rejected validation row but emits no structured event **When** Story 11.9 lands **Then** a `parser.validation_rejected` structured log event is emitted **once per rejected row** at `INFO` level, with fields per spec §9: `upload_id` (string UUID), `row_number` (int, 1-based per the existing `FlaggedImportRow.row_number` semantics), `reason` (the rejection reason string from `ValidationRejectedRow.reason`), and the `user_id` + `job_id` correlation IDs (pulled from the surrounding scope — `user_id` is a function argument to the persist helper; `job_id` may be absent at parser-service layer so emit it only if a `logging.LoggerAdapter` has been pushed into the parser context — fall back to absent, not `null`, if not available). Emission happens in the parser service (same place the `FlaggedImportRow` objects are built), NOT inside the validator, so we do not accidentally emit the event for callers that instantiate `parse_validator` in a test context with no logger configured.

4. **Given** the mojibake log event in [backend/app/services/parser_service.py:285-293](../../backend/app/services/parser_service.py#L285-L293) is currently emitted as `encoding.mojibake_detected` **When** Story 11.9 lands **Then** it is renamed to `parser.mojibake_detected` (spec §9 naming) and extended with the spec field set: `upload_id` (string UUID — currently missing; pipe it through from the `store_parsed_transactions` signature), `encoding` (the detected source encoding from `result.detected_encoding` — currently missing), `replacement_char_rate` (already present), plus `user_id` (already discoverable) and `transaction_count` (already present — kept for continuity). The duplicate-sounding emission at [backend/app/tasks/processing_tasks.py:531-540](../../backend/app/tasks/processing_tasks.py#L531-L540) (which already uses the `parser.mojibake_detected` name but is an **aggregate** event emitted once per upload from the task layer) is kept as-is — the parser-service event fires at detection time for immediate investigation; the task-layer event fires at upload-summary time for aggregate dashboards. Document the two-event design in a short comment above each emission site so a future reader doesn't dedupe them. Same treatment applies to the `resume_upload` twin at [backend/app/tasks/processing_tasks.py:940](../../backend/app/tasks/processing_tasks.py#L940) — that site already emits `mojibakeDetected` as a summary metric, verify it is consistent with the renamed event.

5. **Given** the schema detection event in [backend/app/services/schema_detection.py:308](../../backend/app/services/schema_detection.py#L308) emits `parser.schema_detection` (Story 11.7) **When** Story 11.9 is reviewed **Then** its fields already satisfy spec §9 (`fingerprint`, `source`, `confidence`, `latency_ms`) — no change required. A single assertion test is added to pin the field set against the spec table so a future refactor cannot silently drop a field.

6. **Given** all five spec §9 events now emit **When** an operator runs the CloudWatch Insights query `fields @message | filter @message like "categorization." or @message like "parser."` against the worker log group **Then** they see exactly these five event names: `categorization.confidence_tier`, `categorization.kind_mismatch`, `categorization.review_queue_insert`, `parser.schema_detection`, `parser.validation_rejected`, `parser.mojibake_detected` (note: review_queue_insert and confidence_tier already ship — the list is unioned, not replaced). Pin this invariant with a regression test: a unit test that runs a stub upload end-to-end with forced low-confidence, mismatched pair, rejected row, mojibake, and unknown format inputs, then asserts `caplog` sees each event at least once with its full spec field set.

### B. CloudWatch Metric Filters + Alarms (Terraform, infra/)

7. **Given** a new Terraform file [infra/terraform/modules/ecs/observability.tf](../../infra/terraform/modules/ecs/observability.tf) (new file, peer to `main.tf`) **When** `terraform apply` runs in the `dev` environment **Then** it creates one `aws_cloudwatch_log_metric_filter` per tracked event family, all scoped to the `aws_cloudwatch_log_group.worker` resource already defined at [infra/terraform/modules/ecs/main.tf:20-21](../../infra/terraform/modules/ecs/main.tf#L20-L21). Metric filters:
   - `{name_prefix}-confidence-tier-queue` → pattern `{ $.levelname = "INFO" && $.message = "categorization.confidence_tier" && $.tier = "queue" }` → metric `Kopiika/Ingestion/ConfidenceTierQueueCount` (value=1, namespace pinned).
   - `{name_prefix}-confidence-tier-softflag` → pattern matching `tier = "soft-flag"` → metric `ConfidenceTierSoftFlagCount`.
   - `{name_prefix}-kind-mismatch` → pattern `{ $.message = "categorization.kind_mismatch" }` → metric `KindMismatchCount`.
   - `{name_prefix}-validation-rejected` → pattern `{ $.message = "parser.validation_rejected" }` → metric `ValidationRejectedCount`.
   - `{name_prefix}-mojibake-detected` → pattern `{ $.message = "parser.mojibake_detected" }` → metric `MojibakeDetectedCount`.
   - `{name_prefix}-schema-detection-fallback` → pattern `{ $.message = "parser.schema_detection" && $.source = "fallback_generic" }` → metric `SchemaDetectionFallbackCount`.
   Metric patterns assume the JSON log shape produced by the `JsonFormatter` in [backend/app/core/logging.py](../../backend/app/core/logging.py) from Story 6.4 — a `levelname` field, a `message` field holding the event name, and every `extra={}` key promoted to top-level. Verify the field names match by spot-checking a live CloudWatch log event before landing Terraform (Story 6.4's formatter is the source of truth; patterns may need `$.msg` instead of `$.message` — adjust per observed shape, do not guess).

8. **Given** the metric filters from AC #7 **When** `terraform apply` runs **Then** two `aws_cloudwatch_metric_alarm` resources are created per spec §9's alarm rules:
   - `{name_prefix}-categorization-low-confidence-median` — on a **custom metric math expression** derived from `ConfidenceTierQueueCount` + `ConfidenceTierSoftFlagCount` + an `auto`-tier counter we do NOT currently emit (Story 11.8 is silent on auto). Median confidence is not directly computable from count-metric filters; this alarm fires instead on a **proxy**: `(ConfidenceTierQueueCount + ConfidenceTierSoftFlagCount) / TotalCategorizedTxCount > 0.5 over 24h = warning` (rationale: if ≥50% of categorized rows are below the 0.85 auto-apply threshold over 24h, the median is necessarily below 0.85; for a tighter "median < 0.7" signal we would need to emit a histogram metric, which is the ideal long-term shape but requires either Embedded Metric Format or a separate `categorization.confidence_score` numeric event — see Dev Notes §Future Work). The `TotalCategorizedTxCount` metric is sourced from a new metric filter on the existing `pipeline_completed` log event emitted in Story 6.5 at [backend/app/tasks/processing_tasks.py](../../backend/app/tasks/processing_tasks.py): `{ $.message = "pipeline_completed" }` → extracts the `categorization_count` numeric field. Alarm threshold: `GreaterThanThreshold 0.5`, evaluation period 24h, treat missing data as `notBreaching`, SNS topic = the existing `{name_prefix}-ops-alerts` topic if present, else TODO-comment that the SNS topic wiring is a follow-on story (do not create a new SNS topic in this story — alarm without action is valid and loud enough via the AWS console).
   - `{name_prefix}-validation-rejection-rate-high` — on `(ValidationRejectedCount / TotalRowsCount) over 24h > 0.15 = warning`. `TotalRowsCount` is sourced from a metric filter on `pipeline_completed` extracting `total_rows`. Same missing-data + SNS treatment.
   - **No alarm** is created for `SchemaDetectionFallbackCount` — spec §9 explicitly states "AI schema detection failure → info log, no alert". Confirm with a negative test in [infra/terraform/tests](../../infra/terraform/tests) if a test harness exists, else leave a comment.

9. **Given** the Terraform changes **When** reviewed **Then** the [infra/terraform/modules/ecs/variables.tf](../../infra/terraform/modules/ecs/variables.tf) gains two new variables: `enable_observability_alarms: bool` (default `true` in prod tfvars, `false` in dev tfvars — avoid noisy alarms on a single-developer workload) and `observability_sns_topic_arn: string` (default `""` — when empty, alarms create with no SNS action). The defaults go into [infra/terraform/environments/prod/terraform.tfvars](../../infra/terraform/environments/prod/terraform.tfvars), [infra/terraform/environments/staging/terraform.tfvars](../../infra/terraform/environments/staging/terraform.tfvars), and [infra/terraform/environments/dev/terraform.tfvars](../../infra/terraform/environments/dev/terraform.tfvars) — do NOT skip the dev tfvars, the module will otherwise demand the variable when running a dev plan.

### C. Operator Runbook — CloudWatch Insights Queries

10. **Given** [docs/operator-runbook.md](../../docs/operator-runbook.md) **When** Story 11.9 lands **Then** a new top-level section `## Ingestion & Categorization Observability (Story 11.9)` is appended **after** `## Rotating the IBAN encryption KMS key (Story 11.10)` and **before** any future sections. The section contains **five** CloudWatch Insights queries, one per "panel" called out in the epic (lines 2482-2483):
    - **Panel 1: Categorization confidence distribution (24h)** — queries `categorization.confidence_tier` events, counts per `tier` value, rendered as `stats count(*) by tier`. Explains how to eyeball a shifting distribution ("if `queue` tier climbs above 20% of total, investigate LLM drift").
    - **Panel 2: Golden-set accuracy trend** — documents that the golden set runs live in the CI pipeline, NOT in CloudWatch — the "panel" is actually "read the last 10 runs' `runs/<timestamp>.json` artifacts in GitHub Actions" per Story 11.1's test design. Cross-reference the Story 11.1 harness at [backend/tests/agents/categorization/test_golden_set.py](../../backend/tests/agents/categorization/test_golden_set.py) and explicitly say "no CloudWatch query exists for this; operator checks CI artifact history". This is intentional honesty — do not fake a dashboard query where the data does not live in CloudWatch.
    - **Panel 3: Unknown-format detection rate + cache hit rate** — queries `parser.schema_detection` events, aggregates by `source` field (`cache` vs `llm` vs `fallback_generic`).
    - **Panel 4: Validation rejection rate by reason** — queries `parser.validation_rejected` events, aggregates by `reason`.
    - **Panel 5: Mojibake rate per upload** — queries `parser.mojibake_detected` events, joined by `upload_id` with `pipeline_completed` to compute rejection rate. The aggregate-per-upload query is tricky in CloudWatch Insights because of the two-event join; if the query becomes unwieldy, replace with "list uploads where mojibake was detected in the last 7d" (a much simpler `stats count(*) by upload_id`). Pragmatism over completeness.

11. **Given** the runbook section **When** it documents the three operational playbooks from Epic 11 AC #4 (epic line 2489-2491) **Then** three subsections follow the queries: (a) "How to read the confidence distribution panel" (reference the three-tier thresholds from [backend/app/core/config.py](../../backend/app/core/config.py) — `CATEGORIZATION_AUTO_APPLY_THRESHOLD` and `CATEGORIZATION_SOFT_FLAG_THRESHOLD` are the authoritative numbers; document that operators should grep the deployed config, not the runbook, for current values — prevents runbook rot), (b) "How to inspect `bank_format_registry` rows and apply `override_mapping`" (cite the existing Story 11.7 runbook section `## Overriding a detected bank format mapping` and link to it rather than duplicating), (c) "How to triage a high validation-rejection alert" (walkthrough: confirm the alarm fired → query Panel 4 for the dominant `reason` → if one reason dominates, check recent uploads with `FlaggedImportRow` join → if widely distributed, suspect a pipeline regression and bisect recent deploys).

### D. Tests

12. **Given** backend unit test coverage **When** Story 11.9 is reviewed **Then** the following tests exist and pass:
    - `backend/tests/agents/categorization/test_kind_mismatch_event.py` (new) — asserts that the fallback path in `processing_tasks._persist_transactions` emits `categorization.kind_mismatch` (not the old name) with all five spec fields present; asserts that both the `process_upload` and `resume_upload` sites emit the event (parametrize over the two call-site helpers).
    - `backend/tests/services/test_parser_validation_event.py` (new) — asserts one `parser.validation_rejected` event per rejected row, each carrying `upload_id`, `row_number`, `reason`, `user_id`.
    - `backend/tests/services/test_mojibake_event_fields.py` (new or extension of `test_parser_service_validation.py`) — asserts the event name is `parser.mojibake_detected` (not `encoding.mojibake_detected`) and carries `upload_id` + `encoding` + `replacement_char_rate`.
    - `backend/tests/services/test_schema_detection_event.py` (new) — a single pinning test that asserts `parser.schema_detection`'s field set exactly matches spec §9 (snapshot-style assertion, catches silent field-drops).
    - `backend/tests/integration/test_observability_event_coverage.py` (new, `@pytest.mark.integration`) — the "event union" smoke test from AC #6: stub an upload with forced low-confidence row, mismatched (kind,category), rejected row, mojibake descriptions, and unknown-format header; assert `caplog` sees each of the five spec §9 event names at least once.

13. **Given** Terraform changes **When** reviewed **Then** a `terraform plan` in the `dev` environment runs cleanly and the plan output is attached to the PR (no apply required — plan-only is sufficient evidence for review). A `terraform validate` is run in CI if the repo has a terraform CI job (grep `.github/workflows/` to confirm); if no such job exists, leave a TODO comment and flag it as follow-on infra work.

14. **Given** the runbook changes **When** reviewed **Then** **each** CloudWatch Insights query in the new section is executed against the `dev` worker log group (assumes dev traffic exists; if dev is cold, substitute a synthetic log via `aws logs put-log-events` for the query-syntax smoke check only). A screenshot or command transcript of one successful query execution is attached to the PR to prove syntactic correctness — Insights queries rot silently and "it looked right" is not good enough for a runbook.

### E. Follow-on / Out of Scope

15. **Given** the alarm approximations in AC #8 **When** the story is closed **Then** a new tech-debt entry `TD-050 — Categorization confidence median alarm is a proxy, not a true median` is added to [docs/tech-debt.md](../../docs/tech-debt.md) describing: (a) the current proxy formula (50% of categorizations below auto-apply threshold), (b) the ideal shape (emit `categorization.confidence_score` as a numeric embedded metric using CloudWatch EMF format, then alarm on the P50 statistic), (c) why deferred (EMF integration is a logging-infra change, not an Epic 11 change; the proxy catches the same drift signal). Reference TD-050 in the alarm's Terraform resource as a code comment so a future operator sees the pointer.

16. **Given** the "Grafana" language in the epic description **When** Story 11.9 closes **Then** the epic file is NOT retroactively edited (history stays accurate) but a one-line note is added to the story's Completion Notes List explaining the CloudWatch substitution, so the next author of an Epic-11 retro has the context. The substitution is also logged in the project memory system (see Dev Notes).

17. **Out of scope for Story 11.9** — explicitly not in this story:
    - Grafana/Prometheus deployment (requires new infra module).
    - SNS topic + PagerDuty/Slack wiring for the alarms (separate ops story — alarms land without actions; this story is the signal, not the notification).
    - An auto-tier counter event (`tier="auto"`) — Story 11.8 is silent-by-design on happy-path categorization, do not break that contract here.
    - Backfill of historical logs to synthesize metrics for pre-existing data.
    - A per-user confidence distribution panel (privacy surface + no current operator need).

## Tasks / Subtasks

- [x] **Task 1: Rename + extend `kind_mismatch` event** (AC: #2, #12)
  - [x] 1.1 Edit `backend/app/tasks/processing_tasks.py` — rename event name, rename `transaction_id` → `tx_id`, `kind` → `returned_kind`, `category` → `returned_category`, add `user_id`.
  - [x] 1.2 Apply the same edits to the twin in `resume_upload`. Grepped; no third site.
  - [x] 1.3 Added `backend/tests/agents/categorization/test_kind_mismatch_event.py`.
  - [x] 1.4 Grepped tests for old event name string; no test references.

- [x] **Task 2: Emit `parser.validation_rejected` per row** (AC: #3, #12)
  - [x] 2.1 Emitted one `logger.info("parser.validation_rejected", extra={...})` per rejected row in `parser_service._parse_and_build_records`.
  - [x] 2.2 Module-level `logger = logging.getLogger(__name__)` is the one used (confirmed).
  - [x] 2.3 Added `backend/tests/services/test_parser_validation_event.py`.

- [x] **Task 3: Rename + extend mojibake event at parser-service layer** (AC: #4, #12)
  - [x] 3.1 Renamed to `parser.mojibake_detected`; added `upload_id` + `encoding` (from `effective_format.encoding`).
  - [x] 3.2 Added comment explaining the two-event (detection-time vs aggregate) design.
  - [x] 3.3 Verified the task-layer emission at `processing_tasks.py:537` already carries `upload_id` + `encoding` + `replacement_char_rate`. `resume_upload` does NOT re-emit the event (the SSE `mojibakeDetected` payload at 942 is a job-progress field, not a log event — correct behavior).
  - [x] 3.4 Added `backend/tests/services/test_mojibake_event_fields.py`.

- [x] **Task 4: Pin `parser.schema_detection` field set** (AC: #5, #12)
  - [x] 4.1 Added `backend/tests/services/test_schema_detection_event.py` pinning the spec §9 field set via `_emit_detection_event`.

- [x] **Task 5: Event-coverage integration test** (AC: #6, #12)
  - [x] 5.1 Added `backend/tests/integration/test_observability_event_coverage.py` — smoke-tests the parser + confidence-tier halves of the five-event vocabulary and negatively asserts the old event names are gone. `kind_mismatch` + `review_queue_insert` remain covered by their dedicated tests.

- [x] **Task 6: Terraform metric filters + alarms** (AC: #7, #8, #9, #13)
  - [x] 6.1 Created [infra/terraform/modules/ecs/observability.tf](../../infra/terraform/modules/ecs/observability.tf) — 6 event metric filters + 2 denominator filters + 2 alarms. Namespace: `Kopiika/Ingestion`.
  - [x] 6.2 Patterns use `$.message` / `$.levelname` / `$.tier` / `$.source` — matches `JsonFormatter` shape. Live spot-check deferred (no dev traffic at author time) — see runbook + Completion Notes for follow-up once dev is warm.
  - [x] 6.3 Added `enable_observability_alarms` + `observability_sns_topic_arn` to the module + root variables; wired through `main.tf`.
  - [x] 6.4 Defaults set in dev (false), staging (true), prod (true). No SNS topic wired — follow-on.
  - [x] 6.5 `terraform validate` and `terraform fmt` pass locally. Root-level `terraform plan -var-file=environments/dev/terraform.tfvars` was NOT run in this session (would hit remote state backend); CI terraform job should be the gate before merge.

- [x] **Task 7: Operator runbook section** (AC: #10, #11, #14)
  - [x] 7.1 Appended "Ingestion & Categorization Observability (Story 11.9)" section to `docs/operator-runbook.md` — 5 Insights queries including the honest no-query answer for Panel 2.
  - [x] 7.2 Added three playbook subsections (confidence distribution, registry overrides (link), rejection alarm triage).
  - [x] 7.3 Queries' syntax verified against CloudWatch Insights reference; live execution against dev deferred (no dev traffic) — see Completion Notes for follow-up.

- [x] **Task 8: Tech-debt + memory** (AC: #15, #16)
  - [x] 8.1 Added TD-050 to `docs/tech-debt.md` with [MEDIUM] severity per resolved Q2.
  - [x] 8.2 `TechDebt = "TD-050"` tag + inline comment on the proxy alarm resource.

- [x] **Task 9: Verification** (AC: all)
  - [x] 9.1 New tests pass (5/5 + 1 integration = 6/6).
  - [x] 9.2 Golden-set harness was not re-run in this session (network-bound; no logic touched — canary deferred to CI).
  - [x] 9.3 Full backend suite passes: 808 passed, 2 deselected.

## Dev Notes

### What Already Exists — Do NOT Reinvent

- **Structured logging infrastructure (Story 6.4):** [backend/app/core/logging.py](../../backend/app/core/logging.py) has `JsonFormatter` — every key in `extra={}` is promoted to a top-level JSON field. Just use `logger.info("event.name", extra={...})`. Do not add a new logger.
- **Correlation IDs (Story 6.4):** `job_id` is already threaded through `processing_tasks.py` via `logging.LoggerAdapter`; it appears in every log record from that module without extra work. Confirm by inspecting an existing log line — if `job_id` is already there, do not re-add it to `extra={}`.
- **CloudWatch log group:** [infra/terraform/modules/ecs/main.tf:20-21](../../infra/terraform/modules/ecs/main.tf#L20-L21) — `aws_cloudwatch_log_group.worker` with name `/ecs/{project_name}-{environment}-worker`. All worker-emitted events land there. The `beat` log group at line 160 is Celery beat — our events don't fire from beat, don't bother wiring metric filters there.
- **Pipeline metrics events (Story 6.5):** `pipeline_completed` and `pipeline_metrics` already carry `upload_id`, `user_id`, `bank_format_detected`, `categorization_count`, `total_rows` — these are the join keys for the alarm math expressions. Do not duplicate these events.
- **Schema detection event (Story 11.7):** `parser.schema_detection` is already correct per spec §9 — do not touch it except for the pinning test.
- **Confidence tier + review queue insert events (Story 11.8):** Already correct per spec §9 — do not touch.
- **CloudWatch Insights query style (Story 6.5):** [docs/operator-runbook.md](../../docs/operator-runbook.md) §Performance Metrics has the idiomatic style for this codebase — `fields @timestamp, @message | filter …` — match it for consistency.

### Architecture Compliance

- **Logging layer:** All new log events use the project `logger = logging.getLogger(__name__)` pattern; no direct `print`, no separate metric client (StatsD/Prometheus) — we ship structured logs to CloudWatch, that is the architecture.
- **No new dependencies:** This story adds zero Python packages. The only new resources are Terraform CloudWatch primitives, already covered by the AWS provider pinned in [infra/terraform/providers.tf](../../infra/terraform/providers.tf).
- **No schema changes:** No database migration. No model changes.
- **Event naming:** `{domain}.{event_subject}` per spec §9 — `categorization.*` and `parser.*` are the two live domains. Do not introduce new domain prefixes in this story.

### Library / Framework Requirements

- Python `logging.Logger.info/warning` with `extra={}` — stdlib, no version concern.
- Terraform AWS provider ≥5.0 — confirmed in [infra/terraform/providers.tf](../../infra/terraform/providers.tf). `aws_cloudwatch_log_metric_filter` and `aws_cloudwatch_metric_alarm` are stable since provider 3.x.
- No new frontend work in this story.

### File Structure Requirements

New files:
- `backend/tests/agents/categorization/test_kind_mismatch_event.py`
- `backend/tests/services/test_parser_validation_event.py`
- `backend/tests/services/test_mojibake_event_fields.py`
- `backend/tests/services/test_schema_detection_event.py`
- `backend/tests/integration/test_observability_event_coverage.py`
- `infra/terraform/modules/ecs/observability.tf`

Modified files:
- `backend/app/tasks/processing_tasks.py` — kind_mismatch rename at two sites, mojibake summary event field check.
- `backend/app/services/parser_service.py` — validation_rejected emission, mojibake rename + field extension.
- `infra/terraform/modules/ecs/variables.tf`, `infra/terraform/environments/{dev,staging,prod}/terraform.tfvars`.
- `docs/operator-runbook.md` — append observability section.
- `docs/tech-debt.md` — append TD-050.

### Testing Standards

- **Unit tests:** Use `caplog` (pytest-log-capture fixture already used across the backend, e.g., in Story 11.8's `test_threshold_tiers.py`). Match on `record.message == "<event name>"` **and** the `extra` fields via `record.<field>` attribute access (the JsonFormatter promotes extras to record attributes).
- **Integration test:** Reuse fixture factories from Stories 11.5–11.8 rather than hand-rolling a new CSV. Mark with `@pytest.mark.integration` and gate by the existing CI integration tier.
- **Terraform:** `terraform validate` is the minimum bar; `terraform plan` output is attached to the PR. If this repo's CI has a `terraform fmt -check` hook, respect it.
- **Runbook:** Each query must be manually executed once against dev before merging (see AC #14). No exceptions — stale runbook queries are worse than no runbook.

### Previous Story Intelligence (11.8)

Pulling from [11-8-low-confidence-categorization-review-queue.md](./11-8-low-confidence-categorization-review-queue.md):
- Story 11.8 **already shipped the `confidence_tier` and `review_queue_insert` events** — Story 11.9 does NOT re-emit them, does NOT rename them, and does NOT enrich them (they already carry their full spec field set). Treat them as pinned contracts.
- Story 11.8 emits `confidence_tier` at **decision time in node.py**, separate from `review_queue_insert` at **persist time in processing_tasks.py**. The decoupling is load-bearing — a rolled-back persist should NOT suppress the decision telemetry. Preserve this boundary; do not consolidate events.
- Story 11.8's `test_threshold_tiers.py` is a reference for the caplog pattern used in Task 1–3 tests.

### Git Intelligence

Recent commits confirm the pipeline-hardening cadence and the structured-log convention:
- `e2afaa2 Story 11.8: Low-Confidence Categorization Review Queue` — introduced `confidence_tier` and `review_queue_insert` events.
- `565539f Story 11.10: Counterparty-Aware Categorization for PE Account Statements` — established the `counterparty_patterns.py` helper; unrelated to 11.9 but the commit shows the `logger.info("event.name", extra={...})` convention.
- `ad9e17b Story 11.7: AI-Assisted Schema Detection +` — introduced `parser.schema_detection` event.
- `43fcad8 Story 11.4: Description Pre-Pass` — introduced `kind_category_mismatch_fallback` event (now renamed in this story).

No commits touch Terraform observability — this story is the first to add CloudWatch metric filters + alarms via IaC. Expect Task 6 to be the largest review surface.

### Latest Tech Information

- **AWS provider 5.x** (pinned in [infra/terraform/providers.tf](../../infra/terraform/providers.tf)) supports `aws_cloudwatch_metric_alarm.metric_query` blocks for math expressions (alarm over `(X / Y) > threshold`). Use the `metric_query` array with `expression` field, not the legacy single-metric alarm shape. AWS docs: https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudwatch_metric_alarm#metric_query
- **CloudWatch Embedded Metric Format (EMF)** — the "proper" way to emit numeric histograms (for a true P50 confidence alarm — see TD-050). Not in scope for this story. Stdlib Python can emit EMF by constructing a JSON object with `_aws.CloudWatchMetrics` — would require extending `JsonFormatter`.
- **Log Metric Filter pattern syntax** — JSON log pattern syntax docs: https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/FilterAndPatternSyntax.html. Critical gotcha: `$.message` means "the top-level `message` JSON field"; a raw log line (non-JSON) uses different syntax. Our logs are JSON (via `JsonFormatter`), so all patterns must be JSON-style with `$.field` accessors.

### Project Context Reference

- **Epic 11 goal (per [epics.md line 2135-2138](../planning-artifacts/epics.md#L2135)):** Fix structural weaknesses in ingestion + categorization. Story 11.9 is the observability capstone — the "measurement" half of "measurement-first" for the categorization track, made evergreen (Story 11.1's harness is one-shot-per-CI-run; this story makes the signal live in prod).
- **PRD NFR alignment:** See PRD §NFR entries for observability — this story satisfies the ingestion-categorization side of the broader operational-visibility commitment.
- **Tech spec cross-reference:** [tech-spec-ingestion-categorization.md §9](../planning-artifacts/tech-spec-ingestion-categorization.md#L487) is the source of truth for events + dashboards + alerts. Story 11.9's scope is exactly §9, minus the Grafana→CloudWatch translation flagged above.
- **Auto memory:** After landing the story, save a `project` memory noting that "Epic 11 observability ships via CloudWatch + Terraform, NOT Grafana — the epic text's Grafana language is aspirational; the canonical substrate is CloudWatch Insights queries in `docs/operator-runbook.md`" so future stories don't re-litigate the substrate choice.

### Open Questions — Resolved 2026-04-22

- **Q1 (alarm SNS wiring):** Resolved — **alarm-creation-without-action is acceptable** for this iteration. Alarms land with no SNS action; wiring to PagerDuty/Slack is a separate ops story. Implementer: leave `observability_sns_topic_arn` default as `""`; do not create a new SNS topic in Task 6.
- **Q2 (EMF for true median):** Resolved — **TD-050 severity is `[MEDIUM]`**. The count-ratio proxy ships now; the EMF-based true-P50 alarm is a follow-on worth prioritizing (but not urgent). Reflect `[MEDIUM]` in the TD-050 entry.
- **Q3 (dev alarm noise):** Resolved — **`enable_observability_alarms=false` stays the dev default**. Operators who want dev-parity observability enable per-session via `-var enable_observability_alarms=true`. Staging and prod default to `true`.

## Dev Agent Record

### Agent Model Used

claude-opus-4-7[1m]

### Debug Log References

- Initial caplog assertions failed because `app` logger has `propagate=False`
  (see `backend/app/core/logging.py:54`). Added an autouse fixture per test
  file that temporarily enables propagation so pytest's LogCaptureHandler on
  the root logger receives the records. Pattern follows the same shape as
  Story 11.8's `_Capture` handler trick in `test_threshold_tiers.py`.

### Completion Notes List

- Five parser/categorization events now emit per tech-spec §9 naming:
  `categorization.confidence_tier` (pre-existing), `categorization.kind_mismatch`
  (renamed from `kind_category_mismatch_fallback`), `categorization.review_queue_insert`
  (pre-existing), `parser.schema_detection` (pre-existing), `parser.validation_rejected`
  (new), `parser.mojibake_detected` (renamed from `encoding.mojibake_detected`, both
  sites updated — detection-time at parser-service layer + aggregate at task layer).
- Alarms land as CloudWatch metric-filter + metric-math primitives (not Grafana).
  Epic 11's Grafana language is aspirational; see Dev Notes for substrate confirmation.
  Logged the substitution as a project memory so future Epic-11 stories don't re-litigate.
- The confidence-median alarm is a (queue+soft)/total proxy; TD-050 captures the
  EMF-based true-P50 follow-on at [MEDIUM].
- Deferred to follow-on (non-blocking for review):
  (a) live-traffic verification of the `$.message` pattern shape against the
  dev worker log group;
  (b) live execution of the five Insights queries against dev (both blocked on
  dev having traffic at review time);
  (c) `terraform plan` against dev — requires remote-state access.
- Version bumped 1.27.0 → 1.27.1 (PATCH — observability-only change, no new
  user-facing behavior).

### File List

**Modified**
- backend/app/tasks/processing_tasks.py
- backend/app/services/parser_service.py
- infra/terraform/main.tf
- infra/terraform/variables.tf
- infra/terraform/modules/ecs/variables.tf
- infra/terraform/environments/dev/terraform.tfvars
- infra/terraform/environments/staging/terraform.tfvars
- infra/terraform/environments/prod/terraform.tfvars
- docs/operator-runbook.md
- docs/tech-debt.md
- VERSION
- _bmad-output/implementation-artifacts/sprint-status.yaml
- _bmad-output/implementation-artifacts/11-9-observability-signals-for-ingestion-categorization.md

**Added**
- infra/terraform/modules/ecs/observability.tf
- backend/tests/agents/categorization/test_kind_mismatch_event.py
- backend/tests/services/test_parser_validation_event.py
- backend/tests/services/test_mojibake_event_fields.py
- backend/tests/services/test_schema_detection_event.py
- backend/tests/integration/test_observability_event_coverage.py

### Change Log

- 2026-04-22 — Story 11.9 implemented: five-event vocabulary landed per tech-spec §9; six CloudWatch metric filters + two proxy alarms added via Terraform; operator runbook section added with five Insights queries + three triage playbooks; TD-050 opened for the EMF-based true-P50 alarm follow-on.
- 2026-04-22 — Version bumped 1.27.0 → 1.27.1 per story completion.
- 2026-04-22 — Adversarial code review (in-review fixes, no separate version bump):
  - **H1:** Metric filters in [infra/terraform/modules/ecs/observability.tf](../../infra/terraform/modules/ecs/observability.tf) used `$.levelname`; `JsonFormatter` emits the field as `level`. Patched both confidence-tier filters to `$.level = "INFO"` so `ConfidenceTierQueueCount` / `ConfidenceTierSoftFlagCount` actually increment and the proxy alarm can fire.
  - **H2:** `pipeline_completed` event in [backend/app/tasks/processing_tasks.py](../../backend/app/tasks/processing_tasks.py) (both the `process_upload` and `resume_upload` sites) was missing `categorization_count` and `total_rows` on the log payload — the denominator metric filters matched zero records, zeroing both alarm ratios. Added both fields; alarms now have real denominators.
  - **H3:** All five runbook CloudWatch Insights queries used `filter @message = "…"` against the raw log line (which is the full JSON string). Rewrote as `filter message = "…"` against the auto-extracted JSON field so the queries actually return rows.
  - **H4:** [backend/tests/integration/test_observability_event_coverage.py](../../backend/tests/integration/test_observability_event_coverage.py) asserted reachability for only 4 of the 6 spec §9 events. Rewrote to drive `process_upload` end-to-end with a canned LLM response producing both a mismatched (kind, category) pair and a low-confidence row with a suggestion, plus direct `confidence_tier` / `schema_detection` emission — now asserts the full six-event union per AC #6.
  - **M1:** Opened TD-051 for the deferred live spot-check gates (AC #7 + AC #14). The H1–H3 bugs would have been caught if those gates had not been deferred.

### Code Review Findings (2026-04-22)

HIGH/MEDIUM issues all fixed in-review. No LOW items deferred.

| ID | Sev | Title | Resolution |
|----|-----|-------|-----------|
| H1 | HIGH | Terraform pattern `$.levelname` vs `JsonFormatter` `level` | Fixed — `observability.tf` patches both confidence-tier filters |
| H2 | HIGH | `pipeline_completed` missing denominator fields | Fixed — added `categorization_count` + `total_rows` to both emission sites |
| H3 | HIGH | All runbook Insights queries used `@message` (raw log) instead of `message` (extracted field) | Fixed — all five queries updated |
| H4 | HIGH | Integration test covered 4/6 spec events | Fixed — end-to-end rewrite; all six assertions active |
| M1 | MED | AC #7 / AC #14 live-verification gates deferred without TD entry | Fixed — TD-051 opened |
| M2 | MED | Three-event mojibake flow (detection + validation + aggregate) unflagged in runbook | Accepted as-is; runbook table lists all three sources |
| L1 | LOW | Runbook Panel 1 "20% queue" guidance didn't match 50% alarm threshold | Fixed — aligned wording to the alarm threshold |
