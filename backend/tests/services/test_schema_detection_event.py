"""Story 11.9 AC #5, #12: pin the parser.schema_detection event field set.

Snapshot-style assertion — fails loudly on silent field drops.
"""
from __future__ import annotations

import logging

import pytest

from app.services import schema_detection


@pytest.fixture(autouse=True)
def _enable_app_logger_propagation():
    app_logger = logging.getLogger("app")
    prev = app_logger.propagate
    app_logger.propagate = True
    try:
        yield
    finally:
        app_logger.propagate = prev


def test_schema_detection_event_carries_spec_fields(caplog):
    caplog.set_level(logging.INFO, logger="app.services.schema_detection")
    schema_detection._emit_detection_event(  # type: ignore[attr-defined]
        upload_id="upload-1",
        user_id="user-1",
        fingerprint="abc123",
        source="llm_detected",
        detection_confidence=0.97,
        latency_ms=420,
    )

    events = [r for r in caplog.records if r.getMessage() == "parser.schema_detection"]
    assert len(events) == 1
    rec = events[0]
    # Spec §9: fingerprint, source, confidence (detection_confidence), latency_ms.
    for field in ("upload_id", "user_id", "fingerprint", "source", "detection_confidence", "latency_ms"):
        assert hasattr(rec, field), f"missing spec field: {field}"

    assert rec.fingerprint == "abc123"
    assert rec.source == "llm_detected"
    assert rec.detection_confidence == 0.97
    assert rec.latency_ms == 420
