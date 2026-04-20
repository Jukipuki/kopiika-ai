# Tech Spec: Ingestion & Categorization Hardening (Epic 11)

- **Date:** 2026-04-19
- **Author:** Winston (Architect), reviewed with Oleh
- **Related:** [parsing-and-categorization-issues.md](../implementation-artifacts/parsing-and-categorization-issues.md), ADR-0001, ADR-0002
- **Scope:** Epic 11 stories 11.1 – 11.10, plus cross-epic Story 4.9

## 1. Overview

This spec defines implementation contracts for the work identified in the April 2026 ingestion/categorization incident analysis. The work has two independent tracks:

- **Categorization track** — fixes semantic granularity defects that corrupt financial profiles. Delivered measurement-first: ship the enriched LLM prompt with `transaction_kind`, measure accuracy against a labeled golden set, then decide whether rule-based pre-passes are needed.
- **Parsing track** — replaces brittle heuristic format detection with an AI-assisted schema-detection path, adds a post-parse validation layer, and handles encoding variations.

Stories can be delivered in parallel across tracks. Within the categorization track, stories are ordered for measurement-first delivery.

## 2. Schema Changes

### 2.1 Transactions table

Add one column:

```sql
ALTER TABLE transactions
  ADD COLUMN transaction_kind VARCHAR(16) NOT NULL
  DEFAULT 'spending'
  CHECK (transaction_kind IN ('spending','income','savings','transfer'));
```

Rationale: ADR-0001. Default of `spending` is safe at migration time because greenfield (no existing rows). The default is *not* retained as a long-term fallback — the categorization pipeline always writes an explicit value.

### 2.2 Categories

Add `savings`, `transfers_p2p`, and `charity` to `VALID_CATEGORIES` (in [backend/app/agents/categorization/mcc_mapping.py](../../backend/app/agents/categorization/mcc_mapping.py)):

```python
VALID_CATEGORIES: frozenset[str] = frozenset({
    "groceries", "restaurants", "transport", "entertainment", "utilities",
    "healthcare", "shopping", "travel", "education", "finance",
    "subscriptions", "fuel", "atm_cash", "government",
    "transfers",          # inter-account movements (kept, but narrower)
    "transfers_p2p",      # NEW: outbound payments to named individuals
    "savings",            # NEW: capital retention to deposit/investment accounts
    "charity",            # NEW: donations to charitable/humanitarian/military funds
    "other", "uncategorized",
})
```

Also add to `MCC_TO_CATEGORY`:

```python
8398: "charity",   # Charitable and Social Service Organizations
4215: "shopping",  # Courier Services (Nova Poshta, Meest, Justin, etc.)
```

Semantic boundaries:

| Category | When to use | Typical `transaction_kind` |
|---|---|---|
| `savings` | Outflow to a deposit, investment, or savings account owned by the user | `savings` |
| `transfers` | Inter-account movement between user's own current accounts; currency conversion | `transfer` |
| `transfers_p2p` | Outbound payment to a named individual (includes family, friends, rent split) | `spending` |
| `charity` | Donation to a charitable, humanitarian, or military fund (via any MCC) | `spending` |
| `finance` | Fees, interest paid, bank charges, consumer-credit payments | `spending` |

Note: In the Ukrainian context, military-fund donations (United24, Повернись живим, Армія SOS, Сергій Притула Foundation) commonly arrive under MCC 4829 (Wire Transfer / Money Order) rather than 8398. The LLM pass handles these via description — MCC 8398 is the only deterministic-mapping case.

### 2.3 Kind × Category compatibility matrix

Validation rule enforced at persistence boundary:

| `transaction_kind` | Allowed categories |
|---|---|
| `spending` | All except `savings` |
| `income` | `other`, `uncategorized` (income is not category-classified in this scope) |
| `savings` | `savings` only |
| `transfer` | `transfers` only |

Violations raise `ValueError("kind/category mismatch: …")` at the repository layer; the categorization node either retries or emits `(category=uncategorized, kind=<signed-amount-default>, confidence=0.0)`.

