# Story 2.4: Additional Bank Format Parser

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want the system to parse CSV files from other Ukrainian banks,
so that I'm not limited to only Monobank.

## Acceptance Criteria

1. **Given** a CSV file detected as non-Monobank
   **When** the parser analyzes the column structure
   **Then** it attempts to recognize common patterns (date, amount, description columns) and extract transactions

2. **Given** a CSV with a recognizable but different column layout (e.g., PrivatBank)
   **When** the parser processes it
   **Then** transactions are extracted and normalized to the same internal format as Monobank transactions

3. **Given** a CSV file with a completely unrecognizable format
   **When** parsing fails
   **Then** the user sees a friendly error suggesting the file format is not yet supported, with instructions on supported formats

## Tasks / Subtasks

- [x] Task 1: Implement PrivatBank CSV Parser (AC: #1, #2)
  - [x] 1.1: Create `backend/app/agents/ingestion/parsers/privatbank.py` — `PrivatBankParser(AbstractParser)` implementing `parse(file_bytes, encoding, delimiter) -> ParseResult`
  - [x] 1.2: Implement header mapping for PrivatBank columns: `Дата операції` (date), `Опис операції` (description), `Категорія` (category), `Сума` (amount), `Валюта` (currency)
  - [x] 1.3: Implement date parsing — parse `DD.MM.YYYY HH:MM:SS` format (same as Monobank) to naive datetime
  - [x] 1.4: Implement amount conversion — parse decimal amounts to integer kopiykas using `round(Decimal(value) * 100)` (NOT float arithmetic)
  - [x] 1.5: Implement currency handling — map currency column ("UAH") to ISO 4217 numeric code (980); handle non-UAH currencies gracefully
  - [x] 1.6: Implement row-level error handling — wrap each row in try/except, flag failed rows, continue processing remaining rows (partial success pattern from Story 2.3)
  - [x] 1.7: Implement raw data preservation — store original row as dict in `raw_data` field for audit
  - [x] 1.8: Map PrivatBank's `Категорія` column to a note field or ignore (categorization is handled by the categorization agent in Story 3.1, not the parser)

- [x] Task 2: Implement Generic CSV Parser for Unknown Formats (AC: #1, #3)
  - [x] 2.1: Create `backend/app/agents/ingestion/parsers/generic.py` — `GenericParser(AbstractParser)` that attempts to parse CSVs with unrecognized formats
  - [x] 2.2: Implement column heuristic detection — scan header row for date-like columns (containing "дата", "date"), amount-like columns (containing "сума", "amount", "sum"), description-like columns (containing "опис", "description", "призначення")
  - [x] 2.3: If minimum required columns found (date + amount) → attempt parsing with best-guess column mapping
  - [x] 2.4: If minimum columns NOT found → return empty ParseResult with a single FlaggedRow explaining the format is unsupported
  - [x] 2.5: Implement flexible date parsing — try multiple common Ukrainian date formats: `DD.MM.YYYY HH:MM:SS`, `DD.MM.YYYY`, `YYYY-MM-DD`, `DD/MM/YYYY`
  - [x] 2.6: Implement flexible amount parsing — handle both comma and period decimal separators

- [x] Task 3: Register Parsers in Parser Service (AC: #1, #2, #3)
  - [x] 3.1: Add `PrivatBankParser` to `_PARSERS` registry in `parser_service.py`: `"privatbank": PrivatBankParser`
  - [x] 3.2: Add `GenericParser` as fallback: when `format_result.bank_format == "unknown"` and confidence > 0, attempt GenericParser before raising `UnsupportedFormatError`
  - [x] 3.3: Update `UnsupportedFormatError` message to include user-friendly text: "This file format is not yet supported. Currently supported: Monobank CSV, PrivatBank CSV."

- [x] Task 4: Create Test Fixtures (AC: #1, #2, #3)
  - [x] 4.1: Create `backend/tests/fixtures/privatbank_standard.csv` — UTF-8, comma-delimited, 5 columns (`Дата операції`, `Опис операції`, `Категорія`, `Сума`, `Валюта`), 5+ transactions with typical PrivatBank data
  - [x] 4.2: Create `backend/tests/fixtures/privatbank_malformed.csv` — PrivatBank format with mix of valid and invalid rows (bad dates, non-numeric amounts)
  - [x] 4.3: Create `backend/tests/fixtures/generic_recognizable.csv` — Unknown bank format with recognizable date/amount/description columns using different column names
  - [x] 4.4: Create `backend/tests/fixtures/generic_unrecognizable.csv` — CSV with no recognizable financial columns (e.g., "Name,Email,Phone")

- [x] Task 5: Backend Tests (AC: #1, #2, #3)
  - [x] 5.1: Test PrivatBankParser — standard format: all fields parsed correctly, amounts in kopiykas, dates as naive datetime
  - [x] 5.2: Test PrivatBankParser — currency handling: UAH maps to 980, non-UAH currencies stored correctly
  - [x] 5.3: Test PrivatBankParser — malformed rows: valid rows parsed, invalid rows flagged with reasons, ParseResult reflects partial success
  - [x] 5.4: Test PrivatBankParser — amount conversion: "-150.50" -> -15050, "1000,50" -> 100050 (handle comma decimal)
  - [x] 5.5: Test PrivatBankParser — date parsing: "01.01.2024 12:00:00" -> datetime(2024, 1, 1, 12, 0, 0)
  - [x] 5.6: Test PrivatBankParser — raw_data preservation: original row dict stored in raw_data field
  - [x] 5.7: Test GenericParser — recognizable format: date + amount columns found, transactions parsed
  - [x] 5.8: Test GenericParser — unrecognizable format: empty ParseResult returned with FlaggedRow explaining unsupported format
  - [x] 5.9: Test GenericParser — flexible date formats: DD.MM.YYYY, YYYY-MM-DD, DD/MM/YYYY all parsed correctly
  - [x] 5.10: Test GenericParser — flexible amount parsing: comma and period decimals both handled
  - [x] 5.11: Test parser_service — PrivatBank format selects PrivatBankParser, transactions persisted to DB
  - [x] 5.12: Test parser_service — unknown format with recognizable columns uses GenericParser
  - [x] 5.13: Test parser_service — completely unknown format raises UnsupportedFormatError with user-friendly message
  - [x] 5.14: Test parser_service — all existing Monobank parser tests still pass (regression)

### Review Follow-ups (AI)
- [ ] [AI-Review][FUTURE] Expand CURRENCY_MAP in both PrivatBankParser and GenericParser to cover more currencies (CHF, JPY, CZK, TRY, etc.) — currently only 5 currencies mapped (UAH, USD, EUR, GBP, PLN); unknown currencies default to UAH with a warning log

## Dev Notes

### Architecture Compliance

**Tech Stack (MUST use — do NOT introduce alternatives):**
- **Backend**: Python 3.12, FastAPI, SQLModel, `csv` stdlib module, `decimal.Decimal`
- **Database**: PostgreSQL (RDS) — SQLite for tests with aiosqlite
- **Testing**: pytest + httpx (backend)
- **Existing dependencies only**: `charset-normalizer` (already installed), NO new pip packages

**Parser Architecture — From architecture.md and Story 2.3:**
```
backend/app/agents/ingestion/parsers/
├── __init__.py          # EXISTS
├── base.py              # EXISTS — AbstractParser, ParseResult, TransactionData, FlaggedRow
├── monobank.py          # EXISTS — MonobankParser (DO NOT MODIFY)
├── privatbank.py        # NEW — PrivatBankParser
└── generic.py           # NEW — GenericParser (fallback for unknown formats)
```

**AbstractParser Interface (MUST implement — from base.py):**
```python
class AbstractParser(ABC):
    @abstractmethod
    def parse(self, file_bytes: bytes, encoding: str, delimiter: str) -> ParseResult:
        """Parse file bytes into structured transaction data."""
```

**ParseResult dataclass (from base.py):**
```python
@dataclass
class ParseResult:
    transactions: list[TransactionData]  # Successfully parsed
    flagged_rows: list[FlaggedRow]       # Rows that failed to parse
    total_rows: int
    parsed_count: int
    flagged_count: int
```

**TransactionData dataclass (from base.py):**
```python
@dataclass
class TransactionData:
    date: datetime          # Naive datetime (NO timezone)
    description: str
    mcc: int | None         # MCC code — PrivatBank doesn't have MCC, set to None
    amount: int             # Integer kopiykas
    balance: int | None     # Balance — PrivatBank doesn't have balance, set to None
    currency_code: int      # ISO 4217 numeric (980 = UAH)
    raw_data: dict          # Original row data for audit
```

**Transaction Model (from models/transaction.py — DO NOT MODIFY):**
```python
class Transaction(SQLModel, table=True):
    __tablename__ = "transactions"
    id: uuid.UUID
    user_id: uuid.UUID         # FK → users.id
    upload_id: uuid.UUID       # FK → uploads.id
    date: datetime             # Naive datetime
    description: str
    mcc: int | None = None
    amount: int                # Integer kopiykas
    balance: int | None = None
    currency_code: int = 980   # UAH
    raw_data: dict | None = None  # JSON
    created_at: datetime
```

### Money Storage Convention (CRITICAL)

- All money values stored as **integer kopiykas** (1 UAH = 100 kopiykas)
- Example: -150.50 UAH -> `-15050` in DB
- Use `int(round(Decimal(value) * 100))` for conversion — NOT `int(float(value) * 100)` (floating point precision errors)
- Handle both period (`.`) and comma (`,`) decimal separators: normalize comma to period before Decimal conversion

### Date/Time Convention

- Parse to naive datetime (no timezone): `datetime.replace(tzinfo=None)` if needed
- Required for SQLite test compatibility
- PrivatBank format: `DD.MM.YYYY HH:MM:SS` (same as Monobank)
- GenericParser: try multiple formats in order

### PrivatBank CSV Format Specification

**Known from format_detector.py (Story 2.2):**
- Detection requires ALL 5 columns: `Дата операції`, `Опис операції`, `Категорія`, `Сума`, `Валюта`
- Confidence threshold: >= 0.8 (all 5 columns must match)
- Detection already implemented — parser just needs to handle the data

**Expected PrivatBank CSV structure:**
| Column | Ukrainian Name | Mapping |
|--------|---------------|---------|
| Date | `Дата операції` | -> `TransactionData.date` |
| Description | `Опис операції` | -> `TransactionData.description` |
| Category | `Категорія` | -> stored in `raw_data` only (categorization is Story 3.1's job) |
| Amount | `Сума` | -> `TransactionData.amount` (convert to kopiykas) |
| Currency | `Валюта` | -> `TransactionData.currency_code` (map "UAH" -> 980) |

**Key differences from Monobank:**
- No MCC code column -> set `TransactionData.mcc = None`
- No balance column -> set `TransactionData.balance = None`
- Has `Категорія` (category) column -> store in raw_data but do NOT use for categorization
- Has `Валюта` (currency) column -> map to ISO 4217 numeric code
- Encoding: likely UTF-8 (modern Privat24 exports), but accept any encoding from FormatDetectionResult
- Delimiter: likely comma, but accept any delimiter from FormatDetectionResult

**Currency mapping (ISO 4217):**
```python
CURRENCY_MAP = {
    "UAH": 980,
    "USD": 840,
    "EUR": 978,
    "GBP": 826,
    "PLN": 985,
}
```

### Integration with Existing Code

**Parser Service (`parser_service.py`) — current registry pattern:**
```python
_PARSERS: dict[str, type[AbstractParser]] = {
    "monobank": MonobankParser,
    # Add here:
    "privatbank": PrivatBankParser,
}
```

**Format detection flow (already implemented in Story 2.2):**
1. `format_detector.detect_format(file_bytes)` -> `FormatDetectionResult`
2. `FormatDetectionResult.bank_format` is `"monobank"`, `"privatbank"`, or `"unknown"`
3. Parser service selects parser based on `bank_format`
4. Parser receives `(file_bytes, encoding, delimiter)` from detection result
5. Parser does NOT re-detect encoding or delimiter

**For "unknown" format handling:**
- Currently `parser_service.py` raises `UnsupportedFormatError` for unknown formats
- Story 2.4 adds: try GenericParser first, only raise error if GenericParser also fails
- GenericParser should return empty ParseResult (not raise) when format is truly unrecognizable

### Critical Previous Story Learnings (DO NOT REPEAT THESE BUGS)

1. **DateTime handling**: Use `datetime.now(UTC).replace(tzinfo=None)` for SQLite compatibility — timezone-aware datetimes cause deserialization issues with SQLite
2. **Money as kopiykas**: Use `Decimal` for conversion, never `float` — `int(round(Decimal(value) * 100))`
3. **UTF-8 BOM handling**: Strip BOM character (`\ufeff`) before parsing to prevent header matching failures
4. **Parser does NOT commit session**: `parser_service` adds to session but does NOT call `session.commit()` — caller controls transaction boundary
5. **Flagged rows in separate table**: Use `FlaggedImportRow` model (not mixed into `transactions` table)
6. **Bulk insert pattern**: Use `session.add_all()` for efficient bulk insert of transactions and flagged rows
7. **Pydantic camelCase**: API JSON uses `camelCase` via `alias_generator=to_camel` — DB/Python uses `snake_case`
8. **ProcessingJob status flow**: "pending" -> "validating" -> "validated" / "validation_failed" -> "parsing" -> "parsed" / "parse_failed"
9. **Locale codes**: ISO 639-1 (`"uk"`, `"en"`) — NOT `"ua"`
10. **Monobank format detection**: Uses fingerprint matching, not exact column matching — PrivatBank uses exact column matching (threshold 0.8)

### Git Intelligence (Recent Commits)

```
d5a064e Story 2.3: Monobank CSV Parser
557de19 Story 2.2: File Validation & Format Detection
0a58b72 Story 2.1: File Upload UI & S3 Storage
```

**Patterns established in Story 2.3:**
- Parser files are ~136 lines (focused, single-responsibility)
- Test file is comprehensive (~682 lines) covering all edge cases
- Test fixtures are real CSV files in `tests/fixtures/` (not inline strings)
- Parser service uses registry pattern with dict mapping
- MonobankParser uses helper functions: `_resolve_column_index()`, `_parse_date()`, `_parse_amount_kopiykas()`, `_parse_mcc()`
- Follow the same helper function pattern for PrivatBankParser

### Project Structure Notes

**New files to create:**
```
backend/app/agents/ingestion/parsers/privatbank.py   # NEW — PrivatBankParser
backend/app/agents/ingestion/parsers/generic.py      # NEW — GenericParser
backend/tests/test_privatbank_parser.py              # NEW — PrivatBank parser tests
backend/tests/test_generic_parser.py                 # NEW — Generic parser tests
backend/tests/fixtures/privatbank_standard.csv       # NEW — Test fixture
backend/tests/fixtures/privatbank_malformed.csv      # NEW — Test fixture
backend/tests/fixtures/generic_recognizable.csv      # NEW — Test fixture
backend/tests/fixtures/generic_unrecognizable.csv    # NEW — Test fixture
```

**Files to modify:**
```
backend/app/services/parser_service.py               # Add PrivatBankParser + GenericParser to registry
backend/app/agents/ingestion/parsers/__init__.py     # Export new parsers
```

**Do NOT modify:**
```
backend/app/agents/ingestion/parsers/base.py         # AbstractParser interface is stable
backend/app/agents/ingestion/parsers/monobank.py     # Story 2.3 — parser is complete
backend/app/services/format_detector.py              # Story 2.2 — detection already handles PrivatBank
backend/app/models/transaction.py                    # Transaction model is stable
backend/app/models/flagged_import_row.py             # FlaggedImportRow model is stable
backend/app/services/upload_service.py               # Upload flow unchanged
backend/app/api/v1/uploads.py                        # Upload endpoint unchanged
```

### Testing Requirements

**Backend Tests (pytest) — minimum 14 new test cases across 2 test files:**

**test_privatbank_parser.py:**
- PrivatBankParser: standard format parsed (all 5 columns), amounts in kopiykas, dates as naive datetime
- PrivatBankParser: currency mapping (UAH -> 980, USD -> 840)
- PrivatBankParser: malformed rows flagged, partial results returned
- PrivatBankParser: amount conversion with comma and period decimals
- PrivatBankParser: date parsing DD.MM.YYYY HH:MM:SS
- PrivatBankParser: raw_data preservation
- Parser service integration: PrivatBank format -> PrivatBankParser -> DB persistence

**test_generic_parser.py:**
- GenericParser: recognizable columns found and parsed
- GenericParser: unrecognizable format returns empty ParseResult + FlaggedRow
- GenericParser: flexible date format handling
- GenericParser: flexible amount parsing (comma/period)
- Parser service: unknown format -> GenericParser attempted -> success
- Parser service: unknown format -> GenericParser fails -> UnsupportedFormatError with friendly message

**Test fixture approach:** Create real CSV files in `tests/fixtures/` (pattern from Story 2.2 and 2.3).

**SQLite compatibility:** All tests use SQLite — ensure:
- No timezone-aware datetimes
- Use `sa.JSON` type (works with both PostgreSQL and SQLite)

**Regression**: All 123 existing backend tests must continue to pass.

### Library & Framework Requirements

**Use stdlib CSV module (CRITICAL):**
- `csv.reader()` or `csv.DictReader()` for parsing
- Do NOT use `pandas` (too heavy, not needed)

**Use `decimal.Decimal` for money conversion:**
- `int(round(Decimal(amount_str) * 100))` — NOT `int(float(amount_str) * 100)`

**Do NOT introduce:**
- `pandas` (overkill for CSV parsing)
- `openpyxl` (not needed — CSV only, XLS conversion is user's responsibility)
- Any new pip packages — this story uses only stdlib + existing dependencies

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 2, Story 2.4]
- [Source: _bmad-output/planning-artifacts/architecture.md — Data Architecture, agents/ingestion/parsers/ structure, AbstractParser interface]
- [Source: _bmad-output/planning-artifacts/prd.md — FR2 (auto-detect format), FR4 (additional bank formats), FR5 (validation), FR6 (partial parse)]
- [Source: _bmad-output/implementation-artifacts/2-3-monobank-csv-parser.md — Previous story learnings, parser patterns, test patterns]
- [Source: backend/app/agents/ingestion/parsers/base.py — AbstractParser, ParseResult, TransactionData, FlaggedRow]
- [Source: backend/app/agents/ingestion/parsers/monobank.py — MonobankParser implementation pattern]
- [Source: backend/app/services/parser_service.py — Parser registry, parse_and_store_transactions(), UnsupportedFormatError]
- [Source: backend/app/services/format_detector.py — FormatDetectionResult, PRIVATBANK_REQUIRED_COLUMNS, _check_privatbank()]
- [Source: backend/app/models/transaction.py — Transaction model]
- [Source: backend/app/models/flagged_import_row.py — FlaggedImportRow model]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- One existing test `test_privatbank_format_raises_error` in `test_monobank_parser.py` expected PrivatBank to be unsupported (Story 2.3 placeholder). Updated to verify PrivatBank is now registered in `_PARSERS`.

### Completion Notes List

- Implemented `PrivatBankParser` following MonobankParser patterns: header column resolution, date parsing (DD.MM.YYYY HH:MM:SS), Decimal-based kopiykas conversion, currency mapping (ISO 4217), row-level error handling, raw data preservation
- Implemented `GenericParser` with heuristic column detection (Ukrainian + English keywords), flexible date format support (4 formats), comma/period decimal handling, and graceful fallback when columns not detected
- Registered both parsers in `parser_service.py`: PrivatBank in `_PARSERS` registry, Generic as fallback for unknown formats before raising `UnsupportedFormatError`
- Updated `UnsupportedFormatError` message to user-friendly text listing supported formats
- Created 4 test fixture CSV files covering standard, malformed, recognizable generic, and unrecognizable formats
- Wrote 26 new tests across 2 test files, all passing. Full suite: 149 tests, 0 failures, 0 regressions

### Change Log

- 2026-03-28: Implemented Story 2.4 — PrivatBank CSV Parser, Generic CSV Parser, parser service integration, 26 tests, 4 fixtures
- 2026-03-28: Code review fixes — refactored parser_service control flow, updated __init__.py exports, added currency heuristic detection to GenericParser, added unknown currency warnings to both parsers, strengthened monobank regression test

### File List

**New files:**
- backend/app/agents/ingestion/parsers/privatbank.py
- backend/app/agents/ingestion/parsers/generic.py
- backend/tests/test_privatbank_parser.py
- backend/tests/test_generic_parser.py
- backend/tests/fixtures/privatbank_standard.csv
- backend/tests/fixtures/privatbank_malformed.csv
- backend/tests/fixtures/generic_recognizable.csv
- backend/tests/fixtures/generic_unrecognizable.csv

**Modified files:**
- backend/app/services/parser_service.py
- backend/app/agents/ingestion/parsers/__init__.py
- backend/tests/test_monobank_parser.py
