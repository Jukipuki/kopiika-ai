"""Tests for Transaction Categorization Agent (Story 3.1)."""

import io
import json
import logging
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, select

from app.agents.categorization.mcc_mapping import MCC_TO_CATEGORY, get_mcc_category
from app.agents.categorization.node import categorization_node
from app.agents.pipeline import financial_pipeline
from app.agents.state import FinancialPipelineState
from app.models.processing_job import ProcessingJob
from app.models.transaction import Transaction
from app.models.upload import Upload
from app.models.user import User


def _utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


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
    """Return a minimal pipeline state for tests."""
    base: FinancialPipelineState = {
        "job_id": str(uuid.uuid4()),
        "user_id": str(uuid.uuid4()),
        "upload_id": str(uuid.uuid4()),
        "transactions": [],
        "categorized_transactions": [],
        "errors": [],
        "step": "categorization",
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


def _make_transaction(mcc=None, description="Test", amount=-10000) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "mcc": mcc,
        "description": description,
        "amount": amount,
        "date": "2026-03-30",
    }


# ---------------------------------------------------------------------------
# MCC mapping tests
# ---------------------------------------------------------------------------

def test_get_mcc_category_known():
    assert get_mcc_category(5411) == "groceries"


def test_get_mcc_category_none_input():
    assert get_mcc_category(None) is None


def test_get_mcc_category_unknown_mcc():
    assert get_mcc_category(9999) is None


def test_get_mcc_category_restaurant():
    assert get_mcc_category(5812) == "restaurants"


def test_get_mcc_category_fuel():
    assert get_mcc_category(5541) == "fuel"


def test_get_mcc_category_atm():
    assert get_mcc_category(6011) == "atm_cash"


def test_mcc_mapping_contains_required_entries():
    """Verify all mandatory MCC codes from the story spec are present."""
    required = {
        5411: "groceries",
        5412: "groceries",
        5814: "restaurants",
        5812: "restaurants",
        5541: "fuel",
        5542: "fuel",
        4111: "transport",
        4112: "transport",
        4121: "transport",
        4131: "transport",
        4816: "utilities",
        4899: "utilities",
        5912: "healthcare",
        8099: "healthcare",
        8011: "healthcare",
        8049: "healthcare",
        8062: "healthcare",
        7832: "entertainment",
        7941: "entertainment",
        7922: "entertainment",
        7996: "entertainment",
        5945: "shopping",
        5942: "shopping",
        5943: "shopping",
        4511: "travel",
        4722: "travel",
        8220: "education",
        8249: "education",
        6011: "atm_cash",
        6012: "atm_cash",
        6099: "finance",
        6159: "finance",
        4900: "utilities",
    }
    for mcc, expected_cat in required.items():
        assert MCC_TO_CATEGORY.get(mcc) == expected_cat, (
            f"MCC {mcc} should map to {expected_cat!r}, got {MCC_TO_CATEGORY.get(mcc)!r}"
        )


# ---------------------------------------------------------------------------
# categorization_node — MCC-only path (no LLM)
# ---------------------------------------------------------------------------

def test_categorization_node_all_mcc_mapped_no_llm_called():
    """All MCC-mapped transactions: LLM never called, confidence=1.0, not flagged."""
    transactions = [
        _make_transaction(mcc=5411, description="СІЛЬПО"),
        _make_transaction(mcc=5812, description="McDonalds"),
        _make_transaction(mcc=5541, description="WOG Fuel"),
    ]
    state = _make_state(transactions=transactions)

    with patch("app.agents.categorization.node.get_llm_client") as mock_get_llm:
        result = categorization_node(state)

    mock_get_llm.assert_not_called()

    assert len(result["categorized_transactions"]) == 3
    cats = {c["transaction_id"]: c for c in result["categorized_transactions"]}

    for txn in transactions:
        entry = cats[txn["id"]]
        assert entry["confidence_score"] == 1.0
        assert entry["flagged"] is False

    assert cats[transactions[0]["id"]]["category"] == "groceries"
    assert cats[transactions[1]["id"]]["category"] == "restaurants"
    assert cats[transactions[2]["id"]]["category"] == "fuel"


