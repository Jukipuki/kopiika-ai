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


VALID_KINDS: frozenset[str] = frozenset({"spending", "income", "savings", "transfer"})

# Per tech spec §2.3 — which categories are valid for each transaction_kind.
# `spending` is a catch-all *except* `savings` (savings transfers are their own kind).
# `income` only ever lands in `other` or `uncategorized` (incoming flows aren't
# bucketed by merchant category). `savings` and `transfer` are 1:1 with their
# eponymous categories.
KIND_CATEGORY_RULES: dict[str, frozenset[str]] = {
    "spending": VALID_CATEGORIES - frozenset({"savings"}),
    "income": frozenset({"other", "uncategorized"}),
    "savings": frozenset({"savings"}),
    "transfer": frozenset({"transfers"}),
}


def kind_by_sign(amount: int) -> str:
    """Sign-based default for `transaction_kind` until the LLM emits one (Story 11.3)."""
    return "income" if amount > 0 else "spending"


def validate_kind_category(kind: str, category: str) -> bool:
    """Return True if (kind, category) is a valid combination per the matrix.

    Does not raise — callers decide whether to raise or fall back.
    """
    allowed = KIND_CATEGORY_RULES.get(kind)
    if allowed is None:
        return False
    return category in allowed


_FEW_SHOT_BLOCK = """Few-shot examples:
[
  {"id": "ex-01", "category": "transfers", "transaction_kind": "transfer", "confidence": 0.98},
  {"id": "ex-02", "category": "savings", "transaction_kind": "savings", "confidence": 0.97},
  {"id": "ex-03", "category": "transfers_p2p", "transaction_kind": "spending", "confidence": 0.91},
  {"id": "ex-04", "category": "other", "transaction_kind": "income", "confidence": 0.95},
  {"id": "ex-05", "category": "charity", "transaction_kind": "spending", "confidence": 0.89},
  {"id": "ex-06", "category": "shopping", "transaction_kind": "spending", "confidence": 0.92},
  {"id": "ex-07", "category": "shopping", "transaction_kind": "spending", "confidence": 0.88},
  {"id": "ex-08", "category": "charity", "transaction_kind": "spending", "confidence": 0.95},
  {"id": "ex-09", "category": "charity", "transaction_kind": "spending", "confidence": 0.9},
  {"id": "ex-10", "category": "savings", "transaction_kind": "savings", "confidence": 0.95},
  {"id": "ex-11", "category": "atm_cash", "transaction_kind": "spending", "confidence": 0.95},
  {"id": "ex-12", "category": "atm_cash", "transaction_kind": "spending", "confidence": 0.95},
  {"id": "ex-13", "category": "shopping", "transaction_kind": "spending", "confidence": 0.9},
  {"id": "ex-14", "category": "shopping", "transaction_kind": "spending", "confidence": 0.9},
  {"id": "ex-15", "category": "transfers_p2p", "transaction_kind": "spending", "confidence": 0.9},
  {"id": "ex-16", "category": "other", "transaction_kind": "income", "confidence": 0.95},
  {"id": "ex-17", "category": "other", "transaction_kind": "income", "confidence": 0.95}
]

Examples explained:
ex-01: "З гривневого рахунку на Євро рахунок" -50000.00 UAH (debit, MCC: null) → self-transfer between own accounts
ex-02: "Поповнення депозиту" -19998.00 UAH (debit, MCC: 4829) → deposit top-up, not a charity
ex-03: "Марія Іванова" -1500.00 UAH (debit, MCC: null) → P2P to named individual, kind=spending
ex-04: "Зарплата Лютий 2026 ТОВ Абс Ком" +45000.00 UAH (credit, MCC: null) → salary inflow, always kind=income category=other
ex-05: "Повернись живим фонд збір" -500.00 UAH (debit, MCC: 4829) → military charity via 4829, NOT savings/transfers
ex-06: "KTS Monomarket оплата 2 з 12" -2333.00 UAH (debit, MCC: 6012) → BNPL instalment IS the purchase (kind=spending, not transfer)
ex-07: "Нова Пошта накладений платіж №5912347" -850.00 UAH (debit, MCC: 4215) → COD payment is goods purchase, not a transfer
ex-08: "Поповнення «На детектор FPV»" -100.00 UAH (debit, MCC: 4829) → charity jar for military cause, NOT savings
ex-09: "Top up «На Авто!»" -333.00 UAH (debit, MCC: 4829) → charity jar with military context, NOT savings
ex-10: "Поповнення депозиту" -199980.54 UAH (debit, MCC: 4829) → bank deposit (no quoted jar name) IS savings
ex-11: "Cash withdrawal Близенько" -1000.00 UAH (debit, MCC: 5499) → cash-action narration overrides food MCC → atm_cash
ex-12: "Видача готівки Близенько" -5000.00 UAH (debit, MCC: 5499) → Ukrainian cash-withdrawal narration → atm_cash
ex-13: "FOP Ruban Olha Heorhii" -539.00 UAH (debit, MCC: 5200) → FOP on merchant MCC → shopping, not P2P
ex-14: "LIQPAY*FOP Lutsenko Ev" -1222.00 UAH (debit, MCC: 5977) → FOP via LiqPay on merchant MCC → shopping
ex-15: "Кукушкін Роман Олексійович" -1560.00 UAH (debit, MCC: 4829) → personal name on 4829 with no merchant markers → transfers_p2p
ex-16: "Скасування. Bolt Food" +250.00 UAH (credit, MCC: 5812) → order cancellation is a reverse-direction inflow; positive amount → category=other, kind=income (merchant MCC is NOT authoritative for refunds/cancellations)
ex-17: "Cancellation. LIQPAY*TOV ASHAN" +499.00 UAH (credit, MCC: null) → refund/cancellation inflow → category=other, kind=income"""


