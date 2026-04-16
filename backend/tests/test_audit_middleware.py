"""Tests for AuditMiddleware and audit anonymization (Story 5.6)."""
import hashlib
import os
import tempfile
import uuid
from unittest.mock import patch

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.responses import Response
from httpx import ASGITransport, AsyncClient
from jose import jwt as jose_jwt
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.core.audit import AuditMiddleware, anonymize_user_audit_records
from app.models.audit_log import AuditLog


def _make_jwt(sub: str) -> str:
    """Create a minimal signed JWT — middleware uses get_unverified_claims, no JWKS needed."""
    return jose_jwt.encode({"sub": sub}, "test-secret", algorithm="HS256")


# ==================== Fixtures ====================


@pytest_asyncio.fixture
async def audit_engine():
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
async def audit_session(audit_engine) -> SQLModelAsyncSession:
    async with SQLModelAsyncSession(audit_engine) as session:
        yield session


@pytest_asyncio.fixture
async def audit_client(audit_engine):
    """Minimal stub FastAPI app with financial route stubs + AuditMiddleware patched to test DB."""
    stub_app = FastAPI()

    @stub_app.get("/api/v1/transactions")
    async def get_transactions():
        return []

    @stub_app.post("/api/v1/uploads")
    async def post_uploads():
        return {"id": str(uuid.uuid4())}

    @stub_app.delete("/api/v1/users/me")
    async def delete_user():
        return Response(status_code=204)

    @stub_app.get("/api/v1/health")
    async def health():
        return {"status": "ok"}

    @stub_app.get("/api/v1/insights")
    async def get_insights():
        return []

    @stub_app.get("/api/v1/profile")
    async def get_profile():
        return {}

    stub_app.add_middleware(AuditMiddleware)

    with patch("app.core.audit.engine", audit_engine):
        transport = ASGITransport(app=stub_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac, audit_engine


# ==================== Tests ====================


class TestAuditMiddlewareRecording:
    """Test 5.2–5.6: AuditMiddleware correctly records financial data access events."""

    @pytest.mark.asyncio
    async def test_get_transactions_creates_read_record(self, audit_client):
        """5.2: GET /api/v1/transactions → audit entry with action_type='read', resource_type='transactions'."""
        client, engine = audit_client
        cognito_sub = "test-sub-read-tx"
        token = _make_jwt(cognito_sub)

        response = await client.get(
            "/api/v1/transactions",
            headers={"Authorization": f"Bearer {token}", "User-Agent": "TestUA/1.0"},
        )
        assert response.status_code == 200

        async with SQLModelAsyncSession(engine) as session:
            logs = (await session.exec(select(AuditLog))).all()
            assert len(logs) == 1
            log = logs[0]
            assert log.action_type == "read"
            assert log.resource_type == "transactions"
            assert log.user_id == cognito_sub
            assert log.ip_address is not None
            assert log.user_agent == "TestUA/1.0"

    @pytest.mark.asyncio
    async def test_post_uploads_creates_write_record(self, audit_client):
        """5.3: POST /api/v1/uploads → audit entry with action_type='write', resource_type='uploads'."""
        client, engine = audit_client
        cognito_sub = "test-sub-upload"
        token = _make_jwt(cognito_sub)

        response = await client.post(
            "/api/v1/uploads",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

        async with SQLModelAsyncSession(engine) as session:
            logs = (await session.exec(select(AuditLog))).all()
            assert len(logs) == 1
            log = logs[0]
            assert log.action_type == "write"
            assert log.resource_type == "uploads"
            assert log.user_id == cognito_sub

    @pytest.mark.asyncio
    async def test_delete_user_creates_delete_record(self, audit_client):
        """5.4: DELETE /api/v1/users/me → audit entry with action_type='delete', resource_type='user'."""
        client, engine = audit_client
        cognito_sub = "test-sub-delete"
        token = _make_jwt(cognito_sub)

        response = await client.delete(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 204

        async with SQLModelAsyncSession(engine) as session:
            logs = (await session.exec(select(AuditLog))).all()
            assert len(logs) == 1
            log = logs[0]
            assert log.action_type == "delete"
            assert log.resource_type == "user"
            assert log.user_id == cognito_sub

    @pytest.mark.asyncio
    async def test_non_financial_path_no_audit_record(self, audit_client):
        """5.5: GET /api/v1/health (non-financial) → no audit_logs entry created."""
        client, engine = audit_client
        token = _make_jwt("test-sub-health")

        response = await client.get(
            "/api/v1/health",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

        async with SQLModelAsyncSession(engine) as session:
            logs = (await session.exec(select(AuditLog))).all()
            assert len(logs) == 0

    @pytest.mark.asyncio
    async def test_no_bearer_token_no_audit_record(self, audit_client):
        """5.6: Request without Authorization Bearer header → no audit_logs entry created."""
        client, engine = audit_client

        # No Authorization header — middleware skips logging
        response = await client.get("/api/v1/transactions")
        # Response code doesn't matter for this assertion

        async with SQLModelAsyncSession(engine) as session:
            logs = (await session.exec(select(AuditLog))).all()
            assert len(logs) == 0


class TestAnonymizeAuditRecords:
    """Test 5.7–5.9: audit record anonymization on account deletion."""

    @pytest.mark.asyncio
    async def test_anonymize_replaces_user_id_with_sha256_hash(
        self, audit_session, audit_engine
    ):
        """5.7: Pre-insert 2 audit records, call anonymize, verify both have sha256(cognito_sub) as user_id."""
        cognito_sub = "to-be-anonymized-sub"
        expected_hash = hashlib.sha256(cognito_sub.encode()).hexdigest()

        audit_session.add(
            AuditLog(user_id=cognito_sub, action_type="read", resource_type="transactions")
        )
        audit_session.add(
            AuditLog(user_id=cognito_sub, action_type="read", resource_type="insights")
        )
        await audit_session.commit()

        async with SQLModelAsyncSession(audit_engine) as anon_session:
            await anonymize_user_audit_records(anon_session, cognito_sub)
            await anon_session.commit()

        async with SQLModelAsyncSession(audit_engine) as verify_session:
            logs = (await verify_session.exec(select(AuditLog))).all()
            assert len(logs) == 2
            for log in logs:
                assert log.user_id == expected_hash
                assert log.user_id != cognito_sub

    @pytest.mark.asyncio
    async def test_audit_records_survive_deletion_with_hashed_user_id(
        self, audit_session, audit_engine
    ):
        """5.8: After anonymize (simulating account deletion), audit records survive with hashed user_id."""
        cognito_sub = "deletion-test-sub"
        expected_hash = hashlib.sha256(cognito_sub.encode()).hexdigest()

        audit_session.add(
            AuditLog(user_id=cognito_sub, action_type="read", resource_type="profile")
        )
        await audit_session.commit()

        async with SQLModelAsyncSession(audit_engine) as del_session:
            await anonymize_user_audit_records(del_session, cognito_sub)
            await del_session.commit()

        async with SQLModelAsyncSession(audit_engine) as verify_session:
            logs = (await verify_session.exec(select(AuditLog))).all()
            assert len(logs) == 1
            assert logs[0].user_id == expected_hash

    @pytest.mark.asyncio
    async def test_anonymize_does_not_affect_other_users(
        self, audit_session, audit_engine
    ):
        """5.9: Anonymizing user A's audit records does not affect user B's records."""
        sub_a = "user-a-sub"
        sub_b = "user-b-sub"
        hash_a = hashlib.sha256(sub_a.encode()).hexdigest()

        audit_session.add(
            AuditLog(user_id=sub_a, action_type="read", resource_type="transactions")
        )
        audit_session.add(
            AuditLog(user_id=sub_b, action_type="read", resource_type="insights")
        )
        await audit_session.commit()

        async with SQLModelAsyncSession(audit_engine) as anon_session:
            await anonymize_user_audit_records(anon_session, sub_a)
            await anon_session.commit()

        async with SQLModelAsyncSession(audit_engine) as verify_session:
            logs = (await verify_session.exec(select(AuditLog))).all()
            assert len(logs) == 2
            user_ids = {log.user_id for log in logs}
            assert hash_a in user_ids
            assert sub_b in user_ids  # User B unaffected
            assert sub_a not in user_ids  # User A anonymized
