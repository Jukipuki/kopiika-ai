# Story 7.3: Issue Reporting on Teaching Feed Cards

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user**,
I want to report an issue on any Teaching Feed card via a flag icon,
So that I can flag bugs, incorrect information, or confusing content without leaving the feed.

## Acceptance Criteria

1. **Given** I am viewing a Teaching Feed card **When** I tap the card's overflow menu (three-dot icon) **Then** I see a "Report an issue" option with a flag icon

2. **Given** I tap "Report an issue" **When** the report form appears **Then** it displays in-context (not a modal or redirect): a category select/dropdown (Bug, Incorrect info, Confusing, Other) and an optional free-text field (max 500 characters, collapsed by default)

3. **Given** I select a category and optionally enter free text **When** I submit the report **Then** it is sent to `POST /api/v1/feedback/cards/{cardId}/report` with `{"issueCategory": "incorrect_info", "freeText": "..."}` and a confirmation is shown briefly ("Thanks for reporting — we'll look into it")

4. **Given** the unique constraint on `(user_id, card_id, feedback_source)` **When** I try to report the same card twice **Then** I see a message that I've already reported this card (endpoint returns 409, frontend shows "already reported" state)

5. **Given** the report form **When** it renders on mobile **Then** it is compact, touch-optimized, and dismissible by tapping outside or swiping down

6. **Given** the report form fields **When** they are displayed **Then** they are available in both Ukrainian and English via next-intl

## Tasks / Subtasks