def _build_prompt(transactions: list[dict]) -> str:
    """Build the two-axis (category + transaction_kind) categorization prompt.

    Each transaction line carries signed UAH amount, direction (debit/credit),
    and MCC (or "null"). The prompt ships the 19-category vocabulary, the
    kind×category matrix rules (tech spec §2.3), and 7 few-shot examples.
    """
    lines = []
    for i, txn in enumerate(transactions, start=1):
        amount_uah_str = f"{txn['amount'] / 100:+.2f} UAH"
        direction = "credit" if txn["amount"] > 0 else "debit"
        mcc_val = txn.get("mcc")
        mcc_str = str(mcc_val) if mcc_val is not None else "null"
        lines.append(
            f'{i}. [{txn["id"]}] "{txn["description"]}" {amount_uah_str} '
            f'({direction}, MCC: {mcc_str})'
        )
    txn_block = "\n".join(lines)

    return (
        "You are a financial transaction categorizer for Ukrainian bank statements.\n\n"
        "Each transaction has TWO axes to classify:\n\n"
        "1. category — merchant/activity classification, one of:\n"
        "   groceries, restaurants, transport, entertainment, utilities, healthcare,\n"
        "   shopping, travel, education, finance, subscriptions, fuel, atm_cash,\n"
        "   government, transfers, transfers_p2p, savings, charity, other\n\n"
        "2. transaction_kind — cash-flow classification, one of:\n"
        "   - spending: consumption outflow (groceries, rent, restaurants, donations, P2P)\n"
        "   - income: inflow (salary, refund, interest, reimbursement) — always paired with category=other\n"
        "   - savings: outflow to the user's own deposit/investment account\n"
        "   - transfer: movement between the user's own current accounts\n\n"
        "Rules:\n"
        "- transfers_p2p is ALWAYS kind=spending (P2P payments reduce net worth)\n"
        "- charity is ALWAYS kind=spending (donations reduce net worth)\n"
        "- savings category requires kind=savings\n"
        "- transfers category requires kind=transfer\n"
        "- Inflows (positive amounts) are kind=income with category=other\n"
        "- Outflows (negative amounts) with no clear category → category=other, kind=spending\n\n"
        "Disambiguation rules (surfaced by Story 11.3 golden-set measurement):\n\n"
        "1. Monobank transfers with a «quoted name» — apply in this order:\n"
        "   a. If the description contains the literal word \"депозит\",\n"
        "      \"вклад\", \"deposit\", or \"investment\" (e.g.\n"
        "      \"Поповнення депозиту «Скарбничка»\", \"Deposit top-up\"),\n"
        "      it IS savings, kind=savings — regardless of any quoted\n"
        "      product name.\n"
        "   b. Otherwise, if the description matches \"Поповнення «<name>»\"\n"
        "      or \"Top up «<name>»\" (a banka jar top-up), it is NEVER\n"
        "      savings:\n"
        "      - Quoted name references a military / humanitarian / charity\n"
        "        cause (e.g. «На ЗСУ», «Повернись живим», «На Авто!»,\n"
        "        «На детектор FPV», «Притула», «United24», any Armed Forces\n"
        "        or named-fund reference) → charity, kind=spending.\n"
        "      - Quoted name is a neutral personal goal (e.g. «На відпустку»,\n"
        "        «На iPhone», «На ремонт») → classify by theme: travel\n"
        "        (vacation/trip), shopping (gadget/car/clothes), other\n"
        "        (generic/unclear). Always kind=spending, NEVER savings.\n\n"
        "2. Cash-action narration overrides merchant MCC.\n"
        "   When description explicitly names a cash action — \"Cash withdrawal\n"
        "   <merchant>\", \"Видача готівки <merchant>\", \"Отримання готівки\" —\n"
        "   classify as atm_cash, kind=spending, regardless of the merchant\n"
        "   MCC. Cashback-at-till commonly arrives with food/retail MCCs\n"
        "   (5499, 5411) but the narrative is authoritative.\n\n"
        "3. ФОП/FOP markers indicate a registered merchant, not personal P2P.\n"
        "   When description contains \"ФОП <name>\", \"FOP <name>\", or\n"
        "   \"LIQPAY*FOP <name>\":\n"
        "   - If MCC is a specific merchant category (anything except 4829),\n"
        "     classify by the MCC — dental → healthcare, home → shopping,\n"
        "     food → restaurants.\n"
        "   - If MCC is 4829 or null, still treat the FOP marker as a\n"
        "     merchant signal — default to shopping (or other if truly\n"
        "     unclear), kind=spending. Do NOT use transfers_p2p.\n"
        "   Use transfers_p2p only when the description is a bare personal\n"
        "   name (no ФОП/FOP/LIQPAY*FOP marker, no business identifier) AND\n"
        "   the MCC is 4829 or null.\n\n"
        f"{_FEW_SHOT_BLOCK}\n\n"
        f"Transactions (signed UAH, negative=outflow, positive=inflow):\n{txn_block}\n\n"
        "Return ONLY a JSON array (no markdown, no explanation):\n"
        '[{"id": "uuid", "category": "groceries", "transaction_kind": "spending", "confidence": 0.97}, ...]'
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
                raw_kind = r.get("transaction_kind")
                transaction_kind = raw_kind if raw_kind in VALID_KINDS else kind_by_sign(txn["amount"])
                confidence_score = float(r.get("confidence", 0.0))
                # `uncategorized` is a pipeline sentinel, not part of the LLM's vocabulary
                # — if the model emits it anyway, zero confidence so downstream flagging fires.
                if category == "uncategorized":
                    confidence_score = 0.0
                if not validate_kind_category(transaction_kind, category):
                    category = "uncategorized"
                    transaction_kind = kind_by_sign(txn["amount"])
                    confidence_score = 0.0
                parsed.append({
                    "transaction_id": txn["id"],
                    "category": category,
                    "confidence_score": confidence_score,
                    "transaction_kind": transaction_kind,
                    "flagged": False,
                    "uncategorized_reason": None,
                })
            else:
                parsed.append({
                    "transaction_id": txn["id"],
                    "category": "other",
                    "confidence_score": 0.0,
                    "transaction_kind": kind_by_sign(txn["amount"]),
                    "flagged": False,
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
                "transaction_kind": kind_by_sign(txn["amount"]),
                "flagged": True,
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
        if category is None:
            needs_llm.append(txn)
            continue
        # Derive kind from sign so an MCC-matched inflow (e.g., refund) is not mis-kinded
        # as spending. If the sign-derived kind is incompatible with the MCC's category
        # (e.g., positive amount + "groceries" → income+groceries is matrix-invalid),
        # defer to the LLM rather than emit a confidently-wrong pair.
        kind = kind_by_sign(txn["amount"])
        if not validate_kind_category(kind, category):
            needs_llm.append(txn)
            continue
        categorized.append({
            "transaction_id": txn["id"],
            "category": category,
            "confidence_score": 0.95,
            "transaction_kind": kind,
            "flagged": False,
            "uncategorized_reason": None,
        })

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
                                "transaction_kind": kind_by_sign(txn["amount"]),
                                "flagged": True,
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
                                "transaction_kind": kind_by_sign(txn["amount"]),
                                "flagged": True,
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
                        "transaction_kind": kind_by_sign(txn["amount"]),
                        "flagged": True,
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
