import uuid
from datetime import UTC, datetime
from typing import Any

from sqlmodel import Session, desc, select
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.models.financial_health_score import FinancialHealthScore
from app.models.financial_profile import FinancialProfile


def calculate_health_score(
    session: Session, user_id: uuid.UUID
) -> FinancialHealthScore:
    """Calculate and persist a financial health score from the user's profile (sync, for Celery)."""
    profile = session.exec(
        select(FinancialProfile).where(FinancialProfile.user_id == user_id)
    ).first()

    if not profile:
        raise ValueError("No financial profile — cannot calculate score")

    breakdown = _compute_breakdown(profile)

    final_score = int(
        breakdown["savings_ratio"] * 0.4
        + breakdown["category_diversity"] * 0.2
        + breakdown["expense_regularity"] * 0.2
        + breakdown["income_coverage"] * 0.2
    )
    final_score = max(0, min(100, final_score))

    health_score = FinancialHealthScore(
        user_id=user_id,
        score=final_score,
        calculated_at=datetime.now(UTC).replace(tzinfo=None),
        breakdown={
            "savings_ratio": breakdown["savings_ratio"],
            "category_diversity": breakdown["category_diversity"],
            "expense_regularity": breakdown["expense_regularity"],
            "income_coverage": breakdown["income_coverage"],
        },
    )
    session.add(health_score)
    session.commit()
    session.refresh(health_score)
    return health_score


async def get_score_history(
    session: SQLModelAsyncSession, user_id: uuid.UUID
) -> list[FinancialHealthScore]:
    """Fetch all health scores for a user ordered by calculated_at ascending (async, for API layer)."""
    result = await session.exec(
        select(FinancialHealthScore)
        .where(FinancialHealthScore.user_id == user_id)
        .order_by(FinancialHealthScore.calculated_at.asc())
    )
    return list(result.all())


async def get_latest_score(
    session: SQLModelAsyncSession, user_id: uuid.UUID
) -> FinancialHealthScore | None:
    """Fetch the most recent health score for a user (async, for API layer)."""
    result = await session.exec(
        select(FinancialHealthScore)
        .where(FinancialHealthScore.user_id == user_id)
        .order_by(desc(FinancialHealthScore.calculated_at))
    )
    return result.first()


def _compute_breakdown(profile: FinancialProfile) -> dict[str, Any]:
    """Compute the four component scores (each 0-100) from profile data."""

    # --- Savings ratio (40%) ---
    # total_expenses is negative (kopiykas), total_income is positive
    if profile.total_income > 0:
        # savings = income + expenses (expenses are negative, so this is net)
        savings_rate = (profile.total_income + profile.total_expenses) / profile.total_income
        # 50% savings rate = perfect 100; 0% = 0; negative = 0
        savings_score = max(0, min(100, int(savings_rate * 200)))
    else:
        savings_score = 0

    # --- Category diversity (20%) ---
    # Penalize if >50% of expenses in a single category
    category_totals: dict[str, int] = profile.category_totals or {}
    # Only consider expense categories (negative amounts)
    expense_cats = {k: abs(v) for k, v in category_totals.items() if v < 0}
    total_expense_abs = sum(expense_cats.values())

    if total_expense_abs > 0 and len(expense_cats) > 1:
        max_cat_share = max(expense_cats.values()) / total_expense_abs
        # 1 category = 100% share → score 0; equal split → score ~100
        # If max share <= 25% → 100; if 100% → 0
        diversity_score = max(0, min(100, int((1 - max_cat_share) * 133)))
    elif len(expense_cats) == 1:
        diversity_score = 0  # All in one category
    else:
        diversity_score = 50  # No expense data — neutral

    # --- Expense regularity (20%) ---
    # Use coefficient of variation of category amounts as proxy for predictability
    if total_expense_abs > 0 and len(expense_cats) > 1:
        mean_cat = total_expense_abs / len(expense_cats)
        variance = sum((v - mean_cat) ** 2 for v in expense_cats.values()) / len(
            expense_cats
        )
        std_dev = variance**0.5
        cv = std_dev / mean_cat if mean_cat > 0 else 0
        # Lower CV = more regular/predictable; CV of 0 → 100, CV >= 2 → 0
        regularity_score = max(0, min(100, int((1 - cv / 2) * 100)))
    elif len(expense_cats) == 1:
        regularity_score = 50  # Single category — neutral
    else:
        regularity_score = 50  # No data — neutral

    # --- Income coverage (20%) ---
    # Months of expenses coverable by net savings (emergency fund indicator)
    if total_expense_abs > 0 and profile.period_start and profile.period_end:
        days = (profile.period_end - profile.period_start).days
        months = max(1, days / 30)
        avg_monthly_expense = total_expense_abs / months
        net_savings = profile.total_income + profile.total_expenses  # can be negative
        if avg_monthly_expense > 0 and net_savings > 0:
            months_covered = net_savings / avg_monthly_expense
            # 6+ months covered = 100; 0 months = 0
            coverage_score = max(0, min(100, int(months_covered / 6 * 100)))
        else:
            coverage_score = 0
    else:
        coverage_score = 0

    return {
        "savings_ratio": savings_score,
        "category_diversity": diversity_score,
        "expense_regularity": regularity_score,
        "income_coverage": coverage_score,
    }
