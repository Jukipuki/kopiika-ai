"""Story 11.9 AC #2, #12: categorization.kind_mismatch event renaming + fields.

Exercises the fallback path in ``processing_tasks._persist_transactions`` /
``resume_upload`` where the LLM returns an invalid (kind, category) pair.
"""
from __future__ import annotations

import io
import logging
import uuid
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel

from app.models.processing_job import ProcessingJob
from app.models.upload import Upload
from app.models.user import User


@pytest.fixture(autouse=True)
def _enable_app_logger_propagation():
    app_logger = logging.getLogger("app")
    prev = app_logger.propagate
    app_logger.propagate = True
    try:
        yield
    finally:
        app_logger.propagate = prev


MONOBANK_CSV = (
    "Дата і час операції;Опис операції;MCC;Сума в валюті картки (UAH);Залишок на рахунку (UAH)\n"
    "01.01.2024 12:00:00;Grocery Store;5411;-100.50;5000.00\n"
).encode("utf-8")


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


def _seed(engine):
    user_id = uuid.uuid4()
    upload_id = uuid.uuid4()
    job_id = uuid.uuid4()
    with Session(engine) as session:
        session.add(User(id=user_id, email="km@test.com", cognito_sub="km-sub", locale="en"))
        session.flush()
        session.add(Upload(
            id=upload_id, user_id=user_id, file_name="km.csv",
            s3_key=f"{user_id}/km.csv", file_size=len(MONOBANK_CSV),
            mime_type="text/csv", detected_format="monobank",
            detected_encoding="utf-8", detected_delimiter=";",
        ))
        session.flush()
        session.add(ProcessingJob(
            id=job_id, user_id=user_id, upload_id=upload_id, status="validated",
        ))
        session.commit()
    return user_id, upload_id, job_id


def _mock_session_cm(engine):
    @contextmanager
    def _cm():
        s = Session(engine)
        try:
            yield s
        finally:
            s.close()
    return _cm


def _fake_invoke_mismatch(initial_state, config):
    # Return an invalid pair: transaction_kind="income" + category="groceries"
    # (groceries is a spending-only category → triggers fallback).
    return {
        "categorized_transactions": [
            {
                "transaction_id": t["id"],
                "category": "groceries",
                "transaction_kind": "income",
                "confidence_score": 0.92,
                "flagged": False,
                "uncategorized_reason": None,
            }
            for t in initial_state["transactions"]
        ],
        "insight_cards": [],
        "total_tokens_used": 0,
        "errors": [],
        "upload_id": initial_state["upload_id"],
    }


@patch("app.tasks.processing_tasks.publish_job_progress")
@patch("app.tasks.processing_tasks.build_pipeline")
@patch("app.tasks.processing_tasks.boto3.client")
@patch("app.tasks.processing_tasks.get_sync_session")
def test_kind_mismatch_event_emitted_with_spec_fields(
    mock_get_session, mock_boto, mock_build_pipeline, mock_publish, sync_engine, caplog
):
    user_id, upload_id, job_id = _seed(sync_engine)
    mock_get_session.side_effect = _mock_session_cm(sync_engine)

    mock_s3 = MagicMock()
    mock_s3.get_object.return_value = {"Body": io.BytesIO(MONOBANK_CSV)}
    mock_boto.return_value = mock_s3

    mock_build_pipeline.return_value.invoke.side_effect = _fake_invoke_mismatch

    from app.tasks.processing_tasks import process_upload

    caplog.set_level(logging.WARNING, logger="app.tasks.processing_tasks")
    process_upload(str(job_id))

    events = [r for r in caplog.records if r.getMessage() == "categorization.kind_mismatch"]
    assert len(events) >= 1, "expected at least one kind_mismatch event"

    # Old event name must not appear.
    assert not any(
        r.getMessage() == "kind_category_mismatch_fallback" for r in caplog.records
    )

    rec = events[0]
    # Spec §9 fields.
    assert getattr(rec, "job_id") == str(job_id)
    assert getattr(rec, "user_id") == str(user_id)
    assert getattr(rec, "tx_id")
    assert getattr(rec, "returned_kind") == "income"
    assert getattr(rec, "returned_category") == "groceries"
    # Renamed fields must not appear under their old names.
    assert not hasattr(rec, "transaction_id")
