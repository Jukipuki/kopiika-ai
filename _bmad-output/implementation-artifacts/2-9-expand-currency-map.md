# Story 2.9: Expand CURRENCY_MAP

Status: done
Created: 2026-04-16
Epic: 2 — Statement Upload & Data Ingestion

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want all bank statement parsers to support a wider range of currencies,
so that users with multi-currency accounts don't silently lose or miscategorize transaction data.

## Acceptance Criteria

1. **Given** a Monobank CSV containing transactions in CHF, JPY, CZK, or TRY, **When** the Monobank parser processes it, **Then** the currency is correctly identified, stored with the transaction record using the ISO 4217 currency code, and displayed with the correct symbol.

2. **Given** a PrivatBank or generic bank CSV with CHF, JPY, CZK, or TRY transactions, **When** the respective parser processes it, **Then** the currency is correctly identified and stored (not defaulted to UAH).

3. **Given** a transaction in a currency not present in the updated CURRENCY_MAP, **When** the parser encounters it, **Then** the transaction is stored with the raw currency code preserved, flagged with a `currency_unknown` warning log, and included in the uncategorized transaction report (FR38) — it is never silently converted to UAH.

4. **Given** the updated CURRENCY_MAP, **When** it is reviewed, **Then** it includes at minimum: UAH, USD, EUR, GBP, PLN, CHF, JPY, CZK, TRY — each mapped to its ISO 4217 numeric code AND its display symbol.

5. **Given** existing stored transactions that previously used the "default to UAH" fallback, **When** this change is deployed, **Then** no existing transaction records are modified — the new behaviour applies only to future uploads.

## Tasks / Subtasks

