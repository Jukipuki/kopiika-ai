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


def _build_spending_summary(
    transactions: list[dict],
    categorized_transactions: list[dict],
) -> str:
    """Build a spending summary by joining transactions (amounts) with categories.

    transactions contain {id, amount, ...}; categorized_transactions contain
    {transaction_id, category, ...}. We join on id == transaction_id to get
    the amount per category.
    """
    cat_lookup = {c["transaction_id"]: c.get("category", "other") for c in categorized_transactions}

    totals: dict[str, int] = defaultdict(int)
    for txn in transactions:
        category = cat_lookup.get(txn.get("id", ""), "other")
        # Amounts are in kopiykas (cents), negative = spending
        amount = abs(txn.get("amount", 0))
        totals[category] += amount

    # Sort by total spend descending, take top 3
    top_categories = sorted(totals.items(), key=lambda x: x[1], reverse=True)[:3]

    lines = []
    for category, amount_kopiykas in top_categories:
        amount_uah = amount_kopiykas / 100
        lines.append(f"- {category}: ₴{amount_uah:,.2f}")

    total_spend = sum(totals.values()) / 100
    lines.append(f"- Total spending: ₴{total_spend:,.2f}")
    lines.append(f"- Number of transactions: {len(categorized_transactions)}")

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
                "severity": card.get("severity", "medium"),
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
        })
    return cards


def education_node(state: FinancialPipelineState) -> FinancialPipelineState:
    """LangGraph node: generate personalized financial education insight cards."""
    job_id = state["job_id"]
    user_id = state["user_id"]
    log_ctx = {"job_id": job_id, "user_id": user_id}
    # Build deterministic subscription cards up-front so the except branch
    # can still surface them if the LLM/RAG path raises.
    subscription_cards = _build_subscription_cards(state.get("detected_subscriptions", []))

    try:
        categorized = state.get("categorized_transactions", [])
        if not categorized:
            logger.info("education_skipped", extra={**log_ctx, "step": "education", "reason": "no_categorized_transactions"})
            completed = list(state.get("completed_nodes", []))
            completed.append("education")
            return {**state, "insight_cards": subscription_cards, "step": "education", "completed_nodes": completed, "failed_node": None}

        locale = state.get("locale", "uk")
        literacy_level = state.get("literacy_level", "beginner")
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
        # Subscription alert cards are prepended so they appear first in the
        # feed for this upload — the LLM never sees subscription data.
        all_cards = subscription_cards + cards

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
        logger.error("education_failed", extra={**log_ctx, "step": "education"}, exc_info=True)
        # Subscription cards are deterministic — surface them even when the
        # LLM path fails, so the user still sees detected subscriptions.
        return {**state, "insight_cards": subscription_cards, "step": "education", "failed_node": "education"}
