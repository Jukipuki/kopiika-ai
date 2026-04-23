"""Cross-provider regression matrix for AI-assisted schema detection (Story 9.5c).

Calls `detect_schema(...)` directly — the LLM-invoking entry — so no DB
coupling is required. `resolve_bank_format(...)` owns the header-fingerprint
cache and the DB transaction, but cache-miss behaviour is already covered by
Story 11.7's own integration tests.

NOTE: intentionally NO stubbing of `detect_schema` itself. The full path
(prompt build + LLM invoke + response parse + mapping-shape validation)
runs against each provider. Hand-crafted JSON shortcuts would prove parsing,
not cross-provider equivalence — see the README for the non-scope list.
"""

from __future__ import annotations

import time
from typing import Any

import pytest

from app.services import schema_detection

from .conftest import PROVIDERS, load_fixture, write_run_report

pytestmark = [
    pytest.mark.provider_matrix,
    pytest.mark.parametrize("provider", PROVIDERS),
]


def _present_abstract_keys(mapping: dict) -> set[str]:
    """Return the set of abstract `{date, amount, description, ...}` keys the
    mapping provides evidence for.

    `detect_schema` returns mapping keys like `date_column`, `amount_column`,
    `description_column`. The equivalence contract (AC #2) asserts presence of
    the abstract key set declared in each fixture's `expected_field_map_keys`;
    value strings differ across providers and are not asserted.
    """
    present: set[str] = set()
    if mapping.get("date_column"):
        present.add("date")
    if mapping.get("amount_column"):
        present.add("amount")
    if mapping.get("description_column"):
        present.add("description")
    return present


def test_schema_detection_field_map_per_provider(
    provider: str,
    _provider_setup: dict[str, Any],
) -> None:
    cases = load_fixture("schema_detection_cases.json")
    results: list[dict] = []
    failures: list[str] = []

    for case in cases:
        t0 = time.monotonic()
        try:
            detected = schema_detection.detect_schema(
                header_row=case["header_row"],
                sample_rows=case["sample_rows"],
                encoding=case["encoding"],
            )
        except Exception as exc:  # noqa: BLE001
            latency_ms = int((time.monotonic() - t0) * 1000)
            results.append({
                "case_name": case["name"],
                "provider": provider,
                "passed": False,
                "error": f"{type(exc).__name__}: {exc}",
                "latency_ms": latency_ms,
            })
            failures.append(f"case {case['name']!r} on {provider}: {exc!r}")
            continue
        latency_ms = int((time.monotonic() - t0) * 1000)

        mapping = detected.detected_mapping
        present = _present_abstract_keys(mapping)
        required = set(case["expected_field_map_keys"])
        missing = required - present
        passed = not missing

        results.append({
            "case_name": case["name"],
            "provider": provider,
            "detected_mapping": mapping,
            "detection_confidence": detected.detection_confidence,
            "detected_bank_hint": detected.detected_bank_hint,
            "expected_field_map_keys": sorted(required),
            "present_keys": sorted(present),
            "missing_required_keys": sorted(missing),
            "passed": passed,
            "latency_ms": latency_ms,
        })

        if not passed:
            failures.append(
                f"case {case['name']!r} on provider={provider}: "
                f"missing required keys {sorted(missing)}; mapping={mapping!r}"
            )

    report_path = write_run_report("schema_detection", provider, results, _provider_setup)
    print(f"[provider-matrix] wrote run-report: {report_path}")

    if failures:
        pytest.fail("\n".join(failures))
