# Story 7.4: Feedback Data Privacy Integration

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want my feedback data (votes, reports, free-text) included in my data export and one-click deletion,
So that I have full control over all data the system stores about me.

## Acceptance Criteria

1. **Given** the `card_feedback` table has FK to `users.id` with `ON DELETE CASCADE` **When** a user triggers one-click data deletion (Story 5.5) **Then** all card_feedback rows for that user are deleted via FK cascade

2. **Given** a user requests their stored data (Story 5.4) **When** the data summary API (`GET /api/v1/users/me/data-summary`) responds **Then** it includes: number of card votes (up count, down count separately), number of issue reports, and any free-text feedback the user has submitted

3. **Given** the data export includes free-text feedback **When** the user views it **Then** they can see exactly what they wrote, which card it was on (card_id), and when (created_at)

4. **Given** `feedback_responses` records may exist (Layer 3 milestone cards, future) **When** deletion or export is triggered **Then** feedback_responses rows are also handled: deletion via FK cascade (FK exists by design), and export includes them if any rows exist (graceful empty list if table/rows absent)

5. **Given** the updated data summary response **When** the frontend "My Data" section renders **Then** it displays the feedback summary (vote counts, issue report count, free-text entries) in both English and Ukrainian

## Tasks / Subtasks

- [x] Task 1: Backend — Extend data summary endpoint (AC: #2, #3, #4)
  - [x] 1.1 In `backend/app/api/v1/data_summary.py`, add new Pydantic models:
    - `FeedbackVoteCounts(BaseModel)` with `up: int`, `down: int` (with `alias_generator=to_camel, populate_by_name=True`)
    - `FreeTextFeedbackEntry(BaseModel)` with `card_id: uuid.UUID`, `free_text: str`, `feedback_source: str`, `created_at: datetime` (with camel config)
    - `FeedbackSummary(BaseModel)` with `vote_counts: FeedbackVoteCounts`, `issue_report_count: int`, `free_text_entries: list[FreeTextFeedbackEntry]` (with camel config)
  - [x] 1.2 Add `from app.models.feedback import CardFeedback` import to `data_summary.py`
  - [x] 1.3 Add feedback queries in `get_data_summary`:
    - Vote counts: `SELECT feedback_source, vote, COUNT(*) FROM card_feedback WHERE user_id=? AND feedback_source='card_vote' GROUP BY vote` — use `sa_select(CardFeedback.vote, func.count()).where(CardFeedback.user_id == user_id, CardFeedback.feedback_source == "card_vote").group_by(CardFeedback.vote)` to get separate up/down counts
    - Issue report count: `SELECT COUNT(*) FROM card_feedback WHERE user_id=? AND feedback_source='issue_report'`
    - Free-text entries: `SELECT card_id, free_text, feedback_source, created_at FROM card_feedback WHERE user_id=? AND free_text IS NOT NULL ORDER BY created_at DESC` (no hard limit — user's own data)
  - [x] 1.4 Extend `DataSummaryResponse` with `feedback_summary: FeedbackSummary` field
  - [x] 1.5 Populate and return `feedback_summary` in the `return DataSummaryResponse(...)` call

- [x] Task 2: Backend — Add defensive explicit deletion of feedback models (AC: #1)
  - [x] 2.1 In `backend/app/services/account_deletion_service.py`, add `from app.models.feedback import CardFeedback, CardInteraction` import
  - [x] 2.2 Add `CardFeedback` and `CardInteraction` to the `child_tables` list in `delete_all_user_data` — place before `Insight` since card_feedback.card_id → insights.id CASCADE means insight deletion could race; explicit deletion ensures order: `[FlaggedImportRow, CardFeedback, CardInteraction, Transaction, Insight, ProcessingJob, FinancialHealthScore, FinancialProfile, UserConsent, Upload]`
  - [x] 2.3 Note: `feedback_responses` table (Layer 3) does NOT exist yet — no explicit deletion needed; DB CASCADE handles it when that table is created with `ON DELETE CASCADE` on `user_id` FK (by design per architecture)

- [x] Task 3: Backend — Tests (AC: #1, #2, #3)
  - [x] 3.1 In `backend/tests/test_data_summary_api.py`, extend `test_returns_correct_shape_with_data`:
    - Create two `CardFeedback` rows: one `feedback_source="card_vote"` with `vote="up"`, one `feedback_source="card_vote"` with `vote="down"` and `free_text="Too complex"`, one `feedback_source="issue_report"` with `issue_category="confusing"`
    - Assert `data["feedbackSummary"]["voteCounts"]["up"] == 1`
    - Assert `data["feedbackSummary"]["voteCounts"]["down"] == 1`
    - Assert `data["feedbackSummary"]["issueReportCount"] == 1`
    - Assert `len(data["feedbackSummary"]["freeTextEntries"]) == 1`
    - Assert `data["feedbackSummary"]["freeTextEntries"][0]["freeText"] == "Too complex"`
    - Assert `data["feedbackSummary"]["freeTextEntries"][0]["feedbackSource"] == "card_vote"`
  - [x] 3.2 Extend `test_empty_state`: assert `data["feedbackSummary"]["voteCounts"]["up"] == 0`, `data["feedbackSummary"]["voteCounts"]["down"] == 0`, `data["feedbackSummary"]["issueReportCount"] == 0`, `data["feedbackSummary"]["freeTextEntries"] == []`
  - [x] 3.3 Extend `test_camel_case_keys`: assert `"feedbackSummary"` in data and `"voteCounts"` in `data["feedbackSummary"]` and `"issueReportCount"` in `data["feedbackSummary"]`
  - [x] 3.4 In `backend/tests/test_account_deletion.py` (or `test_data_privacy.py` if it exists), add a test `test_feedback_deleted_on_account_deletion`: create user with `CardFeedback` row, call `delete_all_user_data`, assert `CardFeedback` rows are gone — verifying explicit deletion in service

- [x] Task 4: Frontend — Extend `DataSummary` type and hook (AC: #2, #3, #5)
  - [x] 4.1 In `frontend/src/features/settings/hooks/use-data-summary.ts`, add interfaces:
    ```typescript
    export interface FeedbackVoteCounts { up: number; down: number; }
    export interface FreeTextFeedbackEntry { cardId: string; freeText: string; feedbackSource: string; createdAt: string; }
    export interface FeedbackSummary { voteCounts: FeedbackVoteCounts; issueReportCount: number; freeTextEntries: FreeTextFeedbackEntry[]; }
    ```
  - [x] 4.2 Add `feedbackSummary: FeedbackSummary` to `DataSummary` interface

- [x] Task 5: Frontend — Extend `MyDataSection.tsx` to display feedback (AC: #5)
  - [x] 5.1 In `frontend/src/features/settings/components/MyDataSection.tsx`, add a feedback section after the consent records section (before the empty state):
    - Conditionally render if `data.feedbackSummary.voteCounts.up > 0 || data.feedbackSummary.voteCounts.down > 0 || data.feedbackSummary.issueReportCount > 0 || data.feedbackSummary.freeTextEntries.length > 0`
    - Display: vote counts (`{t("feedbackVotesUp")}: N`, `{t("feedbackVotesDown")}: N`), issue report count (`{t("feedbackIssueReports")}: N`)
    - If `data.feedbackSummary.freeTextEntries.length > 0`, render a list of free-text entries with `formatDateLong(entry.createdAt, locale)` and `entry.freeText`
  - [x] 5.2 Use `useTranslations("settings.myData")` (already imported) for all new strings

- [x] Task 6: Frontend — i18n message keys (AC: #5)
  - [x] 6.1 Add to `frontend/messages/en.json` under `settings.myData`:
    ```json
    "feedbackData": "Feedback Data",
    "feedbackVotesUp": "Helpful votes",
    "feedbackVotesDown": "Not helpful votes",
    "feedbackIssueReports": "Issue reports",
    "feedbackFreeText": "Your written feedback",
    "feedbackFreeTextEntry": "{date} — {text}"
    ```
  - [x] 6.2 Add Ukrainian equivalents to `frontend/messages/uk.json` under `settings.myData`:
    ```json
    "feedbackData": "Зворотній зв'язок",
    "feedbackVotesUp": "Корисні оцінки",
    "feedbackVotesDown": "Некорисні оцінки",
    "feedbackIssueReports": "Звіти про проблеми",
    "feedbackFreeText": "Ваші текстові відгуки",
    "feedbackFreeTextEntry": "{date} — {text}"
    ```

- [x] Task 7: Frontend — Tests (AC: #5)
  - [x] 7.1 In `frontend/src/features/settings/__tests__/MyDataSection.test.tsx`, extend `mockDataSummary` with:
    ```typescript
    feedbackSummary: {
      voteCounts: { up: 3, down: 1 },
      issueReportCount: 2,
      freeTextEntries: [
        { cardId: "abc-123", freeText: "Too complex", feedbackSource: "card_vote", createdAt: "2026-04-01T10:00:00" }
      ]
    }
    ```
  - [x] 7.2 Add test: feedback summary section renders with vote counts, issue count, and free-text entry visible
  - [x] 7.3 Add test: feedback section is hidden when all feedback counts are zero (empty feedback summary)
  - [x] 7.4 Add test to verify `test_empty_state`-equivalent: `feedbackSummary: { voteCounts: { up: 0, down: 0 }, issueReportCount: 0, freeTextEntries: [] }` renders no feedback section

## Dev Notes

### Critical Context

Story 7.4 is **privacy integration only** — no new DB tables, no new API endpoints, no new Alembic migration. It extends two existing backend artifacts (`data_summary.py` and `account_deletion_service.py`) and one frontend component (`MyDataSection.tsx`).

**The `card_feedback` table already has the required FK cascade:**
```python
# From alembic/versions/q3r4s5t6u7v8_add_card_feedback_table.py
sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
```
AC #1 is already satisfied at the DB level. The task adds explicit deletion to `child_tables` for defensive consistency (same pattern as all other user-owned models in the service).

**`feedback_responses` table (Layer 3) does NOT exist yet.** Ignore any `feedback_responses` queries — they're future work when Story 7.7 is built. The architecture spec says this table will have `ON DELETE CASCADE` on `user_id` FK at creation time.

**No compliance audit trail changes needed.** Per Stories 7.1, 7.2, 7.3 precedent: feedback endpoints are NOT in `AUDIT_PATH_RESOURCE_MAP` — feedback is behavioral/user-generated data, not GDPR-regulated financial data access.

### Backend: Data Summary Query Pattern

The existing `data_summary.py` pattern uses a mix of `sa_select(func.count())` for counts and `select(Model)` for full object queries. Follow the same pattern.

For vote counts, use `GROUP BY` to get up/down in a single query:

```python
from sqlalchemy import case

# Get vote counts in one query
vote_result = await session.exec(
    sa_select(
        func.sum(case((CardFeedback.vote == "up", 1), else_=0)).label("up_count"),
        func.sum(case((CardFeedback.vote == "down", 1), else_=0)).label("down_count"),
    ).where(
        CardFeedback.user_id == user_id,
        CardFeedback.feedback_source == "card_vote",
    )
)
vote_row = vote_result.one()
up_votes = vote_row[0] or 0
down_votes = vote_row[1] or 0

# Issue report count
issue_result = await session.exec(
    sa_select(func.count()).select_from(CardFeedback).where(
        CardFeedback.user_id == user_id,
        CardFeedback.feedback_source == "issue_report",
    )
)
issue_count = issue_result.scalar_one()

# Free-text entries (non-null free_text)
ft_result = await session.exec(
    select(CardFeedback)
    .where(
        CardFeedback.user_id == user_id,
        CardFeedback.free_text.is_not(None),
    )
    .order_by(CardFeedback.created_at.desc())
)
free_text_rows = ft_result.all()
free_text_entries = [
    FreeTextFeedbackEntry(
        card_id=row.card_id,
        free_text=row.free_text,
        feedback_source=row.feedback_source,
        created_at=row.created_at,
    )
    for row in free_text_rows
]
```

**Important:** SQLAlchemy `case` is imported as `from sqlalchemy import case` (already available in the file's context via `from sqlalchemy import func`). Add to the existing `from sqlalchemy import func` line: `from sqlalchemy import func, case`.

### Backend: Explicit Deletion Order Matters

The `child_tables` list must delete `CardFeedback` BEFORE `Insight` because `card_feedback.card_id → insights.id ON DELETE CASCADE`. If `Insight` rows are deleted first, the DB cascade would auto-delete `CardFeedback` rows — so the explicit delete is a no-op in that case — but deleting `CardFeedback` first is correct and avoids the implicit cascade behavior:

```python
child_tables = [
    FlaggedImportRow,
    CardFeedback,       # must be before Insight (FK card_id → insights.id)
    CardInteraction,    # must be before Insight (FK card_id → insights.id)
    Transaction,
    Insight,
    ProcessingJob,
    FinancialHealthScore,
    FinancialProfile,
    UserConsent,
    Upload,
]
```

### Backend: Test Setup for CardFeedback

Tests in `test_data_summary_api.py` need an `Insight` row as FK target for `card_feedback.card_id`. Use the existing insight created in `test_returns_correct_shape_with_data`. Capture the `insight.id` before `session.commit()` (SQLAlchemy post-commit expiry pattern from Story 7.1 learnings):

```python
insight = Insight(
    user_id=user_id, upload_id=upload_id, headline="Save more",
    key_metric="50%", why_it_matters="Important", deep_dive="Details",
    category="spending",
)
ds_api_session.add(insight)
await ds_api_session.flush()
insight_id = insight.id  # capture before commit!

ds_api_session.add(CardFeedback(
    user_id=user_id, card_id=insight_id, card_type="spending",
    vote="up", feedback_source="card_vote",
))
```

### Frontend: DataSummary Type Extension

The backend will serialize `feedback_summary` as `feedbackSummary` (camelCase alias). The `FeedbackSummary.vote_counts` → `voteCounts`, `issue_report_count` → `issueReportCount`, `free_text_entries` → `freeTextEntries`. Match exactly in the TypeScript interface.

### Frontend: MyDataSection Conditional Rendering

Only show the feedback section if there is any feedback to display. A user with zero feedback should see no feedback section (preserving the existing clean empty state). Check:
```typescript
const hasFeedback =
  data.feedbackSummary.voteCounts.up > 0 ||
  data.feedbackSummary.voteCounts.down > 0 ||
  data.feedbackSummary.issueReportCount > 0 ||
  data.feedbackSummary.freeTextEntries.length > 0;
```

### Frontend: i18n Pattern

`useTranslations("settings.myData")` is already called at the top of `MyDataSection`. Use the same `t(...)` call for all new keys. No new `useTranslations` call needed.

### Previous Story Intelligence (Stories 7.1–7.3)

1. **Snapshot before commit:** Service functions that read SQLModel objects MUST capture field values BEFORE `session.commit()` — prevents `MissingGreenlet`. Not an issue here since `data_summary.py` reads-only (no commit).

2. **Test isolation:** Always capture `.id`, `.card_id` etc. into local variables BEFORE calling `session.commit()`. Post-commit object attributes expire in SQLAlchemy.

3. **Frontend test mocking:** `vi.mock("next-intl", ...)` is already in `MyDataSection.test.tsx` via `createUseTranslations()`. New keys will be returned as-is by the mock.

4. **Test baseline:** Backend 534 passing, Frontend 426 passing (as of Story 7.3 completion).

5. **No new Alembic migration needed.** All tables referenced (`card_feedback`) already exist.

6. **CardFeedback import:** `from app.models.feedback import CardFeedback, CardInteraction` — `feedback.py` under `models/` contains both models (see Story 7.1 for `CardInteraction`, Story 7.2 for `CardFeedback`).

### Git Intelligence

- Latest commit `8f5b7a0` (Story 7.3): added `submit_issue_report` service function, `IssueReportIn/Out` schemas, `POST /cards/{card_id}/report` endpoint, `ReportIssueForm.tsx`, `use-issue-report.ts`, dropdown-menu shadcn component.
- This story MODIFIES: `data_summary.py` (extend response), `account_deletion_service.py` (extend child_tables), `use-data-summary.ts` (extend DataSummary type), `MyDataSection.tsx` (display feedback section), `en.json`, `uk.json`, `test_data_summary_api.py`, `MyDataSection.test.tsx`.
- No new files (except possibly a new test if `test_account_deletion.py` doesn't exist — check first).

### Project Structure Notes

```
backend/
├── app/
│   ├── api/v1/
│   │   └── data_summary.py          ← MODIFIED: new Pydantic models + feedback queries + extend response
│   └── services/
│       └── account_deletion_service.py  ← MODIFIED: add CardFeedback, CardInteraction to child_tables
└── tests/
    └── test_data_summary_api.py     ← MODIFIED: extend existing tests to assert feedbackSummary fields

frontend/src/
├── features/settings/
│   ├── hooks/
│   │   └── use-data-summary.ts      ← MODIFIED: extend DataSummary with feedbackSummary field
│   ├── components/
│   │   └── MyDataSection.tsx        ← MODIFIED: render feedback section
│   └── __tests__/
│       └── MyDataSection.test.tsx   ← MODIFIED: extend mockDataSummary + add feedback tests
└── messages/
    ├── en.json                      ← MODIFIED: add settings.myData.feedback* keys
    └── uk.json                      ← MODIFIED: add settings.myData.feedback* keys
```

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 7.4] — acceptance criteria, user story, endpoint contract
- [Source: _bmad-output/planning-artifacts/prd.md#Data Handling & Retention] — "right to erasure: complete deletion covering…user feedback data (votes, reason selections, free-text responses, issue reports)"; FR49 definition
- [Source: _bmad-output/planning-artifacts/architecture.md#Feedback Data Model] — card_feedback schema, free_text (nullable, max 500 chars), FK cascade definition, feedback_responses future table
- [Source: backend/app/api/v1/data_summary.py] — complete current endpoint; DataSummaryResponse schema; Pydantic model pattern with to_camel alias
- [Source: backend/app/services/account_deletion_service.py] — child_tables list pattern, explicit deletion approach
- [Source: backend/app/models/feedback.py] — CardFeedback and CardInteraction models, field names
- [Source: backend/alembic/versions/q3r4s5t6u7v8_add_card_feedback_table.py] — confirms `ON DELETE CASCADE` on user_id FK
- [Source: backend/tests/test_data_summary_api.py] — test fixture pattern (`ds_api_engine`, `ds_api_session`, `ds_client`), auth override pattern
- [Source: frontend/src/features/settings/hooks/use-data-summary.ts] — DataSummary interface, useQuery pattern
- [Source: frontend/src/features/settings/components/MyDataSection.tsx] — rendering pattern, useTranslations usage, conditional sections
- [Source: frontend/src/features/settings/__tests__/MyDataSection.test.tsx] — test pattern, mockDataSummary shape, createUseTranslations mock
- [Source: _bmad-output/implementation-artifacts/7-3-issue-reporting-on-teaching-feed-cards.md] — service pattern learnings, test mocking patterns, test baselines

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (1M context)

### Debug Log References

- Initial backend test `test_returns_correct_shape_with_data` failed with `IntegrityError: UNIQUE constraint failed: card_feedback.user_id, card_feedback.card_id, card_feedback.feedback_source` — the unique constraint forbids two `card_vote` rows for the same (user, card). Fixed by creating a second `Insight` and placing the down-vote + free-text row on that card; updated the `insightCount` assertion from 1 to 2.
- `test_feedback_deleted_on_account_deletion` initially failed with `FOREIGN KEY constraint failed` on Insight insert — SQLite enforces FK at flush and Upload wasn't yet flushed. Fixed by adding `await del_api_session.flush()` after adding Upload before adding the Insight.

### Completion Notes List

- Backend `GET /api/v1/users/me/data-summary` now returns a `feedbackSummary` field with `voteCounts.up/down`, `issueReportCount`, and `freeTextEntries` (card_id, free_text, feedback_source, created_at). Queries use a single `sa_select` with `case` for the vote counts, a `COUNT(*)` for issue reports, and a `select(CardFeedback).where(free_text IS NOT NULL)` ordered descending for free-text entries. Pydantic models use `alias_generator=to_camel` so responses are camelCase (verified by `test_camel_case_keys`).
- `account_deletion_service.delete_all_user_data` now explicitly deletes `CardFeedback` and `CardInteraction` before `Insight` in the `child_tables` list, preserving the defensive deletion pattern and avoiding reliance on the `card_id → insights.id` cascade path. AC #1 is already covered at the DB level by the `ON DELETE CASCADE` on `user_id`; the explicit delete matches the pattern used for all other user-owned models.
- `feedback_responses` (Layer 3) is not yet a table — no changes needed; design will use `ON DELETE CASCADE` when it's introduced (Story 7.7).
- Frontend `DataSummary` type extended with `FeedbackVoteCounts`, `FreeTextFeedbackEntry`, and `FeedbackSummary`. `MyDataSection` conditionally renders a "Feedback Data" section (vote counts, issue reports, optional free-text list) only when at least one feedback value is non-zero/non-empty.
- i18n keys added under `settings.myData` in both `en.json` and `uk.json`: `feedbackData`, `feedbackVotesUp`, `feedbackVotesDown`, `feedbackIssueReports`, `feedbackFreeText`, `feedbackFreeTextEntry`.
- Tests: backend 535 passing (baseline 534 + 1 new `test_feedback_deleted_on_account_deletion`); frontend 428 passing (baseline 426 + 2 new `renders feedback summary when feedback exists` and `hides feedback section when all feedback counts are zero`). Ruff clean on modified backend files; ESLint clean on `src/features/settings/`.
- Version bumped `1.9.0` → `1.10.0` (MINOR — new user-facing feedback display in Settings → My Data).

### File List

- backend/app/api/v1/data_summary.py (modified) — added `FeedbackVoteCounts`, `FreeTextFeedbackEntry`, `FeedbackSummary` Pydantic models; extended `DataSummaryResponse`; added feedback queries in `get_data_summary`; imported `case` and `CardFeedback`.
- backend/app/services/account_deletion_service.py (modified) — imported `CardFeedback`, `CardInteraction`; added both to `child_tables` ahead of `Insight`.
- backend/tests/test_data_summary_api.py (modified) — imported `CardFeedback`; extended `test_returns_correct_shape_with_data` with two insights and three feedback rows (up vote, down vote with free_text, issue report); extended `test_empty_state` and `test_camel_case_keys` with feedbackSummary assertions.
- backend/tests/test_account_deletion_api.py (modified) — imported `CardFeedback`, `CardInteraction`; added `test_feedback_deleted_on_account_deletion`.
- frontend/src/features/settings/hooks/use-data-summary.ts (modified) — added `FeedbackVoteCounts`, `FreeTextFeedbackEntry`, `FeedbackSummary` interfaces and `feedbackSummary` on `DataSummary`.
- frontend/src/features/settings/components/MyDataSection.tsx (modified) — added conditionally-rendered feedback section after consents.
- frontend/src/features/settings/__tests__/MyDataSection.test.tsx (modified) — added `feedbackSummary` to `mockDataSummary`; updated empty/retry tests; added two new tests.
- frontend/messages/en.json (modified) — added feedback\* keys under `settings.myData`.
- frontend/messages/uk.json (modified) — added feedback\* keys under `settings.myData` (Ukrainian).
- VERSION (modified) — bumped `1.9.0` → `1.10.0`.

### Change Log

- 2026-04-17 — Implemented Story 7.4: extended `data-summary` endpoint with `feedbackSummary`, added explicit feedback model deletion to account deletion service, extended `MyDataSection` + i18n for feedback display, new backend/frontend tests.
- 2026-04-17 — Version bumped from 1.9.0 to 1.10.0 per story completion (MINOR — new user-facing feedback display).
- 2026-04-17 — Code review fixes applied:
  - (M1 / AC #3) `MyDataSection` now renders `Card {first-8-chars}` alongside date + text so the user can see which card the free-text belongs to; `feedbackFreeTextEntry` message updated in `en.json` / `uk.json`.
  - (M2) Free-text entries query now capped at 100 rows (matches `healthScoreHistory` / `consentRecords` pattern); prevents unbounded responses when users accumulate many feedback entries.
  - (M3 / AC #4) `FeedbackSummary` now exposes `feedback_responses: list[dict[str, Any]] = []` as a stable-contract placeholder; concrete schema lands with Story 7.7 when the `feedback_responses` table is introduced. Frontend `FeedbackSummary` and tests updated to match.
  - (L1) Clarified the `account_deletion_service.child_tables` comment — the explicit BEFORE-Insight ordering is a defensive readability choice, not something the cascade requires.
  - (L4) Fixed archaic Ukrainian spelling `зворотній` → `зворотний` in `uk.json`.
  - (L3) Removed brittle `getByText("2")` assertion; replaced with a targeted regex on the free-text entry.

### Code Review (AI)

**Reviewed:** 2026-04-17 by claude-opus-4-7 (1M context)

**Outcome:** 3 Medium + 5 Low findings. All Medium findings fixed in-story. 3 Lows fixed opportunistically (L1 comment, L3 test brittleness, L4 Ukrainian spelling). 2 Lows promoted to tech-debt register. 1 Low withdrawn.

**Deferred findings → tech-debt register:**

- L2 → [TD-021](../../docs/tech-debt.md). `FreeTextFeedbackEntry.feedbackSource` is returned by the API but never rendered in `MyDataSection`; dead field on the wire.
- (review-surfaced) → [TD-022](../../docs/tech-debt.md). `CardFeedback.free_text` has no `max_length=500` on the SQLModel despite the architecture spec; discovered while adding the query `.limit(100)` cap for M2.

**Withdrawn:**

- L5: Task 3.4 path drift (`test_account_deletion.py` vs `test_account_deletion_api.py`) — the task text even called out "or `test_data_privacy.py` if it exists", so the dev's pick was correct. Not worth tracking.
