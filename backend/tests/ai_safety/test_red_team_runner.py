# Story 10.8b — Red-team safety runner. Marker-gated (`-m eval`); runs the
# Story 10.8a corpus end-to-end against the live ChatSessionHandler.send_turn
# pipeline (input validator → Guardrails input → hardened system prompt +
# canary detector → tool dispatcher → grounding → Guardrails output) and
# computes per-file / per-language / per-OWASP / per-jailbreak-family pass
# rates against ``baselines/baseline.json``.
#
# Out of scope per Story 10.8b §Scope Boundaries: corpus authoring (10.8a),
# chat-runtime patches, Guardrails-config tuning (10.6a), input-validator
# blocklist edits (10.4b), AgentCore Phase B coverage, multi-turn ladders,
# CloudWatch metrics (10.9), frontend assertions, third-party tooling.
"""Marker-gated safety runner driver (Story 10.8b AC #2-#7, #9)."""

from __future__ import annotations

import asyncio
import datetime
import logging
import os
import time
import traceback

import pytest
from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.agents.chat.canaries import get_canary_set
from app.agents.chat.canary_detector import ChatPromptLeakDetectedError
from app.agents.chat.chat_backend import (
    ChatGuardrailInterventionError,
    ChatTransientError,
)
from app.agents.chat.input_validator import ChatInputBlockedError
from app.agents.chat.tools.tool_errors import (
    ChatToolAuthorizationError,
    ChatToolLoopExceededError,
    ChatToolNotAllowedError,
)
from app.core.config import settings
from app.core.consent import (
    CONSENT_TYPE_CHAT_PROCESSING,
    CURRENT_CHAT_CONSENT_VERSION,
)
from app.core.database import engine as _async_engine, get_sync_session
from app.models.user import User
from app.services import consent_service
from tests.ai_safety.runner.corpus_loader import load_corpus
from tests.ai_safety.runner.outcome_judge import judge_row
from tests.ai_safety.runner.report import (
    BASELINE_PATH,
    OVERALL_PASS_RATE_GATE,
    BlessRefused,
    bless_baseline,
    build_run_report,
    load_baseline,
    write_run_report,
)

logger = logging.getLogger(__name__)
pytestmark = [pytest.mark.integration, pytest.mark.eval]


# ----------------------------------------------------------------------
# Pre-flight skip helpers (mirror the grounding harness)
# ----------------------------------------------------------------------


def _check_db_reachable() -> tuple[bool, str]:
    try:
        with get_sync_session() as session:
            session.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        return False, f"database unreachable: {exc}"
    return True, "db reachable"


def _check_bedrock_provider() -> tuple[bool, str]:
    if settings.LLM_PROVIDER != "bedrock":
        return (
            False,
            "safety.runner.skipped — non-bedrock provider; safety harness "
            "asserts Bedrock-Guardrails coverage",
        )
    if not settings.BEDROCK_GUARDRAIL_ARN:
        return False, "BEDROCK_GUARDRAIL_ARN not configured"
    try:
        import boto3  # type: ignore

        region = (
            getattr(settings, "AWS_REGION", None)
            or os.environ.get("AWS_REGION")
            or "eu-central-1"
        )
        client = boto3.client("bedrock-runtime", region_name=region)
        _ = client.meta.region_name
    except Exception as exc:  # noqa: BLE001
        return False, f"bedrock client not buildable: {exc}"
    return True, "bedrock provider configured"


def _resolve_guardrail_id() -> str:
    arn = settings.BEDROCK_GUARDRAIL_ARN or ""
    if not arn:
        return "(unset)"
    tail = arn.rsplit("/", 1)[-1]
    return tail.split(":", 1)[0] if ":" in tail else tail


def _resolve_guardrail_version() -> str:
    arn = settings.BEDROCK_GUARDRAIL_ARN or ""
    if ":" in arn:
        tail = arn.rsplit("/", 1)[-1]
        if ":" in tail:
            _, ver = tail.split(":", 1)
            return ver
    return "DRAFT"


def _resolve_model_id() -> str:
    return (
        getattr(settings, "CHAT_MODEL_ID", None)
        or getattr(settings, "BEDROCK_CHAT_MODEL_ID", None)
        or "(unknown)"
    )


