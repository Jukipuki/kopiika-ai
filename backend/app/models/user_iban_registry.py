"""User IBAN registry — per-user known IBANs with envelope-encrypted plaintext.

Story 11.10 / TD-049. Stores the user's own account IBANs (discovered from
PrivatBank/Monobank statement headers) plus PE-statement self-transfer
counterparties (when counterparty_name matches the user's full name). The
fingerprint is SHA-256 of NFKC-normalized + uppercased IBAN, used for
equality lookups without ever decrypting the ciphertext.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import ForeignKey, Index, LargeBinary
from sqlmodel import Column, Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class UserIbanRegistry(SQLModel, table=True):
    __tablename__ = "user_iban_registry"
    __table_args__ = (
        Index(
            "ix_user_iban_registry_user_fingerprint",
            "user_id",
            "iban_fingerprint",
            unique=True,
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(
        sa_column=Column(
            ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        )
    )
    iban_encrypted: bytes = Field(sa_column=Column(LargeBinary, nullable=False))
    iban_fingerprint: str = Field(max_length=64)
    label: Optional[str] = Field(default=None, max_length=64)
    first_seen_upload_id: Optional[uuid.UUID] = Field(
        default=None,
        sa_column=Column(
            ForeignKey("uploads.id", ondelete="SET NULL"), nullable=True
        ),
    )
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
