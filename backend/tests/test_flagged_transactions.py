"""Tests for GET /api/v1/transactions/flagged endpoint (Story 6.3)."""
import os
import tempfile
import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession
from unittest.mock import AsyncMock, MagicMock

from app.models.transaction import Transaction
from app.models.upload import Upload
from app.models.user import User
from app.services.transaction_service import compute_dedup_hash


def _utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def flagged_async_engine():
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await engine.dispose()
    os.unlink(db_path)


@pytest_asyncio.fixture
async def flagged_async_session(flagged_async_engine) -> SQLModelAsyncSession:
    async with SQLModelAsyncSession(flagged_async_engine) as session:
        yield session


def _auth_override(cognito_sub: str):
    async def mock_payload():
        return {"sub": cognito_sub}
    return mock_payload


@pytest_asyncio.fixture
async def flagged_client(flagged_async_engine):
    from app.api.deps import get_db, get_cognito_service, get_rate_limiter
    from app.main import app

    async def override_get_db():
        async with SQLModelAsyncSession(flagged_async_engine) as session:
            yield session

    mock_cognito = MagicMock()
    mock_rate = AsyncMock()
    mock_rate.check_rate_limit.return_value = None
    mock_rate.check_upload_rate_limit.return_value = None

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_cognito_service] = lambda: mock_cognito
    app.dependency_overrides[get_rate_limiter] = lambda: mock_rate

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


