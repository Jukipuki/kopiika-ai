"""Chat citation assembler — Story 10.6b.

Pure-function projection from the per-turn ``ToolResult`` sequence (Story
10.4c) into a typed, deduplicated tuple of ``Citation`` values. The result
backs the ``chat-citations`` SSE frame (Story 10.7 chip-row consumer) and
the ``ChatTurnResponse.citations`` field on the non-streaming path.

# SCOPE BOUNDARIES (mirror story 10-6b §Scope Boundaries):
#   - No frontend chip rendering            → Story 10.7
#   - No new DB column / Alembic migration  → derived at assembly time
#   - No model-emitted inline [^N] markers  → TD-122 follow-up
#   - No system-prompt change               → preserves 10.6a baseline
#   - No new tools / tool-output schema chg → reads 10.4c outputs as-is
#   - No grounding-rate change              → citations are render contract
#   - No CHAT_REFUSED enum change           → citations attach happy-path only
#   - No CloudWatch metric on count         → Story 10.9 metricifies log
#   - No teaching-feed citations            → drop intentionally; not citable
#   - No PII redaction inside citations     → Guardrails handles assistant text
#   - No Phase-B AgentCore coupling         → reads role='tool' rows only

The module is a function library — no state, no class. The only public
verb is ``assemble_citations(tool_calls) -> tuple[Citation, ...]``; the
only public serializer is ``citation_to_json_dict(c) -> dict``.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date
from enum import StrEnum
from typing import Literal, Sequence, Union

from pydantic import BaseModel

from app.agents.chat.tools.dispatcher import ToolResult
from app.agents.chat.tools.profile_tool import GetProfileOutput
from app.agents.chat.tools.rag_corpus_tool import SearchFinancialCorpusOutput
from app.agents.chat.tools.transactions_tool import GetTransactionsOutput

logger = logging.getLogger(__name__)


CITATION_CONTRACT_VERSION: str = "10.6b-v1"

MAX_CITATIONS_PER_TURN: int = 20

_RAG_SNIPPET_MAX_CHARS: int = 240

_PROFILE_FIELD_LABEL_TEMPLATES: dict[str, str] = {
    "monthly_income_kopiykas": "Monthly income ({as_of_short})",
    "monthly_expenses_kopiykas": "Monthly expenses ({as_of_short})",
    "savings_ratio": "Savings ratio ({as_of_short})",
    "health_score": "Health score ({as_of_short})",
}

_PROFILE_MONETARY_FIELDS: frozenset[str] = frozenset(
    {"monthly_income_kopiykas", "monthly_expenses_kopiykas"}
)


class CitationKind(StrEnum):
    transaction = "transaction"
    category = "category"
    profile_field = "profile_field"
    rag_doc = "rag_doc"


class TransactionCitation(BaseModel):
    kind: Literal["transaction"] = "transaction"
    id: uuid.UUID
    booked_at: date
    description: str
    amount_kopiykas: int
    currency: str
    category_code: str | None = None
    label: str


class CategoryCitation(BaseModel):
    kind: Literal["category"] = "category"
    code: str
    label: str


class ProfileFieldCitation(BaseModel):
    kind: Literal["profile_field"] = "profile_field"
    field: str
    value: int | None
    currency: str | None
    as_of: date
    label: str


class RagDocCitation(BaseModel):
    kind: Literal["rag_doc"] = "rag_doc"
    source_id: str
    title: str
    snippet: str
    similarity: float
    label: str


Citation = Union[
    TransactionCitation,
    CategoryCitation,
    ProfileFieldCitation,
    RagDocCitation,
]


def _category_label(code: str) -> str:
    return code.replace("_", " ").title()


def _profile_label(field: str, as_of: date) -> str:
    template = _PROFILE_FIELD_LABEL_TEMPLATES.get(field, "{field} ({as_of_short})")
    return template.format(field=field, as_of_short=as_of.strftime("%b %Y"))


def _transaction_label(description: str, booked_at: date) -> str:
    return f"{description[:40]} · {booked_at.isoformat()}"


def _safe_validate(model: type[BaseModel], payload: object, *, tool_name: str):
    """Validate ``payload`` against ``model`` or return ``None`` after logging.

    Defends history-replay (Story 10.10) against legacy / shape-drifted rows.
    """
    if not isinstance(payload, dict):
        logger.warning(
            "chat.citations.malformed_payload",
            extra={
                "tool_name": tool_name,
                "validation_error_summary": f"payload not a dict: {type(payload).__name__}",
            },
        )
        return None
    try:
        return model.model_validate(payload)
    except Exception as exc:  # noqa: BLE001 — pydantic ValidationError + defensive
        logger.warning(
            "chat.citations.malformed_payload",
            extra={
                "tool_name": tool_name,
                "validation_error_summary": str(exc)[:200],
            },
        )
        return None


def assemble_citations(tool_calls: Sequence[ToolResult]) -> tuple[Citation, ...]:
    """Project a per-turn ``ToolResult`` sequence into a deduplicated, ordered
    citation tuple.

    Pure function: no DB session, no I/O. Logs are side-effects only for
    observability (chat.citations.dropped/truncated/malformed_payload).

    Callers that need truncation visibility (for the
    ``chat.citations.attached`` log per AC #4 / #5) should use
    ``assemble_citations_with_meta`` instead.
    """
    citations, _truncated = assemble_citations_with_meta(tool_calls)
    return citations


def assemble_citations_with_meta(
    tool_calls: Sequence[ToolResult],
) -> tuple[tuple[Citation, ...], bool]:
    """Same projection as ``assemble_citations`` but also returns whether the
    per-turn cap fired. Use at the session-handler call sites so the
    ``chat.citations.attached`` INFO log carries an honest ``truncated``
    field per AC #4 / #5."""
    out: list[Citation] = []
    seen: set[tuple] = set()

    def _add(citation: Citation, dedup_key: tuple) -> None:
        if dedup_key in seen:
            return
        seen.add(dedup_key)
        out.append(citation)

    for tc in tool_calls:
        ok = getattr(tc, "ok", False)
        if not ok:
            continue
        tool_name = getattr(tc, "tool_name", None)
        payload = getattr(tc, "payload", None)

        if tool_name == "get_teaching_feed":
            row_count = 0
            if isinstance(payload, dict):
                rows = payload.get("rows")
                if isinstance(rows, list):
                    row_count = len(rows)
            logger.debug(
                "chat.citations.dropped",
                extra={"tool_name": "get_teaching_feed", "row_count": row_count},
            )
            continue

        if tool_name == "get_transactions":
            validated = _safe_validate(
                GetTransactionsOutput, payload, tool_name=tool_name
            )
            if validated is None:
                continue
            for row in validated.rows:
                _add(
                    TransactionCitation(
                        id=row.id,
                        booked_at=row.booked_at,
                        description=row.description,
                        amount_kopiykas=row.amount_kopiykas,
                        currency=row.currency,
                        category_code=row.category_code,
                        label=_transaction_label(row.description, row.booked_at),
                    ),
                    ("transaction", row.id),
                )
                if row.category_code:
                    _add(
                        CategoryCitation(
                            code=row.category_code,
                            label=_category_label(row.category_code),
                        ),
                        ("category", row.category_code),
                    )
            continue

        if tool_name == "get_profile":
            validated = _safe_validate(
                GetProfileOutput, payload, tool_name=tool_name
            )
            if validated is None:
                continue
            summary = validated.summary
            for field in (
                "monthly_income_kopiykas",
                "monthly_expenses_kopiykas",
                "savings_ratio",
                "health_score",
            ):
                value = getattr(summary, field)
                if value is None:
                    continue
                currency = (
                    summary.currency if field in _PROFILE_MONETARY_FIELDS else None
                )
                _add(
                    ProfileFieldCitation(
                        field=field,
                        value=value,
                        currency=currency,
                        as_of=summary.as_of,
                        label=_profile_label(field, summary.as_of),
                    ),
                    ("profile_field", field, summary.as_of),
                )
            for breakdown_row in validated.category_breakdown:
                _add(
                    CategoryCitation(
                        code=breakdown_row.category_code,
                        label=_category_label(breakdown_row.category_code),
                    ),
                    ("category", breakdown_row.category_code),
                )
            continue

        if tool_name == "search_financial_corpus":
            validated = _safe_validate(
                SearchFinancialCorpusOutput, payload, tool_name=tool_name
            )
            if validated is None:
                continue
            for row in validated.rows:
                # CorpusDocRow has no `title` field (see rag_corpus_tool.py
                # comment); the source_id doubles as both stable handle and
                # chip-visible title until a doc-title index exists.
                title = row.source_id
                _add(
                    RagDocCitation(
                        source_id=row.source_id,
                        title=title,
                        snippet=row.snippet[:_RAG_SNIPPET_MAX_CHARS],
                        similarity=row.similarity,
                        label=title,
                    ),
                    ("rag_doc", row.source_id),
                )
            continue

        # Unknown tool name — skip silently (not a known citable surface).

    truncated = False
    if len(out) > MAX_CITATIONS_PER_TURN:
        pre = len(out)
        out = out[:MAX_CITATIONS_PER_TURN]
        truncated = True
        logger.warning(
            "chat.citations.truncated",
            extra={
                "pre_truncate_count": pre,
                "kept_count": MAX_CITATIONS_PER_TURN,
                "dropped_count": pre - MAX_CITATIONS_PER_TURN,
            },
        )

    return tuple(out), truncated


def citation_to_json_dict(c: Citation) -> dict:
    """Canonical snake_case serializer. The API layer applies ``to_camel`` at
    the wire boundary."""
    return c.model_dump(mode="json")


__all__ = [
    "CITATION_CONTRACT_VERSION",
    "MAX_CITATIONS_PER_TURN",
    "CategoryCitation",
    "Citation",
    "CitationKind",
    "ProfileFieldCitation",
    "RagDocCitation",
    "TransactionCitation",
    "assemble_citations",
    "assemble_citations_with_meta",
    "citation_to_json_dict",
]
