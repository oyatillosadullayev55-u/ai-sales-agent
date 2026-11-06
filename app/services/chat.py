from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Conversation, Message, Organization, utcnow
from app.services import agent


def _clean_sources(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keys = ("document_id", "document_name", "chunk_index", "score", "snippet")
    return [{key: source.get(key) for key in keys} for source in sources[:4]]


async def find_conversation(
    db: AsyncSession, org_id: str, channel: str, external_id: str
) -> Conversation | None:
    return (
        await db.execute(
            select(Conversation).where(
                Conversation.org_id == org_id,
                Conversation.channel == channel,
                Conversation.external_id == external_id[:120],
            )
        )
    ).scalar_one_or_none()


async def get_or_create_conversation(
    db: AsyncSession,
    org: Organization,
    channel: str,
    external_id: str,
    name: str | None = None,
) -> Conversation:
    conversation = await find_conversation(db, org.id, channel, external_id)
    if conversation is None:
        conversation = Conversation(
            org_id=org.id,
            channel=channel,
            external_id=external_id[:120],
            customer_name=(name or "")[:160],
            state={},
        )
        db.add(conversation)
        await db.flush()
    elif name and not conversation.customer_name:
        conversation.customer_name = name[:160]
    return conversation


async def handle_message(
    db: AsyncSession,
    org: Organization,
    conversation: Conversation,
    text: str,
    source: str = "widget",
) -> agent.AgentResult:
    user_message = Message(
        org_id=org.id,
        conversation_id=conversation.id,
        role="user",
        content=text,
        meta={"channel": source},
    )
    db.add(user_message)
    await db.flush()

    result = await agent.respond(db, org, conversation, text, source=source)

    assistant_message = Message(
        org_id=org.id,
        conversation_id=conversation.id,
        role="assistant",
        content=result.text,
        latency_ms=result.latency_ms,
        meta={
            "channel": source,
            "products": result.products[:4],
            "sources": _clean_sources(result.sources),
            "handoff": result.handoff,
            "order_id": (result.order or {}).get("id") if result.order else None,
        },
    )
    db.add(assistant_message)
    conversation.last_message_at = utcnow()
    await db.flush()
    return result
