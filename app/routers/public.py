from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import AgentSettings, Message, Organization, Widget, utcnow
from app.schemas import ChatReplyOut, PublicChatIn
from app.services.agent import detect_language
from app.services.chat import find_conversation, get_or_create_conversation, handle_message
from app.services.limits import ensure_conversation_limit

router = APIRouter(prefix="/public", tags=["public"])

OPERATOR_TEXT = {
    "uz": "Operatorimiz tez orada javob beradi. Iltimos, biroz kuting.",
    "ru": "Наш оператор скоро ответит. Пожалуйста, подождите немного.",
    "en": "Our operator will reply shortly. Please wait a moment.",
}


async def _widget_org(db: AsyncSession, public_key: str) -> tuple[Widget, Organization]:
    widget = (
        await db.execute(
            select(Widget).where(Widget.public_key == public_key, Widget.active.is_(True))
        )
    ).scalar_one_or_none()
    if widget is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Widget topilmadi")
    org = await db.get(Organization, widget.org_id)
    if org is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tashkilot topilmadi")
    return widget, org


@router.get("/widget/{public_key}/config")
async def widget_config(public_key: str, db: AsyncSession = Depends(get_db)) -> dict:
    widget, org = await _widget_org(db, public_key)
    agent_settings = (
        await db.execute(select(AgentSettings).where(AgentSettings.org_id == org.id))
    ).scalar_one_or_none()
    return {
        "title": widget.title,
        "color": widget.color,
        "greeting": widget.greeting,
        "org_name": org.name,
        "agent_name": agent_settings.agent_name if agent_settings else "Nova",
        "language": agent_settings.language if agent_settings else "uz",
    }


@router.post("/widget/{public_key}/messages", response_model=ChatReplyOut)
async def widget_message(
    public_key: str,
    payload: PublicChatIn,
    db: AsyncSession = Depends(get_db),
) -> ChatReplyOut:
    widget, org = await _widget_org(db, public_key)
    visitor_id = payload.visitor_id.strip()[:120]
    text = payload.text.strip()
    if not text:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Xabar bo'sh")

    conversation = await find_conversation(db, org.id, "widget", visitor_id)
    if conversation is None:
        await ensure_conversation_limit(db, org)
        conversation = await get_or_create_conversation(
            db, org, "widget", visitor_id, payload.name
        )
    elif payload.name and not conversation.customer_name:
        conversation.customer_name = payload.name[:160]
        await db.flush()

    lang = detect_language(text) or (conversation.state or {}).get("lang") or "uz"

    if not conversation.ai_enabled:
        db.add(
            Message(
                org_id=org.id,
                conversation_id=conversation.id,
                role="user",
                content=text,
                meta={"channel": "widget"},
            )
        )
        conversation.last_message_at = utcnow()
        await db.commit()
        return ChatReplyOut(
            conversation_id=conversation.id,
            text=OPERATOR_TEXT.get(lang, OPERATOR_TEXT["uz"]),
            handoff=True,
            ai_enabled=False,
        )

    result = await handle_message(db, org, conversation, text, source="widget")
    await db.commit()
    return ChatReplyOut(
        conversation_id=conversation.id,
        text=result.text,
        products=result.products[:4],
        sources=[
            {
                "document_id": source["document_id"],
                "document_name": source["document_name"],
                "chunk_index": source["chunk_index"],
                "score": source["score"],
                "snippet": source["snippet"],
            }
            for source in result.sources[:4]
        ],
        quick=result.quick[:3],
        handoff=result.handoff,
        ai_enabled=conversation.ai_enabled,
        order=result.order,
    )


@router.get("/widget/{public_key}/history")
async def widget_history(
    public_key: str, visitor_id: str, db: AsyncSession = Depends(get_db)
) -> dict:
    _widget, org = await _widget_org(db, public_key)
    conversation = await find_conversation(db, org.id, "widget", visitor_id.strip()[:120])
    if conversation is None:
        return {"messages": []}
    rows = (
        await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at)
            .limit(100)
        )
    ).scalars().all()
    return {
        "messages": [
            {
                "role": row.role,
                "content": row.content,
                "meta": row.meta,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ],
        "ai_enabled": conversation.ai_enabled,
    }


@router.get("/demo")
async def demo_widget(db: AsyncSession = Depends(get_db)) -> dict:
    org = (
        await db.execute(select(Organization).where(Organization.slug == "demo-store"))
    ).scalar_one_or_none()
    if org is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Demo tashkilot topilmadi")
    widget = (
        await db.execute(select(Widget).where(Widget.org_id == org.id))
    ).scalar_one_or_none()
    if widget is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Demo widget topilmadi")
    agent_settings = (
        await db.execute(select(AgentSettings).where(AgentSettings.org_id == org.id))
    ).scalar_one_or_none()
    return {
        "public_key": widget.public_key,
        "title": widget.title,
        "color": widget.color,
        "greeting": widget.greeting,
        "org_name": org.name,
        "agent_name": agent_settings.agent_name if agent_settings else "Nova",
    }
