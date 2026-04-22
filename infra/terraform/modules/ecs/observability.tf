# Story 11.9 — Observability signals for the ingestion & categorization pipeline.
#
# One metric filter per tracked structured log event, plus two alarms covering
# the two high-signal dashboards from tech-spec §9. Alarm actions are
# intentionally empty: SNS / PagerDuty wiring is a separate ops story. Alarms
# remain visible in the AWS console and can be subscribed to later via
# var.observability_sns_topic_arn.
#
# Log patterns assume the JSON shape produced by backend/app/core/logging.py's
# JsonFormatter (Story 6.4). The `$.message` accessor points at the event name
# promoted to a top-level JSON key. If a future refactor of JsonFormatter ever
# renames that key, update the patterns here in lockstep.

locals {
  observability_namespace = "Kopiika/Ingestion"
}

# ── Metric filters (one per tracked event / dimension) ────────────────────

resource "aws_cloudwatch_log_metric_filter" "confidence_tier_queue" {
  name           = "${local.name_prefix}-confidence-tier-queue"
  log_group_name = aws_cloudwatch_log_group.worker.name
  pattern        = "{ $.level = \"INFO\" && $.message = \"categorization.confidence_tier\" && $.tier = \"queue\" }"

  metric_transformation {
    name          = "ConfidenceTierQueueCount"
    namespace     = local.observability_namespace
    value         = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_log_metric_filter" "confidence_tier_softflag" {
  name           = "${local.name_prefix}-confidence-tier-softflag"
  log_group_name = aws_cloudwatch_log_group.worker.name
  pattern        = "{ $.level = \"INFO\" && $.message = \"categorization.confidence_tier\" && $.tier = \"soft-flag\" }"

  metric_transformation {
    name          = "ConfidenceTierSoftFlagCount"
    namespace     = local.observability_namespace
    value         = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_log_metric_filter" "kind_mismatch" {
  name           = "${local.name_prefix}-kind-mismatch"
  log_group_name = aws_cloudwatch_log_group.worker.name
  pattern        = "{ $.message = \"categorization.kind_mismatch\" }"

  metric_transformation {
    name          = "KindMismatchCount"
    namespace     = local.observability_namespace
    value         = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_log_metric_filter" "validation_rejected" {
  name           = "${local.name_prefix}-validation-rejected"
  log_group_name = aws_cloudwatch_log_group.worker.name
  pattern        = "{ $.message = \"parser.validation_rejected\" }"

  metric_transformation {
    name          = "ValidationRejectedCount"
    namespace     = local.observability_namespace
    value         = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_log_metric_filter" "mojibake_detected" {
  name           = "${local.name_prefix}-mojibake-detected"
  log_group_name = aws_cloudwatch_log_group.worker.name
  pattern        = "{ $.message = \"parser.mojibake_detected\" }"

  metric_transformation {
    name          = "MojibakeDetectedCount"
    namespace     = local.observability_namespace
    value         = "1"
    default_value = "0"
  }
}

# Info-level signal only — spec §9 explicitly states "AI schema detection
# failure → info log, no alert". Metric is still published so the runbook
# panel can render a trend, but no alarm is attached.
resource "aws_cloudwatch_log_metric_filter" "schema_detection_fallback" {
  name           = "${local.name_prefix}-schema-detection-fallback"
  log_group_name = aws_cloudwatch_log_group.worker.name
  pattern        = "{ $.message = \"parser.schema_detection\" && $.source = \"fallback_generic\" }"

  metric_transformation {
    name          = "SchemaDetectionFallbackCount"
    namespace     = local.observability_namespace
    value         = "1"
    default_value = "0"
  }
}

# Denominator metrics extracted from the pipeline_completed event (Story 6.5).
# Needed for the rate-based alarms in this file.
resource "aws_cloudwatch_log_metric_filter" "pipeline_categorization_count" {
  name           = "${local.name_prefix}-pipeline-categorization-count"
  log_group_name = aws_cloudwatch_log_group.worker.name
  pattern        = "{ $.message = \"pipeline_completed\" && $.categorization_count = * }"

  metric_transformation {
    name          = "TotalCategorizedTxCount"
    namespace     = local.observability_namespace
    value         = "$.categorization_count"
    default_value = "0"
  }
}

resource "aws_cloudwatch_log_metric_filter" "pipeline_total_rows" {
  name           = "${local.name_prefix}-pipeline-total-rows"
  log_group_name = aws_cloudwatch_log_group.worker.name
  pattern        = "{ $.message = \"pipeline_completed\" && $.total_rows = * }"

  metric_transformation {
    name          = "TotalRowsCount"
    namespace     = local.observability_namespace
    value         = "$.total_rows"
    default_value = "0"
  }
}

# ── Alarms ────────────────────────────────────────────────────────────────
#
# Two rate-based alarms gated on var.enable_observability_alarms so a lone
# developer in dev isn't paged by a synthetic load test.

# NOTE: This alarm is a proxy for "median categorization confidence < 0.85" —
# a true median/P50 would need Embedded Metric Format (EMF) histograms.
# See TD-050 in docs/tech-debt.md for the follow-on.
resource "aws_cloudwatch_metric_alarm" "categorization_low_confidence_median" {
  count = var.enable_observability_alarms ? 1 : 0

  alarm_name          = "${local.name_prefix}-categorization-low-confidence-median"
  alarm_description   = "Warn when >50% of categorizations fall below the auto-apply threshold over 24h. Proxy for median confidence < 0.85 — see TD-050 for EMF-based follow-on."
  comparison_operator = "GreaterThanThreshold"
  threshold           = 0.5
  evaluation_periods  = 1
  treat_missing_data  = "notBreaching"

  metric_query {
    id          = "below_auto"
    expression  = "queue + soft"
    label       = "Below-auto-apply count"
    return_data = false
  }

  metric_query {
    id = "queue"
    metric {
      metric_name = "ConfidenceTierQueueCount"
      namespace   = local.observability_namespace
      period      = 86400
      stat        = "Sum"
    }
  }

  metric_query {
    id = "soft"
    metric {
      metric_name = "ConfidenceTierSoftFlagCount"
      namespace   = local.observability_namespace
      period      = 86400
      stat        = "Sum"
    }
  }

  metric_query {
    id = "total"
    metric {
      metric_name = "TotalCategorizedTxCount"
      namespace   = local.observability_namespace
      period      = 86400
      stat        = "Sum"
    }
  }

  metric_query {
    id          = "ratio"
    expression  = "IF(total > 0, below_auto / total, 0)"
    label       = "Fraction below auto-apply"
    return_data = true
  }

  alarm_actions = var.observability_sns_topic_arn == "" ? [] : [var.observability_sns_topic_arn]
  ok_actions    = var.observability_sns_topic_arn == "" ? [] : [var.observability_sns_topic_arn]

  tags = {
    Name     = "${local.name_prefix}-categorization-low-confidence-median"
    Story    = "11.9"
    TechDebt = "TD-050"
  }
}

resource "aws_cloudwatch_metric_alarm" "validation_rejection_rate_high" {
  count = var.enable_observability_alarms ? 1 : 0

  alarm_name          = "${local.name_prefix}-validation-rejection-rate-high"
  alarm_description   = "Warn when parser validation rejects >15% of rows over 24h."
  comparison_operator = "GreaterThanThreshold"
  threshold           = 0.15
  evaluation_periods  = 1
  treat_missing_data  = "notBreaching"

  metric_query {
    id = "rejected"
    metric {
      metric_name = "ValidationRejectedCount"
      namespace   = local.observability_namespace
      period      = 86400
      stat        = "Sum"
    }
  }

  metric_query {
    id = "total"
    metric {
      metric_name = "TotalRowsCount"
      namespace   = local.observability_namespace
      period      = 86400
      stat        = "Sum"
    }
  }

  metric_query {
    id          = "ratio"
    expression  = "IF(total > 0, rejected / total, 0)"
    label       = "Validation rejection rate"
    return_data = true
  }

  alarm_actions = var.observability_sns_topic_arn == "" ? [] : [var.observability_sns_topic_arn]
  ok_actions    = var.observability_sns_topic_arn == "" ? [] : [var.observability_sns_topic_arn]

  tags = {
    Name  = "${local.name_prefix}-validation-rejection-rate-high"
    Story = "11.9"
  }
}
