"""Categorization agent node for the LangGraph financial pipeline.

Two-pass categorization strategy:
1. MCC pass: Fast, free, deterministic — covers ~60% of transactions.
2. LLM pass: Batch remaining transactions 50/call — assigns category + confidence.
"""

import json
import logging
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential

from app.agents.categorization.mcc_mapping import VALID_CATEGORIES, get_mcc_category
from app.agents.circuit_breaker import CircuitBreakerOpenError, record_failure, record_success
from app.agents.llm import get_fallback_llm_client, get_llm_client
from app.agents.state import FinancialPipelineState
from app.core.config import settings

logger = logging.getLogger(__name__)


def _build_prompt(transactions: list[dict]) -> str:
    """Build the categorization prompt for a batch of transactions."""
    categories = (
        "groceries, restaurants, transport, entertainment, utilities, healthcare, "
        "shopping, travel, education, finance, subscriptions, fuel, atm_cash, government, other"
    )
    lines = []
    for i, txn in enumerate(transactions, start=1):
        amount_uah = f"{txn['amount'] / 100:.2f} UAH"
        lines.append(f'{i}. [{txn["id"]}] "{txn["description"]}" {amount_uah}')

    txn_block = "\n".join(lines)
    return (
        "You are a financial transaction categorizer for Ukrainian bank statements.\n"
        f"Categorize each transaction into EXACTLY ONE of these categories:\n{categories}\n\n"
        f"Transactions (amounts in UAH):\n{txn_block}\n\n"
        'Return ONLY a JSON array (no markdown, no explanation):\n'
        '[{"id": "uuid", "category": "groceries", "confidence": 0.97}, ...]'
    )


def _parse_llm_response(
    content: str, transactions: list[dict], log_ctx: dict[str, str] | None = None,
) -> list[dict]:
    """Parse JSON array from LLM response. Falls back to other=0.0 on parse failure."""
    try:
        # Strip markdown code fences if present
        text = content.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        results = json.loads(text)
        if not isinstance(results, list):
            raise ValueError("LLM response is not a JSON array")
        # Index by id for quick lookup
        by_id = {r["id"]: r for r in results if "id" in r}
        parsed = []
        for txn in transactions:
            r = by_id.get(txn["id"])
            if r:
                raw_category = r.get("category", "other")
                category = raw_category if raw_category in VALID_CATEGORIES else "other"
                parsed.append({
                    "transaction_id": txn["id"],
                    "category": category,
                    "confidence_score": float(r.get("confidence", 0.0)),
                    "uncategorized_reason": None,
                })
            else:
                parsed.append({
                    "transaction_id": txn["id"],
                    "category": "other",
                    "confidence_score": 0.0,
                    "uncategorized_reason": None,
                })
        return parsed
    except Exception as exc:
        logger.warning("Failed to parse LLM response: %s", exc, extra=log_ctx or {})
        return [
            {
                "transaction_id": txn["id"],
                "category": "uncategorized",
                "confidence_score": 0.0,
                "uncategorized_reason": "parse_failure",
            }
            for txn in transactions
        ]


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=8))
def _invoke_llm(llm: Any, prompt: str) -> Any:
    """Invoke LLM with retry/exponential-backoff."""
    return llm.invoke(prompt)


def _categorize_batch(
    transactions: list[dict], llm: Any, log_ctx: dict[str, str] | None = None,
) -> tuple[list[dict], int]:
    """Categorize a batch of transactions using the given LLM.

    Returns (results, tokens_used).
    """
    prompt = _build_prompt(transactions)
    response = _invoke_llm(llm, prompt)
    tokens = 0
    if hasattr(response, "usage_metadata") and response.usage_metadata:
        tokens = response.usage_metadata.get("total_tokens", 0)
    results = _parse_llm_response(response.content, transactions, log_ctx)
    logger.info(
        "batch_categorized",
        extra={
            **(log_ctx or {}),
            "step": "categorization",
            "batch_size": len(transactions),
            "tokens_used": tokens,
            "model": getattr(llm, "model_name", getattr(llm, "model", "unknown")),
        },
    )
    return results, tokens