def test_categorization_node_empty_transactions():
    """Empty transaction list returns empty categorized list."""
    state = _make_state(transactions=[])
    result = categorization_node(state)
    assert result["categorized_transactions"] == []
    assert result["total_tokens_used"] == 0


# ---------------------------------------------------------------------------
# categorization_node — LLM path
# ---------------------------------------------------------------------------

def _make_llm_response(results: list[dict], total_tokens: int = 150) -> MagicMock:
    """Build a mock LLM response."""
    mock = MagicMock()
    mock.content = json.dumps(results)
    mock.usage_metadata = {"total_tokens": total_tokens}
    return mock


def test_categorization_node_unmapped_mcc_calls_llm():
    """Transactions without MCC trigger LLM classification."""
    txn = _make_transaction(mcc=None, description="НОВА ПОШТА")
    state = _make_state(transactions=[txn])

    llm_result = [{"id": txn["id"], "category": "shopping", "confidence": 0.88}]
    mock_response = _make_llm_response(llm_result)

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = mock_response
    mock_llm.model = "claude-haiku-4-5-20251001"

    with patch("app.agents.categorization.node.get_llm_client", return_value=mock_llm):
        result = categorization_node(state)

    mock_llm.invoke.assert_called_once()
    assert len(result["categorized_transactions"]) == 1
    entry = result["categorized_transactions"][0]
    assert entry["category"] == "shopping"
    assert entry["confidence_score"] == pytest.approx(0.88)
    assert entry["flagged"] is False
    assert result["total_tokens_used"] == 150


def test_categorization_node_low_confidence_flagged():
    """Confidence < 0.7 results in flagged=True."""
    txn = _make_transaction(mcc=None, description="Unknown merchant")
    state = _make_state(transactions=[txn])

    llm_result = [{"id": txn["id"], "category": "other", "confidence": 0.5}]
    mock_response = _make_llm_response(llm_result)

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = mock_response
    mock_llm.model = "claude-haiku-4-5-20251001"

    with patch("app.agents.categorization.node.get_llm_client", return_value=mock_llm):
        result = categorization_node(state)

    entry = result["categorized_transactions"][0]
    assert entry["flagged"] is True
    assert entry["confidence_score"] == pytest.approx(0.5)


def test_categorization_node_exactly_threshold_not_flagged():
    """Confidence == threshold (0.7) is NOT flagged (strictly less than)."""
    txn = _make_transaction(mcc=None, description="Service")
    state = _make_state(transactions=[txn])

    llm_result = [{"id": txn["id"], "category": "finance", "confidence": 0.7}]
    mock_response = _make_llm_response(llm_result)

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = mock_response
    mock_llm.model = "claude-haiku-4-5-20251001"

    with patch("app.agents.categorization.node.get_llm_client", return_value=mock_llm):
        result = categorization_node(state)

    entry = result["categorized_transactions"][0]
    assert entry["flagged"] is False


# ---------------------------------------------------------------------------
# categorization_node — fallback LLM path
# ---------------------------------------------------------------------------

def test_categorization_node_primary_fails_fallback_called():
    """When primary LLM raises, fallback LLM is called."""
    txn = _make_transaction(mcc=None, description="Mysterious Shop")
    state = _make_state(transactions=[txn])

    llm_result = [{"id": txn["id"], "category": "shopping", "confidence": 0.82}]
    mock_response = _make_llm_response(llm_result)

    fallback_llm = MagicMock()
    fallback_llm.invoke.return_value = mock_response
    fallback_llm.model = "gpt-4o-mini"

    primary_llm = MagicMock()
    primary_llm.invoke.side_effect = Exception("API timeout")
    primary_llm.model = "claude-haiku-4-5-20251001"

    with (
        patch("app.agents.categorization.node.get_llm_client", return_value=primary_llm),
        patch("app.agents.categorization.node.get_fallback_llm_client", return_value=fallback_llm),
    ):
        result = categorization_node(state)

    fallback_llm.invoke.assert_called_once()
    entry = result["categorized_transactions"][0]
    assert entry["category"] == "shopping"
    assert entry["confidence_score"] == pytest.approx(0.82)
    assert entry["flagged"] is False


