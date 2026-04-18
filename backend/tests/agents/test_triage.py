"""Tests for Triage Agent (Story 8.3)."""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel

from app.agents.state import FinancialPipelineState
from app.agents.triage.node import triage_node
from app.agents.triage.severity import score_pattern_finding, score_subscription
from app.models.financial_profile import FinancialProfile
from app.models.user import User


# ---------------------------------------------------------------------------
# Sync SQLite fixtures (mirrors test_pattern_detection.py)
# ---------------------------------------------------------------------------

@pytest.fixture
def sync_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)
    engine.dispose()


def _patched_sync_session(engine):
    @contextmanager
    def _cm():
        session = Session(engine)
        try:
            yield session
        finally:
            session.close()
    return _cm


def _make_state(**overrides) -> FinancialPipelineState:
    base: FinancialPipelineState = {
        "job_id": str(uuid.uuid4()),
        "user_id": str(uuid.uuid4()),
        "upload_id": str(uuid.uuid4()),
        "transactions": [],
        "categorized_transactions": [],
        "errors": [],
        "step": "triage",
        "total_tokens_used": 0,
        "locale": "uk",
        "insight_cards": [],
        "literacy_level": "beginner",
        "completed_nodes": ["categorization", "pattern_detection"],
        "failed_node": None,
        "pattern_findings": [],
        "detected_subscriptions": [],
        "triage_category_severity_map": {},
    }
    base.update(overrides)
    return base


def _seed_user_with_profile(engine, user_id: uuid.UUID, total_income: int, period_days: int = 30) -> None:
    end = datetime(2026, 4, 1)
    start = end - timedelta(days=period_days)
    with Session(engine) as session:
        session.add(User(
            id=user_id,
            email=f"{user_id}@test.com",
            cognito_sub=f"sub-{user_id}",
            locale="uk",
        ))
        session.flush()
        session.add(FinancialProfile(
            user_id=user_id,
            total_income=total_income,
            total_expenses=0,
            period_start=start,
            period_end=end,
        ))
        session.commit()


# ---------------------------------------------------------------------------
# score_pattern_finding — pure function tests
# ---------------------------------------------------------------------------

def test_score_pattern_finding_income_relative_critical():
    """25% of monthly income → critical (>20% threshold)."""
    finding = {"current_amount_kopiykas": 250_000, "change_percent": 0.0}
    assert score_pattern_finding(finding, monthly_income_kopiykas=1_000_000) == "critical"


def test_score_pattern_finding_income_relative_warning():
    """10% of monthly income → warning (between 5% and 20%)."""
    finding = {"current_amount_kopiykas": 100_000, "change_percent": 0.0}
    assert score_pattern_finding(finding, monthly_income_kopiykas=1_000_000) == "warning"


def test_score_pattern_finding_income_relative_info():
    """3% of income, MoM 10% → info (below all thresholds)."""
    finding = {"current_amount_kopiykas": 30_000, "change_percent": 10.0}
    assert score_pattern_finding(finding, monthly_income_kopiykas=1_000_000) == "info"


def test_score_pattern_finding_mom_change_triggers_warning():
    """3% of income but MoM 30% → warning (MoM check fires below income fraction)."""
    finding = {"current_amount_kopiykas": 30_000, "change_percent": 30.0}
    assert score_pattern_finding(finding, monthly_income_kopiykas=1_000_000) == "warning"


def test_score_pattern_finding_absolute_fallback_critical():
    """No income, 3,000 UAH impact → critical via absolute threshold."""
    finding = {"current_amount_kopiykas": 300_000, "change_percent": 0.0}
    assert score_pattern_finding(finding, monthly_income_kopiykas=None) == "critical"


def test_score_pattern_finding_absolute_fallback_info():
    """No income, 100 UAH impact, MoM 5% → info."""
    finding = {"current_amount_kopiykas": 10_000, "change_percent": 5.0}
    assert score_pattern_finding(finding, monthly_income_kopiykas=None) == "info"


# ---------------------------------------------------------------------------
# score_subscription — pure function tests
# ---------------------------------------------------------------------------

def test_score_subscription_inactive_above_threshold_is_critical():
    """Inactive sub costing 600 UAH/mo → critical regardless of income."""
    sub = {"estimated_monthly_cost_kopiykas": 60_000, "is_active": False}
    assert score_subscription(sub, monthly_income_kopiykas=10_000_000) == "critical"


def test_score_subscription_active_below_threshold_is_info():
    """Active sub costing 100 UAH/mo, no income → info."""
    sub = {"estimated_monthly_cost_kopiykas": 10_000, "is_active": True}
    assert score_subscription(sub, monthly_income_kopiykas=None) == "info"


def test_score_subscription_income_relative_critical():
    """Active sub at 25% of monthly income (> 20%) → critical."""
    sub = {"estimated_monthly_cost_kopiykas": 250_000, "is_active": True}
    assert score_subscription(sub, monthly_income_kopiykas=1_000_000) == "critical"


def test_score_subscription_income_relative_warning():
    """Active sub at 10% of monthly income (5–20%) → warning."""
    sub = {"estimated_monthly_cost_kopiykas": 100_000, "is_active": True}
    assert score_subscription(sub, monthly_income_kopiykas=1_000_000) == "warning"


def test_score_subscription_income_relative_info():
    """Active sub at 3% of monthly income (< 5%) → info."""
    sub = {"estimated_monthly_cost_kopiykas": 30_000, "is_active": True}
    assert score_subscription(sub, monthly_income_kopiykas=1_000_000) == "info"


