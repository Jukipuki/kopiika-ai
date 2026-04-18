"""Pure severity scoring logic for the Triage Agent (Story 8.3).

No LLM, no DB — just math. Two public functions score pattern findings and
detected subscriptions into one of {"critical", "warning", "info"} based on
either the user's monthly income (when known) or absolute UAH thresholds.
"""

# Income-relative thresholds (fraction of monthly income)
CRITICAL_INCOME_FRACTION = 0.20   # > 20% of monthly income
WARNING_INCOME_FRACTION = 0.05    # 5–20% of monthly income

# Absolute fallback thresholds in kopiykas (UAH × 100)
CRITICAL_ABS_KOPIYKAS = 200_000   # > 2,000 UAH
WARNING_ABS_KOPIYKAS = 50_000     # 500–2,000 UAH

# Subscription-specific absolute threshold in kopiykas
CRITICAL_SUB_KOPIYKAS = 50_000    # inactive sub > 500 UAH/month

# MoM change threshold for warning
WARNING_MOM_CHANGE_PCT = 25.0     # category increased > 25% MoM


def score_pattern_finding(finding: dict, monthly_income_kopiykas: int | None) -> str:
    """Score a pattern finding into 'critical', 'warning', or 'info'."""
    impact_kopiykas = abs(finding.get("current_amount_kopiykas", 0) or 0)
    change_percent = abs(finding.get("change_percent", 0.0) or 0.0)

    if monthly_income_kopiykas and monthly_income_kopiykas > 0:
        ratio = impact_kopiykas / monthly_income_kopiykas
        if ratio > CRITICAL_INCOME_FRACTION:
            return "critical"
        if ratio > WARNING_INCOME_FRACTION:
            return "warning"
        if change_percent > WARNING_MOM_CHANGE_PCT:
            return "warning"
        return "info"

    if impact_kopiykas > CRITICAL_ABS_KOPIYKAS:
        return "critical"
    if impact_kopiykas > WARNING_ABS_KOPIYKAS or change_percent > WARNING_MOM_CHANGE_PCT:
        return "warning"
    return "info"


def score_subscription(sub: dict, monthly_income_kopiykas: int | None) -> str:
    """Score a detected subscription into 'critical', 'warning', or 'info'.

    Inactive subscriptions costing more than CRITICAL_SUB_KOPIYKAS/month are
    always critical (AC: inactive > 500 UAH = critical), since the user is
    paying for something they no longer use.
    """
    monthly_cost = sub.get("estimated_monthly_cost_kopiykas", 0) or 0
    is_active = sub.get("is_active", True)

    if not is_active and monthly_cost > CRITICAL_SUB_KOPIYKAS:
        return "critical"

    if monthly_income_kopiykas and monthly_income_kopiykas > 0:
        ratio = monthly_cost / monthly_income_kopiykas
        if ratio > CRITICAL_INCOME_FRACTION:
            return "critical"
        if ratio > WARNING_INCOME_FRACTION:
            return "warning"
        return "info"

    if monthly_cost > CRITICAL_ABS_KOPIYKAS:
        return "critical"
    if monthly_cost > WARNING_ABS_KOPIYKAS:
        return "warning"
    return "info"
