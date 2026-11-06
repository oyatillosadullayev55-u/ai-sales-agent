from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.crypto import decrypt_secret, encrypt_secret
from app.database import get_db
from app.models import TelegramIntegration, Widget
from app.schemas import TelegramConnectIn, WidgetInfoOut, WidgetOut, WidgetUpdateIn
from app.security import Context, get_context, require_roles
from app.services import telegram
from app.services.audit import log_action

router = APIRouter(prefix="/integrations", tags=["integrations"])


def embed_code(public_key: str) -> str:
    base = settings.public_base_url.rstrip("/")
    return (
        f'<script src="{base}/static/js/widget.js" '
        f'data-ai-widget="{public_key}" defer></script>'
    )


async def ensure_widget(db: AsyncSession, org_id: str) -> Widget:
    widget = (
        await db.execute(select(Widget).where(Widget.org_id == org_id))
    ).scalar_one_or_none()
    if widget is None:
        widget = Widget(org_id=org_id, public_key=secrets.token_urlsafe(12))
        db.add(widget)
        await db.flush()
    return widget


@router.get("/telegram")
async def get_telegram(
    ctx: Context = Depends(get_context), db: AsyncSession = Depends(get_db)
) -> dict:
    integration = (
        await db.execute(
            select(TelegramIntegration).where(TelegramIntegration.org_id == ctx.org_id)
        )
    ).scalar_one_or_none()
    if integration is None:
        return {"connected": False, "bot_username": "", "webhook_url": "", "active": False}
    return {
        "connected": True,
        "bot_username": integration.bot_username,
        "webhook_url": telegram.webhook_url(integration.webhook_secret),
        "active": integration.active,
    }


@router.post("/telegram")
async def connect_telegram(
    payload: TelegramConnectIn,
    ctx: Context = Depends(require_roles("owner")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    token = payload.token.strip()
    try:
        me = await telegram.get_me(token)
    except telegram.TelegramError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Bot tokeni tekshirilmadi: {exc}") from exc

    integration = (
        await db.execute(
            select(TelegramIntegration).where(TelegramIntegration.org_id == ctx.org_id)
        )
    ).scalar_one_or_none()
    if integration is None:
        integration = TelegramIntegration(
            org_id=ctx.org_id,
            token_encrypted=encrypt_secret(token),
            bot_username=me.get("username", ""),
            webhook_secret=secrets.token_urlsafe(24),
        )
        db.add(integration)
    else:
        integration.token_encrypted = encrypt_secret(token)
        integration.bot_username = me.get("username", "")
        integration.active = True

    await log_action(
        db, action="integration.telegram_connect", org_id=ctx.org_id, user_id=ctx.user.id,
        entity="telegram", meta={"bot": me.get("username", "")},
    )
    await db.commit()
    return {
        "connected": True,
        "bot_username": integration.bot_username,
        "webhook_url": telegram.webhook_url(integration.webhook_secret),
        "active": True,
    }


@router.post("/telegram/set-webhook")
async def set_telegram_webhook(
    ctx: Context = Depends(require_roles("owner")), db: AsyncSession = Depends(get_db)
) -> dict:
    integration = (
        await db.execute(
            select(TelegramIntegration).where(TelegramIntegration.org_id == ctx.org_id)
        )
    ).scalar_one_or_none()
    if integration is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Telegram bot ulanmagan")
    if not settings.public_base_url.startswith("https://"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Telegram webhook uchun PUBLIC_BASE_URL https bo'lishi kerak (ngrok yoki deploy domeni).",
        )
    url = telegram.webhook_url(integration.webhook_secret)
    try:
        await telegram.set_webhook(
            decrypt_secret(integration.token_encrypted), url, integration.webhook_secret
        )
    except telegram.TelegramError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    return {"ok": True, "webhook_url": url}


@router.delete("/telegram", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_telegram(
    ctx: Context = Depends(require_roles("owner")), db: AsyncSession = Depends(get_db)
) -> None:
    integration = (
        await db.execute(
            select(TelegramIntegration).where(TelegramIntegration.org_id == ctx.org_id)
        )
    ).scalar_one_or_none()
    if integration is None:
        return
    try:
        await telegram.delete_webhook(decrypt_secret(integration.token_encrypted))
    except Exception:  # noqa: BLE001 - best effort
        pass
    await db.delete(integration)
    await log_action(
        db, action="integration.telegram_disconnect", org_id=ctx.org_id, user_id=ctx.user.id,
        entity="telegram",
    )
    await db.commit()


@router.get("/widget", response_model=WidgetInfoOut)
async def get_widget(
    ctx: Context = Depends(get_context), db: AsyncSession = Depends(get_db)
) -> WidgetInfoOut:
    widget = await ensure_widget(db, ctx.org_id)
    await db.commit()
    data = WidgetOut.model_validate(widget).model_dump()
    return WidgetInfoOut(**data, embed_code=embed_code(widget.public_key))


@router.put("/widget", response_model=WidgetInfoOut)
async def update_widget(
    payload: WidgetUpdateIn,
    ctx: Context = Depends(require_roles("manager")),
    db: AsyncSession = Depends(get_db),
) -> WidgetInfoOut:
    widget = await ensure_widget(db, ctx.org_id)
    data = payload.model_dump(exclude_none=True)
    if "color" in data and not data["color"].startswith("#"):
        data["color"] = "#22d3a6"
    for field, value in data.items():
        setattr(widget, field, value)
    await log_action(
        db, action="integration.widget_update", org_id=ctx.org_id, user_id=ctx.user.id,
        entity="widget", meta={"fields": list(data.keys())},
    )
    await db.commit()
    result = WidgetOut.model_validate(widget).model_dump()
    return WidgetInfoOut(**result, embed_code=embed_code(widget.public_key))
