# Story 10.6a — Chat-grounding eval harness. Marker-gated (`-m eval`); runs
# locally / on demand against the *configured* chat runtime + Bedrock
# Guardrail. Sibling of tests/eval/rag/ — shares the marker, auto-skip
# posture, and run-report shape, but no shared code (rubrics drift
# independently). Out of scope here: SSE event types, regenerate-on-block,
# CloudWatch alarms, CI gating, RELEVANCE filter, frontend, AgentCore
# Phase B, prompt / model / corpus changes. See story 10-6a for the full
# scope deferral list.
"""Marker-gated chat-grounding eval harness driver (Story 10.6a AC #5).

Run:
    cd backend && uv run pytest tests/eval/chat_grounding/ -v -m eval

Auto-skips when the DB is unreachable or Bedrock is not callable, so the
harness is safe to *invoke* without prod creds (it will emit skip warnings
and pass with `pytest.skip`).
"""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
import os
import subprocess
import time
import traceback
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.agents.chat.chat_backend import (
    ChatGuardrailInterventionError,
)
from app.agents.chat.session_handler import (
    ChatSessionHandler,
    build_backend,
)
from app.core.config import settings
from app.core.consent import (
    CONSENT_TYPE_CHAT_PROCESSING,
    CURRENT_CHAT_CONSENT_VERSION,
)
from app.core.database import engine as _async_engine, get_sync_session
from app.models.user import User
from app.services import consent_service
from tests.eval.chat_grounding import judge as judge_module

logger = logging.getLogger(__name__)

pytestmark = [pytest.mark.integration, pytest.mark.eval]

_FIXTURE_DIR = Path(__file__).resolve().parent.parent.parent / "fixtures" / "chat_grounding"
_EVAL_SET_PATH = _FIXTURE_DIR / "eval_set.jsonl"
_RUNS_DIR = _FIXTURE_DIR / "runs"
_CORPUS_ROOT = (
    Path(__file__).resolve().parent.parent.parent.parent / "data" / "rag-corpus"
)

# Mirrors tests/eval/rag/test_rag_harness.py:_MAX_ERROR_FRACTION — judge
# parsing failures above this fraction signal a structural bug in the
# prompt or model, not a metric-threshold miss. Fail the run hard so the
# operator goes and fixes the judge before treating the report as data.
_MAX_ERROR_FRACTION = 0.2

# NFR38 grounding-rate target — xfail (NOT fail) below this so the report
# is the deliverable, not a hard CI gate. Story 10.8b owns the CI gate;
# AC #1's tuning loop closes the gap.
_GROUNDING_RATE_TARGET = 0.90


def _load_eval_set() -> list[dict]:
    rows: list[dict] = []
    for line in _EVAL_SET_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        row = json.loads(stripped)
        if row.get("id") == "_meta":
            continue  # AC #10 — metadata row ignored by the harness
        rows.append(row)
    return rows


def _load_rag_doc(doc_id: str) -> dict:
    """Best-effort RAG-doc loader for fixture-tool stubs.

    The eval set references docs by ``"<lang>/<slug>"``; we translate that
    to ``data/rag-corpus/<lang>/<slug>.md``. If the file is missing, return
    a minimal stub so the harness still runs (the row will likely fail the
    grounding judgement, which is the correct outcome).
    """
    lang, _, slug = doc_id.partition("/")
    path = _CORPUS_ROOT / lang / f"{slug}.md"
    if path.exists():
        return {"doc_id": doc_id, "content": path.read_text(encoding="utf-8")}
    return {"doc_id": doc_id, "content": "(corpus document unavailable)"}


def _check_db_reachable() -> tuple[bool, str]:
    try:
        with get_sync_session() as session:
            session.execute(text("SELECT 1"))
    except Exception as exc:
        return False, f"database unreachable: {exc}"
    return True, "db reachable"


