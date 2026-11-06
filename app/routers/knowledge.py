from __future__ import annotations

import time

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import KnowledgeDocument
from app.schemas import DocumentOut, QueryIn, QueryOut
from app.security import Context, get_context, require_roles
from app.services.audit import log_action
from app.services.knowledge import ingest_bytes, ingest_task, reindex_document
from app.services.limits import ensure_document_limit
from app.services.rag import rag_answer

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

ALLOWED_EXTENSIONS = {"pdf", "docx", "txt", "csv", "md"}


@router.post("/upload", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    ctx: Context = Depends(require_roles("manager")),
    db: AsyncSession = Depends(get_db),
) -> DocumentOut:
    filename = (file.filename or "document.txt").strip()
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"Faqat {', '.join(sorted(ALLOWED_EXTENSIONS))} fayllar qabul qilinadi",
        )

    data = await file.read()
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Fayl bo'sh")
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"Fayl hajmi {settings.max_upload_mb} MB dan oshmasligi kerak",
        )

    await ensure_document_limit(db, ctx.org)

    document = KnowledgeDocument(
        org_id=ctx.org_id,
        filename=filename[:255],
        content_type=file.content_type or "application/octet-stream",
        size_bytes=len(data),
        status="processing",
        created_by=ctx.user.id,
    )
    db.add(document)
    await db.flush()
    await log_action(
        db, action="knowledge.upload", org_id=ctx.org_id, user_id=ctx.user.id,
        entity="document", meta={"filename": filename, "size": len(data)},
    )

    if settings.ingest_sync:
        await ingest_bytes(db, document, data)
    else:
        await db.commit()
        background.add_task(ingest_task, document.id, data)

    await db.refresh(document)
    return DocumentOut.model_validate(document)


@router.get("", response_model=list[DocumentOut])
async def list_documents(
    ctx: Context = Depends(get_context), db: AsyncSession = Depends(get_db)
) -> list[DocumentOut]:
    rows = (
        await db.execute(
            select(KnowledgeDocument)
            .where(KnowledgeDocument.org_id == ctx.org_id)
            .order_by(KnowledgeDocument.created_at.desc())
        )
    ).scalars().all()
    return [DocumentOut.model_validate(row) for row in rows]


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    ctx: Context = Depends(require_roles("manager")),
    db: AsyncSession = Depends(get_db),
) -> None:
    document = await db.get(KnowledgeDocument, document_id)
    if document is None or document.org_id != ctx.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Hujjat topilmadi")
    await db.delete(document)
    await log_action(
        db, action="knowledge.delete", org_id=ctx.org_id, user_id=ctx.user.id,
        entity="document", meta={"document_id": document_id, "filename": document.filename},
    )
    await db.commit()


@router.post("/{document_id}/reindex", response_model=DocumentOut)
async def reindex(
    document_id: str,
    ctx: Context = Depends(require_roles("manager")),
    db: AsyncSession = Depends(get_db),
) -> DocumentOut:
    document = await db.get(KnowledgeDocument, document_id)
    if document is None or document.org_id != ctx.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Hujjat topilmadi")
    await reindex_document(db, document)
    await db.refresh(document)
    return DocumentOut.model_validate(document)


@router.post("/query", response_model=QueryOut)
async def query_knowledge(
    payload: QueryIn,
    ctx: Context = Depends(get_context),
    db: AsyncSession = Depends(get_db),
) -> QueryOut:
    started = time.perf_counter()
    from app.services.agent import get_agent_settings

    aset = await get_agent_settings(db, ctx.org)
    answer, sources = await rag_answer(
        db, ctx.org_id, payload.question, aset.language, aset.agent_name, aset.persona, aset.temperature
    )
    await db.commit()
    return QueryOut(
        answer=answer,
        sources=sources,
        latency_ms=int((time.perf_counter() - started) * 1000),
    )
