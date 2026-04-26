"""Story 10.6b — pure-function unit tests for ``assemble_citations``."""

from __future__ import annotations

import logging
import uuid
from datetime import date
from types import SimpleNamespace

import pytest

from app.agents.chat.citations import (
    CategoryCitation,
    Citation,
    ProfileFieldCitation,
    RagDocCitation,
    TransactionCitation,
    assemble_citations,
    citation_to_json_dict,
)


def _tx_row(
    *,
    id: uuid.UUID | None = None,
    booked_at: date = date(2026, 3, 14),
    description: str = "Coffee Shop",
    amount_kopiykas: int = -8500,
    currency: str = "UAH",
    category_code: str | None = "groceries",
    transaction_kind: str | None = "spending",
) -> dict:
    return {
        "id": str(id or uuid.uuid4()),
        "booked_at": booked_at.isoformat(),
        "description": description,
        "amount_kopiykas": amount_kopiykas,
        "currency": currency,
        "category_code": category_code,
        "transaction_kind": transaction_kind,
    }


def _tx_call(rows: list[dict], *, ok: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        tool_name="get_transactions",
        ok=ok,
        payload={"rows": rows, "row_count": len(rows), "truncated": False},
        error_kind=None,
        elapsed_ms=10,
        tool_use_id="t-1",
    )


def _profile_call(
    *,
    monthly_income_kopiykas: int | None = 7_000_000,
    monthly_expenses_kopiykas: int | None = 4_530_000,
    savings_ratio: int | None = 22,
    health_score: int | None = 78,
    currency: str = "UAH",
    as_of: date = date(2026, 4, 1),
    breakdown_codes: list[str] | None = None,
    ok: bool = True,
) -> SimpleNamespace:
    return SimpleNamespace(
        tool_name="get_profile",
        ok=ok,
        payload={
            "summary": {
                "monthly_income_kopiykas": monthly_income_kopiykas,
                "monthly_expenses_kopiykas": monthly_expenses_kopiykas,
                "savings_ratio": savings_ratio,
                "health_score": health_score,
                "currency": currency,
                "as_of": as_of.isoformat(),
            },
            "category_breakdown": [
                {"category_code": c, "amount_kopiykas": 100, "share_percent": 10}
                for c in (breakdown_codes or [])
            ],
            "monthly_comparison": [],
        },
        error_kind=None,
        elapsed_ms=11,
        tool_use_id="t-2",
    )


def _rag_call(rows: list[dict], *, ok: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        tool_name="search_financial_corpus",
        ok=ok,
        payload={"rows": rows, "row_count": len(rows)},
        error_kind=None,
        elapsed_ms=12,
        tool_use_id="t-3",
    )


def _feed_call(row_count: int = 0, *, ok: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        tool_name="get_teaching_feed",
        ok=ok,
        payload={"rows": [{"title": f"c{i}"} for i in range(row_count)]},
        error_kind=None,
        elapsed_ms=8,
        tool_use_id="t-4",
    )


@pytest.fixture(autouse=True)
def _app_logger_propagates_for_caplog():
    lg = logging.getLogger("app")
    prev = lg.propagate
    lg.propagate = True
    try:
        yield
    finally:
        lg.propagate = prev


# ---------------------------------------------------------------------------


def test_empty_input_returns_empty_tuple():
    assert assemble_citations(()) == ()


def test_failed_tool_calls_skipped():
    calls = [_tx_call([], ok=False), _profile_call(ok=False), _rag_call([], ok=False)]
    assert assemble_citations(calls) == ()


def test_get_transactions_happy_path_emits_tx_and_categories():
    a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    rows = [
        _tx_row(id=a, category_code="groceries", description="Coffee Shop"),
        _tx_row(id=b, category_code="transport", description="Bus pass"),
        _tx_row(id=c, category_code="groceries", description="Bakery"),
    ]
    citations = assemble_citations([_tx_call(rows)])
    kinds = [c.kind for c in citations]
    # 3 transactions interleaved with their categories (first-occurrence dedup).
    assert kinds == [
        "transaction", "category",  # row 0 + groceries
        "transaction", "category",  # row 1 + transport
        "transaction",              # row 2 (groceries already added)
    ]
    cats = [c for c in citations if isinstance(c, CategoryCitation)]
    assert sorted(c.code for c in cats) == ["groceries", "transport"]


def test_get_profile_field_projection_only_non_none_with_currency():
    call = _profile_call(
        monthly_income_kopiykas=None,
        monthly_expenses_kopiykas=5_000_000,
        savings_ratio=22,
        health_score=None,
        as_of=date(2026, 4, 1),
    )
    citations = assemble_citations([call])
    profile_fields = [c for c in citations if isinstance(c, ProfileFieldCitation)]
    by_field = {c.field: c for c in profile_fields}
    assert set(by_field) == {"monthly_expenses_kopiykas", "savings_ratio"}
    assert by_field["monthly_expenses_kopiykas"].currency == "UAH"
    assert by_field["savings_ratio"].currency is None


def test_get_profile_breakdown_dedupes_against_transactions():
    tx_id = uuid.uuid4()
    tx_call = _tx_call([_tx_row(id=tx_id, category_code="groceries")])
    profile = _profile_call(breakdown_codes=["groceries", "transport"])
    citations = assemble_citations([tx_call, profile])
    cats = [c for c in citations if isinstance(c, CategoryCitation)]
    codes = [c.code for c in cats]
    # groceries appears once (TX-derived first), transport added from profile.
    assert codes.count("groceries") == 1
    assert "transport" in codes


