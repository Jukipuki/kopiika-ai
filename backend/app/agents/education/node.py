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
            })
    return valid_cards


def education_node(state: FinancialPipelineState) -> FinancialPipelineState:
    """LangGraph node: generate personalized financial education insight cards."""
    job_id = state["job_id"]
    user_id = state["user_id"]
    log_ctx = {"job_id": job_id, "user_id": user_id}

    try:
        categorized = state.get("categorized_transactions", [])
        if not categorized:
            logger.info("education_skipped", extra={**log_ctx, "step": "education", "reason": "no_categorized_transactions"})
            completed = list(state.get("completed_nodes", []))
            completed.append("education")
            return {**state, "insight_cards": [], "step": "education", "completed_nodes": completed, "failed_node": None}

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

        logger.info(
            "education_completed",
            extra={**log_ctx, "step": "education", "cards_generated": len(cards), "locale": locale, "literacy_level": literacy_level},
        )
        completed = list(state.get("completed_nodes", []))
        completed.append("education")
        return {**state, "insight_cards": cards, "step": "education", "completed_nodes": completed, "failed_node": None}

    except Exception as exc:
        from app.agents.circuit_breaker import CircuitBreakerOpenError
        if isinstance(exc, CircuitBreakerOpenError):
            # Propagate circuit breaker errors so LangGraph checkpointing
            # preserves prior node results for retry
            raise
        logger.error("education_failed", extra={**log_ctx, "step": "education"}, exc_info=True)
        return {**state, "insight_cards": [], "step": "education", "failed_node": "education"}
