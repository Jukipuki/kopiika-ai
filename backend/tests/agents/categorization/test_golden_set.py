"""Golden-set evaluation harness for the categorization pipeline (Story 11.1).

Loads the labeled golden set, runs it through `categorization_node` with REAL LLM
calls, computes per-axis accuracy (category, kind, joint), writes a timestamped
JSON run report, and asserts both axes meet the 90% gate.

Run with:
    cd backend && python -m pytest tests/agents/categorization/test_golden_set.py -v -s -m integration
"""

import datetime
import json
import time
import uuid
from pathlib import Path

import pytest

from app.agents.categorization.mcc_mapping import VALID_CATEGORIES
from app.agents.categorization.node import categorization_node


FIXTURE_DIR = Path(__file__).resolve().parent.parent.parent / "fixtures" / "categorization_golden_set"
GOLDEN_SET_PATH = FIXTURE_DIR / "golden_set.jsonl"
RUNS_DIR = FIXTURE_DIR / "runs"

REQUIRED_FIELDS = {
    "id",
    "description",
    "amount_kopiykas",
    "mcc",
    "expected_category",
    "expected_kind",
    "edge_case_tag",
    "notes",
}


def _load_golden_set() -> list[dict]:
    """Parse the golden set fixture.

    The fixture is a sequence of pretty-printed JSON objects (not strict
    line-delimited JSONL). Use raw_decode to walk the stream.
    """
    text = GOLDEN_SET_PATH.read_text(encoding="utf-8")
    decoder = json.JSONDecoder()
    rows: list[dict] = []
    i = 0
    n = len(text)
    while i < n:
        while i < n and text[i].isspace():
            i += 1
        if i >= n:
            break
        try:
            obj, end = decoder.raw_decode(text, i)
        except json.JSONDecodeError as exc:
            line = text.count("\n", 0, i) + 1
            raise AssertionError(
                f"Failed to decode golden-set JSON at byte {i} (line {line}) "
                f"of {GOLDEN_SET_PATH}: {exc.msg}"
            ) from exc
        rows.append(obj)
        i = end
    return rows


def _build_state(rows: list[dict]) -> dict:
    from app.agents.categorization.counterparty_patterns import edrpou_kind

    transactions = []
    for row in rows:
        txn = {
            "id": row["id"],
            "description": row["description"],
            "amount": row["amount_kopiykas"],
            "mcc": row["mcc"],
            "date": "2025-01-01",
        }
        # Story 11.10: thread optional counterparty fields from the fixture.
        # Non-PE rows have these absent → txn stays card-only.
        if row.get("counterparty_name"):
            txn["counterparty_name"] = row["counterparty_name"]
        if row.get("counterparty_tax_id"):
            txn["counterparty_tax_id"] = row["counterparty_tax_id"]
            txn["counterparty_tax_id_kind"] = edrpou_kind(row["counterparty_tax_id"])
        if row.get("counterparty_account"):
            txn["counterparty_account"] = row["counterparty_account"]
        if "is_self_iban" in row:
            txn["is_self_iban"] = bool(row["is_self_iban"])
        transactions.append(txn)
    return {
        "job_id": f"golden-set-{uuid.uuid4()}",
        "user_id": "golden-set-user",
        "upload_id": "golden-set-upload",
        "transactions": transactions,
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
        "detected_subscriptions": [],
        "triage_category_severity_map": {},
    }


