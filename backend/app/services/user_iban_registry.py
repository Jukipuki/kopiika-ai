"""User IBAN registry service (Story 11.10 / TD-049).

Idempotent `register(...)` and decrypt-free `is_user_iban(...)` over the
`user_iban_registry` table. Fingerprint stability mirrors Story 11.7's
`header_fingerprint` pattern — NFKC-normalize + strip + uppercase + SHA-256.
"""
from __future__ import annotations

import hashlib
import logging
import unicodedata
import uuid
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import select

from app.core.crypto import encrypt_iban
from app.models.user_iban_registry import UserIbanRegistry

logger = logging.getLogger(__name__)


def iban_fingerprint(iban: str) -> str:
    """SHA-256 hex of the canonical IBAN form. Use for equality lookups."""
    canonical = unicodedata.normalize("NFKC", iban).strip().upper()
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class UserIbanRegistryService:
    """Session-scoped service — instantiate per DB session (sync or async)."""

    def __init__(self, session):
        self.session = session

    # -- sync API (used by Celery / parser_service) --------------------------

    def register(
        self,
        user_id: uuid.UUID,
        iban_plaintext: str,
        label: Optional[str] = None,
        first_seen_upload_id: Optional[uuid.UUID] = None,
        overwrite_label: bool = False,
    ) -> UserIbanRegistry:
        if not iban_plaintext or not iban_plaintext.strip():
            raise ValueError("iban_plaintext required")

        fp = iban_fingerprint(iban_plaintext)
        existing = self.session.execute(
            select(UserIbanRegistry).where(
                UserIbanRegistry.user_id == user_id,
                UserIbanRegistry.iban_fingerprint == fp,
            )
        ).scalars().first()

        if existing is not None:
            existing.updated_at = _utcnow()
            if overwrite_label and label is not None:
                existing.label = label
            self.session.add(existing)
            return existing

        row = UserIbanRegistry(
            user_id=user_id,
            iban_encrypted=encrypt_iban(iban_plaintext),
            iban_fingerprint=fp,
            label=label,
            first_seen_upload_id=first_seen_upload_id,
        )
        self.session.add(row)
        return row

    def is_user_iban(self, user_id: uuid.UUID, iban_plaintext: str) -> bool:
        if not iban_plaintext:
            return False
        fp = iban_fingerprint(iban_plaintext)
        result = self.session.execute(
            select(UserIbanRegistry.id).where(
                UserIbanRegistry.user_id == user_id,
                UserIbanRegistry.iban_fingerprint == fp,
            )
        ).first()
        return result is not None

    def list_for_user(self, user_id: uuid.UUID) -> list[UserIbanRegistry]:
        """Operator / admin path. Not used by the categorization hot path."""
        return (
            self.session.execute(
                select(UserIbanRegistry).where(
                    UserIbanRegistry.user_id == user_id
                )
            )
            .scalars()
            .all()
        )
