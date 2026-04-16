from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.version import APP_VERSION
from app.main import app


def _read_version_file_directly() -> str:
    # Walk up from this test file to the repo root and read /VERSION. Done
    # independently of app.core.version so the test fails loudly if the file
    # moves/disappears — relying solely on APP_VERSION would let both the
    # endpoint and the test silently collapse to the fallback sentinel.
    for candidate in Path(__file__).resolve().parents:
        version_file = candidate / "VERSION"
        if version_file.is_file():
            return version_file.read_text(encoding="utf-8").strip()
    raise AssertionError("VERSION file not found walking up from tests/")


@pytest.mark.asyncio
async def test_health_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"

    # Independently re-read /VERSION so the test validates the wiring end-to-
    # end, not just that the endpoint agrees with whatever APP_VERSION loaded.
    version_on_disk = _read_version_file_directly()
    assert data["version"] == version_on_disk
    assert APP_VERSION == version_on_disk, (
        "APP_VERSION drifted from /VERSION — likely fell back to the "
        "sentinel during import. Fix backend/app/core/version.py."
    )


@pytest.mark.asyncio
async def test_health_response_format():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    data = response.json()
    assert set(data.keys()) == {"status", "version"}
