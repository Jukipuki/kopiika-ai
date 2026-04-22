"""Unit tests for app.services.schema_detection (Story 11.7 AC #14)."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel, select

from app.models.bank_format_registry import BankFormatRegistry
from app.services import schema_detection
from app.services.schema_detection import (
    DetectedSchema,
    SchemaDetectionFailed,
    detect_schema,
    header_fingerprint,
    resolve_bank_format,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sync_session():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def _fake_llm(content: str):
    """Return a fake LLM client whose .invoke() yields `content`."""

    class _FakeLLM:
        def invoke(self, prompt: str):
            return SimpleNamespace(content=content)

    return _FakeLLM()


_VALID_LLM_PAYLOAD = {
    "date_column": "Дата",
    "date_format": "%d.%m.%Y %H:%M:%S",
    "amount_column": "Сума",
    "amount_sign_convention": "negative_is_outflow",
    "description_column": "Призначення",
    "currency_column": "Валюта",
    "mcc_column": None,
    "balance_column": "Залишок",
    "encoding_hint": "windows-1251",
    "confidence": 0.92,
    "bank_hint": "pe_statement",
}
_VALID_HEADER = ["Дата", "Сума", "Призначення", "Валюта", "Залишок"]


# ---------------------------------------------------------------------------
# Fingerprint tests (AC #14)
# ---------------------------------------------------------------------------


def test_fingerprint_stable_across_whitespace():
    a = header_fingerprint(["Date", "Amount", "Description"])
    b = header_fingerprint(["Date ", " Amount", "  Description  "])
    assert a == b


def test_fingerprint_stable_across_nfkc_variants():
    # "Café" has a Latin small letter e with acute combining form (NFD) vs
    # the single-codepoint precomposed form (NFC). NFKC collapses both.
    import unicodedata

    nfc = unicodedata.normalize("NFC", "Café")
    nfd = unicodedata.normalize("NFD", "Café")
    assert nfc != nfd
    a = header_fingerprint([nfc, "Amount"])
    b = header_fingerprint([nfd, "Amount"])
    assert a == b


def test_fingerprint_case_insensitive():
    a = header_fingerprint(["Date", "AMOUNT", "Description"])
    b = header_fingerprint(["date", "amount", "description"])
    assert a == b


def test_fingerprint_changes_on_column_reorder():
    a = header_fingerprint(["Date", "Amount", "Description"])
    b = header_fingerprint(["Amount", "Date", "Description"])
    assert a != b


# ---------------------------------------------------------------------------
# resolve_bank_format — cache hit / miss / override
# ---------------------------------------------------------------------------


def test_resolve_cache_hit_no_llm_call(monkeypatch, sync_session):
    fingerprint = header_fingerprint(_VALID_HEADER)
    sync_session.add(
        BankFormatRegistry(
            header_fingerprint=fingerprint,
            detected_mapping=dict(_VALID_LLM_PAYLOAD),
            sample_header=" | ".join(_VALID_HEADER),
            detection_confidence=0.9,
            use_count=1,
        )
    )
    sync_session.commit()

    called = {"count": 0}

    def _boom(*_a, **_kw):
        called["count"] += 1
        raise AssertionError("LLM must not be called on cache hit")

    monkeypatch.setattr(schema_detection, "get_llm_client", _boom)

    resolved = resolve_bank_format(
        header_row=_VALID_HEADER,
        sample_rows=[["01.01.2024", "100.00", "test", "UAH", "1000.00"]],
        encoding="windows-1251",
        db_session=sync_session,
    )
    assert resolved.source == "cached_detected"
    assert resolved.mapping["date_column"] == "Дата"
    assert called["count"] == 0

    row = sync_session.execute(
        select(BankFormatRegistry).where(
            BankFormatRegistry.header_fingerprint == fingerprint
        )
    ).scalar_one()
    assert row.use_count == 2


def test_resolve_cache_miss_calls_llm_and_persists(monkeypatch, sync_session):
    monkeypatch.setattr(
        schema_detection,
        "get_llm_client",
        lambda: _fake_llm(json.dumps(_VALID_LLM_PAYLOAD)),
    )
    monkeypatch.setattr(schema_detection, "record_success", lambda *_a, **_kw: None)

    resolved = resolve_bank_format(
        header_row=_VALID_HEADER,
        sample_rows=[["01.01.2024 10:00:00", "100.00", "test", "UAH", "1000.00"]],
        encoding="windows-1251",
        db_session=sync_session,
    )
    assert resolved.source == "llm_detected"

    rows = sync_session.execute(select(BankFormatRegistry)).scalars().all()
    assert len(rows) == 1
    assert rows[0].detection_confidence == pytest.approx(0.92)
    assert rows[0].detected_bank_hint == "pe_statement"


def test_resolve_override_takes_precedence_over_detected(monkeypatch, sync_session):
    fingerprint = header_fingerprint(_VALID_HEADER)
    override = dict(_VALID_LLM_PAYLOAD)
    override["date_column"] = "ORIGIN"
    sync_session.add(
        BankFormatRegistry(
            header_fingerprint=fingerprint,
            detected_mapping=dict(_VALID_LLM_PAYLOAD),
            override_mapping=override,
            sample_header=" | ".join(_VALID_HEADER),
            use_count=1,
        )
    )
    sync_session.commit()

    monkeypatch.setattr(
        schema_detection,
        "get_llm_client",
        lambda: (_ for _ in ()).throw(
            AssertionError("LLM must not be called on override hit")
        ),
    )

    resolved = resolve_bank_format(
        header_row=_VALID_HEADER,
        sample_rows=[],
        encoding="windows-1251",
        db_session=sync_session,
    )
    assert resolved.source == "cached_override"
    assert resolved.mapping["date_column"] == "ORIGIN"


# ---------------------------------------------------------------------------
# detect_schema — JSON parsing + shape validation
# ---------------------------------------------------------------------------


def test_detect_schema_invalid_json_raises(monkeypatch):
    monkeypatch.setattr(
        schema_detection,
        "get_llm_client",
        lambda: _fake_llm("this is not json, sorry"),
    )
    monkeypatch.setattr(schema_detection, "record_success", lambda *_a, **_kw: None)

    with pytest.raises(SchemaDetectionFailed):
        detect_schema(_VALID_HEADER, [], "utf-8")


def test_detect_schema_valid_json_returns_dataclass(monkeypatch):
    monkeypatch.setattr(
        schema_detection,
        "get_llm_client",
        lambda: _fake_llm(json.dumps(_VALID_LLM_PAYLOAD)),
    )
    monkeypatch.setattr(schema_detection, "record_success", lambda *_a, **_kw: None)

    schema = detect_schema(_VALID_HEADER, [], "windows-1251")
    assert isinstance(schema, DetectedSchema)
    assert schema.detection_confidence == pytest.approx(0.92)
    assert schema.detected_bank_hint == "pe_statement"
    assert schema.detected_mapping["amount_sign_convention"] == "negative_is_outflow"


def test_counterparty_columns_persisted_when_detected(monkeypatch, sync_session):
    header = _VALID_HEADER + ["Контрагент", "ІПН", "Рахунок", "Валюта контр"]
    payload = dict(_VALID_LLM_PAYLOAD)
    payload["counterparty_name_column"] = "Контрагент"
    payload["counterparty_tax_id_column"] = "ІПН"
    payload["counterparty_account_column"] = "Рахунок"
    payload["counterparty_currency_column"] = "Валюта контр"

    monkeypatch.setattr(
        schema_detection,
        "get_llm_client",
        lambda: _fake_llm(json.dumps(payload)),
    )
    monkeypatch.setattr(schema_detection, "record_success", lambda *_a, **_kw: None)

    resolved = resolve_bank_format(
        header_row=header,
        sample_rows=[],
        encoding="windows-1251",
        db_session=sync_session,
    )
    for key in (
        "counterparty_name_column",
        "counterparty_tax_id_column",
        "counterparty_account_column",
        "counterparty_currency_column",
    ):
        assert resolved.mapping[key] is not None

    row = sync_session.execute(select(BankFormatRegistry)).scalar_one()
    assert row.detected_mapping["counterparty_name_column"] == "Контрагент"