def _check_bedrock_client_buildable() -> tuple[bool, str]:
    """Build a bedrock-runtime client and verify its region resolves.

    This is a *local* build/config check, not a network probe — it
    verifies that ``BEDROCK_GUARDRAIL_ARN`` is set, ``boto3`` is
    importable, and a client can be constructed for the configured
    region. It does NOT call IAM or Bedrock; missing or expired creds
    will surface on the first real ``send_turn`` call (and be captured
    in the row's ``error_class`` / ``traceback_tail``).

    Mirrors the cheap-precondition stance of tests/eval/rag/test_rag_harness.py
    while being honest about scope.
    """
    if not settings.BEDROCK_GUARDRAIL_ARN:
        return False, "BEDROCK_GUARDRAIL_ARN not configured in settings"
    try:
        import boto3  # type: ignore
    except ImportError as exc:
        return False, f"boto3 not importable: {exc}"
    try:
        region = (
            getattr(settings, "AWS_REGION", None)
            or os.environ.get("AWS_REGION")
            or "eu-central-1"
        )
        client = boto3.client("bedrock-runtime", region_name=region)
        _ = client.meta.region_name
    except Exception as exc:
        return False, f"bedrock client not buildable: {exc}"
    return True, "bedrock client built ok"


def _git_short_sha() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=Path(__file__).resolve().parent,
            stderr=subprocess.DEVNULL,
        )
        return out.decode("utf-8").strip()
    except Exception:
        return "unknown"


def _install_tool_stubs(monkeypatch, current_row: dict) -> None:
    """Install monkeypatched chat tool handlers ONCE — they read the row's
    ``data_fixture`` from a mutable holder so the harness loop can swap
    rows without re-stacking monkeypatch undo entries every iteration.

    The agent / handler / backend / Guardrail are exercised LIVE; only the
    data layer is faked. Mocking the tools is necessary because real tools
    touch the DB with seed data that (a) couples runs to seed state and
    (b) may include data the eval logs shouldn't see.

    Caller mutates ``current_row["row"]`` (and ``current_row["rag_docs"]``
    for the per-row dedup cache) before each ``send_turn`` call.
    """
    from app.agents.chat.tools import (
        profile_tool,
        rag_corpus_tool,
        teaching_feed_tool,
        transactions_tool,
    )

    async def _fake_get_transactions_handler(**_kwargs):
        transactions = current_row["row"]["data_fixture"].get("transactions") or []
        rows = [
            transactions_tool.TransactionRow(
                id=uuid.UUID(tx["id"]),
                booked_at=datetime.date.fromisoformat(tx["booked_at"]),
                description=tx["description"],
                amount_kopiykas=int(tx["amount_kopiykas"]),
                currency=tx["currency"],
                category_code=tx.get("category_code"),
                transaction_kind=tx.get("transaction_kind"),
            )
            for tx in transactions
        ]
        return transactions_tool.GetTransactionsOutput(
            rows=rows, row_count=len(rows), truncated=False
        )

    async def _fake_get_profile_handler(**_kwargs):
        return profile_tool.GetProfileOutput(
            summary=profile_tool.ProfileSummary(
                monthly_income_kopiykas=None,
                monthly_expenses_kopiykas=None,
                savings_ratio=None,
                health_score=None,
                currency="UAH",
                as_of=datetime.date.today(),
            ),
            category_breakdown=[],
            monthly_comparison=[],
        )

    async def _fake_search_financial_corpus_handler(**_kwargs):
        rag_docs = current_row.get("rag_docs") or []
        rows = [
            rag_corpus_tool.CorpusDocRow(
                source_id=doc["doc_id"],
                snippet=doc["content"][:1500],
                similarity=0.9,
            )
            for doc in rag_docs
        ]
        return rag_corpus_tool.SearchFinancialCorpusOutput(
            rows=rows, row_count=len(rows)
        )

    async def _fake_get_teaching_feed_handler(**_kwargs):
        return teaching_feed_tool.GetTeachingFeedOutput(
            rows=[], row_count=0
        )

    # The TOOL_MANIFEST is built at import time and freezes each ToolSpec's
    # ``handler`` attribute (frozen dataclass). Patching the source module
    # has no effect on the dispatcher's resolved handler. Build a new
    # manifest tuple of ToolSpecs whose ``handler`` points at our fakes,
    # then monkeypatch the module-level TOOL_MANIFEST. ``get_tool_spec``
    # iterates the manifest on every call, so the swap is picked up.
    import dataclasses

    from app.agents.chat import tools as tools_pkg

    fakes = {
        "get_transactions": _fake_get_transactions_handler,
        "get_profile": _fake_get_profile_handler,
        "search_financial_corpus": _fake_search_financial_corpus_handler,
        "get_teaching_feed": _fake_get_teaching_feed_handler,
    }
    new_manifest = tuple(
        dataclasses.replace(spec, handler=fakes[spec.name])
        if spec.name in fakes
        else spec
        for spec in tools_pkg.TOOL_MANIFEST
    )
    monkeypatch.setattr(tools_pkg, "TOOL_MANIFEST", new_manifest)
    monkeypatch.setattr(
        transactions_tool, "get_transactions_handler", _fake_get_transactions_handler
    )
    monkeypatch.setattr(
        profile_tool, "get_profile_handler", _fake_get_profile_handler
    )
    monkeypatch.setattr(
        rag_corpus_tool,
        "search_financial_corpus_handler",
        _fake_search_financial_corpus_handler,
    )
    monkeypatch.setattr(
        teaching_feed_tool,
        "get_teaching_feed_handler",
        _fake_get_teaching_feed_handler,
    )


