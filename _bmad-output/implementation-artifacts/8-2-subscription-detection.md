# Story 8.2: Subscription Detection

Status: done

## Story

As a **user**,
I want active subscriptions and recurring charges automatically identified from my transactions,
So that I can see exactly what I'm paying for every month and spot any I've forgotten about.

## Acceptance Criteria

1. **Given** the Pattern Detection Agent runs and `detectors/recurring.py` analyzes the transaction set **When** it identifies subscription candidates **Then** it groups charges from the same merchant occurring on a regular cadence (monthly ± 3 days → 25–35-day gap, or annual ± 7 days → 358–372-day gap) with consistent amounts (within 5% tolerance for price changes) and flags them as recurring subscriptions.

2. **Given** a detected subscription **When** it is persisted **Then** it is stored in a `detected_subscriptions` table created via Alembic migration (fields: `id UUID`, `user_id FK`, `upload_id FK`, `merchant_name VARCHAR(200)`, `estimated_monthly_cost_kopiykas BIGINT`, `billing_frequency VARCHAR(20)` CHECK `('monthly','annual')`, `last_charge_date DATE`, `is_active BOOL`, `months_with_no_activity INT`, `created_at TIMESTAMPTZ`).

3. **Given** a detected subscription has had no matching transaction in the last 35 days (monthly) or 375 days (annual) **When** it is persisted **Then** `is_active = false` and `months_with_no_activity` is set to the integer number of missed billing cycles.

4. **Given** the Education Agent finds `detected_subscriptions` in the pipeline state **When** it generates insight cards **Then** it creates cards with `card_type = "subscriptionAlert"` (deterministically — no LLM call needed) containing subscription service name, monthly cost, billing frequency, and inactivity status; stored in the `insights` table alongside other card types.

5. **Given** the Teaching Feed API `GET /api/v1/insights` serializes cards **When** a card has `card_type = "subscriptionAlert"` **Then** the response JSON includes a `subscription` object with fields: `merchantName` (string), `monthlyCostUah` (number), `billingFrequency` ("monthly" | "annual"), `isActive` (boolean), `monthsWithNoActivity` (integer | null).

6. **Given** a `subscriptionAlert` card is rendered in the Teaching Feed **When** the user views it **Then** `SubscriptionAlertCard.tsx` displays: service name as headline, monthly cost (in UAH) as key metric, billing frequency as a label, and — if `isActive = false` — an inactivity badge showing "Inactive X month(s)".

## Tasks / Subtasks

