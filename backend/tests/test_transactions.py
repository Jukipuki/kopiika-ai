"""Tests for transaction deduplication and API endpoints (Story 2.7)."""
import io
import os
import tempfile
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.models.processing_job import ProcessingJob
from app.models.transaction import Transaction
from app.models.upload import Upload
from app.models.user import User
from app.services.transaction_service import compute_dedup_hash


def _utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


# ==================== 8.1: Dedup Hash Tests ====================


class TestComputeDedupHash:
    """Test dedup hash computation: same inputs -> same hash, different inputs -> different hash."""

    def test_same_inputs_same_hash(self):
        user_id = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        h1 = compute_dedup_hash(user_id, "2026-02-15", -95000, "Сільпо")
        h2 = compute_dedup_hash(user_id, "2026-02-15", -95000, "Сільпо")
        assert h1 == h2

    def test_different_amount_different_hash(self):
        user_id = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        h1 = compute_dedup_hash(user_id, "2026-02-15", -95000, "Сільпо")
        h2 = compute_dedup_hash(user_id, "2026-02-15", -10000, "Сільпо")
        assert h1 != h2

    def test_different_user_different_hash(self):
        u1 = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        u2 = uuid.UUID("11111111-2222-3333-4444-555555555555")
        h1 = compute_dedup_hash(u1, "2026-02-15", -95000, "Сільпо")
        h2 = compute_dedup_hash(u2, "2026-02-15", -95000, "Сільпо")
        assert h1 != h2

    def test_different_date_different_hash(self):
        user_id = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        h1 = compute_dedup_hash(user_id, "2026-02-15", -95000, "Сільпо")
        h2 = compute_dedup_hash(user_id, "2026-02-16", -95000, "Сільпо")
        assert h1 != h2

    def test_different_description_different_hash(self):
        user_id = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        h1 = compute_dedup_hash(user_id, "2026-02-15", -95000, "Сільпо")
        h2 = compute_dedup_hash(user_id, "2026-02-15", -95000, "ATB")
        assert h1 != h2

    def test_description_normalized_case_insensitive(self):
        user_id = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        h1 = compute_dedup_hash(user_id, "2026-02-15", -95000, "Сільпо")
        h2 = compute_dedup_hash(user_id, "2026-02-15", -95000, "сільпо")
        assert h1 == h2

    def test_description_normalized_whitespace(self):
        user_id = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        h1 = compute_dedup_hash(user_id, "2026-02-15", -95000, "Сільпо")
        h2 = compute_dedup_hash(user_id, "2026-02-15", -95000, "  Сільпо  ")
        assert h1 == h2

    def test_hash_is_64_char_hex(self):
        user_id = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        h = compute_dedup_hash(user_id, "2026-02-15", -95000, "test")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_datetime_input(self):
        user_id = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        h1 = compute_dedup_hash(user_id, datetime(2026, 2, 15, 10, 30), -95000, "test")
        h2 = compute_dedup_hash(user_id, "2026-02-15", -95000, "test")
        assert h1 == h2


# ==================== Sync Engine Fixtures ====================


MONOBANK_CSV = (
    "Дата і час операції;Опис операції;MCC;Сума в валюті картки (UAH);Залишок на рахунку (UAH)\n"
    "01.01.2024 12:00:00;Grocery Store;5411;-100.50;5000.00\n"
    "02.01.2024 14:30:00;Coffee Shop;5814;-45.00;4955.00\n"
).encode("utf-8")

MONOBANK_CSV_OVERLAPPING = (
    "Дата і час операції;Опис операції;MCC;Сума в валюті картки (UAH);Залишок на рахунку (UAH)\n"
    "01.01.2024 12:00:00;Grocery Store;5411;-100.50;5000.00\n"
    "03.01.2024 10:00:00;New Txn;5411;-200.00;4800.00\n"
).encode("utf-8")

