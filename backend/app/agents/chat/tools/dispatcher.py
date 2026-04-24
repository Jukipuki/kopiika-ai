"""Chat tool dispatcher — the only module that invokes a ToolSpec handler.

Story 10.4c. ``dispatch_tool`` is a pure request/response primitive. Callers
outside ``DirectBedrockBackend.invoke``'s tool-use loop should not touch
handlers directly; any such caller indicates scope drift.

Error posture:
- ``not_allowed`` → soft (ToolResult ok=False, error_kind="not_allowed").
  Unknown tool names from the model are a self-correction signal, not a
  security event. Only the loop-level guard in the backend (past hop cap)
  raises ``ChatToolNotAllowedError`` upward.
- ``schema_error`` → soft. Pydantic validation failure. Never echoes raw
  input back in the error payload — adversarial input could shape the
  error message into something the model then relays.
- ``execution_error`` → soft for SQL / other unexpected errors.
  The dispatcher ALSO emits an ERROR log at this point so the observability
  pipeline (Story 10.9) has a paging signal.
- ``PermissionError`` from a handler → HARD: raises ``ChatToolAuthorizationError``
  upward, the turn is aborted. A misrouted cross-user read is never returned
  to the model.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass

from pydantic import BaseModel, ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.agents.chat.tools.tool_errors import (
    ChatToolAuthorizationError,
    ChatToolNotAllowedError,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ToolInvocation:
    tool_name: str
    raw_input: dict
    tool_use_id: str


@dataclass(frozen=True)
class ToolResult:
    tool_use_id: str
    tool_name: str
    ok: bool
    payload: dict
    error_kind: str | None  # "not_allowed" | "schema_error" | "execution_error" | None
    elapsed_ms: int


def _hash_user_id(user_id: uuid.UUID) -> str:
    # Mirrors session_handler._hash_user_id — 64-bit blake2b prefix.
    import hashlib

    return hashlib.blake2b(user_id.bytes, digest_size=8).hexdigest()


def _truncate_rows(payload: dict, max_rows: int) -> tuple[dict, bool]:
    """Second-layer defensive cap: if payload has ``rows``, slice at ``max_rows``.

    Sets ``truncated=True`` if we sliced. Handlers already enforce ``limit``;
    this is belt-and-braces against a future bug.
    """
    rows = payload.get("rows")
    if not isinstance(rows, list) or len(rows) <= max_rows:
        return payload, bool(payload.get("truncated", False))
    new_payload = dict(payload)
    new_payload["rows"] = rows[:max_rows]
    new_payload["row_count"] = len(new_payload["rows"])
    new_payload["truncated"] = True
    return new_payload, True


async def dispatch_tool(
    invocation: ToolInvocation,
    *,
    user_id: uuid.UUID,
    db: SQLModelAsyncSession,
    db_session_id: uuid.UUID | None = None,
) -> ToolResult:
    """Resolve, validate, execute, validate-output, and time a tool call.

    ``db_session_id`` is the chat session primary key; when present it is
    attached to every ``chat.tool.*`` log event so CloudWatch Insights can
    slice by session (Story 10.9 dashboards). Optional only so legacy unit
    tests that pass no session id still work; production callers always
    thread it through.
    """
    # Import inline — the manifest imports the handlers which import
    # SQL/pydantic; keeping this lazy mirrors the rest of the chat module
    # and avoids collection-time surprises under pytest.
    from app.agents.chat.tools import get_tool_spec

    started = time.perf_counter()
    sid = str(db_session_id) if db_session_id is not None else None

    logger.info(
        "chat.tool.invoked",
        extra={
            "db_session_id": sid,
            "tool_name": invocation.tool_name,
            "tool_use_id": invocation.tool_use_id,
            "input_keys": sorted(list(invocation.raw_input.keys())),
        },
    )

    # 1. Resolve spec — unknown tool becomes a soft result.
    try:
        spec = get_tool_spec(invocation.tool_name)
    except ChatToolNotAllowedError:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        result = ToolResult(
            tool_use_id=invocation.tool_use_id,
            tool_name=invocation.tool_name,
            ok=False,
            payload={
                "error": "tool_not_allowed",
                "tool_name": invocation.tool_name,
            },
            error_kind="not_allowed",
            elapsed_ms=elapsed_ms,
        )
        _log_blocked(result, sid)
        return result

    # 2. Validate input.
    try:
        validated: BaseModel = spec.input_model.model_validate(invocation.raw_input)
    except ValidationError as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        # Summarize the validation error into a safe string; never echo
        # the raw input (adversarial values can shape error messages).
        detail = _summarize_validation_error(exc)
        result = ToolResult(
            tool_use_id=invocation.tool_use_id,
            tool_name=invocation.tool_name,
            ok=False,
            payload={"error": "schema_error", "detail": detail},
            error_kind="schema_error",
            elapsed_ms=elapsed_ms,
        )
        _log_blocked(result, sid)
        return result

    # 3. Call handler.
    try:
        handler_out = await spec.handler(
            user_id=user_id, db=db, **validated.model_dump()
        )
    except PermissionError as exc:
        # Fail-closed: a cross-user read attempt is never returned to the model.
        logger.error(
            "chat.tool.authorization_failed",
            extra={
                "db_session_id": sid,
                "tool_name": invocation.tool_name,
                "tool_use_id": invocation.tool_use_id,
                "user_id_hash": _hash_user_id(user_id),
            },
        )
        raise ChatToolAuthorizationError(tool_name=invocation.tool_name) from exc
    except SQLAlchemyError as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        logger.error(
            "chat.tool.execution_failed",
            extra={
                "db_session_id": sid,
                "tool_name": invocation.tool_name,
                "tool_use_id": invocation.tool_use_id,
                "error_class": type(exc).__name__,
                "error_message": str(exc)[:200],
            },
        )
        result = ToolResult(
            tool_use_id=invocation.tool_use_id,
            tool_name=invocation.tool_name,
            ok=False,
            payload={"error": "execution_error"},
            error_kind="execution_error",
            elapsed_ms=elapsed_ms,
        )
        _log_blocked(result, sid)
        return result
    except Exception as exc:  # noqa: BLE001 — defensive catch-all for handler bugs
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        logger.error(
            "chat.tool.execution_failed",
            extra={
                "db_session_id": sid,
                "tool_name": invocation.tool_name,
                "tool_use_id": invocation.tool_use_id,
                "error_class": type(exc).__name__,
                "error_message": str(exc)[:200],
            },
        )
        result = ToolResult(
            tool_use_id=invocation.tool_use_id,
            tool_name=invocation.tool_name,
            ok=False,
            payload={"error": "execution_error"},
            error_kind="execution_error",
            elapsed_ms=elapsed_ms,
        )
        _log_blocked(result, sid)
        return result

    # 4. Output-schema round-trip defense.
    try:
        validated_out = spec.output_model.model_validate(handler_out.model_dump())
    except (ValidationError, AttributeError) as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        logger.error(
            "chat.tool.output_schema_drift",
            extra={
                "db_session_id": sid,
                "tool_name": invocation.tool_name,
                "tool_use_id": invocation.tool_use_id,
                "validation_error_summary": str(exc)[:200],
            },
        )
        result = ToolResult(
            tool_use_id=invocation.tool_use_id,
            tool_name=invocation.tool_name,
            ok=False,
            payload={"error": "execution_error"},
            error_kind="execution_error",
            elapsed_ms=elapsed_ms,
        )
        _log_blocked(result, sid)
        return result

    # 5. Defensive max_rows truncation.
    payload = validated_out.model_dump(mode="json")
    payload, _truncated = _truncate_rows(payload, spec.max_rows)

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    result = ToolResult(
        tool_use_id=invocation.tool_use_id,
        tool_name=invocation.tool_name,
        ok=True,
        payload=payload,
        error_kind=None,
        elapsed_ms=elapsed_ms,
    )

    # Only compute payload_bytes for the success log to keep the observability
    # side-effects proportional to what we actually ship to the model.
    try:
        import json as _json

        payload_bytes = len(_json.dumps(payload, default=str).encode("utf-8"))
    except Exception:  # noqa: BLE001
        payload_bytes = -1

    logger.info(
        "chat.tool.result",
        extra={
            "db_session_id": sid,
            "tool_name": invocation.tool_name,
            "tool_use_id": invocation.tool_use_id,
            "row_count": payload.get("row_count")
            if isinstance(payload, dict)
            else None,
            "payload_bytes": payload_bytes,
            "elapsed_ms": elapsed_ms,
        },
    )
    return result


def _summarize_validation_error(exc: ValidationError) -> str:
    try:
        errors = exc.errors()
    except Exception:  # noqa: BLE001
        return "validation_error"
    if not errors:
        return "validation_error"
    first = errors[0]
    loc = ".".join(str(p) for p in first.get("loc", ()))
    msg = str(first.get("msg", "invalid"))[:120]
    return f"{loc}: {msg}" if loc else msg


def _log_blocked(result: ToolResult, db_session_id: str | None = None) -> None:
    # Level WARN, not ERROR — a schema error is a model self-correction
    # signal, not an operator-paging event. Execution errors already emit
    # their own ERROR from inside the dispatcher's except clauses.
    logger.warning(
        "chat.tool.blocked",
        extra={
            "db_session_id": db_session_id,
            "tool_name": result.tool_name,
            "tool_use_id": result.tool_use_id,
            "error_kind": result.error_kind,
            "elapsed_ms": result.elapsed_ms,
        },
    )


__all__ = [
    "ToolInvocation",
    "ToolResult",
    "dispatch_tool",
]