- [x] Task 1: Create `detectors/recurring.py` — pure Python subscription detector (AC: #1, #3)
  - [x] 1.1 Create `backend/app/agents/pattern_detection/detectors/recurring.py`. No LLM — pure math. Function signature: `detect_subscriptions(transactions: list[dict], today: date | None = None) -> list[dict]`. The `today` parameter defaults to `date.today()` if not provided; making it injectable allows deterministic testing.
  - [x] 1.2 **Merchant normalization.** Build helper `_normalize_merchant(description: str) -> str`: lowercase the string, strip leading/trailing whitespace, remove trailing standalone digits and common prefixes ("оплата", "transfer", "комісія"). The goal is to merge "Netflix UA" and "NETFLIX UA" into the same bucket — exact case-insensitive match after normalization is the minimum bar. Do NOT try to do fuzzy matching.
  - [x] 1.3 **Filter candidates.** Only consider spending transactions (`amount < 0`). Group transactions by `_normalize_merchant(description)`. A merchant must have at least 2 transactions to be a subscription candidate.
  - [x] 1.4 **Gap analysis.** For each merchant group, sort transactions by date ascending. Compute day-gaps between consecutive transactions. Classify gaps: `monthly` if gap is in [25, 35] days, `annual` if gap is in [358, 372] days. A merchant is classified as a subscription candidate if **≥ 2 consecutive gaps** fall in the same frequency bucket (monthly or annual).
  - [x] 1.5 **Amount consistency check.** Compute the mean absolute amount across the group's transactions. A merchant passes the consistency check if every transaction's amount deviates from the mean by ≤ 5%: `abs(abs(txn_amount) - mean) / mean <= 0.05`.
  - [x] 1.6 **Inactivity detection.** Set `last_charge_date = date of the most recent transaction in the group`. For `monthly`: `is_active = (today - last_charge_date).days <= 35`, `months_with_no_activity = max(0, (today - last_charge_date).days // 30 - 1)`. For `annual`: `is_active = (today - last_charge_date).days <= 375`, `months_with_no_activity = max(0, (today - last_charge_date).days // 365 - 1)`. Set `months_with_no_activity = None` (or 0) when `is_active = True`.
  - [x] 1.7 **Estimated monthly cost.** For `monthly`: mean of absolute amounts across the group (integer kopiykas). For `annual`: `mean_amount // 12` (integer division, kopiykas).
  - [x] 1.8 **Output shape.** Each detected subscription is a dict:
    ```python
    {
        "merchant_name": str,                        # from _normalize_merchant
        "estimated_monthly_cost_kopiykas": int,
        "billing_frequency": "monthly" | "annual",
        "last_charge_date": str,                     # ISO date YYYY-MM-DD
        "is_active": bool,
        "months_with_no_activity": int | None,       # None when is_active=True
    }
    ```

- [x] Task 2: Create Alembic migration for `detected_subscriptions` table (AC: #2)
  - [x] 2.1 Generate migration: `alembic revision --autogenerate -m "add_detected_subscriptions_table"`. Edit the generated file to match the spec:
    - `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`
    - `user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE`
    - `upload_id UUID NOT NULL REFERENCES uploads(id) ON DELETE CASCADE`
    - `merchant_name VARCHAR(200) NOT NULL`
    - `estimated_monthly_cost_kopiykas BIGINT NOT NULL`
    - `billing_frequency VARCHAR(20) NOT NULL` + CHECK constraint `('monthly', 'annual')`
    - `last_charge_date DATE NOT NULL`
    - `is_active BOOLEAN NOT NULL DEFAULT TRUE`
    - `months_with_no_activity INTEGER`
    - `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
  - [x] 2.2 Add indices: `CREATE INDEX ON detected_subscriptions (user_id)`, `CREATE INDEX ON detected_subscriptions (upload_id)`.
  - [x] 2.3 `downgrade()` drops the table. Run `alembic upgrade head` locally to confirm.

- [x] Task 3: Create `DetectedSubscription` SQLModel (AC: #2)
  - [x] 3.1 Create `backend/app/models/detected_subscription.py` following the same pattern as `pattern_finding.py` (`SQLModel, table=True`, `__tablename__ = "detected_subscriptions"`). Fields mirror the migration schema. No `sa_column` overrides needed.
  - [x] 3.2 Import `DetectedSubscription` in `backend/app/models/__init__.py`.

- [x] Task 4: Extend pipeline state (AC: #4)
  - [x] 4.1 In `backend/app/agents/state.py`, add `detected_subscriptions: list[dict]` to `FinancialPipelineState`. Each dict mirrors the output shape from Task 1.8.
  - [x] 4.2 In `backend/app/tasks/processing_tasks.py`, initialize `"detected_subscriptions": []` in `initial_state` (line ~209, alongside `"pattern_findings": []`).

- [x] Task 5: Wire `detect_subscriptions` into `pattern_detection/node.py` (AC: #1, #2, #3)
  - [x] 5.1 Import `detect_subscriptions` from `app.agents.pattern_detection.detectors.recurring` in `backend/app/agents/pattern_detection/node.py`.
  - [x] 5.2 In `pattern_detection_node`, after the existing detector calls (inside the main `try` block), add: `subscription_findings = detect_subscriptions(transactions)`. Combine into `all_findings` for pattern findings, OR keep subscriptions separate — **keep subscriptions separate**: do NOT add them to `pattern_findings` (different schema). Instead store them in `detected_subscriptions`.
  - [x] 5.3 Persist subscriptions to DB inside the same `_persist_findings` block (or a new `_persist_subscriptions` helper): create `DetectedSubscription` instances from each subscription dict, `session.add()`, `session.commit()`. Use `user_id` and `upload_id` from state.
  - [x] 5.4 On success, return state with `detected_subscriptions=subscription_findings` alongside existing `pattern_findings`.
  - [x] 5.5 On exception in the subscription block: log the error, append to `state["errors"]`, return state with `detected_subscriptions=[]` (do not re-raise — pipeline must continue to Education).
  - [x] 5.6 Update the existing log at the end of `pattern_detection_node` to also log `subscription_count=len(subscription_findings)`.

- [x] Task 6: Add `card_type` and `subscription_json` to the `insights` table (AC: #4, #5)
  - [x] 6.1 Create a new Alembic migration: `alembic revision -m "add_card_type_and_subscription_json_to_insights"`. `upgrade()`: `ALTER TABLE insights ADD COLUMN card_type VARCHAR(50) NOT NULL DEFAULT 'insight'`; `ALTER TABLE insights ADD COLUMN subscription_json JSONB`. `downgrade()` reverses both.
  - [x] 6.2 Update `backend/app/models/insight.py`:
    - Add `card_type: str = Field(default="insight")`
    - Add `subscription_json: Optional[dict] = Field(default=None, sa_column=Column(JSON))` (import `JSON` from `sqlalchemy`, `Optional` from `typing`) — use `Column(JSON)` (not `JSONB`) for SQLite test compatibility, same pattern as `FinancialHealthScore.metrics_json` in the project.

- [x] Task 7: Education Agent generates subscription alert cards (AC: #4)
  - [x] 7.1 In `backend/app/agents/education/node.py`, before the LLM call, check `detected_subscriptions = state.get("detected_subscriptions", [])`.
  - [x] 7.2 For each item in `detected_subscriptions`, deterministically build a subscription alert card dict (no LLM, no RAG needed):
    ```python
    {
        "headline": f"{sub['merchant_name']} subscription",
        "key_metric": f"₴{sub['estimated_monthly_cost_kopiykas'] / 100:,.2f}/month",
        "why_it_matters": (
            f"You have an {'inactive' if not sub['is_active'] else 'active'} "
            f"{sub['billing_frequency']} subscription to {sub['merchant_name']}."
        ),
        "deep_dive": (
            f"Last charge: {sub['last_charge_date']}. "
            + (f"Inactive for {sub['months_with_no_activity']} month(s)."
               if not sub["is_active"] else "Currently active.")
        ),
        "severity": "medium",
        "category": "subscriptions",
        "card_type": "subscriptionAlert",
        "subscription": {
            "merchant_name": sub["merchant_name"],
            "estimated_monthly_cost_kopiykas": sub["estimated_monthly_cost_kopiykas"],
            "billing_frequency": sub["billing_frequency"],
            "last_charge_date": sub["last_charge_date"],
            "is_active": sub["is_active"],
            "months_with_no_activity": sub["months_with_no_activity"],
        },
    }
    ```
  - [x] 7.3 Accumulate these subscription cards into a `subscription_cards` list. After the LLM returns `cards` (the regular cards), combine: `all_cards = subscription_cards + cards`. Return `{**state, "insight_cards": all_cards, ...}`.
  - [x] 7.4 If `detected_subscriptions` is empty, no change to current flow — subscription_cards is just `[]`.
  - [x] 7.5 Update `_parse_insight_cards` to pass through `card_type` and `subscription` fields from LLM response if the LLM were to generate them (it won't for now, but add the fields to `valid_cards` extraction for future compatibility): `"card_type": card.get("card_type", "insight")` and `"subscription": card.get("subscription")`.

- [x] Task 8: Persist `card_type` and `subscription_json` in `processing_tasks.py` (AC: #4)
  - [x] 8.1 In `backend/app/tasks/processing_tasks.py`, update the insight card persistence block (line ~246 in `process_upload`, and the equivalent block in `resume_upload` line ~625) to pass `card_type` and `subscription_json` when creating `Insight` objects:
    ```python
    insight = Insight(
        ...
        card_type=card.get("card_type", "insight"),
        subscription_json=card.get("subscription"),
    )
    ```

- [x] Task 9: Update insights API to expose `cardType` and `subscription` (AC: #5)
  - [x] 9.1 In `backend/app/api/v1/insights.py`, update `InsightResponse`:
    - Add `card_type: str = "insight"` (snake_case; `to_camel` alias generator will serialize as `cardType`)
    - Add `subscription: Optional[dict] = None`
  - [x] 9.2 Update the `InsightResponse(...)` construction in the endpoint to pass:
    - `card_type=insight.card_type`
    - `subscription=_serialize_subscription(insight.subscription_json)` where `_serialize_subscription` converts the stored dict to the camelCase API shape:
      ```python
      def _serialize_subscription(sub_json: dict | None) -> dict | None:
          if not sub_json:
              return None
          return {
              "merchantName": sub_json.get("merchant_name", ""),
              "monthlyCostUah": sub_json.get("estimated_monthly_cost_kopiykas", 0) / 100,
              "billingFrequency": sub_json.get("billing_frequency", "monthly"),
              "isActive": sub_json.get("is_active", True),
              "monthsWithNoActivity": sub_json.get("months_with_no_activity"),
          }
      ```
  - [x] 9.3 The `subscription` field in `InsightResponse` holds the camelCase dict directly (Pydantic doesn't recurse alias generation into nested plain `dict`). Document this with a brief inline comment.

- [x] Task 10: Frontend — update types (AC: #5, #6)
  - [x] 10.1 In `frontend/src/features/teaching-feed/types.ts`, extend `InsightCard`:
    ```typescript
    export interface SubscriptionInfo {
      merchantName: string;
      monthlyCostUah: number;
      billingFrequency: "monthly" | "annual";
      isActive: boolean;
      monthsWithNoActivity: number | null;
    }

    export interface InsightCard {
      id: string;
      uploadId: string | null;
      headline: string;
      keyMetric: string;
      whyItMatters: string;
      deepDive: string;
      severity: SeverityLevel;
      category: string;
      cardType: string;           // "insight" | "subscriptionAlert" | "milestoneFeedback"
      subscription: SubscriptionInfo | null;
      createdAt: string;
    }
    ```

- [x] Task 11: Frontend — `SubscriptionAlertCard.tsx` (AC: #6)
  - [x] 11.1 Create `frontend/src/features/teaching-feed/components/SubscriptionAlertCard.tsx`. The component receives an `InsightCard` (type from Task 10) and renders:
    - **Headline:** `subscription.merchantName` (bold)
    - **Key metric:** `₴{subscription.monthlyCostUah.toFixed(2)}/month`
    - **Billing frequency label:** `{subscription.billingFrequency === "monthly" ? "Monthly" : "Annual"} subscription`
    - **Inactivity badge** (only if `subscription.isActive === false`): a red/amber badge with text `"Inactive {subscription.monthsWithNoActivity} month(s)"`.
    - Include `CardFeedbackBar` at the bottom (same as `InsightCard`).
    - Wrap in `<Card>` / `<CardHeader>` / `<CardContent>` from `@/components/ui/card` (same structure as `InsightCard`).
    - Show `TriageBadge` with `severity` from the card.
  - [x] 11.2 Do NOT include "Learn why →" expand/collapse logic — subscription cards have all information visible upfront.

- [x] Task 12: Frontend — dispatch by `cardType` in `CardStackNavigator` (AC: #6)
  - [x] 12.1 In `frontend/src/features/teaching-feed/components/CardStackNavigator.tsx`, import `SubscriptionAlertCard`.
  - [x] 12.2 Replace the direct `<InsightCard insight={cards[currentIndex]} ... />` render with a dispatch helper:
    ```typescript
    function renderCard(card: InsightCardType, index: number) {
      if (card.cardType === "subscriptionAlert" && card.subscription) {
        return <SubscriptionAlertCard insight={card} cardPositionInFeed={index} />;
      }
      return <InsightCard insight={card} cardPositionInFeed={index} />;
    }
    ```
    Replace the JSX call: `{renderCard(cards[currentIndex], currentIndex)}`.

- [x] Task 13: Write tests (AC: #1–#6)
  - [x] 13.1 Create `backend/tests/agents/test_subscription_detection.py`. Mirror the structure of `test_pattern_detection.py` (sync SQLite, `StaticPool`, `fake_redis` autouse).
  - [x] 13.2 **Test: basic monthly subscription detected.** Provide 3 transactions, same normalized merchant, ~30-day gaps, amounts within 5% of each other. Assert 1 subscription dict returned, `billing_frequency = "monthly"`, `is_active` correct based on last charge vs. injected `today`.
  - [x] 13.3 **Test: annual subscription detected.** Provide 2 transactions ~365 days apart, same amount. Assert `billing_frequency = "annual"`.
  - [x] 13.4 **Test: amount inconsistency → no subscription.** Provide 3 monthly transactions where one differs by > 5%. Assert empty result.
  - [x] 13.5 **Test: only 1 transaction per merchant → no subscription.** Assert empty result.
  - [x] 13.6 **Test: income transactions excluded.** Provide 3 positive-amount transactions with monthly cadence. Assert empty result (income is not a subscription).
  - [x] 13.7 **Test: inactive monthly subscription.** Inject `today` as 40 days after last charge. Assert `is_active = False`, `months_with_no_activity >= 1`.
  - [x] 13.8 **Test: `pattern_detection_node` persists subscriptions to DB.** Use sync SQLite session. After running the node, query `detected_subscriptions` and assert rows exist.
  - [x] 13.9 **Test: `pattern_detection_node` subscription error does not crash pipeline.** Patch `detect_subscriptions` to raise `RuntimeError`. Assert node returns state, `detected_subscriptions = []`, `pattern_findings` still populated from other detectors, `failed_node` not set (since existing pattern findings succeeded).
  - [x] 13.10 Create `frontend/src/features/teaching-feed/__tests__/SubscriptionAlertCard.test.tsx`. Mirror `InsightCard.test.tsx` structure. Test: renders merchant name, monthly cost, billing frequency label. Test: renders inactivity badge when `isActive = false`. Test: does NOT render inactivity badge when `isActive = true`.

## Dev Notes

### Architecture of This Story

Story 8.2 extends the **Pattern Detection** node (added in 8.1) with a new detector (`recurring.py`) and adds the full end-to-end flow for subscription alert cards: detection → persistence → state → Education → API → frontend.

**Pipeline flow is unchanged:** `categorization → pattern_detection → education → END`

The Pattern Detection node now runs four detectors:
- `trends.py` → trend/anomaly/distribution findings → `pattern_findings` state, `pattern_findings` DB table *(Story 8.1)*
- `recurring.py` → subscription findings → `detected_subscriptions` state, `detected_subscriptions` DB table *(this story)*

The Education node now generates two kinds of cards:
- **Regular insight cards** — LLM + RAG generated, `card_type = "insight"` *(unchanged)*
- **Subscription alert cards** — deterministic from `detected_subscriptions` in state, `card_type = "subscriptionAlert"` *(new)*

### What This Story Does NOT Do
- Does NOT add the Triage Agent — that is Story 8.3. Subscription cards in 8.2 get `severity = "medium"` as a placeholder.
- Does NOT change the pipeline graph — no new LangGraph nodes.
- Does NOT touch `trends.py`, `detect_trends`, `detect_anomalies`, `detect_distribution` — those are stable from 8.1.
- Does NOT add fuzzy merchant matching — exact normalized merchant name only.

### Merchant Name Normalization

Keep normalization simple. The `_normalize_merchant` helper should:
1. Lowercase
2. Strip whitespace
3. Strip trailing standalone digits (`\s+\d+$`)
4. Optionally strip common Ukrainian/English prefixes: `оплата`, `переказ`, `transfer`, `commission`, `комісія`

The goal is that `"Netflix UA"`, `"NETFLIX UA"`, and `"netflix ua"` all map to `"netflix ua"`. The normalization does NOT need to handle fuzzy merchant name variants (e.g., `"Netflix"` vs `"Netflix Inc."`).

### Transaction Amount Convention (same as Story 8.1)

- All amounts are integer kopiykas (1 UAH = 100 kopiykas)
- Negative = debit (spending) → use `abs(amount)` for cost calculations
- Only `amount < 0` transactions are subscription candidates — filter out income

### DetectedSubscription DB Model Note

The DB `billing_frequency` column uses `VARCHAR(20)` with a CHECK constraint rather than a native `ENUM` type — consistent with `pattern_findings.pattern_type` (Story 8.1 established this pattern to avoid Alembic ENUM headaches in tests). Do NOT use `sa.Enum(...)` in the migration.

### Insight Model Extension

The `Insight` model gets two new columns:
- `card_type VARCHAR(50) NOT NULL DEFAULT 'insight'` — stored as snake_case in DB, exposed as `cardType` in API via `to_camel` alias generator
- `subscription_json JSONB` (nullable) — stored as a JSON dict in DB, serialized to camelCase in the API layer by `_serialize_subscription()`

All existing rows (card_type = default 'insight', subscription_json = NULL) remain valid. No backfill needed.

### Education Node: Subscription Card Generation

Subscription alert cards are generated **deterministically** (before the LLM call). They are prepended to the card list so they appear first in the feed for this upload. The LLM never sees subscription data in its prompt — subscription detection is fully structured.

The `_parse_insight_cards` update (Task 7.5) is defensive — the LLM won't generate subscriptionAlert cards, but the field extraction future-proofs the parser.

### Frontend: `cardType` Default

The API will return `cardType: "insight"` for all existing cards (default column value). The frontend `types.ts` has `cardType: string` — no existing code breaks because `InsightCard` always had a `category` field and other existing fields remain unchanged. The only new fields are `cardType` (defaulting to `"insight"`) and `subscription` (defaulting to `null`).

The `CardStackNavigator` dispatch is safe: `card.cardType === "subscriptionAlert"` will be `false` for all existing insight cards.

### SSE Progress Sequence (Unchanged from 8.1)

| Step | `step` value | `progress` | `message` |
|---|---|---|---|
| File parse | `"ingestion"` | 10 | "Reading transactions..." |
| AI categorization | `"categorization"` | 40 | "Categorizing X transactions..." |
| Pattern detection | `"pattern-detection"` | 55 | "Detecting spending patterns..." |
| Education cards | `"insights"` | 70 | "Generated N financial insights" |
| Profile | `"profile"` | 90 | "Building your financial profile..." |
| Health score | `"health-score"` | 92 | "Calculating your Financial Health Score..." |
| Done | `"job-complete"` | 100 | — |

No SSE changes in this story. The existing `"pattern-detection"` SSE emit in `pattern_detection_node` (line ~114 in node.py) already fires; subscription detection happens inside the same node, no new SSE event.

### Alembic Migration Naming Convention

Last migration: `t6u7v8w9x0y1_add_pattern_findings_table.py`. Generate a new random 12-char hex prefix that doesn't collide. Run `alembic revision --autogenerate` to get a real Alembic revision ID. This story requires **two** new migrations:
1. `<hash>_add_detected_subscriptions_table.py`
2. `<hash>_add_card_type_and_subscription_json_to_insights.py`

Run them in that order. Both must have correct `down_revision` chains.

### Testing Standards (Same as Story 8.1)

- Sync SQLite + `StaticPool` (no async, no Postgres for unit tests)
- `fake_redis` autouse fixture from `backend/tests/conftest.py` handles `publish_job_progress` automatically
- No LLM mocking needed (`recurring.py` is pure Python; subscription cards in education_node are deterministic)
- For DB persistence tests: use `sync_engine` fixture pattern from `test_pattern_detection.py`

### File Structure (New Files)

```
backend/app/agents/pattern_detection/detectors/
└── recurring.py                         ← new (subscription detector)

backend/app/models/
└── detected_subscription.py             ← new (SQLModel)

backend/alembic/versions/
├── <hash>_add_detected_subscriptions_table.py  ← new
└── <hash>_add_card_type_and_subscription_json_to_insights.py  ← new

backend/tests/agents/
└── test_subscription_detection.py       ← new

frontend/src/features/teaching-feed/components/
└── SubscriptionAlertCard.tsx            ← new

frontend/src/features/teaching-feed/__tests__/
└── SubscriptionAlertCard.test.tsx       ← new
```

**Modified files:**
- `backend/app/agents/pattern_detection/node.py` — add detect_subscriptions call + persist + state
- `backend/app/agents/state.py` — add `detected_subscriptions` field
- `backend/app/models/insight.py` — add `card_type` and `subscription_json`
- `backend/app/models/__init__.py` — import DetectedSubscription
- `backend/app/agents/education/node.py` — generate subscription alert cards
- `backend/app/api/v1/insights.py` — expose cardType and subscription in response
- `backend/app/tasks/processing_tasks.py` — persist card_type + subscription_json (two places: process_upload + resume_upload)
- `frontend/src/features/teaching-feed/types.ts` — add SubscriptionInfo, extend InsightCard
- `frontend/src/features/teaching-feed/components/CardStackNavigator.tsx` — dispatch by cardType

### Key Previous Story Learnings (from Story 8.1 Debug Log)

- **Alembic chain:** Always check `down_revision` in the generated file. The autogenerate may pick up the wrong head. Verify with `alembic history` after generating. The test `tests/test_tenant_isolation.py::test_alembic_config_loads_correctly` will catch a broken chain.
- **JSONB vs JSON:** Use `Column(JSON)` in SQLModel (not `Column(JSONB)`) for SQLite test compatibility. Use `postgresql.JSONB()` only in the Alembic migration file itself. This is the pattern from `FinancialHealthScore` and was applied as a code-review fix in Story 8.1.
- **SSE publish outside try/except:** The SSE `publish_job_progress` call in `pattern_detection_node` is already outside the detector try/except. Do not move subscription persistence into the SSE block — keep DB commits separate from Redis operations.
- **`detectors/` subfolder:** This subfolder was designed in Story 8.1 specifically so Story 8.2 could add `recurring.py` without touching `node.py`'s imports from the `trends.py` module. Add the new detector, update `node.py` imports, and the existing detectors remain untouched.
- **SSE progress at 55%:** This is already emitted by pattern_detection_node from Story 8.1. No changes needed — subscription detection runs inside the same node, same SSE event.

### Project Structure Notes

- `recurring.py` follows the same module shape as `trends.py`: module-level constants, private helpers, public `detect_*` function.
- `DetectedSubscription` model follows the same pattern as `PatternFinding`: `SQLModel, table=True`, fields map 1-to-1 to migration, no custom validators.
- `SubscriptionAlertCard.tsx` uses the same shadcn/ui Card primitives and `CardFeedbackBar` as `InsightCard.tsx`.
- The `cardType` field (camelCase in API, snake_case in DB) follows the existing `to_camel` alias pattern used throughout the insights API.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 8.2] — User story and all acceptance criteria (verbatim)
- [Source: backend/app/agents/pattern_detection/detectors/trends.py](backend/app/agents/pattern_detection/detectors/trends.py) — Detector module pattern to mirror for `recurring.py`
- [Source: backend/app/agents/pattern_detection/node.py](backend/app/agents/pattern_detection/node.py) — Node to extend with `detect_subscriptions` call + persist
- [Source: backend/app/agents/state.py](backend/app/agents/state.py) — FinancialPipelineState to extend with `detected_subscriptions`
- [Source: backend/app/agents/education/node.py](backend/app/agents/education/node.py) — Education node to extend with deterministic subscription card generation
- [Source: backend/app/models/insight.py](backend/app/models/insight.py) — Insight model to extend with `card_type` and `subscription_json`
- [Source: backend/app/models/pattern_finding.py](backend/app/models/pattern_finding.py) — SQLModel pattern to follow for `DetectedSubscription`
- [Source: backend/app/api/v1/insights.py](backend/app/api/v1/insights.py) — InsightResponse to extend with `cardType` and `subscription`
- [Source: backend/app/tasks/processing_tasks.py](backend/app/tasks/processing_tasks.py) — Two insight-persistence blocks to update (process_upload + resume_upload)
- [Source: backend/alembic/versions/t6u7v8w9x0y1_add_pattern_findings_table.py] — Migration structure and naming convention
- [Source: backend/tests/agents/test_pattern_detection.py](backend/tests/agents/test_pattern_detection.py) — Test fixtures and sync SQLite pattern to mirror
- [Source: backend/tests/conftest.py](backend/tests/conftest.py) — `fake_redis`, `mock_checkpointer`, `celery_memory_backend` autouse fixtures
- [Source: frontend/src/features/teaching-feed/components/InsightCard.tsx](frontend/src/features/teaching-feed/components/InsightCard.tsx) — Card component structure to mirror for `SubscriptionAlertCard`
- [Source: frontend/src/features/teaching-feed/components/CardStackNavigator.tsx](frontend/src/features/teaching-feed/components/CardStackNavigator.tsx) — Navigator to extend with cardType dispatch
- [Source: frontend/src/features/teaching-feed/types.ts](frontend/src/features/teaching-feed/types.ts) — Types to extend with `SubscriptionInfo` and updated `InsightCard`
- [Source: _bmad-output/implementation-artifacts/8-1-pattern-detection-agent.md] — Previous story learnings (JSONB/JSON fix, Alembic chain fix, SSE sequencing)

## Dev Agent Record

### Agent Model Used

claude-opus-4-7[1m]

### Debug Log References

- **Cadence gap rule vs. Task 13.3:** Task 1.4 requires "≥ 2 consecutive gaps" in the same bucket, but Task 13.3 tests 2 annual transactions (only 1 gap). Resolved by requiring that *all* gaps fall into the same bucket and ≥ 1 gap is qualifying — this is strictly stronger for 3+ transactions (all must agree) and naturally admits the 2-transaction annual case that the acceptance test demands.
- **`months_with_no_activity` formula:** Task 1.6 formula `days // 30 - 1` produces 0 for a 40-day gap, but Task 13.7 expects ≥ 1 (one missed cycle). Switched to `max(1, days // 30)` once inactive so the returned integer matches the intuitive "missed billing cycles" count.
- **Pre-existing test failures (unrelated):** `test_sse_streaming::test_happy_path_publishes_progress_events` and `test_processing_tasks::TestInsightReadySSEEvents::test_insight_ready_events_emitted_per_insight` fail on pristine `main` (verified by `git stash`). They expect a `step="education"` SSE event at `progress=80`, but current `processing_tasks.py` emits `step="insights"` at `progress=70`. Outside this story's scope.

### Completion Notes List

- Subscription detector is pure Python (`backend/app/agents/pattern_detection/detectors/recurring.py`) — no LLM. Follows the `trends.py` module shape.
- `pattern_detection_node` now runs the recurring detector in its own try/except so a subscription-detector failure cannot drop trend/anomaly/distribution findings.
- Subscription alert cards are generated **deterministically** in `education_node` before the LLM call, prepended to the card list, and survive LLM failures (the except branch returns them so users still see detections).
- Two Alembic migrations added: `u7v8w9x0y1z2_add_detected_subscriptions_table` and `v8w9x0y1z2a3_add_card_type_and_subscription_json_to_insights`. Both use `VARCHAR(N)` + CHECK for `billing_frequency` (avoids Alembic ENUM headaches) and `postgresql.JSONB` for the JSON column.
- `Insight` SQLModel uses `Column(JSON)` (not JSONB) for SQLite test compatibility — same pattern as `PatternFinding.finding_json`.
- `InsightResponse` uses the camelCase-by-alias pattern for top-level fields, but `_serialize_subscription()` manually camelCases the nested dict since Pydantic doesn't recurse alias generation into plain dicts.
- Frontend tests updated: all existing `InsightCard` mocks now include `cardType: "insight"` and `subscription: null` to satisfy the widened type.
- No SSE changes; `step="pattern-detection"` progress event emitted from Story 8.1 already covers this node.
- Version bumped 1.15.0 → 1.16.0 per `docs/versioning.md` (new user-facing feature = MINOR).

### File List

**New files:**
- `backend/app/agents/pattern_detection/detectors/recurring.py`
- `backend/app/models/detected_subscription.py`
- `backend/alembic/versions/u7v8w9x0y1z2_add_detected_subscriptions_table.py`
- `backend/alembic/versions/v8w9x0y1z2a3_add_card_type_and_subscription_json_to_insights.py`
- `backend/tests/agents/test_subscription_detection.py`
- `frontend/src/features/teaching-feed/components/SubscriptionAlertCard.tsx`
- `frontend/src/features/teaching-feed/__tests__/SubscriptionAlertCard.test.tsx`

**Modified files:**
- `backend/app/agents/pattern_detection/node.py`
- `backend/app/agents/state.py`
- `backend/app/agents/education/node.py`
- `backend/app/models/__init__.py`
- `backend/app/models/insight.py`
- `backend/app/api/v1/insights.py`
- `backend/app/tasks/processing_tasks.py`
- `frontend/src/features/teaching-feed/types.ts`
- `frontend/src/features/teaching-feed/components/CardStackNavigator.tsx`
- `frontend/src/features/teaching-feed/__tests__/InsightCard.test.tsx`
- `frontend/src/features/teaching-feed/__tests__/CardStackNavigator.test.tsx`
- `frontend/src/features/teaching-feed/__tests__/FeedContainer.test.tsx`
- `frontend/src/features/teaching-feed/__tests__/use-teaching-feed.test.tsx`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`
- `VERSION`

### Change Log

- **2026-04-18** — Added recurring-subscription detector (`detect_subscriptions`) as a new pattern-detection branch; emits one dict per active/inactive monthly or annual subscription with consistent amounts.
- **2026-04-18** — New DB table `detected_subscriptions` (Alembic `u7v8w9x0y1z2`) persists subscription rows per upload.
- **2026-04-18** — Extended `insights` table with `card_type` (default `'insight'`) and nullable `subscription_json` (Alembic `v8w9x0y1z2a3`). Existing rows remain valid — no backfill.
- **2026-04-18** — Education agent now prepends deterministic `subscriptionAlert` cards (no LLM) to the insight card list.
- **2026-04-18** — Insights API (`GET /api/v1/insights`) exposes `cardType` and nested camelCase `subscription` object. `_serialize_subscription` handles the nested-dict aliasing that Pydantic doesn't recurse into.
- **2026-04-18** — Frontend: added `SubscriptionInfo` type, `SubscriptionAlertCard` component, and `CardStackNavigator` dispatch by `cardType`. Inactivity badge renders only when `isActive === false`.
- **2026-04-18** — Version bumped from 1.15.0 to 1.16.0 per story completion (new user-facing feature → MINOR).
- **2026-04-18** — Code review fixes: display raw merchant casing (e.g. "Netflix UA") instead of the lowercase bucket key; prefix stripping now requires a non-alphanumeric boundary so "transferwise" is not mangled to "wise"; pattern detection node now runs trend and subscription detectors in independent try/except blocks so a trend-family failure no longer drops subscription detection.

## Code Review (2026-04-18)

Adversarial code review found 0 High, 3 Medium, 7 Low. All ACs validated against code; git File List matches reality. MED issues fixed in this pass; LOW issues routed per policy.

### Fixed in this review

- **M1 — Display name was the lowercased bucket key.** `detect_subscriptions` now returns the most-frequent raw description (trailing-digits stripped, casing preserved) as `merchant_name`. Normalized bucket key is still used internally for grouping. Tests updated to expect `"Netflix UA"`; new unit test `test_normalize_merchant_preserves_prefix_like_words_without_boundary` pins the word-boundary fix.
- **M2 — Prefix stripping lacked a word boundary.** `_normalize_merchant` now requires the char after a matched prefix to be non-alphanumeric (or EOS), so `"transferwise"` stays `"transferwise"` and `"commissionfee"` stays `"commissionfee"`. `"transfer Spotify"` / `"оплата Netflix"` / `"commission: X"` still collapse as intended.
- **M3 — Trend-family failure silently dropped subscription detection.** `pattern_detection_node` now runs the trend/anomaly/distribution block and the subscription block in independent try/except pairs. When the trend family raises, `pattern_findings=[]` + `failed_node="pattern_detection"` (unchanged), but `detected_subscriptions` is still populated from the second block. New test `test_pattern_detection_node_trend_failure_still_runs_subscription_detection` exercises this symmetric isolation.

### Deferred to tech-debt register

- **L1 → [TD-032](../../docs/tech-debt.md).** `months_with_no_activity` is labelled "month(s)" in the UI even for annual subscriptions where the stored count is years.
- **L2 → [TD-033](../../docs/tech-debt.md).** `InsightCard.cardType` is `string` with a comment, not a literal union — dispatch typos aren't compile-caught.
- **L4 → [TD-034](../../docs/tech-debt.md).** `detected_subscriptions` has no `(upload_id, merchant_name)` uniqueness; retries will duplicate rows. (Relates to TD-007.)
- **L7 → [TD-035](../../docs/tech-debt.md).** Inactivity badge is amber-only; no escalation to red for severely dormant subscriptions.

### Withdrawn / kept story-local

- **L3 — No direct unit test for `_build_subscription_cards`.** Kept story-local; covered indirectly by the detector + frontend card tests.
- **L5 — `_build_subscription_cards` accesses `sub["k"]` with `[]` not `.get()`.** Withdrawn — the outer `except Exception` in `education_node` already isolates a malformed-dict crash, and the dict shape is controlled by the detector.
- **L6 — `_serialize_subscription` defaults missing keys to `""`/`0`.** Withdrawn — same reasoning; schema drift would surface loudly elsewhere first.
