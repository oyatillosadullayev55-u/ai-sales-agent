from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Conversation, Membership, Message, Order, Organization, User
from app.schemas import AdminOrgOut, AdminStatsOut, PlanUpdateIn
from app.security import require_super_admin
from app.services.audit import log_action

router = APIRouter(prefix="/admin", tags=["admin"])


async def _org_row(db: AsyncSession, org: Organization) -> AdminOrgOut:
    owner = await db.get(User, org.owner_id)
    users = int(
        await db.scalar(select(func.count(Membership.id)).where(Membership.org_id == org.id)) or 0
    )
    conversations = int(
        await db.scalar(select(func.count(Conversation.id)).where(Conversation.org_id == org.id)) or 0
    )
    orders = int(
        await db.scalar(select(func.count(Order.id)).where(Order.org_id == org.id)) or 0
    )
    revenue = float(
        await db.scalar(
            select(func.coalesce(func.sum(Order.total), 0)).where(
                Order.org_id == org.id, Order.status != "cancelled"
            )
        )
        or 0
    )
    return AdminOrgOut(
        id=org.id,
        name=org.name,
        slug=org.slug,
        plan=org.plan,
        owner_email=owner.email if owner else "",
        users=users,
        conversations=conversations,
        orders=orders,
        revenue=round(revenue, 2),
        created_at=org.created_at,
    )


@router.get("/stats", response_model=AdminStatsOut)
async def stats(
    _: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)
) -> AdminStatsOut:
    orgs = int(await db.scalar(select(func.count(Organization.id))) or 0)
    users = int(await db.scalar(select(func.count(User.id))) or 0)
    conversations = int(await db.scalar(select(func.count(Conversation.id))) or 0)
    orders = int(await db.scalar(select(func.count(Order.id))) or 0)
    revenue = float(
        await db.scalar(
            select(func.coalesce(func.sum(Order.total), 0)).where(Order.status != "cancelled")
        )
        or 0
    )
    ai_messages = int(
        await db.scalar(select(func.count(Message.id)).where(Message.role == "assistant")) or 0
    )

    plan_rows = (
        await db.execute(select(Organization.plan, func.count(Organization.id)).group_by(Organization.plan))
    ).all()
    by_plan = {row[0]: int(row[1]) for row in plan_rows}

    recent = (
        await db.execute(select(Organization).order_by(Organization.created_at.desc()).limit(10))
    ).scalars().all()
    recent_orgs = [await _org_row(db, org) for org in recent]

    return AdminStatsOut(
        orgs=orgs,
        users=users,
        conversations=conversations,
        orders=orders,
        revenue=round(revenue, 2),
        ai_messages=ai_messages,
        by_plan=by_plan,
        recent_orgs=recent_orgs,
    )


@router.get("/orgs", response_model=list[AdminOrgOut])
async def list_orgs(
    _: User = Depends(require_super_admin), db: AsyncSession = Depends(get_db)
) -> list[AdminOrgOut]:
    orgs = (
        await db.execute(select(Organization).order_by(Organization.created_at.desc()).limit(200))
    ).scalars().all()
    return [await _org_row(db, org) for org in orgs]


@router.patch("/orgs/{org_id}/plan", response_model=AdminOrgOut)
async def change_plan(
    org_id: str,
    payload: PlanUpdateIn,
    admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminOrgOut:
    org = await db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tashkilot topilmadi")
    org.plan = payload.plan
    await log_action(
        db, action="admin.plan_change", org_id=org.id, user_id=admin.id,
        entity="organization", meta={"plan": payload.plan},
    )
    await db.commit()
    return await _org_row(db, org)
