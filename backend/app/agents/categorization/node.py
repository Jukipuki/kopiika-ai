"""Categorization agent node for the LangGraph financial pipeline.

Two-pass categorization strategy:
1. MCC pass: Fast, free, deterministic — covers ~60% of transactions.
2. LLM pass: Batch remaining transactions 50/call — assigns category + confidence.
"""

import json
import logging
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential

from app.agents.categorization.mcc_mapping import (
    VALID_CATEGORIES,
    VALID_KINDS,
    get_mcc_category,
    kind_by_sign,
    validate_kind_category,
)
from app.agents.categorization.pre_pass import classify_pre_pass
from app.agents.circuit_breaker import CircuitBreakerOpenError, record_failure, record_success
from app.agents.llm import get_fallback_llm_client, get_llm_client
from app.agents.state import FinancialPipelineState
from app.core.config import settings

logger = logging.getLogger(__name__)


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
  {"id": "ex-17", "category": "other", "transaction_kind": "income", "confidence": 0.95},
  {"id": "ex-18", "category": "transfers", "transaction_kind": "transfer", "confidence": 0.9},
  {"id": "ex-19", "category": "transfers", "transaction_kind": "transfer", "confidence": 0.9},
  {"id": "ex-20", "category": "transfers", "transaction_kind": "transfer", "confidence": 0.95}
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
ex-17: "Cancellation. LIQPAY*TOV ASHAN" +499.00 UAH (credit, MCC: null) → refund/cancellation inflow → category=other, kind=income

Self-transfer vs P2P (Rule 4):
ex-18: "Переказ на картку" -50000.00 UAH (debit, MCC: 4829) → generic account language, no personal name → transfers, kind=transfer (NOT transfers_p2p)
ex-19: "З Білої картки" +1125.10 UAH (credit, MCC: 4829) → inbound leg of a Monobank card-color self-transfer → transfers, kind=transfer
ex-20: "Конвертація UAH → USD" -50000.00 UAH (debit, MCC: 4829) → currency conversion between own accounts → transfers, kind=transfer"""


_RULE_5_8_BLOCK = """\
5. Self-transfer by IBAN (Story 11.10).
   When a transaction carries counterparty fields and `is_self_iban` is true,
   the counterparty account is a KNOWN account of the user. Classify as
   transfers, kind=transfer with confidence ≥ 0.98. Rule 5 overrides Rule 4
   (description-based self-transfer) when signals conflict — IBAN match is
   deterministic, description match is heuristic.

6. Ukrainian State Treasury / Tax Service (Rule 6).
   When `counterparty_tax_id_kind == "treasury"`:
     - Outflow → category=government, kind=spending (tax payments).
     - Inflow → category=other, kind=income (tax refunds).

7. RNOKPP (10-digit individual tax ID, Rule 7).
   When `counterparty_tax_id_kind == "rnokpp_10"` (individual counterparty):
     - Inflow → category=other, kind=income (payment received from individual).
     - Outflow → category=transfers_p2p, kind=spending.

8. EDRPOU (8-digit legal-entity tax ID, Rule 8).
   When `counterparty_tax_id_kind == "edrpou_8"` (non-Treasury legal entity):
     - Inflow → category=other, kind=income (business income).
     - Outflow → classify by description per existing rules. Rule 8 does NOT
       auto-categorize outbound payments to legal entities — description
       remains authoritative for expense bucketing.

