"""Tests for the Subscription Detection detector and node wiring (Story 8.2)."""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import date
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, select

from app.agents.pattern_detection.detectors.recurring import (
    _normalize_merchant,
    detect_subscriptions,
)
from app.agents.pattern_detection.node import pattern_detection_node
from app.agents.state import FinancialPipelineState
from app.models.detected_subscription import DetectedSubscription
from app.models.pattern_finding import PatternFinding
from app.models.upload import Upload
from app.models.user import User


# ---------------------------------------------------------------------------
# Sync SQLite fixtures (no async needed for agent tests) — same pattern as
# test_pattern_detection.py.
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


def _make_state(**overrides) -> FinancialPipelineState:
    base: FinancialPipelineState = {
        "job_id": str(uuid.uuid4()),
        "user_id": str(uuid.uuid4()),
        "upload_id": str(uuid.uuid4()),
        "transactions": [],
        "categorized_transactions": [],
        "errors": [],
        "step": "pattern_detection",
        "total_tokens_used": 0,
        "locale": "uk",
        "insight_cards": [],
        "literacy_level": "beginner",
        "completed_nodes": [],
        "failed_node": None,
        "pattern_findings": [],
        "detected_subscriptions": [],
    }
    base.update(overrides)
    return base


def _txn(
    description: str = "Netflix UA",
    date_str: str = "2026-03-15",
    amount: int = -30000,
    tid: str | None = None,
) -> dict:
    return {
        "id": tid or str(uuid.uuid4()),
        "date": date_str,
        "description": description,
        "mcc": None,
        "amount": amount,
    }


def _cat(transaction_id: str, category: str = "subscriptions") -> dict:
    return {
        "transaction_id": transaction_id,
        "category": category,
        "confidence_score": 1.0,
        "flagged": False,
        "uncategorized_reason": None,
    }


def _seed_user_upload(engine, user_id: uuid.UUID, upload_id: uuid.UUID) -> None:
    with Session(engine) as session:
        session.add(User(
            id=user_id,
            email=f"{user_id}@test.com",
            cognito_sub=f"sub-{user_id}",
            locale="uk",
        ))
        session.flush()
        session.add(Upload(
            id=upload_id, user_id=user_id, file_name="test.csv",
            s3_key=f"{user_id}/test.csv", file_size=1024,
            mime_type="text/csv", detected_format="monobank",
            detected_encoding="utf-8", detected_delimiter=";",
        ))
        session.commit()


def _patched_sync_session(engine):
    """Factory returning a context manager that yields sessions from the test engine."""
    @contextmanager
    def _cm():
        session = Session(engine)
        try:
            yield session
        finally:
            session.close()
    return _cm


# ---------------------------------------------------------------------------
# Pure detector unit tests (Task 13.2–13.7)
# ---------------------------------------------------------------------------

def test_normalize_merchant_case_insensitive_match():
    """'Netflix UA', 'NETFLIX UA', 'netflix ua' all produce the same bucket key."""
    assert _normalize_merchant("Netflix UA") == _normalize_merchant("NETFLIX UA")
    assert _normalize_merchant("Netflix UA") == _normalize_merchant("netflix ua")


def test_normalize_merchant_strips_trailing_digits_and_prefixes():
    """Trailing digits and Ukrainian/English prefixes are stripped."""
    assert _normalize_merchant("Netflix UA 123") == "netflix ua"
    assert _normalize_merchant("оплата Netflix") == "netflix"
    assert _normalize_merchant("transfer Spotify") == "spotify"


def test_normalize_merchant_preserves_prefix_like_words_without_boundary():
    """Prefix stripping requires a boundary — 'transferwise' must stay intact."""
    assert _normalize_merchant("TransferWise") == "transferwise"
    assert _normalize_merchant("commissionfee") == "commissionfee"


def test_monthly_subscription_detected_active():
    """3 transactions ~30 days apart with consistent amounts → monthly subscription."""
    txns = [
        _txn(date_str="2026-01-15", amount=-30000),
        _txn(date_str="2026-02-14", amount=-30000),
        _txn(date_str="2026-03-16", amount=-30000),
    ]
    today = date(2026, 3, 20)
    result = detect_subscriptions(txns, today=today)
    assert len(result) == 1
    sub = result[0]
    # Display name preserves original casing from the bank statement rather
    # than the lowercase bucket key.
    assert sub["merchant_name"] == "Netflix UA"
    assert sub["billing_frequency"] == "monthly"
    assert sub["estimated_monthly_cost_kopiykas"] == 30000
    assert sub["is_active"] is True
    assert sub["months_with_no_activity"] is None
    assert sub["last_charge_date"] == "2026-03-16"


