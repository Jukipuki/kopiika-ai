"""Tests for Pattern Detection Agent (Story 8.1)."""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, select

from app.agents.pattern_detection.node import pattern_detection_node
from app.agents.pattern_detection.detectors.trends import (
    detect_anomalies,
    detect_distribution,
    detect_trends,
)
from app.agents.state import FinancialPipelineState
from app.models.pattern_finding import PatternFinding
from app.models.upload import Upload
from app.models.user import User


# ---------------------------------------------------------------------------
# Sync SQLite fixtures (no async needed for agent tests)
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


@contextmanager
def _sync_session(engine):
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()


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
    }
    base.update(overrides)
    return base


def _txn(tid: str | None = None, date: str = "2026-03-15", amount: int = -10000, category_id: str | None = None) -> dict:
    return {
        "id": tid or str(uuid.uuid4()),
        "date": date,
        "description": "test",
        "mcc": None,
        "amount": amount,
    }


def _cat(transaction_id: str, category: str) -> dict:
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
    """Return a context manager factory that yields sessions from the test engine."""
    @contextmanager
    def _cm():
        session = Session(engine)
        try:
            yield session
        finally:
            session.close()
    return _cm


# ---------------------------------------------------------------------------
# Pure detector unit tests
# ---------------------------------------------------------------------------

def test_detect_trends_single_month_returns_empty():
    """Fewer than two distinct months → no trend findings."""
    txns = [_txn(amount=-10000, date="2026-03-10"), _txn(amount=-20000, date="2026-03-20")]
    cats = [_cat(t["id"], "food") for t in txns]
    assert detect_trends(txns, cats) == []


def test_detect_trends_month_over_month_positive_change():
    """Category rising >10% produces a trend finding with correct change_percent."""
    txns = [
        _txn(amount=-10000, date="2026-02-15"),  # baseline 100 UAH
        _txn(amount=-15000, date="2026-03-15"),  # current 150 UAH = +50%
    ]
    cats = [_cat(t["id"], "groceries") for t in txns]
    findings = detect_trends(txns, cats)
    assert len(findings) == 1
    assert findings[0]["pattern_type"] == "trend"
    assert findings[0]["category"] == "groceries"
    assert findings[0]["change_percent"] == pytest.approx(50.0)
    assert findings[0]["baseline_amount_kopiykas"] == 10000
    assert findings[0]["current_amount_kopiykas"] == 15000


def test_detect_trends_ignores_sub_threshold_change():
    """|change| < 10% produces no finding."""
    txns = [
        _txn(amount=-10000, date="2026-02-15"),
        _txn(amount=-10500, date="2026-03-15"),  # +5% — below threshold
    ]
    cats = [_cat(t["id"], "transport") for t in txns]
    assert detect_trends(txns, cats) == []


def test_detect_anomalies_outlier_detected():
    """Six transactions where one is 3× mean → one anomaly."""
    tids = [str(uuid.uuid4()) for _ in range(6)]
    txns = [
        _txn(tid=tids[0], amount=-10000, date="2026-03-01"),
        _txn(tid=tids[1], amount=-11000, date="2026-03-02"),
        _txn(tid=tids[2], amount=-9000, date="2026-03-03"),
        _txn(tid=tids[3], amount=-10500, date="2026-03-04"),
        _txn(tid=tids[4], amount=-9500, date="2026-03-05"),
        _txn(tid=tids[5], amount=-40000, date="2026-03-06"),  # outlier
    ]
    cats = [_cat(t["id"], "shopping") for t in txns]
    findings = detect_anomalies(txns, cats)
    anomalies = [f for f in findings if f["pattern_type"] == "anomaly"]
    assert len(anomalies) == 1
    assert anomalies[0]["finding_json"]["transaction_id"] == tids[5]
    assert anomalies[0]["finding_json"]["amount_kopiykas"] == 40000


def test_detect_anomalies_below_sample_threshold_no_findings():
    """Fewer than 5 txns in a category → no anomaly findings for that category."""
    txns = [
        _txn(amount=-10000, date="2026-03-01"),
        _txn(amount=-11000, date="2026-03-02"),
        _txn(amount=-40000, date="2026-03-03"),
    ]
    cats = [_cat(t["id"], "healthcare") for t in txns]
    assert detect_anomalies(txns, cats) == []


def test_detect_distribution_share_percent_correct():
    """Distribution returns share_percent summing to ~100% across categories in current month."""
    txns = [
        _txn(amount=-30000, date="2026-03-01"),  # 300 UAH → food
        _txn(amount=-20000, date="2026-03-02"),  # 200 UAH → food (total food=500)
        _txn(amount=-50000, date="2026-03-03"),  # 500 UAH → transport
    ]
    cats = [
        _cat(txns[0]["id"], "food"),
        _cat(txns[1]["id"], "food"),
        _cat(txns[2]["id"], "transport"),
    ]
    findings = detect_distribution(txns, cats)
    by_cat = {f["category"]: f for f in findings}
    assert by_cat["food"]["finding_json"]["share_percent"] == pytest.approx(50.0)
    assert by_cat["transport"]["finding_json"]["share_percent"] == pytest.approx(50.0)
    assert by_cat["food"]["finding_json"]["total_kopiykas"] == 100000