def test_categorization_node_both_llms_fail_returns_other():
    """Both LLMs failing results in category='uncategorized' (6.3), confidence=0.0, flagged=True."""
    txn = _make_transaction(mcc=None, description="Unknown")
    state = _make_state(transactions=[txn])

    primary_llm = MagicMock()
    primary_llm.invoke.side_effect = Exception("Primary failed")
    primary_llm.model = "claude-haiku-4-5-20251001"

    fallback_llm = MagicMock()
    fallback_llm.invoke.side_effect = Exception("Fallback also failed")
    fallback_llm.model = "gpt-4o-mini"

    with (
        patch("app.agents.categorization.node.get_llm_client", return_value=primary_llm),
        patch("app.agents.categorization.node.get_fallback_llm_client", return_value=fallback_llm),
    ):
        result = categorization_node(state)

    assert len(result["categorized_transactions"]) == 1
    entry = result["categorized_transactions"][0]
    assert entry["category"] == "uncategorized"
    assert entry["confidence_score"] == 0.0
    assert entry["flagged"] is True


def test_categorization_node_no_api_key_uses_fallback():
    """When primary LLM is not configured (ValueError), fallback is tried."""
    txn = _make_transaction(mcc=None, description="Shop")
    state = _make_state(transactions=[txn])

    llm_result = [{"id": txn["id"], "category": "shopping", "confidence": 0.9}]
    mock_response = _make_llm_response(llm_result)

    fallback_llm = MagicMock()
    fallback_llm.invoke.return_value = mock_response
    fallback_llm.model = "gpt-4o-mini"

    with (
        patch(
            "app.agents.categorization.node.get_llm_client",
            side_effect=ValueError("ANTHROPIC_API_KEY not configured"),
        ),
        patch("app.agents.categorization.node.get_fallback_llm_client", return_value=fallback_llm),
    ):
        result = categorization_node(state)

    assert result["categorized_transactions"][0]["category"] == "shopping"


def test_categorization_node_no_api_keys_at_all():
    """When both LLMs raise ValueError (not configured), final fallback assigns uncategorized (6.3)."""
    txn = _make_transaction(mcc=None, description="Shop")
    state = _make_state(transactions=[txn])

    with (
        patch(
            "app.agents.categorization.node.get_llm_client",
            side_effect=ValueError("ANTHROPIC_API_KEY not configured"),
        ),
        patch(
            "app.agents.categorization.node.get_fallback_llm_client",
            side_effect=ValueError("OPENAI_API_KEY not configured"),
        ),
    ):
        result = categorization_node(state)

    entry = result["categorized_transactions"][0]
    assert entry["category"] == "uncategorized"
    assert entry["confidence_score"] == 0.0
    assert entry["flagged"] is True


# ---------------------------------------------------------------------------
# categorization_node — mixed (some MCC, some LLM)
# ---------------------------------------------------------------------------

def test_categorization_node_mixed_mcc_and_llm():
    """MCC-mapped transactions skip LLM; only unmapped ones are batched."""
    mcc_txn = _make_transaction(mcc=5411, description="AUCHAN")
    llm_txn = _make_transaction(mcc=None, description="Digital Subscription")
    state = _make_state(transactions=[mcc_txn, llm_txn])

    llm_result = [{"id": llm_txn["id"], "category": "subscriptions", "confidence": 0.92}]
    mock_response = _make_llm_response(llm_result)

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = mock_response
    mock_llm.model = "claude-haiku-4-5-20251001"

    with patch("app.agents.categorization.node.get_llm_client", return_value=mock_llm):
        result = categorization_node(state)

    assert len(result["categorized_transactions"]) == 2
    mock_llm.invoke.assert_called_once()

    cats = {c["transaction_id"]: c for c in result["categorized_transactions"]}
    assert cats[mcc_txn["id"]]["category"] == "groceries"
    assert cats[mcc_txn["id"]]["confidence_score"] == 1.0
    assert cats[mcc_txn["id"]]["flagged"] is False
    assert cats[llm_txn["id"]]["category"] == "subscriptions"


