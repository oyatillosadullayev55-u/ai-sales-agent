from __future__ import annotations

import logging

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import SessionLocal
from app.models import KnowledgeChunk, KnowledgeDocument
from app.services.embeddings import embed_texts
from app.services.extract import chunk_text, extract_text

logger = logging.getLogger(__name__)


async def ingest_bytes(db: AsyncSession, document: KnowledgeDocument, data: bytes) -> None:
    try:
        text = extract_text(document.filename, document.content_type, data)
        chunks = chunk_text(text)
        if not chunks:
            raise ValueError("Hujjatdan matn ajratib olinmadi")

        vectors = await embed_texts(chunks)
        await db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.document_id == document.id))
        for index, (content, vector) in enumerate(zip(chunks, vectors)):
            db.add(
                KnowledgeChunk(
                    org_id=document.org_id,
                    document_id=document.id,
                    chunk_index=index,
                    content=content,
                    embedding=vector,
                )
            )
        document.chunk_count = len(chunks)
        document.status = "ready"
        document.error = None
    except Exception as exc:  # keep the document row for diagnostics
        logger.exception("Ingestion failed for %s", document.filename)
        document.status = "failed"
        document.error = str(exc)[:500]
    await db.commit()


async def ingest_task(document_id: str, data: bytes) -> None:
    async with SessionLocal() as db:
        document = await db.get(KnowledgeDocument, document_id)
        if document is None:
            return
        await ingest_bytes(db, document, data)


async def reindex_document(db: AsyncSession, document: KnowledgeDocument) -> None:
    rows = (
        await db.execute(select(KnowledgeChunk).where(KnowledgeChunk.document_id == document.id))
    ).scalars().all()
    if not rows:
        document.status = "failed"
        document.error = "Qayta indekslash uchun matn yo'q — faylni qayta yuklang"
        await db.commit()
        return
    vectors = await embed_texts([row.content for row in rows])
    for row, vector in zip(rows, vectors):
        row.embedding = vector
    document.status = "ready"
    document.error = None
    await db.commit()