def test_detect_trends_excludes_income():
    """Positive amounts (income) are excluded from trend math."""
    tids = [str(uuid.uuid4()) for _ in range(3)]
    txns = [
        _txn(tid=tids[0], amount=-10000, date="2026-02-15"),
        _txn(tid=tids[1], amount=50000, date="2026-03-10"),  # income — skipped
        _txn(tid=tids[2], amount=-12000, date="2026-03-15"),  # +20%
    ]
    cats = [_cat(t["id"], "salary" if i == 1 else "food") for i, t in enumerate(txns)]
    findings = detect_trends(txns, cats)
    food = [f for f in findings if f["category"] == "food"]
    assert len(food) == 1
    assert food[0]["change_percent"] == pytest.approx(20.0)


# ---------------------------------------------------------------------------
# Node-level tests
# ---------------------------------------------------------------------------

def test_pattern_detection_node_intra_period_only_single_month(sync_engine):
    """Task 8.2: Single calendar month → distribution findings only, no trend findings."""
    user_id = uuid.uuid4()
    upload_id = uuid.uuid4()
    _seed_user_upload(sync_engine, user_id, upload_id)

    txns = [
        _txn(amount=-30000, date="2026-03-01"),
        _txn(amount=-20000, date="2026-03-10"),
        _txn(amount=-50000, date="2026-03-20"),
    ]
    cats = [_cat(t["id"], "groceries") for t in txns]
    state = _make_state(
        user_id=str(user_id),
        upload_id=str(upload_id),
        transactions=txns,
        categorized_transactions=cats,
    )

    with patch("app.agents.pattern_detection.node.get_sync_session", _patched_sync_session(sync_engine)):
        result = pattern_detection_node(state)

    types = {f["pattern_type"] for f in result["pattern_findings"]}
    assert "distribution" in types
    assert "trend" not in types
    assert "pattern_detection" in result["completed_nodes"]
    assert result["failed_node"] is None


def test_pattern_detection_node_month_over_month_trend(sync_engine):
    """Task 8.3: Two months with a category rising >10% → trend finding present."""
    user_id = uuid.uuid4()
    upload_id = uuid.uuid4()
    _seed_user_upload(sync_engine, user_id, upload_id)

    txns = [
        _txn(amount=-10000, date="2026-02-10"),
        _txn(amount=-10000, date="2026-02-20"),
        _txn(amount=-15000, date="2026-03-10"),  # current month: 150 UAH
        _txn(amount=-15000, date="2026-03-20"),  # current total: 300 UAH vs baseline 200 = +50%
    ]
    cats = [_cat(t["id"], "restaurants") for t in txns]
    state = _make_state(
        user_id=str(user_id),
        upload_id=str(upload_id),
        transactions=txns,
        categorized_transactions=cats,
    )

    with patch("app.agents.pattern_detection.node.get_sync_session", _patched_sync_session(sync_engine)):
        result = pattern_detection_node(state)

    trends = [f for f in result["pattern_findings"] if f["pattern_type"] == "trend"]
    assert len(trends) == 1
    assert trends[0]["category"] == "restaurants"
    assert trends[0]["change_percent"] == pytest.approx(50.0)


def test_pattern_detection_node_anomaly_detection(sync_engine):
    """Task 8.4: 6 txns in same category where one is 3× mean → one anomaly."""
    user_id = uuid.uuid4()
    upload_id = uuid.uuid4()
    _seed_user_upload(sync_engine, user_id, upload_id)

    tids = [str(uuid.uuid4()) for _ in range(6)]
    txns = [
        _txn(tid=tids[0], amount=-10000, date="2026-03-01"),
        _txn(tid=tids[1], amount=-11000, date="2026-03-02"),
        _txn(tid=tids[2], amount=-9000, date="2026-03-03"),
        _txn(tid=tids[3], amount=-10500, date="2026-03-04"),
        _txn(tid=tids[4], amount=-9500, date="2026-03-05"),
        _txn(tid=tids[5], amount=-40000, date="2026-03-06"),
    ]
    cats = [_cat(t["id"], "shopping") for t in txns]
    state = _make_state(
        user_id=str(user_id),
        upload_id=str(upload_id),
        transactions=txns,
        categorized_transactions=cats,
    )

    with patch("app.agents.pattern_detection.node.get_sync_session", _patched_sync_session(sync_engine)):
        result = pattern_detection_node(state)

    anomalies = [f for f in result["pattern_findings"] if f["pattern_type"] == "anomaly"]
    assert len(anomalies) == 1
    assert anomalies[0]["finding_json"]["transaction_id"] == tids[5]


