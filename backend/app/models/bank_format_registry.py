"""Bank format registry — cached AI-detected column mappings keyed by header fingerprint.

Story 11.7 / ADR-0002. Each row caches the column mapping detected (by either
the LLM or an operator override) for a distinct statement header shape. The
fingerprint is the SHA-256 of the canonical header form (see
`schema_detection.header_fingerprint`); hitting the cache avoids a per-upload
LLM call.
"""
import uuid
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel

# JSONB on Postgres (where production runs), plain JSON on SQLite (tests).
# `with_variant` keeps the Postgres-specific JSONB columns intact in the real
# schema while letting SQLModel.metadata.create_all emit a working JSON column
# for the in-memory test DB.
_JSON_TYPE = JSON().with_variant(JSONB(), "postgresql")


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class BankFormatRegistry(SQLModel, table=True):
    __tablename__ = "bank_format_registry"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    header_fingerprint: str = Field(max_length=64, unique=True, index=True)
    detected_mapping: dict = Field(sa_column=Column(_JSON_TYPE, nullable=False))
    override_mapping: Optional[dict] = Field(
        default=None, sa_column=Column(_JSON_TYPE, nullable=True)
    )
    detection_confidence: Optional[float] = Field(default=None)
    detected_bank_hint: Optional[str] = Field(default=None, max_length=255)
    sample_header: str
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
    last_used_at: datetime = Field(default_factory=_utcnow)
    use_count: int = Field(default=1)
