# Story 2.3: Monobank CSV Parser

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want the system to correctly parse my Monobank CSV bank statements,
so that all my transactions are accurately extracted.

## Acceptance Criteria

1. **Given** a Monobank CSV file with Windows-1251 encoding
   **When** the parser processes it
   **Then** the encoding is correctly detected and handled, producing valid UTF-8 transaction data

2. **Given** a Monobank CSV with semicolon delimiters and embedded newlines in description fields
   **When** the parser processes it
   **Then** all fields are correctly split respecting quoted fields with embedded newlines

3. **Given** a Monobank CSV with 200-500 transactions
   **When** the parser extracts transaction data
   **Then** each transaction has: date, description, MCC code, amount (stored as integer kopiykas), and balance — stored in a `transactions` table created via Alembic migration

4. **Given** a CSV where some rows have unexpected or missing fields
   **When** the parser encounters them
   **Then** it processes all recognizable rows and flags unrecognizable ones, providing partial results rather than failing entirely

## Tasks / Subtasks

- [x] Task 1: Create Transaction Model & Alembic Migration (AC: #3)
  - [x] 1.1: Create `backend/app/models/transaction.py` — `Transaction` SQLModel with fields: `id` (UUID PK), `user_id` (FK→users), `upload_id` (FK→uploads), `date` (datetime), `description` (str), `mcc` (int, nullable), `amount` (int, kopiykas), `balance` (int, kopiykas, nullable), `currency_code` (int, default 980 for UAH), `raw_data` (JSON, nullable — original row for audit), `is_flagged` (bool, default False — for unrecognizable rows), `flag_reason` (str, nullable), `created_at` (datetime)
  - [x] 1.2: Add indexes: `idx_transactions_user_id`, `idx_transactions_upload_id`, `idx_transactions_date`
  - [x] 1.3: Create Alembic migration `create_transactions_table.py` — create `transactions` table with all columns, FKs, and indexes
  - [x] 1.4: Register `Transaction` model in `backend/app/models/__init__.py`

- [x] Task 2: Create Abstract Parser Interface (AC: #3, #4)
  - [x] 2.1: Create `backend/app/agents/ingestion/parsers/base.py` — `AbstractParser` with method `parse(file_bytes: bytes, encoding: str, delimiter: str) -> ParseResult`
  - [x] 2.2: Define `ParseResult` dataclass: `transactions: list[TransactionData]`, `flagged_rows: list[FlaggedRow]`, `total_rows: int`, `parsed_count: int`, `flagged_count: int`
  - [x] 2.3: Define `TransactionData` dataclass: `date: datetime`, `description: str`, `mcc: int | None`, `amount: int` (kopiykas), `balance: int | None` (kopiykas), `currency_code: int`, `raw_data: dict`
  - [x] 2.4: Define `FlaggedRow` dataclass: `row_number: int`, `raw_data: dict | str`, `reason: str`

- [x] Task 3: Implement Monobank CSV Parser (AC: #1, #2, #3, #4)
  - [x] 3.1: Create `backend/app/agents/ingestion/parsers/monobank.py` — `MonobankParser(AbstractParser)`
  - [x] 3.2: Implement encoding handling — accept encoding from `FormatDetectionResult` (already detected in Story 2.2), decode bytes to text using provided encoding
  - [x] 3.3: Implement CSV reading with `csv.reader()` — use provided delimiter, handle quoted fields with embedded newlines natively via Python's csv module
  - [x] 3.4: Implement header mapping — map detected header columns to internal fields using flexible matching (support both legacy "Дата і час операції" and modern "Дата i час операції" with Latin `i`)
  - [x] 3.5: Implement date parsing — parse "DD.MM.YYYY HH:MM:SS" format to datetime, store as naive UTC (`datetime.replace(tzinfo=None)` for SQLite test compatibility)
  - [x] 3.6: Implement amount conversion — parse decimal string (e.g., "-150.50") to integer kopiykas (e.g., -15050) using `round(Decimal(value) * 100)`
  - [x] 3.7: Implement MCC extraction — parse integer MCC code from string, handle empty/missing MCC gracefully (set to `None`)
  - [x] 3.8: Implement row-level error handling — wrap each row parse in try/except, add failed rows to `flagged_rows` with reason, continue processing remaining rows
  - [x] 3.9: Implement raw data preservation — store original row as dict in `raw_data` field for audit/compliance

- [x] Task 4: Create Parser Service for Orchestration (AC: #3, #4)
  - [x] 4.1: Create `backend/app/services/parser_service.py` — orchestrates parsing + persistence
  - [x] 4.2: Implement `parse_and_store_transactions(session, user_id, upload_id, file_bytes, format_result)` — selects parser based on `format_result.bank_format`, runs parser, persists transactions
  - [x] 4.3: Implement transaction persistence — bulk insert `Transaction` records from `ParseResult.transactions`, set `is_flagged=True` + `flag_reason` for flagged rows
  - [x] 4.4: Implement partial result handling — if some rows fail, still persist all successfully parsed transactions and return summary with flagged count

- [x] Task 5: Backend Tests (AC: #1, #2, #3, #4)
  - [x] 5.1: Create `backend/tests/fixtures/monobank_legacy.csv` — legacy format (Windows-1251, semicolons, 5 columns: Дата і час операції;Опис операції;MCC;Сума в валюті картки (UAH);Залишок на рахунку (UAH))
  - [x] 5.2: Create `backend/tests/fixtures/monobank_modern_multi.csv` — modern format (UTF-8, commas, 10 columns, 10+ transactions including edge cases)
  - [x] 5.3: Create `backend/tests/fixtures/monobank_embedded_newlines.csv` — CSV with quoted fields containing newlines in description
  - [x] 5.4: Create `backend/tests/fixtures/monobank_malformed_rows.csv` — CSV with mix of valid and invalid rows (missing fields, bad dates, non-numeric amounts)
  - [x] 5.5: Test MonobankParser — legacy format: all fields parsed correctly, amounts in kopiykas, dates as datetime
  - [x] 5.6: Test MonobankParser — modern format: all 10 columns mapped, encoding handled, MCC parsed
  - [x] 5.7: Test MonobankParser — embedded newlines: rows correctly split despite newlines in quoted fields
  - [x] 5.8: Test MonobankParser — malformed rows: valid rows parsed, invalid rows flagged with reasons, ParseResult reflects partial success
  - [x] 5.9: Test MonobankParser — amount conversion: "-150.50" → -15050, "1000.00" → 100000, "0.01" → 1
  - [x] 5.10: Test MonobankParser — date parsing: "01.01.2024 12:00:00" → datetime(2024, 1, 1, 12, 0, 0)
  - [x] 5.11: Test parser_service — parse_and_store_transactions: transactions persisted to DB, flagged rows have is_flagged=True
  - [x] 5.12: Test parser_service — partial results: some rows fail, valid rows still persisted, summary accurate
  - [x] 5.13: Test Transaction model — Alembic migration creates table with correct columns, indexes, and FKs
  - [x] 5.14: Test parser selection — monobank format selects MonobankParser, unknown format raises appropriate error

## Dev Notes

### Architecture Compliance

**Tech Stack (MUST use — do NOT introduce alternatives):**
- **Backend**: Python 3.12, FastAPI, SQLModel, Alembic, `csv` stdlib module
- **Database**: PostgreSQL (RDS) — SQLite for tests with aiosqlite
- **Testing**: pytest + httpx (backend)
- **Existing dependency**: `charset-normalizer` (already installed in Story 2.2 — do NOT re-add)

**Parser Architecture — From architecture.md:**
```
backend/app/agents/ingestion/parsers/
├── __init__.py
├── base.py         # AbstractParser interface
└── monobank.py     # Monobank CSV parser
```

This is the architecture-defined location for parsers. The `agents/ingestion/` directory does NOT exist yet — it must be created with proper `__init__.py` files at each level (`agents/`, `agents/ingestion/`, `agents/ingestion/parsers/`).

**Transaction Model — From architecture.md:**
```python
# backend/app/models/transaction.py
class Transaction(SQLModel, table=True):
    __tablename__ = "transactions"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    upload_id: uuid.UUID = Field(foreign_key="uploads.id", index=True)
    date: datetime
    description: str
    mcc: int | None = None
    amount: int          # Integer kopiykas (e.g., -15050 = -150.50 UAH)
    balance: int | None = None  # Integer kopiykas
    currency_code: int = 980    # ISO 4217 numeric (980 = UAH)
    raw_data: dict | None = None  # JSONB — original row for audit
    is_flagged: bool = False
    flag_reason: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)
```

**Money Storage Convention (CRITICAL):**
- All money values stored as **integer kopiykas** (1 UAH = 100 kopiykas)
- Example: -150.50 UAH → `-15050` in DB
- Use `round(Decimal(value) * 100)` for conversion — NOT float arithmetic (floating point precision errors)
- This is mandated by architecture: "Money in API: Integer (kopiykas)"

**Date/Time Convention:**
- Parse Monobank's `DD.MM.YYYY HH:MM:SS` format
- Store as naive datetime (no timezone): `datetime.replace(tzinfo=None)`
- This is required for SQLite test compatibility (learned from Story 2.2 Debug Log)

**Monobank CSV Format Variants (learned from Story 2.2):**

*Legacy format (older exports):*
- Encoding: Windows-1251
- Delimiter: semicolon (`;`)
- Columns: `Дата і час операції;Опис операції;MCC;Сума в валюті картки (UAH);Залишок на рахунку (UAH)`

*Modern format (current exports):*
- Encoding: UTF-8
- Delimiter: comma (`,`)
- Quoted fields
- Columns: `"Дата i час операції","Деталі операції",MCC,"Сума в валюті картки (UAH)","Сума в валюті операції",Валюта,Курс,"Сума комісій (UAH)","Сума кешбеку (UAH)","Залишок після операції"`
- Note: Uses Latin `i` in "Дата i час" (not Cyrillic `і`)
- Note: "Деталі операції" instead of "Опис операції"

**Column Mapping Strategy:**
The parser must handle both formats. Use flexible header matching:
```python
HEADER_MAPPINGS = {
    "date": ["Дата і час операції", "Дата i час операції"],      # Cyrillic і / Latin i
    "description": ["Опис операції", "Деталі операції"],
    "mcc": ["MCC"],
    "amount": ["Сума в валюті картки (UAH)"],
    "balance": ["Залишок на рахунку (UAH)", "Залишок після операції"],
    "commission": ["Сума комісій (UAH)"],     # Modern only
    "cashback": ["Сума кешбеку (UAH)"],       # Modern only
    "operation_amount": ["Сума в валюті операції"],  # Modern only
    "currency": ["Валюта"],                    # Modern only
    "exchange_rate": ["Курс"],                 # Modern only
}
```

### Critical Previous Story Learnings (DO NOT REPEAT THESE BUGS)

1. **DateTime handling**: Use `datetime.now(UTC).replace(tzinfo=None)` for SQLite compatibility — timezone-aware datetimes cause deserialization issues with SQLite
2. **Locale codes**: ISO 639-1 (`"uk"`, `"en"`) — NOT `"ua"`
3. **Data fetching pattern**: Use native `fetch()` with Bearer token from `useSession().accessToken` — do NOT introduce TanStack Query mid-epic (consistency with Stories 1.1-1.7)
4. **Dark mode default**: All new UI components must work with dark theme
5. **Font**: DM Sans with `latin + latin-ext` subsets (NOT cyrillic subset)
6. **shadcn/ui**: Components are owned source code in `components/ui/`
7. **Feature folder pattern**: `features/upload/{components,hooks,__tests__}/`
8. **i18n pattern**: Namespace-based `useTranslations('upload')`, identical key structure in both `en.json` and `uk.json`
9. **Test mocking**: Use `test-utils/intl-mock.ts` for i18n, mock `useSession()` with `{ accessToken: 'test-token', status: 'authenticated' }`
10. **Accessibility**: WCAG 2.1 AA — semantic HTML, `aria-label`, keyboard nav, 44px min touch targets, 4.5:1 contrast
11. **Environment variables**: Use `|| ""` fallback, NOT `!` assertion
12. **python-multipart**: Already installed for FastAPI UploadFile support
13. **intl-mock**: Doesn't support nested dot-notation keys — use flat key names
14. **Pydantic camelCase**: API JSON uses `camelCase` via `alias_generator=to_camel` — DB/Python uses `snake_case`
15. **Monobank format detection**: Real exports use fingerprint matching, not exact column matching (Story 2.2 Debug Log) — the parser should be similarly flexible
16. **Locale switch**: Always use `window.location.href` for locale switching, never `router.replace` with locale option
17. **ProcessingJob status flow**: "pending" → "validating" → "validated" / "validation_failed" (set in Story 2.2) → next step will be "parsing" → "parsed" / "parse_failed"

### Integration with Story 2.2

The format detection from Story 2.2 provides a `FormatDetectionResult` with:
- `bank_format`: "monobank" | "privatbank" | "unknown"
- `encoding`: detected encoding (e.g., "utf-8", "windows-1251")
- `delimiter`: detected delimiter (e.g., ",", ";")
- `column_count`: number of columns
- `confidence_score`: 0.0-1.0
- `header_row`: list of column names

**The parser MUST use these pre-detected values** — do NOT re-detect encoding or delimiter. The `FormatDetectionResult` is available from the `Upload` record (`detected_format`, `detected_encoding`) and can be reconstructed or passed through the pipeline.

**Current upload flow (from upload endpoint in `uploads.py`):**
1. File uploaded → validated → format detected → stored in S3 → Upload + ProcessingJob records created
2. ProcessingJob status set to "validated"
3. **Story 2.3 adds**: After validation, the parser reads the file (from S3 or from the bytes already in memory), parses transactions, and stores them in the `transactions` table

**Note on parser invocation:** Story 2.5 (Celery async pipeline) is not yet implemented. For now, the parser can be invoked synchronously within the upload endpoint OR exposed as a service that Story 2.5 will later call from a Celery task. Prefer the service approach — create `parser_service.py` as a standalone service that can be called from either the upload endpoint (sync, for testing) or a Celery task (async, Story 2.5).

### File Structure Requirements

**New files to create:**
```
backend/app/
├── agents/
│   ├── __init__.py                         # NEW (empty)
│   └── ingestion/
│       ├── __init__.py                     # NEW (empty)
│       └── parsers/
│           ├── __init__.py                 # NEW (empty)
│           ├── base.py                     # NEW — AbstractParser interface
│           └── monobank.py                 # NEW — Monobank CSV parser
├── models/
│   └── transaction.py                      # NEW — Transaction SQLModel
├── services/
│   └── parser_service.py                   # NEW — Parser orchestration service

backend/alembic/versions/
└── xxx_create_transactions_table.py        # NEW — Migration

backend/tests/
├── fixtures/
│   ├── monobank_legacy.csv                 # NEW — Legacy format test fixture
│   ├── monobank_modern_multi.csv           # NEW — Modern format, multiple rows
│   ├── monobank_embedded_newlines.csv      # NEW — Embedded newlines test
│   └── monobank_malformed_rows.csv         # NEW — Malformed rows test
└── test_monobank_parser.py                 # NEW — Parser tests
```

**Files to modify:**
```
backend/app/models/__init__.py              # Register Transaction model
```

**Do NOT modify:**
```
backend/app/services/format_detector.py     # Story 2.2 — detection is complete
backend/app/services/upload_service.py      # Upload flow unchanged — parser invoked separately
backend/app/api/v1/uploads.py               # Upload endpoint unchanged for now
```

### Testing Requirements

**Backend Tests (pytest + httpx) — minimum 14 new test cases:**
- Transaction model: migration creates table, CRUD operations work
- MonobankParser: legacy format parsed, modern format parsed, embedded newlines handled
- MonobankParser: amount conversion (decimal → kopiykas), date parsing (DD.MM.YYYY → datetime)
- MonobankParser: malformed rows flagged, partial results returned
- Parser service: end-to-end parse + persist, partial results persisted
- Parser selection: correct parser selected by bank_format

**Test fixture approach:** Create real CSV files (not inline strings) in `tests/fixtures/` — this was the pattern established in Story 2.2.

**SQLite compatibility:** All tests use SQLite (via aiosqlite) — ensure:
- No timezone-aware datetimes (use `replace(tzinfo=None)`)
- No PostgreSQL-specific SQL (e.g., no `JSONB` — use `JSON` type that works with both)
- Use `sa.JSON` for raw_data column in migration (SQLAlchemy `JSON` type works with both PostgreSQL and SQLite)

**Regression**: All 83 existing backend tests and 86 existing frontend tests must continue to pass.

### Library & Framework Requirements

**Use stdlib CSV module (CRITICAL):**
- `csv.reader()` for parsing — handles quoted fields and embedded newlines natively
- `csv.DictReader()` is also acceptable for header-based access
- Do NOT use `pandas` for CSV parsing (too heavy, not needed for this use case)

**Use `decimal.Decimal` for money conversion:**
- `from decimal import Decimal`
- `int(round(Decimal(amount_str) * 100))` — NOT `int(float(amount_str) * 100)` (floating point errors)

**Do NOT introduce:**
- `pandas` (overkill for CSV parsing)
- `openpyxl` (not needed — CSV only)
- Any new pip packages — this story uses only stdlib + existing dependencies

### Project Structure Notes

- `backend/app/agents/` directory exists but only contains `__init__.py` — the `ingestion/parsers/` subdirectories must be created
- `backend/tests/fixtures/` directory already exists (created in Story 2.2) — add new fixture files there
- Existing fixture files: `monobank_sample.csv`, `monobank_modern.csv`, `unknown_bank.csv`, `empty.csv`, `binary_disguised.csv` — these are for format detection tests, do NOT modify them
- The `format_detector.py` service already handles Monobank detection — the parser builds on top of detection results

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 2, Story 2.3]
- [Source: _bmad-output/planning-artifacts/architecture.md — Data Architecture, API Patterns, Structure Patterns (agents/ingestion/parsers/), Naming Patterns, Format Patterns (Money as kopiykas)]
- [Source: _bmad-output/planning-artifacts/prd.md — FR2, FR5, FR6 (partial parse), FR8 (extract/structure transactions), FR37 (format detection), FR40 (user-friendly errors)]
- [Source: _bmad-output/implementation-artifacts/2-2-file-validation-format-detection.md — Previous Story Learnings, Format Detector Code, Monobank Header Patterns, Debug Log (format detection fixes)]
- [Source: backend/app/services/format_detector.py — FormatDetectionResult dataclass, detect_format(), Monobank fingerprints]
- [Source: backend/app/models/upload.py — Upload model with detected_format/detected_encoding fields]
- [Source: backend/app/models/processing_job.py — ProcessingJob model with status field]
- [Source: backend/tests/fixtures/monobank_modern.csv — Real Monobank modern format example]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

No blocking issues encountered during implementation.

### Completion Notes List

- Transaction model created with all specified fields, using `sa.JSON` for raw_data (SQLite-compatible)
- AbstractParser interface with ParseResult, TransactionData, FlaggedRow dataclasses
- MonobankParser handles both legacy (Windows-1251, semicolons, 5 cols) and modern (UTF-8, commas, 10 cols) formats
- Flexible header mapping supports Cyrillic `і` and Latin `i` variants
- Amount conversion uses `Decimal` for precision (no float arithmetic)
- Dates stored as naive datetime for SQLite test compatibility
- Row-level error handling: malformed rows flagged, valid rows still parsed
- Parser service orchestrates parser selection, parsing, and DB persistence
- Flagged rows stored in separate `flagged_import_rows` table (not mixed into transactions)
- Parser service does NOT commit session — caller controls transaction boundary
- Uses `session.add_all()` for bulk insert of transactions and flagged rows
- UTF-8 BOM handling: BOM character stripped before parsing to prevent header matching failures
- 38 new tests covering all acceptance criteria + edge cases; 123 total backend tests pass (0 regressions)

### Change Log

- 2026-03-28: Story 2.3 implementation — Monobank CSV parser with Transaction model, parser interface, parser service, and 33 tests
- 2026-03-28: Code review fixes — Separated flagged rows to own table, removed session.commit from service, added BOM handling, bulk insert, 5 new edge case tests

### File List

**New files:**
- backend/app/models/transaction.py
- backend/app/models/flagged_import_row.py
- backend/app/agents/ingestion/__init__.py
- backend/app/agents/ingestion/parsers/__init__.py
- backend/app/agents/ingestion/parsers/base.py
- backend/app/agents/ingestion/parsers/monobank.py
- backend/app/services/parser_service.py
- backend/alembic/versions/b7d9e1f3a2c4_create_transactions_table.py
- backend/tests/test_monobank_parser.py
- backend/tests/fixtures/monobank_legacy.csv
- backend/tests/fixtures/monobank_modern_multi.csv
- backend/tests/fixtures/monobank_embedded_newlines.csv
- backend/tests/fixtures/monobank_malformed_rows.csv

**Modified files:**
- backend/app/models/__init__.py (added Transaction and FlaggedImportRow imports)