# ----------------------------------------------------------------------
# Tool-call observer — mirrors tests/eval/chat_grounding/test_chat_grounding_harness.py
# (vendored with provenance comment per Story 10.8b Task 6 sub-bullet).
# ----------------------------------------------------------------------


class _ToolCallObserver(logging.Handler):
    # Source: tests/eval/chat_grounding/test_chat_grounding_harness.py.
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


# ----------------------------------------------------------------------
# Per-row driver
# ----------------------------------------------------------------------


async def _seed_synthetic_user(db) -> "User":
    """Create one throwaway user with chat-processing consent granted.

    Mirrors ``tests/eval/chat_grounding/test_chat_grounding_harness.py:_seed_synthetic_user``.
    Lives in the test module (not a fixture) so it runs inside the test's
    own ``asyncio.run`` loop — session-scoped async fixtures cannot share
    asyncpg connections with the test's loop.
    """
    import uuid as _uuid

    user = User(
        cognito_sub=f"safety-runner-{_uuid.uuid4()}",
        email=f"safety-runner-{_uuid.uuid4()}@example.invalid",
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


async def _drive_one(
    handler,
    user,
    entry,
    observer: _ToolCallObserver,
):
    def _new_session() -> SQLModelAsyncSession:
        return SQLModelAsyncSession(_async_engine, expire_on_commit=False)

    observer.reset()
    candidate: str | None = None
    exception: BaseException | None = None
    error_class: str | None = None
    tb_tail: str | None = None
    elapsed_start = time.perf_counter()
    handle = None
    async with _new_session() as db:
        try:
            handle = await handler.create_session(db, user)
            result = await handler.send_turn(db, handle, entry.prompt)
            candidate = result.assistant_message
        except (
            ChatInputBlockedError,
            ChatPromptLeakDetectedError,
            ChatGuardrailInterventionError,
            ChatToolLoopExceededError,
            ChatToolNotAllowedError,
            ChatToolAuthorizationError,
            ChatTransientError,
        ) as exc:
            exception = exc
        except Exception as exc:  # noqa: BLE001 — judge surfaces as error outcome
            exception = exc
            error_class = type(exc).__name__
            tb_tail = traceback.format_exc()[-1500:]
        finally:
            if handle is not None:
                try:
                    await handler.terminate_session(handle)
                except Exception:  # noqa: BLE001
                    pass
    elapsed_ms = int((time.perf_counter() - elapsed_start) * 1000)
    return candidate, exception, error_class, tb_tail, elapsed_ms, list(observer.tool_names)


# ----------------------------------------------------------------------
# Default-mode test — runs the whole corpus and gates on AC #7
# ----------------------------------------------------------------------


def test_red_team_corpus_runs_under_gate(
    safety_runner_handler, safety_runner_user_holder
) -> None:
    db_ok, db_reason = _check_db_reachable()
    if not db_ok:
        pytest.skip(f"safety.runner.skipped — {db_reason}")
    bedrock_ok, bedrock_reason = _check_bedrock_provider()
    if not bedrock_ok:
        pytest.skip(bedrock_reason)

    if os.environ.get("KOPIIKA_BLESS_RED_TEAM_BASELINE") == "1" and os.environ.get("CI") == "true":
        pytest.fail(
            "KOPIIKA_BLESS_RED_TEAM_BASELINE=1 must NOT be set in CI — "
            "bless mode is for the corpus owner's manual workflow only."
        )

    handler = safety_runner_handler

    dispatcher_logger = logging.getLogger("app.agents.chat.tools.dispatcher")
    observer = _ToolCallObserver()
    dispatcher_logger.addHandler(observer)

    rows = []
    start = time.perf_counter()
    canary_set_version_id = "(unresolved)"
    try:

        async def _run_all() -> None:
            nonlocal canary_set_version_id
            async with SQLModelAsyncSession(_async_engine, expire_on_commit=False) as db:
                user = await _seed_synthetic_user(db)
            safety_runner_user_holder["id"] = user.id
            canary_set = await get_canary_set()
            canary_set_version_id = canary_set.version_id
            entries = await load_corpus(canary_set=canary_set)
            for entry in entries:
                candidate, exc, err_class, tb_tail, elapsed_ms, observed = await _drive_one(
                    handler, user, entry, observer
                )
                rows.append(
                    judge_row(
                        entry,
                        exception=exc,
                        candidate_text=candidate,
                        observed_tool_hops=len(observed),
                        elapsed_ms=elapsed_ms,
                        error_class=err_class,
                        traceback_tail=tb_tail,
                    )
                )

        asyncio.run(_run_all())
    finally:
        dispatcher_logger.removeHandler(observer)

    elapsed_seconds = time.perf_counter() - start
    baseline = load_baseline()
    report = build_run_report(
        rows,
        elapsed_seconds=elapsed_seconds,
        guardrail_id=_resolve_guardrail_id(),
        guardrail_version=_resolve_guardrail_version(),
        model_id=_resolve_model_id(),
        canary_set_version_id=canary_set_version_id,
        baseline=baseline,
    )
    report_path = write_run_report(report)
    _emit_step_summary(report, report_path)

    aggregate = report["aggregate"]
    overall = aggregate["overall_pass_rate"]
    nfr37_failures = aggregate.get("nfr37_critical_surface_failures") or []
    hard_regressions = aggregate.get("regression_hard_failures") or []

    if nfr37_failures:
        pytest.fail(
            "Safety harness NFR37 critical-surface gate failed:\n"
            + "\n".join(nfr37_failures)
            + f"\nReport: {report_path}"
        )
    if overall < OVERALL_PASS_RATE_GATE:
        pytest.fail(
            f"Safety harness overall_pass_rate={overall:.3f} below "
            f"{OVERALL_PASS_RATE_GATE:.2f}. Report: {report_path}"
        )
    if hard_regressions and baseline is not None:
        pytest.fail(
            "Safety harness baseline regression:\n"
            + "\n".join(hard_regressions)
            + f"\nReport: {report_path}"
        )

    # First-run side-effect: if no baseline exists yet, write one. This is the
    # "first run on this story's PR establishes baselines/baseline.json"
    # behaviour (Scope Boundaries §No retroactive baseline). Subsequent runs
    # use the committed baseline; bless flow is the only way to update it.
    if baseline is None:
        BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
        BASELINE_PATH.write_text(
            __dumps_baseline(report),
            encoding="utf-8",
        )


# ----------------------------------------------------------------------
# Bless-mode test — env-gated, never runs in CI
# ----------------------------------------------------------------------


@pytest.mark.skipif(
    os.environ.get("KOPIIKA_BLESS_RED_TEAM_BASELINE") != "1",
    reason="set KOPIIKA_BLESS_RED_TEAM_BASELINE=1 to invoke the bless flow",
)
def test_red_team_bless_baseline(
    safety_runner_handler, safety_runner_user_holder
) -> None:
    db_ok, db_reason = _check_db_reachable()
    if not db_ok:
        pytest.skip(f"safety.runner.skipped — {db_reason}")
    bedrock_ok, bedrock_reason = _check_bedrock_provider()
    if not bedrock_ok:
        pytest.skip(bedrock_reason)

    handler = safety_runner_handler
    dispatcher_logger = logging.getLogger("app.agents.chat.tools.dispatcher")
    observer = _ToolCallObserver()
    dispatcher_logger.addHandler(observer)

    rows = []
    start = time.perf_counter()
    canary_set_version_id = "(unresolved)"
    try:

        async def _run_all() -> None:
            nonlocal canary_set_version_id
            async with SQLModelAsyncSession(_async_engine, expire_on_commit=False) as db:
                user = await _seed_synthetic_user(db)
            safety_runner_user_holder["id"] = user.id
            canary_set = await get_canary_set()
            canary_set_version_id = canary_set.version_id
            entries = await load_corpus(canary_set=canary_set)
            for entry in entries:
                candidate, exc, err_class, tb_tail, elapsed_ms, observed = await _drive_one(
                    handler, user, entry, observer
                )
                rows.append(
                    judge_row(
                        entry,
                        exception=exc,
                        candidate_text=candidate,
                        observed_tool_hops=len(observed),
                        elapsed_ms=elapsed_ms,
                        error_class=err_class,
                        traceback_tail=tb_tail,
                    )
                )

        asyncio.run(_run_all())
    finally:
        dispatcher_logger.removeHandler(observer)

    elapsed_seconds = time.perf_counter() - start
    baseline = load_baseline()
    report = build_run_report(
        rows,
        elapsed_seconds=elapsed_seconds,
        guardrail_id=_resolve_guardrail_id(),
        guardrail_version=_resolve_guardrail_version(),
        model_id=_resolve_model_id(),
        canary_set_version_id=canary_set_version_id,
        baseline=baseline,
    )
    write_run_report(report)
    try:
        new_path = bless_baseline(report)
    except BlessRefused as exc:
        pytest.fail(f"baseline bless refused: {exc}")
    old_rate = (
        baseline["aggregate"]["overall_pass_rate"]
        if baseline and "aggregate" in baseline
        else None
    )
    new_rate = report["aggregate"]["overall_pass_rate"]
    delta_pp = (
        round((new_rate - old_rate) * 100.0, 4) if old_rate is not None else None
    )
    logger.info(
        "safety.runner.baseline_blessed",
        extra={
            "old_pass_rate": old_rate,
            "new_pass_rate": new_rate,
            "delta_pp": delta_pp,
            "blessed_by_user": os.environ.get("USER", "unknown"),
            "git_sha": report["git_sha"],
            "canary_set_version_id": report["canary_set_version_id"],
        },
    )
    print(
        f"\n✅ baseline blessed → {new_path}\n"
        f"   old_pass_rate={old_rate} new_pass_rate={new_rate} delta_pp={delta_pp}\n"
        f"   commit baselines/baseline.json in this PR for the gate to pick it up."
    )


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def __dumps_baseline(report: dict) -> str:
    import json

    return json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True)


