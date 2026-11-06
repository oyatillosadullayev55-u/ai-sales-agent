from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Membership, Organization, User
from app.schemas import (
    AgentSettingsIn,
    AgentSettingsOut,
    InviteIn,
    MemberOut,
    MemberRoleIn,
    OrgOut,
    OrgUpdateIn,
)
from app.security import Context, get_context, hash_password, require_roles
from app.services.agent import get_agent_settings
from app.services.audit import log_action
from app.services.limits import member_usage, plan_limits

router = APIRouter(prefix="/orgs", tags=["organizations"])


@router.get("", response_model=OrgOut)
async def get_org(ctx: Context = Depends(get_context)) -> OrgOut:
    return OrgOut.model_validate(ctx.org)


@router.patch("", response_model=OrgOut)
async def update_org(
    payload: OrgUpdateIn,
    ctx: Context = Depends(require_roles("owner")),
    db: AsyncSession = Depends(get_db),
) -> OrgOut:
    org = await db.get(Organization, ctx.org_id)
    assert org is not None
    data = payload.model_dump(exclude_none=True)
    for field, value in data.items():
        setattr(org, field, value)
    await log_action(
        db, action="org.update", org_id=org.id, user_id=ctx.user.id, entity="organization",
        meta={"fields": list(data.keys())},
    )
    await db.commit()
    return OrgOut.model_validate(org)


@router.get("/members", response_model=list[MemberOut])
async def list_members(
    ctx: Context = Depends(get_context), db: AsyncSession = Depends(get_db)
) -> list[MemberOut]:
    rows = (
        await db.execute(
            select(Membership, User)
            .join(User, User.id == Membership.user_id)
            .where(Membership.org_id == ctx.org_id)
            .order_by(Membership.created_at)
        )
    ).all()
    return [
        MemberOut(
            id=membership.id,
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=membership.role,
            created_at=membership.created_at,
        )
        for membership, user in rows
    ]


@router.post("/members", status_code=status.HTTP_201_CREATED)
async def invite_member(
    payload: InviteIn,
    ctx: Context = Depends(require_roles("manager")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    limits = plan_limits(ctx.org)
    if await member_usage(db, ctx.org_id) >= limits["team"]:
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            f"Tarif bo'yicha xodimlar limiti ({limits['team']}) tugadi",
        )

    email = payload.email.lower().strip()
    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    temporary_password = None

    if user is None:
        temporary_password = payload.password or secrets.token_urlsafe(9)
        try:
            password_hash = hash_password(temporary_password)
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
        user = User(email=email, password_hash=password_hash, full_name=payload.full_name.strip())
        db.add(user)
        await db.flush()

    existing = await db.scalar(
        select(Membership.id).where(
            Membership.org_id == ctx.org_id, Membership.user_id == user.id
        )
    )
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Bu foydalanuvchi allaqachon a'zo")

    membership = Membership(org_id=ctx.org_id, user_id=user.id, role=payload.role)
    db.add(membership)
    await log_action(
        db, action="member.invite", org_id=ctx.org_id, user_id=ctx.user.id, entity="membership",
        meta={"email": email, "role": payload.role},
    )
    await db.commit()
    return {
        "id": membership.id,
        "user_id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": membership.role,
        "created_at": membership.created_at.isoformat(),
        "temporary_password": temporary_password,
    }


@router.patch("/members/{membership_id}")
async def update_member_role(
    membership_id: str,
    payload: MemberRoleIn,
    ctx: Context = Depends(require_roles("owner")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    membership = await db.get(Membership, membership_id)
    if membership is None or membership.org_id != ctx.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "A'zo topilmadi")
    if membership.role == "owner":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Tashkilot egasining rolini o'zgartirib bo'lmaydi")
    membership.role = payload.role
    await log_action(
        db, action="member.role", org_id=ctx.org_id, user_id=ctx.user.id,
        entity="membership", meta={"membership_id": membership.id, "role": payload.role},
    )
    await db.commit()
    return {"ok": True}


@router.delete("/members/{membership_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    membership_id: str,
    ctx: Context = Depends(require_roles("owner")),
    db: AsyncSession = Depends(get_db),
) -> None:
    membership = await db.get(Membership, membership_id)
    if membership is None or membership.org_id != ctx.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "A'zo topilmadi")
    if membership.role == "owner":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Tashkilot egasini o'chirib bo'lmaydi")
    await db.delete(membership)
    await log_action(
        db, action="member.remove", org_id=ctx.org_id, user_id=ctx.user.id, entity="membership",
        meta={"membership_id": membership_id},
    )
    await db.commit()


@router.get("/agent", response_model=AgentSettingsOut)
async def get_agent(
    ctx: Context = Depends(get_context), db: AsyncSession = Depends(get_db)
) -> AgentSettingsOut:
    row = await get_agent_settings(db, ctx.org)
    await db.commit()
    return AgentSettingsOut.model_validate(row)


@router.put("/agent", response_model=AgentSettingsOut)
async def update_agent(
    payload: AgentSettingsIn,
    ctx: Context = Depends(require_roles("manager")),
    db: AsyncSession = Depends(get_db),
) -> AgentSettingsOut:
    row = await get_agent_settings(db, ctx.org)
    data = payload.model_dump(exclude_none=True)
    if "handoff_keywords" in data:
        data["handoff_keywords"] = [
            str(keyword).strip()[:40] for keyword in data["handoff_keywords"] if str(keyword).strip()
        ][:20]
    for field, value in data.items():
        setattr(row, field, value)
    await log_action(
        db, action="agent.update", org_id=ctx.org_id, user_id=ctx.user.id, entity="agent_settings",
        meta={"fields": list(data.keys())},
    )
    await db.commit()
    return AgentSettingsOut.model_validate(row)
