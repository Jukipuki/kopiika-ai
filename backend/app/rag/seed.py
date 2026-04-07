"""Seed the document_embeddings table from the RAG corpus markdown files.

Usage:
    cd backend
    python -m app.rag.seed

Idempotent: uses INSERT ... ON CONFLICT DO UPDATE (upsert by doc_id + chunk_type).
"""

import logging
import re
import uuid
from pathlib import Path

from sqlalchemy import text

from app.core.database import get_sync_session
from app.rag.embeddings import embed_batch

logger = logging.getLogger(__name__)

CORPUS_ROOT = Path(__file__).resolve().parent.parent.parent / "data" / "rag-corpus"
LANGUAGES = ["en", "uk"]
H2_PATTERN = re.compile(r"^## (.+)$", re.MULTILINE)


def _chunk_document(content: str) -> list[tuple[str, str]]:
    """Split markdown content by H2 headers.

    Returns list of (chunk_type, chunk_content) tuples.
    chunk_type is the slugified H2 header name.
    chunk_content is the full '## Header\\n...content' text.
    """
    matches = list(H2_PATTERN.finditer(content))
    if not matches:
        return [("full_document", content.strip())]

    chunks: list[tuple[str, str]] = []

    # Capture any content before the first H2 header (e.g. H1 title, intro)
    preamble = content[: matches[0].start()].strip()
    if preamble:
        chunks.append(("preamble", preamble))

    for i, match in enumerate(matches):
        header = match.group(1).strip()
        chunk_type = header.lower().replace(" ", "_")
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        chunk_content = content[start:end].strip()
        if chunk_content:
            chunks.append((chunk_type, chunk_content))
    return chunks


def _slugify_filename(path: Path) -> str:
    """Convert filename to slug: 'budgeting-basics.md' -> 'budgeting-basics'."""
    return path.stem


def seed() -> None:
    """Read corpus files, embed chunks, and upsert into document_embeddings."""
    total_chunks = 0
    total_files = 0

    for lang in LANGUAGES:
        lang_dir = CORPUS_ROOT / lang
        if not lang_dir.exists():
            logger.warning("Corpus directory not found: %s", lang_dir)
            continue

        md_files = sorted(lang_dir.glob("*.md"))
        logger.info("Found %d corpus files for language '%s'", len(md_files), lang)

        for md_file in md_files:
            content = md_file.read_text(encoding="utf-8")
            slug = _slugify_filename(md_file)
            doc_id = f"{lang}/{slug}"

            chunks = _chunk_document(content)
            if not chunks:
                continue

            total_files += 1
            chunk_texts = [cc for _, cc in chunks]

            # Embed all chunks in a single API call per document
            embeddings = embed_batch(chunk_texts)

            with get_sync_session() as session:
                for (chunk_type, chunk_content), embedding in zip(chunks, embeddings):
                    embedding_literal = "[" + ",".join(str(v) for v in embedding) + "]"
                    session.execute(
                        text(f"""
                            INSERT INTO document_embeddings
                                (id, doc_id, language, chunk_type, content, embedding, created_at)
                            VALUES
                                (:id, :doc_id, :language, :chunk_type, :content,
                                 '{embedding_literal}'::vector, NOW())
                            ON CONFLICT (doc_id, chunk_type) DO UPDATE SET
                                content = EXCLUDED.content,
                                embedding = EXCLUDED.embedding,
                                created_at = NOW()
                        """),
                        {
                            "id": str(uuid.uuid4()),
                            "doc_id": doc_id,
                            "language": lang,
                            "chunk_type": chunk_type,
                            "content": chunk_content,
                        },
                    )
                session.commit()

            total_chunks += len(chunks)
            logger.info("Seeded %d chunks for %s", len(chunks), doc_id)

    logger.info(
        "Seed complete: %d files processed, %d total chunks upserted",
        total_files,
        total_chunks,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    seed()
