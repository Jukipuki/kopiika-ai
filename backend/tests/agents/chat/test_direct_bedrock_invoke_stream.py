"""Story 10.5 AC #11 — DirectBedrockBackend.invoke_stream tests.

Mocks the langchain-aws ``ChatBedrockConverse`` client's ``ainvoke`` /
``astream`` / ``with_config`` at the boundary.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.chat.chat_backend import (
    BackendStreamDone,
    BackendTokenDelta,
    BackendToolHop,
    ChatGuardrailInterventionError,
    DirectBedrockBackend,
)
from app.core.config import settings


@pytest.fixture
def bedrock_env(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "bedrock")


@pytest.fixture(autouse=True)
def _propagate_app_logger():
    import logging

    lg = logging.getLogger("app")
    prev = lg.propagate
    lg.propagate = True
    try:
        yield
    finally:
        lg.propagate = prev


def _ai_plain(content="hello", in_t=3, out_t=2):
    m = MagicMock()
    m.content = content
    m.usage_metadata = {"input_tokens": in_t, "output_tokens": out_t}
    m.tool_calls = []
    m.response_metadata = {}
    m.additional_kwargs = {}
    return m


def _ai_tool_use(name="get_transactions", args=None, tc_id="tu_1"):
    m = MagicMock()
    m.content = [{"type": "tool_use", "id": tc_id, "name": name, "input": args or {}}]
    m.usage_metadata = {"input_tokens": 1, "output_tokens": 1}
    m.tool_calls = [{"name": name, "args": args or {}, "id": tc_id}]
    m.response_metadata = {}
    m.additional_kwargs = {}
    return m


def _chunk(text):
    c = MagicMock()
    c.content = text
    c.usage_metadata = {}
    c.response_metadata = {}
    c.additional_kwargs = {}
    return c


def _chunk_final(text, in_t=10, out_t=5, stop_reason=None, trace=None):
    c = MagicMock()
    c.content = text
    c.usage_metadata = {"input_tokens": in_t, "output_tokens": out_t}
    md = {}
    if stop_reason:
        md["stopReason"] = stop_reason
    if trace:
        md["trace"] = {"guardrail": trace}
    c.response_metadata = md
    c.additional_kwargs = {}
    return c


def _fake_client(ai_msg=None, stream_chunks=None, ainvoke_side_effect=None):
    client = MagicMock()
    if ainvoke_side_effect is not None:
        client.ainvoke = AsyncMock(side_effect=list(ainvoke_side_effect))
    else:
        client.ainvoke = AsyncMock(return_value=ai_msg)

    async def _astream(_msgs):
        for c in stream_chunks or []:
            yield c

    client.astream = _astream
    client.bind_tools = MagicMock(return_value=client)
    client.bind = MagicMock(return_value=client)
    client.with_config = MagicMock(return_value=client)
    return client


async def _collect(agen):
    out = []
    async for e in agen:
        out.append(e)
    return out


def _kwargs(**o):
    base = {
        "db_session_id": uuid.uuid4(),
        "context_messages": [],
        "user_message": "hi",
        "system_prompt": "sys",
        "user_id": uuid.uuid4(),
        "db": MagicMock(),
    }
    base.update(o)
    return base


@pytest.mark.asyncio
async def test_no_tool_uses_streams_deltas_and_terminates(bedrock_env):
    peek = _ai_plain(content="")
    chunks = [_chunk("Hello, "), _chunk_final("world.", in_t=10, out_t=5)]
    fake = _fake_client(ai_msg=peek, stream_chunks=chunks)

    with patch("app.agents.llm._get_client_for", return_value=fake):
        be = DirectBedrockBackend()
        events = await _collect(be.invoke_stream(**_kwargs(guardrail_id="gid")))

    texts = [e.text for e in events if isinstance(e, BackendTokenDelta)]
    assert texts == ["Hello, ", "world."]
    done = events[-1]
    assert isinstance(done, BackendStreamDone)
    assert done.input_tokens == 10
    assert done.output_tokens == 5


@pytest.mark.asyncio
async def test_one_tool_hop_then_stream(bedrock_env):
    tool_ai = _ai_tool_use(name="get_transactions", args={"month": "2026-03"})
    final_peek = _ai_plain(content="")
    chunks = [_chunk_final("Found 3.", in_t=20, out_t=3)]
    fake = _fake_client(
        ainvoke_side_effect=[tool_ai, final_peek], stream_chunks=chunks
    )

    async def _fake_dispatch(inv, *, user_id, db, db_session_id):
        from types import SimpleNamespace

        return SimpleNamespace(
            tool_name=inv.tool_name,
            ok=True,
            payload={"rows": []},
            error_kind=None,
            elapsed_ms=1,
            tool_use_id=inv.tool_use_id,
        )

    with patch("app.agents.llm._get_client_for", return_value=fake), patch(
        "app.agents.chat.tools.dispatcher.dispatch_tool", side_effect=_fake_dispatch
    ):
        be = DirectBedrockBackend()
        events = await _collect(be.invoke_stream(**_kwargs()))

    assert any(isinstance(e, BackendToolHop) for e in events)
    assert [e.text for e in events if isinstance(e, BackendTokenDelta)] == ["Found 3."]


@pytest.mark.asyncio
async def test_guardrail_id_threaded_to_bind(bedrock_env):
    peek = _ai_plain(content="")
    fake = _fake_client(ai_msg=peek, stream_chunks=[_chunk_final("ok")])
    with patch("app.agents.llm._get_client_for", return_value=fake):
        be = DirectBedrockBackend()
        await _collect(
            be.invoke_stream(
                **_kwargs(guardrail_id="g-xyz", guardrail_version="DRAFT")
            )
        )
    # Guardrail must attach via ``.bind(guardrail_config=...)`` — this is the
    # kwarg path that actually routes through langchain-aws's
    # ``_converse_params`` → Bedrock ``guardrailConfig``. ``with_config`` is a
    # no-op here (see chat_backend.py comment).
    fake.bind.assert_called_once()
    kwargs = fake.bind.call_args.kwargs
    gc = kwargs.get("guardrail_config")
    assert gc is not None, "guardrail_config not passed to .bind()"
    assert gc["guardrailIdentifier"] == "g-xyz"
    assert gc["guardrailVersion"] == "DRAFT"


@pytest.mark.asyncio
async def test_guardrail_none_emits_warn(bedrock_env, caplog):
    import logging

    peek = _ai_plain(content="")
    fake = _fake_client(ai_msg=peek, stream_chunks=[_chunk_final("ok")])
    with patch("app.agents.llm._get_client_for", return_value=fake):
        be = DirectBedrockBackend()
        with caplog.at_level(logging.WARNING, logger="app.agents.chat.chat_backend"):
            await _collect(be.invoke_stream(**_kwargs(guardrail_id=None)))
    assert any(
        "chat.stream.guardrail_detached" in r.getMessage() for r in caplog.records
    )


@pytest.mark.asyncio
async def test_guardrail_intervened_on_peek_raises_intervention(bedrock_env):
    peek = MagicMock()
    peek.content = ""
    peek.usage_metadata = {"input_tokens": 1, "output_tokens": 1}
    peek.tool_calls = []
    peek.response_metadata = {
        "stopReason": "guardrail_intervened",
        "trace": {
            "guardrail": {
                "outputAssessments": {
                    "gid": [{"contextualGroundingPolicy": {"filters": []}}]
                }
            }
        },
    }
    peek.additional_kwargs = {}
    fake = _fake_client(ai_msg=peek, stream_chunks=[])

    with patch("app.agents.llm._get_client_for", return_value=fake):
        be = DirectBedrockBackend()
        with pytest.raises(ChatGuardrailInterventionError) as exc_info:
            await _collect(be.invoke_stream(**_kwargs(guardrail_id="g")))
    assert exc_info.value.intervention_kind == "grounding"


@pytest.mark.asyncio
async def test_guardrail_intervened_on_final_chunk_raises(bedrock_env):
    peek = _ai_plain(content="")
    final = _chunk_final(
        "",
        stop_reason="guardrail_intervened",
        trace={
            "outputAssessments": {"gid": [{"topicPolicy": {"topics": []}}]}
        },
    )
    fake = _fake_client(ai_msg=peek, stream_chunks=[final])
    with patch("app.agents.llm._get_client_for", return_value=fake):
        be = DirectBedrockBackend()
        with pytest.raises(ChatGuardrailInterventionError) as exc_info:
            await _collect(be.invoke_stream(**_kwargs(guardrail_id="g")))
    assert exc_info.value.intervention_kind == "denied_topic"
