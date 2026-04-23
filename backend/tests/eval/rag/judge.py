"""Candidate-answer generation + LLM-as-judge for the RAG eval harness (Story 9.1).

Both calls use `app.agents.llm.get_llm_client()` so the harness automatically
picks up whatever provider `llm.py` returns (Claude Haiku primary today; a
future Bedrock swap from Story 9.5b will route here transparently).
"""

from __future__ import annotations

import json
import logging

from langchain_core.messages import HumanMessage

from app.agents.llm import get_llm_client

logger = logging.getLogger(__name__)


_CANDIDATE_PROMPT_EN = """\
You are a financial-literacy assistant. Answer the user's question using ONLY \
the RAG Context below. If the context does not contain the answer, reply with \
a brief acknowledgement that the information is not available. Answer in English.

RAG Context:
{rag_context}

Question: {question}

Answer (2-4 sentences, English only, grounded in the RAG Context):"""


_CANDIDATE_PROMPT_UK = """\
Ти — асистент з фінансової грамотності. Відповідай на запитання користувача, \
використовуючи ВИКЛЮЧНО наведений нижче RAG-контекст. Якщо контекст не містить \
відповіді, коротко повідом, що інформації недостатньо. Відповідай українською.

RAG-контекст:
{rag_context}

Запитання: {question}

Відповідь (2-4 речення, лише українською, базуючись на RAG-контексті):"""


_JUDGE_PROMPT = """\
You are a strict evaluation judge for a Retrieval-Augmented Generation (RAG) \
financial-literacy assistant. Score the candidate answer along four axes.

Rubric (axes):
- groundedness (0|1|2) — measured against the RETRIEVED CONTEXT the generator \
was given (NOT the gold reference). 0: answer contains claims not supported by \
the retrieved context (hallucination); 1: partially supported; 2: every claim \
is supported by the retrieved context. If retrieval missed the gold material, \
a careful "I don't know" answer should still score 2.
- relevance (0|1|2) — measured against the GOLD REFERENCE. 0: off-topic or \
contradicts the reference; 1: partially addresses the question; 2: directly \
and correctly answers per the reference.
- language_correctness (0|1|2) — 0: wrong language or translation artefacts; \
1: right language but awkward phrasing; 2: natural target-language answer.
- overall (integer 0..4) — your holistic summary score. Use your judgement; \
it may differ from the sum of axes.
- rationale — ONE short sentence explaining the overall score.

Target language: {language}
Question: {question}
Candidate answer: {candidate_answer}

Retrieved context the generator saw (score `groundedness` against THIS):
{retrieved_context}

Gold reference content (score `relevance` against THIS):
{expected_content}

Respond with STRICT JSON ONLY — no markdown fences, no prose preamble, no trailing \
commentary. Use exactly this schema (replace each placeholder with your score):
{{"groundedness": <int 0-2>, "relevance": <int 0-2>, "language_correctness": <int 0-2>, "overall": <int 0-4>, "rationale": "<one sentence>"}}"""


def detect_script_language(text: str) -> str:
    """Script-based language sniff: returns `"uk"` if any Cyrillic codepoint is
    present, else `"en"`.

    Shared by the Story 9.5c cross-provider matrix (`test_education_matrix.py`)
    to avoid re-implementing the rubric's `language_correctness` semantics in
    each caller. The judge's own axis is an LLM-as-judge scoring surface, not a
    cheap boolean — this helper is the cheap pre-check for the matrix; the
    judge remains authoritative when a semantic-grade score is needed.
    """
    # U+0400–U+04FF (Cyrillic) + U+0500–U+052F (Cyrillic Supplement) cover
    # every script codepoint Ukrainian output would plausibly emit.
    return "uk" if any("Ѐ" <= ch <= "ԯ" for ch in text) else "en"


def _tokens_from_response(response) -> int:
    """Extract total-tokens used from a langchain response, best-effort."""
    usage = getattr(response, "usage_metadata", None) or {}
    if isinstance(usage, dict):
        return int(usage.get("input_tokens", 0)) + int(usage.get("output_tokens", 0))
    return 0


def _build_rag_context(retrieved_chunks: list[dict]) -> str:
    """Mirror the Education-Agent concatenation pattern."""
    if not retrieved_chunks:
        return "(no retrieved context)"
    return "\n\n".join(
        f"[{doc.get('doc_id', '?')} — {doc.get('chunk_type', '?')}]\n{doc.get('content', '')}"
        for doc in retrieved_chunks
    )


def build_candidate_answer(
    question: str,
    retrieved_chunks: list[dict],
    language: str,
) -> tuple[str, int]:
    """Generate an answer to `question` grounded in `retrieved_chunks`.

    Returns `(answer_text, tokens_used)`.
    """
    template = _CANDIDATE_PROMPT_UK if language == "uk" else _CANDIDATE_PROMPT_EN
    prompt = template.format(
        rag_context=_build_rag_context(retrieved_chunks),
        question=question,
    )
    llm = get_llm_client()
    response = llm.invoke([HumanMessage(content=prompt)])
    text = getattr(response, "content", "") or ""
    if isinstance(text, list):
        text = "".join(part if isinstance(part, str) else str(part) for part in text)
    return text.strip(), _tokens_from_response(response)


def _parse_judge_json(raw: str) -> dict:
    """Parse the judge response. Tolerate accidental code-fencing."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    return json.loads(text)


def _default_score(reason: str) -> dict:
    return {
        "groundedness": 0,
        "relevance": 0,
        "language_correctness": 0,
        "overall": 0,
        "rationale": reason,
    }


def judge_answer(
    question: str,
    candidate_answer: str,
    retrieved_chunks: list[dict],
    expected_doc_content: str,
    language: str,
) -> tuple[dict, int]:
    """Score `candidate_answer` along the four rubric axes.

    `retrieved_chunks` scores `groundedness` (was the candidate faithful to
    what the generator actually saw?) and `expected_doc_content` scores
    `relevance` (did it correctly answer the question per the gold reference?).
    This separation is deliberate — see rubric docstring in `_JUDGE_PROMPT`.

    Returns `(score_dict, tokens_used)`. On parse failure, returns a zeroed
    score dict with `rationale='parse-error: <message>'` so the harness still
    produces a structurally-valid report.
    """
    prompt = _JUDGE_PROMPT.format(
        language=language,
        question=question,
        candidate_answer=candidate_answer,
        retrieved_context=_build_rag_context(retrieved_chunks),
        expected_content=expected_doc_content,
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
        logger.warning("rag_judge_parse_error", extra={"error": str(exc), "raw": raw[:400]})
        return _default_score(f"parse-error: {exc}"), tokens

    score = _default_score("ok")
    for axis in ("groundedness", "relevance", "language_correctness", "overall"):
        value = parsed.get(axis, 0)
        try:
            score[axis] = int(value)
        except (TypeError, ValueError):
            score[axis] = 0
    score["rationale"] = str(parsed.get("rationale", ""))[:400]
    return score, tokens
