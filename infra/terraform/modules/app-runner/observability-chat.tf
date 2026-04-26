# Story 10.9 — Chat safety observability (metric filters + alarms on the
# App Runner application log group).
#
# ── Location decision (AC #2) ────────────────────────────────────────────
# Co-located with the App Runner module per the AC #2 PREFERRED placement
# strategy. The metric filters reference the App Runner-managed application
# log group; co-location keeps the log-group reference local and avoids
# cross-module ARN passing. ECS-owned ingestion signals stay in
# modules/ecs/observability.tf (Story 11.9); the warn-level Bedrock alarm
# stays in modules/bedrock-guardrail/main.tf (Story 10.9 AC #9).
#
# ── Scope deferrals (per Story 10.9 §Scope Boundaries) ───────────────────
# - No new chat-event emission (one-line additions to chat.turn.completed
#   for `total_tokens_used` + `user_id_hash` are made under the AC #3 row 6
#   exemption pattern; no new logger.info call sites are introduced).
# - No SNS topic creation — `var.observability_sns_topic_arn` is wired
#   from the root stack the same way 11.9 wires it.
# - No new dashboards — Logs Insights snippets ship in the operator runbook
#   per `docs/operator-runbook.md` §Chat Safety Operations.
# - No anomaly-detection model deployment — per-user token-spend uses
#   CloudWatch's built-in `ANOMALY_DETECTION_BAND` math expression.
# - No edits to the existing page-level Bedrock-Guardrail alarm; the warn
#   companion lands in modules/bedrock-guardrail/main.tf as a fresh
#   resource (AC #9). The bedrock-guardrail module is prod-only.
# - The `chat.stream.first_token` event already carries `ttfb_ms` (Story
#   10.5); we use that field directly. No deviation from §Scope Boundaries
#   was required for AC #3 row 6 latency.
# - TD-095 / TD-100 / TD-103 are NOT closed — their triggers are post-prod
#   data, not the existence of these metric filters.
#
# ── Per-user dimensioning (AC #6) ────────────────────────────────────────
# Token-spend is dimensioned by `user_bucket` — the first hex char of
# `_hash_user_id(...)` — emitted as a precomputed field on
# `chat.turn.completed` (CloudWatch JSON metric filters cannot slice
# strings, so the bucket is computed runtime-side). 16 buckets stays
# inside the free-tier 10-values-per-name cap when the active-user count
# is small enough that buckets are sparsely populated, and inside the
# paid 3000-values-per-ARN cap unconditionally. Per-bucket alarms are
# generated via `for_each` over `local.user_buckets` below; widening to
# more granular buckets requires both a runtime emission change and a
# matching `local.user_buckets` rebuild.

# ── App Runner application log group reference ──────────────────────────
# App Runner auto-creates two log groups per service:
#   /aws/apprunner/<svc-name>/<svc-id>/application  (chat events stream here)
#   /aws/apprunner/<svc-name>/<svc-id>/service      (App Runner system events)
# The service ID is the trailing segment of the service ARN. We extract it
# via regex rather than relying on a `service_id` attribute (the AWS
# provider does not surface one as of v5.x).
locals {
  apprunner_service_id = regex("/[^/]+/([0-9a-f]+)$", aws_apprunner_service.api.arn)[0]
  chat_log_group_name  = "/aws/apprunner/${aws_apprunner_service.api.service_name}/${local.apprunner_service_id}/application"
  chat_namespace       = "Kopiika/Chat"
  user_buckets         = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "a", "b", "c", "d", "e", "f"]
}

# ── Metric filters (one per tracked event / dimension) ───────────────────
#
# Filters are unconditional (free); alarms gate behind
# var.enable_observability_alarms below. Pattern shape mirrors
# `infra/terraform/modules/ecs/observability.tf` — JSON pattern + extracted
# numeric value where applicable, default value 0 so missing log lines
# don't synthesize zero-points.

# ─── Stream lifecycle ────────────────────────────────────────────────────