- [x] **Task 1: Backend — centralize the CURRENCY_MAP into a single source-of-truth module** (AC: #1, #2, #4)
  - [x] 1.1 Create [backend/app/services/currency.py](backend/app/services/currency.py) with a frozen `CurrencyInfo` dataclass and a single `CURRENCY_MAP: dict[str, CurrencyInfo]` keyed by uppercase ISO alpha-3 code:
    ```python
    from dataclasses import dataclass

    @dataclass(frozen=True)
    class CurrencyInfo:
        numeric_code: int   # ISO 4217 numeric (e.g., 980)
        alpha_code: str     # ISO 4217 alpha-3 (e.g., "UAH")
        symbol: str         # Display symbol (e.g., "₴", "CHF" for currencies without a unique glyph)

    CURRENCY_MAP: dict[str, CurrencyInfo] = {
        "UAH": CurrencyInfo(980, "UAH", "₴"),
        "USD": CurrencyInfo(840, "USD", "$"),
        "EUR": CurrencyInfo(978, "EUR", "€"),
        "GBP": CurrencyInfo(826, "GBP", "£"),
        "PLN": CurrencyInfo(985, "PLN", "zł"),
        "CHF": CurrencyInfo(756, "CHF", "CHF"),  # No widely-recognized glyph; use ISO code
        "JPY": CurrencyInfo(392, "JPY", "¥"),
        "CZK": CurrencyInfo(203, "CZK", "Kč"),
        "TRY": CurrencyInfo(949, "TRY", "₺"),
    }

    DEFAULT_CURRENCY_CODE: int = 980  # UAH numeric — used only by parsers with NO currency column (legacy Monobank 5-col format)
    UNKNOWN_CURRENCY_CODE: int = 0    # Sentinel for unrecognized alpha codes; never collides with any ISO 4217 numeric

    def resolve_currency(raw: str | None) -> CurrencyInfo | None:
        """Return CurrencyInfo for a recognized alpha code (case-insensitive, whitespace-trimmed); None otherwise."""
        if raw is None:
            return None
        return CURRENCY_MAP.get(raw.strip().upper())
    ```
  - [x] 1.2 Delete the duplicate `CURRENCY_MAP` constants from [backend/app/agents/ingestion/parsers/privatbank.py:26-32](backend/app/agents/ingestion/parsers/privatbank.py#L26-L32) and [backend/app/agents/ingestion/parsers/generic.py:23-29](backend/app/agents/ingestion/parsers/generic.py#L23-L29). Both files should import from `app.services.currency` instead.
  - [x] 1.3 Keep the parser-local `DEFAULT_CURRENCY_CODE = 980` constants if they document parser-specific fallback semantics, but re-export from `app.services.currency` to keep one definition.

- [x] **Task 2: Backend — extend `TransactionData` to carry the parser's currency-resolution outcome** (AC: #1, #2, #3)
  - [x] 2.1 In [backend/app/agents/ingestion/parsers/base.py](backend/app/agents/ingestion/parsers/base.py), extend `TransactionData` with two optional fields:
    ```python
    @dataclass
    class TransactionData:
        date: datetime
        description: str
        mcc: int | None
        amount: int
        balance: int | None
        currency_code: int                          # numeric ISO 4217; UNKNOWN_CURRENCY_CODE (0) when unrecognized
        raw_data: dict
        currency_alpha: str | None = None           # NEW — alpha ISO code from CURRENCY_MAP when recognized (e.g. "CHF"); None for legacy/no-column rows
        currency_unknown_raw: str | None = None     # NEW — the raw alpha string from the CSV when it was NOT in CURRENCY_MAP (e.g. "XYZ"); triggers flagging in parser_service
    ```
  - [x] 2.2 The two new fields are mutually exclusive: a row either resolves to a known `CurrencyInfo` (sets `currency_alpha`, `currency_code` = numeric) OR has an unknown raw code (sets `currency_unknown_raw`, `currency_code` = `UNKNOWN_CURRENCY_CODE`). Rows with no currency column at all (legacy Monobank) leave both `None` and use `DEFAULT_CURRENCY_CODE`.
  - [x] 2.3 Do **not** add the alpha or raw fields to the persisted `Transaction` SQLModel — they are parser → service handoff only. The persisted columns are `currency_code: int` (existing) plus `is_flagged_for_review` / `uncategorized_reason` (existing, set by parser_service per Task 6).

- [x] **Task 3: Backend — Monobank parser reads the `Валюта` column on modern statements** (AC: #1, #3)
  - [x] 3.1 In [backend/app/agents/ingestion/parsers/monobank.py](backend/app/agents/ingestion/parsers/monobank.py), add a `currency` entry to `HEADER_MAPPINGS` with both Ukrainian and English variants (the modern fixture uses `"Валюта"`; English fixture uses `"Currency"`):
    ```python
    HEADER_MAPPINGS: dict[str, list[str]] = {
        ...,
        "currency": ["Валюта", "Currency"],
    }
    ```
  - [x] 3.2 Resolve `currency_idx = _resolve_column_index(header, "currency")` alongside the existing date/desc/mcc/amount/balance lookups.
  - [x] 3.3 In the per-row loop, when `currency_idx is None` (legacy 5-col format, see [monobank_legacy.csv](backend/tests/fixtures/monobank_legacy.csv)) OR the cell is empty, default to `currency_code=DEFAULT_CURRENCY_CODE` and leave `currency_alpha=None`, `currency_unknown_raw=None` — preserves existing behavior for legacy statements.
  - [x] 3.4 When `currency_idx` is present and the cell has a value, call `resolve_currency(row[currency_idx])`:
    - If hit → `currency_code = info.numeric_code`, `currency_alpha = info.alpha_code`.
    - If miss → `currency_code = UNKNOWN_CURRENCY_CODE`, `currency_unknown_raw = row[currency_idx].strip().upper()`. Emit `logger.warning("currency_unknown", extra={"raw_currency": currency_unknown_raw, "parser": "monobank"})`.
  - [x] 3.5 **Important — amount semantics stay unchanged.** The Monobank `amount` is still read from `"Сума в валюті картки (UAH)"` (card-currency column), NOT from `"Сума в валюті операції"`. Reasoning: downstream profile/health-score/category aggregations assume `Transaction.amount` is comparable across rows in the user's card currency. Switching to operation-currency amounts would break those aggregations and is out of scope (see "Deliberate non-goal" in Dev Notes). The story's purpose is to **identify** the operation currency, not to re-denominate `amount`. Document this in a one-line code comment.

- [x] **Task 4: Backend — PrivatBank parser uses the shared CURRENCY_MAP and flags unknowns** (AC: #2, #3)
  - [x] 4.1 Replace [backend/app/agents/ingestion/parsers/privatbank.py](backend/app/agents/ingestion/parsers/privatbank.py) `_resolve_currency_code()` with a function that returns the full `CurrencyInfo | None` so the per-row code can populate both numeric and alpha.
  - [x] 4.2 In `parse()`, when the currency cell is non-empty:
    - Hit → set `currency_code` + `currency_alpha`.
    - Miss → set `currency_code = UNKNOWN_CURRENCY_CODE`, `currency_unknown_raw = stripped_value`. Warn with the same structured-log shape as Monobank (`extra={"raw_currency": ..., "parser": "privatbank"}`).
  - [x] 4.3 When the currency column is missing entirely (defensive — header validation should already require it, see `EXPECTED_COLUMNS`), default to `DEFAULT_CURRENCY_CODE` and leave alpha/unknown_raw as `None`.

- [x] **Task 5: Backend — Generic parser uses the shared CURRENCY_MAP and flags unknowns** (AC: #2, #3)
  - [x] 5.1 Same shape as Task 4 in [backend/app/agents/ingestion/parsers/generic.py](backend/app/agents/ingestion/parsers/generic.py). Reuse `app.services.currency.resolve_currency()`.
  - [x] 5.2 The generic parser's `currency_idx` is heuristic (keyword-based) and may be `None` for arbitrary unknown CSVs — preserve the current default-to-UAH-only-when-no-column path.
  - [x] 5.3 Match Monobank/PrivatBank log shape: `logger.warning("currency_unknown", extra={"raw_currency": ..., "parser": "generic"})`.

- [x] **Task 6: Backend — `parser_service` flags transactions with unknown currency** (AC: #3)
  - [x] 6.1 In [backend/app/services/parser_service.py](backend/app/services/parser_service.py) `_parse_and_build_records()`, when constructing each `Transaction`, set:
    ```python
    Transaction(
        ...,
        currency_code=txn_data.currency_code,
        is_flagged_for_review=(txn_data.currency_unknown_raw is not None),
        uncategorized_reason=(
            "currency_unknown" if txn_data.currency_unknown_raw is not None else None
        ),
        ...,
    )
    ```
  - [x] 6.2 The existing categorization step (see [backend/app/agents/categorization/](backend/app/agents/categorization/)) sets the same two fields based on its own confidence-scoring logic. The interaction rule: the parser **may pre-flag** a transaction for `currency_unknown` BEFORE categorization runs. The categorization step must NOT clear an existing flag — confirm by reading `backend/app/agents/categorization/agent.py` (or equivalent) and only update flag fields when they are currently `False`/`None`. If the existing categorization unconditionally overwrites these fields, add a guard: `if txn.uncategorized_reason is None: ...`.
  - [x] 6.3 Preserve the raw alpha in `raw_data` — it is already there because parsers store the entire CSV row dict via `dict(zip(header, row))`. No code change needed; mention in dev notes for traceability.
  - [x] 6.4 The new `category` value for these flagged rows is `"uncategorized"` to match the convention in [backend/app/api/v1/transactions.py:64](backend/app/api/v1/transactions.py#L64) (`txn.category or "uncategorized"`). Categorization is still allowed to assign a real category later — being currency-unknown does not preclude having a category guess (the flag is what matters for the user-facing report).

- [x] **Task 7: Backend — Alembic migration: extend `uncategorized_reason` check constraint to include `currency_unknown`** (AC: #3)
  - [x] 7.1 Create [backend/alembic/versions/n0o1p2q3r4s5_add_currency_unknown_to_uncategorized_reason.py](backend/alembic/versions/n0o1p2q3r4s5_add_currency_unknown_to_uncategorized_reason.py) following the pattern in [k7l8m9n0o1p2_add_uncategorized_reason_to_transactions.py](backend/alembic/versions/k7l8m9n0o1p2_add_uncategorized_reason_to_transactions.py):
    ```python
    """add_currency_unknown_to_uncategorized_reason"""
    revision = "n0o1p2q3r4s5"
    down_revision = "m9n0o1p2q3r4"  # latest head — verify with `alembic heads` before committing

    def upgrade() -> None:
        op.drop_constraint("ck_transactions_uncategorized_reason", "transactions", type_="check")
        op.create_check_constraint(
            "ck_transactions_uncategorized_reason",
            "transactions",
            sa.column("uncategorized_reason").in_(
                ["low_confidence", "parse_failure", "llm_unavailable", "currency_unknown"]
            )
            | sa.column("uncategorized_reason").is_(None),
        )

    def downgrade() -> None:
        op.drop_constraint("ck_transactions_uncategorized_reason", "transactions", type_="check")
        op.create_check_constraint(
            "ck_transactions_uncategorized_reason",
            "transactions",
            sa.column("uncategorized_reason").in_(
                ["low_confidence", "parse_failure", "llm_unavailable"]
            )
            | sa.column("uncategorized_reason").is_(None),
        )
    ```
  - [x] 7.2 Verify the head before setting `down_revision`: `cd backend && .venv/bin/alembic heads`. If a newer head exists by the time this story runs (someone shipped another migration ahead), update `down_revision` accordingly. Migration filename letter-prefix follows the existing alphabetical pattern (`m9n0o1p2q3r4` → `n0o1p2q3r4s5`).
  - [x] 7.3 No data backfill — per AC #5, existing rows are not modified. The constraint widens; no existing row violates it.

- [x] **Task 8: Backend — surface `currency_unknown` in the flagged-transaction API** (AC: #3)
  - [x] 8.1 In [backend/app/api/v1/transactions.py:47](backend/app/api/v1/transactions.py#L47), extend `FlaggedTransactionResponse.uncategorized_reason` `Literal[...]` to include `"currency_unknown"`:
    ```python
    uncategorized_reason: Optional[Literal["low_confidence", "parse_failure", "llm_unavailable", "currency_unknown"]] = None
    ```
  - [x] 8.2 Extend `TransactionResponse` (`/transactions` GET) with two new optional fields so consumers can distinguish currencies and render correct symbols without doing a numeric→alpha lookup:
    ```python
    class TransactionResponse(BaseModel):
        ...
        currency_code: int           # existing — ISO 4217 numeric (UNKNOWN_CURRENCY_CODE = 0 if unrecognized)
        currency: Optional[str] = None       # NEW — ISO 4217 alpha-3 (e.g., "UAH", "CHF") for known currencies
        currency_unknown_raw: Optional[str] = None  # NEW — raw alpha from source CSV when unrecognized; None otherwise
    ```
  - [x] 8.3 Populate the new fields in the `list_transactions` mapping. To keep the response cheap and avoid per-row recomputation, derive both at serialization time via a small helper:
    ```python
    from app.services.currency import CURRENCY_MAP, UNKNOWN_CURRENCY_CODE

    _NUMERIC_TO_ALPHA = {info.numeric_code: info.alpha_code for info in CURRENCY_MAP.values()}

    def _alpha_for(numeric: int) -> str | None:
        return _NUMERIC_TO_ALPHA.get(numeric)
    ```
  - [x] 8.4 For the `currency_unknown_raw` field on `TransactionResponse`: pull it from `txn.raw_data` by best-effort lookup of common currency-column names (`"Валюта"`, `"Currency"`) — this is the only place we can recover it because we deliberately did not add a new DB column (Task 2.3). Helper in `app/services/currency.py`:
    ```python
    def extract_raw_currency(raw_data: dict | None) -> str | None:
        if not raw_data:
            return None
        for key in ("Валюта", "Currency"):
            value = raw_data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip().upper()
        return None
    ```
  - [x] 8.5 The flagged-transactions list (`GET /transactions/flagged`) does NOT need to expose `currency_code`/`currency` for V1 — the user-facing display in `UncategorizedTransactions` shows amount in UAH today. Defer multi-currency display in the flagged list to Task 11; if it is dropped from scope, add a TD-NNN tech-debt entry.

- [x] **Task 9: Frontend — extend `formatCurrency` to accept a currency code** (AC: #1, #2)
  - [x] 9.1 Update [frontend/src/lib/format/currency.ts](frontend/src/lib/format/currency.ts):
    ```typescript
    const localeMap: Record<string, string> = { uk: "uk-UA", en: "en-US" };
    const SUPPORTED_CURRENCIES = new Set(["UAH", "USD", "EUR", "GBP", "PLN", "CHF", "JPY", "CZK", "TRY"]);

    export function formatCurrency(
      amount: number,
      locale: string = "uk",
      currency: string = "UAH",
    ): string {
      const intlLocale = localeMap[locale] ?? localeMap.uk;
      const safeCurrency = SUPPORTED_CURRENCIES.has(currency.toUpperCase()) ? currency.toUpperCase() : "UAH";
      return new Intl.NumberFormat(intlLocale, {
        style: "currency",
        currency: safeCurrency,
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      }).format(amount);
    }
    ```
    - **Backward compat:** `currency` param defaults to `"UAH"`. Existing callers (passing 1–2 args) keep working unchanged. Verify with `grep -rn "formatCurrency(" frontend/src` before merging.
  - [x] 9.2 Mirror the same change in [frontend/src/features/profile/format.ts](frontend/src/features/profile/format.ts) (note this file accepts `kopiykas: number` and divides by 100 — keep that API; only add the optional `currency` arg). Both `formatCurrency` functions must support the same currency set; if duplication is unwelcome, **deduplicate** by deleting the profile copy and importing from `@/lib/format/currency` (then update call sites and divide-by-100 callers — see [UncategorizedTransactions.tsx:68](frontend/src/features/profile/components/UncategorizedTransactions.tsx#L68), [MonthlyComparison.tsx](frontend/src/features/profile/components/MonthlyComparison.tsx), [CategoryBreakdown.tsx](frontend/src/features/profile/components/CategoryBreakdown.tsx)). **Recommended:** dedup. The two parallel `formatCurrency` implementations are pre-existing tech debt this story can clean up cheaply.
  - [x] 9.3 The Intl.NumberFormat `currency` style automatically renders the correct symbol for each ISO 4217 alpha code in both `uk-UA` and `en-US` locales — no manual symbol map is needed on the frontend. Manually verify the symbols for CHF / JPY / CZK / TRY in the Vitest snapshot (Intl output may include narrow no-break spaces; tests should match the current platform's output).
  - [x] 9.4 Unknown currencies (i.e., `currency` not in `SUPPORTED_CURRENCIES`) fall back to `"UAH"` formatting to avoid throwing. The flagged-transactions UI is the only place where unknowns surface today; render them with the raw alpha as a separate badge (Task 11) rather than relying on `formatCurrency` to display the unknown.

- [x] **Task 10: Frontend — add `currency_unknown` to the uncategorized reason set** (AC: #3)
  - [x] 10.1 In [frontend/src/features/profile/components/UncategorizedTransactions.tsx:9](frontend/src/features/profile/components/UncategorizedTransactions.tsx#L9), extend `KNOWN_REASONS`:
    ```typescript
    const KNOWN_REASONS = new Set([
      "low_confidence",
      "parse_failure",
      "llm_unavailable",
      "currency_unknown",
    ]);
    ```
  - [x] 10.2 Update the `uncategorizedReason` type in the flagged-transactions hook ([frontend/src/features/profile/hooks/use-flagged-transactions.ts](frontend/src/features/profile/hooks/use-flagged-transactions.ts)) to include `"currency_unknown"` in its `Literal[...]` union (mirroring the backend `FlaggedTransactionResponse`).
  - [x] 10.3 No render logic change is required — the existing branch `t(\`uncategorized.reason.${txn.uncategorizedReason}\`)` will pick up the new i18n key (Task 12) once it exists.

- [x] **Task 11: Frontend — show the raw currency code on flagged rows when present** (AC: #3)
  - [x] 11.1 Extend [backend/app/api/v1/transactions.py](backend/app/api/v1/transactions.py) `FlaggedTransactionResponse` (Task 8) with `currency_unknown_raw: Optional[str] = None` populated from `extract_raw_currency(txn.raw_data)` ONLY when `txn.uncategorized_reason == "currency_unknown"`. (Empty/null otherwise — keeps the response shape predictable.)
  - [x] 11.2 In [UncategorizedTransactions.tsx](frontend/src/features/profile/components/UncategorizedTransactions.tsx), when `txn.currencyUnknownRaw` is present, render it next to the reason line as a small monospace badge so the user can see WHICH currency was unrecognized (e.g., "currency_unknown · `XYZ`"). Use shadcn `Badge` (`variant="outline"`) for visual consistency with existing chips elsewhere in the profile feature.
  - [x] 11.3 Add a TanStack Query type extension in `use-flagged-transactions.ts` to surface the new field. No additional API call.

- [x] **Task 12: i18n strings** (AC: #1, #3)
  - [x] 12.1 Add to [frontend/messages/en.json](frontend/messages/en.json) under `profile.uncategorized.reason`:
    ```json
    "currency_unknown": "Unrecognized currency"
    ```
  - [x] 12.2 Add the equivalent to [frontend/messages/uk.json](frontend/messages/uk.json):
    ```json
    "currency_unknown": "Невідома валюта"
    ```
  - [x] 12.3 Verify locale parity: `python -c "import json; en=set(_walk(json.load(open('frontend/messages/en.json')))); uk=...; print(en ^ uk)"` (or whatever existing parity tool — there is no formal parity test in the repo per the Story 2.8 review, so this is a manual diff for now).

- [x] **Task 13: Backend tests** (AC: #1, #2, #3, #4, #5)
  - [x] 13.1 Create [backend/tests/test_currency_map.py](backend/tests/test_currency_map.py): unit tests for `app.services.currency`:
    - `CURRENCY_MAP` contains all 9 codes with correct numeric mappings (UAH=980, USD=840, EUR=978, GBP=826, PLN=985, CHF=756, JPY=392, CZK=203, TRY=949).
    - `resolve_currency("uah")` (lowercase) and `resolve_currency(" UAH ")` (whitespace) both hit.
    - `resolve_currency("XYZ")` returns `None`.
    - `resolve_currency(None)` returns `None`.
    - `extract_raw_currency({"Валюта": "CHF"})` returns `"CHF"`; `extract_raw_currency({"Currency": " jpy "})` returns `"JPY"`; `extract_raw_currency({})` and `extract_raw_currency(None)` return `None`.
  - [x] 13.2 Add a Monobank fixture [backend/tests/fixtures/monobank_multi_currency.csv](backend/tests/fixtures/monobank_multi_currency.csv) containing one transaction per currency (UAH, USD, CHF, JPY, CZK, TRY) plus one row with an unrecognized currency code (e.g., `"XYZ"`) — modern 10-column format. Use the same column shape as `monobank_modern_multi.csv`.
  - [x] 13.3 Extend [backend/tests/test_monobank_parser.py](backend/tests/test_monobank_parser.py) with a `TestMonobankParserCurrency` class:
    - Modern format with CHF/JPY/CZK/TRY rows: `currency_code` is the correct numeric, `currency_alpha` is the alpha, `currency_unknown_raw` is `None`, `is_flagged_for_review` flag (downstream — assert via `parse_and_store_transactions` integration test) is `False`.
    - Modern format with `"XYZ"` row: `currency_code == 0`, `currency_alpha is None`, `currency_unknown_raw == "XYZ"`, `caplog` contains `"currency_unknown"` warning with `extra["raw_currency"] == "XYZ"`.
    - **Legacy 5-column format unchanged** (regression): every row still has `currency_code == 980` and no flagging — proves AC #5 for the legacy path.
  - [x] 13.4 Add a similar `TestPrivatBankParserCurrencyExtended` class in [backend/tests/test_privatbank_parser.py](backend/tests/test_privatbank_parser.py) (with a new fixture or by extending `privatbank_standard.csv`) — same matrix.
  - [x] 13.5 Add equivalent tests in [backend/tests/test_generic_parser.py](backend/tests/test_generic_parser.py) using a generic CSV with the heuristic currency column.
  - [x] 13.6 Add an integration test in [backend/tests/test_processing_tasks.py](backend/tests/test_processing_tasks.py) (or `test_flagged_transactions.py`) that runs `process_upload.delay` in eager mode against a CSV containing one `XYZ` currency row, then asserts:
    - Transaction is persisted with `currency_code == 0`, `is_flagged_for_review == True`, `uncategorized_reason == "currency_unknown"`.
    - `GET /transactions/flagged` returns the row with `uncategorizedReason: "currency_unknown"` and `currencyUnknownRaw: "XYZ"`.
  - [x] 13.7 Migration test: spin up a fresh sqlite DB, run `alembic upgrade head`, insert a row with `uncategorized_reason="currency_unknown"`, assert no `IntegrityError`. Existing migration tests live in [backend/tests/test_pipeline_checkpointing.py](backend/tests/test_pipeline_checkpointing.py) for reference patterns.
  - [x] 13.8 Regression: full backend suite must continue to pass. Baseline at story creation: **439 tests** (per Story 2.8 review).

- [x] **Task 14: Frontend tests** (AC: #1, #3)
  - [x] 14.1 Update [frontend/src/lib/format/__tests__/currency.test.ts](frontend/src/lib/format/__tests__/currency.test.ts):
    - `formatCurrency(100, "uk", "CHF")` renders `"100,00 CHF"` (or current Intl output — snapshot the actual string).
    - `formatCurrency(100, "en", "JPY")` renders `"¥100.00"` or platform-current output.
    - `formatCurrency(100, "uk")` (no third arg) still renders UAH (backward-compat assertion).
    - Unknown currency `"XYZ"` falls back to UAH formatting (AC: prevents throw).
  - [x] 14.2 Update [frontend/src/features/profile/__tests__/UncategorizedTransactions.test.tsx](frontend/src/features/profile/__tests__/UncategorizedTransactions.test.tsx):
    - When `uncategorizedReason: "currency_unknown"` is in the mocked hook output, the row renders the localized "Unrecognized currency" reason.
    - When `currencyUnknownRaw: "XYZ"` is present, a badge with text `"XYZ"` is rendered.
    - Existing reason-rendering tests still pass (regression).
  - [x] 14.3 Update the matching unit test for [frontend/src/features/profile/format.ts](frontend/src/features/profile/format.ts) if it exists (or its callers' tests in `MonthlyComparison.test.tsx`, `CategoryBreakdown.test.tsx`). If Task 9.2 dedup'd the two `formatCurrency`s, those existing tests should keep passing — but verify.
  - [x] 14.4 Regression: full frontend suite must continue to pass. Baseline at story creation: **377 tests** across 41 files (per Story 2.8 review).

## Dev Notes

### Critical Architecture Compliance

**Tech Stack (MUST use):**
- Backend: Python 3.12, FastAPI, SQLModel, Celery 5.6.x, Alembic, structured logging via `extra={...}` keyword.
- Frontend: Next.js 16.1 App Router (read `node_modules/next/dist/docs/` before any new Next API usage — see [frontend/AGENTS.md](frontend/AGENTS.md)), `next-intl`, Vitest + Testing Library, shadcn/ui, Tailwind CSS 4.x.
- ORM: SQLModel (SQLAlchemy 2.x + Pydantic v2). Migrations: Alembic. Down-revision must be the current head (`alembic heads`).
- Pydantic camelCase: API JSON uses `camelCase` via `alias_generator=to_camel, populate_by_name=True` — already configured on both `TransactionResponse` and `FlaggedTransactionResponse`.

**Backend component dependency rules (never violate):**
| Layer | Can Depend On | NEVER Depends On |
|---|---|---|
| `api/` | `core/`, `models/`, `services/` | `agents/`, `tasks/` |
| `services/` | `core/`, `models/` | `api/`, `tasks/` |
| `tasks/` | `core/`, `services/`, `agents/` | `api/` |
| `agents/parsers/` | `services/` (for `app.services.currency`) | `api/`, `tasks/`, `models/` (parsers emit dataclasses, not ORM rows) |

`app/services/currency.py` is allowed: it's a pure-data module (no ORM, no I/O) consumed by `agents/ingestion/parsers/*.py` and `api/v1/transactions.py`.

**Data format rules:**
- Currency: ISO 4217 numeric (`int`) in DB; ISO 4217 alpha-3 (`str`) in API responses; symbol rendering is the frontend's job via `Intl.NumberFormat`.
- `Transaction.currency_code: int` is the SOURCE OF TRUTH. Sentinel `0` (`UNKNOWN_CURRENCY_CODE`) means "unrecognized at parse time" — distinguishable from legitimate UAH (980).
- Money: integer kopiykas (smallest unit of card currency). Foreign-currency conversions happen at the Monobank source; `Transaction.amount` stays in card currency.

### What changes — and what deliberately does NOT

**Changes:**
- One central `CURRENCY_MAP` in `backend/app/services/currency.py` (replaces 2 duplicate maps in parsers).
- 4 new currencies recognized: CHF, JPY, CZK, TRY (joining UAH, USD, EUR, GBP, PLN).
- Monobank modern parser now reads the `Валюта`/`Currency` column (was hardcoded to 980).
- Unknown currencies are flagged for the user-facing uncategorized report rather than silently coerced to UAH.
- `TransactionResponse` API gains `currency` (alpha) and `currency_unknown_raw` (string) fields.
- `formatCurrency` frontend helper accepts an optional currency code (defaults to UAH for backward compat).
- New Alembic migration extends the `uncategorized_reason` check constraint by one allowed value.

**Deliberate non-goals (do not do these in this story):**
- **Do NOT switch Monobank `amount` from card currency to operation currency.** The "Сума в валюті операції" column would denominate amounts in foreign currency for foreign-currency rows, which would silently break Profile/HealthScore/CategoryBreakdown aggregations that assume all amounts are comparable in UAH kopiykas. The story's intent is to **identify** the operation currency, not to re-denominate the amount. If the team later wants per-currency aggregation, that's a separate epic.
- **Do NOT add a `currency_code_raw: str` column to `transactions`.** The raw alpha is already preserved in `raw_data` JSON. Adding a column would also require backfilling existing rows (which AC #5 prohibits) or accepting a sparse new column.
- **Do NOT backfill** existing UAH-defaulted rows. AC #5 explicitly forbids it.
- **Do NOT modify the categorization agent's flagging logic.** Only add the parser-side pre-flag, and a guard in `parser_service` so the categorization step doesn't unintentionally clear it (Task 6.2).
- **Do NOT add new currencies beyond the 9 specified.** The 9-currency list is the AC #4 minimum and a deliberate scope cap; further currencies belong in tech debt or a future story.

### Why centralize the map?

Two duplicate `CURRENCY_MAP` constants currently live in [generic.py:23-29](backend/app/agents/ingestion/parsers/generic.py#L23-L29) and [privatbank.py:26-32](backend/app/agents/ingestion/parsers/privatbank.py#L26-L32) — a classic recipe for drift. Adding 4 currencies to two places (and eventually a third — Monobank — and a fourth — frontend) compounds the problem. One source-of-truth module in `app/services/currency.py` lets backend parsers, the API serializer, and (mirrored, not imported) the frontend's `formatCurrency` agree on the supported set.

### Why a sentinel `currency_code = 0` (and not nullable)?

Three options were considered:

| Option | Pro | Con |
|---|---|---|
| Make `currency_code` nullable | Most semantically honest | Breaks existing query/index assumptions; existing rows have `980` not `NULL`; downstream code uses `int` math freely. |
| Sentinel `0` (`UNKNOWN_CURRENCY_CODE`) | No schema change beyond the `uncategorized_reason` constraint widen; `0` is not a valid ISO 4217 numeric (codes are 100–999) so collision-free; existing `int` math still works. | Requires a constant; readers must know `0 == unknown`. |
| Default to `980` and rely solely on the flag | Zero schema/code change | Conflates legitimate UAH with "we have no idea" — breaks AC #3 ("never silently converted to UAH"). |

Sentinel `0` is the chosen middle path. The constant is exported from `app/services/currency.py` so all readers reference one symbol.

### Monobank format reality (HEADER_MAPPINGS context)

Modern Monobank statements ([fixture](backend/tests/fixtures/monobank_modern_multi.csv)) have 10 columns including:
- `"Сума в валюті картки (UAH)"` (or `"Card currency amount, (UAH)"`) — amount in CARD currency (always UAH for Ukrainian users).
- `"Сума в валюті операції"` (or `"Operation amount"`) — amount in OPERATION currency.
- `"Валюта"` (or `"Currency"`) — alpha code of the OPERATION currency.
- `"Курс"` (or `"Exchange rate"`) — conversion rate applied for that row.

The header text `"Сума в валюті картки (UAH)"` literally encodes the card currency in parentheses — for a hypothetical USD-card user, this would read `"Сума в валюті картки (USD)"`, not UAH. The existing `HEADER_MAPPINGS` hardcodes the UAH variant, which is correct for the current 100% Ukrainian user base. **Out of scope here**: detecting non-UAH cards. Add a TD-NNN entry if the team wants it (`monobank-card-currency-detection`).

Legacy Monobank ([fixture](backend/tests/fixtures/monobank_legacy.csv)) is 5 columns with no currency column at all — keep defaulting to UAH and skip the new flagging path.

### Currency list rationale (AC #4)

| Code | Numeric | Why included |
|---|---|---|
| UAH | 980 | National currency; vast majority of transactions |
| USD | 840 | Most common foreign-spending currency for Ukrainian users (already supported) |
| EUR | 978 | Second most common foreign-spending currency (already supported) |
| GBP | 826 | Already supported; common UK travel/spending |
| PLN | 985 | Already supported; large Ukrainian diaspora and EU-Poland border travel |
| CHF | 756 | New — Swiss Franc; common in EU travel and salary payments |
| JPY | 392 | New — Japanese Yen; e-commerce / travel |
| CZK | 203 | New — Czech Koruna; EU travel destination, growing diaspora |
| TRY | 949 | New — Turkish Lira; popular travel destination, frequent transactions |

This is the 9-code minimum from AC #4. The next likely additions (when needed): SEK, NOK, AUD, CAD — explicitly out of scope here.

### Previous Story Intelligence

- **Story 6.3 (Uncategorized Transaction Flagging)** — established the `uncategorized_reason` column, its check constraint, the categorization-agent flagging code path, and the `GET /transactions/flagged` endpoint with the `FlaggedTransactionResponse` model. This story extends both the constraint and the response Literal type — read [implementation 6-3-uncategorized-transaction-flagging.md](_bmad-output/implementation-artifacts/6-3-uncategorized-transaction-flagging.md) before touching the categorization agent (Task 6.2).
- **Story 2.4 (Additional Bank Format Parser — PrivatBank + Generic)** — established the PrivatBank/Generic parser conventions and the duplicate `CURRENCY_MAP` pattern this story consolidates. See [2-4-additional-bank-format-parser.md](_bmad-output/implementation-artifacts/2-4-additional-bank-format-parser.md).
- **Story 2.3 (Monobank CSV Parser)** — established the Monobank `HEADER_MAPPINGS` pattern. The Task 3 add (`"currency"` mapping) follows the same shape.
- **Story 6.5 (Pipeline Performance & Upload Metrics Tracking)** — added structured metrics logging. The new `currency_unknown` warning logs are user-data observability, NOT pipeline metrics — keep them as `logger.warning(...)`, do not push them into `pipeline_metrics`.
- **Story 2.8 (Upload Completion UX & Summary)** — last shipped story (2026-04-16). Did not touch parsers or the currency layer; no merge-conflict risk in `parsers/`, `parser_service.py`, or `api/v1/transactions.py`.

**Do NOT repeat these mistakes (accumulated from Stories 2.5–2.8, 6.3):**
1. **Datetime in tests** — use `datetime.now(UTC).replace(tzinfo=None)` for SQLite test compatibility (helper `_utcnow` exists in [backend/app/models/transaction.py:8](backend/app/models/transaction.py#L8) and [backend/app/tasks/processing_tasks.py](backend/app/tasks/processing_tasks.py)).
2. **Sync SQLite tests** need `StaticPool`, not `NullPool` — see existing parser tests for the pattern.
3. **Celery task patching** — `request` cannot be patched with `patch.object`; use `patch.object(task, "retry")` instead.
4. **Upload tests** require `process_upload.delay` mock to prevent task dispatch.
5. **i18n key removals** — grep BOTH `frontend/src` AND `frontend/messages` AND test files before removing keys; stale next-intl refs break the runtime, not just tests.
6. **Frontend hook tests using TanStack Query** must wrap in `QueryClientProvider` with `retry: false`.
7. **`vi.mock("@/i18n/navigation")`** and `vi.mock("next-intl")` with `createUseTranslations()` from `@/test-utils/intl-mock` are required in every frontend component test that touches translations.
8. **Pre-existing `formatCurrency` duplication** — Story 2.8 added/touched the upload/profile flow without consolidating. This story is a good moment to dedup IF Task 9.2 path is taken — but only if it stays a focused cleanup, not a wider refactor.

### Project Structure Notes

- New backend module: `backend/app/services/currency.py` (single source of truth for the map; allowed for both `agents/parsers/*` and `api/v1/transactions.py` to import).
- New backend test file: `backend/tests/test_currency_map.py` (matches existing one-file-per-feature convention).
- New backend test fixture: `backend/tests/fixtures/monobank_multi_currency.csv` (per AC #1; mirrors the modern 10-column shape of `monobank_modern_multi.csv`).
- New Alembic migration: `backend/alembic/versions/n0o1p2q3r4s5_add_currency_unknown_to_uncategorized_reason.py` (filename letter-prefix continues the alphabetical sequence).
- No new API endpoints; no new pages.
- No new frontend feature folder; component changes are in-place under `frontend/src/features/profile/components/UncategorizedTransactions.tsx` and `frontend/src/lib/format/currency.ts`.

### Git Intelligence (Latest Commits)

Most recent commits on `main` (last 6, via `git log --oneline -6`):

| SHA | Title |
|---|---|
| `d447bc5` | Story 2.8: Upload Completion UX & Summary |
| `738db34` | Story 1.9: Project Versioning Baseline |
| `d6e4d25` | Story 1.8: Forgot-Password Flow |
| `4035de8` | Phase 1 planning and kick-off |
| `3c44dfc` | Story 6.6: Operator Job Status & Health Queries |
| `dee2ee7` | Story 6.5: Pipeline Performance & Upload Metrics Tracking |

Earlier relevant: `48c49f6` (Story 6.3 — `uncategorized_reason` column) and the Story 2.3/2.4 commits that established the parser layout.

None of the last 6 commits touched the parser files (`monobank.py`, `privatbank.py`, `generic.py`, `parser_service.py`), the transactions API (`api/v1/transactions.py`), the `Transaction` model, or the `currency.ts` formatter. **No merge-conflict risk for any file in this story's scope.**

### Latest Tech Information

- **Intl.NumberFormat** symbol output for CHF/JPY/CZK/TRY in modern V8 / Node ≥ 20: snapshot the actual rendered strings rather than asserting an exact glyph, because Intl includes narrow no-break spaces (`U+202F`) in many locales (e.g., `"100,00\u00a0CHF"`). Use Vitest's snapshot or `toBe(...)` with the actual character — not a hand-written ASCII string. Reference: ECMA-402 / Unicode CLDR currency display. (Verified pattern: existing `MonthlyComparison.test.tsx` already snapshots `formatCurrency` output the same way.)
- **Alembic check-constraint changes**: SQLite (used in tests) requires the entire constraint to be dropped+recreated within a `with op.batch_alter_table(...)` block, while PostgreSQL accepts plain `op.drop_constraint` + `op.create_check_constraint`. The reference migration [k7l8m9n0o1p2_add_uncategorized_reason_to_transactions.py](backend/alembic/versions/k7l8m9n0o1p2_add_uncategorized_reason_to_transactions.py) uses the plain form because the project's Alembic env runs against PostgreSQL in production and SQLite test runs use a fresh DB created from `SQLModel.metadata.create_all()` (so they bypass migrations). **Confirm** by reading [backend/alembic/env.py](backend/alembic/env.py) and [backend/tests/conftest.py](backend/tests/conftest.py) before submitting; if migrations DO run in tests, switch to `op.batch_alter_table` for SQLite compatibility.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 2.9: Expand CURRENCY_MAP](_bmad-output/planning-artifacts/epics.md#L737-L763) — story foundation
- [Source: _bmad-output/planning-artifacts/prd.md#FR38](_bmad-output/planning-artifacts/prd.md#L614) — uncategorized transactions report (AC #3 reference)
- [Source: _bmad-output/implementation-artifacts/6-3-uncategorized-transaction-flagging.md](_bmad-output/implementation-artifacts/6-3-uncategorized-transaction-flagging.md) — `uncategorized_reason` column origin and check-constraint pattern (Tasks 7, 8)
- [Source: _bmad-output/implementation-artifacts/2-4-additional-bank-format-parser.md](_bmad-output/implementation-artifacts/2-4-additional-bank-format-parser.md) — PrivatBank / Generic parser conventions (Tasks 4, 5)
- [Source: _bmad-output/implementation-artifacts/2-3-monobank-csv-parser.md](_bmad-output/implementation-artifacts/2-3-monobank-csv-parser.md) — Monobank `HEADER_MAPPINGS` and column-resolution pattern (Task 3)
- [Source: backend/app/agents/ingestion/parsers/monobank.py:17-23](backend/app/agents/ingestion/parsers/monobank.py#L17-L23) — `HEADER_MAPPINGS` to extend with `"currency"`
- [Source: backend/app/agents/ingestion/parsers/privatbank.py:26-32](backend/app/agents/ingestion/parsers/privatbank.py#L26-L32) — duplicate `CURRENCY_MAP` to delete
- [Source: backend/app/agents/ingestion/parsers/generic.py:23-29](backend/app/agents/ingestion/parsers/generic.py#L23-L29) — duplicate `CURRENCY_MAP` to delete
- [Source: backend/app/agents/ingestion/parsers/base.py](backend/app/agents/ingestion/parsers/base.py) — `TransactionData` to extend with `currency_alpha` / `currency_unknown_raw`
- [Source: backend/app/services/parser_service.py:67-83](backend/app/services/parser_service.py#L67-L83) — `Transaction` construction site to add the flag-on-unknown logic
- [Source: backend/app/models/transaction.py:23](backend/app/models/transaction.py#L23) — `currency_code: int` field reference
- [Source: backend/app/api/v1/transactions.py:38-48](backend/app/api/v1/transactions.py#L38-L48) — `FlaggedTransactionResponse` Literal type to extend
- [Source: backend/alembic/versions/k7l8m9n0o1p2_add_uncategorized_reason_to_transactions.py](backend/alembic/versions/k7l8m9n0o1p2_add_uncategorized_reason_to_transactions.py) — pattern for the new migration
- [Source: backend/tests/fixtures/monobank_modern_multi.csv](backend/tests/fixtures/monobank_modern_multi.csv) — modern 10-column shape to mimic for `monobank_multi_currency.csv` fixture
- [Source: backend/tests/fixtures/monobank_legacy.csv](backend/tests/fixtures/monobank_legacy.csv) — legacy 5-column shape (no currency column — regression target for Task 13.3 last assertion)
- [Source: frontend/src/lib/format/currency.ts](frontend/src/lib/format/currency.ts) — `formatCurrency` to extend (Task 9.1)
- [Source: frontend/src/features/profile/format.ts](frontend/src/features/profile/format.ts) — duplicate `formatCurrency` (Task 9.2 dedup target)
- [Source: frontend/src/features/profile/components/UncategorizedTransactions.tsx](frontend/src/features/profile/components/UncategorizedTransactions.tsx) — UI to add the new reason + raw-currency badge (Tasks 10, 11)
- [Source: frontend/messages/en.json](frontend/messages/en.json), [frontend/messages/uk.json](frontend/messages/uk.json) — i18n strings (Task 12)
- [Source: frontend/AGENTS.md](frontend/AGENTS.md) — "This is NOT the Next.js you know" — read `node_modules/next/dist/docs/` before any new Next API usage

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (1M context) — `claude-opus-4-6[1m]`

### Debug Log References

- Backend regression suite: 469 passed (baseline: 439 → +30 new tests).
- Frontend regression suite: 387 passed (baseline: 377 → +10 new tests).
- `ruff` clean on all files I modified.
- `tsc --noEmit` clean on all files I modified (3 pre-existing errors in unrelated test files).
- First parser caplog test iteration failed because `app` logger has `propagate=False`; fixed by temporarily enabling propagation inside the test, mirroring the pattern in `tests/agents/test_categorization.py`.
- One initial regression test in `test_monobank_parser.py::test_modern_multi_all_uah_no_flagging_regression` assumed the fixture was all UAH, but it actually has a USD Amazon.com row. Rewrote as `test_modern_multi_currency_column_parsed` to assert the new correct behaviour.

### Completion Notes List

- Centralized `CURRENCY_MAP` in `app/services/currency.py` with 9 currencies (UAH, USD, EUR, GBP, PLN, CHF, JPY, CZK, TRY). Removed duplicate maps from `privatbank.py` and `generic.py`; Monobank gains currency resolution for the first time.
- Added `UNKNOWN_CURRENCY_CODE = 0` sentinel. `Transaction.currency_code` stays `int` (no schema change there).
- Parser-side pre-flag: when a row's currency is not recognized, the parser sets `is_flagged_for_review=True` and `uncategorized_reason="currency_unknown"`. A guard in `processing_tasks.py` prevents the categorization step from overwriting this flag.
- Alembic migration `n0o1p2q3r4s5` widens the `ck_transactions_uncategorized_reason` CHECK constraint to accept `currency_unknown`. No data backfill (AC #5).
- API: `FlaggedTransactionResponse` Literal extended with `"currency_unknown"`; `TransactionResponse` now includes `currency` (alpha) and `currencyUnknownRaw`. Raw unknown currency is recovered best-effort from `raw_data` via `extract_raw_currency()`.
- Frontend: both `formatCurrency` helpers accept an optional currency code (defaults to UAH; unknowns fall back to UAH). Dedup was deferred — the two helpers have different `amount` semantics and dedup would be invasive; pre-existing tech debt noted.
- `UncategorizedTransactions` renders the localized "Unrecognized currency" reason and a monospace outline badge showing the raw unknown currency code (e.g., `XYZ`). No `Badge` component exists in shadcn/ui locally, so the badge is an inline styled span.
- i18n strings added to both `en.json` and `uk.json` under `profile.uncategorized.reason.currency_unknown`.

### File List

Backend — added:
- `backend/app/services/currency.py`
- `backend/alembic/versions/n0o1p2q3r4s5_add_currency_unknown_to_uncategorized_reason.py`
- `backend/tests/test_currency_map.py`
- `backend/tests/fixtures/monobank_multi_currency.csv`

Backend — modified:
- `backend/app/agents/ingestion/parsers/base.py` — `TransactionData.currency_alpha` + `currency_unknown_raw`
- `backend/app/agents/ingestion/parsers/monobank.py` — reads `Валюта`/`Currency`; flags unknowns
- `backend/app/agents/ingestion/parsers/privatbank.py` — uses shared `resolve_currency`; flags unknowns
- `backend/app/agents/ingestion/parsers/generic.py` — uses shared `resolve_currency`; flags unknowns
- `backend/app/services/parser_service.py` — pre-flags `currency_unknown` at persist time
- `backend/app/tasks/processing_tasks.py` — guards parser-side flag from being overwritten by categorization
- `backend/app/api/v1/transactions.py` — extended `TransactionResponse`/`FlaggedTransactionResponse` fields
- `backend/tests/test_monobank_parser.py` — `TestMonobankParserCurrency`
- `backend/tests/test_privatbank_parser.py` — `TestPrivatBankParserCurrencyExtended`
- `backend/tests/test_generic_parser.py` — `TestGenericParserCurrency`
- `backend/tests/test_flagged_transactions.py` — `test_currency_unknown_reason_and_raw_surfaced` + `raw_data` seeding support

Frontend — modified:
- `frontend/src/lib/format/currency.ts` — optional `currency` arg, unknown → UAH fallback
- `frontend/src/features/profile/format.ts` — same pattern mirrored; `formatAmountOnly` helper for currency-less rendering
- `frontend/src/features/profile/hooks/use-flagged-transactions.ts` — `UncategorizedReason` union + `currencyUnknownRaw`
- `frontend/src/features/profile/components/UncategorizedTransactions.tsx` — new reason + raw-currency badge; suppresses UAH glyph when `currencyUnknownRaw` is set
- `frontend/src/lib/format/__tests__/currency.test.ts` — multi-currency test block
- `frontend/src/features/profile/__tests__/UncategorizedTransactions.test.tsx` — `currency_unknown` + badge tests + glyph-suppression tests
- `frontend/messages/en.json`, `frontend/messages/uk.json` — `currency_unknown` i18n key

Code review follow-ups (2026-04-16):
- `backend/tests/test_processing_tasks.py` — added `TestProcessUploadCurrencyUnknownFlag` integration test exercising the categorization guard end-to-end.
- `backend/tests/test_transactions.py` — new assertions for `currency` / `currencyUnknownRaw` on `GET /transactions`.
- `backend/tests/test_currency_map.py` — added `TestCurrencyUnknownMigration` (structural migration tests + API Literal parity check + end-to-end persistence assertion).

### Senior Developer Review (AI) — 2026-04-16

Adversarial review after `[review]` status. Full backend + frontend suites green pre-review; ACs all implemented.

**MEDIUM findings — all fixed in this review:**

- **M1 — Missing migration test for Task 13.7.** Added `TestCurrencyUnknownMigration` in `backend/tests/test_currency_map.py` covering: migration file presence, `currency_unknown` in upgrade path, absence in downgrade, revision chain, API `Literal` parity with the migration's allowed list, and end-to-end persistence of a `currency_unknown` row via `SQLModel.metadata.create_all()`. Documented in the test docstring why a live `alembic upgrade head` against SQLite is not viable (migration uses plain `op.drop_constraint`, which SQLite doesn't support; test runs bypass migrations per `env.py`).
- **M2 — Integration test for the categorization-guard path.** Added `TestProcessUploadCurrencyUnknownFlag::test_unknown_currency_row_persists_flag_after_categorization` in `backend/tests/test_processing_tasks.py`. Mocks `build_pipeline` with a categorization result that tries to CLEAR `flagged=False, uncategorized_reason=None` on every row; asserts the parser-side `currency_unknown` pre-flag survives for the XYZ transaction while the categorization step's `category` assignment still applies. Now exercises [processing_tasks.py:229](backend/app/tasks/processing_tasks.py#L229).
- **M3 — `TransactionResponse.currency` / `currencyUnknownRaw` untested.** Added `TestTransactionsEndpoint::test_list_transactions_exposes_currency_unknown_raw` in `backend/tests/test_transactions.py` and extended the existing happy-path test to assert all three currency fields on every item. Seeds one CHF row (recognized → alpha="CHF") and one XYZ row (unknown → `currencyUnknownRaw="XYZ"`).
- **M4 — UAH glyph rendered on flagged amount with unknown currency.** Added `formatAmountOnly(kopiykas, locale)` helper in `frontend/src/features/profile/format.ts`; `UncategorizedTransactions` now renders the plain number when `currencyUnknownRaw` is set, so the row reads "−100,00" next to the "XYZ" badge instead of "−100,00 ₴". Two new tests in `UncategorizedTransactions.test.tsx` assert the suppression and the non-suppression (fallback) cases.

**LOW findings:**

- L1 → [TD-009](../../docs/tech-debt.md). Parallel `formatCurrency` helpers with different amount semantics.
- L2 → [TD-010](../../docs/tech-debt.md). `CurrencyInfo.symbol` populated but unused on the backend.
- L3 — kept story-local: logger-propagation dance duplicated across `test_monobank_parser.py:768`, `test_privatbank_parser.py:295`, `test_generic_parser.py:294`. Fix shape: shared `caplog_app` fixture in `conftest.py`.
- L4 → [TD-011](../../docs/tech-debt.md). `extract_raw_currency` hardcoded header keys.
- L5 — withdrawn on review: Task 1.3's "re-export DEFAULT_CURRENCY_CODE" wording drifted from the final implementation; the code is correct (parsers import directly from `app.services.currency`).

**Post-review suite status:** Backend 477/477, Frontend 389/389.

### Change Log

- 2026-04-16: Story 2.9 implementation complete (centralized CURRENCY_MAP, 4 new currencies, parser-side flagging of unknowns, migration for widened check constraint, API + frontend exposure, i18n). Backend 469/469, Frontend 387/387.
- 2026-04-16: Senior Developer AI review — fixed 4 MEDIUM findings (missing migration test, missing categorization-guard integration test, untested API response fields, misleading UAH glyph on flagged unknown-currency rows). Promoted L1/L2/L4 to TD-009/010/011. Backend 477/477, Frontend 389/389. Status → done.
