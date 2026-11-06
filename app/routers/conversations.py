from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.crypto import decrypt_secret
from app.database import get_db
from app.models import Conversation, Message, TelegramIntegration, utcnow
from app.schemas import (
    ConversationDetailOut,
    ConversationOut,
    HandoffIn,
    MessageOut,
    ReplyIn,
)
from app.security import Context, get_context, require_roles
import app.services.telegram as telegram_api
from app.services.audit import log_action

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("")
async def list_conversations(
    channel: str | None = Query(default=None),
    handoff: bool | None = Query(default=None),
    q: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=60, ge=1, le=200),
    ctx: Context = Depends(get_context),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    stmt = select(Conversation).where(Conversation.org_id == ctx.org_id)
    if channel:
        stmt = stmt.where(Conversation.channel == channel)
    if handoff is not None:
        stmt = stmt.where(Conversation.is_handoff.is_(handoff))
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Conversation.customer_name.ilike(pattern),
                Conversation.external_id.ilike(pattern),
            )
        )

    conversations = (
        await db.execute(
            stmt.order_by(Conversation.last_message_at.desc()).limit(limit)
        )
    ).scalars().all()
    if not conversations:
        return []

    ids = [conversation.id for conversation in conversations]
    messages = (
        await db.execute(
            select(Message)
            .where(Message.conversation_id.in_(ids))
            .order_by(Message.created_at.desc())
        )
    ).scalars().all()
    latest: dict[str, Message] = {}
    for message in messages:
        latest.setdefault(message.conversation_id, message)

    result = []
    for conversation in conversations:
        last = latest.get(conversation.id)
        result.append(
            {
                "id": conversation.id,
                "channel": conversation.channel,
                "external_id": conversation.external_id,
                "customer_name": conversation.customer_name or "Anonim mijoz",
                "ai_enabled": conversation.ai_enabled,
                "is_handoff": conversation.is_handoff,
                "handoff_reason": conversation.handoff_reason,
                "assigned_to": conversation.assigned_to,
                "last_message_at": conversation.last_message_at.isoformat(),
                "last_message": (last.content[:140] if last else ""),
                "last_role": last.role if last else "",
            }
        )
    return result


@router.get("/{conversation_id}", response_model=ConversationDetailOut)
async def get_conversation(
    conversation_id: str,
    ctx: Context = Depends(get_context),
    db: AsyncSession = Depends(get_db),
) -> ConversationDetailOut:
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None or conversation.org_id != ctx.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Suhbat topilmadi")
    messages = (
        await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at)
            .limit(500)
        )
    ).scalars().all()
    return ConversationDetailOut(
        conversation=ConversationOut.model_validate(conversation),
        messages=[MessageOut.model_validate(message) for message in messages],
    )


@router.post("/{conversation_id}/reply", response_model=MessageOut)
async def operator_reply(
    conversation_id: str,
    payload: ReplyIn,
    ctx: Context = Depends(require_roles("operator")),
    db: AsyncSession = Depends(get_db),
) -> MessageOut:
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None or conversation.org_id != ctx.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Suhbat topilmadi")

    message = Message(
        org_id=ctx.org_id,
        conversation_id=conversation.id,
        role="operator",
        content=payload.text,
        meta={"operator_id": ctx.user.id, "channel": conversation.channel},
    )
    db.add(message)
    conversation.ai_enabled = False
    conversation.is_handoff = True
    conversation.assigned_to = ctx.user.id
    conversation.last_message_at = utcnow()
    await log_action(
        db, action="conversation.reply", org_id=ctx.org_id, user_id=ctx.user.id,
        entity="conversation", meta={"conversation_id": conversation.id},
    )
    await db.commit()
    await db.refresh(message)

    integration = (
        await db.execute(
            select(TelegramIntegration).where(TelegramIntegration.org_id == ctx.org_id)
        )
    ).scalar_one_or_none()
    if integration is not None and integration.active and conversation.channel == "telegram":
        try:
            await telegram_api.send_message(
                decrypt_secret(integration.token_encrypted),
                conversation.external_id,
                payload.text,
            )
        except telegram_api.TelegramError:
            pass

    return MessageOut.model_validate(message)


@router.post("/{conversation_id}/handoff", response_model=ConversationOut)
async def handoff(
    conversation_id: str,
    payload: HandoffIn,
    ctx: Context = Depends(require_roles("operator")),
    db: AsyncSession = Depends(get_db),
) -> ConversationOut:
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None or conversation.org_id != ctx.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Suhbat topilmadi")
    conversation.is_handoff = True
    conversation.ai_enabled = False
    conversation.assigned_to = payload.assigned_to or ctx.user.id
    conversation.handoff_reason = payload.reason or "Operator qabul qildi"
    await log_action(
        db, action="conversation.handoff", org_id=ctx.org_id, user_id=ctx.user.id,
        entity="conversation", meta={"conversation_id": conversation.id},
    )
    await db.commit()
    return ConversationOut.model_validate(conversation)


@router.post("/{conversation_id}/resume-ai", response_model=ConversationOut)
async def resume_ai(
    conversation_id: str,
    ctx: Context = Depends(require_roles("operator")),
    db: AsyncSession = Depends(get_db),
) -> ConversationOut:
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None or conversation.org_id != ctx.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Suhbat topilmadi")
    conversation.is_handoff = False
    conversation.ai_enabled = True
    conversation.assigned_to = None
    conversation.handoff_reason = ""
    await log_action(
        db, action="conversation.resume_ai", org_id=ctx.org_id, user_id=ctx.user.id,
        entity="conversation", meta={"conversation_id": conversation.id},
    )
    await db.commit()
    return ConversationOut.model_validate(conversation)
