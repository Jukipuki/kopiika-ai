"""Chat tool manifest — read-only allowlist exposing user-scoped data tools.

Story 10.4c. Phase A / Phase B agnostic: this manifest is the single source
of truth for what the chat agent may do against the DB + RAG corpus. Phase B
(AgentCore backend) will consume the same ``TOOL_MANIFEST`` unchanged.

Scope boundary — read-only. Any handler that mutates state is FORBIDDEN by
the Epic 10 no-write-tools invariant (epics.md §Out of Scope). Adding a
write-tool requires a new story + security review.

Public surface (do not expand — downstream stories 10.5 / 10.6b compose this
module, they do not mutate it):

- ``CHAT_TOOL_MANIFEST_VERSION`` — bump on any tool set / schema change.
- ``ToolSpec`` — frozen dataclass describing one tool.
- ``TOOL_MANIFEST`` — the frozen tuple of four ToolSpecs (authored order).
- ``TOOL_ALLOWLIST`` — ``frozenset`` of allowed tool names.
- ``get_tool_spec(name)`` — raises ``ChatToolNotAllowedError`` on miss.
- ``render_bedrock_tool_config()`` — Converse ``toolConfig`` shape.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from pydantic import BaseModel

from app.agents.chat.tools.profile_tool import (
    GetProfileInput,
    GetProfileOutput,
    get_profile_handler,
)
from app.agents.chat.tools.rag_corpus_tool import (
    SearchFinancialCorpusInput,
    SearchFinancialCorpusOutput,
    search_financial_corpus_handler,
)
from app.agents.chat.tools.teaching_feed_tool import (
    GetTeachingFeedInput,
    GetTeachingFeedOutput,
    get_teaching_feed_handler,
)
from app.agents.chat.tools.tool_errors import ChatToolNotAllowedError
from app.agents.chat.tools.transactions_tool import (
    GetTransactionsInput,
    GetTransactionsOutput,
    get_transactions_handler,
)

CHAT_TOOL_MANIFEST_VERSION: str = "10.4c-v1"


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    handler: Callable[..., Awaitable[BaseModel]]
    max_rows: int


TOOL_MANIFEST: tuple[ToolSpec, ...] = (
    ToolSpec(
        name="get_transactions",
        description=(
            "Return the authenticated user's own transactions, most recent first. "
            "Optional filters: inclusive date range (start_date, end_date), exact "
            "category match (category), and a row limit. Returns signed amounts in "
            "kopiykas (negative = debit)."
        ),
        input_model=GetTransactionsInput,
        output_model=GetTransactionsOutput,
        handler=get_transactions_handler,
        max_rows=200,
    ),
    ToolSpec(
        name="get_profile",
        description=(
            "Return the authenticated user's cumulative financial profile: income, "
            "expenses, savings ratio, health score, and optionally a per-category "
            "spending breakdown and month-over-month comparison."
        ),
        input_model=GetProfileInput,
        output_model=GetProfileOutput,
        handler=get_profile_handler,
        max_rows=1,
    ),
    ToolSpec(
        name="get_teaching_feed",
        description=(
            "Return titles and metadata for insight cards delivered to the "
            "authenticated user's teaching feed. Returns card_type, title, and "
            "delivery date only — card bodies are not surfaced through chat. If the "
            "user asks what card X said, ask them to open the card in the teaching "
            "feed."
        ),
        input_model=GetTeachingFeedInput,
        output_model=GetTeachingFeedOutput,
        handler=get_teaching_feed_handler,
        max_rows=50,
    ),
    ToolSpec(
        name="search_financial_corpus",
        description=(
            "Search the shared financial-literacy corpus for snippets relevant to a "
            "query. This corpus is cross-user educational content (not user data). "
            "Returns up to top_k snippets with source identifiers for citation."
        ),
        input_model=SearchFinancialCorpusInput,
        output_model=SearchFinancialCorpusOutput,
        handler=search_financial_corpus_handler,
        max_rows=10,
    ),
)

TOOL_ALLOWLIST: frozenset[str] = frozenset(spec.name for spec in TOOL_MANIFEST)


def get_tool_spec(name: str) -> ToolSpec:
    """Return the ``ToolSpec`` for ``name`` or raise ``ChatToolNotAllowedError``.

    No fallback, no similarity suggestion — the allowlist is the allowlist.
    """
    for spec in TOOL_MANIFEST:
        if spec.name == name:
            return spec
    raise ChatToolNotAllowedError(tool_name=name)


def render_bedrock_tool_config() -> dict:
    """Produce the Bedrock Converse ``toolConfig`` dict from the manifest.

    Shape matches the Converse API contract:
        {
          "tools": [{"toolSpec": {"name", "description", "inputSchema"}}, ...],
          "toolChoice": {"auto": {}},
        }
    """
    return {
        "tools": [
            {
                "toolSpec": {
                    "name": spec.name,
                    "description": spec.description,
                    "inputSchema": {"json": spec.input_model.model_json_schema()},
                }
            }
            for spec in TOOL_MANIFEST
        ],
        "toolChoice": {"auto": {}},
    }


__all__ = [
    "CHAT_TOOL_MANIFEST_VERSION",
    "TOOL_ALLOWLIST",
    "TOOL_MANIFEST",
    "ToolSpec",
    "get_tool_spec",
    "render_bedrock_tool_config",
]
