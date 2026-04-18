"""Triage agent node (Story 8.3).

Runs between the pattern_detection and education nodes. Pure computation —
no LLM. Reads the persisted FinancialProfile to estimate monthly income,
then assigns a severity ('critical', 'warning', 'info') to each pattern
finding and detected subscription. Builds a category→worst-severity map so
the education node can override LLM-assigned severities for matching cards.

The node never halts the pipeline (AC #4): on any failure the original
findings/subscriptions are returned unmodified and the severity map is empty.
"""

import logging
import uuid

from app.agents.state import FinancialPipelineState
from app.agents.triage.severity import score_pattern_finding, score_subscription
from app.core.database import get_sync_session
from app.models.financial_profile import FinancialProfile
from sqlmodel import select

logger = logging.getLogger(__name__)

# Severity priority for "worst-per-category" reduction. Lower = more severe.
_SEVERITY_PRIORITY = {"critical": 0, "warning": 1, "info": 2}


def _estimate_monthly_income_kopiykas(user_id: str) -> int | None:
    """Read the user's FinancialProfile and estimate monthly income in kopiykas.

    Returns None when no profile exists, total_income is 0, or the period is
    incomplete — the caller treats None as "no income, use absolute thresholds".
    """
    user_uuid = uuid.UUID(user_id)
    with get_sync_session() as session:
        profile = session.exec(
            select(FinancialProfile).where(FinancialProfile.user_id == user_uuid)
        ).first()

    if not profile or profile.total_income <= 0:
        return None
    if not profile.period_start or not profile.period_end:
        return None

    months = max(1.0, (profile.period_end - profile.period_start).days / 30.0)
    return int(profile.total_income / months)


def _worst_severity_per_category(scored_findings: list[dict]) -> dict[str, str]:
    """Reduce findings to {category: worst_severity} — critical beats warning beats info."""
    out: dict[str, str] = {}
    for f in scored_findings:
        cat = f.get("category")
        sev = f.get("severity")
        if not cat or not sev:
            continue
        prev = out.get(cat)
        if prev is None or _SEVERITY_PRIORITY.get(sev, 2) < _SEVERITY_PRIORITY.get(prev, 2):
            out[cat] = sev
    return out


def triage_node(state: FinancialPipelineState) -> FinancialPipelineState:
    """LangGraph node: assign severity to findings/subscriptions; never halts pipeline."""
    job_id = state["job_id"]
    user_id = state["user_id"]
    log_ctx = {"job_id": job_id, "user_id": user_id, "step": "triage"}

    # DB lookup is isolated: its failure must not abort scoring — the spec
    # says "DB query fails: monthly_income = None, scoring continues with
    # absolute thresholds." A shared try/except would instead return the
    # findings unscored.
    try:
        monthly_income_kopiykas = _estimate_monthly_income_kopiykas(user_id)
    except Exception as db_exc:
        logger.warning(
            "triage_income_lookup_failed",
            extra={**log_ctx, "error": str(db_exc)},
        )
        monthly_income_kopiykas = None

    try:
        pattern_findings = state.get("pattern_findings", []) or []
        detected_subscriptions = state.get("detected_subscriptions", []) or []

        scored_findings = [
            {**f, "severity": score_pattern_finding(f, monthly_income_kopiykas)}
            for f in pattern_findings
        ]
        scored_subscriptions = [
            {**s, "severity": score_subscription(s, monthly_income_kopiykas)}
            for s in detected_subscriptions
        ]

        category_map = _worst_severity_per_category(scored_findings)

        critical_count = sum(1 for f in scored_findings if f.get("severity") == "critical")
        warning_count = sum(1 for f in scored_findings if f.get("severity") == "warning")
        logger.info(
            "triage_completed",
            extra={
                **log_ctx,
                "pattern_count": len(scored_findings),
                "subscription_count": len(scored_subscriptions),
                "critical_count": critical_count,
                "warning_count": warning_count,
                "monthly_income_available": bool(monthly_income_kopiykas),
            },
        )

        completed = list(state.get("completed_nodes", []))
        completed.append("triage")
        return {
            **state,
            "pattern_findings": scored_findings,
            "detected_subscriptions": scored_subscriptions,
            "triage_category_severity_map": category_map,
            "step": "triage",
            "completed_nodes": completed,
        }

    except Exception as exc:
        logger.error("triage_failed", extra={**log_ctx, "error": str(exc)}, exc_info=True)
        errors = list(state.get("errors", []))
        errors.append({
            "step": "triage",
            "error_code": "TRIAGE_FAILED",
            "message": str(exc),
        })
        return {
            **state,
            "errors": errors,
            "triage_category_severity_map": {},
            "step": "triage",
        }