async def _seed_user_with_transactions(
    session: SQLModelAsyncSession,
    cognito_sub: str,
    email: str,
    flagged_txns: list[dict] | None = None,
) -> tuple[uuid.UUID, uuid.UUID]:
    """Seed user + upload + transactions. flagged_txns is a list of dicts with txn overrides."""
    user_id = uuid.uuid4()
    upload_id = uuid.uuid4()

    user = User(id=user_id, email=email, cognito_sub=cognito_sub, locale="en")
    session.add(user)
    await session.flush()

    upload = Upload(
        id=upload_id, user_id=user_id, file_name="test.csv",
        s3_key=f"{user_id}/test.csv", file_size=100,
        mime_type="text/csv", detected_format="monobank",
    )
    session.add(upload)
    await session.flush()

    for i, spec in enumerate(flagged_txns or []):
        txn = Transaction(
            user_id=user_id,
            upload_id=upload_id,
            date=spec.get("date", datetime(2026, 1, i + 1)),
            description=spec.get("description", f"Unknown Merchant {i}"),
            amount=spec.get("amount", -10000),
            currency_code=spec.get("currency_code", 980),
            raw_data=spec.get("raw_data"),
            dedup_hash=f"hash-{user_id}-{i}",
            is_flagged_for_review=spec.get("is_flagged_for_review", False),
            category=spec.get("category", "other"),
            confidence_score=spec.get("confidence_score", 0.4),
            uncategorized_reason=spec.get("uncategorized_reason", None),
        )
        session.add(txn)

    await session.commit()
    return user_id, upload_id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFlaggedTransactionsEndpoint:
    """Story 6.3: GET /api/v1/transactions/flagged."""

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_flagged_transactions(
        self, flagged_client, flagged_async_session
    ):
        """Returns 200 with empty list when user has no flagged transactions."""
        from app.core.security import get_current_user_payload
        from app.main import app

        cognito_sub = "flagged-empty-sub"
        await _seed_user_with_transactions(
            flagged_async_session,
            cognito_sub,
            "flagged-empty@test.com",
            flagged_txns=[
                {"is_flagged_for_review": False, "category": "groceries", "uncategorized_reason": None},
            ],
        )
        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)

        try:
            response = await flagged_client.get("/api/v1/transactions/flagged")
            assert response.status_code == 200
            assert response.json() == []
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_returns_flagged_transactions_with_correct_fields(
        self, flagged_client, flagged_async_session
    ):
        """Returns flagged transactions with correct camelCase fields."""
        from app.core.security import get_current_user_payload
        from app.main import app

        cognito_sub = "flagged-fields-sub"
        await _seed_user_with_transactions(
            flagged_async_session,
            cognito_sub,
            "flagged-fields@test.com",
            flagged_txns=[
                {
                    "is_flagged_for_review": True,
                    "category": "uncategorized",
                    "uncategorized_reason": "low_confidence",
                    "description": "Mystery Shop",
                    "amount": -25000,
                    "date": datetime(2026, 3, 15),
                },
            ],
        )
        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)

        try:
            response = await flagged_client.get("/api/v1/transactions/flagged")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            txn = data[0]
            assert txn["description"] == "Mystery Shop"
            assert txn["amount"] == -25000
            assert txn["date"] == "2026-03-15"
            assert txn["uncategorizedReason"] == "low_confidence"
            assert "id" in txn
            assert "uploadId" in txn
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_returns_all_reason_types(
        self, flagged_client, flagged_async_session
    ):
        """All three uncategorized_reason values are returned correctly."""
        from app.core.security import get_current_user_payload
        from app.main import app

        cognito_sub = "flagged-reasons-sub"
        await _seed_user_with_transactions(
            flagged_async_session,
            cognito_sub,
            "flagged-reasons@test.com",
            flagged_txns=[
                {"is_flagged_for_review": True, "uncategorized_reason": "low_confidence", "date": datetime(2026, 3, 1)},
                {"is_flagged_for_review": True, "uncategorized_reason": "parse_failure", "date": datetime(2026, 3, 2)},
                {"is_flagged_for_review": True, "uncategorized_reason": "llm_unavailable", "date": datetime(2026, 3, 3)},
            ],
        )
        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)

        try:
            response = await flagged_client.get("/api/v1/transactions/flagged")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 3
            reasons = {txn["uncategorizedReason"] for txn in data}
            assert reasons == {"low_confidence", "parse_failure", "llm_unavailable"}
            # Verify date DESC sort order
            dates = [txn["date"] for txn in data]
            assert dates == sorted(dates, reverse=True)
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_tenant_isolation_returns_only_requesting_users_flagged(
        self, flagged_client, flagged_async_session
    ):
        """User A cannot see user B's flagged transactions."""
        from app.core.security import get_current_user_payload
        from app.main import app

        # User A with 2 flagged
        await _seed_user_with_transactions(
            flagged_async_session,
            "flagged-isolation-a",
            "flagged-iso-a@test.com",
            flagged_txns=[
                {"is_flagged_for_review": True, "uncategorized_reason": "low_confidence"},
                {"is_flagged_for_review": True, "uncategorized_reason": "parse_failure"},
            ],
        )
        # User B with 1 flagged
        await _seed_user_with_transactions(
            flagged_async_session,
            "flagged-isolation-b",
            "flagged-iso-b@test.com",
            flagged_txns=[
                {"is_flagged_for_review": True, "uncategorized_reason": "llm_unavailable"},
            ],
        )

        # Query as user A — should see only 2
        app.dependency_overrides[get_current_user_payload] = _auth_override("flagged-isolation-a")
        try:
            response = await flagged_client.get("/api/v1/transactions/flagged")
            assert response.status_code == 200
            assert len(response.json()) == 2
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

        # Query as user B — should see only 1
        app.dependency_overrides[get_current_user_payload] = _auth_override("flagged-isolation-b")
        try:
            response = await flagged_client.get("/api/v1/transactions/flagged")
            assert response.status_code == 200
            assert len(response.json()) == 1
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_unauthenticated_returns_401_or_403(self, flagged_client):
        """Requires valid JWT — returns 401 or 403 without auth."""
        response = await flagged_client.get("/api/v1/transactions/flagged")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_currency_unknown_reason_and_raw_surfaced(
        self, flagged_client, flagged_async_session
    ):
        """Story 2.9: GET /transactions/flagged exposes currency_unknown + currencyUnknownRaw."""
        from app.core.security import get_current_user_payload
        from app.main import app

        cognito_sub = "flagged-currency-sub"
        await _seed_user_with_transactions(
            flagged_async_session,
            cognito_sub,
            "flagged-currency@test.com",
            flagged_txns=[
                {
                    "is_flagged_for_review": True,
                    "uncategorized_reason": "currency_unknown",
                    "currency_code": 0,
                    "raw_data": {"Валюта": "XYZ", "Сума": "-10.00"},
                    "description": "Exotic Exchange",
                    "date": datetime(2026, 3, 15),
                },
            ],
        )
        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)

        try:
            response = await flagged_client.get("/api/v1/transactions/flagged")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["uncategorizedReason"] == "currency_unknown"
            assert data[0]["currencyUnknownRaw"] == "XYZ"
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_non_flagged_not_included(
        self, flagged_client, flagged_async_session
    ):
        """Non-flagged transactions are not included in the response."""
        from app.core.security import get_current_user_payload
        from app.main import app

        cognito_sub = "flagged-mix-sub"
        await _seed_user_with_transactions(
            flagged_async_session,
            cognito_sub,
            "flagged-mix@test.com",
            flagged_txns=[
                {"is_flagged_for_review": True, "uncategorized_reason": "low_confidence"},
                {"is_flagged_for_review": False, "category": "groceries", "uncategorized_reason": None},
                {"is_flagged_for_review": False, "category": "transport", "uncategorized_reason": None},
            ],
        )
        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)

        try:
            response = await flagged_client.get("/api/v1/transactions/flagged")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["uncategorizedReason"] == "low_confidence"
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)
