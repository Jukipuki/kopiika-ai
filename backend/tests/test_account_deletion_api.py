"""Tests for DELETE /api/v1/users/me endpoint (Story 5.5)."""
import os
import tempfile
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.models.consent import UserConsent
from app.models.financial_health_score import FinancialHealthScore
from app.models.financial_profile import FinancialProfile
from app.models.flagged_import_row import FlaggedImportRow
from app.models.insight import Insight
from app.models.processing_job import ProcessingJob
from app.models.transaction import Transaction
from app.models.upload import Upload
from app.models.user import User


# ==================== Fixtures ====================


@pytest_asyncio.fixture
async def del_api_engine():
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)
    async with engine.begin() as conn:
        # Enable FK enforcement for SQLite
        await conn.execute(text("PRAGMA foreign_keys = ON"))
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await engine.dispose()
    os.unlink(db_path)


@pytest_asyncio.fixture
async def del_api_session(del_api_engine) -> SQLModelAsyncSession:
    async with SQLModelAsyncSession(del_api_engine) as session:
        yield session


def _auth_override(cognito_sub: str):
    async def mock_payload():
        return {"sub": cognito_sub}
    return mock_payload


async def _create_user(session: SQLModelAsyncSession, cognito_sub: str, email: str):
    user_id = uuid.uuid4()
    user = User(id=user_id, email=email, cognito_sub=cognito_sub, locale="en")
    session.add(user)
    await session.flush()
    return user_id


async def _seed_user_data(session: SQLModelAsyncSession, user_id: uuid.UUID):
    """Seed a full set of user data for deletion testing."""
    upload_id = uuid.uuid4()
    session.add(Upload(
        id=upload_id, user_id=user_id, file_name="stmt.csv",
        s3_key=f"{user_id}/stmt.csv", file_size=1024, mime_type="text/csv",
    ))
    await session.flush()
    session.add(Transaction(
        user_id=user_id, upload_id=upload_id, date=datetime(2026, 1, 15),
        description="Groceries", amount=-5000, dedup_hash=f"h-{user_id}-1",
        category="groceries",
    ))
    session.add(Insight(
        user_id=user_id, upload_id=upload_id, headline="Save more",
        key_metric="50%", why_it_matters="Important", deep_dive="Details",
        category="spending",
    ))
    session.add(FinancialProfile(
        user_id=user_id, total_income=100000, total_expenses=70000,
        category_totals={"groceries": 50000},
    ))
    session.add(FinancialHealthScore(
        user_id=user_id, score=72, calculated_at=datetime(2026, 2, 1),
        breakdown={"savings_ratio": 80},
    ))
    session.add(UserConsent(
        user_id=user_id, consent_type="ai_processing", version="1",
        granted_at=datetime(2026, 1, 1), locale="en",
    ))
    job_id = uuid.uuid4()
    session.add(ProcessingJob(
        id=job_id, user_id=user_id, upload_id=upload_id,
        status="completed",
    ))
    session.add(FlaggedImportRow(
        user_id=user_id, upload_id=upload_id,
        row_number=1, raw_data={"desc": "Unknown"}, reason="unrecognized",
    ))
    await session.flush()
    return upload_id


@pytest_asyncio.fixture
async def del_client(del_api_engine):
    from app.api.deps import get_db, get_cognito_service, get_rate_limiter
    from app.main import app

    async def override_get_db():
        async with SQLModelAsyncSession(del_api_engine) as session:
            yield session

    mock_cognito = MagicMock()
    mock_cognito.delete_user.return_value = {"deleted": True}
    mock_rate = AsyncMock()
    mock_rate.check_rate_limit.return_value = None

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_cognito_service] = lambda: mock_cognito
    app.dependency_overrides[get_rate_limiter] = lambda: mock_rate

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, mock_cognito

    app.dependency_overrides.clear()


# ==================== Tests ====================


