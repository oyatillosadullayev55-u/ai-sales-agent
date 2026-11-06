from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Conversation, Message, Order, utcnow


async def overview(db: AsyncSession, org_id: str, days: int = 30) -> dict[str, Any]:
    days = max(1, min(days, 365))
    since = (utcnow() - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)

    base = (Conversation.org_id == org_id, Conversation.created_at >= since)
    conversations = int(await db.scalar(select(func.count(Conversation.id)).where(*base)) or 0)
    new_customers = int(
        await db.scalar(
            select(func.count(func.distinct(Conversation.external_id))).where(*base)
        )
        or 0
    )
    handoffs = int(
        await db.scalar(
            select(func.count(Conversation.id)).where(*base, Conversation.is_handoff.is_(True))
        )
        or 0
    )

    message_base = (Message.org_id == org_id, Message.created_at >= since)
    messages = int(await db.scalar(select(func.count(Message.id)).where(*message_base)) or 0)
    ai_messages = int(
        await db.scalar(
            select(func.count(Message.id)).where(*message_base, Message.role == "assistant")
        )
        or 0
    )
    avg_response = await db.scalar(
        select(func.avg(Message.latency_ms)).where(
            *message_base, Message.role == "assistant", Message.latency_ms > 0
        )
    )

    order_base = (
        Order.org_id == org_id,
        Order.created_at >= since,
        Order.status != "cancelled",
    )
    orders = int(await db.scalar(select(func.count(Order.id)).where(*order_base)) or 0)
    revenue = float(await db.scalar(select(func.coalesce(func.sum(Order.total), 0)).where(*order_base)) or 0)

    channel_rows = (
        await db.execute(
            select(Conversation.channel, func.count(Conversation.id))
            .where(*base)
            .group_by(Conversation.channel)
        )
    ).all()
    by_channel = {row[0]: int(row[1]) for row in channel_rows}

    series: list[dict[str, Any]] = []
    conv_rows = (
        await db.execute(
            select(Conversation.created_at).where(Conversation.org_id == org_id, Conversation.created_at >= since)
        )
    ).scalars().all()
    order_rows = (
        await db.execute(
            select(Order.created_at, Order.total).where(*order_base)
        )
    ).all()
    for offset in range(days):
        day = (since + timedelta(days=offset)).date()
        series.append(
            {
                "date": day.isoformat(),
                "conversations": sum(1 for value in conv_rows if value.date() == day),
                "orders": sum(1 for row in order_rows if row[0].date() == day),
                "revenue": round(sum(float(row[1]) for row in order_rows if row[0].date() == day), 2),
            }
        )

    top_counter: dict[str, dict[str, Any]] = {}
    all_orders = (
        await db.execute(select(Order.items).where(*order_base))
    ).scalars().all()
    for items in all_orders:
        for item in items or []:
            key = str(item.get("product_id") or item.get("name"))
            entry = top_counter.setdefault(
                key, {"name": item.get("name", ""), "qty": 0, "revenue": 0.0}
            )
            entry["qty"] += int(item.get("qty", 0))
            entry["revenue"] += float(item.get("price", 0)) * int(item.get("qty", 0))
    top_products = sorted(top_counter.values(), key=lambda x: x["revenue"], reverse=True)[:5]

    recent = (
        await db.execute(
            select(Conversation)
            .where(Conversation.org_id == org_id)
            .order_by(Conversation.last_message_at.desc())
            .limit(6)
        )
    ).scalars().all()

    recent_conversations = []
    for conversation in recent:
        last_message = await db.scalar(
            select(Message.content)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        recent_conversations.append(
            {
                "id": conversation.id,
                "channel": conversation.channel,
                "customer_name": conversation.customer_name or "Anonim mijoz",
                "external_id": conversation.external_id,
                "is_handoff": conversation.is_handoff,
                "ai_enabled": conversation.ai_enabled,
                "last_message_at": conversation.last_message_at.isoformat(),
                "last_message": (last_message or "")[:120],
            }
        )

    conversion = round((orders / conversations) * 100, 1) if conversations else 0.0

    return {
        "range_days": days,
        "conversations": conversations,
        "new_customers": new_customers,
        "messages": messages,
        "ai_messages": ai_messages,
        "orders": orders,
        "revenue": round(revenue, 2),
        "handoffs": handoffs,
        "conversion_rate": conversion,
        "avg_response_ms": int(avg_response or 0),
        "by_channel": by_channel,
        "series": series,
        "top_products": top_products,
        "recent_conversations": recent_conversations,
    }


def parse_days(value: str | int | None, default: int = 30) -> int:
    try:
        days = int(value) if value is not None else default
    except (TypeError, ValueError):
        return default
    return max(1, min(days, 365))


def today_start() -> datetime:
    return utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