MONOBANK_CSV_ALL_NEW = (
    "Дата і час операції;Опис операції;MCC;Сума в валюті картки (UAH);Залишок на рахунку (UAH)\n"
    "05.01.2024 10:00:00;Restaurant;5812;-300.00;4500.00\n"
    "06.01.2024 12:00:00;Pharmacy;5912;-50.00;4450.00\n"
).encode("utf-8")


@pytest.fixture
def sync_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)
    engine.dispose()


def _mock_sync_session_cm(engine):
    @contextmanager
    def _cm():
        session = Session(engine)
        try:
            yield session
        finally:
            session.close()
    return _cm


def _seed_data(engine, user_email="txn@test.com", cognito_sub="txn-test-sub"):
    user_id = uuid.uuid4()
    upload_id = uuid.uuid4()
    job_id = uuid.uuid4()

    with Session(engine) as session:
        user = User(id=user_id, email=user_email, cognito_sub=cognito_sub, locale="en")
        session.add(user)
        session.flush()

        upload = Upload(
            id=upload_id, user_id=user_id, file_name="test.csv",
            s3_key=f"{user_id}/test_original.csv", file_size=1024,
            mime_type="text/csv", detected_format="monobank", detected_encoding="utf-8",
            detected_delimiter=";",
        )
        session.add(upload)
        session.flush()

        job = ProcessingJob(id=job_id, user_id=user_id, upload_id=upload_id, status="validated")
        session.add(job)
        session.commit()

    return user_id, upload_id, job_id


# ==================== 8.2-8.5: Dedup Integration Tests ====================


