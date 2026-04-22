"""Education agent node for the LangGraph financial pipeline.

Retrieves relevant financial education content via RAG and generates
personalized insight cards combining the user's spending data with
educational context.
"""

import json
import logging
from collections import defaultdict

from app.agents.education.prompts import get_prompt
from app.agents.llm import get_fallback_llm_client, get_llm_client
from app.agents.state import FinancialPipelineState
from app.rag.retriever import retrieve_relevant_docs

logger = logging.getLogger(__name__)

# Story 11.11: above this share of non-spending activity, emit a single
# deterministic "mostly-transfers" structural card instead of letting the LLM
# riff on the same observation multiple times.
MOSTLY_TRANSFERS_THRESHOLD = 0.70

_NON_SPENDING_KINDS = ("income", "savings", "transfer")


def _compute_kind_totals(
    transactions: list[dict],
    categorized_transactions: list[dict],
) -> tuple[dict[str, int], dict[str, int]]:
    """Join transactions with categorized_transactions and aggregate by kind.

    Returns `(spending_totals_by_category, totals_by_kind)` where amounts are
    sums of `abs(amount)` in kopiykas. Rows missing `transaction_kind` default
    to `'spending'` (matches the DB default and preserves pre-11.2 behaviour).
    """
    cat_lookup: dict[str, tuple[str, str]] = {
        c["transaction_id"]: (
            c.get("category", "other"),
            c.get("transaction_kind", "spending"),
        )
        for c in categorized_transactions
    }

    spending_totals: dict[str, int] = defaultdict(int)
    kind_totals: dict[str, int] = defaultdict(int)
    for txn in transactions:
        txn_id = txn.get("id")
        amount = txn.get("amount", 0)
        if not txn_id or txn_id not in cat_lookup:
            # Surface data-integrity issues instead of silently bucketing into
            # spending — Story 11.11 moved kind to an explicit source-of-truth
            # field; a missing join means categorization is incomplete.
            logger.warning(
                "education_uncategorized_transaction",
                extra={"txn_id": txn_id, "amount": amount},
            )
            continue
        category, kind = cat_lookup[txn_id]
        kind_totals[kind] += abs(amount)
        if kind == "spending":
            spending_totals[category] += abs(amount)

    return dict(spending_totals), dict(kind_totals)


def _build_spending_summary(
    transactions: list[dict],
    categorized_transactions: list[dict],
) -> str:
    """Build a spending summary by joining transactions (amounts) with categories.

    Filters by `transaction_kind == 'spending'` (Story 11.11). Non-spending
    kinds are summarised in a trailing "(excluded from analysis)" block so the
    LLM sees them as context without them inflating spending totals.
    """
    spending_totals, kind_totals = _compute_kind_totals(transactions, categorized_transactions)

    top_categories = sorted(spending_totals.items(), key=lambda x: x[1], reverse=True)[:3]

    lines = []
    for category, amount_kopiykas in top_categories:
        amount_uah = amount_kopiykas / 100
        lines.append(f"- {category}: ₴{amount_uah:,.2f}")

    total_spend = sum(spending_totals.values()) / 100
    spending_txn_count = sum(
        1 for c in categorized_transactions if c.get("transaction_kind", "spending") == "spending"
    )
    lines.append(f"- Total spending: ₴{total_spend:,.2f}")
    lines.append(f"- Number of transactions (analyzed): {spending_txn_count}")

    excluded_lines = []
    for kind in _NON_SPENDING_KINDS:
        amount_kopiykas = kind_totals.get(kind, 0)
        if amount_kopiykas > 0:
            excluded_lines.append(f"- {kind}: ₴{amount_kopiykas / 100:,.2f}")
    if excluded_lines:
        lines.append("(excluded from analysis)")
        lines.extend(excluded_lines)

    return "\n".join(lines)


def _parse_insight_cards(content: str) -> list[dict]:
    """Parse JSON array from LLM response into insight card dicts."""
    text = content.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    cards = json.loads(text)
    if not isinstance(cards, list):
        raise ValueError("LLM response is not a JSON array")

    valid_cards = []
    for card in cards:
        if isinstance(card, dict) and "headline" in card:
            valid_cards.append({
                "headline": card.get("headline", ""),
                "key_metric": card.get("key_metric", ""),
                "why_it_matters": card.get("why_it_matters", ""),
                "deep_dive": card.get("deep_dive", ""),
                "severity": card.get("severity", "info"),
                "category": card.get("category", "other"),
                "card_type": card.get("card_type", "insight"),
                "subscription": card.get("subscription"),
            })
    return valid_cards


