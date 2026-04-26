"""Monkeypatched chat-tool stubs for the safety runner (Story 10.8b AC #3).

The runner exercises the LIVE chat handler / backend / Bedrock Guardrail.
The data layer is replaced with deterministic, user-scoped fixtures so:
  (1) cross-user probes can verify the production rebind invariant
      (handler always rebinds ``user_id`` from ``handle.user_id`` regardless
      of model-supplied tool args) without depending on prod data;
  (2) ``answered_safely`` rows have plausible material to discuss.

Foreign-user data is NEVER returned. If the dispatcher ever forwards a
``user_id`` kwarg that does not match the synthetic user, the stub raises
``ChatToolAuthorizationError`` — which surfaces as a ``tool_blocked``
refusal, exactly what the corpus's cross-user entries expect.

Mirrors the dual-write pattern from
``tests/eval/chat_grounding/test_chat_grounding_harness.py:_install_tool_stubs``
because ``TOOL_MANIFEST`` freezes handler attributes at import time AND
the per-tool modules are imported directly elsewhere — both surfaces must
be patched.
"""

from __future__ import annotations

import dataclasses
import datetime as _dt
import json
import uuid
from pathlib import Path
from typing import Any

from app.agents.chat.tools.tool_errors import ChatToolAuthorizationError

_FIXTURE_PATH = (
    Path(__file__).resolve().parent.parent.parent / "fixtures" / "ai_safety"
    / "synthetic_user_data.json"
)


def _load_fixture() -> dict[str, Any]:
    return json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))


def install_tool_stubs(
    monkeypatch,
    *,
    authenticated_user_id: uuid.UUID | None = None,
    user_id_holder: dict | None = None,
) -> None:
    """Install monkeypatched read-only tool handlers scoped to a single user.

    Pass either:
      - ``authenticated_user_id`` — fixed at install time; or
      - ``user_id_holder`` — a mutable dict whose ``["id"]`` entry is read
        at tool-call time (so the test can populate it inside its own
        asyncio loop after fixture setup, mirroring the grounding-harness
        ``current_row`` pattern in ``test_chat_grounding_harness.py``).

    Any forwarded ``user_id`` kwarg that does not match the resolved id
    raises :class:`ChatToolAuthorizationError`.
    """
    if (authenticated_user_id is None) == (user_id_holder is None):
        raise ValueError(
            "install_tool_stubs requires exactly one of authenticated_user_id "
            "or user_id_holder"
        )
    from app.agents.chat import tools as tools_pkg
    from app.agents.chat.tools import (
        profile_tool,
        rag_corpus_tool,
        teaching_feed_tool,
        transactions_tool,
    )

    fixture = _load_fixture()

    def _resolve_authenticated_id() -> uuid.UUID | None:
        if authenticated_user_id is not None:
            return authenticated_user_id
        return user_id_holder.get("id") if user_id_holder is not None else None

    def _check_user(name: str, kwargs: dict[str, Any]) -> None:
        forwarded = kwargs.get("user_id")
        if forwarded is None:
            return
        expected = _resolve_authenticated_id()
        if expected is None:
            # Fixture not yet populated; treat as authorization failure
            # (defense-in-depth — a tool call before user setup is a bug).
            raise ChatToolAuthorizationError(tool_name=name)
        if str(forwarded) != str(expected):
            raise ChatToolAuthorizationError(tool_name=name)

    async def _fake_get_transactions(**kwargs: Any) -> Any:
        _check_user("get_transactions", kwargs)
        rows = [
            transactions_tool.TransactionRow(
                id=uuid.UUID(tx["id"]),
                booked_at=_dt.date.fromisoformat(tx["booked_at"]),
                description=tx["description"],
                amount_kopiykas=int(tx["amount_kopiykas"]),
                currency=tx["currency"],
                category_code=tx.get("category_code"),
                transaction_kind=tx.get("transaction_kind"),
            )
            for tx in fixture["transactions"]
        ]
        return transactions_tool.GetTransactionsOutput(
            rows=rows, row_count=len(rows), truncated=False
        )

    async def _fake_get_profile(**kwargs: Any) -> Any:
        _check_user("get_profile", kwargs)
        p = fixture["profile"]
        return profile_tool.GetProfileOutput(
            summary=profile_tool.ProfileSummary(
                monthly_income_kopiykas=p.get("monthly_income_kopiykas"),
                monthly_expenses_kopiykas=p.get("monthly_expenses_kopiykas"),
                savings_ratio=p.get("savings_ratio"),
                health_score=p.get("health_score"),
                currency=p["currency"],
                as_of=_dt.date.fromisoformat(p["as_of"]),
            ),
            category_breakdown=[],
            monthly_comparison=[],
        )

    async def _fake_get_teaching_feed(**kwargs: Any) -> Any:
        _check_user("get_teaching_feed", kwargs)
        rows = [
            teaching_feed_tool.TeachingFeedRow(
                insight_id=uuid.UUID(card["insight_id"]),
                card_type=card["card_type"],
                title=card["title"],
                delivered_at=_dt.date.fromisoformat(card["delivered_at"]),
            )
            for card in fixture["teaching_feed"]
        ]
        return teaching_feed_tool.GetTeachingFeedOutput(
            rows=rows, row_count=len(rows), truncated=False
        )

    async def _fake_search_financial_corpus(**kwargs: Any) -> Any:
        _check_user("search_financial_corpus", kwargs)
        rows = [
            rag_corpus_tool.CorpusDocRow(
                source_id=doc["source_id"],
                snippet=doc["snippet"],
                similarity=float(doc["similarity"]),
            )
            for doc in fixture["rag_snippets"]
        ]
        return rag_corpus_tool.SearchFinancialCorpusOutput(
            rows=rows, row_count=len(rows)
        )

    fakes = {
        "get_transactions": _fake_get_transactions,
        "get_profile": _fake_get_profile,
        "get_teaching_feed": _fake_get_teaching_feed,
        "search_financial_corpus": _fake_search_financial_corpus,
    }

    new_manifest = tuple(
        dataclasses.replace(spec, handler=fakes[spec.name])
        if spec.name in fakes
        else spec
        for spec in tools_pkg.TOOL_MANIFEST
    )
    monkeypatch.setattr(tools_pkg, "TOOL_MANIFEST", new_manifest)
    monkeypatch.setattr(
        transactions_tool, "get_transactions_handler", _fake_get_transactions
    )
    monkeypatch.setattr(profile_tool, "get_profile_handler", _fake_get_profile)
    monkeypatch.setattr(
        teaching_feed_tool, "get_teaching_feed_handler", _fake_get_teaching_feed
    )
    monkeypatch.setattr(
        rag_corpus_tool,
        "search_financial_corpus_handler",
        _fake_search_financial_corpus,
    )


__all__ = ["install_tool_stubs"]