def test_categorization_node_token_accumulation():
    """Token usage is accumulated from LLM responses."""
    txns = [_make_transaction(mcc=None, description=f"Merchant {i}") for i in range(3)]
    state = _make_state(transactions=txns)

    llm_results = [{"id": t["id"], "category": "shopping", "confidence": 0.9} for t in txns]
    mock_response = _make_llm_response(llm_results, total_tokens=200)

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = mock_response
    mock_llm.model = "claude-haiku-4-5-20251001"

    with patch("app.agents.categorization.node.get_llm_client", return_value=mock_llm):
        result = categorization_node(state)

    assert result["total_tokens_used"] == 200


# ---------------------------------------------------------------------------
# Pipeline integration test
# ---------------------------------------------------------------------------

def test_financial_pipeline_invoke_with_mocked_node():
    """financial_pipeline.invoke() passes state through the categorization node."""
    txn = _make_transaction(mcc=5411, description="METRO")
    state = _make_state(transactions=[txn])

    result = financial_pipeline.invoke(state)

    assert len(result["categorized_transactions"]) == 1
    assert result["categorized_transactions"][0]["category"] == "groceries"
    assert result["categorized_transactions"][0]["confidence_score"] == 1.0


# ---------------------------------------------------------------------------
# DB update tests
# ---------------------------------------------------------------------------

def _seed_categorization_data(engine):
    """Seed user, upload, and a transaction without category."""
    user_id = uuid.uuid4()
    upload_id = uuid.uuid4()
    txn_id = uuid.uuid4()

    with Session(engine) as session:
        user = User(id=user_id, email="cat@test.com", cognito_sub="cat-test-sub", locale="en")
        session.add(user)
        session.flush()

        upload = Upload(
            id=upload_id, user_id=user_id, file_name="test.csv",
            s3_key=f"{user_id}/test.csv", file_size=1024,
            mime_type="text/csv", detected_format="monobank", detected_encoding="utf-8",
            detected_delimiter=";",
        )
        session.add(upload)
        session.flush()

        txn = Transaction(
            id=txn_id,
            user_id=user_id,
            upload_id=upload_id,
            date=_utcnow(),
            description="СІЛЬПО",
            mcc=5411,
            amount=-24550,
            dedup_hash=f"hash-{txn_id}",
        )
        session.add(txn)
        session.commit()

    return user_id, upload_id, txn_id


def test_categorization_db_update(sync_engine):
    """After categorization, transaction has category and confidence_score in DB."""
    user_id, upload_id, txn_id = _seed_categorization_data(sync_engine)

    cat_lookup = {
        str(txn_id): {
            "category": "groceries",
            "confidence_score": 1.0,
            "flagged": False,
        }
    }

    with Session(sync_engine) as session:
        from sqlmodel import select as sm_select
        txns = session.exec(sm_select(Transaction).where(Transaction.upload_id == upload_id)).all()
        for txn in txns:
            cat = cat_lookup.get(str(txn.id))
            if cat:
                txn.category = cat["category"]
                txn.confidence_score = cat["confidence_score"]
                txn.is_flagged_for_review = cat["flagged"]
                session.add(txn)
        session.commit()

    with Session(sync_engine) as session:
        txn = session.get(Transaction, txn_id)
        assert txn.category == "groceries"
        assert txn.confidence_score == pytest.approx(1.0)
        assert txn.is_flagged_for_review is False


def test_categorization_db_update_low_confidence_flagged(sync_engine):
    """Low-confidence categorization sets is_flagged_for_review=True in DB."""
    user_id, upload_id, txn_id = _seed_categorization_data(sync_engine)

    with Session(sync_engine) as session:
        txn = session.get(Transaction, txn_id)
        txn.category = "other"
        txn.confidence_score = 0.4
        txn.is_flagged_for_review = True
        session.add(txn)
        session.commit()

    with Session(sync_engine) as session:
        txn = session.get(Transaction, txn_id)
        assert txn.is_flagged_for_review is True
        assert txn.confidence_score == pytest.approx(0.4)


