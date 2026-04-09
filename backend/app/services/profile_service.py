import uuid
from datetime import UTC, datetime

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
