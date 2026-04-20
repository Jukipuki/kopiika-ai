# Story 11.2: `transaction_kind` Field + Expanded Category Taxonomy

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As the **system**,
I want `transaction_kind` stored as a first-class field on every transaction, alongside an expanded category taxonomy,
So that downstream consumers (health score, spending breakdowns, pattern detection) can filter by cash-flow semantics without re-deriving them from ad-hoc rules.

## Acceptance Criteria

1. **Given** the Alembic migration for Epic 11 **When** it runs **Then** the `transactions` table gains `transaction_kind VARCHAR(16) NOT NULL DEFAULT 'spending' CHECK (transaction_kind IN ('spending','income','savings','transfer'))` per tech spec §2.1

2. **Given** the categorization module at `backend/app/agents/categorization/mcc_mapping.py` **When** `VALID_CATEGORIES` is checked **Then** it already includes `savings`, `transfers_p2p`, and `charity` (done in Story 11.1 review pass); **AND** `MCC_TO_CATEGORY` gains `8398: "charity"` (Charitable and Social Service Organizations) and `4215: "shopping"` (Courier Services), and `4829` is **removed** so it falls through to the LLM pass — per tech spec §2.2

3. **Given** a transaction is being persisted with a `(transaction_kind, category)` pair that violates the compatibility matrix in tech spec §2.3 **When** the persistence layer validates it **Then** it logs a `kind_category_mismatch_fallback` warning and overrides the row to `(category='uncategorized', kind=<by-sign>, confidence=0.0)`, marking the row `is_flagged_for_review=True` with `uncategorized_reason='kind_category_mismatch'` so triage is discoverable (deviation from the original spec wording "raises `ValueError`" — see Dev Notes for rationale; fallback is safer than aborting the whole upload)

4. **Given** the MCC-pass stage encounters MCC 4829 (Wire Transfer / Money Order) **When** it runs **Then** MCC 4829 is not in `MCC_TO_CATEGORY` so `get_mcc_category(4829)` returns `None`, routing the transaction to the LLM pass — it does NOT default to `finance` or `transfers`

5. **Given** any MCC with a deterministic mapping (not 4829) **When** the MCC pass runs **Then** the categorized result includes `transaction_kind='spending'` with `confidence_score=0.95`

## Tasks / Subtasks

- [x] Task 1: Alembic migration — add `transaction_kind` column (AC: #1)
  - [x] 1.1 Create `backend/alembic/versions/w9x0y1z2a3b4_add_transaction_kind_to_transactions.py` with `down_revision = "v8w9x0y1z2a3"`. `upgrade()` calls `op.add_column("transactions", sa.Column("transaction_kind", sa.String(16), nullable=False, server_default="spending"))` then `op.create_check_constraint("ck_transactions_transaction_kind", "transactions", "transaction_kind IN ('spending','income','savings','transfer')")`. `downgrade()` drops constraint then column.
  - [x] 1.2 Update `backend/app/models/transaction.py`: add `transaction_kind: str = Field(default="spending", max_length=16)` after `uncategorized_reason`. No `Optional` — the field always has a value (default or pipeline-written).

- [x] Task 2: Expand `MCC_TO_CATEGORY` (AC: #2, #4)
  - [x] 2.1 In `backend/app/agents/categorization/mcc_mapping.py`: **remove** `4829: "transfers"` from `MCC_TO_CATEGORY`. MCC 4829 (Wire Transfer / Money Order) is semantically ambiguous — the LLM must resolve it. Removing it causes `get_mcc_category(4829)` to return `None`, naturally routing 4829 transactions to the LLM pass.
  - [x] 2.2 Add `8398: "charity"` under a new `# Charity / Social` section in `MCC_TO_CATEGORY`. Comment: `# Charitable and Social Service Organizations`.
  - [x] 2.3 Add `4215: "shopping"` under the existing `# Shopping` section or a new `# Courier / Delivery` section. Comment: `# Courier Services (Nova Poshta, Meest, Justin, etc.)`.
  - [x] 2.4 Verify `VALID_CATEGORIES` already contains `savings`, `transfers_p2p`, `charity` (confirmed in Story 11.1 review pass — no change needed).

- [x] Task 3: MCC pass emits `transaction_kind` (AC: #5)
  - [x] 3.1 In `backend/app/agents/categorization/node.py`, in `categorization_node()`, update the MCC pass result dict to include `"transaction_kind": "spending"`. The full MCC-categorized dict becomes: `{"transaction_id": txn["id"], "category": category, "confidence_score": 0.95, "transaction_kind": "spending", "flagged": False, "uncategorized_reason": None}`. Note: confidence was `1.0` before; change to `0.95` per tech spec §3.2. (Both values are reasonable — `0.95` matches the spec explicitly.)

- [x] Task 4: Sign-based `transaction_kind` default for LLM pass (pre-Story-11.3 bridge) (AC: #3)
  - [x] 4.1 Add a module-level helper `_kind_by_sign(amount: int) -> str` to `node.py`: returns `"income"` if `amount > 0`, else `"spending"`. This is the `<by-sign>` default referenced throughout tech spec §3.4.
  - [x] 4.2 In `_parse_llm_response()`, after resolving `category`, add: `raw_kind = r.get("transaction_kind")` (will be `None` until Story 11.3 enriches the prompt). Do NOT apply kind/category validation in the parser — that happens at persistence time.
  - [x] 4.3 In `_parse_llm_response()`, pass `transactions` dicts (which include `amount`) through the helper: for the fallback row (transaction not in LLM response) and for all rows, resolve `transaction_kind = raw_kind if raw_kind in ("spending","income","savings","transfer") else _kind_by_sign(txn["amount"])`. Add `"transaction_kind": transaction_kind` to every result dict.
  - [x] 4.4 For the `parse_failure` fallback path (exception in `_parse_llm_response`), also add `"transaction_kind": _kind_by_sign(txn["amount"])` to each fallback dict.

- [x] Task 5: Kind/category compatibility validation at persistence (AC: #3)
  - [x] 5.1 Add a module-level dict `KIND_CATEGORY_RULES: dict[str, frozenset[str]]` to `node.py` (or new `validation.py`) per tech spec §2.3:
    ```python
    KIND_CATEGORY_RULES: dict[str, frozenset[str]] = {
        "spending":  VALID_CATEGORIES - frozenset({"savings"}),
        "income":    frozenset({"other", "uncategorized"}),
        "savings":   frozenset({"savings"}),
        "transfer":  frozenset({"transfers"}),
    }
    ```
  - [x] 5.2 Add helper `validate_kind_category(kind: str, category: str) -> bool` that returns `True` if the pair is valid. Returns `False` (does not raise) — the **raise** happens at the call site in `processing_tasks.py`.
  - [x] 5.3 In `backend/app/tasks/processing_tasks.py`, in the bulk-update loop (both `process_upload` and `resume_upload`), after resolving `cat["category"]` and `cat.get("transaction_kind", "spending")`, call `validate_kind_category`. If invalid: raise `ValueError(f"kind/category mismatch: kind={kind!r} category={category!r}")` — this is caught by the existing `except (SoftTimeLimitExceeded, ValueError, KeyError, Exception)` handler. Actually: re-reading the spec, "the caller must either retry with a valid pair or fall back to `(category='uncategorized', kind=<by-sign>, confidence=0.0)`". Retrying is impractical in a bulk loop; **use the fallback instead**. So: if invalid pair, override to `(category='uncategorized', kind=_kind_by_sign(txn.amount), confidence=0.0)` and log a warning. This is safer than raising and aborting the whole upload. Document this deviation from the AC in Dev Notes below.
  - [x] 5.4 In the bulk-update loop in `processing_tasks.py`, add `txn.transaction_kind = cat.get("transaction_kind", "spending")` alongside the existing `txn.category = cat["category"]` line.

- [x] Task 6: Tests (non-LLM) (AC: #1, #2, #3, #4, #5)
  - [x] 6.1 Add unit tests in `backend/tests/agents/categorization/test_transaction_kind.py` (new file):
    - `test_mcc_pass_emits_transaction_kind_spending` — verify MCC-categorized results include `transaction_kind='spending'`
    - `test_mcc_4829_routes_to_llm_pass` — verify `get_mcc_category(4829)` returns `None`
    - `test_mcc_8398_maps_to_charity` — verify `get_mcc_category(8398) == "charity"`
    - `test_mcc_4215_maps_to_shopping` — verify `get_mcc_category(4215) == "shopping"`
    - `test_validate_kind_category_valid_pairs` — spot-check valid combos
    - `test_validate_kind_category_invalid_pairs` — verify `savings+spending` returns False, `income+groceries` returns False, etc.
    - `test_kind_by_sign` — negative amount → spending, positive → income, zero → spending
  - [x] 6.2 Run `cd backend && python -m pytest tests/agents/categorization/test_transaction_kind.py -v`. All tests must pass.
  - [x] 6.3 Run the existing 34-test `test_categorization.py` suite to confirm no regressions: `cd backend && python -m pytest tests/agents/test_categorization.py -v`.

## Dev Notes

### What Story 11.1 Already Did (Do NOT Redo)

Story 11.1's code-review pass already expanded `VALID_CATEGORIES` in `backend/app/agents/categorization/mcc_mapping.py` to include `savings`, `transfers_p2p`, and `charity`. It also updated the LLM prompt in `categorization_node._build_prompt()` to enumerate these three new categories. **Do not touch these changes.** Only the `MCC_TO_CATEGORY` dict and the `transaction_kind` plumbing are net-new in Story 11.2.

### Deviation from AC #3 — Persistence Fallback vs. Raise

The original AC wording said "raises `ValueError("kind/category mismatch: …")`". If we raise in the bulk-update loop, we abort the entire upload for one bad LLM pair, which is too destructive. Instead, Story 11.2 applies the **fallback** the spec also describes: `(category='uncategorized', kind=<by-sign>, confidence=0.0)`, with `is_flagged_for_review=True` and `uncategorized_reason='kind_category_mismatch'` so the mismatched row is discoverable in the teaching-feed / triage UX rather than landing silently. The `ValueError` semantics are preserved as a `kind_category_mismatch_fallback` log warning for observability. AC #3 has been updated to reflect the as-shipped behavior.

### Transaction Model — `transaction_kind` Field

```python
# In backend/app/models/transaction.py, after uncategorized_reason:
transaction_kind: str = Field(default="spending", max_length=16)
```

Using `str` (not `Optional[str]`) since the DB column is `NOT NULL DEFAULT 'spending'`. The Python default `"spending"` matches the DB default and means existing code that constructs `Transaction(...)` without `transaction_kind` still works during the transition period before Story 11.3 backfills all paths.

### Migration Convention

File: `backend/alembic/versions/w9x0y1z2a3b4_add_transaction_kind_to_transactions.py`

Follows the existing alphanumeric revision chain (`v8w9x0y1z2a3` → `w9x0y1z2a3b4`).

```python
revision: str = "w9x0y1z2a3b4"
down_revision: str = "v8w9x0y1z2a3"
```

The DB migration note says "greenfield (no existing rows)" — meaning this is a new project without production data, so `DEFAULT 'spending'` is purely for schema validity. Do not write a data backfill.

```python
def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column(
            "transaction_kind",
            sa.String(16),
            nullable=False,
            server_default=sa.text("'spending'"),
        ),
    )
    op.create_check_constraint(
        "ck_transactions_transaction_kind",
        "transactions",
        "transaction_kind IN ('spending','income','savings','transfer')",
    )

def downgrade() -> None:
    op.drop_constraint("ck_transactions_transaction_kind", "transactions", type_="check")
    op.drop_column("transactions", "transaction_kind")
```

### MCC 4829 — Why Removed vs. Special-Cased

The current code has `4829: "transfers"` which silently buckets all wire transfers / Monobank jar payments / military-fund donations as `transfers`. This is wrong (charity donations are `charity`+`spending`; P2P jar payments could be `transfers_p2p`+`spending`). 

The fix is to **remove 4829 entirely** from `MCC_TO_CATEGORY`. This makes `get_mcc_category(4829)` return `None`, routing 4829 transactions to the LLM pass (Stage C) for description-aware classification. This is simpler than a special sentinel value and naturally satisfies AC #4.

Note: this also means all existing golden-set rows tagged `mcc_4829_ambiguous` will go through the LLM path, which is exactly what the harness measures.

### `_parse_llm_response` — Backward Compatibility with Story 11.3

Story 11.3 will enrich the LLM prompt to emit `transaction_kind` per result. Until then, LLM responses do not include `transaction_kind`, so `.get("transaction_kind")` returns `None`. The `_kind_by_sign(amount)` fallback handles this gracefully. When Story 11.3 lands, it will add `transaction_kind` to LLM responses and the `.get("transaction_kind")` call will start using the LLM-returned value — no further change to this parsing path is needed.

### Kind × Category Compatibility Matrix (tech spec §2.3)

| `transaction_kind` | Allowed categories |
|---|---|
| `spending` | All categories except `savings` |
| `income` | `other`, `uncategorized` only |
| `savings` | `savings` only |
| `transfer` | `transfers` only |

Violations in the LLM pass (before Story 11.3) are extremely unlikely since the current prompt doesn't emit `transaction_kind` (it will always be sign-derived). Once Story 11.3 adds `transaction_kind` to LLM responses, violations may surface for ambiguous transactions — the fallback handles them silently.

### Downstream Consumers — No Breaking Changes in Story 11.2

No API endpoints return `transaction_kind` yet. `processing_tasks.py` persists it, but nothing reads it back. Story 4.9 (Savings Ratio) and the health score service are the downstream consumers — they are not touched in Story 11.2. The field is additive.

### Categorization Pipeline State — `categorized_transactions` Shape Change

After Story 11.2, each dict in `state["categorized_transactions"]` gains `"transaction_kind": str`. The `FinancialPipelineState` TypedDict comment says `list of {transaction_id, category, confidence_score, flagged, uncategorized_reason}` — update this comment to include `transaction_kind`. No TypedDict structural change is needed (it's a `list[dict]`).

### Existing Test `test_categorization.py` — Integration With Changes

The 34-test `test_categorization.py` file mocks LLM calls. After Story 11.2, the mock responses will lack `transaction_kind`, which means `_parse_llm_response` will apply the sign-based default. This is correct behavior — existing tests should still pass since they don't assert on `transaction_kind`. If any test **does** assert on the exact shape of `categorized_transactions`, update it to expect `transaction_kind` in the result dict.

### Project Structure Notes

**New files:**
- `backend/alembic/versions/w9x0y1z2a3b4_add_transaction_kind_to_transactions.py`
- `backend/tests/agents/categorization/test_transaction_kind.py`

**Modified files:**
- `backend/app/models/transaction.py` — add `transaction_kind` field
- `backend/app/agents/categorization/mcc_mapping.py` — remove 4829, add 8398 + 4215
- `backend/app/agents/categorization/node.py` — `_kind_by_sign` helper; MCC pass `transaction_kind='spending'`; LLM pass sign-based default; `validate_kind_category`; `KIND_CATEGORY_RULES`
- `backend/app/tasks/processing_tasks.py` — persist `transaction_kind`; kind/category fallback on mismatch

### References

- Tech spec §2.1 (transaction_kind column): [tech-spec-ingestion-categorization.md](../_bmad-output/planning-artifacts/tech-spec-ingestion-categorization.md)
- Tech spec §2.2 (VALID_CATEGORIES + MCC additions): same file
- Tech spec §2.3 (kind × category matrix): same file
- Tech spec §3.2 (MCC pass contract, MCC 4829 behavior): same file
- Tech spec §3.4 (fallback behavior, `<by-sign>` default): same file
- ADR-0001 (transaction_kind first-class field): [docs/](../../docs/) (see parsing-and-categorization-issues.md)
- Story 11.1 (baseline measurement, `xfail` marker): [11-1-golden-set-evaluation-harness-for-categorization.md](./11-1-golden-set-evaluation-harness-for-categorization.md)
- Existing MCC mapping: [backend/app/agents/categorization/mcc_mapping.py](../../backend/app/agents/categorization/mcc_mapping.py)
- Categorization node: [backend/app/agents/categorization/node.py](../../backend/app/agents/categorization/node.py)
- Transaction model: [backend/app/models/transaction.py](../../backend/app/models/transaction.py)
- Processing tasks (persistence): [backend/app/tasks/processing_tasks.py](../../backend/app/tasks/processing_tasks.py)
- Latest migration (chain predecessor): [backend/alembic/versions/v8w9x0y1z2a3_add_card_type_and_subscription_json_to_insights.py](../../backend/alembic/versions/v8w9x0y1z2a3_add_card_type_and_subscription_json_to_insights.py)

## Dev Agent Record

### Agent Model Used

claude-opus-4-7[1m]

### Debug Log References

- 26 new unit tests in `tests/agents/categorization/test_transaction_kind.py` pass.
- 34 existing tests in `tests/agents/test_categorization.py` pass (updated MCC-pass expectations to `confidence_score=0.95`).
- Full backend regression: 678 passed. 3 pre-existing failures in `test_processing_tasks.py` / `test_sse_streaming.py` are unrelated (Story 11.6 in-progress + pre-existing SSE tests); confirmed by running baseline without these changes.

### Completion Notes List

- MCC mapping: removed `4829`, added `8398 → charity` and `4215 → shopping` per AC #2/#4.
- MCC pass now emits `transaction_kind="spending"` with `confidence_score=0.95` per AC #5 / tech spec §3.2.
- `_kind_by_sign()` helper added; LLM parser applies it when the LLM response omits `transaction_kind` (pre-Story-11.3 bridge).
- `KIND_CATEGORY_RULES` + `validate_kind_category()` added to `node.py` per tech spec §2.3.
- Persistence-time validation applies **fallback** (category=`uncategorized`, kind=by-sign, confidence=0.0) rather than raising on mismatch — documented deviation in Dev Notes above. One bad LLM pair must not abort an entire upload.
- Alembic migration `w9x0y1z2a3b4` chains on `v8w9x0y1z2a3`; greenfield project, no backfill.
- `FinancialPipelineState.categorized_transactions` comment updated to list `transaction_kind` in the dict shape.

### File List

**New:**
- `backend/alembic/versions/w9x0y1z2a3b4_add_transaction_kind_to_transactions.py`
- `backend/tests/agents/categorization/test_transaction_kind.py`

**Modified:**
- `backend/app/models/transaction.py`
- `backend/app/agents/categorization/mcc_mapping.py`
- `backend/app/agents/categorization/node.py`
- `backend/app/agents/state.py`
- `backend/app/tasks/processing_tasks.py`
- `backend/tests/agents/test_categorization.py`
- `VERSION`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`

## Change Log

- 2026-04-20: Story 11.2 implemented — `transaction_kind` first-class field, MCC taxonomy expanded (4829 removed, 8398/4215 added), kind/category compatibility validation at persistence with safe fallback.
- 2026-04-20: Version bumped 1.20.0 → 1.21.0 per story completion (MINOR — new user-facing capability via `transaction_kind` field enabling downstream features like Savings Ratio).
- 2026-04-20: Code review pass — H1 fix: persistence fallback now sets `is_flagged_for_review=True` + `uncategorized_reason='kind_category_mismatch'` so mismatched rows surface in triage rather than landing silently. M1: LLM-path result dicts now include `"flagged"` key (shape parity with MCC-path dicts). M3: `_kind_by_sign` → `kind_by_sign` (public helper) since it's imported from `processing_tasks.py`. AC #3 text updated to match as-shipped fallback semantics. New test `test_fallback_pair_is_always_valid` locks the invariant.