def _emit_step_summary(report: dict, report_path) -> None:
    """Render a markdown summary table to GitHub Actions Step Summary (AC #10)."""
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    lines = [
        "## Red-Team Safety Runner",
        f"- Report: `{report_path}`",
        f"- Overall pass rate: **{report['aggregate']['overall_pass_rate']:.3f}**",
        f"- Rows: {report['row_count']} (errors: {report['aggregate']['error_count']})",
        f"- Elapsed: {report['elapsed_seconds']:.1f}s",
        f"- Git: `{report['git_sha']}` ({report['git_branch']})",
        f"- Guardrail: `{report['guardrail_id']}@{report['guardrail_version']}`",
        f"- Canary set version: `{report['canary_set_version_id']}`",
        "",
        "### Per-file pass rate",
        "| File | pass | fail | total | rate |",
        "|------|-----:|-----:|------:|-----:|",
    ]
    for fname, bucket in sorted(report["aggregate"]["by_file"].items()):
        lines.append(
            f"| `{fname}` | {bucket['pass']} | {bucket['fail']} | {bucket['total']} | {bucket['pass_rate']:.3f} |"
        )
    nfr37 = report["aggregate"].get("nfr37_critical_surface_failures") or []
    if nfr37:
        lines.append("\n### NFR37 critical-surface failures\n")
        for line in nfr37:
            lines.append(f"- {line}")
    hard = report["aggregate"].get("regression_hard_failures") or []
    if hard:
        lines.append("\n### Hard regressions\n")
        for line in hard:
            lines.append(f"- {line}")
    soft = report["aggregate"].get("regression_warnings") or []
    if soft:
        lines.append("\n### Soft regression warnings (informational)\n")
        for line in soft:
            lines.append(f"- {line}")
    body = "\n".join(lines) + "\n"
    print(body)
    if summary_path:
        try:
            with open(summary_path, "a", encoding="utf-8") as fh:
                fh.write(body)
        except OSError as exc:
            logger.warning(
                "safety.runner.step_summary_write_failed path=%s err=%s",
                summary_path,
                exc,
            )


# Suppress unused-import false-positive for type-checker happiness.
_ = datetime
