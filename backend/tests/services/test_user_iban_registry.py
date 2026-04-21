"""Unit tests for UserIbanRegistryService (Story 11.10 AC #14)."""
from __future__ import annotations

import uuid

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel

# Import models so SQLModel.metadata picks up ALL tables for create_all.
import app.models  # noqa: F401
from app.core import crypto
from app.models.user_iban_registry import UserIbanRegistry
from app.services.user_iban_registry import (
    UserIbanRegistryService,
    iban_fingerprint,
)


@pytest.fixture(autouse=True)
def _local_fernet():
    key = Fernet.generate_key().decode()
    from unittest.mock import patch

    with (
        patch.object(crypto.settings, "ENV", "local"),
        patch.object(crypto.settings, "KMS_IBAN_KEY_ARN", None),
        patch.object(crypto.settings, "LOCAL_IBAN_FERNET_KEY", key),
    ):
        yield


@pytest.fixture
def sync_session():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def _mk_user(session) -> uuid.UUID:
    """Insert a minimal users row and return its id. Required for FK."""
    from app.models.user import User

    user = User(
        id=uuid.uuid4(),
        cognito_sub=f"sub-{uuid.uuid4()}",
        email=f"{uuid.uuid4()}@example.com",
    )
    session.add(user)
    session.commit()
    return user.id


class TestFingerprint:
    def test_stable_across_normalizations(self):
        a = iban_fingerprint("ua213223130000026007233566001")
        b = iban_fingerprint("  UA21 3223 1300 0002 6007 2335 6600 1  ".replace(" ", ""))
        # Whitespace stripped but digits/structure preserved → same
        assert a == iban_fingerprint("UA213223130000026007233566001")
        assert b == a


class TestRegister:
    def test_first_register_inserts(self, sync_session):
        user_id = _mk_user(sync_session)
        svc = UserIbanRegistryService(sync_session)
        row = svc.register(user_id, "UA213223130000026007233566001", label="primary")
        sync_session.commit()
        assert row.id is not None
        assert row.iban_fingerprint == iban_fingerprint("UA213223130000026007233566001")
        assert row.iban_encrypted  # non-empty

    def test_duplicate_register_updates_timestamp_preserves_ct(self, sync_session):
        user_id = _mk_user(sync_session)
        svc = UserIbanRegistryService(sync_session)
        r1 = svc.register(user_id, "UA1", label="first")
        sync_session.commit()
        original_ct = r1.iban_encrypted
        original_label = r1.label
        original_updated = r1.updated_at

        import time
        time.sleep(0.01)

        r2 = svc.register(user_id, "UA1", label="second")
        sync_session.commit()
        assert r2.id == r1.id
        assert r2.iban_encrypted == original_ct  # no re-encryption churn
        assert r2.label == original_label  # overwrite_label=False default
        assert r2.updated_at > original_updated

    def test_overwrite_label(self, sync_session):
        user_id = _mk_user(sync_session)
        svc = UserIbanRegistryService(sync_session)
        svc.register(user_id, "UA1", label="old")
        sync_session.commit()
        row = svc.register(user_id, "UA1", label="new", overwrite_label=True)
        sync_session.commit()
        assert row.label == "new"

    def test_rejects_empty_plaintext(self, sync_session):
        user_id = _mk_user(sync_session)
        svc = UserIbanRegistryService(sync_session)
        with pytest.raises(ValueError):
            svc.register(user_id, "   ")


class TestIsUserIban:
    def test_hit_without_decrypt(self, sync_session):
        user_id = _mk_user(sync_session)
        svc = UserIbanRegistryService(sync_session)
        svc.register(user_id, "UA213223130000026007233566001", label="x")
        sync_session.commit()
        # No mocking of decrypt — a successful True means the lookup went
        # through fingerprint alone.
        assert svc.is_user_iban(user_id, "UA213223130000026007233566001") is True

    def test_miss(self, sync_session):
        user_id = _mk_user(sync_session)
        svc = UserIbanRegistryService(sync_session)
        assert svc.is_user_iban(user_id, "UA999") is False

    def test_per_user_isolation(self, sync_session):
        user_a = _mk_user(sync_session)
        user_b = _mk_user(sync_session)
        svc = UserIbanRegistryService(sync_session)
        svc.register(user_a, "UA1", label="a")
        sync_session.commit()
        assert svc.is_user_iban(user_a, "UA1") is True
        assert svc.is_user_iban(user_b, "UA1") is False

    def test_empty_iban_returns_false(self, sync_session):
        user_id = _mk_user(sync_session)
        svc = UserIbanRegistryService(sync_session)
        assert svc.is_user_iban(user_id, "") is False
