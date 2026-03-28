"""Tests for tenant isolation, resource ownership, and Alembic migration (Story 1.5)."""
import os
import uuid
from unittest.mock import patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import Field, SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.core.exceptions import ForbiddenError
from app.core.security import get_current_user_payload
from app.core.tenant import user_scoped_query, verify_resource_ownership
from app.main import app


# --------------- Test model with user_id for scoping tests ---------------

class FakeResource(SQLModel, table=True):
    __tablename__ = "fake_resources"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(index=True)
    name: str = Field(default="")


@pytest_asyncio.fixture
async def tenant_engine():
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(
            SQLModel.metadata.create_all,
            tables=[FakeResource.__table__],
        )
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def tenant_session(tenant_engine):
    async with SQLModelAsyncSession(tenant_engine) as session:
        yield session


# ==================== 6.1 Unauthenticated GET /me returns 401 ====================


@pytest.mark.asyncio
async def test_unauthenticated_get_me_returns_401(client):
    """6.1 Test unauthenticated GET /api/v1/auth/me returns 401."""
    response = await client.get("/api/v1/auth/me")
    assert response.status_code in (401, 403)


# ==================== 6.2 Unauthenticated POST to protected endpoints ====================


@pytest.mark.asyncio
async def test_unauthenticated_post_logout_returns_401(client):
    """6.2 Test unauthenticated POST to /logout returns 401."""
    response = await client.post("/api/v1/auth/logout")
    assert response.status_code in (401, 403)


# ==================== 6.3 user_scoped_query filters by user_id ====================


@pytest.mark.asyncio
async def test_user_scoped_query_filters_by_user_id(tenant_session):
    """6.3 Test user_scoped_query() correctly filters results by user_id."""
    user_a_id = uuid.uuid4()
    user_b_id = uuid.uuid4()

    # Create resources for two different users
    resource_a1 = FakeResource(user_id=user_a_id, name="a1")
    resource_a2 = FakeResource(user_id=user_a_id, name="a2")
    resource_b1 = FakeResource(user_id=user_b_id, name="b1")

    tenant_session.add(resource_a1)
    tenant_session.add(resource_a2)
    tenant_session.add(resource_b1)
    await tenant_session.commit()

    # Query scoped to user A — should only see a1, a2
    stmt = user_scoped_query(select(FakeResource), user_a_id)
    result = await tenant_session.exec(stmt)
    resources = result.all()

    assert len(resources) == 2
    names = {r.name for r in resources}
    assert names == {"a1", "a2"}

    # Query scoped to user B — should only see b1
    stmt_b = user_scoped_query(select(FakeResource), user_b_id)
    result_b = await tenant_session.exec(stmt_b)
    resources_b = result_b.all()

    assert len(resources_b) == 1
    assert resources_b[0].name == "b1"


@pytest.mark.asyncio
async def test_user_scoped_query_with_explicit_model(tenant_session):
    """6.3b Test user_scoped_query() with explicit model parameter."""
    user_id = uuid.uuid4()
    other_id = uuid.uuid4()

    tenant_session.add(FakeResource(user_id=user_id, name="mine"))
    tenant_session.add(FakeResource(user_id=other_id, name="theirs"))
    await tenant_session.commit()

    stmt = user_scoped_query(select(FakeResource), user_id, model=FakeResource)
    result = await tenant_session.exec(stmt)
    resources = result.all()

    assert len(resources) == 1
    assert resources[0].name == "mine"


# ==================== 6.4 verify_resource_ownership returns 403 ====================


def test_verify_resource_ownership_raises_403_for_non_owner():
    """6.4 Test verify_resource_ownership() raises ForbiddenError for non-owned resource."""
    owner_id = uuid.uuid4()
    intruder_id = uuid.uuid4()

    resource = FakeResource(user_id=owner_id, name="secret")

    with pytest.raises(ForbiddenError) as exc_info:
        verify_resource_ownership(resource, intruder_id)

    assert exc_info.value.code == "ACCESS_DENIED"
    assert exc_info.value.status_code == 403


# ==================== 6.5 verify_resource_ownership passes for owner ====================


def test_verify_resource_ownership_passes_for_owner():
    """6.5 Test verify_resource_ownership() passes for owned resource."""
    owner_id = uuid.uuid4()
    resource = FakeResource(user_id=owner_id, name="my-resource")

    # Should not raise
    verify_resource_ownership(resource, owner_id)


# ==================== 6.6 403 response format ====================


@pytest.mark.asyncio
async def test_forbidden_error_response_format(client):
    """6.6 Test 403 response includes correct error format."""
    from app.core.exceptions import ForbiddenError as FErr

    # Temporarily override an endpoint to raise ForbiddenError
    async def mock_payload():
        return {"sub": "test-cognito-sub-123"}

    app.dependency_overrides[get_current_user_payload] = mock_payload

    # Create user first (via login from conftest fixtures)
    await client.post(
        "/api/v1/auth/login",
        json={"email": "forbidden-test@example.com", "password": "StrongPass1!"},
    )

    # Now override get_current_user to raise ForbiddenError
    from app.api.deps import get_current_user

    async def raise_forbidden():
        raise FErr()

    app.dependency_overrides[get_current_user] = raise_forbidden

    try:
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 403
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "ACCESS_DENIED"
        assert "message" in data["error"]
    finally:
        app.dependency_overrides.pop(get_current_user_payload, None)
        app.dependency_overrides.pop(get_current_user, None)