def test_annual_subscription_detected():
    """2 transactions ~365 days apart with same amount → annual subscription."""
    txns = [
        _txn(description="Adobe Creative Cloud", date_str="2025-03-10", amount=-600000),
        _txn(description="Adobe Creative Cloud", date_str="2026-03-09", amount=-600000),
    ]
    today = date(2026, 3, 15)
    result = detect_subscriptions(txns, today=today)
    assert len(result) == 1
    sub = result[0]
    assert sub["billing_frequency"] == "annual"
    # annual cost spread across 12 months
    assert sub["estimated_monthly_cost_kopiykas"] == 50000
    assert sub["is_active"] is True


def test_amount_inconsistency_rejects_subscription():
    """One transaction > 5% off the mean → no subscription emitted."""
    txns = [
        _txn(date_str="2026-01-15", amount=-30000),
        _txn(date_str="2026-02-14", amount=-30000),
        _txn(date_str="2026-03-15", amount=-40000),  # > 5% above mean
    ]
    result = detect_subscriptions(txns, today=date(2026, 3, 20))
    assert result == []


def test_single_transaction_per_merchant_returns_empty():
    """One transaction per merchant is not enough for a subscription."""
    txns = [
        _txn(description="Netflix UA", date_str="2026-03-15", amount=-30000),
        _txn(description="Spotify", date_str="2026-03-18", amount=-15000),
    ]
    result = detect_subscriptions(txns, today=date(2026, 3, 20))
    assert result == []


def test_income_transactions_excluded():
    """Positive amounts are skipped even at monthly cadence."""
    txns = [
        _txn(description="Employer payroll", date_str="2026-01-15", amount=5000000),
        _txn(description="Employer payroll", date_str="2026-02-14", amount=5000000),
        _txn(description="Employer payroll", date_str="2026-03-15", amount=5000000),
    ]
    result = detect_subscriptions(txns, today=date(2026, 3, 20))
    assert result == []


def test_inactive_monthly_subscription_sets_months_inactive():
    """last_charge > 35 days ago → is_active=False, months_with_no_activity >= 1."""
    txns = [
        _txn(date_str="2026-01-10", amount=-30000),
        _txn(date_str="2026-02-10", amount=-30000),
        _txn(date_str="2026-03-10", amount=-30000),
    ]
    today = date(2026, 4, 19)  # 40 days after last charge
    result = detect_subscriptions(txns, today=today)
    assert len(result) == 1
    sub = result[0]
    assert sub["is_active"] is False
    assert sub["months_with_no_activity"] >= 1


def test_two_consecutive_monthly_gaps_sufficient():
    """Exactly 2 consecutive monthly gaps qualify as a subscription."""
    txns = [
        _txn(date_str="2026-01-15", amount=-30000),
        _txn(date_str="2026-02-14", amount=-30000),
        _txn(date_str="2026-03-16", amount=-30000),
    ]
    result = detect_subscriptions(txns, today=date(2026, 3, 20))
    assert len(result) == 1


def test_irregular_gaps_rejected():
    """Gaps outside the monthly/annual buckets → no subscription."""
    txns = [
        _txn(date_str="2026-01-01", amount=-30000),
        _txn(date_str="2026-01-10", amount=-30000),  # 9-day gap
        _txn(date_str="2026-02-01", amount=-30000),  # 22-day gap
    ]
    result = detect_subscriptions(txns, today=date(2026, 3, 1))
    assert result == []


# ---------------------------------------------------------------------------
# Node-level tests (Task 13.8, 13.9)
# ---------------------------------------------------------------------------