class TestAccountDeletion:
    """Test DELETE /api/v1/users/me."""

    @pytest.mark.asyncio
    @patch("app.services.account_deletion_service.delete_s3_objects")
    async def test_successful_deletion_returns_204(
        self, mock_s3_delete, del_client, del_api_session
    ):
        """Successful deletion removes user + all child data, returns 204."""
        from app.core.security import get_current_user_payload
        from app.main import app

        client, mock_cognito = del_client

        cognito_sub = "del-user-sub"
        user_id = await _create_user(del_api_session, cognito_sub, "del@test.com")
        await _seed_user_data(del_api_session, user_id)
        await del_api_session.commit()

        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)
        try:
            response = await client.delete("/api/v1/users/me")
            assert response.status_code == 204

            # Verify S3 deletion called with correct keys
            mock_s3_delete.assert_called_once()
            s3_keys = mock_s3_delete.call_args[0][0]
            assert f"{user_id}/stmt.csv" in s3_keys

            # Verify Cognito deletion called
            mock_cognito.delete_user.assert_called_once_with(cognito_sub)

            # Verify user and all child data removed from DB
            async with SQLModelAsyncSession(del_api_session.bind) as verify_session:
                user = (await verify_session.exec(
                    select(User).where(User.id == user_id)
                )).first()
                assert user is None

                uploads = (await verify_session.exec(
                    select(Upload).where(Upload.user_id == user_id)
                )).all()
                assert len(uploads) == 0

                transactions = (await verify_session.exec(
                    select(Transaction).where(Transaction.user_id == user_id)
                )).all()
                assert len(transactions) == 0

                insights = (await verify_session.exec(
                    select(Insight).where(Insight.user_id == user_id)
                )).all()
                assert len(insights) == 0

                profiles = (await verify_session.exec(
                    select(FinancialProfile).where(FinancialProfile.user_id == user_id)
                )).all()
                assert len(profiles) == 0

                scores = (await verify_session.exec(
                    select(FinancialHealthScore).where(FinancialHealthScore.user_id == user_id)
                )).all()
                assert len(scores) == 0

                consents = (await verify_session.exec(
                    select(UserConsent).where(UserConsent.user_id == user_id)
                )).all()
                assert len(consents) == 0

                jobs = (await verify_session.exec(
                    select(ProcessingJob).where(ProcessingJob.user_id == user_id)
                )).all()
                assert len(jobs) == 0

                flagged = (await verify_session.exec(
                    select(FlaggedImportRow).where(FlaggedImportRow.user_id == user_id)
                )).all()
                assert len(flagged) == 0
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    @patch("app.services.account_deletion_service.delete_s3_objects")
    async def test_tenant_isolation(
        self, mock_s3_delete, del_client, del_api_session
    ):
        """Deleting user A does not affect user B's data."""
        from app.core.security import get_current_user_payload
        from app.main import app

        client, _ = del_client

        # Create user A with data
        user_a_id = await _create_user(del_api_session, "del-a-sub", "a@test.com")
        await _seed_user_data(del_api_session, user_a_id)

        # Create user B with data
        user_b_id = await _create_user(del_api_session, "del-b-sub", "b@test.com")
        await _seed_user_data(del_api_session, user_b_id)
        await del_api_session.commit()

        # Delete user A
        app.dependency_overrides[get_current_user_payload] = _auth_override("del-a-sub")
        try:
            response = await client.delete("/api/v1/users/me")
            assert response.status_code == 204

            # Verify user B's data is intact
            async with SQLModelAsyncSession(del_api_session.bind) as verify_session:
                user_b = (await verify_session.exec(
                    select(User).where(User.id == user_b_id)
                )).first()
                assert user_b is not None

                b_uploads = (await verify_session.exec(
                    select(Upload).where(Upload.user_id == user_b_id)
                )).all()
                assert len(b_uploads) == 1

                b_transactions = (await verify_session.exec(
                    select(Transaction).where(Transaction.user_id == user_b_id)
                )).all()
                assert len(b_transactions) == 1
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_unauthenticated_returns_401(self, del_client):
        """Unauthenticated request returns 401."""
        client, _ = del_client
        response = await client.delete("/api/v1/users/me")
        assert response.status_code in (401, 403)

    @pytest.mark.asyncio
    @patch("app.services.account_deletion_service.delete_s3_objects")
    async def test_s3_deletion_called_with_correct_keys(
        self, mock_s3_delete, del_client, del_api_session
    ):
        """S3 deletion is called with all user's upload S3 keys."""
        from app.core.security import get_current_user_payload
        from app.main import app

        client, _ = del_client

        cognito_sub = "del-s3-sub"
        user_id = await _create_user(del_api_session, cognito_sub, "s3@test.com")

        # Add multiple uploads
        for i in range(3):
            upload_id = uuid.uuid4()
            del_api_session.add(Upload(
                id=upload_id, user_id=user_id, file_name=f"file{i}.csv",
                s3_key=f"{user_id}/file{i}.csv", file_size=512,
                mime_type="text/csv",
            ))
        await del_api_session.commit()

        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)
        try:
            response = await client.delete("/api/v1/users/me")
            assert response.status_code == 204

            mock_s3_delete.assert_called_once()
            s3_keys = mock_s3_delete.call_args[0][0]
            assert len(s3_keys) == 3
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    @patch("app.services.account_deletion_service.delete_s3_objects")
    async def test_cognito_deletion_called(
        self, mock_s3_delete, del_client, del_api_session
    ):
        """Cognito delete_user is called with correct cognito_sub."""
        from app.core.security import get_current_user_payload
        from app.main import app

        client, mock_cognito = del_client

        cognito_sub = "del-cognito-sub"
        await _create_user(del_api_session, cognito_sub, "cognito@test.com")
        await del_api_session.commit()

        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)
        try:
            response = await client.delete("/api/v1/users/me")
            assert response.status_code == 204
            mock_cognito.delete_user.assert_called_once_with(cognito_sub)
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)
