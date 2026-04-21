"""End-to-end tests for Story 11.7 schema detection (AC #13).

All tests hit the real LLM via `get_llm_client()` and are therefore gated with
`@pytest.mark.integration`. They are excluded from the default pytest sweep
(`addopts = -m 'not integration'` in pyproject.toml); run explicitly with:

    pytest -m integration tests/integration/test_schema_detection_e2e.py

The fallback test uses a canned non-JSON response and does NOT call the LLM,
but is grouped here for coherence.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel, select

from app.models.bank_format_registry import BankFormatRegistry
from app.services import schema_detection
from app.services.schema_detection import (
    SchemaDetectionFailed,
    resolve_bank_format,
)

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "pe_statement_sample.csv"


@pytest.fixture
def sync_session():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def _load_fixture() -> tuple[list[str], list[list[str]]]:
    import csv as _csv

    text = FIXTURE_PATH.read_text(encoding="utf-8")
    reader = _csv.reader(text.splitlines(), delimiter=";")
    header = next(reader)
    samples = [row for row in reader]
    return [c.strip() for c in header], samples


@pytest.mark.integration
def test_first_upload_detects_and_persists(sync_session):
    header, samples = _load_fixture()
    assert sync_session.execute(select(BankFormatRegistry)).scalars().all() == []

    resolved = resolve_bank_format(
        header_row=header,
        sample_rows=samples,
        encoding="utf-8",
        db_session=sync_session,
    )
    assert resolved.source == "llm_detected"

    rows = sync_session.execute(select(BankFormatRegistry)).scalars().all()
    assert len(rows) == 1
    mapping = rows[0].detected_mapping

    for key in (
        "date_column",
        "date_format",
        "amount_column",
        "amount_sign_convention",
        "description_column",
        "currency_column",
        "delimiter",
        "encoding_hint",
    ):
        assert key in mapping, f"required key {key} missing"

    # Counterparty columns from the PE statement should be identified.
    counterparty_keys = [
        "counterparty_name_column",
        "counterparty_tax_id_column",
        "counterparty_account_column",
        "counterparty_currency_column",
    ]
    present = [mapping.get(k) for k in counterparty_keys if mapping.get(k)]
    assert present, (
        "Expected at least one counterparty column in PE mapping; got "
        f"{mapping}"
    )


@pytest.mark.integration
def test_second_upload_hits_cache(sync_session):
    header, samples = _load_fixture()
    first = resolve_bank_format(
        header_row=header,
        sample_rows=samples,
        encoding="utf-8",
        db_session=sync_session,
    )
    assert first.source == "llm_detected"

    # Re-resolve with a poisoned LLM client — if it were called we'd know.
    original = schema_detection.get_llm_client

    def _poisoned():
        raise AssertionError("LLM must not be called on fingerprint cache hit")

    schema_detection.get_llm_client = _poisoned
    try:
        second = resolve_bank_format(
            header_row=header,
            sample_rows=samples,
            encoding="utf-8",
            db_session=sync_session,
        )
    finally:
        schema_detection.get_llm_client = original

    assert second.source == "cached_detected"
    row = sync_session.execute(select(BankFormatRegistry)).scalar_one()
    assert row.use_count == 2


@pytest.mark.integration
def test_fallback_when_llm_returns_non_json(monkeypatch, sync_session):
    # Synthesize a malformed-but-not-empty header (collision-free so it won't
    # conflict with other fixtures).
    header = ["X", "Y", "Z"]
    samples = [["foo", "bar", "baz"]]

    class _BadLLM:
        def invoke(self, prompt: str):
            return SimpleNamespace(content="I refuse to return JSON")

    monkeypatch.setattr(schema_detection, "get_llm_client", lambda: _BadLLM())
    monkeypatch.setattr(
        schema_detection, "record_success", lambda *_a, **_kw: None
    )

    with pytest.raises(SchemaDetectionFailed):
        resolve_bank_format(
            header_row=header,
            sample_rows=samples,
            encoding="utf-8",
            db_session=sync_session,
        )
    # No row was persisted on failure.
    assert sync_session.execute(select(BankFormatRegistry)).scalars().all() == []