# ==================== 6.7 Structured logging for access violations ====================


def test_access_denied_is_logged_with_structured_fields():
    """6.7 Test unauthorized access attempt is logged with structured fields."""
    owner_id = uuid.uuid4()
    intruder_id = uuid.uuid4()
    resource = FakeResource(id=uuid.uuid4(), user_id=owner_id, name="secret-data")

    with patch("app.core.tenant.logger") as mock_logger:
        with pytest.raises(ForbiddenError):
            verify_resource_ownership(
                resource, intruder_id, resource_type="FakeResource", ip="192.168.1.1"
            )

        mock_logger.warning.assert_called_once()
        call_kwargs = mock_logger.warning.call_args
        extra = call_kwargs.kwargs.get("extra") or call_kwargs[1].get("extra")

        assert extra["action"] == "access_denied"
        assert extra["user_id"] == str(intruder_id)
        assert extra["resource_type"] == "FakeResource"
        assert extra["resource_id"] == str(resource.id)
        assert extra["ip"] == "192.168.1.1"


# ==================== 6.8 Alembic migration verification ====================


def test_alembic_migration_file_exists_and_correct():
    """6.8 Test Alembic migration creates users table with correct schema."""
    import importlib.util
    import os

    migration_dir = os.path.join(
        os.path.dirname(__file__), "..", "alembic", "versions"
    )

    # Find the migration file
    migration_files = [
        f
        for f in os.listdir(migration_dir)
        if f.endswith(".py") and not f.startswith("__")
    ]
    assert len(migration_files) >= 1, "No migration files found"

    # Find the initial migration (down_revision is None) regardless of alphabetical order
    initial_migration_path = None
    for mf in migration_files:
        mp = os.path.join(migration_dir, mf)
        s = importlib.util.spec_from_file_location("migration_scan", mp)
        m = importlib.util.module_from_spec(s)
        s.loader.exec_module(m)
        if getattr(m, "down_revision", "MISSING") is None:
            initial_migration_path = mp
            break
    assert initial_migration_path is not None, "No initial migration (down_revision=None) found"

    # Load and verify the initial migration module
    migration_path = initial_migration_path
    spec = importlib.util.spec_from_file_location("migration", migration_path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    assert migration.down_revision is None, "First migration should have no parent"
    assert callable(getattr(migration, "upgrade", None)), "Migration must have upgrade()"
    assert callable(getattr(migration, "downgrade", None)), "Migration must have downgrade()"

    # Verify schema elements in source (actual execution requires PostgreSQL
    # due to gen_random_uuid() server default)
    with open(migration_path) as f:
        source = f.read()

    assert "'users'" in source, "Migration should create 'users' table"
    assert "sa.Uuid()" in source, "id column should be UUID type"
    assert "gen_random_uuid()" in source, "id should have gen_random_uuid() default"
    assert "timezone=True" in source, "timestamps should use timezone=True (timestamptz)"
    assert "uq_users_email" in source, "Should have uq_users_email constraint"
    assert "uq_users_cognito_sub" in source, "Should have uq_users_cognito_sub constraint"
    assert "ix_users_email" in source, "Should have email index"
    assert "ix_users_cognito_sub" in source, "Should have cognito_sub index"


def test_alembic_config_loads_correctly():
    """6.8c Verify Alembic configuration is valid and can resolve the migration chain."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    alembic_cfg = Config(
        os.path.join(os.path.dirname(__file__), "..", "alembic.ini")
    )
    script_dir = ScriptDirectory.from_config(alembic_cfg)

    # Walk the full revision chain — verifies no broken links
    revisions = list(script_dir.walk_revisions())
    assert len(revisions) >= 1, "Should have at least one migration revision"

    # Verify head is reachable
    heads = script_dir.get_heads()
    assert len(heads) == 1, "Should have exactly one head revision"


@pytest.mark.asyncio
async def test_users_table_schema_via_metadata(async_engine):
    """6.8b Verify users table schema matches AC#4 requirements via SQLModel metadata."""
    from sqlalchemy import inspect

    async with async_engine.connect() as conn:
        columns = await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).get_columns("users")
        )

    col_names = {c["name"] for c in columns}
    expected_cols = {"id", "cognito_sub", "email", "is_verified", "locale", "created_at", "updated_at"}
    assert expected_cols.issubset(col_names), f"Missing columns: {expected_cols - col_names}"


# ==================== 6.9 Regression check ====================


@pytest.mark.asyncio
async def test_existing_signup_still_works(client, mock_cognito_service):
    """6.9 Regression: signup endpoint still works."""
    response = await client.post(
        "/api/v1/auth/signup",
        json={"email": "regression@example.com", "password": "StrongPass1!"},
    )
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_existing_login_still_works(client, mock_cognito_service, mock_rate_limiter):
    """6.9 Regression: login endpoint still works."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "regression-login@example.com", "password": "StrongPass1!"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_endpoint_still_works(client):
    """6.9 Regression: health endpoint still works."""
    response = await client.get("/health")
    assert response.status_code == 200