class TestSyncParseDeduplication:
    """Test sync_parse_and_store_transactions with deduplication."""

    @patch("app.tasks.processing_tasks.publish_job_progress")
    @patch("app.tasks.processing_tasks.boto3.client")
    @patch("app.tasks.processing_tasks.get_sync_session")
    def test_first_upload_inserts_all(self, mock_get_session, mock_boto_client, mock_publish, sync_engine):
        """8.4: First upload with completely new transactions — all inserted."""
        user_id, upload_id, job_id = _seed_data(sync_engine)
        mock_get_session.side_effect = _mock_sync_session_cm(sync_engine)
        mock_s3 = MagicMock()
        mock_s3.get_object.return_value = {"Body": io.BytesIO(MONOBANK_CSV)}
        mock_boto_client.return_value = mock_s3

        from app.tasks.processing_tasks import process_upload
        result = process_upload(str(job_id))

        assert result["parsed_count"] == 2
        assert result["duplicates_skipped"] == 0
        with Session(sync_engine) as s:
            txns = s.exec(select(Transaction).where(Transaction.user_id == user_id)).all()
            assert len(txns) == 2
            # Verify dedup_hash is populated
            assert all(txn.dedup_hash and len(txn.dedup_hash) == 64 for txn in txns)

    @patch("app.tasks.processing_tasks.publish_job_progress")
    @patch("app.tasks.processing_tasks.boto3.client")
    @patch("app.tasks.processing_tasks.get_sync_session")
    def test_overlapping_upload_deduplicates(self, mock_get_session, mock_boto_client, mock_publish, sync_engine):
        """8.3: Second upload with overlapping transactions — only new ones inserted."""
        user_id, upload_id, job_id = _seed_data(sync_engine)
        mock_get_session.side_effect = _mock_sync_session_cm(sync_engine)
        mock_s3 = MagicMock()
        mock_s3.get_object.return_value = {"Body": io.BytesIO(MONOBANK_CSV)}
        mock_boto_client.return_value = mock_s3

        from app.tasks.processing_tasks import process_upload
        # First upload
        process_upload(str(job_id))

        # Second upload with overlapping data
        upload_id2 = uuid.uuid4()
        job_id2 = uuid.uuid4()
        with Session(sync_engine) as s:
            upload2 = Upload(
                id=upload_id2, user_id=user_id, file_name="test2.csv",
                s3_key=f"{user_id}/test2_original.csv", file_size=1024,
                mime_type="text/csv", detected_format="monobank", detected_encoding="utf-8",
                detected_delimiter=";",
            )
            s.add(upload2)
            s.flush()
            job2 = ProcessingJob(id=job_id2, user_id=user_id, upload_id=upload_id2, status="validated")
            s.add(job2)
            s.commit()

        mock_s3.get_object.return_value = {"Body": io.BytesIO(MONOBANK_CSV_OVERLAPPING)}
        result2 = process_upload(str(job_id2))

        # 1 new txn, 1 duplicate
        assert result2["duplicates_skipped"] == 1

        with Session(sync_engine) as s:
            txns = s.exec(select(Transaction).where(Transaction.user_id == user_id)).all()
            assert len(txns) == 3  # 2 from first + 1 new from second

    @patch("app.tasks.processing_tasks.publish_job_progress")
    @patch("app.tasks.processing_tasks.boto3.client")
    @patch("app.tasks.processing_tasks.get_sync_session")
    def test_exact_same_file_all_skipped(self, mock_get_session, mock_boto_client, mock_publish, sync_engine):
        """8.5: Exact same file uploaded twice — zero new transactions, job still 'completed'."""
        user_id, upload_id, job_id = _seed_data(sync_engine)
        mock_get_session.side_effect = _mock_sync_session_cm(sync_engine)
        mock_s3 = MagicMock()
        mock_s3.get_object.return_value = {"Body": io.BytesIO(MONOBANK_CSV)}
        mock_boto_client.return_value = mock_s3

        from app.tasks.processing_tasks import process_upload
        # First upload
        process_upload(str(job_id))

        # Same file again
        upload_id2 = uuid.uuid4()
        job_id2 = uuid.uuid4()
        with Session(sync_engine) as s:
            upload2 = Upload(
                id=upload_id2, user_id=user_id, file_name="test.csv",
                s3_key=f"{user_id}/test2_original.csv", file_size=1024,
                mime_type="text/csv", detected_format="monobank", detected_encoding="utf-8",
                detected_delimiter=";",
            )
            s.add(upload2)
            s.flush()
            job2 = ProcessingJob(id=job_id2, user_id=user_id, upload_id=upload_id2, status="validated")
            s.add(job2)
            s.commit()

        mock_s3.get_object.return_value = {"Body": io.BytesIO(MONOBANK_CSV)}
        result2 = process_upload(str(job_id2))

        # All duplicates
        assert result2["duplicates_skipped"] == 2
        assert result2["parsed_count"] == 2

        # Job should still be "completed", not error
        with Session(sync_engine) as s:
            job = s.get(ProcessingJob, job_id2)
            assert job.status == "completed"

        # Total txns unchanged
        with Session(sync_engine) as s:
            txns = s.exec(select(Transaction).where(Transaction.user_id == user_id)).all()
            assert len(txns) == 2

    @patch("app.tasks.processing_tasks.publish_job_progress")
    @patch("app.tasks.processing_tasks.boto3.client")
    @patch("app.tasks.processing_tasks.get_sync_session")
    def test_all_new_transactions_second_upload(self, mock_get_session, mock_boto_client, mock_publish, sync_engine):
        """8.4: Second upload with completely new transactions — all inserted."""
        user_id, upload_id, job_id = _seed_data(sync_engine)
        mock_get_session.side_effect = _mock_sync_session_cm(sync_engine)
        mock_s3 = MagicMock()
        mock_s3.get_object.return_value = {"Body": io.BytesIO(MONOBANK_CSV)}
        mock_boto_client.return_value = mock_s3

        from app.tasks.processing_tasks import process_upload
        process_upload(str(job_id))

        # Second upload with all-new data
        upload_id2 = uuid.uuid4()
        job_id2 = uuid.uuid4()
        with Session(sync_engine) as s:
            upload2 = Upload(
                id=upload_id2, user_id=user_id, file_name="test3.csv",
                s3_key=f"{user_id}/test3_original.csv", file_size=1024,
                mime_type="text/csv", detected_format="monobank", detected_encoding="utf-8",
                detected_delimiter=";",
            )
            s.add(upload2)
            s.flush()
            job2 = ProcessingJob(id=job_id2, user_id=user_id, upload_id=upload_id2, status="validated")
            s.add(job2)
            s.commit()

        mock_s3.get_object.return_value = {"Body": io.BytesIO(MONOBANK_CSV_ALL_NEW)}
        result2 = process_upload(str(job_id2))

        assert result2["duplicates_skipped"] == 0
        assert result2["parsed_count"] == 2

        with Session(sync_engine) as s:
            txns = s.exec(select(Transaction).where(Transaction.user_id == user_id)).all()
            assert len(txns) == 4  # 2 from first + 2 from second