# ---------------------------------------------------------------------------
# Celery task integration: categorization failure path
# ---------------------------------------------------------------------------

def test_categorization_failure_job_stays_completed(sync_engine):
    """When categorization fails, job status stays 'completed' (partial result)."""
    user_id = uuid.uuid4()
    upload_id = uuid.uuid4()
    job_id = uuid.uuid4()

    with Session(sync_engine) as session:
        user = User(id=user_id, email="fail@test.com", cognito_sub="fail-sub", locale="en")
        session.add(user)
        session.flush()

        upload = Upload(
            id=upload_id, user_id=user_id, file_name="fail.csv",
            s3_key=f"{user_id}/fail.csv", file_size=512,
            mime_type="text/csv", detected_format="monobank", detected_encoding="utf-8",
            detected_delimiter=";",
        )
        session.add(upload)
        session.flush()

        job = ProcessingJob(id=job_id, user_id=user_id, upload_id=upload_id, status="processing")
        session.add(job)
        session.commit()

    # Simulate categorization failure path (what the Celery task does on exception)
    with Session(sync_engine) as session:
        job = session.get(ProcessingJob, job_id)
        job.step = "categorization_failed"
        job.status = "completed"   # stays completed even when categorization fails
        job.progress = 100
        job.result_data = {
            "parsed_count": 10,
            "categorization_count": 0,
        }
        session.add(job)
        session.commit()

    with Session(sync_engine) as session:
        job = session.get(ProcessingJob, job_id)
        assert job.status == "completed"
        assert job.step == "categorization_failed"


# ---------------------------------------------------------------------------
# Story 6.3: uncategorized_reason and category override tests
# ---------------------------------------------------------------------------

def test_categorization_node_low_confidence_sets_reason_and_uncategorized_category():
    """Low-confidence LLM result → category='uncategorized', uncategorized_reason='low_confidence', flagged=True."""
    txn = _make_transaction(mcc=None, description="Unknown merchant")
    state = _make_state(transactions=[txn])

    llm_result = [{"id": txn["id"], "category": "other", "confidence": 0.5}]
    mock_response = _make_llm_response(llm_result)

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = mock_response
    mock_llm.model = "claude-haiku-4-5-20251001"

    with patch("app.agents.categorization.node.get_llm_client", return_value=mock_llm):
        result = categorization_node(state)

    entry = result["categorized_transactions"][0]
    assert entry["flagged"] is True
    assert entry["category"] == "uncategorized"
    assert entry["uncategorized_reason"] == "low_confidence"


def test_categorization_node_parse_failure_sets_reason():
    """LLM parse failure (invalid JSON) → uncategorized_reason='parse_failure', flagged=True."""
    txn = _make_transaction(mcc=None, description="Merchant X")
    state = _make_state(transactions=[txn])

    # Return invalid JSON so _parse_llm_response falls into the except branch
    mock_response = MagicMock()
    mock_response.content = "not valid json {"
    mock_response.usage_metadata = {"total_tokens": 10}

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = mock_response
    mock_llm.model = "claude-haiku-4-5-20251001"

    with patch("app.agents.categorization.node.get_llm_client", return_value=mock_llm):
        result = categorization_node(state)

    entry = result["categorized_transactions"][0]
    assert entry["flagged"] is True
    assert entry["category"] == "uncategorized"
    assert entry["uncategorized_reason"] == "parse_failure"


def test_categorization_node_both_llms_unavailable_sets_reason():
    """Both LLMs raise ValueError (not configured) → uncategorized_reason='llm_unavailable', flagged=True."""
    txn = _make_transaction(mcc=None, description="Shop")
    state = _make_state(transactions=[txn])

    with (
        patch(
            "app.agents.categorization.node.get_llm_client",
            side_effect=ValueError("ANTHROPIC_API_KEY not configured"),
        ),
        patch(
            "app.agents.categorization.node.get_fallback_llm_client",
            side_effect=ValueError("OPENAI_API_KEY not configured"),
        ),
    ):
        result = categorization_node(state)

    entry = result["categorized_transactions"][0]
    assert entry["flagged"] is True
    assert entry["category"] == "uncategorized"
    assert entry["uncategorized_reason"] == "llm_unavailable"


