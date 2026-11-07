from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import TelegramIntegration
from app.services.telegram_bot import process_update

router = APIRouter(prefix="/telegram", tags=["telegram"])


@router.post("/webhook/{secret}")
async def webhook(
    secret: str,
    update: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    integration = (
        await db.execute(
            select(TelegramIntegration).where(
                TelegramIntegration.webhook_secret == secret,
                TelegramIntegration.active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if integration is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Webhook topilmadi")

    header_secret = request.headers.get("x-telegram-bot-api-secret-token")
    if header_secret and header_secret != secret:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Secret mos emas")

    await process_update(db, integration, update)
    return {"ok": True}
