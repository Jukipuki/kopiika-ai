"""Persist-path queue insertion tests (Story 11.8 AC #11 item 4).

Covers the logic in ``processing_tasks._maybe_build_review_queue_entry``:
  - low_confidence + suggestion → queue entry built
  - low_confidence without suggestion → skipped (infrastructure failures)
  - llm_unavailable / parse_failure / currency_unknown → skipped
  - no uncategorized_reason → skipped
"""
from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from sqlmodel import Session, SQLModel, create_engine

import app.models  # noqa: F401
from app.models.transaction import Transaction
from app.models.uncategorized_review_queue import UncategorizedReviewQueue
from app.models.upload import Upload
from app.models.user import User
from app.tasks.processing_tasks import (
    _existing_queue_txn_ids,
    _maybe_build_review_queue_entry,
)


def _mk_txn() -> Transaction:
    return Transaction(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        upload_id=uuid.uuid4(),
        date=datetime(2026, 4, 22),
        description="desc",
        amount=-5000,
        currency_code=980,
        dedup_hash=uuid.uuid4().hex,
    )


def test_low_confidence_with_suggestion_is_queued():
    txn = _mk_txn()
    cat = {
        "uncategorized_reason": "low_confidence",
        "confidence_score": 0.42,
        "suggested_category": "shopping",
        "suggested_kind": "spending",
    }
    entry = _maybe_build_review_queue_entry(cat=cat, txn=txn)
    assert entry is not None
    assert entry.user_id == txn.user_id
    assert entry.transaction_id == txn.id
    assert entry.categorization_confidence == 0.42
    assert entry.suggested_category == "shopping"
    assert entry.suggested_kind == "spending"
    assert entry.status == "pending"


def test_low_confidence_without_suggestion_skipped():
    """Infrastructure failures can stamp low_confidence but carry no suggestion."""
    txn = _mk_txn()
    cat = {
        "uncategorized_reason": "low_confidence",
        "confidence_score": 0.3,
        # No suggested_category / suggested_kind
    }
    assert _maybe_build_review_queue_entry(cat=cat, txn=txn) is None


def test_llm_unavailable_skipped():
    txn = _mk_txn()
    cat = {
        "uncategorized_reason": "llm_unavailable",
        "confidence_score": 0.0,
        "suggested_category": None,
        "suggested_kind": None,
    }
    assert _maybe_build_review_queue_entry(cat=cat, txn=txn) is None


def test_parse_failure_skipped():
    txn = _mk_txn()
    cat = {
        "uncategorized_reason": "parse_failure",
        "confidence_score": 0.0,
    }
    assert _maybe_build_review_queue_entry(cat=cat, txn=txn) is None


def test_currency_unknown_skipped():
    txn = _mk_txn()
    cat = {
        "uncategorized_reason": "currency_unknown",
        "confidence_score": 0.0,
    }
    assert _maybe_build_review_queue_entry(cat=cat, txn=txn) is None


def test_no_reason_skipped():
    """Auto-applied / soft-flag rows have no uncategorized_reason → no queue entry."""
    txn = _mk_txn()
    cat = {
        "uncategorized_reason": None,
        "confidence_score": 0.9,
        "category": "restaurants",
        "transaction_kind": "spending",
    }
    assert _maybe_build_review_queue_entry(cat=cat, txn=txn) is None


@pytest.fixture
def sync_db():
    """In-memory sync SQLite for the dedup test below."""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def _seed_txn(session, user_id, upload_id) -> uuid.UUID:
    txn_id = uuid.uuid4()
    session.add(Transaction(
        id=txn_id, user_id=user_id, upload_id=upload_id,
        date=datetime(2026, 4, 22), description="x", amount=-1,
        currency_code=980, dedup_hash=uuid.uuid4().hex,
    ))
    session.commit()
    return txn_id


def test_existing_queue_txn_ids_finds_duplicates(sync_db):
    """H1 regression: resume_upload must skip txns already queued.

    Verifies ``_existing_queue_txn_ids`` returns the subset of txn_ids that
    already have a queue row — regardless of status — so the caller can
    skip re-inserting and avoid duplicate "review me" rows.
    """
    user_id = uuid.uuid4()
    sync_db.add(User(id=user_id, cognito_sub=f"s-{uuid.uuid4()}", email=f"{uuid.uuid4()}@e.co"))
    upload_id = uuid.uuid4()
    sync_db.add(Upload(id=upload_id, user_id=user_id, file_name="t.csv", s3_key=f"{user_id}/t.csv", file_size=1, mime_type="text/csv"))
    sync_db.commit()

    t_queued = _seed_txn(sync_db, user_id, upload_id)
    t_fresh = _seed_txn(sync_db, user_id, upload_id)
    t_dismissed = _seed_txn(sync_db, user_id, upload_id)

    sync_db.add(UncategorizedReviewQueue(
        user_id=user_id, transaction_id=t_queued,
        categorization_confidence=0.4, suggested_category="shopping",
        suggested_kind="spending", status="pending",
    ))
    sync_db.add(UncategorizedReviewQueue(
        user_id=user_id, transaction_id=t_dismissed,
        categorization_confidence=0.3, suggested_category="shopping",
        suggested_kind="spending", status="dismissed",
    ))
    sync_db.commit()

    found = _existing_queue_txn_ids(sync_db, [t_queued, t_fresh, t_dismissed])
    assert found == {t_queued, t_dismissed}
    # Empty input → empty set, no SQL issued.
    assert _existing_queue_txn_ids(sync_db, []) == set()
