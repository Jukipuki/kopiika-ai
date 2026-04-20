# Story 11.6: Encoding Detection with Mojibake Flagging

Status: done

## Story

As a **user uploading a statement with unusual encoding**,
I want the pipeline to auto-detect the file encoding and surface a warning if descriptions look corrupted,
So that merchant names used for categorization aren't silently reduced to garbage strings.

## Acceptance Criteria

**Given** a raw uploaded file  
**When** ingestion begins  
**Then** `charset-normalizer` is invoked on the bytes to detect encoding; the detected encoding and chaos score are logged per tech spec §7

**Given** decoding produces more than 5% U+FFFD replacement characters across transaction description fields  
**When** the partial-import response is constructed  
**Then** `mojibake_detected: true` is set in the response and the upload is tagged in observability for alerting

**Given** decoding fails under the detected encoding  
**When** the pipeline runs  
**Then** it falls back to UTF-8 with `errors="replace"` rather than raising an unhandled exception; the upload proceeds with `mojibake_detected: true` flagged

**Given** the detected encoding is UTF-8 with high confidence  
**When** ingestion runs  
**Then** no warning is emitted and no observability flag is set (happy-path behavior unchanged)

## Tasks / Subtasks

- [x] Task 1 — Add `detect_mojibake()` to `format_detector.py` (AC: #1, #2, #3, #4)
  - [x] 1.1 Implement `detect_mojibake(descriptions: list[str]) -> tuple[bool, float]` — count U+FFFD (`\ufffd`) characters across all description chars combined; threshold is > 5% replacement rate; return `(is_mojibake, replacement_char_rate)`
  - [x] 1.2 Module-level constant `_MOJIBAKE_THRESHOLD = 0.05` (do not hardcode inline)
  - [x] 1.3 Unit tests: add to `backend/tests/test_format_detector.py` — cover: empty list, all-clean descriptions, U+FFFD rate exactly at threshold (boundary), over threshold (>5%), under threshold (<5%), descriptions that are empty strings

- [x] Task 2 — Wire mojibake detection into `parser_service.py` (AC: #1, #2)
  - [x] 2.1 Add two new fields to `ParseAndStoreResult` dataclass (line 27): `mojibake_detected: bool = False` and `mojibake_replacement_rate: float = 0.0`
  - [x] 2.2 After the `validate_parsed_rows()` call at line 80, extract descriptions from `validation.accepted` (use `txn.description or ""` — description may be None); call `detect_mojibake(descriptions)` and populate `store_result.mojibake_detected` and `store_result.mojibake_replacement_rate`
  - [x] 2.3 When `mojibake_detected` is True, emit a `logger.warning("encoding.mojibake_detected", extra={"replacement_char_rate": mojibake_rate, "transaction_count": len(validation.accepted)})` at the parser service level

- [x] Task 3 — Verify and fix decoding fallback in parsers (AC: #3)
  - [x] 3.1 Read `MonobankParser`, `PrivatBankParser`, and `GenericParser` — identify exactly where they decode `file_bytes` (likely in `parse()` method); if any call `file_bytes.decode(encoding)` without `errors="replace"`, wrap it: try the detected encoding first, except `(UnicodeDecodeError, LookupError)` → fall back to `file_bytes.decode("utf-8", errors="replace")` and log a warning
  - [x] 3.2 `_decode_content()` in `format_detector.py` (line 89–91) does not use `errors="replace"` — it is only called inside `detect_format()` which already has a `UnicodeDecodeError` catch at lines 166–169; verify this is sufficient and no parsers call `_decode_content()` directly. If the parsers handle decoding separately, ensure they also have the fallback.
  - [x] 3.3 Add unit test: parser given bytes that fail under detected encoding still returns a result with `mojibake_detected: True` (not an unhandled exception)

- [x] Task 4 — Replace hardcoded `False` in `processing_tasks.py` (AC: #2, #4)
  - [x] 4.1 Replace `"mojibake_detected": False` at line 400 with `result.mojibake_detected`
  - [x] 4.2 Replace `"mojibakeDetected": False` in the SSE `job-complete` publish at line ~419 with `result.mojibake_detected`
  - [x] 4.3 When `result.mojibake_detected` is True, emit observability log immediately after the `result_data` dict is built: `logger.warning("parser.mojibake_detected", extra={"upload_id": str(upload.id), "encoding": upload.detected_encoding or format_result.encoding, "replacement_char_rate": result.mojibake_replacement_rate})`

- [x] Task 5 — Integration tests (AC: all)
  - [x] 5.1 In `backend/tests/test_parser_service_validation.py`: add a test that stubs the parser returning transactions with U+FFFD-heavy descriptions (>5% rate); verify `ParseAndStoreResult.mojibake_detected == True` and `mojibake_replacement_rate > 0.05`
  - [x] 5.2 Add happy-path test: clean UTF-8 descriptions → `mojibake_detected == False`, `mojibake_replacement_rate == 0.0`

## Dev Notes

### Architecture: Where Mojibake Detection Fits

The detection runs after parsing and validation, before the result is returned to the Celery task:

```
format_detector.detect_format(file_bytes)     ← encoding detected here (already exists)
  ↓ FormatDetectionResult (encoding, delimiter, bank_format)
_parse_and_build_records()
  parser.parse(file_bytes, encoding, delimiter) ← parsers decode here
    ↓ ParseResult (transactions, flagged_rows)
  validate_parsed_rows(result.transactions)     ← Story 11.5 (done)
    ↓ ValidationResult (accepted, rejected_rows, warnings)
  detect_mojibake([txn.description for txn in validation.accepted])  ← NEW (Story 11.6)
    ↓ (mojibake_detected: bool, replacement_char_rate: float)
  → ParseAndStoreResult (includes mojibake_detected, mojibake_replacement_rate)
```

Mojibake detection in `processing_tasks.py`:
```
result = parse_and_store_transactions(...)   ← calls _parse_and_build_records internally
result.mojibake_detected                     ← replaces hardcoded False at lines 400 + 419
if result.mojibake_detected:
    logger.warning("parser.mojibake_detected", extra={...})  ← new observability event
```

### `detect_mojibake()` Implementation Sketch

Add to `backend/app/services/format_detector.py` after `detect_encoding()`:

```python
_MOJIBAKE_THRESHOLD = 0.05

def detect_mojibake(descriptions: list[str]) -> tuple[bool, float]:
    if not descriptions:
        return False, 0.0
    total_chars = sum(len(d) for d in descriptions)
    if total_chars == 0:
        return False, 0.0
    replacement_count = sum(d.count("\ufffd") for d in descriptions)
    rate = replacement_count / total_chars
    return rate > _MOJIBAKE_THRESHOLD, rate
```

### `ParseAndStoreResult` Extension (`parser_service.py` line 27)

```python
@dataclass
class ParseAndStoreResult:
    total_rows: int
    parsed_count: int
    flagged_count: int
    persisted_count: int
    duplicates_skipped: int = 0
    validation_rejected_count: int = 0
    validation_warnings_count: int = 0
    rejected_rows: list[dict] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)
    mojibake_detected: bool = False          # NEW
    mojibake_replacement_rate: float = 0.0  # NEW
```

### Wiring in `_parse_and_build_records()` (`parser_service.py`)

After the `validate_parsed_rows()` call (currently line 80–85), add:

```python
from app.services.format_detector import detect_mojibake

descriptions = [txn.description or "" for txn in validation.accepted]
mojibake_flag, mojibake_rate = detect_mojibake(descriptions)
if mojibake_flag:
    logger.warning(
        "encoding.mojibake_detected",
        extra={"replacement_char_rate": mojibake_rate, "transaction_count": len(validation.accepted)},
    )
```

Then populate in `ParseAndStoreResult` return:
```python
store_result.mojibake_detected = mojibake_flag
store_result.mojibake_replacement_rate = mojibake_rate
```

### Observability Event (`processing_tasks.py`)

Add after `job.result_data = {...}` at line ~402:

```python
if result.mojibake_detected:
    logger.warning(
        "parser.mojibake_detected",
        extra={
            "upload_id": str(upload.id),
            "encoding": format_result.encoding,
            "replacement_char_rate": result.mojibake_replacement_rate,
        },
    )
```

This satisfies tech spec §9: event `parser.mojibake_detected` with fields `upload_id`, `encoding`, `replacement_char_rate`.

### charset-normalizer: `chaos` vs `coherence`

The existing `detect_encoding()` at [format_detector.py:86](backend/app/services/format_detector.py#L86) returns `result.coherence` (higher = more confident). Tech spec §7 mentions `result.chaos` (lower = less chaotic = more confident). These are inverses. **Do not change `detect_encoding()` signature** — it's already in production. The observability event logs `replacement_char_rate` (the per-description signal), which is the definitive mojibake indicator. The chaos score from encoding detection is supplementary and already captured in the existing `detect_format()` log at line 189.

### Fallback Decoding — Scope Check

`format_detector.detect_format()` at lines 164–169 already handles `UnicodeDecodeError` for the header-detection path (falls back to UTF-8 with `errors="replace"`). However, each parser (MonobankParser, PrivatBankParser, GenericParser) independently decodes `file_bytes` inside their `parse()` method using the encoding from `FormatDetectionResult`. If those parsers call `file_bytes.decode(encoding)` without `errors="replace"`, a misdetected encoding can still crash the pipeline.

Task 3.1 requires reading the three parsers to confirm. The fix pattern if needed:

```python
try:
    text = file_bytes.decode(encoding)
except (UnicodeDecodeError, LookupError):
    logger.warning("Parser decode fallback to utf-8 with replacement", extra={"encoding": encoding})
    text = file_bytes.decode("utf-8", errors="replace")
```

After this fallback, descriptions in the parsed rows will contain U+FFFD characters, which `detect_mojibake()` will catch — so AC #3 is satisfied.

### Project Structure Notes

- Modified: `backend/app/services/format_detector.py` (add `detect_mojibake()` + `_MOJIBAKE_THRESHOLD`)
- Modified: `backend/app/services/parser_service.py` (add 2 fields to `ParseAndStoreResult`, wire call after validation, conditional ~3 lines)
- Modified: `backend/app/tasks/processing_tasks.py` (lines 400, ~419 replace `False`; add observability `logger.warning` block)
- Possibly modified: `backend/app/agents/ingestion/parsers/monobank.py`, `privatbank.py`, `generic.py` (add decode fallback if missing — Task 3)
- New/modified tests: `backend/tests/test_format_detector.py`, `backend/tests/test_parser_service_validation.py`

**Do NOT touch:**
- Frontend — `mojibakeDetected` is already plumbed end-to-end from Story 11.5 (types, SSE hook, UploadSummaryCard). This story only replaces the hardcoded `False` value. No frontend changes needed.
- Bank format registry — that is Story 11.7
- `transaction_kind` field — that is Story 11.2
- `UploadSummaryCard` mojibake UI display — not in scope (field is in payload but no dedicated UI treatment specified for 11.6)

### Constraints from Story 11.5 (Previous Story)

- Tests are in flat `backend/tests/` layout (not `tests/services/`); keep new tests there
- 4 pre-existing test failures remain on `main` unrelated to this work (test_profile_service ×2, test_sse_streaming, test_processing_tasks); do not count these as regressions
- TD-044: reason strings backend↔frontend mirrored — this story adds no new per-row reasons, so TD-044 scope is unchanged
- `amount_sign_convention` is threaded through `FormatDetectionResult` (Story 11.5 added `get_sign_convention()` in format_detector.py)

### References

- Tech spec §7 (encoding detection contract): [Source: _bmad-output/planning-artifacts/tech-spec-ingestion-categorization.md#7-encoding-detection-story-116]
- Tech spec §9 (observability events): [Source: _bmad-output/planning-artifacts/tech-spec-ingestion-categorization.md#9-observability]
- `detect_encoding()` function: [Source: backend/app/services/format_detector.py#L77]
- Existing UnicodeDecodeError fallback: [Source: backend/app/services/format_detector.py#L164-169]
- `ParseAndStoreResult` dataclass: [Source: backend/app/services/parser_service.py#L27]
- `validate_parsed_rows()` integration point: [Source: backend/app/services/parser_service.py#L80-85]
- `mojibake_detected: False` hardcoded (result_data): [Source: backend/app/tasks/processing_tasks.py#L400]
- `mojibakeDetected: False` hardcoded (SSE publish): [Source: backend/app/tasks/processing_tasks.py#L419]
- Story 11.5 completion notes (files modified, regression list): [Source: _bmad-output/implementation-artifacts/11-5-post-parse-validation-layer-partial-import-semantics.md]
- `charset-normalizer>=3.4.0` dep: [Source: backend/pyproject.toml]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.7 (1M context) — `claude-opus-4-7[1m]`

### Debug Log References

- New unit tests: `backend/tests/test_format_detector.py` (9 cases, all pass)
- Parser integration tests: `backend/tests/test_parser_service_validation.py` (2 new cases, all pass)
- Decode fallback regression test: `backend/tests/test_monobank_parser.py::TestMonobankDecodeFallback` (1 case, passes)
- Full regression: 7 failures observed but all attributable to Story 11.2 parallel work (categorization/node.py, state.py, transaction.py changes) + 2 pre-existing 11.5 residue (test_sse_streaming, test_processing_tasks::TestInsightReadySSEEvents). None caused by 11.6 changes — verified via `git stash` baseline comparison.

### Completion Notes List

- `detect_mojibake()` added to `format_detector.py`: strictly-greater-than comparison against `_MOJIBAKE_THRESHOLD = 0.05`, so exactly 5% is NOT flagged (documented in tests). Empty list and all-empty-string inputs short-circuit to `(False, 0.0)` to avoid division by zero.
- `ParseAndStoreResult` gained two fields: `mojibake_detected: bool` and `mojibake_replacement_rate: float` — defaulted so existing construction sites compile unchanged.
- Wired call site lives in `_parse_and_build_records()` immediately after `validate_parsed_rows()`; emits `encoding.mojibake_detected` warning at the parser-service level only when the flag trips.
- All three parsers (`monobank`, `privatbank`, `generic`) now wrap `file_bytes.decode(encoding)` in a `try/except (UnicodeDecodeError, LookupError)` that falls back to `utf-8` with `errors="replace"` and logs `parser.decode_fallback` — satisfies AC #3.
- `processing_tasks.py`: `result_data.mojibake_detected` and SSE `mojibakeDetected` now reflect `result.mojibake_detected`; observability event `parser.mojibake_detected` fires immediately after `result_data` assignment per tech spec §9.
- Frontend untouched per story notes — plumbing already exists from 11.5.

### File List

- backend/app/services/format_detector.py (modified — added `_MOJIBAKE_THRESHOLD` and `detect_mojibake()`)
- backend/app/services/parser_service.py (modified — added 2 fields to `ParseAndStoreResult`, wired mojibake detection post-validation)
- backend/app/agents/ingestion/parsers/monobank.py (modified — decode fallback)
- backend/app/agents/ingestion/parsers/privatbank.py (modified — decode fallback)
- backend/app/agents/ingestion/parsers/generic.py (modified — decode fallback)
- backend/app/tasks/processing_tasks.py (modified — replaced hardcoded `False`, added `parser.mojibake_detected` observability event)
- backend/tests/test_format_detector.py (new — unit tests for `detect_mojibake()`)
- backend/tests/test_parser_service_validation.py (modified — 2 new mojibake integration tests)
- backend/tests/test_monobank_parser.py (modified — `TestMonobankDecodeFallback` added)
- backend/tests/test_privatbank_parser.py (modified — `TestPrivatBankDecodeFallback` added during code review)
- backend/tests/test_generic_parser.py (modified — `TestGenericDecodeFallback` added during code review)
- VERSION (bumped 1.20.0 → 1.21.0)

### Code Review Fixes (2026-04-20)

- **H1** — AC #1 now satisfied: `detect_format()` logs `encoding_coherence` and `encoding_chaos` in addition to the bank-format confidence ([format_detector.py:207-218](backend/app/services/format_detector.py#L207-L218)).
- **H2** — Added decode-fallback regression tests for PrivatBank and Generic parsers (previously only Monobank was covered).
- **M1** — Moved `parser.mojibake_detected` observability event to fire immediately after `result_data` assignment, before `session.commit()` — so an alert still fires if the commit later fails.
- **M2** — Realigned encoding field in the observability event to `format_result.encoding` per Task 4.3 spec (was `upload.detected_encoding or format_result.encoding`).

### Change Log

| Date | Change | Notes |
|------|--------|-------|
| 2026-04-20 | Story 11.6 implemented | Mojibake detection end-to-end: `detect_mojibake()`, parser-service wiring, decode fallbacks, observability events |
| 2026-04-20 | Version bumped 1.20.0 → 1.21.0 | MINOR bump — adds user-facing `mojibakeDetected` payload signal |
| 2026-04-20 | Code review fixes applied | H1 (chaos log), H2 (privatbank/generic fallback tests), M1 (event order), M2 (encoding field source) |

## Code Review — Deferred Findings (2026-04-20)

Promoted to [docs/tech-debt.md](../../docs/tech-debt.md):

- **M3 → [TD-045](../../docs/tech-debt.md) — Pooled mojibake rate dilutes single-row corruption.** Pooled-rate math means single-row encoding damage can't trip the flag; track `rows_with_any_replacement_char` alongside.
- **M4 → [TD-046](../../docs/tech-debt.md) — `parser.decode_fallback` log lacks upload/user correlation.** Parser API has no upload context; thread via `contextvars` or surface `decode_fallback_used` on `ParseResult`.
- **L3 → [TD-047](../../docs/tech-debt.md) — `_decode_content()` helper lacks `errors="replace"` safety net.** Safe today (only caller wraps in try/except), but future callers silently inherit the unsafe version.

Kept story-local (cosmetic / by-design):

- **L1 — Redundant fallback branch when detected encoding is utf-8** [monobank.py:70-76](backend/app/agents/ingestion/parsers/monobank.py#L70-L76). `except` path re-decodes the same bytes under utf-8; only `errors="replace"` differs. Log message cosmetic.
- **L2 — Two observability events fire per mojibake upload** [parser_service.py:92-98](backend/app/services/parser_service.py#L92-L98) + [processing_tasks.py:427-435](backend/app/tasks/processing_tasks.py#L427-L435). Spec asked for both; dashboards must not double-count.