def _run_golden_set(model_label: str) -> tuple[float, float, float, Path]:
    """Execute the golden set, write a timestamped report, assert ≥0.90 gates.

    Returns (category_accuracy, kind_accuracy, joint_accuracy, report_path).
    """
    rows = _load_golden_set()
    _assert_fixture_schema(rows)
    _assert_expected_categories_valid(rows)

    state = _build_state(rows)
    start = time.perf_counter()
    result_state = categorization_node(state)
    elapsed_s = time.perf_counter() - start

    results_by_id: dict[str, dict] = {
        r["transaction_id"]: r for r in result_state["categorized_transactions"]
    }
    for row in rows:
        results_by_id.setdefault(
            row["id"], {"category": "uncategorized", "transaction_kind": None}
        )

    # Story 11.10 / AC #12: PE-statement rows are no longer segregated. The
    # primary gate runs on the full unified set. `pe_statement_accuracy` is
    # retained as a non-gating operator-visibility metric.
    pe_rows = [r for r in rows if r.get("edge_case_tag") == "pe_statement"]

    total = len(rows)
    category_correct = sum(
        1 for row in rows
        if results_by_id[row["id"]].get("category") == row["expected_category"]
    )
    kind_correct = sum(
        1 for row in rows
        if results_by_id[row["id"]].get("transaction_kind") == row["expected_kind"]
    )
    joint_correct = sum(
        1 for row in rows
        if results_by_id[row["id"]].get("category") == row["expected_category"]
        and results_by_id[row["id"]].get("transaction_kind") == row["expected_kind"]
    )
    category_accuracy = category_correct / total if total else 0.0
    kind_accuracy = kind_correct / total if total else 0.0
    joint_accuracy = joint_correct / total if total else 0.0

    pe_total = len(pe_rows)
    pe_joint_correct = sum(
        1 for row in pe_rows
        if results_by_id[row["id"]].get("category") == row["expected_category"]
        and results_by_id[row["id"]].get("transaction_kind") == row["expected_kind"]
    )
    pe_statement_accuracy = (pe_joint_correct / pe_total) if pe_total else None

    mismatches = [
        {
            "id": row["id"],
            "description": row["description"],
            "expected_category": row["expected_category"],
            "actual_category": results_by_id[row["id"]].get("category"),
            "expected_kind": row["expected_kind"],
            "actual_kind": results_by_id[row["id"]].get("transaction_kind"),
            "edge_case_tag": row["edge_case_tag"],
        }
        for row in rows
        if results_by_id[row["id"]].get("category") != row["expected_category"]
        or results_by_id[row["id"]].get("transaction_kind") != row["expected_kind"]
    ]

    report = {
        "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
        "model_label": model_label,
        "elapsed_seconds": elapsed_s,
        "total_tokens_used": result_state.get("total_tokens_used", 0),
        "total": total,
        "main_total": total,
        "pe_total": pe_total,
        "category_correct": category_correct,
        "kind_correct": kind_correct,
        "joint_correct": joint_correct,
        "category_accuracy": category_accuracy,
        "kind_accuracy": kind_accuracy,
        "joint_accuracy": joint_accuracy,
        "pe_statement_accuracy": pe_statement_accuracy,
        "mismatches": mismatches,
    }

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%S%fZ")
    report_path = RUNS_DIR / f"{ts}-{model_label}.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))

    pe_acc_str = f"{pe_statement_accuracy:.3f}" if pe_statement_accuracy is not None else "n/a"
    print(
        f"\nGolden set run [{model_label}]: main_total={total} pe_total={pe_total} "
        f"category_accuracy={category_accuracy:.3f} "
        f"kind_accuracy={kind_accuracy:.3f} "
        f"joint_accuracy={joint_accuracy:.3f} "
        f"pe_statement_accuracy={pe_acc_str} "
        f"elapsed={elapsed_s:.2f}s "
        f"tokens={result_state.get('total_tokens_used', 0)} "
        f"report={report_path}"
    )

    assert category_accuracy >= 0.92, (
        f"[{model_label}] category_accuracy={category_accuracy:.3f} < 0.92 "
        f"(unified total={total}, pe_included={pe_total}). "
        f"See {report_path} for mismatch details."
    )
    assert kind_accuracy >= 0.92, (
        f"[{model_label}] kind_accuracy={kind_accuracy:.3f} < 0.92 "
        f"(unified total={total}, pe_included={pe_total}). "
        f"See {report_path} for mismatch details."
    )
    return category_accuracy, kind_accuracy, joint_accuracy, report_path


@pytest.mark.integration
def test_golden_set_accuracy() -> None:
    """Haiku (production model) golden-set gate.

    Story 11.3a closed the gate: category_accuracy 0.856 → 0.900, kind_accuracy
    0.978 (both ≥ 0.90) via 3 disambiguation rules + MCC table tweaks, making
    Story 11.4's description-pattern pre-pass unnecessary (TD-042 resolved).
    """
    _run_golden_set("haiku")