def _build_subscription_cards(detected_subscriptions: list[dict]) -> list[dict]:
    """Deterministically build subscription alert card dicts from pipeline state.

    Runs before the LLM call; no LLM/RAG involvement. One card per detected
    subscription, with all user-facing fields pre-rendered so the frontend can
    display without recomputation.
    """
    cards: list[dict] = []
    for sub in detected_subscriptions:
        monthly_uah = sub["estimated_monthly_cost_kopiykas"] / 100
        why_it_matters = (
            f"You have an {'inactive' if not sub['is_active'] else 'active'} "
            f"{sub['billing_frequency']} subscription to {sub['merchant_name']}."
        )
        if sub["is_active"]:
            deep_dive = f"Last charge: {sub['last_charge_date']}. Currently active."
        else:
            deep_dive = (
                f"Last charge: {sub['last_charge_date']}. "
                f"Inactive for {sub['months_with_no_activity']} month(s)."
            )
        cards.append({
            "headline": f"{sub['merchant_name']} subscription",
            "key_metric": f"₴{monthly_uah:,.2f}/month",
            "why_it_matters": why_it_matters,
            "deep_dive": deep_dive,
            "severity": sub.get("severity", "info"),
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
        })
    return cards


_MOSTLY_TRANSFERS_COPY = {
    "en": {
        "headline": "Your statement is mostly transfers",
        "key_metric_fmt": "{pct}% of activity",
        "why_it_matters_fmt": (
            "{pct}% of this upload's activity moved between accounts rather than being spent. "
            "Insights below focus only on the remaining spending."
        ),
        "deep_dive": (
            "When most of a statement is transfers, spending-pattern insights get noisy. "
            "We've filtered them out; if you want insights on transfers themselves, upload "
            "a statement from the destination account."
        ),
    },
    "uk": {
        "headline": "Ваша виписка — переважно перекази",
        "key_metric_fmt": "{pct}% активності",
        "why_it_matters_fmt": (
            "{pct}% руху коштів у цій виписці — це перекази між рахунками, а не витрати. "
            "Інсайти нижче враховують лише справжні витрати."
        ),
        "deep_dive": (
            "Коли більшість виписки — це перекази, шаблони витрат стають галасливими. "
            "Ми відфільтрували їх; якщо хочете побачити інсайти по самих переказах, "
            "завантажте виписку з рахунку-одержувача."
        ),
    },
}


def _build_mostly_transfers_card(
    kind_totals: dict[str, int],
    locale: str,
    threshold: float = MOSTLY_TRANSFERS_THRESHOLD,
) -> dict | None:
    """Return a single deterministic "mostly-transfers" card or None.

    Threshold comparison is strictly `>`: exactly-at-threshold returns None.
    """
    total_abs = sum(kind_totals.values())
    if total_abs == 0:
        return None
    non_spending_abs = total_abs - kind_totals.get("spending", 0)
    if non_spending_abs / total_abs <= threshold:
        return None

    transfer_pct = round(100 * non_spending_abs / total_abs)
    copy = _MOSTLY_TRANSFERS_COPY.get(locale, _MOSTLY_TRANSFERS_COPY["uk"])
    return {
        "headline": copy["headline"],
        "key_metric": copy["key_metric_fmt"].format(pct=transfer_pct),
        "why_it_matters": copy["why_it_matters_fmt"].format(pct=transfer_pct),
        "deep_dive": copy["deep_dive"],
        "severity": "info",
        "category": "transfers",
        "card_type": "structuralCard",
        "subscription": None,
    }


