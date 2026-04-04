"""create_document_embeddings_table

Revision ID: g3h4i5j6k7l8
Revises: f2a4b6c8d0e1
Create Date: 2026-04-04 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "g3h4i5j6k7l8"
down_revision: Union[str, Sequence[str], None] = "f2a4b6c8d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Enable pgvector extension and create document_embeddings table."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.execute("""
        CREATE TABLE document_embeddings (
            id UUID PRIMARY KEY,
            doc_id VARCHAR NOT NULL,
            language VARCHAR NOT NULL,
            chunk_type VARCHAR NOT NULL,
            content TEXT NOT NULL,
            embedding vector(1536) NOT NULL,
            created_at TIMESTAMP NOT NULL,
            CONSTRAINT uq_doc_id_chunk_type UNIQUE (doc_id, chunk_type)
        )
    """)
    op.execute("CREATE INDEX ix_document_embeddings_doc_id ON document_embeddings (doc_id)")
    op.execute("CREATE INDEX ix_document_embeddings_language ON document_embeddings (language)")

    # HNSW index for fast approximate nearest-neighbor cosine similarity search
    op.execute(
        "CREATE INDEX ix_document_embeddings_hnsw ON document_embeddings "
        "USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)"
    )


def downgrade() -> None:
    """Drop document_embeddings table."""
    op.drop_table("document_embeddings")
