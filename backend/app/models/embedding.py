import uuid
from datetime import UTC, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, UniqueConstraint
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class DocumentEmbedding(SQLModel, table=True):
    __tablename__ = "document_embeddings"
    __table_args__ = (
        UniqueConstraint("doc_id", "chunk_type", name="uq_doc_id_chunk_type"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    doc_id: str = Field(index=True)  # e.g. "en/budgeting-basics"
    language: str = Field(index=True)  # "en" or "uk"
    chunk_type: str  # e.g. "overview", "key_concepts"
    content: str
    embedding: list[float] = Field(sa_column=Column(Vector(1536)))
    created_at: datetime = Field(default_factory=_utcnow)