def categorization_node(state: FinancialPipelineState) -> FinancialPipelineState:
    """LangGraph node: categorize all transactions using MCC codes + LLM fallback."""
    job_id = state["job_id"]
    user_id = state["user_id"]
    log_ctx = {"job_id": job_id, "user_id": user_id}

    transactions = state["transactions"]
    batch_size = settings.CATEGORIZATION_BATCH_SIZE
    confidence_threshold = settings.CATEGORIZATION_CONFIDENCE_THRESHOLD

    categorized: list[dict] = []
    needs_llm: list[dict] = []

    # Pass 1: MCC-based categorization (fast, free, no LLM)
    for txn in transactions:
        category = get_mcc_category(txn.get("mcc"))
        if category is not None:
            categorized.append({
                "transaction_id": txn["id"],
                "category": category,
                "confidence_score": 1.0,
                "flagged": False,
                "uncategorized_reason": None,
            })
        else:
            needs_llm.append(txn)

    total_tokens = state.get("total_tokens_used", 0)

    # Pass 2: LLM-based categorization for unmapped transactions
    if needs_llm:
        llm_results: list[dict] = []

        try:
            primary_llm = get_llm_client()
            for i in range(0, len(needs_llm), batch_size):
                batch = needs_llm[i : i + batch_size]
                try:
                    results, tokens = _categorize_batch(batch, primary_llm, log_ctx)
                    llm_results.extend(results)
                    total_tokens += tokens
                    record_success("anthropic")
                except CircuitBreakerOpenError:
                    raise
                except Exception as primary_exc:
                    record_failure("anthropic")
                    logger.warning(
                        "Primary LLM failed for batch, trying fallback: %s", primary_exc,
                        extra=log_ctx,
                    )
                    try:
                        fallback_llm = get_fallback_llm_client()
                        results, tokens = _categorize_batch(batch, fallback_llm, log_ctx)
                        llm_results.extend(results)
                        total_tokens += tokens
                        record_success("openai")
                    except CircuitBreakerOpenError:
                        raise
                    except Exception as fallback_exc:
                        record_failure("openai")
                        logger.error(
                            "Fallback LLM also failed for batch: %s", fallback_exc,
                            extra=log_ctx,
                        )
                        for txn in batch:
                            llm_results.append({
                                "transaction_id": txn["id"],
                                "category": "uncategorized",
                                "confidence_score": 0.0,
                                "uncategorized_reason": "llm_unavailable",
                            })
        except CircuitBreakerOpenError:
            raise
        except ValueError as exc:
            logger.warning("Primary LLM not available: %s. Trying fallback.", exc, extra=log_ctx)
            try:
                fallback_llm = get_fallback_llm_client()
                for i in range(0, len(needs_llm), batch_size):
                    batch = needs_llm[i : i + batch_size]
                    try:
                        results, tokens = _categorize_batch(batch, fallback_llm, log_ctx)
                        llm_results.extend(results)
                        total_tokens += tokens
                        record_success("openai")
                    except CircuitBreakerOpenError:
                        raise
                    except Exception as fb_exc:
                        record_failure("openai")
                        logger.error("Fallback LLM failed for batch: %s", fb_exc, extra=log_ctx)
                        for txn in batch:
                            llm_results.append({
                                "transaction_id": txn["id"],
                                "category": "uncategorized",
                                "confidence_score": 0.0,
                                "uncategorized_reason": "llm_unavailable",
                            })
            except CircuitBreakerOpenError:
                raise
            except ValueError as fb_exc:
                logger.error("Fallback LLM not available: %s", fb_exc, extra=log_ctx)
                for txn in needs_llm:
                    llm_results.append({
                        "transaction_id": txn["id"],
                        "category": "uncategorized",
                        "confidence_score": 0.0,
                        "uncategorized_reason": "llm_unavailable",
                    })

        # Apply flagging threshold, set reason, override category for flagged transactions
        for r in llm_results:
            r["flagged"] = r["confidence_score"] < confidence_threshold
            if r["flagged"]:
                if r.get("uncategorized_reason") is None:
                    r["uncategorized_reason"] = "low_confidence"
                r["category"] = "uncategorized"
            categorized.append(r)

    completed = list(state.get("completed_nodes", []))
    completed.append("categorization")
    return {
        **state,
        "categorized_transactions": categorized,
        "total_tokens_used": total_tokens,
        "step": "categorization",
        "completed_nodes": completed,
        "failed_node": None,
    }