### 2.4 bank_format_registry table

New table (Alembic migration):

```sql
CREATE TABLE bank_format_registry (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  header_fingerprint CHAR(64) NOT NULL UNIQUE,  -- SHA-256 of normalized header row
  detected_mapping JSONB NOT NULL,              -- LLM-produced column mapping
  override_mapping JSONB,                       -- operator-edited override, takes precedence
  detection_confidence REAL,                    -- 0.0–1.0 from LLM
  detected_bank_hint VARCHAR(64),               -- LLM best guess, display only
  sample_header TEXT NOT NULL,                  -- raw header for operator inspection
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_used_at TIMESTAMPTZ,
  use_count INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX ix_bank_format_registry_fingerprint ON bank_format_registry(header_fingerprint);
```

`detected_mapping` / `override_mapping` shape:

```json
{
  "date_column": "Дата операції",
  "date_format": "%d.%m.%Y %H:%M:%S",
  "amount_column": "Сума",
  "amount_sign_convention": "positive_is_income" | "negative_is_outflow",
  "description_column": "Опис операції",
  "currency_column": "Валюта",
  "mcc_column": "MCC",
  "balance_column": null,
  "delimiter": ";",
  "encoding_hint": "utf-8"
}
```

### 2.5 uncategorized_review_queue table

New table for the low-confidence review queue:

```sql
CREATE TABLE uncategorized_review_queue (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  transaction_id UUID NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
  categorization_confidence REAL NOT NULL,
  suggested_category VARCHAR(32),
  suggested_kind VARCHAR(16),
  status VARCHAR(16) NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending','resolved','dismissed')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  resolved_at TIMESTAMPTZ,
  resolved_category VARCHAR(32),
  resolved_kind VARCHAR(16)
);

CREATE INDEX ix_uncat_queue_user_status ON uncategorized_review_queue(user_id, status);
```

## 3. Categorization Pipeline Contract

### 3.1 Pipeline stages

```
Transaction batch
  ↓
Stage A: MCC pass (deterministic)
  ↓ (unmatched)
Stage B: Description-pattern pre-pass (CONDITIONAL — see §3.5)
  ↓ (unmatched)
Stage C: LLM batch pass (enriched prompt)
  ↓
Stage D: Confidence-tier routing
  ├── conf ≥ 0.85 → auto-apply
  ├── 0.6 ≤ conf < 0.85 → auto-apply + soft-flag
  └── conf < 0.6 → uncategorized_review_queue insert, transaction.category = "uncategorized"
```

### 3.2 MCC pass (Stage A)

Unchanged behavior; outputs include `transaction_kind` derived from the MCC entry:

- MCC 4829 (wire transfer / money order) — emits `(category=uncategorized, kind=null, confidence=0.0)` to force Stage C analysis (it's semantically ambiguous by MCC alone).
- All other MCC mappings emit `kind = spending` with `confidence = 0.95` (MCC is deterministic for merchant category; kind is inferred from MCC class).

### 3.3 LLM pass (Stage C) — prompt contract

**Inputs per transaction:**
- `id` (UUID, for response matching)
- `description` (string, raw)
- `amount_uah` (decimal, **signed** — negative for outflow, positive for inflow)
- `mcc` (integer or null)
- `direction` (`debit` or `credit`, derived from sign — redundant but reduces LLM reasoning load)

**Prompt structure:**

```
You are a financial transaction categorizer for Ukrainian bank statements.

Each transaction has TWO axes:

1. category — merchant/activity classification, one of:
   groceries, restaurants, transport, entertainment, utilities, healthcare,
   shopping, travel, education, finance, subscriptions, fuel, atm_cash,
   government, transfers, transfers_p2p, savings, other

2. transaction_kind — cash-flow classification, one of:
   - spending: consumption outflow (groceries, rent, restaurants)
   - income: inflow (salary, refund, interest, reimbursement)
   - savings: outflow to the user's own deposit/investment account
   - transfer: movement between the user's own current accounts

Rules:
- transfers_p2p is ALWAYS kind=spending (P2P payments reduce net worth)
- savings category requires kind=savings
- transfers category requires kind=transfer
- Negative amounts with no clear category → "other", kind inferred from context

Few-shot examples:
[3–5 hand-labeled examples covering: self-transfer, deposit top-up,
 P2P to individual, salary inflow, ambiguous case]

Transactions:
1. [id] "description" -1234.56 UAH (debit, MCC: 5411)
2. [id] "description" +10000.00 UAH (credit, MCC: null)
…

Return ONLY a JSON array:
[{"id": "uuid", "category": "groceries", "transaction_kind": "spending",
  "confidence": 0.97}, ...]
```

**Batch size:** 50 transactions per call (unchanged from current).
**Timeout / retry:** unchanged (existing tenacity retry logic).

### 3.4 Fallback behavior

- LLM returns no row for a transaction → `(category="other", kind=<by-sign>, confidence=0.0)`.
- LLM returns invalid category → `(category="other", kind=<returned-or-by-sign>, confidence=0.0)`.
- LLM returns kind that violates matrix §2.3 → `(category="uncategorized", kind=<by-sign>, confidence=0.0)`, transaction enters review queue.
- `<by-sign>` default: negative amount → `spending`; positive amount → `income`.

### 3.5 Description-pattern pre-pass (CONDITIONAL — Story 11.4)

**This stage is gated on Story 11.3 measurement results.** Only implemented if Stage C on the golden set measures < 90% accuracy on either axis. Otherwise this stage is skipped and the work is deferred to tech-debt (TD-NNN).

If implemented, patterns are narrow and deterministic:

- Self-transfer: description matches `/(З|From|To|На) (гривневого|UAH|EUR|USD) рахунк[уа]/i` AND both legs visible in batch → `(category=transfers, kind=transfer, confidence=0.9)`
- Deposit top-up: description matches `/Поповнення (депозиту|вкладу)/i` → `(category=savings, kind=savings, confidence=0.9)`
- P2P (heuristic): description matches Cyrillic full-name pattern `/^[А-ЯЁЇІЄҐ][а-яёїієґ]+ [А-ЯЁЇІЄҐ][а-яёїієґ]+$/` AND amount is debit → `(category=transfers_p2p, kind=spending, confidence=0.85)`

All other patterns route to Stage C.

## 4. Golden-Set Evaluation Harness (Story 11.1)

### 4.1 Fixture format

Location: `backend/tests/fixtures/categorization_golden_set/`

```
golden_set.jsonl         # 50+ labeled transactions, one JSON object per line
source_statements/       # redacted real Monobank CSVs they were sampled from
README.md                # sampling methodology, edge-case coverage checklist
```

`golden_set.jsonl` row shape:

```json
{
  "id": "gs-001",
  "description": "Поповнення депозиту",
  "amount_kopiykas": -19998000,
  "mcc": 4829,
  "expected_category": "savings",
  "expected_kind": "savings",
  "edge_case_tag": "deposit_top_up",
  "notes": "Large outbound transfer with explicit 'deposit' marker"
}
```

### 4.2 Edge case coverage checklist

- Self-transfer between own UAH/EUR/USD accounts (≥ 3 examples)
- Deposit top-up / withdrawal (≥ 3)
- P2P to named individual (≥ 3)
- Salary inflow (≥ 2)
- Refund / reimbursement (≥ 2)
- Standard grocery/restaurant/transport (≥ 10 spread across categories)
- MCC 4829 ambiguous cases (≥ 5)
- Large outliers (> 50k UAH) in mixed categories (≥ 3)
- Mojibake descriptions (≥ 2) — tests graceful degradation
- Edge currencies (non-UAH) (≥ 2)

Minimum: 50 transactions. Target: 75–100 once fixture is established.

### 4.3 Harness

`backend/tests/agents/categorization/test_golden_set.py`:

- Loads `golden_set.jsonl`.
- Runs the full categorization pipeline (Stages A → C) against the batch.
- Computes per-axis accuracy: `category_accuracy = correct_category / total`, `kind_accuracy = correct_kind / total`, plus joint accuracy (`both correct / total`).
- Emits a JSON report to `backend/tests/fixtures/categorization_golden_set/runs/<timestamp>.json`.
- Pytest assertion: `kind_accuracy >= 0.90 AND category_accuracy >= 0.90`. Failing either fails CI.

### 4.4 Success criterion (Story 11.3 gate)

After Story 11.3 (enriched prompt) lands, run the harness. If **both axes** score ≥ 90% on the golden set: Story 11.4 (pre-pass rules) is deferred to tech-debt. If either axis is < 90%: Story 11.4 proceeds with rules scoped to the specific failure patterns identified.

## 5. Parsing Validation Contract (Story 11.5)

### 5.1 Validation rules

After any parser returns rows and before transactions are persisted:

| Rule | Fail condition | Action |
|---|---|---|
| Date plausibility | date outside `[today - 5y, today + 1d]` | row rejected, reason="date_out_of_range" |
| Amount presence | amount is null or 0 | row rejected, reason="zero_or_null_amount" |
| Amount type | amount is not numeric after cleanup | row rejected, reason="non_numeric_amount" |
| Sign convention | parsed sign disagrees with column's `amount_sign_convention` | row flagged, not rejected; warning emitted |
| Description presence | description is null/empty AND merchant/mcc also null | row rejected, reason="no_identifying_info" |
| Duplicate rate | > 20% of rows identical (description + amount + date) | parser output rejected wholesale, reason="suspicious_duplicate_rate" |

### 5.2 Partial-import response shape

The ingestion API surfaces validation outcomes to the frontend:

```json
{
  "upload_id": "uuid",
  "imported_transaction_count": 147,
  "rejected_rows": [
    {
      "row_number": 23,
      "reason": "date_out_of_range",
      "raw_row": {"...": "..."}
    }
  ],
  "warnings": [
    {"row_number": 42, "reason": "sign_convention_mismatch"}
  ],
  "mojibake_detected": false,
  "schema_detection_source": "cached_fingerprint" | "llm_detected" | "known_bank_parser" | "generic_fallback"
}
```

UX decision (confirmed): partial import proceeds; rejected rows are surfaced in the upload completion UI (existing Story 2.8 component, extended with a "couldn't process N rows" expandable section).

## 6. AI-Assisted Schema Detection (Story 11.7)

See ADR-0002 for rationale. Implementation:

### 6.1 Fingerprint

```python
def header_fingerprint(header_row: list[str]) -> str:
    normalized = [
        unicodedata.normalize("NFKC", col).strip().lower()
        for col in header_row
    ]
    canonical = "|".join(normalized)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
```

### 6.2 Detection prompt

Inputs: header row, up to 5 sample data rows, detected encoding.

Prompt asks for the JSON mapping shape in §2.4 plus a `confidence` (0.0–1.0) and `bank_hint` (best-guess bank name for display).

### 6.3 Application

- Fingerprint → `bank_format_registry` lookup.
- If hit AND `override_mapping` exists → use override.
- If hit AND only `detected_mapping` → use detected_mapping, increment `use_count`.
- If miss → call LLM, persist row, use returned mapping.
- After parse: if validation layer rejects > 30% of rows → mark detection as suspect (log + operator alert), still return partial import.

### 6.4 Operator override path

No UI in this scope. Overrides are applied via direct DB update (operator runbook §TBD entry added). Full operator UI deferred to future story.

## 7. Encoding Detection (Story 11.6)

Uses `charset-normalizer` (already installable; no heavy deps):

```python
from charset_normalizer import from_bytes

def detect_encoding(raw_bytes: bytes) -> tuple[str, float]:
    result = from_bytes(raw_bytes).best()
    if result is None:
        return ("utf-8", 0.0)
    return (result.encoding, result.chaos)  # chaos ~ inverse of confidence
```

- Detected encoding logged on every upload.
- If decode produces > 5% replacement characters (`U+FFFD`) in `description` fields, emit `mojibake_detected: true` in the partial-import response and tag the upload for observability alerting.
- Fall back to UTF-8 with `errors="replace"` rather than failing the upload.

## 8. Review Queue API (Story 11.8)

### 8.1 API

- `GET /api/v1/transactions/review-queue?status=pending&limit=50&cursor=…` — list entries for the current user
- `POST /api/v1/transactions/review-queue/{id}/resolve` — body: `{category, kind}` — validates against matrix §2.3, updates transaction, sets `status=resolved`
- `POST /api/v1/transactions/review-queue/{id}/dismiss` — body: optional `{reason}` — sets `status=dismissed`, leaves transaction as `uncategorized`

### 8.2 UI (minimal scope for Story 11.8)

A settings-level page at `/settings/review-queue` that lists pending entries with suggested category/kind, transaction context (description, amount, date), and `resolve` / `dismiss` actions. Not surfaced in the Teaching Feed. Link from account settings with a badge count of pending items.

## 9. Observability (Story 11.9)

New structured log events (correlation IDs already present per Epic 6 story 6.4):

| Event | Emitted by | Fields |
|---|---|---|
| `categorization.confidence_tier` | Stage D router | `tier` (auto/soft-flag/queue), `user_id`, `upload_id`, `tx_id`, `confidence` |
| `categorization.kind_mismatch` | Validation layer §2.3 | `user_id`, `tx_id`, `returned_kind`, `returned_category` |
| `parser.schema_detection` | AI schema-detection path | `fingerprint`, `source` (cache/llm/fallback), `confidence`, `latency_ms` |
| `parser.validation_rejected` | Validation layer §5.1 | `upload_id`, `row_number`, `reason` |
| `parser.mojibake_detected` | Encoding pipeline | `upload_id`, `encoding`, `replacement_char_rate` |

Dashboards (Grafana panels in the existing operator dashboard):

- Categorization confidence distribution (histogram; auto-update hourly)
- Golden-set accuracy (pytest-emitted metric; last-run value)
- Unknown-format detection rate (detections per day, cache hit rate)
- Validation rejection rate by reason
- Mojibake rate per upload

Alerts:

- Categorization confidence median < 0.7 for 24h → warning
- Validation rejection rate > 15% of rows for 24h → warning
- AI schema detection failure (fell through to `generic.py`) → info log, no alert (expected edge case)

## 10. Story-to-Spec Cross-Reference

| Story | Covers spec sections |
|---|---|
| 11.1 Golden-set harness | §4 |
| 11.2 Schema changes (kind field + new categories) | §2.1, §2.2, §2.3 |
| 11.3 Enriched LLM prompt | §3.2, §3.3, §3.4 |
| 11.4 Description pre-pass (conditional) | §3.5 |
| 11.5 Post-parse validation | §5 |
| 11.6 Encoding detection | §7 |
| 11.7 AI schema detection + registry | §2.4, §6 |
| 11.8 Review queue + API/UI | §2.5, §3.1 (Stage D), §8 |
| 11.9 Observability signals | §9 |
| 11.10 Deprecate `generic.py` (conditional, future) | N/A — trigger condition only |
| 4.9 Savings Ratio wired to `transaction_kind` | §2.1 consumer |

## 11. Out of Scope

- Split transactions (one transaction → multiple kind events). Revisit if/when a product need emerges.
- Operator UI for bank_format_registry overrides (DB-only for now; full UI deferred).
- Automatic re-categorization of historical data (not needed — greenfield).
- Multi-leg transfer detection (matching outbound and inbound legs of the same self-transfer). The two sides are categorized independently; matching is an insight-layer concern.
- `generic.py` deletion. Sunset path only — deprecation criteria defined, execution is a future story.