def test_search_financial_corpus_snippet_truncated_to_240():
    snippet = "x" * 500
    call = _rag_call([
        {"source_id": "en/emergency-fund", "snippet": snippet, "similarity": 0.9}
    ])
    citations = assemble_citations([call])
    assert len(citations) == 1
    assert isinstance(citations[0], RagDocCitation)
    assert len(citations[0].snippet) == 240


def test_search_financial_corpus_dedupe_by_source_id():
    call = _rag_call([
        {"source_id": "en/x", "snippet": "a", "similarity": 0.9},
        {"source_id": "en/x", "snippet": "b", "similarity": 0.7},
    ])
    citations = assemble_citations([call])
    assert len(citations) == 1
    assert citations[0].snippet == "a"


def test_get_teaching_feed_dropped_with_debug_log(caplog):
    with caplog.at_level(logging.DEBUG, logger="app.agents.chat.citations"):
        citations = assemble_citations([_feed_call(row_count=5)])
    assert citations == ()
    drops = [
        r for r in caplog.records if r.message == "chat.citations.dropped"
    ]
    assert drops
    assert getattr(drops[0], "tool_name") == "get_teaching_feed"
    assert getattr(drops[0], "row_count") == 5


def test_truncation_cap_emits_warn_log(caplog):
    rows = [_tx_row(id=uuid.uuid4(), category_code=None) for _ in range(25)]
    with caplog.at_level(logging.WARNING, logger="app.agents.chat.citations"):
        citations = assemble_citations([_tx_call(rows)])
    assert len(citations) == 20
    truncs = [r for r in caplog.records if r.message == "chat.citations.truncated"]
    assert truncs
    assert getattr(truncs[0], "pre_truncate_count") == 25
    assert getattr(truncs[0], "kept_count") == 20
    assert getattr(truncs[0], "dropped_count") == 5


def test_malformed_payload_silently_skipped(caplog):
    bad = SimpleNamespace(
        tool_name="get_transactions",
        ok=True,
        payload={"rows": [{"id": "not-a-uuid"}]},  # missing required fields
        error_kind=None,
        elapsed_ms=1,
        tool_use_id="t-bad",
    )
    with caplog.at_level(logging.WARNING, logger="app.agents.chat.citations"):
        citations = assemble_citations([bad])
    assert citations == ()
    warns = [r for r in caplog.records if r.message == "chat.citations.malformed_payload"]
    assert warns
    assert getattr(warns[0], "tool_name") == "get_transactions"


def test_label_rendering_per_kind():
    tx_id = uuid.uuid4()
    tx_call = _tx_call(
        [
            _tx_row(
                id=tx_id,
                description="Coffee Shop",
                booked_at=date(2026, 3, 14),
                category_code="transfers_p2p",
            )
        ]
    )
    profile = _profile_call(
        monthly_income_kopiykas=None,
        monthly_expenses_kopiykas=4_530_000,
        savings_ratio=None,
        health_score=None,
        as_of=date(2026, 4, 1),
    )
    rag = _rag_call(
        [{"source_id": "en/emergency-fund", "snippet": "x", "similarity": 0.5}]
    )
    citations = assemble_citations([tx_call, profile, rag])

    by_kind = {c.kind: c for c in citations}
    assert by_kind["transaction"].label == "Coffee Shop · 2026-03-14"
    assert by_kind["category"].label == "Transfers P2P"
    assert by_kind["profile_field"].label == "Monthly expenses (Apr 2026)"
    assert by_kind["rag_doc"].label == "en/emergency-fund"


def test_order_stability_tools_then_rows():
    tx_a, tx_b = uuid.uuid4(), uuid.uuid4()
    tx_call = _tx_call([_tx_row(id=tx_a, category_code=None), _tx_row(id=tx_b, category_code=None)])
    profile = _profile_call(
        monthly_income_kopiykas=None,
        monthly_expenses_kopiykas=10,
        savings_ratio=None,
        health_score=None,
    )
    citations = assemble_citations([tx_call, profile])
    kinds = [c.kind for c in citations]
    assert kinds == ["transaction", "transaction", "profile_field"]
    tx_ids = [c.id for c in citations if isinstance(c, TransactionCitation)]
    assert tx_ids == [tx_a, tx_b]


def test_json_round_trip_each_kind():
    samples: list[Citation] = [
        TransactionCitation(
            id=uuid.uuid4(),
            booked_at=date(2026, 3, 14),
            description="Coffee",
            amount_kopiykas=-100,
            currency="UAH",
            category_code="groceries",
            label="Coffee · 2026-03-14",
        ),
        CategoryCitation(code="groceries", label="Groceries"),
        ProfileFieldCitation(
            field="monthly_expenses_kopiykas",
            value=4_530_000,
            currency="UAH",
            as_of=date(2026, 4, 1),
            label="Monthly expenses (Apr 2026)",
        ),
        RagDocCitation(
            source_id="en/x",
            title="en/x",
            snippet="a",
            similarity=0.5,
            label="en/x",
        ),
    ]
    for c in samples:
        d = citation_to_json_dict(c)
        roundtripped = type(c).model_validate(d)
        assert roundtripped == c