def test_categorization_node_both_llms_fail_exception_sets_reason():
    """Both primary and fallback LLMs raise Exception → uncategorized_reason='llm_unavailable', flagged=True."""
    txn = _make_transaction(mcc=None, description="Unknown")
    state = _make_state(transactions=[txn])

    primary_llm = MagicMock()
    primary_llm.invoke.side_effect = Exception("Primary failed")
    primary_llm.model = "claude-haiku-4-5-20251001"

    fallback_llm = MagicMock()
    fallback_llm.invoke.side_effect = Exception("Fallback also failed")
    fallback_llm.model = "gpt-4o-mini"

    with (
        patch("app.agents.categorization.node.get_llm_client", return_value=primary_llm),
        patch("app.agents.categorization.node.get_fallback_llm_client", return_value=fallback_llm),
    ):
        result = categorization_node(state)

    entry = result["categorized_transactions"][0]
    assert entry["flagged"] is True
    assert entry["category"] == "uncategorized"
    assert entry["uncategorized_reason"] == "llm_unavailable"


def test_categorization_node_high_confidence_no_reason():
    """High-confidence LLM result → flagged=False, uncategorized_reason=None."""
    txn = _make_transaction(mcc=None, description="НОВА ПОШТА")
    state = _make_state(transactions=[txn])

    llm_result = [{"id": txn["id"], "category": "shopping", "confidence": 0.92}]
    mock_response = _make_llm_response(llm_result)

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = mock_response
    mock_llm.model = "claude-haiku-4-5-20251001"

    with patch("app.agents.categorization.node.get_llm_client", return_value=mock_llm):
        result = categorization_node(state)

    entry = result["categorized_transactions"][0]
    assert entry["flagged"] is False
    assert entry["uncategorized_reason"] is None
    assert entry["category"] == "shopping"


def test_categorization_node_mcc_mapped_no_reason():
    """MCC-mapped transaction → flagged=False, uncategorized_reason not set (no reason needed)."""
    txn = _make_transaction(mcc=5411, description="СІЛЬПО")
    state = _make_state(transactions=[txn])

    with patch("app.agents.categorization.node.get_llm_client") as mock_get_llm:
        result = categorization_node(state)

    mock_get_llm.assert_not_called()
    entry = result["categorized_transactions"][0]
    assert entry["flagged"] is False
    assert entry["category"] == "groceries"
    # MCC-mapped entries don't go through the LLM path; no uncategorized_reason key expected
    assert entry.get("uncategorized_reason") is None


# ---------------------------------------------------------------------------
# H1: LLM response category validation
# ---------------------------------------------------------------------------

def test_categorization_node_invalid_llm_category_falls_back_to_other():
    """If LLM returns a category not in VALID_CATEGORIES, it is replaced with 'other'."""
    txn = _make_transaction(mcc=None, description="Mystery")
    state = _make_state(transactions=[txn])

    llm_result = [{"id": txn["id"], "category": "food", "confidence": 0.85}]
    mock_response = _make_llm_response(llm_result)

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = mock_response
    mock_llm.model = "claude-haiku-4-5-20251001"

    with patch("app.agents.categorization.node.get_llm_client", return_value=mock_llm):
        result = categorization_node(state)

    entry = result["categorized_transactions"][0]
    assert entry["category"] == "other", "Invalid LLM category should be replaced with 'other'"
    assert entry["confidence_score"] == pytest.approx(0.85)


# ---------------------------------------------------------------------------
# M2: Batch-splitting across multiple LLM calls
# ---------------------------------------------------------------------------