def test_pattern_detection_node_persists_subscriptions_to_db(sync_engine):
    """After the node runs, detected_subscriptions rows exist for this upload."""
    user_id = uuid.uuid4()
    upload_id = uuid.uuid4()
    _seed_user_upload(sync_engine, user_id, upload_id)

    txns = [
        _txn(description="Netflix UA", date_str="2026-01-15", amount=-30000),
        _txn(description="Netflix UA", date_str="2026-02-14", amount=-30000),
        _txn(description="Netflix UA", date_str="2026-03-16", amount=-30000),
    ]
    cats = [_cat(t["id"]) for t in txns]
    state = _make_state(
        user_id=str(user_id),
        upload_id=str(upload_id),
        transactions=txns,
        categorized_transactions=cats,
    )

    with patch(
        "app.agents.pattern_detection.node.get_sync_session",
        _patched_sync_session(sync_engine),
    ):
        result = pattern_detection_node(state)

    assert result["detected_subscriptions"]
    assert result["detected_subscriptions"][0]["merchant_name"] == "Netflix UA"

    with Session(sync_engine) as session:
        rows = session.exec(
            select(DetectedSubscription).where(
                DetectedSubscription.upload_id == upload_id
            )
        ).all()
        assert len(rows) == 1
        assert rows[0].merchant_name == "Netflix UA"
        assert rows[0].billing_frequency == "monthly"
        assert rows[0].user_id == user_id


def test_pattern_detection_node_subscription_error_does_not_crash_pipeline(sync_engine):
    """Recurring detector exception → detected_subscriptions=[] but pattern findings persist."""
    user_id = uuid.uuid4()
    upload_id = uuid.uuid4()
    _seed_user_upload(sync_engine, user_id, upload_id)

    # Enough transactions to produce distribution findings from the other detectors.
    txns = [
        _txn(description="Store A", date_str="2026-03-01", amount=-30000),
        _txn(description="Store A", date_str="2026-03-10", amount=-20000),
        _txn(description="Store B", date_str="2026-03-20", amount=-50000),
    ]
    cats = [_cat(t["id"], "groceries") for t in txns]
    state = _make_state(
        user_id=str(user_id),
        upload_id=str(upload_id),
        transactions=txns,
        categorized_transactions=cats,
    )

    with (
        patch(
            "app.agents.pattern_detection.node.detect_subscriptions",
            side_effect=RuntimeError("boom"),
        ),
        patch(
            "app.agents.pattern_detection.node.get_sync_session",
            _patched_sync_session(sync_engine),
        ),
    ):
        result = pattern_detection_node(state)

    assert result["detected_subscriptions"] == []
    assert result["pattern_findings"], "pattern findings must still be populated"
    assert result["failed_node"] is None
    assert any(
        e.get("error_code") == "SUBSCRIPTION_DETECTION_FAILED"
        for e in result["errors"]
    )

    with Session(sync_engine) as session:
        pattern_rows = session.exec(
            select(PatternFinding).where(PatternFinding.upload_id == upload_id)
        ).all()
        assert pattern_rows, "trend/distribution findings must be persisted"
        sub_rows = session.exec(
            select(DetectedSubscription).where(
                DetectedSubscription.upload_id == upload_id
            )
        ).all()
        assert sub_rows == []


def test_pattern_detection_node_trend_failure_still_runs_subscription_detection(
    sync_engine,
):
    """Symmetric isolation: trend-family failure must not suppress subscription detection."""
    user_id = uuid.uuid4()
    upload_id = uuid.uuid4()
    _seed_user_upload(sync_engine, user_id, upload_id)

    txns = [
        _txn(description="Netflix UA", date_str="2026-01-15", amount=-30000),
        _txn(description="Netflix UA", date_str="2026-02-14", amount=-30000),
        _txn(description="Netflix UA", date_str="2026-03-16", amount=-30000),
    ]
    cats = [_cat(t["id"], "subscriptions") for t in txns]
    state = _make_state(
        user_id=str(user_id),
        upload_id=str(upload_id),
        transactions=txns,
        categorized_transactions=cats,
    )

    with (
        patch(
            "app.agents.pattern_detection.node.detect_trends",
            side_effect=RuntimeError("boom"),
        ),
        patch(
            "app.agents.pattern_detection.node.get_sync_session",
            _patched_sync_session(sync_engine),
        ),
    ):
        result = pattern_detection_node(state)

    # Trend family failed → failed_node set, pattern_findings empty.
    assert result["pattern_findings"] == []
    assert result["failed_node"] == "pattern_detection"
    assert any(e.get("error_code") == "DETECTION_FAILED" for e in result["errors"])

    # Subscription detection still ran and persisted.
    assert result["detected_subscriptions"], "subscriptions must survive trend failure"
    assert result["detected_subscriptions"][0]["merchant_name"] == "Netflix UA"

    with Session(sync_engine) as session:
        sub_rows = session.exec(
            select(DetectedSubscription).where(
                DetectedSubscription.upload_id == upload_id
            )
        ).all()
        assert len(sub_rows) == 1
        assert sub_rows[0].merchant_name == "Netflix UA"