# ---------------------------------------------------------------------------
# triage_node — integration tests
# ---------------------------------------------------------------------------

def test_triage_node_adds_severity_to_pattern_findings(sync_engine):
    """Each finding in returned state has 'severity' set."""
    user_id = uuid.uuid4()
    state = _make_state(
        user_id=str(user_id),
        pattern_findings=[{
            "pattern_type": "trend",
            "category": "food",
            "current_amount_kopiykas": 300_000,
            "change_percent": 0.0,
        }],
    )

    with patch("app.agents.triage.node.get_sync_session", _patched_sync_session(sync_engine)):
        result = triage_node(state)

    assert "severity" in result["pattern_findings"][0]
    assert result["pattern_findings"][0]["severity"] in {"critical", "warning", "info"}
    assert "triage" in result["completed_nodes"]


def test_triage_node_adds_severity_to_detected_subscriptions(sync_engine):
    """Each detected subscription in returned state has 'severity' set."""
    user_id = uuid.uuid4()
    state = _make_state(
        user_id=str(user_id),
        detected_subscriptions=[{
            "merchant_name": "Spotify",
            "estimated_monthly_cost_kopiykas": 15_000,
            "billing_frequency": "monthly",
            "last_charge_date": "2026-03-15",
            "is_active": True,
            "months_with_no_activity": 0,
        }],
    )

    with patch("app.agents.triage.node.get_sync_session", _patched_sync_session(sync_engine)):
        result = triage_node(state)

    assert "severity" in result["detected_subscriptions"][0]


def test_triage_node_reads_financial_profile_for_income(sync_engine):
    """With a small monthly income, a 1,000 UAH finding becomes critical via income ratio
    (would be only 'warning' on absolute thresholds)."""
    user_id = uuid.uuid4()
    # Income 4,000 UAH/month → 400_000 kopiykas/month
    _seed_user_with_profile(sync_engine, user_id, total_income=400_000, period_days=30)

    state = _make_state(
        user_id=str(user_id),
        pattern_findings=[{
            "pattern_type": "trend",
            "category": "entertainment",
            "current_amount_kopiykas": 100_000,  # 1,000 UAH — 25% of income → critical
            "change_percent": 0.0,
        }],
    )

    with patch("app.agents.triage.node.get_sync_session", _patched_sync_session(sync_engine)):
        result = triage_node(state)

    # Without income this would be "warning" (>500 UAH absolute, <2000 UAH).
    # With income known and ratio 25% > 20% → critical.
    assert result["pattern_findings"][0]["severity"] == "critical"


def test_triage_node_failure_does_not_halt_pipeline(sync_engine):
    """Patch scorer to raise — node returns state with errors appended, originals preserved."""
    user_id = uuid.uuid4()
    original_findings = [{
        "pattern_type": "trend",
        "category": "food",
        "current_amount_kopiykas": 100_000,
        "change_percent": 0.0,
    }]
    state = _make_state(
        user_id=str(user_id),
        pattern_findings=list(original_findings),
    )

    with (
        patch(
            "app.agents.triage.node.score_pattern_finding",
            side_effect=RuntimeError("boom"),
        ),
        patch("app.agents.triage.node.get_sync_session", _patched_sync_session(sync_engine)),
    ):
        result = triage_node(state)

    # State returned, no raise
    assert isinstance(result, dict)
    # Errors appended
    assert any(e["step"] == "triage" for e in result["errors"])
    # Originals preserved (no severity added)
    assert result["pattern_findings"] == original_findings
    assert "severity" not in result["pattern_findings"][0]
    # Empty severity map on failure
    assert result["triage_category_severity_map"] == {}


def test_triage_node_db_failure_falls_back_to_absolute_thresholds(sync_engine):
    """If the FinancialProfile lookup raises, scoring continues with
    monthly_income=None (absolute thresholds) — the node does NOT bail."""
    user_id = uuid.uuid4()
    state = _make_state(
        user_id=str(user_id),
        pattern_findings=[{
            "pattern_type": "trend",
            "category": "food",
            "current_amount_kopiykas": 300_000,  # > 2,000 UAH → absolute critical
            "change_percent": 0.0,
        }],
    )

    with patch(
        "app.agents.triage.node._estimate_monthly_income_kopiykas",
        side_effect=RuntimeError("db connection lost"),
    ):
        result = triage_node(state)

    # Scoring MUST proceed using absolute thresholds.
    assert result["pattern_findings"][0]["severity"] == "critical"
    # No triage-level error recorded — DB failure is degraded, not fatal.
    assert not any(e.get("step") == "triage" for e in result.get("errors", []))
    # Node marks itself as completed.
    assert "triage" in result["completed_nodes"]


def test_triage_category_severity_map_takes_worst_per_category(sync_engine):
    """Two findings in 'food' (warning + critical) → map['food'] == 'critical'."""
    user_id = uuid.uuid4()
    state = _make_state(
        user_id=str(user_id),
        pattern_findings=[
            {
                "pattern_type": "trend",
                "category": "food",
                "current_amount_kopiykas": 80_000,   # absolute warning (>500 UAH, <2,000)
                "change_percent": 0.0,
            },
            {
                "pattern_type": "anomaly",
                "category": "food",
                "current_amount_kopiykas": 300_000,  # absolute critical (>2,000 UAH)
                "change_percent": 0.0,
            },
        ],
    )

    with patch("app.agents.triage.node.get_sync_session", _patched_sync_session(sync_engine)):
        result = triage_node(state)

    assert result["triage_category_severity_map"]["food"] == "critical"