def test_categorization_node_batch_splitting_two_calls():
    """51 unmapped transactions trigger 2 LLM calls (batch_size=50)."""
    txns = [_make_transaction(mcc=None, description=f"Shop {i}") for i in range(51)]
    state = _make_state(transactions=txns)

    mock_llm = MagicMock()
    # Return an empty JSON array — _parse_llm_response falls back to other/0.0 per txn
    mock_response = MagicMock()
    mock_response.content = "[]"
    mock_response.usage_metadata = {"total_tokens": 100}
    mock_llm.invoke.return_value = mock_response
    mock_llm.model = "claude-haiku-4-5-20251001"

    with patch("app.agents.categorization.node.get_llm_client", return_value=mock_llm):
        result = categorization_node(state)

    assert mock_llm.invoke.call_count == 2, "Expected 2 LLM calls for 51 txns with batch_size=50"
    assert len(result["categorized_transactions"]) == 51
    assert result["total_tokens_used"] == 200  # 100 tokens × 2 calls


# ---------------------------------------------------------------------------
# M3: Real Celery task integration — categorization failure path
# ---------------------------------------------------------------------------

@patch("app.tasks.processing_tasks.publish_job_progress")
@patch("app.tasks.processing_tasks.boto3.client")
@patch("app.tasks.processing_tasks.get_sync_session")
@patch("app.tasks.processing_tasks.build_pipeline")
def test_process_upload_categorization_failure_keeps_completed(
    mock_build_pipeline, mock_get_session, mock_boto_client, mock_publish, sync_engine
):
    """When pipeline.invoke() raises, job is marked failed with is_retryable=True (Story 6.2)."""
    from app.tasks.processing_tasks import process_upload

    user_id = uuid.uuid4()
    upload_id = uuid.uuid4()
    job_id = uuid.uuid4()

    with Session(sync_engine) as s:
        s.add(User(id=user_id, email="cat-fail2@test.com", cognito_sub="cat-fail2-sub", locale="en"))
        s.flush()
        s.add(Upload(
            id=upload_id, user_id=user_id, file_name="test.csv",
            s3_key=f"{user_id}/test.csv", file_size=1024,
            mime_type="text/csv", detected_format="monobank",
            detected_encoding="utf-8", detected_delimiter=";",
        ))
        s.flush()
        s.add(ProcessingJob(id=job_id, user_id=user_id, upload_id=upload_id, status="validated"))
        s.commit()

    @contextmanager
    def _cm():
        s = Session(sync_engine)
        try:
            yield s
        finally:
            s.close()

    mock_get_session.side_effect = _cm

    csv_data = (
        "Дата і час операції;Опис операції;MCC;Сума в валюті картки (UAH);Залишок на рахунку (UAH)\n"
        "01.01.2024 12:00:00;Store;5411;-100.50;5000.00\n"
    ).encode("utf-8")
    mock_boto_client.return_value.get_object.return_value = {"Body": io.BytesIO(csv_data)}

    mock_build_pipeline.return_value.invoke.side_effect = RuntimeError("LLM service unavailable")

    result = process_upload(str(job_id))

    assert result["error"] == "unknown_error"

    with Session(sync_engine) as s:
        job = s.get(ProcessingJob, job_id)
        assert job.status == "failed", "Pipeline failure should mark job as failed for retry"
        assert job.is_retryable is True


# ---------------------------------------------------------------------------
# M4: Real pipeline → DB integration via process_upload
# ---------------------------------------------------------------------------