# ==================== 8.6-8.9: API Endpoint Tests ====================


# Fixtures for async API tests — use a temp file per run to avoid cross-run collisions


@pytest_asyncio.fixture
async def txn_async_engine():
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
async def txn_async_session(txn_async_engine) -> SQLModelAsyncSession:
    async with SQLModelAsyncSession(txn_async_engine) as session:
        yield session


def _auth_override(cognito_sub: str):
    async def mock_payload():
        return {"sub": cognito_sub}
    return mock_payload


async def _create_user_and_data(session: SQLModelAsyncSession, cognito_sub: str, email: str):
    """Create a user, upload, and transactions for testing."""
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

    job = ProcessingJob(
        user_id=user_id, upload_id=upload_id, status="completed",
        result_data={"total_rows": 3, "parsed_count": 3, "flagged_count": 0, "persisted_count": 3, "duplicates_skipped": 0},
    )
    session.add(job)

    # Add transactions
    for i in range(3):
        txn = Transaction(
            user_id=user_id, upload_id=upload_id,
            date=datetime(2026, 1, i + 1),
            description=f"Transaction {i}",
            amount=-(i + 1) * 10000,
            currency_code=980,
            dedup_hash=compute_dedup_hash(user_id, datetime(2026, 1, i + 1), -(i + 1) * 10000, f"Transaction {i}"),
        )
        session.add(txn)

    await session.commit()
    return user_id, upload_id


@pytest_asyncio.fixture
async def txn_client(txn_async_engine):
    from app.api.deps import get_db, get_cognito_service, get_rate_limiter
    from app.main import app
    from unittest.mock import AsyncMock

    async def override_get_db():
        async with SQLModelAsyncSession(txn_async_engine) as session:
            yield session

    mock_cognito = MagicMock()
    mock_cognito.sign_up.return_value = {"user_sub": "txn-test-sub", "user_confirmed": False}
    mock_cognito.confirm_sign_up.return_value = {"confirmed": True}
    mock_cognito.authenticate_user.return_value = {
        "access_token": "fake-token",
        "refresh_token": "fake-refresh",
        "expires_in": 900,
    }

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


