# Story 11.5: Post-Parse Validation Layer with Partial-Import Semantics

Status: done

## Story

As a **user**,
I want invalid or suspect rows in my uploaded statement to be surfaced as warnings rather than silently imported as corrupt data,
So that I can trust that imported transactions are real and that anything unreliable is flagged for my review.

## Acceptance Criteria

**Given** any parser (monobank, privatbank, or generic fallback) returns rows  
**When** the validation layer runs per tech spec §5.1  
**Then** it applies rules: date plausibility (`[today - 5y, today + 1d]`), amount presence (non-zero), sign-convention consistency, description-or-identifier presence, and duplicate-rate threshold (reject wholesale if > 20% identical rows)

**Given** individual row violations (date out of range, zero amount, no identifying info)  
**When** the validation layer encounters them  
**Then** those rows are **rejected** (not persisted) with a `reason` tag; the rest of the upload proceeds normally

**Given** sign-convention violations on individual rows  
**When** the validation layer encounters them  
**Then** the row is **flagged with a warning but still persisted** (sign is a soft signal, not a hard failure)

**Given** the suspicious-duplicate-rate threshold is exceeded (> 20% of rows share the same description + amount + date)  
**When** the validation layer runs  
**Then** the parser's entire output is **rejected wholesale** — no rows persisted — and the upload returns a structured error (`reason: "suspicious_duplicate_rate"`) requesting the user re-export or contact support

**Given** a completed or partially-completed upload  
**When** the ingestion API responds (via SSE `job-complete` event)  
**Then** the payload matches tech spec §5.2: `{upload_id, imported_transaction_count, rejected_rows: [{row_number, reason, raw_row}], warnings: [{row_number, reason}], mojibake_detected, schema_detection_source}`

**Given** the upload completion UI (existing `UploadSummaryCard` component, `frontend/src/features/upload/components/UploadSummaryCard.tsx`)  
**When** the SSE response contains `rejected_rows` or `warnings`  
**Then** the UI displays a "Couldn't process N rows" expandable section listing row numbers and reasons — the user can proceed to the Teaching Feed regardless

## Tasks / Subtasks