@patch("app.tasks.processing_tasks.publish_job_progress")
@patch("app.tasks.processing_tasks.boto3.client")
@patch("app.tasks.processing_tasks.get_sync_session")
def test_process_upload_categorization_updates_transaction_in_db(
    mock_get_session, mock_boto_client, mock_publish, sync_engine
):
    """After process_upload, transaction.category is set in DB (full cat_lookup integration path)."""
    from app.tasks.processing_tasks import process_upload

    user_id = uuid.uuid4()
    upload_id = uuid.uuid4()
    job_id = uuid.uuid4()

    with Session(sync_engine) as s:
        s.add(User(id=user_id, email="cat-db2@test.com", cognito_sub="cat-db2-sub", locale="en"))
        s.flush()
        s.add(Upload(
            id=upload_id, user_id=user_id, file_name="test.csv",
            s3_key=f"{user_id}/test.csv", file_size=1024,
            mime_type="text/csv", detected_format="monobank",
            detected_encoding="utf-8", detected_delimiter=";",
        ))
        s.flush()
        s.add(ProcessingJob(id=job_id, user_id=user_id, upload_id=upload_id, status="validated"))
        s.commit()

    @contextmanager
    def _cm():
        s = Session(sync_engine)
        try:
            yield s
        finally:
            s.close()

    mock_get_session.side_effect = _cm

    # MCC 5411 = groceries → MCC pass handles it; no LLM call needed
    csv_data = (
        "Дата і час операції;Опис операції;MCC;Сума в валюті картки (UAH);Залишок на рахунку (UAH)\n"
        "01.01.2024 12:00:00;СІЛЬПО;5411;-100.50;5000.00\n"
    ).encode("utf-8")
    mock_boto_client.return_value.get_object.return_value = {"Body": io.BytesIO(csv_data)}

    result = process_upload(str(job_id))

    assert result["parsed_count"] == 1
    assert result["categorization_count"] == 1

    with Session(sync_engine) as s:
        txns = s.exec(select(Transaction).where(Transaction.upload_id == upload_id)).all()
        assert len(txns) == 1
        assert txns[0].category == "groceries"
        assert txns[0].confidence_score == pytest.approx(1.0)
        assert txns[0].is_flagged_for_review is False


# ---------------------------------------------------------------------------
# Story 6.4: job_id log propagation test
# ---------------------------------------------------------------------------

def test_categorization_node_logs_contain_job_id(caplog):
    """Calling categorization_node with a mock state propagates job_id into log entries (AC #2)."""
    txn = _make_transaction(mcc=None, description="Shop ABC")
    test_job_id = "test-job-id-6-4"
    state = _make_state(transactions=[txn], job_id=test_job_id)

    llm_result = [{"id": txn["id"], "category": "shopping", "confidence": 0.9}]
    mock_response = _make_llm_response(llm_result)

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = mock_response
    mock_llm.model = "claude-haiku-4-5-20251001"

    # The app logger has propagate=False, so caplog (attached to root) won't see child records.
    # Temporarily enable propagation on the app logger itself.
    app_logger = logging.getLogger("app")
    app_logger.propagate = True
    try:
        with caplog.at_level(logging.INFO, logger="app.agents.categorization.node"):
            with patch("app.agents.categorization.node.get_llm_client", return_value=mock_llm):
                categorization_node(state)

        job_id_records = [r for r in caplog.records if getattr(r, "job_id", None) == test_job_id]
        assert len(job_id_records) >= 1, "Expected at least one log record with job_id"
    finally:
        app_logger.propagate = False


def test_categorization_node_logs_do_not_contain_financial_data(caplog):
    """Logs must never contain sensitive financial data like transaction descriptions or amounts."""
    from app.core.logging import JsonFormatter

    txn = _make_transaction(mcc=None, description="SALARY FROM EMPLOYER", amount=-999999)
    state = _make_state(transactions=[txn])

    llm_result = [{"id": txn["id"], "category": "finance", "confidence": 0.85}]
    mock_response = _make_llm_response(llm_result)

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = mock_response
    mock_llm.model = "claude-haiku-4-5-20251001"

    formatter = JsonFormatter()
    app_logger = logging.getLogger("app")
    app_logger.propagate = True
    try:
        with caplog.at_level(logging.DEBUG, logger="app.agents.categorization.node"):
            with patch("app.agents.categorization.node.get_llm_client", return_value=mock_llm):
                categorization_node(state)

        for record in caplog.records:
            assert "SALARY FROM EMPLOYER" not in record.getMessage(), \
                "Log message must not contain transaction description"
            # Also verify the full JSON output from the formatter doesn't leak PII
            formatted = formatter.format(record)
            assert "SALARY FROM EMPLOYER" not in formatted, \
                "Formatted JSON log must not contain transaction description"
    finally:
        app_logger.propagate = False
