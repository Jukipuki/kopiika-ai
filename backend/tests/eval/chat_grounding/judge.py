"""Single-axis LLM-as-judge for the chat-grounding eval harness (Story 10.6a).

Sibling of ``tests/eval/rag/judge.py`` (Story 9.1) but deliberately simplified
to a single ``groundedness`` axis (0|1|2). Multi-axis scoring (relevance,
language, overall) is a RAG-harness concern; chat grounding is the *single*
contract from architecture.md L1711 — did the model claim something the
sources don't support? — and adding axes would invite the judge to drift on
what "grounding" means.

Reuses ``app.agents.llm.get_llm_client()`` for provider-portability so a
future Bedrock / model swap routes here transparently.
"""

from __future__ import annotations

import json
import logging

from langchain_core.messages import HumanMessage

from app.agents.llm import get_llm_client

logger = logging.getLogger(__name__)


_JUDGE_PROMPT_EN = """\
You are a strict evaluation judge for a financial-literacy chat agent. Score \
the candidate answer on a single axis: GROUNDEDNESS — whether every claim in \
the candidate answer is supported by the SOURCES the agent had access to.

Rubric:
- 2: every claim in the candidate is supported by the SOURCES, OR the \
candidate is a careful refusal ("I don't have data to support that") when \
the SOURCES lack the information needed.
- 1: partially supported — some claims are grounded but others are not.
- 0: the candidate contains claims not supported by the SOURCES \
(hallucination), OR invents specific numbers / dates / merchants the \
SOURCES do not show.

Question: {question}

SOURCES the agent had access to (transactions snippet + RAG corpus snippets):
{sources}

Candidate answer:
{candidate_answer}

Respond with STRICT JSON ONLY — no markdown fences, no prose preamble. Use \
exactly this schema:
{{"groundedness": <int 0-2>, "rationale": "<one short sentence>"}}"""


_JUDGE_PROMPT_UK = """\
Ти — суворий оцінювач відповідей фінансового чат-асистента. Оціни кандидатну \
відповідь за одним критерієм: GROUNDEDNESS — чи кожне твердження в \
відповіді підкріплене ДЖЕРЕЛАМИ, до яких мав доступ асистент.

Шкала:
- 2: кожне твердження підкріплене ДЖЕРЕЛАМИ, АБО відповідь — це обережна \
відмова ("у мене недостатньо даних"), коли ДЖЕРЕЛА не містять потрібної \
інформації.
- 1: частково підкріплено — деякі твердження мають опору, інші ні.
- 0: відповідь містить твердження, не підкріплені ДЖЕРЕЛАМИ (галюцинація), \
АБО вигадує конкретні числа / дати / контрагентів, яких немає в ДЖЕРЕЛАХ.

Запитання: {question}

ДЖЕРЕЛА, до яких мав доступ асистент (виписка по транзакціях + RAG-фрагменти):
{sources}

Кандидатна відповідь:
{candidate_answer}

Відповідай ВИКЛЮЧНО суворим JSON — без markdown-обгортки, без преамбули. \
Використовуй цю схему:
{{"groundedness": <int 0-2>, "rationale": "<одне коротке речення>"}}"""


def _tokens_from_response(response) -> int:
    usage = getattr(response, "usage_metadata", None) or {}
    if isinstance(usage, dict):
        return int(usage.get("input_tokens", 0)) + int(usage.get("output_tokens", 0))
    return 0


def _format_sources(transactions: list[dict] | None, rag_docs: list[dict]) -> str:
    parts: list[str] = []
    if transactions:
        parts.append("[transactions]")
        for tx in transactions[:50]:
            parts.append(json.dumps(tx, ensure_ascii=False, default=str))
    else:
        parts.append("[transactions] (none)")
    if rag_docs:
        parts.append("\n[rag_corpus]")
        for doc in rag_docs:
            doc_id = doc.get("doc_id") or doc.get("id") or "?"
            content = doc.get("content") or doc.get("body") or ""
            parts.append(f"[{doc_id}]\n{content[:1500]}")
    else:
        parts.append("\n[rag_corpus] (none)")
    return "\n".join(parts)


def _parse_judge_json(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    return json.loads(text)


def score_grounding(
    question: str,
    transactions: list[dict] | None,
    rag_docs: list[dict],
    candidate_answer: str,
    language: str,
) -> tuple[dict, int]:
    """Score ``candidate_answer`` for groundedness against the agent's sources.

    Returns ``({"groundedness": int, "rationale": str}, tokens_used)``.

    On parse failure, returns ``({"groundedness": 0, "rationale": "parse-error: ..."}, tokens)``
    so the harness can flag the row in ``judge_error_count`` without aborting.
    """
    template = _JUDGE_PROMPT_UK if language == "uk" else _JUDGE_PROMPT_EN
    prompt = template.format(
        question=question,
        sources=_format_sources(transactions, rag_docs),
        candidate_answer=candidate_answer,
    )
    llm = get_llm_client()
    response = llm.invoke([HumanMessage(content=prompt)])
    raw = getattr(response, "content", "") or ""
    if isinstance(raw, list):
        raw = "".join(part if isinstance(part, str) else str(part) for part in raw)
    tokens = _tokens_from_response(response)

    try:
        parsed = _parse_judge_json(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning(
            "chat_grounding_judge_parse_error",
            extra={"error": str(exc), "raw": raw[:400]},
        )
        return {"groundedness": 0, "rationale": f"parse-error: {exc}"}, tokens

    score = {"groundedness": 0, "rationale": ""}
    try:
        score["groundedness"] = int(parsed.get("groundedness", 0))
    except (TypeError, ValueError):
        score["groundedness"] = 0
    if score["groundedness"] not in (0, 1, 2):
        score["groundedness"] = 0
    score["rationale"] = str(parsed.get("rationale", ""))[:400]
    return score, tokens
