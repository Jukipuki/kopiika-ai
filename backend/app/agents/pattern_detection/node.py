"""Pattern detection agent node (Story 8.1).

Runs between the categorization and education nodes. Uses pure statistical
detectors — no LLM — to emit trend, anomaly, and distribution findings, then
persists them to the pattern_findings table.
"""

import logging
import uuid
from datetime import date

from app.agents.pattern_detection.detectors.trends import (
    detect_anomalies,
    detect_distribution,
    detect_trends,
)
from app.agents.state import FinancialPipelineState
from app.core.database import get_sync_session
from app.core.redis import publish_job_progress
from app.models.pattern_finding import PatternFinding

logger = logging.getLogger(__name__)


def _to_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _persist_findings(
    findings: list[dict],
    user_id: str,
    upload_id: str,
) -> None:
    if not findings:
        return
    user_uuid = uuid.UUID(user_id)
    upload_uuid = uuid.UUID(upload_id)
    with get_sync_session() as session:
        for f in findings:
            session.add(PatternFinding(
                user_id=user_uuid,
                upload_id=upload_uuid,
                pattern_type=f["pattern_type"],
                category=f.get("category"),
                period_start=_to_date(f.get("period_start")),
                period_end=_to_date(f.get("period_end")),
                baseline_amount_kopiykas=f.get("baseline_amount_kopiykas"),
                current_amount_kopiykas=f.get("current_amount_kopiykas"),
                change_percent=f.get("change_percent"),
                finding_json=f.get("finding_json", {}),
            ))
        session.commit()


def pattern_detection_node(state: FinancialPipelineState) -> FinancialPipelineState:
    """LangGraph node: detect trends/anomalies/distribution over categorized transactions."""
    job_id = state["job_id"]
    user_id = state["user_id"]
    upload_id = state["upload_id"]
    log_ctx = {"job_id": job_id, "user_id": user_id, "step": "pattern_detection"}

    categorized = state.get("categorized_transactions", [])
    if not categorized:
        logger.warning("pattern_detection_skipped_no_categorized", extra=log_ctx)
        completed = list(state.get("completed_nodes", []))
        completed.append("pattern_detection")
        return {
            **state,
            "pattern_findings": [],
            "step": "pattern_detection",
            "completed_nodes": completed,
        }

    transactions = state.get("transactions", [])

    try:
        trend_findings = detect_trends(transactions, categorized)
        anomaly_findings = detect_anomalies(transactions, categorized)
        distribution_findings = detect_distribution(transactions, categorized)
        all_findings = [*trend_findings, *anomaly_findings, *distribution_findings]

        _persist_findings(all_findings, user_id, upload_id)
    except Exception as exc:
        logger.error(
            "pattern_detection_failed",
            extra={**log_ctx, "error": str(exc)},
            exc_info=True,
        )
        errors = list(state.get("errors", []))
        errors.append({
            "step": "pattern_detection",
            "error_code": "DETECTION_FAILED",
            "message": str(exc),
        })
        return {
            **state,
            "pattern_findings": [],
            "errors": errors,
            "step": "pattern_detection",
            "failed_node": state.get("failed_node") or "pattern_detection",
        }

    # SSE publish is outside the persist try/except: findings are already
    # committed to the DB, so a Redis failure here must not cause the node
    # to report failure or drop findings from state.
    try:
        publish_job_progress(job_id, {
            "event": "pipeline-progress",
            "jobId": job_id,
            "step": "pattern-detection",
            "progress": 55,
            "message": "Detecting spending patterns...",
        })
    except Exception as publish_exc:
        logger.warning(
            "pattern_detection_sse_publish_failed",
            extra={**log_ctx, "error": str(publish_exc)},
        )

    logger.info(
        "pattern_detection_completed",
        extra={
            **log_ctx,
            "trend_count": len(trend_findings),
            "anomaly_count": len(anomaly_findings),
            "distribution_count": len(distribution_findings),
        },
    )
    completed = list(state.get("completed_nodes", []))
    completed.append("pattern_detection")
    return {
        **state,
        "pattern_findings": all_findings,
        "step": "pattern_detection",
        "completed_nodes": completed,
    }