resource "aws_cloudwatch_log_metric_filter" "chat_stream_opened" {
  name           = "${local.name_prefix}-chat-stream-opened"
  log_group_name = local.chat_log_group_name
  pattern        = "{ $.message = \"chat.stream.opened\" }"

  metric_transformation {
    name          = "ChatStreamOpenedCount"
    namespace     = local.chat_namespace
    value         = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_log_metric_filter" "chat_stream_first_token" {
  name           = "${local.name_prefix}-chat-stream-first-token"
  log_group_name = local.chat_log_group_name
  pattern        = "{ $.message = \"chat.stream.first_token\" && $.ttfb_ms = * }"

  metric_transformation {
    name          = "ChatStreamFirstTokenLatencyMs"
    namespace     = local.chat_namespace
    value         = "$.ttfb_ms"
    default_value = "0"
  }
}

resource "aws_cloudwatch_log_metric_filter" "chat_stream_completed" {
  name           = "${local.name_prefix}-chat-stream-completed"
  log_group_name = local.chat_log_group_name
  pattern        = "{ $.message = \"chat.stream.completed\" }"

  metric_transformation {
    name          = "ChatStreamCompletedCount"
    namespace     = local.chat_namespace
    value         = "1"
    default_value = "0"
  }
}

# Refusal — unfiltered (denominator of refusal-rate; numerator of overall
# refusal alarm).
resource "aws_cloudwatch_log_metric_filter" "chat_stream_refused_total" {
  name           = "${local.name_prefix}-chat-stream-refused-total"
  log_group_name = local.chat_log_group_name
  pattern        = "{ $.message = \"chat.stream.refused\" }"

  metric_transformation {
    name          = "ChatStreamRefusedCount"
    namespace     = local.chat_namespace
    value         = "1"
    default_value = "0"
  }
}

# Refusal — `reason = ungrounded` slice (numerator of grounding-block-rate).
resource "aws_cloudwatch_log_metric_filter" "chat_stream_refused_ungrounded" {
  name           = "${local.name_prefix}-chat-stream-refused-ungrounded"
  log_group_name = local.chat_log_group_name
  pattern        = "{ $.message = \"chat.stream.refused\" && $.reason = \"ungrounded\" }"

  metric_transformation {
    name          = "ChatStreamRefusedUngroundedCount"
    namespace     = local.chat_namespace
    value         = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_log_metric_filter" "chat_stream_guardrail_intervened" {
  name           = "${local.name_prefix}-chat-stream-guardrail-intervened"
  log_group_name = local.chat_log_group_name
  pattern        = "{ $.message = \"chat.stream.guardrail_intervened\" }"

  metric_transformation {
    name          = "ChatStreamGuardrailIntervenedCount"
    namespace     = local.chat_namespace
    value         = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_log_metric_filter" "chat_stream_guardrail_detached" {
  name           = "${local.name_prefix}-chat-stream-guardrail-detached"
  log_group_name = local.chat_log_group_name
  pattern        = "{ $.message = \"chat.stream.guardrail_detached\" }"

  metric_transformation {
    name          = "ChatStreamGuardrailDetachedCount"
    namespace     = local.chat_namespace
    value         = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_log_metric_filter" "chat_stream_finalizer_failed" {
  name           = "${local.name_prefix}-chat-stream-finalizer-failed"
  log_group_name = local.chat_log_group_name
  pattern        = "{ $.message = \"chat.stream.finalizer_failed\" }"

  metric_transformation {
    name          = "ChatStreamFinalizerFailedCount"
    namespace     = local.chat_namespace
    value         = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_log_metric_filter" "chat_stream_disconnected" {
  name           = "${local.name_prefix}-chat-stream-disconnected"
  log_group_name = local.chat_log_group_name
  pattern        = "{ $.message = \"chat.stream.disconnected\" }"

  metric_transformation {
    name          = "ChatStreamDisconnectedCount"
    namespace     = local.chat_namespace
    value         = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_log_metric_filter" "chat_stream_consent_drift" {
  name           = "${local.name_prefix}-chat-stream-consent-drift"
  log_group_name = local.chat_log_group_name
  pattern        = "{ $.message = \"chat.stream.consent_drift\" }"

  metric_transformation {
    name          = "ChatStreamConsentDriftCount"
    namespace     = local.chat_namespace
    value         = "1"
    default_value = "0"
  }
}

# ─── Input / canary / tool guards ────────────────────────────────────────

resource "aws_cloudwatch_log_metric_filter" "chat_input_blocked" {
  name           = "${local.name_prefix}-chat-input-blocked"
  log_group_name = local.chat_log_group_name
  pattern        = "{ $.message = \"chat.input.blocked\" }"

  metric_transformation {
    name          = "ChatInputBlockedCount"
    namespace     = local.chat_namespace
    value         = "1"
    default_value = "0"
  }
}

# Canary leak — counts ANY occurrence (happy-path and finalizer-path
# leaks both fire `chat.canary.leaked` ERROR; only the latter carries
# `finalizer_path=true`). The alarm below treats both as sev-1 per
# TD-099. Forensic split by `finalizer_path` is via Logs Insights.
resource "aws_cloudwatch_log_metric_filter" "chat_canary_leaked" {
  name           = "${local.name_prefix}-chat-canary-leaked"
  log_group_name = local.chat_log_group_name
  pattern        = "{ $.message = \"chat.canary.leaked\" }"

  metric_transformation {
    name          = "ChatCanaryLeakedCount"
    namespace     = local.chat_namespace
    value         = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_log_metric_filter" "chat_canary_load_failed" {
  name           = "${local.name_prefix}-chat-canary-load-failed"
  log_group_name = local.chat_log_group_name
  pattern        = "{ $.message = \"chat.canary.load_failed\" }"

  metric_transformation {
    name          = "ChatCanaryLoadFailedCount"
    namespace     = local.chat_namespace
    value         = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_log_metric_filter" "chat_tool_loop_exceeded" {
  name           = "${local.name_prefix}-chat-tool-loop-exceeded"
  log_group_name = local.chat_log_group_name
  pattern        = "{ $.message = \"chat.tool.loop_exceeded\" }"

  metric_transformation {
    name          = "ChatToolLoopExceededCount"
    namespace     = local.chat_namespace
    value         = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_log_metric_filter" "chat_tool_authorization_failed" {
  name           = "${local.name_prefix}-chat-tool-authorization-failed"
  log_group_name = local.chat_log_group_name
  pattern        = "{ $.message = \"chat.tool.authorization_failed\" }"

  metric_transformation {
    name          = "ChatToolAuthorizationFailedCount"
    namespace     = local.chat_namespace
    value         = "1"
    default_value = "0"
  }
}

# ─── Turn / citations / summarization ────────────────────────────────────

# chat.turn.completed → token-spend (numeric extraction, dimensioned by
# `user_bucket` per AC #6). Two metric transformations: one for the
# spend value (with bucket dim), one for an undimensioned turn count.
resource "aws_cloudwatch_log_metric_filter" "chat_turn_completed_token_spend" {
  name           = "${local.name_prefix}-chat-turn-completed-token-spend"
  log_group_name = local.chat_log_group_name
  pattern        = "{ $.message = \"chat.turn.completed\" && $.total_tokens_used = * && $.user_bucket = * }"

  metric_transformation {
    name      = "ChatTurnTotalTokensUsed"
    namespace = local.chat_namespace
    value     = "$.total_tokens_used"
    # NOTE: default_value is intentionally OMITTED — CloudWatch Logs
    # rejects the combo of `dimensions` + `default_value`
    # (InvalidParameterException: mutually exclusive). Dimensioned
    # filters publish nothing for unmatched log lines; the per-bucket
    # alarms below use treat_missing_data = "notBreaching" to handle
    # the missing-data semantics instead.
    dimensions = {
      UserBucket = "$.user_bucket"
    }
  }
}

# Undimensioned turn count for global rate denominators / refusal ratios.
resource "aws_cloudwatch_log_metric_filter" "chat_turn_completed" {
  name           = "${local.name_prefix}-chat-turn-completed"
  log_group_name = local.chat_log_group_name
  pattern        = "{ $.message = \"chat.turn.completed\" }"

  metric_transformation {
    name          = "ChatTurnCompletedCount"
    namespace     = local.chat_namespace
    value         = "1"
    default_value = "0"
  }
}

# Citation count — TD-123 close (AC #5). One metric filter, one metric
# stream; P50 and P95 are statistics applied at query time on this
# stream (the alarm below uses `extended_statistic = "p95"`; ad-hoc P50
# queries use the same metric name with stat `p50`). Story AC #5's
# literal "TWO metric filters" wording is a spec defect — duplicate
# filters double-bill IncomingLogEvents matches and produce identical
# streams. Documented in operator-runbook §Metric Inventory.
# Story 10.9 H3 + H4 fix: `chat.citations.attached` now fires
# unconditionally (with citation_count=0 when tools didn't run), so the
# P95-zero alarm has a heartbeat datapoint when the regression hits.
resource "aws_cloudwatch_log_metric_filter" "chat_citations_attached" {
  name           = "${local.name_prefix}-chat-citations-attached"
  log_group_name = local.chat_log_group_name
  pattern        = "{ $.message = \"chat.citations.attached\" && $.citation_count = * }"

  metric_transformation {
    name          = "ChatCitationCount"
    namespace     = local.chat_namespace
    value         = "$.citation_count"
    default_value = "0"
  }
}

resource "aws_cloudwatch_log_metric_filter" "chat_summarization_triggered" {
  name           = "${local.name_prefix}-chat-summarization-triggered"
  log_group_name = local.chat_log_group_name
  pattern        = "{ $.message = \"chat.summarization.triggered\" }"

  metric_transformation {
    name          = "ChatSummarizationTriggeredCount"
    namespace     = local.chat_namespace
    value         = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_log_metric_filter" "chat_summarization_failed" {
  name           = "${local.name_prefix}-chat-summarization-failed"
  log_group_name = local.chat_log_group_name
  pattern        = "{ $.message = \"chat.summarization.failed\" }"

  metric_transformation {
    name          = "ChatSummarizationFailedCount"
    namespace     = local.chat_namespace
    value         = "1"
    default_value = "0"
  }
}

# ── Alarms ───────────────────────────────────────────────────────────────
#
# All alarms gate behind var.enable_observability_alarms. SNS routing is
# optional: empty var.observability_sns_topic_arn → console-only.

# AC #3 row 2 — Grounding-block rate warn (≥10% over 15m).
resource "aws_cloudwatch_metric_alarm" "chat_grounding_block_rate_warn" {
  count = var.enable_observability_alarms ? 1 : 0

  alarm_name          = "${local.name_prefix}-chat-grounding-block-rate-warn"
  alarm_description   = "warn — Grounding-block rate (chat.stream.refused reason=ungrounded / chat.stream.opened) ≥10% sustained over 15m. Story 10.9 AC #3 row 2."
  comparison_operator = "GreaterThanOrEqualToThreshold"
  threshold           = 0.10
  evaluation_periods  = 3
  treat_missing_data  = "notBreaching"

  metric_query {
    id = "ungrounded"
    metric {
      metric_name = "ChatStreamRefusedUngroundedCount"
      namespace   = local.chat_namespace
      period      = 300
      stat        = "Sum"
    }
  }

  metric_query {
    id = "opened"
    metric {
      metric_name = "ChatStreamOpenedCount"
      namespace   = local.chat_namespace
      period      = 300
      stat        = "Sum"
    }
  }

  metric_query {
    id          = "rate"
    expression  = "IF(opened > 0, ungrounded / opened, 0)"
    label       = "Grounding-block rate"
    return_data = true
  }

  alarm_actions = var.observability_sns_topic_arn == "" ? [] : [var.observability_sns_topic_arn]

  tags = {
    Name     = "${local.name_prefix}-chat-grounding-block-rate-warn"
    Story    = "10.9"
    Severity = "warn"
  }
}

# AC #3 row 2 — Grounding-block rate page (≥25% over 5m × 3).
resource "aws_cloudwatch_metric_alarm" "chat_grounding_block_rate_page" {
  count = var.enable_observability_alarms ? 1 : 0

  alarm_name          = "${local.name_prefix}-chat-grounding-block-rate-page"
  alarm_description   = "page — Grounding-block rate ≥25% sustained over 5m × 3. Story 10.9 AC #3 row 2."
  comparison_operator = "GreaterThanOrEqualToThreshold"
  threshold           = 0.25
  evaluation_periods  = 3
  treat_missing_data  = "notBreaching"

  metric_query {
    id = "ungrounded"
    metric {
      metric_name = "ChatStreamRefusedUngroundedCount"
      namespace   = local.chat_namespace
      period      = 300
      stat        = "Sum"
    }
  }

  metric_query {
    id = "opened"
    metric {
      metric_name = "ChatStreamOpenedCount"
      namespace   = local.chat_namespace
      period      = 300
      stat        = "Sum"
    }
  }

  metric_query {
    id          = "rate"
    expression  = "IF(opened > 0, ungrounded / opened, 0)"
    label       = "Grounding-block rate"
    return_data = true
  }

  alarm_actions = var.observability_sns_topic_arn == "" ? [] : [var.observability_sns_topic_arn]

  tags = {
    Name     = "${local.name_prefix}-chat-grounding-block-rate-page"
    Story    = "10.9"
    Severity = "page"
  }
}

# AC #3 row 3 + AC #4 — Canary leak sev-1 (count > 0 over 5m). Closes TD-099.
resource "aws_cloudwatch_metric_alarm" "chat_canary_leaked_sev1" {
  count = var.enable_observability_alarms ? 1 : 0

  alarm_name          = "${local.name_prefix}-chat-canary-leaked-sev1"
  alarm_description   = "sev-1 — A chat canary token was detected in model output (chat.canary.leaked). Page security on-call. Forensic: split by finalizer_path via Logs Insights (see operator-runbook.md §Canary Leak Response). Story 10.9 AC #3 row 3 / TD-099."
  comparison_operator = "GreaterThanThreshold"
  threshold           = 0
  evaluation_periods  = 1
  period              = 300
  statistic           = "Sum"
  metric_name         = "ChatCanaryLeakedCount"
  namespace           = local.chat_namespace
  treat_missing_data  = "notBreaching"

  alarm_actions = var.observability_sns_topic_arn == "" ? [] : [var.observability_sns_topic_arn]

  tags = {
    Name     = "${local.name_prefix}-chat-canary-leaked-sev1"
    Story    = "10.9"
    Severity = "sev-1"
    TechDebt = "TD-099"
  }
}

# AC #4 — Stream finalizer failed sev-2 (count > 0 over 5m). Closes second
# half of TD-099.
resource "aws_cloudwatch_metric_alarm" "chat_stream_finalizer_failed_sev2" {
  count = var.enable_observability_alarms ? 1 : 0

  alarm_name          = "${local.name_prefix}-chat-stream-finalizer-failed-sev2"
  alarm_description   = "sev-2 — A chat stream's late-write finalizer raised an exception (chat.stream.finalizer_failed). Breaks Story 10.5a AC #14 invariant 4 (persistence on disconnect). Business-hours pager. Story 10.9 AC #4 / TD-099."
  comparison_operator = "GreaterThanThreshold"
  threshold           = 0
  evaluation_periods  = 1
  period              = 300
  statistic           = "Sum"
  metric_name         = "ChatStreamFinalizerFailedCount"
  namespace           = local.chat_namespace
  treat_missing_data  = "notBreaching"

  alarm_actions = var.observability_sns_topic_arn == "" ? [] : [var.observability_sns_topic_arn]

  tags = {
    Name     = "${local.name_prefix}-chat-stream-finalizer-failed-sev2"
    Story    = "10.9"
    Severity = "sev-2"
    TechDebt = "TD-099"
  }
}

# AC #3 row 4 — Refusal rate (all causes) warn (≥20% over 30m).
resource "aws_cloudwatch_metric_alarm" "chat_refusal_rate_warn" {
  count = var.enable_observability_alarms ? 1 : 0

  alarm_name          = "${local.name_prefix}-chat-refusal-rate-warn"
  alarm_description   = "warn — Overall refusal rate (chat.stream.refused / chat.stream.opened) ≥20% sustained over 30m. Story 10.9 AC #3 row 4."
  comparison_operator = "GreaterThanOrEqualToThreshold"
  threshold           = 0.20
  evaluation_periods  = 1
  treat_missing_data  = "notBreaching"

  metric_query {
    id = "refused"
    metric {
      metric_name = "ChatStreamRefusedCount"
      namespace   = local.chat_namespace
      period      = 1800
      stat        = "Sum"
    }
  }

  metric_query {
    id = "opened"
    metric {
      metric_name = "ChatStreamOpenedCount"
      namespace   = local.chat_namespace
      period      = 1800
      stat        = "Sum"
    }
  }

  metric_query {
    id          = "rate"
    expression  = "IF(opened > 0, refused / opened, 0)"
    label       = "Refusal rate"
    return_data = true
  }

  alarm_actions = var.observability_sns_topic_arn == "" ? [] : [var.observability_sns_topic_arn]

  tags = {
    Name     = "${local.name_prefix}-chat-refusal-rate-warn"
    Story    = "10.9"
    Severity = "warn"
  }
}

# AC #3 row 5 — Per-bucket token-spend anomaly (warn ≥3σ).
# `ChatTurnTotalTokensUsed` is published with dimension `UserBucket`
# (16 buckets). CloudWatch does NOT aggregate across dimensions, so we
# fan out one alarm per bucket via `for_each`; an alarm without a
# matching `dimensions` filter would see an empty stream.
# Story 10.9 H1 fix.
resource "aws_cloudwatch_metric_alarm" "chat_token_spend_anomaly_warn" {
  for_each = var.enable_observability_alarms ? toset(local.user_buckets) : toset([])

  alarm_name          = "${local.name_prefix}-chat-token-spend-anomaly-warn-${each.value}"
  alarm_description   = "warn — Per-bucket (UserBucket=${each.value}) chat token-spend anomaly (≥3σ vs trailing baseline). Bucketed by user_id_hash[0] (16 buckets) per Story 10.9 AC #6. Story 10.9 AC #3 row 5."
  comparison_operator = "LessThanLowerOrGreaterThanUpperThreshold"
  evaluation_periods  = 1
  threshold_metric_id = "band"
  treat_missing_data  = "notBreaching"

  metric_query {
    id          = "spend"
    return_data = true
    metric {
      metric_name = "ChatTurnTotalTokensUsed"
      namespace   = local.chat_namespace
      period      = 900
      stat        = "Sum"
      dimensions  = { UserBucket = each.value }
    }
  }

  metric_query {
    id         = "band"
    expression = "ANOMALY_DETECTION_BAND(spend, 3)"
    label      = "Token-spend anomaly band (3σ)"
    # MUST be true for anomaly-detection alarms — AWS PutMetricAlarm docs:
    # "the expression that contains the ANOMALY_DETECTION_BAND function,
    # and that expression's ReturnData field must be set to true."
    # Setting false produces ValidationError: "Metrics list must contain
    # exactly one metric matching the ThresholdMetricId parameter".
    return_data = true
  }

  alarm_actions = var.observability_sns_topic_arn == "" ? [] : [var.observability_sns_topic_arn]

  tags = {
    Name       = "${local.name_prefix}-chat-token-spend-anomaly-warn-${each.value}"
    Story      = "10.9"
    Severity   = "warn"
    UserBucket = each.value
  }
}

# AC #3 row 5 — Per-bucket token-spend anomaly (page ≥5σ).
resource "aws_cloudwatch_metric_alarm" "chat_token_spend_anomaly_page" {
  for_each = var.enable_observability_alarms ? toset(local.user_buckets) : toset([])

  alarm_name          = "${local.name_prefix}-chat-token-spend-anomaly-page-${each.value}"
  alarm_description   = "page — Per-bucket (UserBucket=${each.value}) chat token-spend anomaly (≥5σ vs trailing baseline). Story 10.9 AC #3 row 5."
  comparison_operator = "LessThanLowerOrGreaterThanUpperThreshold"
  evaluation_periods  = 1
  threshold_metric_id = "band"
  treat_missing_data  = "notBreaching"

  metric_query {
    id          = "spend"
    return_data = true
    metric {
      metric_name = "ChatTurnTotalTokensUsed"
      namespace   = local.chat_namespace
      period      = 900
      stat        = "Sum"
      dimensions  = { UserBucket = each.value }
    }
  }

  metric_query {
    id         = "band"
    expression = "ANOMALY_DETECTION_BAND(spend, 5)"
    label      = "Token-spend anomaly band (5σ)"
    # See sibling chat_token_spend_anomaly_warn for the AWS-API contract
    # rationale — anomaly-detection band must have return_data = true.
    return_data = true
  }

  alarm_actions = var.observability_sns_topic_arn == "" ? [] : [var.observability_sns_topic_arn]

  tags = {
    Name       = "${local.name_prefix}-chat-token-spend-anomaly-page-${each.value}"
    Story      = "10.9"
    Severity   = "page"
    UserBucket = each.value
  }
}

# AC #3 row 6 — P95 first-token latency warn (≥2s over 15m).
resource "aws_cloudwatch_metric_alarm" "chat_first_token_p95_warn" {
  count = var.enable_observability_alarms ? 1 : 0

  alarm_name          = "${local.name_prefix}-chat-first-token-p95-warn"
  alarm_description   = "warn — P95 chat first-token latency ≥2000ms over 15m (3 × 5m periods). Story 10.9 AC #3 row 6."
  comparison_operator = "GreaterThanOrEqualToThreshold"
  threshold           = 2000
  evaluation_periods  = 3
  period              = 300
  extended_statistic  = "p95"
  metric_name         = "ChatStreamFirstTokenLatencyMs"
  namespace           = local.chat_namespace
  treat_missing_data  = "notBreaching"

  alarm_actions = var.observability_sns_topic_arn == "" ? [] : [var.observability_sns_topic_arn]

  tags = {
    Name     = "${local.name_prefix}-chat-first-token-p95-warn"
    Story    = "10.9"
    Severity = "warn"
  }
}

# AC #3 row 6 — P95 first-token latency page (≥5s over 5m × 3).
resource "aws_cloudwatch_metric_alarm" "chat_first_token_p95_page" {
  count = var.enable_observability_alarms ? 1 : 0

  alarm_name          = "${local.name_prefix}-chat-first-token-p95-page"
  alarm_description   = "page — P95 chat first-token latency ≥5000ms over 5m × 3. Story 10.9 AC #3 row 6."
  comparison_operator = "GreaterThanOrEqualToThreshold"
  threshold           = 5000
  evaluation_periods  = 3
  period              = 300
  extended_statistic  = "p95"
  metric_name         = "ChatStreamFirstTokenLatencyMs"
  namespace           = local.chat_namespace
  treat_missing_data  = "notBreaching"

  alarm_actions = var.observability_sns_topic_arn == "" ? [] : [var.observability_sns_topic_arn]

  tags = {
    Name     = "${local.name_prefix}-chat-first-token-p95-page"
    Story    = "10.9"
    Severity = "page"
  }
}

# AC #5 — Citation count P95 == 0 over 30m (warn). Closes TD-123.
# Pairs with the H3 runtime fix in session_handler.py: when tools stop
# firing, `chat.citations.attached` still emits with `citation_count=0`,
# so this alarm sees a real datapoint instead of going INSUFFICIENT_DATA.
resource "aws_cloudwatch_metric_alarm" "chat_citation_count_p95_zero" {
  count = var.enable_observability_alarms ? 1 : 0

  alarm_name          = "${local.name_prefix}-chat-citation-count-p95-zero"
  alarm_description   = "warn — P95 chat citation count dropped to 0 over 30m (signal: tools stopped firing — regression). Story 10.9 AC #5 / TD-123."
  comparison_operator = "LessThanOrEqualToThreshold"
  threshold           = 0
  evaluation_periods  = 1
  period              = 1800
  extended_statistic  = "p95"
  metric_name         = "ChatCitationCount"
  namespace           = local.chat_namespace
  treat_missing_data  = "notBreaching"

  alarm_actions = var.observability_sns_topic_arn == "" ? [] : [var.observability_sns_topic_arn]

  tags = {
    Name     = "${local.name_prefix}-chat-citation-count-p95-zero"
    Story    = "10.9"
    Severity = "warn"
    TechDebt = "TD-123"
  }
}

# Canary-load-failed warn (count > 0 over 5m). Without a working canary
# secret the canary-leak detection layer is silently disabled, which
# turns the sev-1 alarm above into a no-op. This is not on AC #3's
# original metric table — added during code review to close the gap.
resource "aws_cloudwatch_metric_alarm" "chat_canary_load_failed_warn" {
  count = var.enable_observability_alarms ? 1 : 0

  alarm_name          = "${local.name_prefix}-chat-canary-load-failed-warn"
  alarm_description   = "warn — Canary secret failed to load (chat.canary.load_failed). Without a hydrated canary the chat-canary-leaked-sev1 detection layer is silently disabled. Investigate Secrets Manager + App Runner permissions before clearing."
  comparison_operator = "GreaterThanThreshold"
  threshold           = 0
  evaluation_periods  = 1
  period              = 300
  statistic           = "Sum"
  metric_name         = "ChatCanaryLoadFailedCount"
  namespace           = local.chat_namespace
  treat_missing_data  = "notBreaching"

  alarm_actions = var.observability_sns_topic_arn == "" ? [] : [var.observability_sns_topic_arn]

  tags = {
    Name     = "${local.name_prefix}-chat-canary-load-failed-warn"
    Story    = "10.9"
    Severity = "warn"
  }
}
