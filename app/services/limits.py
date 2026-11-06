from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import PLANS
from app.models import Conversation, KnowledgeDocument, Membership, Order, Organization


def month_start() -> datetime:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def plan_limits(org: Organization) -> dict:
    return PLANS.get(org.plan, PLANS["starter"])


async def conversation_usage(db: AsyncSession, org_id: str) -> int:
    value = await db.scalar(
        select(func.count(Conversation.id)).where(
            Conversation.org_id == org_id, Conversation.created_at >= month_start()
        )
    )
    return int(value or 0)


async def document_usage(db: AsyncSession, org_id: str) -> int:
    value = await db.scalar(
        select(func.count(KnowledgeDocument.id)).where(KnowledgeDocument.org_id == org_id)
    )
    return int(value or 0)


async def member_usage(db: AsyncSession, org_id: str) -> int:
    value = await db.scalar(
        select(func.count(Membership.id)).where(Membership.org_id == org_id)
    )
    return int(value or 0)


async def ensure_conversation_limit(db: AsyncSession, org: Organization) -> None:
    limits = plan_limits(org)
    used = await conversation_usage(db, org.id)
    if used >= limits["conversations"]:
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            {
                "code": "plan_limit_reached",
                "message": "Oylik suhbatlar limiti tugadi. Tarifni oshiring.",
                "plan": org.plan,
                "limit": limits["conversations"],
            },
        )


async def ensure_document_limit(db: AsyncSession, org: Organization) -> None:
    limits = plan_limits(org)
    used = await document_usage(db, org.id)
    if used >= limits["documents"]:
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            {
                "code": "plan_limit_reached",
                "message": "Hujjatlar limiti tugadi. Tarifni oshiring.",
                "plan": org.plan,
                "limit": limits["documents"],
            },
        )


async def usage_snapshot(db: AsyncSession, org: Organization) -> dict:
    return {
        "conversations": await conversation_usage(db, org.id),
        "conversation_limit": plan_limits(org)["conversations"],
        "documents": await document_usage(db, org.id),
        "document_limit": plan_limits(org)["documents"],
        "team": await member_usage(db, org.id),
        "team_limit": plan_limits(org)["team"],
        "orders": int(
            await db.scalar(select(func.count(Order.id)).where(Order.org_id == org.id)) or 0
        ),
    }
