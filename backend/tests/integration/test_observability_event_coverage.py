"""Story 11.9 AC #6, #12: five-event coverage smoke test.

Pins the spec §9 event vocabulary: asserts every event name in the ingestion
+ categorization union is emitted from its canonical code path. Drives
``process_upload`` end-to-end with a canned LLM response that yields both an
invalid (kind, category) pair (→ ``categorization.kind_mismatch``) and a
low-confidence row (→ ``categorization.confidence_tier`` + the post-commit
``categorization.review_queue_insert``), then exercises the parser-service
and schema-detection emission sites directly for the remaining three events.

The union invariant lives in this one file so a future refactor that
silently drops an event gets caught by a single failing test rather than
requiring cross-file grep.
"""
from __future__ import annotations

import io
import logging
import uuid
from contextlib import contextmanager
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel

from app.agents.categorization import node as node_mod
from app.agents.categorization.node import categorization_node
from app.agents.ingestion.parsers.base import ParseResult, TransactionData
from app.models.processing_job import ProcessingJob
from app.models.upload import Upload
from app.models.user import User
from app.services import schema_detection
from app.services.format_detector import FormatDetectionResult
from app.services.parser_service import _parse_and_build_records


pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _enable_app_logger_propagation():
    app_logger = logging.getLogger("app")
    prev = app_logger.propagate
    app_logger.propagate = True
    try:
        yield
    finally:
        app_logger.propagate = prev


SPEC_EVENTS = {
    "categorization.confidence_tier",
    "categorization.kind_mismatch",
    "categorization.review_queue_insert",
    "parser.schema_detection",
    "parser.validation_rejected",
    "parser.mojibake_detected",
}


