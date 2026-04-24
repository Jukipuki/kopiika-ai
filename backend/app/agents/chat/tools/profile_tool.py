# Read-only — MUST NOT mutate. Any INSERT/UPDATE/DELETE introduction breaks the Epic 10 no-write-tools invariant.
"""``get_profile`` — return the authenticated user's cumulative financial profile.

Story 10.4c. Wraps ``profile_service.get_profile_for_user``,
``get_category_breakdown``, and ``get_monthly_comparison``, plus
``health_score_service.get_latest_score`` for the savings/health numbers.

Empty-profile path (brand-new user, no uploads) returns all-``None`` summary
fields + empty lists. The model is expected to answer "I don't see any
profile data yet" through the Guardrails-grounded path (Story 10.6a), not
hallucinate numbers from priors.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Optional

from pydantic import BaseModel

from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.services.health_score_service import get_latest_score
from app.services.profile_service import (
    get_category_breakdown,
    get_monthly_comparison,
    get_profile_for_user,
)

_MAX_BREAKDOWN_ROWS = 12
_MAX_COMPARISON_ROWS = 12


class GetProfileInput(BaseModel):
    include_category_breakdown: bool = False
    include_monthly_comparison: bool = False


class ProfileSummary(BaseModel):
    monthly_income_kopiykas: Optional[int] = None
    monthly_expenses_kopiykas: Optional[int] = None
    savings_ratio: Optional[int] = None
    health_score: Optional[int] = None
    currency: str
    as_of: date


class CategoryBreakdownRow(BaseModel):
    category_code: str
    amount_kopiykas: int
    share_percent: int


class MonthlyComparisonRow(BaseModel):
    month: date
    # income_kopiykas is Optional because ``get_monthly_comparison`` in the
    # profile service only reports expenses; reporting 0 would be a grounded-
    # but-wrong "you earned nothing" answer. Left ``None`` until the service
    # grows a month-income aggregate.
    income_kopiykas: Optional[int] = None
    expenses_kopiykas: int


class GetProfileOutput(BaseModel):
    summary: ProfileSummary
    category_breakdown: list[CategoryBreakdownRow] = []
    monthly_comparison: list[MonthlyComparisonRow] = []


def _today_utc() -> date:
    return datetime.now(UTC).date()


def _to_date(v: datetime | date | None) -> Optional[date]:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date()
    return v


async def get_profile_handler(
    *,
    user_id: uuid.UUID,
    db: SQLModelAsyncSession,
    include_category_breakdown: bool = False,
    include_monthly_comparison: bool = False,
) -> GetProfileOutput:
    profile = await get_profile_for_user(db, user_id)
    latest = await get_latest_score(db, user_id)

    if profile is None:
        return GetProfileOutput(
            summary=ProfileSummary(
                monthly_income_kopiykas=None,
                monthly_expenses_kopiykas=None,
                savings_ratio=None,
                health_score=None,
                # UAH is the default throughout the product; it stays the
                # answer when no data exists. Real multi-currency wiring is
                # epic-scoped elsewhere and out of scope here.
                currency="UAH",
                as_of=_today_utc(),
            ),
        )

    savings_ratio: Optional[int] = None
    if latest is not None and isinstance(latest.breakdown, dict):
        raw = latest.breakdown.get("savings_ratio")
        if isinstance(raw, int):
            savings_ratio = raw

    as_of = _to_date(profile.updated_at) or _today_utc()

    summary = ProfileSummary(
        monthly_income_kopiykas=profile.total_income,
        monthly_expenses_kopiykas=profile.total_expenses,
        savings_ratio=savings_ratio,
        health_score=latest.score if latest is not None else None,
        currency="UAH",
        as_of=as_of,
    )

    breakdown_rows: list[CategoryBreakdownRow] = []
    if include_category_breakdown:
        raw_breakdown = await get_category_breakdown(db, user_id) or []
        for item in raw_breakdown[:_MAX_BREAKDOWN_ROWS]:
            breakdown_rows.append(
                CategoryBreakdownRow(
                    category_code=item["category"],
                    amount_kopiykas=int(item["amount"]),
                    share_percent=int(round(float(item["percentage"]))),
                )
            )

    comparison_rows: list[MonthlyComparisonRow] = []
    if include_monthly_comparison:
        comp = await get_monthly_comparison(db, user_id)
        if comp is not None:
            # `get_monthly_comparison` returns two aggregated months. Build a
            # flat per-month summary the model can reason about; income is
            # not broken out by the existing service, so we report only the
            # expenses side and leave income at 0 here (the profile-level
            # income field covers the cumulative number). The cap at 12 is
            # prospective — if the service grows to return up to 12 months,
            # this cap is already enforced.
            months = [
                (comp.get("current_month"), int(comp.get("total_current", 0))),
                (comp.get("previous_month"), int(comp.get("total_previous", 0))),
            ]
            for month_str, expenses in months[:_MAX_COMPARISON_ROWS]:
                if not month_str:
                    continue
                try:
                    year_s, month_s = month_str.split("-")
                    month_start = date(int(year_s), int(month_s), 1)
                except (ValueError, AttributeError):
                    continue
                comparison_rows.append(
                    MonthlyComparisonRow(
                        month=month_start,
                        income_kopiykas=None,
                        expenses_kopiykas=expenses,
                    )
                )

    return GetProfileOutput(
        summary=summary,
        category_breakdown=breakdown_rows,
        monthly_comparison=comparison_rows,
    )
