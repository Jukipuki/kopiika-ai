# AWS Budgets — top-line account budget plus a Bedrock-specific budget that
# acts as defense-in-depth against the github_bedrock_ci OIDC role being
# abused for cost-attack on PR-triggered workflows.

resource "aws_budgets_budget" "monthly_total" {
  name              = "${local.name_prefix}-monthly-total"
  budget_type       = "COST"
  limit_amount      = tostring(var.monthly_budget_usd)
  limit_unit        = "USD"
  time_unit         = "MONTHLY"
  # Hardcoded to a past month-start so this resource is creation-only —
  # AWS Budgets requires a start date, but evaluating from a past date does
  # not retroactively alarm; budgets calculate forward from the current
  # month. Re-creating in 2027+ would NOT pull historical spend (a common
  # misconception). Leave as-is unless creating a brand-new account.
  time_period_start = "2026-04-01_00:00"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = var.alarm_email != "" ? [var.alarm_email] : []
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = var.alarm_email != "" ? [var.alarm_email] : []
  }
}

resource "aws_budgets_budget" "bedrock_monthly" {
  name              = "${local.name_prefix}-bedrock-monthly"
  budget_type       = "COST"
  limit_amount      = tostring(var.bedrock_monthly_budget_usd)
  limit_unit        = "USD"
  time_unit         = "MONTHLY"
  # Hardcoded to a past month-start so this resource is creation-only —
  # AWS Budgets requires a start date, but evaluating from a past date does
  # not retroactively alarm; budgets calculate forward from the current
  # month. Re-creating in 2027+ would NOT pull historical spend (a common
  # misconception). Leave as-is unless creating a brand-new account.
  time_period_start = "2026-04-01_00:00"

  cost_filter {
    name   = "Service"
    values = ["Amazon Bedrock"]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = var.alarm_email != "" ? [var.alarm_email] : []
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = var.alarm_email != "" ? [var.alarm_email] : []
  }
}