class TestTransactionsEndpoint:
    """8.6-8.7: Test GET /api/v1/transactions."""

    @pytest.mark.asyncio
    async def test_list_transactions_returns_cumulative_data(self, txn_client, txn_async_session):
        """8.6: Returns cumulative transactions from all uploads, paginated."""
        from app.core.security import get_current_user_payload
        from app.main import app

        cognito_sub = "txn-list-sub"
        user_id, _ = await _create_user_and_data(txn_async_session, cognito_sub, "txn-list@test.com")
        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)

        try:
            response = await txn_client.get("/api/v1/transactions")
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 3
            assert len(data["items"]) == 3
            assert "hasMore" in data

            # Check camelCase
            item = data["items"][0]
            assert "uploadId" in item
            assert "currencyCode" in item
            assert "createdAt" in item
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_list_transactions_pagination(self, txn_client, txn_async_session):
        """8.6: Pagination works correctly."""
        from app.core.security import get_current_user_payload
        from app.main import app

        cognito_sub = "txn-page-sub"
        user_id, _ = await _create_user_and_data(txn_async_session, cognito_sub, "txn-page@test.com")
        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)

        try:
            response = await txn_client.get("/api/v1/transactions?pageSize=2")
            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) == 2
            assert data["hasMore"] is True
            assert data["nextCursor"] is not None

            # Load next page
            response2 = await txn_client.get(f"/api/v1/transactions?pageSize=2&cursor={data['nextCursor']}")
            data2 = response2.json()
            assert len(data2["items"]) == 1
            assert data2["hasMore"] is False
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_transactions_tenant_isolation(self, txn_client, txn_async_session):
        """8.7: User A cannot see user B's transactions."""
        from app.core.security import get_current_user_payload
        from app.main import app

        # Create user A with data
        await _create_user_and_data(txn_async_session, "user-a-sub", "usera@test.com")
        # Create user B with data
        await _create_user_and_data(txn_async_session, "user-b-sub", "userb@test.com")

        # Query as user A
        app.dependency_overrides[get_current_user_payload] = _auth_override("user-a-sub")
        try:
            response = await txn_client.get("/api/v1/transactions")
            data = response.json()
            assert data["total"] == 3  # Only user A's transactions
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

        # Query as user B
        app.dependency_overrides[get_current_user_payload] = _auth_override("user-b-sub")
        try:
            response = await txn_client.get("/api/v1/transactions")
            data = response.json()
            assert data["total"] == 3  # Only user B's transactions
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_transactions_unauthenticated(self, txn_client):
        """Unauthenticated access returns 401/403."""
        response = await txn_client.get("/api/v1/transactions")
        assert response.status_code in (401, 403)


class TestUploadsListEndpoint:
    """8.8-8.9: Test GET /api/v1/uploads."""

    @pytest.mark.asyncio
    async def test_list_uploads_returns_upload_history(self, txn_client, txn_async_session):
        """8.8: Returns all uploads with transaction counts."""
        from app.core.security import get_current_user_payload
        from app.main import app

        cognito_sub = "upload-list-sub"
        user_id, _ = await _create_user_and_data(txn_async_session, cognito_sub, "upload-list@test.com")
        app.dependency_overrides[get_current_user_payload] = _auth_override(cognito_sub)

        try:
            response = await txn_client.get("/api/v1/uploads")
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1
            assert len(data["items"]) == 1

            item = data["items"][0]
            assert item["fileName"] == "test.csv"
            assert item["detectedFormat"] == "monobank"
            assert item["transactionCount"] == 3
            assert item["duplicatesSkipped"] == 0
            assert item["status"] == "completed"
            assert "createdAt" in item
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_uploads_tenant_isolation(self, txn_client, txn_async_session):
        """8.9: Upload tenant isolation — user A cannot see user B's uploads."""
        from app.core.security import get_current_user_payload
        from app.main import app

        await _create_user_and_data(txn_async_session, "upload-a-sub", "upload-a@test.com")
        await _create_user_and_data(txn_async_session, "upload-b-sub", "upload-b@test.com")

        # Query as user A
        app.dependency_overrides[get_current_user_payload] = _auth_override("upload-a-sub")
        try:
            response = await txn_client.get("/api/v1/uploads")
            data = response.json()
            assert data["total"] == 1  # Only user A's upload
        finally:
            app.dependency_overrides.pop(get_current_user_payload, None)

    @pytest.mark.asyncio
    async def test_uploads_unauthenticated(self, txn_client):
        """Unauthenticated access returns 401/403."""
        response = await txn_client.get("/api/v1/uploads")
        assert response.status_code in (401, 403)
