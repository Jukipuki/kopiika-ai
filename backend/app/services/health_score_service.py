import uuid
from datetime import UTC, datetime
from sqlalchemy import func
from sqlmodel import Session, desc, select
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.models.financial_health_score import FinancialHealthScore
from app.models.financial_profile import FinancialProfile
from app.models.transaction import Transaction


def calculate_health_score(
    session: Session, user_id: uuid.UUID
) -> FinancialHealthScore:
    """Calculate and persist a financial health score from the user's profile (sync, for Celery)."""
    profile = session.exec(
        select(FinancialProfile).where(FinancialProfile.user_id == user_id)
    ).first()

    if not profile:
        raise ValueError("No financial profile — cannot calculate score")

    breakdown = _compute_breakdown(session, user_id, profile)

    # Weighted average with re-normalization over non-null components.
    # `savings_ratio` may be None when the user has no income-kind transactions
    # (AC #2); in that case redistribute its weight over the remaining three
    # components so the final score stays on a 0–100 scale.
    weights = {
        "savings_ratio": 0.4,
        "category_diversity": 0.2,
        "expense_regularity": 0.2,
        "income_coverage": 0.2,
    }
    pairs = [
        (breakdown[key], weights[key])
        for key in weights
        if breakdown[key] is not None
    ]
    total_weight = sum(w for _, w in pairs)
    if total_weight > 0:
        final_score = int(round(sum(s * w for s, w in pairs) / total_weight))
    else:
        final_score = 0
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


def _compute_breakdown(
    session: Session, user_id: uuid.UUID, profile: FinancialProfile
) -> dict[str, int | None]:
    """Compute the four component scores from profile/transaction data.

    Returns a dict with keys `savings_ratio`, `category_diversity`,
    `expense_regularity`, `income_coverage`. `savings_ratio` is `int | None` —
    `None` means the user has no `transaction_kind='income'` entries in the
    period and the UI must render this as "Not enough data yet" while the
    final score is re-normalized over the remaining three components (see
    `calculate_health_score`).
    """

    # --- Savings ratio (40%) — read transaction_kind directly (Story 4.9) ---
    # Short-circuit on empty profile: no period → no transactions → no data.
    if profile.period_start is None or profile.period_end is None:
        savings_score: int | None = None
    else:
        kind_rows = session.exec(
            select(
                Transaction.transaction_kind,
                func.sum(func.abs(Transaction.amount)),
            )
            .where(Transaction.user_id == user_id)
            .where(Transaction.date >= profile.period_start)
            .where(Transaction.date <= profile.period_end)
            .group_by(Transaction.transaction_kind)
        ).all()
        kind_totals: dict[str, int] = {kind: int(total or 0) for kind, total in kind_rows}
        income_total = kind_totals.get("income", 0)
        savings_total = kind_totals.get("savings", 0)
        if income_total == 0:
            savings_score = None
        else:
            raw_ratio = min(1.0, max(0.0, savings_total / income_total))
            savings_score = int(round(raw_ratio * 100))

    # --- Category diversity (20%) ---
    # Penalize if >50% of expenses in a single category
    category_totals: dict[str, int] = profile.category_totals or {}
    # Since Story 4.10 `category_totals` contains only kind='spending' rows,
    # which are non-positive by sign convention. The `v < 0` filter is kept
    # as a legacy-user guard: pre-Epic-11 data defaults to kind='spending'
    # regardless of sign, so positive rows (e.g. salary) can sneak in.
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