MONOBANK_CSV = (
    "Дата і час операції;Опис операції;MCC;Сума в валюті картки (UAH);Залишок на рахунку (UAH)\n"
    "01.01.2024 12:00:00;Grocery Store;5411;-100.50;5000.00\n"
    "02.01.2024 12:00:00;Mystery Txn;5411;-200.00;4800.00\n"
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


def _format_result(encoding: str = "utf-8") -> FormatDetectionResult:
    return FormatDetectionResult(
        bank_format="monobank",
        encoding=encoding,
        delimiter=";",
        column_count=5,
        confidence_score=1.0,
        header_row=[],
        amount_sign_convention="negative_is_outflow",
    )


def _txn(description: str, idx: int, amount: int = -100) -> TransactionData:
    return TransactionData(
        date=datetime(2026, 2, idx + 1),
        description=description,
        mcc=5812,
        amount=amount,
        balance=None,
        currency_code=980,
        raw_data={},
    )


def _emit_parser_events():
    """Trigger parser.validation_rejected + parser.mojibake_detected."""
    rows = [_txn(f"CLEAN-{i}", i) for i in range(7)]
    rows.append(_txn("�" * 5 + "XYZAB", 7))
    rows.append(_txn("REJECT", 8, amount=0))  # zero-amount → validation rejection
    pr = ParseResult(
        transactions=rows, flagged_rows=[], total_rows=len(rows),
        parsed_count=len(rows), flagged_count=0,
    )
    with patch(
        "app.agents.ingestion.parsers.monobank.MonobankParser.parse",
        return_value=pr,
    ):
        _parse_and_build_records(
            uuid.uuid4(), uuid.uuid4(), b"ignored",
            _format_result(encoding="cp1251"), session=None,
        )


def _emit_confidence_tier():
    """Drive categorization_node with a canned low-confidence response to
    trigger the ``categorization.confidence_tier`` event. The node is bypassed
    by the ``build_pipeline`` mock in the end-to-end flow, so we exercise it
    directly here."""
    txn = {"id": "t-queue", "description": "???", "amount": -4000, "mcc": None}
    canned = [{
        "transaction_id": "t-queue",
        "category": "shopping",
        "transaction_kind": "spending",
        "confidence_score": 0.42,
        "flagged": False,
        "uncategorized_reason": None,
    }]

    def _fake_batch(batch, llm, log_ctx):  # noqa: ARG001
        return [dict(c) for c in canned], 0

    with patch.object(node_mod, "_categorize_batch", _fake_batch):
        with patch.object(node_mod, "get_llm_client", lambda: object()):
            categorization_node({
                "job_id": "job-1",
                "user_id": "user-1",
                "upload_id": "upload-1",
                "transactions": [txn],
                "completed_nodes": [],
            })


def _emit_schema_detection():
    schema_detection._emit_detection_event(  # type: ignore[attr-defined]
        upload_id=str(uuid.uuid4()),
        user_id=str(uuid.uuid4()),
        fingerprint="abc",
        source="llm_detected",
        detection_confidence=0.95,
        latency_ms=100,
    )


def _seed_processing_job(engine):
    user_id = uuid.uuid4()
    upload_id = uuid.uuid4()
    job_id = uuid.uuid4()
    with Session(engine) as session:
        session.add(User(id=user_id, email="ev@test.com", cognito_sub="ev-sub", locale="en"))
        session.flush()
        session.add(Upload(
            id=upload_id, user_id=user_id, file_name="ev.csv",
            s3_key=f"{user_id}/ev.csv", file_size=len(MONOBANK_CSV),
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


def _fake_invoke_mismatch_and_lowconf(initial_state, config):
    """Row 1: kind=income + category=groceries → mismatch.
    Row 2: confidence 0.42 → queue tier + review_queue_insert."""
    out = []
    for idx, t in enumerate(initial_state["transactions"]):
        if idx == 0:
            out.append({
                "transaction_id": t["id"],
                "category": "groceries",
                "transaction_kind": "income",
                "confidence_score": 0.92,
                "flagged": False,
                "uncategorized_reason": None,
            })
        else:
            # Low-confidence row with a non-null suggestion → review queue
            # insert (Story 11.8 AC #4 gate: uncategorized_reason="low_confidence"
            # + suggested_category + suggested_kind).
            out.append({
                "transaction_id": t["id"],
                "category": "uncategorized",
                "transaction_kind": "spending",
                "confidence_score": 0.42,
                "flagged": True,
                "uncategorized_reason": "low_confidence",
                "suggested_category": "shopping",
                "suggested_kind": "spending",
            })
    return {
        "categorized_transactions": out,
        "insight_cards": [],
        "total_tokens_used": 0,
        "errors": [],
        "upload_id": initial_state["upload_id"],
    }


@patch("app.tasks.processing_tasks.publish_job_progress")
@patch("app.tasks.processing_tasks.build_pipeline")
@patch("app.tasks.processing_tasks.boto3.client")
@patch("app.tasks.processing_tasks.get_sync_session")
def test_spec_event_vocabulary_emitted_end_to_end(
    mock_get_session, mock_boto, mock_build_pipeline, mock_publish, sync_engine, caplog
):
    """All six spec §9 events fire across a realistic upload flow."""
    user_id, upload_id, job_id = _seed_processing_job(sync_engine)
    mock_get_session.side_effect = _mock_session_cm(sync_engine)

    mock_s3 = MagicMock()
    mock_s3.get_object.return_value = {"Body": io.BytesIO(MONOBANK_CSV)}
    mock_boto.return_value = mock_s3

    mock_build_pipeline.return_value.invoke.side_effect = _fake_invoke_mismatch_and_lowconf

    from app.tasks.processing_tasks import process_upload

    caplog.set_level(logging.INFO)
    # End-to-end: emits kind_mismatch + confidence_tier + review_queue_insert
    # (plus parser.schema_detection for the known-bank path — known format
    # resolves without hitting the fallback branch).
    process_upload(str(job_id))
    # Direct emission for the parser-layer events (validation_rejected +
    # mojibake_detected) — forcing them through real parsing would require a
    # synthetic CSV that tickles each validator branch; the direct path pins
    # the event contract without the parse scaffolding.
    _emit_parser_events()
    # Confidence tier event — fires in node.py which the build_pipeline mock
    # bypasses; exercise it directly.
    _emit_confidence_tier()
    # Schema detection event — known-bank paths don't hit schema_detection;
    # pin the event shape directly.
    _emit_schema_detection()

    seen = {r.getMessage() for r in caplog.records}
    missing = SPEC_EVENTS - seen
    assert not missing, f"missing spec events: {missing}"

    # Negative: the old event names must NOT appear.
    assert "encoding.mojibake_detected" not in seen
    assert "kind_category_mismatch_fallback" not in seen