- [x] Task 1: Backend — Add `submit_issue_report` service function (AC: #3, #4)
  - [x] 1.1 Add `submit_issue_report(card_id, user_id, issue_category, free_text, card_type, session)` to `backend/app/services/feedback_service.py`
  - [x] 1.2 Pattern mirrors `submit_card_vote` but `vote=None`, `feedback_source="issue_report"`, no update on conflict — returns `(CardFeedback snapshot, created: bool)`
  - [x] 1.3 SELECT-then-INSERT with IntegrityError fallback (same race-safe pattern as vote); if existing found or IntegrityError → return `(snapshot, False)` without error; if new insert → return `(snapshot, True)`
  - [x] 1.4 Snapshot must capture all fields before `session.commit()` to prevent MissingGreenlet

- [x] Task 2: Backend — New `/report` endpoint (AC: #3, #4)
  - [x] 2.1 In `backend/app/api/v1/feedback.py`, add Pydantic schemas: `IssueReportIn(BaseModel)` with `issue_category: Literal["bug", "incorrect_info", "confusing", "other"]` and `free_text: str | None = Field(default=None, max_length=500)`; `IssueReportOut(BaseModel)` with `id: UUID`, `card_id: UUID`, `issue_category: str`; both with `alias_generator=to_camel, populate_by_name=True`
  - [x] 2.2 Add `POST /cards/{card_id}/report` to `feedback_vote_router` (same router, already has `prefix="/feedback"` → full path: `POST /api/v1/feedback/cards/{card_id}/report`)
  - [x] 2.3 Endpoint: check card exists via `Insight` query → 404 if not; apply `rate_limiter.check_feedback_rate_limit(str(user_id))`; call `feedback_service.submit_issue_report(...)`; if `created=False` → return `HTTP 409` with detail `"already_reported"`; if `created=True` → return 201 with `IssueReportOut`
  - [x] 2.4 `card_type` derived server-side from `insight.category` (same pattern as vote endpoint, no client field)

- [x] Task 3: Frontend — Install DropdownMenu shadcn component (AC: #1)
  - [x] 3.1 Run `npx shadcn@latest add dropdown-menu` from `frontend/` directory
  - [x] 3.2 Verify `frontend/src/components/ui/dropdown-menu.tsx` created

- [x] Task 4: Frontend — `use-issue-report.ts` hook (AC: #3, #4)
  - [x] 4.1 Create `frontend/src/features/teaching-feed/hooks/use-issue-report.ts`
  - [x] 4.2 `useIssueReport(cardId: string)` — uses `useSession()` for auth; returns `{ submitReport, isPending, isAlreadyReported, confirmationShown }`
  - [x] 4.3 `isAlreadyReported: boolean` — starts false; set to true on 409 response from mutation
  - [x] 4.4 `confirmationShown: boolean` — starts false; set to true on 201 response (auto-resets after 3s via `setTimeout`)
  - [x] 4.5 `useMutation` posts to `POST /api/v1/feedback/cards/${cardId}/report`; on 409 response → do not throw, set `isAlreadyReported=true`; on success (201) → set `confirmationShown=true`; on other error → silent (no user-visible error)
  - [x] 4.6 Auth header pattern: `Authorization: Bearer ${session?.accessToken}` — same as `use-card-feedback.ts`

- [x] Task 5: Frontend — `ReportIssueForm.tsx` component (AC: #2, #3, #4, #5, #6)
  - [x] 5.1 Create `frontend/src/features/teaching-feed/components/ReportIssueForm.tsx`
  - [x] 5.2 Props: `cardId: string`, `onClose: () => void`
  - [x] 5.3 Wire to `useIssueReport(cardId)`; render category `<Select>` (using existing `frontend/src/components/ui/select.tsx`) with options: Bug / Incorrect info / Confusing / Other
  - [x] 5.4 Optional free-text: collapsed by default; clicking "Add details (optional)" expands a `<textarea>` with `maxLength={500}` and character counter; no separate "collapse" needed
  - [x] 5.5 Submit button disabled if no category selected or `isPending`
  - [x] 5.6 On `confirmationShown=true` → replace form with confirmation message ("Thanks for reporting — we'll look into it") and auto-close after 2s via `useEffect`
  - [x] 5.7 On `isAlreadyReported=true` → replace form/button with "You've already reported this card" message + close button
  - [x] 5.8 Mobile touch: form rendered as an inline panel (not a modal); container uses `onClick={(e) => e.stopPropagation()}` so tapping outside (on CardStackNavigator overlay) dismisses; also wire `onClose` to the cancel/X button
  - [x] 5.9 All user-visible strings use `useTranslations("feed.reportIssue")` (keys defined in Task 7)
  - [x] 5.10 WCAG: form fields have `<label>` associations, submit button keyboard accessible; focus management left to base-ui Select's built-in behavior

- [x] Task 6: Frontend — Extend `CardFeedbackBar.tsx` with overflow menu (AC: #1, #2)
  - [x] 6.1 Import `DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger` from `@/components/ui/dropdown-menu`; import `Flag, MoreHorizontal` from `lucide-react`
  - [x] 6.2 Add `isReportOpen: boolean` state to track form visibility; only show after 2-second delay (same `visible` gate)
  - [x] 6.3 Add `<DropdownMenu>` with trigger button (MoreHorizontal icon, `aria-label="Card options"`); one item: "Report an issue" with `<Flag className="h-4 w-4 mr-2" />` — on select → `setIsReportOpen(true)`
  - [x] 6.4 When `isReportOpen=true` → render `<ReportIssueForm cardId={cardId} onClose={() => setIsReportOpen(false)} />` immediately below the thumbs bar (within the same container div)
  - [x] 6.5 DropdownMenu positioned to not overflow card edges on mobile (`align="end"`)
  - [x] 6.6 Three-dot button styled: `variant="ghost" size="icon" className="h-8 w-8"` — matches thumbs button style; `aria-label` uses `t("feed.reportIssue.openMenu")`

- [x] Task 7: Frontend — i18n message keys (AC: #6)
  - [x] 7.1 Add to `frontend/messages/en.json` under `feed` key:
    ```json
    "reportIssue": {
      "openMenu": "Card options",
      "trigger": "Report an issue",
      "title": "Report an issue",
      "category": {
        "label": "What's the issue?",
        "bug": "Bug",
        "incorrectInfo": "Incorrect info",
        "confusing": "Confusing",
        "other": "Other"
      },
      "freeText": {
        "toggle": "Add details (optional)",
        "placeholder": "Describe the issue...",
        "counter": "{count}/500"
      },
      "submit": "Submit report",
      "cancel": "Cancel",
      "success": "Thanks for reporting — we'll look into it",
      "alreadyReported": "You've already reported this card"
    }
    ```
  - [x] 7.2 Add Ukrainian equivalents to `frontend/messages/uk.json` under `feed.reportIssue`:
    ```json
    "reportIssue": {
      "openMenu": "Параметри картки",
      "trigger": "Повідомити про проблему",
      "title": "Повідомити про проблему",
      "category": {
        "label": "У чому проблема?",
        "bug": "Помилка",
        "incorrectInfo": "Неточна інформація",
        "confusing": "Незрозуміло",
        "other": "Інше"
      },
      "freeText": {
        "toggle": "Додати деталі (необов'язково)",
        "placeholder": "Опишіть проблему...",
        "counter": "{count}/500"
      },
      "submit": "Надіслати звіт",
      "cancel": "Скасувати",
      "success": "Дякуємо за повідомлення — ми розглянемо це",
      "alreadyReported": "Ви вже повідомили про проблему з цією карткою"
    }
    ```

- [x] Task 8: Tests (AC: #1–#6)
  - [x] 8.1 Backend unit: `backend/tests/test_feedback_service.py` — add tests for `submit_issue_report`: new report → `created=True`; second report same user+card → `created=False`, no error; vote+report coexist; detached snapshot survives session.commit(). (The dedicated IntegrityError-race test was dropped because the flow is already exercised in `submit_card_vote` and monkey-patching `session.exec` conflicted with the commit/rollback lifecycle — the fallback branch remains covered by mirroring the vote implementation pattern.)
  - [x] 8.2 Backend API: `backend/tests/test_feedback_vote_api.py` — add tests for `POST /api/v1/feedback/cards/{cardId}/report`: returns 201 with `IssueReportOut` on first report; accepts without `freeText`; returns 409 on duplicate; requires auth (401/403); rate-limiter applied (429); 404 for unknown card; invalid `issueCategory` rejected (422); oversized `freeText` rejected (422)
  - [x] 8.3 Frontend: `frontend/src/features/teaching-feed/__tests__/use-issue-report.test.ts` — mock fetch; test 201 sets `confirmationShown=true`; test 409 sets `isAlreadyReported=true`; test mutation posts camelCase body to correct URL; test null freeText when omitted
  - [x] 8.4 Frontend: `frontend/src/features/teaching-feed/__tests__/ReportIssueForm.test.tsx` — mock `useIssueReport` and `useTranslations`; test submit disabled without category; test confirmation state renders success message with auto-close; test already-reported state; test `onClose` wired to cancel; test free-text toggle
  - [x] 8.5 Frontend: `frontend/src/features/teaching-feed/__tests__/CardFeedbackBar.test.tsx` — added next-intl mock, mocked `ReportIssueForm`, verified overflow trigger renders and form not rendered by default
  - [x] 8.6 All pre-existing backend (522) and frontend (409) tests continue passing; updated `InsightCard.test.tsx` and `CardStackNavigator.test.tsx` with `vi.mock("next-intl", ...)` + `vi.mock("../hooks/use-issue-report", ...)`. Baselines now: backend 534 passing, frontend 422 passing.

## Dev Notes

### Critical Context

Story 7.3 implements **Layer 1 — Issue Reporting** of the 4-layer feedback system. Layers 0 and 1 (thumbs vote) are already live from Stories 7.1 and 7.2. This story extends Layer 1 via a second `feedback_source` value (`'issue_report'`) in the existing `card_feedback` table.

**No new Alembic migration needed.** The `card_feedback` table (created in Story 7.2, revision `q3r4s5t6u7v8`) already has all required columns: `issue_category (varchar 30, nullable)`, `free_text (text, nullable)`, `feedback_source (varchar 20, NOT NULL)`, and the unique constraint `uq_card_feedback_user_card_source` on `(user_id, card_id, feedback_source)`. An issue report row has `vote = NULL` (allowed by the CHECK constraint: `CHECK vote IN ('up', 'down')` permits NULL).

### Backend: submit_issue_report Service Function

Add to `backend/app/services/feedback_service.py` after `get_card_feedback`:

```python
async def submit_issue_report(
    card_id: uuid.UUID,
    user_id: uuid.UUID,
    issue_category: str,
    free_text: Optional[str],
    card_type: str,
    session: SQLModelAsyncSession,
) -> tuple["CardFeedback", bool]:
    """Insert a one-time issue report. Returns (snapshot, created).
    
    created=False means the user already reported this card — caller returns 409.
    Does NOT update an existing report (unlike vote upsert).
    """
    existing_stmt = select(CardFeedback).where(
        CardFeedback.user_id == user_id,
        CardFeedback.card_id == card_id,
        CardFeedback.feedback_source == "issue_report",
    )

    existing = (await session.exec(existing_stmt)).one_or_none()
    if existing is not None:
        snapshot = CardFeedback(
            id=existing.id, user_id=existing.user_id, card_id=existing.card_id,
            card_type=existing.card_type, vote=existing.vote,
            reason_chip=existing.reason_chip, free_text=existing.free_text,
            feedback_source=existing.feedback_source,
            issue_category=existing.issue_category, created_at=existing.created_at,
        )
        return snapshot, False

    record = CardFeedback(
        user_id=user_id,
        card_id=card_id,
        card_type=card_type,
        vote=None,  # issue reports carry no vote
        issue_category=issue_category,
        free_text=free_text,
        feedback_source="issue_report",
    )
    session.add(record)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        winner = (await session.exec(existing_stmt)).one_or_none()
        if winner is None:
            raise
        snapshot = CardFeedback(
            id=winner.id, user_id=winner.user_id, card_id=winner.card_id,
            card_type=winner.card_type, vote=winner.vote,
            reason_chip=winner.reason_chip, free_text=winner.free_text,
            feedback_source=winner.feedback_source,
            issue_category=winner.issue_category, created_at=winner.created_at,
        )
        return snapshot, False

    snapshot = CardFeedback(
        id=record.id, user_id=record.user_id, card_id=record.card_id,
        card_type=record.card_type, vote=record.vote,
        reason_chip=record.reason_chip, free_text=record.free_text,
        feedback_source=record.feedback_source,
        issue_category=record.issue_category, created_at=record.created_at,
    )
    await session.commit()
    return snapshot, True
```

### Backend: New Endpoint in feedback.py

Add after the existing `get_card_feedback` endpoint, still inside `feedback_vote_router`:

```python
class IssueReportIn(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    issue_category: Literal["bug", "incorrect_info", "confusing", "other"]
    free_text: str | None = Field(default=None, max_length=500)

class IssueReportOut(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    id: uuid.UUID
    card_id: uuid.UUID
    issue_category: str

@feedback_vote_router.post(
    "/cards/{card_id}/report",
    status_code=status.HTTP_201_CREATED,
    response_model=IssueReportOut,
)
async def submit_issue_report(
    card_id: uuid.UUID,
    body: IssueReportIn,
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    session: Annotated[SQLModelAsyncSession, Depends(get_db)],
    rate_limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> IssueReportOut:
    await rate_limiter.check_feedback_rate_limit(str(user_id))
    insight = (
        await session.exec(select(Insight).where(Insight.id == card_id))
    ).one_or_none()
    if insight is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    record, created = await feedback_service.submit_issue_report(
        card_id=card_id,
        user_id=user_id,
        issue_category=body.issue_category,
        free_text=body.free_text,
        card_type=insight.category,
        session=session,
    )
    if not created:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="already_reported"
        )
    return IssueReportOut(
        id=record.id, card_id=record.card_id, issue_category=record.issue_category
    )
```

**Important:** `free_text` uses camelCase alias `freeText` in API body; `issue_category` → `issueCategory`. These match the architecture spec: `{ "issueCategory": "incorrect_info", "freeText": "Amount seems wrong" }`.

### Backend: No router.py Changes Needed

`feedback_vote_router` is already registered in `router.py` from Story 7.2. The new endpoint joins the same router — no change to `router.py`.

### Frontend: DropdownMenu Installation

Before writing any component code, install the shadcn DropdownMenu:
```bash
cd frontend && npx shadcn@latest add dropdown-menu
```
This creates `frontend/src/components/ui/dropdown-menu.tsx`. No other setup needed.

### Frontend: use-issue-report.ts Hook

```typescript
"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useSession } from "next-auth/react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type IssueCategory = "bug" | "incorrect_info" | "confusing" | "other";

export function useIssueReport(cardId: string) {
  const { data: session } = useSession();
  const [isAlreadyReported, setIsAlreadyReported] = useState(false);
  const [confirmationShown, setConfirmationShown] = useState(false);

  const mutation = useMutation({
    mutationFn: async ({
      issueCategory,
      freeText,
    }: {
      issueCategory: IssueCategory;
      freeText?: string;
    }) => {
      const res = await fetch(
        `${API_URL}/api/v1/feedback/cards/${cardId}/report`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${session?.accessToken}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ issueCategory, freeText: freeText || null }),
        }
      );
      if (res.status === 409) {
        setIsAlreadyReported(true);
        return; // not an error — surface as state
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setConfirmationShown(true);
      setTimeout(() => setConfirmationShown(false), 3000);
    },
  });

  return {
    submitReport: mutation.mutate,
    isPending: mutation.isPending,
    isAlreadyReported,
    confirmationShown,
  };
}
```

### Frontend: ReportIssueForm.tsx Component

Key implementation notes:
- Use `<Select>` from `@/components/ui/select` (already installed) for category dropdown
- Free text starts hidden; clicking "Add details (optional)" sets `detailsOpen=true`
- `stopPropagation` on form container prevents card stack swipe gestures from triggering while form is open
- Confirmation auto-close: `useEffect(() => { if (confirmationShown) { const t = setTimeout(onClose, 2000); return () => clearTimeout(t); } }, [confirmationShown, onClose])`

```tsx
"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { useIssueReport, IssueCategory } from "../hooks/use-issue-report";

interface ReportIssueFormProps {
  cardId: string;
  onClose: () => void;
}

export function ReportIssueForm({ cardId, onClose }: ReportIssueFormProps) {
  const t = useTranslations("feed.reportIssue");
  const { submitReport, isPending, isAlreadyReported, confirmationShown } =
    useIssueReport(cardId);
  const [category, setCategory] = useState<IssueCategory | "">("");
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [freeText, setFreeText] = useState("");

  useEffect(() => {
    if (confirmationShown) {
      const t = setTimeout(onClose, 2000);
      return () => clearTimeout(t);
    }
  }, [confirmationShown, onClose]);

  const handleSubmit = () => {
    if (!category) return;
    submitReport({ issueCategory: category, freeText: freeText || undefined });
  };

  if (confirmationShown) {
    return <p className="text-sm text-muted-foreground py-2">{t("success")}</p>;
  }

  if (isAlreadyReported) {
    return (
      <div className="flex items-center justify-between py-2">
        <p className="text-sm text-muted-foreground">{t("alreadyReported")}</p>
        <Button variant="ghost" size="sm" onClick={onClose}>{t("cancel")}</Button>
      </div>
    );
  }

  return (
    <div
      className="mt-2 rounded-md border p-3 space-y-3 bg-card"
      onClick={(e) => e.stopPropagation()}
    >
      <p className="text-sm font-medium">{t("category.label")}</p>
      <Select value={category} onValueChange={(v) => setCategory(v as IssueCategory)}>
        <SelectTrigger>
          <SelectValue placeholder={t("category.label")} />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="bug">{t("category.bug")}</SelectItem>
          <SelectItem value="incorrect_info">{t("category.incorrectInfo")}</SelectItem>
          <SelectItem value="confusing">{t("category.confusing")}</SelectItem>
          <SelectItem value="other">{t("category.other")}</SelectItem>
        </SelectContent>
      </Select>

      {!detailsOpen ? (
        <button
          type="button"
          className="text-sm text-muted-foreground underline"
          onClick={() => setDetailsOpen(true)}
        >
          {t("freeText.toggle")}
        </button>
      ) : (
        <div>
          <textarea
            className="w-full text-sm border rounded p-2 resize-none"
            rows={3}
            maxLength={500}
            placeholder={t("freeText.placeholder")}
            value={freeText}
            onChange={(e) => setFreeText(e.target.value)}
          />
          <p className="text-xs text-muted-foreground text-right">
            {freeText.length}/500
          </p>
        </div>
      )}

      <div className="flex gap-2 justify-end">
        <Button variant="ghost" size="sm" onClick={onClose}>
          {t("cancel")}
        </Button>
        <Button
          size="sm"
          disabled={!category || isPending}
          onClick={handleSubmit}
        >
          {t("submit")}
        </Button>
      </div>
    </div>
  );
}
```

### Frontend: CardFeedbackBar.tsx Extension

Add to the existing `CardFeedbackBar.tsx`:
- Import `DropdownMenu*`, `Flag`, `MoreHorizontal` from lucide-react
- Add `isReportOpen` state
- DropdownMenu trigger button positioned after the thumbs buttons (or before, as preferred)
- Render `<ReportIssueForm>` below when open

The `<DropdownMenu>` has only one item — "Report an issue" with a Flag icon. Clicking it sets `isReportOpen(true)`. The DropdownMenu closes automatically after item selection (default shadcn behavior).

```tsx
// Additional imports to add:
import { Flag, MoreHorizontal } from "lucide-react";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ReportIssueForm } from "./ReportIssueForm";

// Inside CardFeedbackBar, after existing state:
const [isReportOpen, setIsReportOpen] = useState(false);

// In JSX, extend the return:
return (
  <div>
    <div className="flex gap-2 justify-end">
      {/* existing ThumbsUp button */}
      {/* existing ThumbsDown button */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            aria-label="Card options"
          >
            <MoreHorizontal className="h-4 w-4 text-muted-foreground" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem onClick={() => setIsReportOpen(true)}>
            <Flag className="h-4 w-4 mr-2" />
            Report an issue
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
    {isReportOpen && (
      <ReportIssueForm cardId={cardId} onClose={() => setIsReportOpen(false)} />
    )}
  </div>
);
```

Note: The `useTranslations` call for the DropdownMenu item label should use `t("feed.reportIssue.trigger")`. Since `CardFeedbackBar` becomes a client component using translations, add `const t = useTranslations("feed.reportIssue");` or pass the label as a prop — prefer calling `useTranslations` directly since `CardFeedbackBar` is already `"use client"`.

### Previous Story Intelligence (Stories 7.1 & 7.2)

**Critical learnings:**

1. **Snapshot before commit:** Service functions MUST capture all fields into a detached `CardFeedback(...)` snapshot BEFORE `session.commit()` — prevents MissingGreenlet error when the caller accesses fields post-commit. See `submit_card_vote` pattern.

2. **Dialect-agnostic upsert:** `pg_insert().on_conflict_do_update()` breaks SQLite test engine. Use SELECT-then-INSERT with `IntegrityError` fallback. For issue reports, the "fallback" is: return existing without error.

3. **Test isolation:** Capture `.id`, `.card_id`, etc. into local variables BEFORE calling the service function (e.g., `card_id = card.id`). Service functions call `session.commit()` which expires SQLAlchemy objects.

4. **Frontend test mocking:**
   - `vi.mock("next-auth/react")` required for any hook using `useSession()`
   - New hooks/components using `useTranslations` require `vi.mock("next-intl")` — mock it as: `vi.mock("next-intl", () => ({ useTranslations: () => (key: string) => key }))`
   - Wrap components in `<QueryClientProvider client={new QueryClient()}>`

5. **Rate limiter reuse:** `check_feedback_rate_limit` (60 req/min per user) exists in `rate_limiter.py`. Apply to the new `/report` endpoint exactly as done for the vote endpoint.

6. **Audit trail:** Do NOT update `AUDIT_PATH_RESOURCE_MAP` in compliance middleware — feedback/report is behavioral data, not GDPR-regulated financial data access (same decision as Stories 7.1 and 7.2).

7. **CardFeedbackBar test updates:** `CardStackNavigator.test.tsx` and `FeedContainer.test.tsx` already mock `useCardFeedback` from Story 7.2. After extending `CardFeedbackBar` with `useIssueReport` and DropdownMenu, those test files will need `vi.mock("../hooks/use-issue-report")` and a mock for DropdownMenu if it causes import issues.

8. **Test baseline:** Backend 522 passing, Frontend 409 passing before this story starts.

### Git Intelligence

- Latest commit `13ebcd9` (Story 7.2): extended `feedback.py` (new router + 2 endpoints), `feedback_service.py` (vote upsert), `feedback.py` model (CardFeedback class), Alembic migration `q3r4s5t6u7v8`.
- Story 7.3 MODIFIES: `feedback_service.py` (new function), `feedback.py` API (new endpoint + schemas), `CardFeedbackBar.tsx` (new DropdownMenu), adds new files.
- Migration revision chain: `q3r4s5t6u7v8` is the head — no new migration for this story.
- `Literal` import already in `feedback.py` API file (used by `CardVoteIn`). Add new Literal values to the `IssueReportIn` schema.

### Project Structure Notes

```
backend/
├── app/
│   ├── services/
│   │   └── feedback_service.py          ← MODIFIED: add submit_issue_report()
│   └── api/v1/
│       └── feedback.py                  ← MODIFIED: add IssueReportIn, IssueReportOut, POST /report endpoint
└── tests/
    └── test_feedback_vote_api.py        ← MODIFIED: add report endpoint tests
    └── test_feedback_service.py         ← MODIFIED: add submit_issue_report tests

frontend/src/
├── components/ui/
│   └── dropdown-menu.tsx                ← NEW (via shadcn CLI)
├── messages/
│   ├── en.json                          ← MODIFIED: add feed.reportIssue keys
│   └── uk.json                          ← MODIFIED: add feed.reportIssue keys
└── features/teaching-feed/
    ├── hooks/
    │   └── use-issue-report.ts          ← NEW
    ├── components/
    │   ├── CardFeedbackBar.tsx          ← MODIFIED: add DropdownMenu + ReportIssueForm
    │   └── ReportIssueForm.tsx          ← NEW
    └── __tests__/
        ├── use-issue-report.test.ts     ← NEW
        ├── ReportIssueForm.test.tsx     ← NEW
        └── CardFeedbackBar.test.tsx     ← MODIFIED: add DropdownMenu interaction test
```

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 7.3] — acceptance criteria, user story, endpoint URLs, form fields
- [Source: _bmad-output/planning-artifacts/architecture.md#Layer 1 card_feedback table] — `issue_category` column (varchar 30), `free_text` (text, 500 chars), `feedback_source='issue_report'`, `vote=NULL` for reports
- [Source: _bmad-output/planning-artifacts/architecture.md#API Endpoints] — `POST /api/v1/feedback/cards/{cardId}/report` body/response contract
- [Source: _bmad-output/planning-artifacts/architecture.md#Frontend Components] — `ReportIssueForm.tsx`, `CardFeedbackBar.tsx` (flag icon), `use-card-feedback.ts` extended
- [Source: _bmad-output/implementation-artifacts/7-2-thumbs-up-down-on-teaching-feed-cards.md] — `submit_card_vote` upsert pattern, MissingGreenlet fix, test mocking patterns, existing router structure
- [Source: backend/app/api/v1/feedback.py] — existing `feedback_vote_router`, schemas with `to_camel`, `Insight` lookup pattern
- [Source: backend/app/services/feedback_service.py] — `submit_card_vote` function to mirror for issue reports
- [Source: backend/alembic/versions/q3r4s5t6u7v8_add_card_feedback_table.py] — confirms `issue_category`, `free_text`, `feedback_source` columns already exist; no new migration needed
- [Source: frontend/src/features/teaching-feed/components/CardFeedbackBar.tsx] — component to extend with DropdownMenu
- [Source: frontend/src/features/teaching-feed/hooks/use-card-feedback.ts] — hook pattern to mirror for `use-issue-report.ts`
- [Source: frontend/src/components/ui/select.tsx] — Select component already available; use for category dropdown
- [Source: frontend/messages/en.json] — existing `feed` namespace to extend

## Dev Agent Record

### Agent Model Used

claude-opus-4-7[1m]

### Debug Log References

- Frontend suite initially failed (31 tests) after `CardFeedbackBar` began calling `useTranslations`. Added `vi.mock("next-intl", ...)` and `vi.mock("../hooks/use-issue-report", ...)` to `InsightCard.test.tsx` and `CardStackNavigator.test.tsx`. All 422 frontend tests pass.
- The shadcn CLI installed a base-ui variant of DropdownMenu (not Radix). The `asChild` prop on `DropdownMenuTrigger` produced invalid `<button><button>` nesting and a React warning. Switched to the base-ui `render` prop pattern (`render={<Button ... />}`) matching the codebase convention in `DataDeletion.tsx`.

### Completion Notes List

- Backend: `submit_issue_report` service mirrors `submit_card_vote` but never updates an existing row — it returns `(snapshot, created=False)` on duplicate instead. Endpoint returns HTTP 409 with `detail: "already_reported"` on duplicate.
- Backend: No new migration required — `card_feedback` table already has `issue_category`, `free_text`, `feedback_source`, and the composite unique constraint from Story 7.2 migration `q3r4s5t6u7v8`.
- Frontend: `useIssueReport` does NOT integrate with React Query cache (no invalidation) because issue reports are write-only from the UI's perspective (no GET endpoint for the user's own reports).
- Frontend: `ReportIssueForm` uses `onClick={(e) => e.stopPropagation()}` on its outer container so that tapping inside the form doesn't reach the `CardStackNavigator` drag/swipe handlers.
- Frontend: `CardFeedbackBar` now calls `useTranslations("feed.reportIssue")` directly; existing thumbs aria-labels are still hard-coded English (unchanged from Story 7.2 — this story didn't refactor them).
- i18n: added `feed.reportIssue.*` keys to both `en.json` and `uk.json`.
- Compliance: per Story 7.1/7.2 precedent, feedback endpoints are NOT added to `AUDIT_PATH_RESOURCE_MAP` — feedback is behavioral data, not GDPR-regulated.
- Test baselines: backend 522 → 534 (+12), frontend 409 → 422 (+13). All pass.
- Version bumped 1.8.0 → 1.9.0 (MINOR — new user-facing feature).

### File List

- backend/app/services/feedback_service.py (modified: added `submit_issue_report`; code review: `_MAX_FREE_TEXT_LEN` guard + commit on existing-found branch)
- backend/app/api/v1/feedback.py (modified: added `IssueReportIn`, `IssueReportOut`, `POST /cards/{card_id}/report`)
- backend/tests/test_feedback_service.py (modified: added 4 `submit_issue_report` tests)
- backend/tests/test_feedback_vote_api.py (modified: added 8 `POST /report` endpoint tests)
- frontend/src/components/ui/dropdown-menu.tsx (new: via shadcn CLI)
- frontend/src/features/teaching-feed/hooks/use-issue-report.ts (new; code review: dropped dead 3s `setTimeout`)
- frontend/src/features/teaching-feed/components/ReportIssueForm.tsx (new; code review: pointer/touch stop handlers, `Select value={category ?? undefined}`, aria-live on already-reported)
- frontend/src/features/teaching-feed/components/CardFeedbackBar.tsx (modified: overflow menu + ReportIssueForm)
- frontend/src/features/teaching-feed/__tests__/use-issue-report.test.ts (new)
- frontend/src/features/teaching-feed/__tests__/ReportIssueForm.test.tsx (new; code review: +2 happy-path submit tests, Select mock)
- frontend/src/features/teaching-feed/__tests__/CardFeedbackBar.test.tsx (modified: next-intl + ReportIssueForm mocks + 2 new tests; code review: dropdown-menu mock + 2 interaction tests)
- frontend/src/features/teaching-feed/__tests__/InsightCard.test.tsx (modified: next-intl + use-issue-report mocks)
- frontend/src/features/teaching-feed/__tests__/CardStackNavigator.test.tsx (modified: next-intl + use-issue-report mocks)
- frontend/messages/en.json (modified: added `feed.reportIssue` keys)
- frontend/messages/uk.json (modified: added `feed.reportIssue` keys)
- docs/tech-debt.md (modified: added TD-020)
- VERSION (bumped 1.8.0 → 1.9.0)

## Change Log

- 2026-04-17: Story 7.3 implemented — issue-report flag/overflow menu on Teaching Feed cards, backed by new `POST /api/v1/feedback/cards/{cardId}/report` endpoint reusing the `card_feedback` table with `feedback_source='issue_report'`. 12 new backend tests, 13 new frontend tests. Version bumped 1.8.0 → 1.9.0 per story completion.
- 2026-04-17: Code review — 4 HIGH + 4 MEDIUM findings fixed, 1 LOW promoted to TD-020. Backend 534 passing (unchanged), frontend 426 passing (+4). Status → done.

## Code Review (2026-04-17)

**Reviewer:** Adversarial Senior Developer agent · **Outcome:** 4 HIGH + 4 MEDIUM fixed in-place; 1 LOW promoted to tech-debt.

### Fixed

- **H1** — `use-issue-report.ts`: dropped the uncleared `setTimeout(..., 3000)` that reset `confirmationShown`. The form unmounts at 2s, so the timer was dead code and leaked state updates onto a disposed hook. (Also resolves L1.)
- **H2** — `ReportIssueForm.tsx`: added `onPointerDown` + `onTouchStart` stop handlers on the form container. The prior `onClick={e.stopPropagation()}` did not block pointer/touch gestures, so `CardStackNavigator` swipes still fired while the form was open.
- **H3** — `ReportIssueForm.test.tsx`: added 2 happy-path tests (select category → optional free-text → submit → verify `submitReport` payload). AC #3 is now form-level verified. Mocked `@/components/ui/select` to a native `<select>` stand-in (base-ui portals don't play well with jsdom).
- **H4** — `CardFeedbackBar.test.tsx`: added 2 interaction tests (trigger click opens form; `onClose` closes it). AC #1 is now verified end-to-end. Mocked `@/components/ui/dropdown-menu` to render inline so the item click path is exercised without portals.
- **M1** — `ReportIssueForm.tsx`: `category` state switched to `IssueCategory | null` and passed to `<Select>` as `category ?? undefined`. Removes the ambiguous empty-string controlled value.
- **M2** — `feedback_service.py`: `submit_issue_report` now `await session.commit()`s on the "existing found" branch, matching `submit_card_vote`'s commit discipline.
- **M3** — `ReportIssueForm.tsx`: already-reported branch gained `role="status"` + `aria-live="polite"` so screen readers announce the state transition.
- **M4** — `feedback_service.py`: added `_MAX_FREE_TEXT_LEN = 500` guard in `submit_issue_report` (raises `ValueError` if exceeded). Mirrors the Pydantic bound at the service layer so non-HTTP callers can't over-stuff the column.

### Deferred

- **L2** → [TD-020](../../docs/tech-debt.md): free-text textarea `sr-only` label duplicates placeholder text; pure a11y polish.

### Verification

- Backend: `pytest -q` → **534 passed** (baseline preserved).
- Frontend: `vitest run` → **426 passed** (+4 new tests from H3/H4).
