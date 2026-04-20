"""Golden-set evaluation harness for the categorization pipeline (Story 11.1).

Loads the labeled golden set, runs it through `categorization_node` with REAL LLM
calls, computes per-axis accuracy (category, kind, joint), writes a timestamped
JSON run report, and asserts both axes meet the 90% gate.

Run with:
    cd backend && python -m pytest tests/agents/categorization/test_golden_set.py -v -s -m integration
"""

import datetime
import json
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
    transactions = [
        {
            "id": row["id"],
            "description": row["description"],
            "amount": row["amount_kopiykas"],
            "mcc": row["mcc"],
            "date": "2025-01-01",
        }
        for row in rows
    ]
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


@pytest.mark.integration
@pytest.mark.xfail(
    strict=False,
    reason="kind_accuracy < 0.90 until Story 11.3 enriches the prompt to emit transaction_kind",
)
def test_golden_set_accuracy() -> None:
    rows = _load_golden_set()
    _assert_fixture_schema(rows)
    _assert_expected_categories_valid(rows)

    state = _build_state(rows)
    result_state = categorization_node(state)

    results_by_id: dict[str, dict] = {
        r["transaction_id"]: r for r in result_state["categorized_transactions"]
    }
    for row in rows:
        results_by_id.setdefault(
            row["id"], {"category": "uncategorized", "transaction_kind": None}
        )

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
    category_accuracy = category_correct / total
    kind_accuracy = kind_correct / total
    joint_accuracy = joint_correct / total

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
        "total": total,
        "category_correct": category_correct,
        "kind_correct": kind_correct,
        "joint_correct": joint_correct,
        "category_accuracy": category_accuracy,
        "kind_accuracy": kind_accuracy,
        "joint_accuracy": joint_accuracy,
        "mismatches": mismatches,
    }

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%S%fZ")
    report_path = RUNS_DIR / f"{ts}.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))

    print(
        f"\nGolden set run: total={total} "
        f"category_accuracy={category_accuracy:.3f} "
        f"kind_accuracy={kind_accuracy:.3f} "
        f"joint_accuracy={joint_accuracy:.3f} "
        f"report={report_path}"
    )

    assert category_accuracy >= 0.90, (
        f"category_accuracy={category_accuracy:.3f} < 0.90. "
        f"See {report_path} for mismatch details."
    )
    assert kind_accuracy >= 0.90, (
        f"kind_accuracy={kind_accuracy:.3f} < 0.90. "
        f"See {report_path} for mismatch details. "
        f"Expected to fail until Story 11.3 lands."
    )


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


def test_golden_set_edge_case_coverage() -> None:
    """Verify §4.2 minimum-per-tag coverage."""
    rows = _load_golden_set()
    minimums = {
        "self_transfer": 3,
        "deposit_top_up": 3,
        "p2p_individual": 3,
        "salary_inflow": 2,
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