class _ToolCallObserver(logging.Handler):
    """Capture ``chat.tool.result`` log records and accumulate the tool
    names that fired during a single ``send_turn`` invocation.

    The dispatcher emits ``chat.tool.result`` (INFO) on each tool call
    with ``tool_name`` in ``extra``; scraping it gives us the AC #5
    ``tool_calls_observed`` field without coupling to the agent's
    internals.
    """

    def __init__(self) -> None:
        super().__init__(level=logging.INFO)
        self.tool_names: list[str] = []

    def reset(self) -> None:
        self.tool_names = []

    def emit(self, record: logging.LogRecord) -> None:  # noqa: D401
        if record.getMessage() != "chat.tool.result":
            return
        name = getattr(record, "tool_name", None)
        if isinstance(name, str):
            self.tool_names.append(name)


async def _seed_synthetic_user(db: SQLModelAsyncSession) -> User:
    """Create a single throwaway User with chat-processing consent granted."""
    user = User(
        cognito_sub=f"chat-grounding-eval-{uuid.uuid4()}",
        email=f"cg-eval-{uuid.uuid4()}@example.invalid",
        is_verified=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    await consent_service.grant_consent(
        session=db,
        user=user,
        consent_type=CONSENT_TYPE_CHAT_PROCESSING,
        version=CURRENT_CHAT_CONSENT_VERSION,
        locale="en",
        ip=None,
        user_agent=None,
    )
    return user


async def _drive_row(
    handler: ChatSessionHandler,
    db: SQLModelAsyncSession,
    user: User,
    row: dict,
    observer: "_ToolCallObserver",
) -> tuple[str, str | None, list[str], str | None, str | None]:
    """Drive a single eval row through ``send_turn``.

    Returns ``(outcome, candidate_answer_or_none, observed_tool_calls, error_class_or_none, traceback_tail_or_none)``
    where ``outcome`` is one of:
      - ``"refused_ungrounded"``
      - ``"refused_other"``
      - ``"answered"``
    """
    handle = await handler.create_session(db, user)
    observer.reset()
    try:
        result = await handler.send_turn(db, handle, row["question"])
    except ChatGuardrailInterventionError as exc:
        if exc.intervention_kind == "grounding":
            return "refused_ungrounded", None, list(observer.tool_names), None, None
        return "refused_other", None, list(observer.tool_names), (
            f"ChatGuardrailInterventionError({exc.intervention_kind})"
        ), None
    except Exception as exc:  # noqa: BLE001
        tb = traceback.format_exc()
        logger.warning(
            "chat.grounding.eval.row_other_refusal",
            extra={
                "row_id": row["id"],
                "error_class": type(exc).__name__,
                "error_message": str(exc)[:300],
            },
        )
        return (
            "refused_other",
            None,
            list(observer.tool_names),
            type(exc).__name__,
            tb[-1500:],
        )
    finally:
        try:
            await handler.terminate_session(handle)
        except Exception:  # noqa: BLE001
            pass

    return "answered", result.assistant_message, list(observer.tool_names), None, None


def _classify_pass(row: dict, outcome: str, judge_score: dict | None) -> bool:
    expected = row["expected_outcome"]
    if outcome == "refused_ungrounded":
        return expected == "should_refuse_ungrounded"
    if outcome == "refused_other":
        return False  # excluded from aggregate; per-row pass=False is informational
    # answered — judge decides
    if judge_score is None:
        return False
    g = int(judge_score.get("groundedness", 0))
    if expected == "grounded_answer":
        return g >= 2
    return g >= 2  # for should_refuse_ungrounded, judge_score==2 means grounded refusal


def _resolve_guardrail_version() -> str:
    arn = settings.BEDROCK_GUARDRAIL_ARN or ""
    if ":" in arn:
        tail = arn.rsplit("/", 1)[-1]
        if ":" in tail:
            _, ver = tail.split(":", 1)
            return ver
    return "DRAFT"


def _resolve_guardrail_id() -> str:
    arn = settings.BEDROCK_GUARDRAIL_ARN or ""
    if not arn:
        return "(unset)"
    tail = arn.rsplit("/", 1)[-1]
    return tail.split(":", 1)[0] if ":" in tail else tail


def _resolve_model_id() -> str:
    return (
        getattr(settings, "CHAT_MODEL_ID", None)
        or getattr(settings, "BEDROCK_CHAT_MODEL_ID", None)
        or "(unknown)"
    )


def test_chat_grounding_harness_runs_and_emits_report(monkeypatch, request) -> None:
    db_ok, db_reason = _check_db_reachable()
    if not db_ok:
        pytest.skip(f"chat.grounding.eval.row_skipped — {db_reason}")
    bedrock_ok, bedrock_reason = _check_bedrock_client_buildable()
    if not bedrock_ok:
        pytest.skip(f"chat.grounding.eval.row_skipped — {bedrock_reason}")

    rows = _load_eval_set()
    assert rows, "eval_set.jsonl produced zero scorable rows"

    handler = ChatSessionHandler(build_backend())

    def _new_session() -> SQLModelAsyncSession:
        return SQLModelAsyncSession(_async_engine, expire_on_commit=False)

    # Install tool stubs ONCE; the closure reads the current row + cached
    # RAG docs from this dict, so per-iteration switches don't stack
    # monkeypatch undo entries.
    current_row: dict = {"row": rows[0], "rag_docs": []}
    _install_tool_stubs(monkeypatch, current_row)

    # Attach a tool-call observer to the dispatcher's logger so we can
    # surface AC #5 ``tool_calls_observed`` per row from real telemetry.
    dispatcher_logger = logging.getLogger("app.agents.chat.tools.dispatcher")
    observer = _ToolCallObserver()
    dispatcher_logger.addHandler(observer)

    per_row: list[dict] = []
    judge_error_count = 0
    excluded_other = 0
    total_judge_tokens = 0
    start = time.perf_counter()

    async def _run_all() -> None:
        nonlocal judge_error_count, excluded_other, total_judge_tokens
        async with _new_session() as db:
            user = await _seed_synthetic_user(db)
        for row in rows:
            row_start = time.perf_counter()
            # Resolve RAG docs once per row; both the tool stub and the
            # judge consume them.
            rag_docs = [
                _load_rag_doc(d)
                for d in row["data_fixture"].get("rag_corpus_doc_ids", [])
            ]
            current_row["row"] = row
            current_row["rag_docs"] = rag_docs

            async with _new_session() as db:
                outcome, candidate, observed, error_class, tb_tail = await _drive_row(
                    handler, db, user, row, observer
                )

            judge_score: dict | None = None
            if outcome == "answered":
                try:
                    judge_score, judge_tokens = await asyncio.to_thread(
                        judge_module.score_grounding,
                        row["question"],
                        row["data_fixture"].get("transactions"),
                        rag_docs,
                        candidate or "",
                        row["language"],
                    )
                    total_judge_tokens += judge_tokens
                    if str(judge_score.get("rationale", "")).startswith(
                        "parse-error"
                    ):
                        judge_error_count += 1
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "chat.grounding.eval.judge_failed",
                        extra={"row_id": row["id"], "error_class": type(exc).__name__},
                    )
                    judge_score = {
                        "groundedness": 0,
                        "rationale": f"judge-error: {type(exc).__name__}",
                    }
                    judge_error_count += 1

            if outcome == "refused_other":
                excluded_other += 1

            elapsed_ms = int((time.perf_counter() - row_start) * 1000)
            per_row.append(
                {
                    "id": row["id"],
                    "language": row["language"],
                    "outcome": outcome,
                    "expected_outcome": row["expected_outcome"],
                    "judge_groundedness": (
                        int(judge_score["groundedness"]) if judge_score else None
                    ),
                    "pass": _classify_pass(row, outcome, judge_score),
                    "elapsed_ms": elapsed_ms,
                    "tool_calls_observed": observed,
                    "judge_rationale": (
                        judge_score.get("rationale") if judge_score else None
                    ),
                    "candidate_answer_prefix": (candidate or "")[:240],
                    "error_class": error_class,
                    "traceback_tail": tb_tail,
                }
            )

    try:
        asyncio.run(_run_all())
    finally:
        dispatcher_logger.removeHandler(observer)
    elapsed_s = time.perf_counter() - start

    # ------------------------------------------------------------------
    # Aggregate metrics (AC #5)
    # ------------------------------------------------------------------
    scored = [r for r in per_row if r["outcome"] != "refused_other"]
    answered_rows = [r for r in scored if r["outcome"] == "answered"]
    grounded_answer_rows = [
        r for r in scored if r["expected_outcome"] == "grounded_answer"
    ]
    should_refuse_rows = [
        r for r in scored if r["expected_outcome"] == "should_refuse_ungrounded"
    ]

    grounding_rate = (
        sum(1 for r in scored if r["pass"]) / len(scored) if scored else 0.0
    )
    fp_block_rate = (
        sum(1 for r in grounded_answer_rows if r["outcome"] == "refused_ungrounded")
        / len(grounded_answer_rows)
        if grounded_answer_rows
        else 0.0
    )
    leak_rows = [
        r
        for r in should_refuse_rows
        if r["outcome"] == "answered"
        and (r["judge_groundedness"] or 0) < 2
    ]
    leak_rate = (
        len(leak_rows) / len(should_refuse_rows) if should_refuse_rows else 0.0
    )
    judge_error_rate = (
        judge_error_count / len(answered_rows) if answered_rows else 0.0
    )

    report = {
        "schema_version": 1,
        "run_id": str(uuid.uuid4()),
        "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
        "git_sha": _git_short_sha(),
        "guardrail_id": _resolve_guardrail_id(),
        "guardrail_version": _resolve_guardrail_version(),
        "model_id": _resolve_model_id(),
        "row_count": len(per_row),
        "row_count_scored": len(scored),
        "elapsed_seconds": elapsed_s,
        "total_judge_tokens": total_judge_tokens,
        "aggregate": {
            "grounding_rate": grounding_rate,
            "false_positive_block_rate": fp_block_rate,
            "ungrounded_leak_rate": leak_rate,
            "excluded_other_refusal_count": excluded_other,
            "judge_error_count": judge_error_count,
            "judge_error_rate": judge_error_rate,
        },
        "rows": per_row,
    }

    _RUNS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H-%M-%S")
    report_path = _RUNS_DIR / f"{ts}.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(
        "\nchat-grounding harness: "
        f"rows={len(per_row)} scored={len(scored)} "
        f"grounding_rate={grounding_rate:.3f} "
        f"fp_block_rate={fp_block_rate:.3f} "
        f"leak_rate={leak_rate:.3f} "
        f"excluded_other={excluded_other} "
        f"judge_errors={judge_error_count} "
        f"elapsed={elapsed_s:.1f}s "
        f"report={report_path}"
    )

    # Structural-validity gate first — a fully-broken judge run must not
    # silently masquerade as data (AC #5).
    assert judge_error_rate <= _MAX_ERROR_FRACTION, (
        f"judge_error_rate={judge_error_rate:.1%} exceeds "
        f"{_MAX_ERROR_FRACTION:.0%} budget — fix the judge prompt / model "
        f"before treating this run as a baseline (see report `judge_rationale`)"
    )

    # AC #5 — xfail (NOT fail) when grounding_rate < 0.90. The xfail
    # reason must include the actual rate so the report is readable from
    # the test output alone.
    if grounding_rate < _GROUNDING_RATE_TARGET:
        pytest.xfail(
            f"grounding_rate={grounding_rate:.3f} below NFR38 target "
            f"{_GROUNDING_RATE_TARGET:.2f} — see report at {report_path}; "
            "AC #1 tuning loop addresses the gap"
        )