@pytest.mark.integration
@pytest.mark.xfail(
    strict=False,
    reason=(
        "Sonnet is not a production candidate (per Story 11.3 retrospective + "
        "Story 11.3a close). Haiku is the shipping model; this test remains as "
        "a dormant comparison only — xfail indefinitely."
    ),
)
def test_golden_set_accuracy_sonnet(monkeypatch) -> None:
    """Sonnet comparison run (AC #5). Informs future model-swap decision."""
    from app.agents import llm as llm_module

    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
    # Reset any cached LLM client singletons if present.
    for attr in ("_llm_client", "_fallback_llm_client", "_cached_llm_client"):
        if hasattr(llm_module, attr):
            setattr(llm_module, attr, None)
    _run_golden_set("sonnet")


def _assert_fixture_schema(rows: list[dict]) -> None:
    assert len(rows) >= 50, f"Golden set must contain ≥50 rows, found {len(rows)}"
    for row in rows:
        missing = REQUIRED_FIELDS - row.keys()
        assert not missing, f"Row {row.get('id')} missing required fields: {missing}"


def _assert_expected_categories_valid(rows: list[dict]) -> None:
    """Pre-flight: every expected_category must be producible by the pipeline.

    Guards against the Story-11.1 H1 finding: if the fixture labels a row with a
    category outside VALID_CATEGORIES, _parse_llm_response coerces the LLM output
    to 'other' and the row is structurally unscorable — the accuracy gate is a lie.
    """
    invalid = {
        row["id"]: row["expected_category"]
        for row in rows
        if row["expected_category"] not in VALID_CATEGORIES
    }
    assert not invalid, (
        f"Golden set rows use expected_category values not in VALID_CATEGORIES "
        f"(pipeline can never emit these → row is structurally unscorable): {invalid}. "
        f"Either expand VALID_CATEGORIES + the categorization prompt, or relabel the rows."
    )


def test_golden_set_fixture_schema() -> None:
    """Cheap, non-LLM check that fixture parses and has every required field."""
    rows = _load_golden_set()
    _assert_fixture_schema(rows)


def test_golden_set_expected_categories_valid() -> None:
    """Cheap, non-LLM check that the fixture's expected_category vocabulary is producible."""
    rows = _load_golden_set()
    _assert_expected_categories_valid(rows)


def test_gs_074_expected_category_is_atm_cash() -> None:
    """Story 11.3a AC #5: gs-074 (City24, MCC 6010) must stay labeled atm_cash.

    Guards against accidental revert — without this assertion, a future fixture
    edit could silently flip the label and the harness would still be green.
    """
    rows = _load_golden_set()
    row = next((r for r in rows if r["id"] == "gs-074"), None)
    assert row is not None, "gs-074 missing from golden_set.jsonl"
    assert row["expected_category"] == "atm_cash", (
        f"gs-074 expected_category must remain 'atm_cash' (Story 11.3a AC #5), "
        f"got {row['expected_category']!r}"
    )
    assert row["mcc"] == 6010, (
        f"gs-074 mcc must remain 6010 (Manual Cash Disbursement), got {row['mcc']!r}"
    )


def test_golden_set_edge_case_coverage() -> None:
    """Verify §4.2 minimum-per-tag coverage."""
    rows = _load_golden_set()
    minimums = {
        "self_transfer": 3,
        "deposit_top_up": 3,
        "p2p_individual": 3,
        # salary_inflow was dropped from the fixture when PE-statement edge
        # cases replaced it (Story 11.3a / 11.4 sprint). Kept at 0 to document
        # the tag's history; re-raise the minimum if salary-inflow rows are
        # re-added to the golden set.
        "salary_inflow": 0,
        "pe_statement": 8,
        "refund": 2,
        "standard": 10,
        "mcc_4829_ambiguous": 5,
        "large_outlier": 3,
        "mojibake": 2,
        "non_uah_currency": 2,
    }
    counts: dict[str, int] = {}
    for row in rows:
        tag = row["edge_case_tag"]
        counts[tag] = counts.get(tag, 0) + 1
    for tag, required in minimums.items():
        actual = counts.get(tag, 0)
        assert actual >= required, (
            f"edge_case_tag '{tag}' has {actual} rows, requires ≥ {required}"
        )