- [x] Task 1 — Create `parse_validator.py` service (AC: #1, #2, #3, #4)
  - [x] 1.1 Define `ValidationResult` dataclass: `accepted`, `rejected_rows`, `warnings`, `wholesale_rejected`, `wholesale_rejection_reason`
  - [x] 1.2 Implement `validate_parsed_rows(rows, amount_sign_convention, today)` with all 5 per-row rules from §5.1
  - [x] 1.3 Implement wholesale duplicate-rate check (> 20% identical `(description, amount, date)` tuples) — reject ALL rows if triggered
  - [x] 1.4 Write unit tests: `backend/tests/test_parse_validator.py` covering every rule and the wholesale-rejection path

- [x] Task 2 — Wire validator into `parser_service.py` (AC: #1, #2, #3, #4)
  - [x] 2.1 In `_parse_and_build_records()`, call `validate_parsed_rows()` after `parser.parse()` returns, before building `Transaction` ORM objects
  - [x] 2.2 On wholesale rejection: raise `WholesaleRejectionError` (new exception) with rejection reason; caller handles it as a non-retryable terminal failure
  - [x] 2.3 Add `validation_rejected_count`, `validation_warnings_count`, `wholesale_rejected`, `rejected_rows`, `warnings` fields to `ParseAndStoreResult`
  - [x] 2.4 Pass `format_result.amount_sign_convention` to the validator (added the field to `FormatDetectionResult`; populated for monobank/privatbank)

- [x] Task 3 — Propagate validation results through the Celery task (AC: #5)
  - [x] 3.1 Catch `WholesaleRejectionError` and mark job failed with `WHOLESALE_REJECTION` code (non-retryable, `isRetryable: False`)
  - [x] 3.2 Add `rejected_rows`, `warnings`, `schema_detection_source`, `mojibake_detected` to `result_data` dict
  - [x] 3.3 Include these fields in the SSE `job-complete` event payload published via `publish_job_progress()`

- [x] Task 4 — Frontend: update types and `UploadSummaryCard` (AC: #6)
  - [x] 4.1 Extend the `JobCompleteEvent` TypeScript type to include `rejectedRows`, `warnings`, `schemaDetectionSource`, `mojibakeDetected`
  - [x] 4.2 Add `rejectedRows?` and `warnings?` optional props to `UploadSummaryCard`
  - [x] 4.3 Render a collapsible "Couldn't process N rows" `<details>` block when `rejectedRows.length > 0`, listing row number + localized reason
  - [x] 4.4 Pass the new fields from `UploadDropzone` → `UploadSummaryCard` (via `jobStatus.result`)

- [x] Task 5 — Integration test (AC: all)
  - [x] 5.1 Add `backend/tests/test_parser_service_validation.py`: exercises `_parse_and_build_records()` with stubbed parsers triggering each rejection rule and the wholesale path

## Dev Notes

### Where the Validation Layer Fits

The insertion point is `backend/app/services/parser_service.py`, function `_parse_and_build_records()` (lines 38–108). The call sequence after this change:

```
parser.parse() → ParseResult
  ↓
validate_parsed_rows(result.transactions, amount_sign_convention)
  ↓ wholesale_rejected == True → raise WholesaleRejectionError
  ↓ wholesale_rejected == False
ValidationResult.rejected_rows → build FlaggedImportRow records (merged with parser's flagged_rows)
ValidationResult.warnings     → stored in ParseAndStoreResult.warnings
ValidationResult.accepted     → build Transaction ORM objects (replaces result.transactions)
```

The validator receives `list[TransactionData]` (already parsed; parsers already flag format-level errors). The validation layer is a second defence pass for semantic validity.

### New File: `backend/app/services/parse_validator.py`

```python
from dataclasses import dataclass, field
from datetime import date, timedelta
from collections import Counter

from app.agents.ingestion.parsers.base import FlaggedRow, TransactionData

_DUPLICATE_RATE_THRESHOLD = 0.20
_DATE_LOOKBACK_YEARS = 5


@dataclass
class ValidationResult:
    accepted: list[TransactionData] = field(default_factory=list)
    rejected_rows: list[FlaggedRow] = field(default_factory=list)
    warnings: list[FlaggedRow] = field(default_factory=list)
    wholesale_rejected: bool = False
    wholesale_rejection_reason: str | None = None


def validate_parsed_rows(
    rows: list[TransactionData],
    amount_sign_convention: str | None = None,
    today: date | None = None,
) -> ValidationResult:
    today = today or date.today()
    earliest = today.replace(year=today.year - _DATE_LOOKBACK_YEARS)
    latest = today + timedelta(days=1)

    # Rule 6 — wholesale duplicate check first (cheapest rejection)
    if rows:
        key_counts = Counter(
            (r.description, r.amount, r.date.date() if hasattr(r.date, "date") else r.date)
            for r in rows
        )
        most_common_count = key_counts.most_common(1)[0][1]
        if most_common_count / len(rows) > _DUPLICATE_RATE_THRESHOLD:
            return ValidationResult(
                wholesale_rejected=True,
                wholesale_rejection_reason="suspicious_duplicate_rate",
            )

    result = ValidationResult()
    for idx, txn in enumerate(rows):
        row_num = idx + 1  # 1-based; parsers use 1-based row_number

        # Rule 1 — date plausibility
        txn_date = txn.date.date() if hasattr(txn.date, "date") else txn.date
        if not (earliest <= txn_date <= latest):
            result.rejected_rows.append(
                FlaggedRow(row_number=row_num, raw_data=txn.raw_data, reason="date_out_of_range")
            )
            continue

        # Rule 2 — amount presence (zero = no meaningful transaction)
        if txn.amount == 0:
            result.rejected_rows.append(
                FlaggedRow(row_number=row_num, raw_data=txn.raw_data, reason="zero_or_null_amount")
            )
            continue

        # Rule 5 — description presence
        has_description = bool(txn.description and txn.description.strip())
        has_identifier = txn.mcc is not None
        if not has_description and not has_identifier:
            result.rejected_rows.append(
                FlaggedRow(row_number=row_num, raw_data=txn.raw_data, reason="no_identifying_info")
            )
            continue

        # Rule 4 — sign convention (soft: warn, do not reject)
        if amount_sign_convention == "positive_is_income" and txn.amount < 0:
            # Negative amount under positive_is_income convention is suspicious but not fatal
            result.warnings.append(
                FlaggedRow(row_number=row_num, raw_data=txn.raw_data, reason="sign_convention_mismatch")
            )
        elif amount_sign_convention == "negative_is_outflow" and txn.amount > 0:
            result.warnings.append(
                FlaggedRow(row_number=row_num, raw_data=txn.raw_data, reason="sign_convention_mismatch")
            )

        result.accepted.append(txn)

    return result
```

**Note on Rule 3 (non_numeric_amount):** `TransactionData.amount` is typed `int` (kopiykas). Parsers already emit `FlaggedRow` for rows where amount parsing fails. The validation layer therefore does not need to re-check numeric type — Rule 2 (zero check) covers the residual case. This is intentional and documented in the service.

### `ParseAndStoreResult` Extension (`parser_service.py`)

Add to the existing `@dataclass`:

```python
@dataclass
class ParseAndStoreResult:
    total_rows: int
    parsed_count: int
    flagged_count: int
    persisted_count: int
    duplicates_skipped: int = 0
    validation_rejected_count: int = 0          # NEW
    validation_warnings_count: int = 0          # NEW
    wholesale_rejected: bool = False            # NEW
    rejected_rows: list[dict] = field(default_factory=list)   # NEW — [{row_number, reason, raw_row}]
    warnings: list[dict] = field(default_factory=list)        # NEW — [{row_number, reason}]
```

### New Exception: `WholesaleRejectionError`

Add to `parser_service.py` alongside `UnsupportedFormatError`:

```python
class WholesaleRejectionError(Exception):
    """Raised when validation rejects the entire parser output (e.g. suspicious_duplicate_rate)."""
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"Wholesale rejection: {reason}")
```

In `processing_tasks.py` catch block, treat this as non-retryable (same pattern as `UnsupportedFormatError`).

### `result_data` Dict Changes (`processing_tasks.py` lines 370-386)

Add these keys to the existing `result_data` dict:

```python
result_data = {
    # ... existing keys ...
    "rejected_rows": [
        {"row_number": r["row_number"], "reason": r["reason"], "raw_row": r["raw_row"]}
        for r in store_result.rejected_rows
    ],
    "warnings": [
        {"row_number": w["row_number"], "reason": w["reason"]}
        for w in store_result.warnings
    ],
    "schema_detection_source": "known_bank_parser"
        if format_result.bank_format in ("monobank", "privatbank")
        else "generic_fallback",
    "mojibake_detected": False,   # Story 11.6 will populate this
}
```

### SSE Event Extension

The `job-complete` SSE event is published via `publish_job_progress()`. Extend the payload:

```python
# In the job-complete publish call:
{
    "event": "job-complete",
    # ... existing fields (totalInsights, duplicatesSkipped, newTransactions, bankName, dateRange) ...
    "rejectedRows": result_data.get("rejected_rows", []),
    "warnings": result_data.get("warnings", []),
    "schemaDetectionSource": result_data.get("schema_detection_source", "known_bank_parser"),
    "mojibakeDetected": result_data.get("mojibake_detected", False),
}
```

### Frontend: TypeScript Types

Locate the `JobCompletePayload` / job status result type (likely in `frontend/src/features/upload/types.ts` or similar). Add:

```typescript
interface RejectedRow {
  row_number: number;
  reason: string;
  raw_row: Record<string, unknown>;
}

interface UploadWarning {
  row_number: number;
  reason: string;
}

// Extend existing JobCompletePayload:
rejectedRows?: RejectedRow[];
warnings?: UploadWarning[];
schemaDetectionSource?: "known_bank_parser" | "generic_fallback" | "cached_fingerprint" | "llm_detected";
mojibakeDetected?: boolean;
```

`cached_fingerprint` and `llm_detected` are Story 11.7 values — include in the union now to avoid a breaking type change later.

### Frontend: `UploadSummaryCard` Extension

The component is at `frontend/src/features/upload/components/UploadSummaryCard.tsx` (lines 21-107). Add optional props:

```typescript
interface UploadSummaryCardProps {
  // ... existing props ...
  rejectedRows?: RejectedRow[];
  warnings?: UploadWarning[];
}
```

Render below the existing summary stats — a collapsible section (use existing Shadcn/Radix `Collapsible` if already in project, else a simple `<details>` element):

```
⚠️ Couldn't process 3 rows  [v]
  Row 23 — date_out_of_range
  Row 41 — zero_or_null_amount
  Row 67 — no_identifying_info
```

Only show if `rejectedRows.length > 0`. Warnings (sign_convention_mismatch) are informational — show inline as a softer note without an expand/collapse (they're persisted, not rejected).

### Project Structure Notes

- New file: `backend/app/services/parse_validator.py`
- Modified: `backend/app/services/parser_service.py` (lines 25-108 affected)
- Modified: `backend/app/tasks/processing_tasks.py` (steps 4 and 7 affected)
- Modified: `frontend/src/features/upload/components/UploadSummaryCard.tsx`
- Modified: `frontend/src/features/upload/` — job status types
- New tests: `backend/tests/services/test_parse_validator.py`
- New tests: `backend/tests/services/test_parser_service_validation.py`

**Do NOT touch** the parser classes themselves (`monobank.py`, `privatbank.py`, `generic.py`). The validation layer is a pure post-parse addition.

**Do NOT add `transaction_kind` field** — that is Story 11.2. This story does not touch categorization.

**Do NOT add encoding detection** — that is Story 11.6. Leave `mojibake_detected: False` hardcoded.

**Do NOT add `bank_format_registry`** — that is Story 11.7. `schema_detection_source` for now is always `"known_bank_parser"` or `"generic_fallback"`.

### Sign Convention Note

`FormatDetectionResult` (returned by `format_detector.py`) carries `amount_sign_convention`. This value is already threaded into `_parse_and_build_records()` via `format_result`. Pass it through to `validate_parsed_rows()` at the call site. If `amount_sign_convention` is `None` (unknown format), skip Rule 4 entirely.

### Validation Insertion Point — Exact Lines

```python
# parser_service.py — _parse_and_build_records() (line 38)
# After line 65 (result = generic.parse(...) or result = parser.parse(...)):

from app.services.parse_validator import validate_parsed_rows, ValidationResult

validation = validate_parsed_rows(
    rows=result.transactions,
    amount_sign_convention=format_result.amount_sign_convention,  # may be None
)
if validation.wholesale_rejected:
    raise WholesaleRejectionError(validation.wholesale_rejection_reason)

# Then use validation.accepted instead of result.transactions:
transactions = [
    Transaction(
        ...
    )
    for txn_data in validation.accepted  # ← was result.transactions
]

# Append validation rejections to parser's existing flagged_rows:
validation_flagged = [
    FlaggedImportRow(
        user_id=user_id,
        upload_id=upload_id,
        row_number=fr.row_number,
        raw_data=fr.raw_data if isinstance(fr.raw_data, dict) else {"raw": fr.raw_data},
        reason=fr.reason,
    )
    for fr in validation.rejected_rows
]
flagged_records = [
    ...existing flagged_records from result.flagged_rows...
] + validation_flagged
```

### References

- Tech spec §5.1 (validation rules): [Source: docs/../_bmad-output/planning-artifacts/tech-spec-ingestion-categorization.md#5-parsing-validation-contract-story-115]
- Tech spec §5.2 (response shape): same file, §5.2
- `ParseResult` / `FlaggedRow` / `TransactionData`: [Source: backend/app/agents/ingestion/parsers/base.py]
- `_parse_and_build_records()` insertion point: [Source: backend/app/services/parser_service.py#L38]
- `result_data` dict: [Source: backend/app/tasks/processing_tasks.py#L370-386]
- Upload completion UI: [Source: frontend/src/features/upload/components/UploadSummaryCard.tsx#L21-107]
- `publish_job_progress()` SSE publishing: [Source: backend/app/tasks/processing_tasks.py]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Backend validation layer landed as `app/services/parse_validator.py` with 16 unit tests covering every per-row rule (date, amount, identifying info, sign convention) plus the wholesale-rejection path.
- Wholesale duplicate-rate rule guards against single-row corpora (`most_common_count > 1`) so a one-row upload isn't spuriously flagged as 100% duplicate.
- `FormatDetectionResult.amount_sign_convention` added; `monobank`/`privatbank` set to `"negative_is_outflow"`, unknown formats leave it `None` (validator skips Rule 4).
- `WholesaleRejectionError` surfaces in `processing_tasks.py` as a non-retryable `WHOLESALE_REJECTION` job failure — the job-failed SSE event carries `isRetryable: false`.
- `job-complete` SSE payload now carries `rejectedRows`, `warnings`, `schemaDetectionSource`, `mojibakeDetected`; fields plumbed through `JobCompleteEvent` → `useJobStatus` → `UploadSummaryCard`.
- `UploadSummaryCard` renders a `<details>` "Couldn't process N rows" collapsible with localized reason labels (en/uk); warning rows get a softer inline note. New i18n keys added to `messages/en.json` and `messages/uk.json`.
- Tests were placed at `backend/tests/test_parse_validator.py` and `backend/tests/test_parser_service_validation.py` to match the repo's flat `tests/` layout (story referenced `tests/services/`; flat layout wins to stay consistent).
- Regression: 4 pre-existing test failures remain on `main` (unrelated to this story — `test_profile_service.test_creates_profile_from_transactions`, `test_profile_service.test_mixed_categories`, `test_sse_streaming.test_happy_path_publishes_progress_events`, `test_processing_tasks.test_insight_ready_events_emitted_per_insight`). Verified via `git stash` before this change. 525 tests pass.
- Frontend: all 70 upload-module Vitest tests pass; `tsc --noEmit` shows no new errors in touched files.

### File List

- backend/app/services/parse_validator.py (new)
- backend/app/services/parser_service.py (modified)
- backend/app/services/format_detector.py (modified — added `amount_sign_convention`)
- backend/app/tasks/processing_tasks.py (modified)
- backend/tests/test_parse_validator.py (new)
- backend/tests/test_parser_service_validation.py (new)
- backend/tests/test_processing_tasks.py (modified — `_EmptyResult` fixture)
- frontend/src/features/upload/types.ts (modified)
- frontend/src/features/upload/hooks/use-job-status.ts (modified)
- frontend/src/features/upload/components/UploadDropzone.tsx (modified)
- frontend/src/features/upload/components/UploadSummaryCard.tsx (modified)
- frontend/messages/en.json (modified)
- frontend/messages/uk.json (modified)
- VERSION (bumped 1.19.0 → 1.20.0)

## Change Log

- 2026-04-20 — Story 11.5 implemented: post-parse validation layer with per-row rejections, wholesale duplicate-rate guard, partial-import SSE payload, and `UploadSummaryCard` rejection/warning UI.
- 2026-04-20 — Version bumped from 1.19.0 to 1.20.0 per story completion (MINOR — new user-facing validation surface).
- 2026-04-20 — Code review: fixed 2 HIGH + 4 MEDIUM issues (sign-convention plumbed through Celery path, resume-upload SSE payload now includes validation fields, Feb 29 leap-year crash, dropped dead `wholesale_rejected` field, surfaced validation counts in structured logs). Tests: 642 passed, 0 new regressions.

## Code Review (2026-04-20)

**Verdict:** All HIGH and MEDIUM findings resolved; story → done.

**Fixed:**
- H1 — `amount_sign_convention` now plumbed through `process_upload`'s `FormatDetectionResult` reconstruction via new `get_sign_convention()` helper, so Rule 4 actually runs in production (previously dead code). Unit test added.
- H2 — `resume_upload`'s `job-complete` SSE payload now carries `rejectedRows`, `warnings`, `schemaDetectionSource`, `mojibakeDetected` from persisted `result_data`.
- M1 — `parse_validator._date_floor` guarded against Feb 29 × non-leap-year `ValueError` (falls back to Feb 28); test added.
- M2 — Removed always-`False` `ParseAndStoreResult.wholesale_rejected` (dead field — wholesale path raises).
- M3 — `validation_rejected_count` / `validation_warnings_count` now appear in the `Parse and store complete` structured log `extra`.
- M4 — `persisted_count` semantic (= txns + flagged rows persisted) clarified; downstream `new_transactions` calc unchanged.

**Deferred — tech-debt register:**
- L2 → [TD-043](../../docs/tech-debt.md). Warnings list in `UploadSummaryCard` is count-only; mirror the rejections `<details>` once more warning types ship.
- L3 → [TD-044](../../docs/tech-debt.md). Reason strings hand-mirrored backend↔frontend; centralize as shared enum when Epic 11.6/11.7 add more reasons.

**Deferred — story-local:**
- L1 — Wholesale duplicate-rate key ignores `currency_code`. Edge case (cross-currency false match); cost of fix ≈ cost of test; kept story-local as minor follow-up.