Rule precedence: Rule 5 > Rule 6 > Rule 4 > Rule 7 / Rule 8."""


def _counterparty_block(txn: dict) -> str:
    """Render the counterparty block for one row, or empty string if absent."""
    has_any = any(
        txn.get(k)
        for k in ("counterparty_name", "counterparty_tax_id", "counterparty_account")
    )
    if not has_any and not txn.get("is_self_iban"):
        return ""
    parts = []
    name = txn.get("counterparty_name")
    tax = txn.get("counterparty_tax_id")
    acct = txn.get("counterparty_account")
    kind = txn.get("counterparty_tax_id_kind") or "unknown"
    if name:
        parts.append(f'name="{name}"')
    if tax:
        parts.append(f'tax_id="{tax}" (kind={kind})')
    if acct:
        parts.append(f'account="{acct}"')
    parts.append(f"is_self_iban={bool(txn.get('is_self_iban'))}")
    return "    counterparty: " + ", ".join(parts)


def _build_prompt(transactions: list[dict]) -> str:
    """Build the two-axis (category + transaction_kind) categorization prompt.

    Each transaction line carries signed UAH amount, direction (debit/credit),
    and MCC (or "null"). The prompt ships the 19-category vocabulary, the
    kind×category matrix rules (tech spec §2.3), and 7 few-shot examples.
    Rows carrying counterparty fields (PE statements) also ship a counterparty
    block consumed by Rule 5-8 (Story 11.10).
    """
    lines = []
    any_counterparty = False
    for i, txn in enumerate(transactions, start=1):
        amount_uah_str = f"{txn['amount'] / 100:+.2f} UAH"
        direction = "credit" if txn["amount"] > 0 else "debit"
        mcc_val = txn.get("mcc")
        mcc_str = str(mcc_val) if mcc_val is not None else "null"
        lines.append(
            f'{i}. [{txn["id"]}] "{txn["description"]}" {amount_uah_str} '
            f'({direction}, MCC: {mcc_str})'
        )
        cp_block = _counterparty_block(txn)
        if cp_block:
            lines.append(cp_block)
            any_counterparty = True
    txn_block = "\n".join(lines)
    # The Rule 5-8 block is documentation-only for the LLM; deterministic
    # post-processing enforces Rule 5/6 regardless. Omit it when no row in the
    # batch has counterparty data (card-only regression path) so card users
    # get bitwise-identical prompts to pre-11.10.
    rule_5_8 = f"\n\n{_RULE_5_8_BLOCK}" if any_counterparty else ""

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
        "4. Self-transfer between own accounts (MCC 4829, no personal name).\n"
        "   When MCC is 4829 AND the description contains ONLY generic\n"
        "   account/card/currency language (\"Переказ на картку\",\n"
        "   \"Transfer to card\", \"На гривневий рахунок\", \"To USD account\",\n"
        "   \"З <color> картки\", \"From <currency> account\",\n"
        "   \"Конвертація валют\", \"Переказ між власними рахунками\") AND\n"
        "   the description does NOT contain any of: a personal full name\n"
        "   (Cyrillic or Latin first+last/patronymic), a business marker\n"
        "   (ФОП, FOP, LIQPAY*, TOV, LLC), a fund/charity marker («...»,\n"
        "   named fund), a deposit/investment marker (\"депозит\", \"deposit\",\n"
        "   \"вклад\", \"investment\") → transfers, kind=transfer. This is\n"
        "   the default for MCC 4829 debits that survive the other rules —\n"
        "   NOT transfers_p2p (which requires a personal full name).\n\n"
        f"{_FEW_SHOT_BLOCK}"
        f"{rule_5_8}\n\n"
        f"Transactions (signed UAH, negative=outflow, positive=inflow):\n{txn_block}\n\n"
        "Return ONLY a JSON array (no markdown, no explanation):\n"
        '[{"id": "uuid", "category": "groceries", "transaction_kind": "spending", "confidence": 0.97}, ...]'
    )


def _apply_counterparty_rules(
    txn: dict,
    result: dict,
    log_ctx: dict[str, str] | None = None,
    *,
    row_index: int | None = None,
) -> dict:
    """Deterministic Rule 5/6 enforcement and Rule 7/8 advisory logging.

    Rule 5/6: if the deterministic verdict disagrees with the LLM, override.
    Rule 7/8: log what rule the LLM's answer aligned with, but do not override.
    Emits `categorization.counterparty_rule_hit` on any rule match; emits
    `categorization.counterparty_rule_override` when we overrode the LLM.
    """
    is_self = bool(txn.get("is_self_iban"))
    tax_kind = txn.get("counterparty_tax_id_kind") or "unknown"
    amount = txn.get("amount", 0)
    rule_number: int | None = None
    deterministic: dict | None = None

    if is_self:
        rule_number = 5
        deterministic = {"category": "transfers", "transaction_kind": "transfer"}
    elif tax_kind == "treasury":
        rule_number = 6
        if amount < 0:
            deterministic = {"category": "government", "transaction_kind": "spending"}
        else:
            deterministic = {"category": "other", "transaction_kind": "income"}
    elif tax_kind == "rnokpp_10":
        rule_number = 7  # advisory only
    elif tax_kind == "edrpou_8":
        rule_number = 8  # advisory only

    if rule_number is None:
        return result

    log_payload = {
        **(log_ctx or {}),
        "transaction_row_index": row_index,
        "transaction_row_id": txn.get("id"),
        "rule_number": rule_number,
        "counterparty_tax_id_kind": tax_kind if tax_kind != "unknown" else None,
        "is_self_iban": is_self,
    }
    logger.info("categorization.counterparty_rule_hit", extra=log_payload)

    if deterministic is not None:
        if (
            result.get("category") != deterministic["category"]
            or result.get("transaction_kind") != deterministic["transaction_kind"]
        ):
            logger.info(
                "categorization.counterparty_rule_override",
                extra={
                    **log_payload,
                    "llm_category": result.get("category"),
                    "llm_kind": result.get("transaction_kind"),
                    "deterministic_category": deterministic["category"],
                    "deterministic_kind": deterministic["transaction_kind"],
                },
            )
        result["category"] = deterministic["category"]
        result["transaction_kind"] = deterministic["transaction_kind"]
        result["confidence_score"] = 1.0
        result["flagged"] = False
        result["uncategorized_reason"] = None
        # Sentinel consumed by the post-LLM threshold loop to skip re-flagging —
        # a deterministic rule must not be clobbered by a raised threshold.
        result["deterministic_rule"] = rule_number
    return result


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
        for row_index, txn in enumerate(transactions):
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
                entry = {
                    "transaction_id": txn["id"],
                    "category": category,
                    "confidence_score": confidence_score,
                    "transaction_kind": transaction_kind,
                    "flagged": False,
                    "uncategorized_reason": None,
                }
                parsed.append(_apply_counterparty_rules(txn, entry, log_ctx, row_index=row_index))
            else:
                entry = {
                    "transaction_id": txn["id"],
                    "category": "other",
                    "confidence_score": 0.0,
                    "transaction_kind": kind_by_sign(txn["amount"]),
                    "flagged": False,
                    "uncategorized_reason": None,
                }
                parsed.append(_apply_counterparty_rules(txn, entry, log_ctx, row_index=row_index))
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
    upload_id = state.get("upload_id")
    log_ctx = {"job_id": job_id, "user_id": user_id, "upload_id": upload_id}

    transactions = state["transactions"]
    batch_size = settings.CATEGORIZATION_BATCH_SIZE
    # Story 11.8: three-tier routing replaces the single
    # CATEGORIZATION_CONFIDENCE_THRESHOLD. See config.py for semantics.
    soft_flag_threshold = settings.CATEGORIZATION_SOFT_FLAG_THRESHOLD
    auto_apply_threshold = settings.CATEGORIZATION_AUTO_APPLY_THRESHOLD

    categorized: list[dict] = []
    needs_llm: list[dict] = []

    # Pass 0: Description pre-pass — overrides MCC for cash-action narration
    remaining_after_pre_pass: list[dict] = []
    for txn in transactions:
        pre_result = classify_pre_pass(txn)
        if pre_result is not None:
            categorized.append(pre_result)
        else:
            remaining_after_pre_pass.append(txn)
    transactions = remaining_after_pre_pass

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

        # Story 11.8: three-tier routing on LLM confidence.
        #   >= AUTO_APPLY                         → silent accept
        #   [SOFT_FLAG, AUTO_APPLY)               → accept + emit soft-flag telemetry
        #   < SOFT_FLAG                           → route to review queue
        #                                           (flagged, uncategorized,
        #                                            suggested_category/kind carried)
        # Rows stamped with `deterministic_rule` (Story 11.10 Rule 5/6) skip the
        # threshold gate — a deterministic counterparty verdict must not be
        # clobbered by an operator raising a threshold.
        for r in llm_results:
            if r.pop("deterministic_rule", None) is not None:
                r["flagged"] = False
                categorized.append(r)
                continue

            # Pre-existing non-low-confidence flags (llm_unavailable, parse_failure)
            # short-circuit: they bypass the tier decision entirely — the row is
            # already uncategorized with no suggestion to carry.
            if r.get("uncategorized_reason") is not None:
                r["flagged"] = True
                r["category"] = "uncategorized"
                categorized.append(r)
                continue

            conf = r["confidence_score"]
            tx_ev_ctx = {
                **log_ctx,
                "tx_id": r.get("transaction_id"),
                "confidence": conf,
            }

            if conf >= auto_apply_threshold:
                r["flagged"] = False
            elif conf >= soft_flag_threshold:
                # Soft-flag: keep the LLM's category/kind, no flag, emit telemetry.
                r["flagged"] = False
                logger.info(
                    "categorization.confidence_tier",
                    extra={**tx_ev_ctx, "tier": "soft-flag"},
                )
            else:
                # Queue tier: preserve original suggestion for the persist path
                # to insert into uncategorized_review_queue, then overwrite the
                # live row with uncategorized per Story 6.3 contract.
                r["suggested_category"] = r.get("category")
                r["suggested_kind"] = r.get("transaction_kind")
                r["flagged"] = True
                r["uncategorized_reason"] = "low_confidence"
                r["category"] = "uncategorized"
                logger.info(
                    "categorization.confidence_tier",
                    extra={**tx_ev_ctx, "tier": "queue"},
                )
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