def test_pattern_detection_node_below_sample_size_no_anomaly(sync_engine):
    """Task 8.5: <5 txns in a category → no anomaly findings for that category."""
    user_id = uuid.uuid4()
    upload_id = uuid.uuid4()
    _seed_user_upload(sync_engine, user_id, upload_id)

    txns = [
        _txn(amount=-10000, date="2026-03-01"),
        _txn(amount=-11000, date="2026-03-02"),
        _txn(amount=-40000, date="2026-03-03"),
    ]
    cats = [_cat(t["id"], "healthcare") for t in txns]
    state = _make_state(
        user_id=str(user_id),
        upload_id=str(upload_id),
        transactions=txns,
        categorized_transactions=cats,
    )

    with patch("app.agents.pattern_detection.node.get_sync_session", _patched_sync_session(sync_engine)):
        result = pattern_detection_node(state)

    anomalies = [f for f in result["pattern_findings"] if f["pattern_type"] == "anomaly"]
    assert anomalies == []


def test_pattern_detection_node_empty_categorized_early_exit(sync_engine):
    """Task 8.6: Empty categorized_transactions → pattern_findings=[], no DB writes, state intact."""
    user_id = uuid.uuid4()
    upload_id = uuid.uuid4()
    _seed_user_upload(sync_engine, user_id, upload_id)

    state = _make_state(
        user_id=str(user_id),
        upload_id=str(upload_id),
        transactions=[],
        categorized_transactions=[],
    )

    with patch("app.agents.pattern_detection.node.get_sync_session", _patched_sync_session(sync_engine)):
        result = pattern_detection_node(state)

    assert result["pattern_findings"] == []
    assert "pattern_detection" in result["completed_nodes"]
    with Session(sync_engine) as session:
        rows = session.exec(select(PatternFinding)).all()
        assert rows == []


def test_pattern_detection_node_unhandled_exception_does_not_crash(sync_engine):
    """Task 8.7: Detector raising → node returns state, failed_node='pattern_detection', education can still run."""
    user_id = uuid.uuid4()
    upload_id = uuid.uuid4()
    _seed_user_upload(sync_engine, user_id, upload_id)

    txn = _txn(amount=-10000, date="2026-03-01")
    state = _make_state(
        user_id=str(user_id),
        upload_id=str(upload_id),
        transactions=[txn],
        categorized_transactions=[_cat(txn["id"], "shopping")],
    )

    with (
        patch("app.agents.pattern_detection.node.detect_trends", side_effect=RuntimeError("boom")),
        patch("app.agents.pattern_detection.node.get_sync_session", _patched_sync_session(sync_engine)),
    ):
        result = pattern_detection_node(state)

    assert result["pattern_findings"] == []
    assert result["failed_node"] == "pattern_detection"
    assert "pattern_detection" not in result["completed_nodes"]
    assert any(e["step"] == "pattern_detection" for e in result["errors"])


def test_pattern_detection_node_sse_publish_failure_does_not_drop_findings(sync_engine):
    """Redis outage during SSE publish must not roll back state or persisted rows.

    Regression: previously the publish_job_progress call sat inside the same
    try/except as persist, so a Redis error caused the node to return
    pattern_findings=[] and failed_node='pattern_detection' even though the
    rows had already been committed. State/DB would diverge.
    """
    user_id = uuid.uuid4()
    upload_id = uuid.uuid4()
    _seed_user_upload(sync_engine, user_id, upload_id)

    txns = [
        _txn(amount=-30000, date="2026-03-01"),
        _txn(amount=-20000, date="2026-03-10"),
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
            "app.agents.pattern_detection.node.publish_job_progress",
            side_effect=RuntimeError("redis down"),
        ),
        patch("app.agents.pattern_detection.node.get_sync_session", _patched_sync_session(sync_engine)),
    ):
        result = pattern_detection_node(state)

    # State keeps the findings and marks the node completed (not failed).
    assert result["pattern_findings"], "findings dropped despite successful persist"
    assert "pattern_detection" in result["completed_nodes"]
    assert result["failed_node"] is None

    # DB rows exist.
    with Session(sync_engine) as session:
        rows = session.exec(
            select(PatternFinding).where(PatternFinding.upload_id == upload_id)
        ).all()
        assert len(rows) == len(result["pattern_findings"])


def test_pattern_detection_node_persists_findings_to_db(sync_engine):
    """Task 8.8: After node runs, expected rows exist in pattern_findings filtered by upload_id."""
    user_id = uuid.uuid4()
    upload_id = uuid.uuid4()
    _seed_user_upload(sync_engine, user_id, upload_id)

    txns = [
        _txn(amount=-30000, date="2026-03-01"),
        _txn(amount=-20000, date="2026-03-10"),
        _txn(amount=-50000, date="2026-03-20"),
    ]
    cats = [_cat(t["id"], "restaurants") for t in txns]
    state = _make_state(
        user_id=str(user_id),
        upload_id=str(upload_id),
        transactions=txns,
        categorized_transactions=cats,
    )

    with patch("app.agents.pattern_detection.node.get_sync_session", _patched_sync_session(sync_engine)):
        pattern_detection_node(state)

    with Session(sync_engine) as session:
        rows = session.exec(
            select(PatternFinding).where(PatternFinding.upload_id == upload_id)
        ).all()
        assert len(rows) >= 1
        assert all(r.user_id == user_id for r in rows)
        assert all(r.pattern_type in {"trend", "anomaly", "distribution"} for r in rows)
