import uuid
from datetime import UTC, datetime

from sqlalchemy import and_, func, or_
from sqlmodel import Session, select
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.models.financial_profile import FinancialProfile
from app.models.transaction import Transaction


def build_or_update_profile(session: Session, user_id: uuid.UUID) -> FinancialProfile:
    """Recalculate and upsert the financial profile from ALL user transactions (sync)."""
    transactions = session.exec(
        select(Transaction).where(Transaction.user_id == user_id)
    ).all()

    return _upsert_profile(session, user_id, transactions)


async def get_profile_for_user(
    session: SQLModelAsyncSession, user_id: uuid.UUID
) -> FinancialProfile | None:
    """Fetch the financial profile for a user (async, for API layer)."""
    result = await session.exec(
        select(FinancialProfile).where(FinancialProfile.user_id == user_id)
    )
    return result.first()


async def get_monthly_comparison(
    session: SQLModelAsyncSession, user_id: uuid.UUID
) -> dict | None:
    """Compare spending by category for the two most recent months.

    Returns per-category totals for the two most recent calendar months,
    or None if fewer than 2 distinct months exist.
    Amounts are returned as positive kopiykas (absolute values).
    """
    # Step 1: Find the two most recent distinct months with expenses
    month_query = (
        select(
            func.extract("year", Transaction.date).label("year"),
            func.extract("month", Transaction.date).label("month"),
        )
        .where(Transaction.user_id == user_id, Transaction.amount < 0)
        .group_by(
            func.extract("year", Transaction.date),
            func.extract("month", Transaction.date),
        )
        .order_by(
            func.extract("year", Transaction.date).desc(),
            func.extract("month", Transaction.date).desc(),
        )
        .limit(2)
    )
    result = await session.exec(month_query)
    months = list(result.all())
    if len(months) < 2:
        return None

    current_year, current_month = int(months[0].year), int(months[0].month)
    previous_year, previous_month = int(months[1].year), int(months[1].month)

    # Step 2: Get per-category totals for both months
    category_query = (
        select(
            func.extract("year", Transaction.date).label("year"),
            func.extract("month", Transaction.date).label("month"),
            func.coalesce(Transaction.category, "uncategorized").label("cat"),
            func.sum(func.abs(Transaction.amount)).label("total"),
        )
        .where(
            Transaction.user_id == user_id,
            Transaction.amount < 0,
            or_(
                and_(
                    func.extract("year", Transaction.date) == current_year,
                    func.extract("month", Transaction.date) == current_month,
                ),
                and_(
                    func.extract("year", Transaction.date) == previous_year,
                    func.extract("month", Transaction.date) == previous_month,
                ),
            ),
        )
        .group_by(
            func.extract("year", Transaction.date),
            func.extract("month", Transaction.date),
            func.coalesce(Transaction.category, "uncategorized"),
        )
    )
    result = await session.exec(category_query)
    rows = list(result.all())

    # Step 3: Build lookup: {category: {(year, month): total}}
    cat_data: dict[str, dict[tuple[int, int], int]] = {}
    for row in rows:
        y, m, cat, total = int(row.year), int(row.month), row.cat, int(row.total)
        if cat not in cat_data:
            cat_data[cat] = {}
        cat_data[cat][(y, m)] = total

    # Step 4: Build per-category comparison
    categories = []
    total_current = 0
    total_previous = 0
    for cat, month_totals in cat_data.items():
        current_amount = month_totals.get((current_year, current_month), 0)
        previous_amount = month_totals.get((previous_year, previous_month), 0)
        total_current += current_amount
        total_previous += previous_amount

        if previous_amount > 0:
            change_percent = round(
                (current_amount - previous_amount) / previous_amount * 100, 1
            )
        elif current_amount > 0:
            change_percent = 100.0
        else:
            change_percent = 0.0

        categories.append(
            {
                "category": cat,
                "current_amount": current_amount,
                "previous_amount": previous_amount,
                "change_percent": change_percent,
                "change_amount": current_amount - previous_amount,
            }
        )

    # Sort by absolute change_amount descending (biggest movers first)
    categories.sort(key=lambda c: abs(c["change_amount"]), reverse=True)

    # Total change percent
    if total_previous > 0:
        total_change_percent = round(
            (total_current - total_previous) / total_previous * 100, 1
        )
    elif total_current > 0:
        total_change_percent = 100.0
    else:
        total_change_percent = 0.0

    return {
        "current_month": f"{current_year}-{current_month:02d}",
        "previous_month": f"{previous_year}-{previous_month:02d}",
        "categories": categories,
        "total_current": total_current,
        "total_previous": total_previous,
        "total_change_percent": total_change_percent,
    }


def _upsert_profile(
    session: Session,
    user_id: uuid.UUID,
    transactions: list[Transaction],
) -> FinancialProfile:
    """Compute aggregates and upsert the profile row."""
    total_income = sum(t.amount for t in transactions if t.amount > 0)
    total_expenses = sum(t.amount for t in transactions if t.amount < 0)

    category_totals: dict[str, int] = {}
    for t in transactions:
        cat = t.category or "uncategorized"
        category_totals[cat] = category_totals.get(cat, 0) + t.amount

    period_start = min(t.date for t in transactions) if transactions else None
    period_end = max(t.date for t in transactions) if transactions else None

    profile = session.exec(
        select(FinancialProfile).where(FinancialProfile.user_id == user_id)
    ).first()

    if not profile:
        profile = FinancialProfile(user_id=user_id)

    profile.total_income = total_income
    profile.total_expenses = total_expenses
    profile.category_totals = category_totals
    profile.period_start = period_start
    profile.period_end = period_end
    profile.updated_at = datetime.now(UTC).replace(tzinfo=None)

    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile
