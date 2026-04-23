"""migrate_document_embeddings_to_halfvec_3072

Revision ID: e0f04e4194bc
Revises: a3b4c5d6e7f8
Create Date: 2026-04-23 19:07:26.157735

Story 9.6: migrate document_embeddings from OpenAI text-embedding-3-small
(1536-dim `vector`) to text-embedding-3-large (3072-dim `halfvec`) — closes
TD-079 (pgvector native vector HNSW caps at 2000 dims, 3-large is 3072).
Shape mirrors the Story 9.3 spike at backend/tests/eval/rag/candidates/runner.py.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'e0f04e4194bc'
down_revision: Union[str, Sequence[str], None] = 'a3b4c5d6e7f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop + re-create document_embeddings with halfvec(3072) + halfvec_cosine_ops HNSW.

    Data-destructive: the 276 existing 3-small embeddings are discarded and must be
    re-seeded via `python -m app.rag.seed` after upgrade (seed upserts from the
    committed corpus markdown). The `content` column is not preserved across the
    drop — the re-seed regenerates content + embeddings atomically per corpus file.
    """
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # halfvec requires pgvector >= 0.7.0 — fail loudly with a readable message
    # if the installed extension predates halfvec support.
    op.execute("""
        DO $$
        DECLARE
            v text;
        BEGIN
            SELECT extversion INTO v FROM pg_extension WHERE extname = 'vector';
            IF v IS NULL OR string_to_array(v, '.')::int[] < ARRAY[0,7,0] THEN
                RAISE EXCEPTION
                    'pgvector >= 0.7.0 required for halfvec (found: %)', COALESCE(v, 'not installed');
            END IF;
        END $$;
    """)

    op.execute("DROP TABLE IF EXISTS document_embeddings CASCADE")

    op.execute("""
        CREATE TABLE document_embeddings (
            id UUID PRIMARY KEY,
            doc_id VARCHAR NOT NULL,
            language VARCHAR NOT NULL,
            chunk_type VARCHAR NOT NULL,
            content TEXT NOT NULL,
            embedding halfvec(3072) NOT NULL,
            created_at TIMESTAMP NOT NULL,
            CONSTRAINT uq_doc_id_chunk_type UNIQUE (doc_id, chunk_type)
        )
    """)
    op.execute("CREATE INDEX ix_document_embeddings_doc_id ON document_embeddings (doc_id)")
    op.execute("CREATE INDEX ix_document_embeddings_language ON document_embeddings (language)")

    op.execute(
        "CREATE INDEX ix_document_embeddings_hnsw ON document_embeddings "
        "USING hnsw (embedding halfvec_cosine_ops) WITH (m = 16, ef_construction = 64)"
    )


def downgrade() -> None:
    """Schema-only downgrade. The `document_embeddings` table is TRUNCATED and must be re-seeded via `python -m app.rag.seed` after downgrade. The 3-small embeddings that existed pre-migration are not recoverable from the migration alone."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.execute("DROP TABLE IF EXISTS document_embeddings CASCADE")

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

    op.execute(
        "CREATE INDEX ix_document_embeddings_hnsw ON document_embeddings "
        "USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)"
    )
