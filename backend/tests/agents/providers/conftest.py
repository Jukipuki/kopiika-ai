"""Shared fixtures for the cross-provider regression matrix (Story 9.5c).

The matrix exercises real LLM API calls across all three providers. It is
opt-in via the `provider_matrix` marker, which the default pytest sweep
deselects (see backend/pyproject.toml).

Key responsibilities of this conftest:

- Credential gating. If a given provider's env is missing, the test is
  skipped with a reason — not errored — so a developer with partial access
  (e.g. only Anthropic) can still exercise the subset locally.
- `LLM_PROVIDER_MATRIX_PROVIDERS` env filter (comma-separated allowlist)
  used by CI to disable Bedrock until OIDC lands.
- `settings.LLM_PROVIDER` monkeypatch + models.yaml cache reload per param,
  so each run exercises the factory's real routing code.
- Circuit-breaker neutralization (a per-param no-op monkeypatch on
  `check_circuit`) so a transient Bedrock throttle mid-run cannot contaminate
  the anthropic/openai params that follow.
- Run-report writer (`write_run_report`) producing structured JSON under
  `runs/` for reproducibility.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

PROVIDERS = ("anthropic", "openai", "bedrock")

HERE = Path(__file__).resolve().parent
FIXTURES_DIR = HERE / "fixtures"
RUNS_DIR = HERE / "runs"


def _provider_filter() -> set[str]:
    """Resolve `LLM_PROVIDER_MATRIX_PROVIDERS` env filter. Default: all three."""
    raw = os.environ.get("LLM_PROVIDER_MATRIX_PROVIDERS")
    if not raw:
        return set(PROVIDERS)
    return {p.strip() for p in raw.split(",") if p.strip()}


def _has_aws_credentials() -> bool:
    # Explicit env-var check first — cheapest, avoids importing boto3 in the
    # hot path when no AWS creds are set at all.
    if any(os.environ.get(k) for k in ("AWS_ACCESS_KEY_ID", "AWS_PROFILE", "AWS_ROLE_ARN")):
        return True
    try:
        import boto3
    except ImportError:
        return False
    try:
        creds = boto3.Session().get_credentials()
    except Exception:
        return False
    return creds is not None


def _provider_env_ok(provider: str) -> tuple[bool, str]:
    if provider == "anthropic":
        return (bool(os.environ.get("ANTHROPIC_API_KEY")), "ANTHROPIC_API_KEY not set")
    if provider == "openai":
        return (bool(os.environ.get("OPENAI_API_KEY")), "OPENAI_API_KEY not set")
    if provider == "bedrock":
        return (_has_aws_credentials(), "no AWS credentials in boto3 default chain")
    return (False, f"unknown provider {provider!r}")


def _models_yaml_sha() -> str:
    path = Path(__file__).resolve().parents[3] / "app" / "agents" / "models.yaml"
    if not path.is_file():
        return "unknown"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_sha() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            cwd=Path(__file__).resolve().parents[3],
        )
        return result.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


@pytest.fixture(autouse=True)
def _provider_setup(request, monkeypatch) -> dict[str, Any]:
    """Autouse fixture: gates on env, swaps `settings.LLM_PROVIDER`, neuters
    the circuit breaker, and yields a `provider_ctx` dict.

    Tests that are not parametrized over `provider` are a no-op (the fixture
    simply yields an empty context).
    """
    params = getattr(request.node, "callspec", None)
    provider = (params.params.get("provider") if params else None)
    if provider is None:
        yield {}
        return

    allowed = _provider_filter()
    if provider not in allowed:
        pytest.skip(f"provider={provider} not in LLM_PROVIDER_MATRIX_PROVIDERS={sorted(allowed)}")

    ok, reason = _provider_env_ok(provider)
    if not ok:
        pytest.skip(f"missing credentials for provider={provider}: {reason}")

    from app.agents import llm as llm_module
    from app.core.config import settings

    monkeypatch.setattr(settings, "LLM_PROVIDER", provider, raising=False)
    llm_module.reload_models_config_for_tests()
    # Neutralize circuit breaker so a Bedrock throttle mid-run cannot trip a
    # breaker and poison subsequent anthropic/openai params.
    monkeypatch.setattr(llm_module, "check_circuit", lambda p: None)

    ctx = {
        "provider": provider,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "git_sha": _git_sha(),
        "models_yaml_sha": _models_yaml_sha(),
    }
    yield ctx
    llm_module.reload_models_config_for_tests()


def load_fixture(name: str) -> Any:
    """Load a JSON fixture from the `fixtures/` sibling dir."""
    with (FIXTURES_DIR / name).open("r", encoding="utf-8") as fp:
        return json.load(fp)


def write_run_report(agent: str, provider: str, results: list[dict], ctx: dict) -> Path:
    """Write a structured run-report to `runs/<agent>-<provider>-<ts>.json`.

    The write is atomic: tmpfile + `os.replace`. Returns the final path.
    """
    RUNS_DIR.mkdir(exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    out = RUNS_DIR / f"{agent}-{provider}-{ts}.json"
    passed = sum(1 for r in results if r.get("passed"))
    total = len(results)
    payload = {
        "agent": agent,
        "provider": provider,
        "timestamp_utc": ctx.get("timestamp_utc"),
        "meta": {
            "git_sha": ctx.get("git_sha"),
            "models_yaml_sha": ctx.get("models_yaml_sha"),
            "pytest_version": _pytest_version(),
            "python_version": sys.version.split()[0],
        },
        "pass_rate_by_provider": {
            provider: {"passed": passed, "total": total, "rate": (passed / total) if total else 0.0}
        },
        "results": results,
    }
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, out)
    return out


def _pytest_version() -> str:
    try:
        import pytest as _pt
        return _pt.__version__
    except Exception:
        return "unknown"


def time_ms() -> int:
    return int(time.monotonic() * 1000)
