"""RAG retriever — cosine similarity search over document embeddings."""

import logging

from sqlalchemy import text

from app.core.database import get_sync_session
from app.rag.embeddings import embed_text

logger = logging.getLogger(__name__)

MIN_RESULTS = 3


def retrieve_relevant_docs(
    query: str,
    language: str,
    top_k: int = 5,
) -> list[dict]:
    """Retrieve the most relevant document chunks for a query.

    Filters by language first. If fewer than MIN_RESULTS are found,
    falls back to cross-lingual search to fill the gap.
    """
    query_embedding = embed_text(query)
    embedding_literal = "[" + ",".join(str(v) for v in query_embedding) + "]"

    with get_sync_session() as session:
        # Language-filtered search
        rows = session.execute(
            text("""
                SELECT doc_id, language, chunk_type, content,
                       1 - (embedding <=> :embedding::vector) AS similarity
                FROM document_embeddings
                WHERE language = :language
                ORDER BY embedding <=> :embedding::vector
                LIMIT :top_k
            """),
            {"embedding": embedding_literal, "language": language, "top_k": top_k},
        ).fetchall()

        results = [
            {
                "doc_id": r.doc_id,
                "language": r.language,
                "chunk_type": r.chunk_type,
                "content": r.content,
                "similarity": float(r.similarity),
            }
            for r in rows
        ]

        # Fallback: cross-lingual if not enough language-matched results
        if len(results) < MIN_RESULTS:
            remaining = top_k - len(results)
            existing_ids = {(r["doc_id"], r["chunk_type"]) for r in results}

            cross_rows = session.execute(
                text("""
                    SELECT doc_id, language, chunk_type, content,
                           1 - (embedding <=> :embedding::vector) AS similarity
                    FROM document_embeddings
                    WHERE language != :language
                    ORDER BY embedding <=> :embedding::vector
                    LIMIT :limit
                """),
                {"embedding": embedding_literal, "language": language, "limit": remaining + 5},
            ).fetchall()

            for r in cross_rows:
                if len(results) >= top_k:
                    break
                if (r.doc_id, r.chunk_type) not in existing_ids:
                    results.append({
                        "doc_id": r.doc_id,
                        "language": r.language,
                        "chunk_type": r.chunk_type,
                        "content": r.content,
                        "similarity": float(r.similarity),
                    })

    logger.info(
        '{"level": "INFO", "step": "rag_retrieval", "language": "%s", "results": %d}',
        language,
        len(results),
    )
    return results