def education_node(state: FinancialPipelineState) -> FinancialPipelineState:
    """LangGraph node: generate personalized financial education insight cards."""
    job_id = state["job_id"]
    user_id = state["user_id"]
    log_ctx = {"job_id": job_id, "user_id": user_id}
    # Build deterministic subscription cards up-front so the except branch
    # can still surface them if the LLM/RAG path raises.
    subscription_cards = _build_subscription_cards(state.get("detected_subscriptions", []))
    structural_cards: list[dict] = []

    try:
        categorized = state.get("categorized_transactions", [])
        if not categorized:
            logger.info("education_skipped", extra={**log_ctx, "step": "education", "reason": "no_categorized_transactions"})
            completed = list(state.get("completed_nodes", []))
            completed.append("education")
            return {**state, "insight_cards": subscription_cards, "step": "education", "completed_nodes": completed, "failed_node": None}

        locale = state.get("locale", "uk")
        literacy_level = state.get("literacy_level", "beginner")

        # Story 11.11: compute kind totals up-front so we can both emit a
        # deterministic mostly-transfers card and short-circuit the LLM path
        # when the statement has zero spending to analyse.
        _, kind_totals = _compute_kind_totals(state.get("transactions", []), categorized)
        mostly_transfers = _build_mostly_transfers_card(kind_totals, locale)
        if mostly_transfers is not None:
            structural_cards.append(mostly_transfers)

        if mostly_transfers is not None and kind_totals.get("spending", 0) == 0:
            logger.info(
                "education_mostly_transfers_short_circuit",
                extra={**log_ctx, "step": "education", "locale": locale},
            )
            completed = list(state.get("completed_nodes", []))
            completed.append("education")
            return {
                **state,
                "insight_cards": subscription_cards + structural_cards,
                "step": "education",
                "completed_nodes": completed,
                "failed_node": None,
            }

        spending_summary = _build_spending_summary(
            state.get("transactions", []),
            categorized,
        )

        # RAG retrieval
        rag_docs = retrieve_relevant_docs(
            query=spending_summary,
            language=locale,
            top_k=5,
        )
        rag_context = "\n\n".join(
            f"[{doc['doc_id']} — {doc['chunk_type']}]\n{doc['content']}"
            for doc in rag_docs
        )

        # Build prompt
        prompt_template = get_prompt(locale, literacy_level)
        prompt = prompt_template.format(
            user_context=spending_summary,
            rag_context=rag_context if rag_context else "No educational content available.",
        )

        # Call LLM with fallback
        try:
            llm = get_llm_client()
            response = llm.invoke(prompt)
        except Exception as primary_exc:
            logger.warning("Primary LLM failed for education, trying fallback: %s", primary_exc, extra=log_ctx)
            llm = get_fallback_llm_client()
            response = llm.invoke(prompt)

        cards = _parse_insight_cards(response.content)
        # Story 8.3: override LLM-assigned severity with triage-computed
        # severity for matching categories. Cards whose category isn't in
        # triage_map keep the LLM-assigned severity.
        triage_map = state.get("triage_category_severity_map", {})
        if triage_map:
            cards = [
                {**card, "severity": triage_map.get(card.get("category", ""), card.get("severity", "info"))}
                for card in cards
            ]
        # Subscription alert cards are prepended so they appear first in the
        # feed for this upload — the LLM never sees subscription data.
        all_cards = subscription_cards + structural_cards + cards

        # Observability for Story 3.9: sample every key_metric > 30 chars so
        # prompt drift toward compound/verbose metrics is visible without
        # blocking LLM output. 30 is the prior constraint — anything longer
        # is a candidate for future prompt tuning review.
        for card in cards:
            metric = card.get("key_metric", "")
            if len(metric) > 30:
                logger.info(
                    "key_metric_length_over_30",
                    extra={**log_ctx, "step": "education", "length": len(metric), "value": metric[:120]},
                )

        logger.info(
            "education_completed",
            extra={
                **log_ctx,
                "step": "education",
                "cards_generated": len(cards),
                "subscription_cards": len(subscription_cards),
                "locale": locale,
                "literacy_level": literacy_level,
            },
        )
        completed = list(state.get("completed_nodes", []))
        completed.append("education")
        return {**state, "insight_cards": all_cards, "step": "education", "completed_nodes": completed, "failed_node": None}

    except Exception as exc:
        from app.agents.circuit_breaker import CircuitBreakerOpenError
        if isinstance(exc, CircuitBreakerOpenError):
            # Propagate circuit breaker errors so LangGraph checkpointing
            # preserves prior node results for retry
            raise
        if isinstance(exc, AssertionError):
            # Tests use AssertionError on patched dependencies to prove a code
            # path is NOT taken; swallowing it here would let regressions in
            # the short-circuit / no-LLM-call invariants pass silently.
            raise
        logger.error("education_failed", extra={**log_ctx, "step": "education"}, exc_info=True)
        # Subscription cards are deterministic — surface them even when the
        # LLM path fails, so the user still sees detected subscriptions.
        return {**state, "insight_cards": subscription_cards + structural_cards, "step": "education", "failed_node": "education"}
