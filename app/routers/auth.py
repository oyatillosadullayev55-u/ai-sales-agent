from __future__ import annotations

import re
import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import (
    AgentSettings,
    Membership,
    Organization,
    PasswordReset,
    RefreshToken,
    User,
    Widget,
    utcnow,
)
from app.schemas import (
    ForgotIn,
    LoginIn,
    MeOut,
    OrgOut,
    RefreshIn,
    RegisterIn,
    ResetIn,
    SwitchOrgIn,
    TokenOut,
    UserOut,
)
from app.security import (
    create_access_token,
    get_current_user,
    get_membership,
    hash_password,
    hash_token,
    issue_refresh_token,
    verify_password,
)
from app.services.audit import log_action

router = APIRouter(prefix="/auth", tags=["auth"])


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "org"


async def unique_slug(db: AsyncSession, name: str) -> str:
    base = slugify(name)[:60]
    slug = base
    while await db.scalar(select(Organization.id).where(Organization.slug == slug)):
        slug = f"{base}-{secrets.token_hex(2)}"
    return slug


async def _token_response(db: AsyncSession, user: User, org: Organization | None, role: str) -> TokenOut:
    access = create_access_token(user, org.id if org else None, role)
    refresh = await issue_refresh_token(db, user, org.id if org else None)
    await db.commit()
    return TokenOut(
        access_token=access,
        refresh_token=refresh,
        user=UserOut.model_validate(user),
        org=OrgOut.model_validate(org) if org else None,
        role=role,
    )


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterIn, request: Request, db: AsyncSession = Depends(get_db)) -> TokenOut:
    email = payload.email.lower().strip()
    if await db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Bu email allaqachon ro'yxatdan o'tgan")

    try:
        password_hash = hash_password(payload.password)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    user = User(email=email, password_hash=password_hash, full_name=payload.full_name.strip())
    db.add(user)
    await db.flush()

    org = Organization(
        name=payload.org_name.strip(),
        slug=await unique_slug(db, payload.org_name),
        owner_id=user.id,
    )
    db.add(org)
    await db.flush()

    db.add(Membership(org_id=org.id, user_id=user.id, role="owner"))
    db.add(
        AgentSettings(
            org_id=org.id,
            persona=(
                f"Siz {org.name} kompaniyasining xushmuomala, professional va natijaga "
                f"yo'naltirilgan sotuv yordamchisisiz."
            ),
            greeting=(
                f"Assalomu alaykum! Men {org.name} AI yordamchisiman. "
                f"Mahsulot tanlash, narxlar va buyurtma bo'yicha yordam beraman."
            ),
        )
    )
    db.add(Widget(org_id=org.id, public_key=secrets.token_urlsafe(12)))
    await log_action(
        db,
        action="auth.register",
        org_id=org.id,
        user_id=user.id,
        entity="organization",
        meta={"email": email},
        ip=request.client.host if request.client else "",
    )
    return await _token_response(db, user, org, "owner")


@router.post("/login", response_model=TokenOut)
async def login(payload: LoginIn, db: AsyncSession = Depends(get_db)) -> TokenOut:
    user = (
        await db.execute(select(User).where(User.email == payload.email.lower().strip()))
    ).scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email yoki parol noto'g'ri")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Hisob bloklangan")

    membership = (
        await db.execute(
            select(Membership).where(Membership.user_id == user.id).order_by(Membership.created_at)
        )
    ).scalars().first()

    org = await db.get(Organization, membership.org_id) if membership else None
    role = membership.role if membership else ("super" if user.is_super_admin else "operator")
    return await _token_response(db, user, org, role)


@router.post("/refresh", response_model=TokenOut)
async def refresh(payload: RefreshIn, db: AsyncSession = Depends(get_db)) -> TokenOut:
    token_hash = hash_token(payload.refresh_token)
    stored = (
        await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    ).scalar_one_or_none()
    if stored is None or stored.revoked or stored.expires_at < utcnow():
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token yaroqsiz")

    user = await db.get(User, stored.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Foydalanuvchi topilmadi")

    org = await db.get(Organization, stored.org_id) if stored.org_id else None
    membership = await get_membership(db, user.id, org.id) if org else None
    if org and membership is None and not user.is_super_admin:
        org = None
    role = membership.role if membership else ("super" if user.is_super_admin else "operator")

    stored.revoked = True
    return await _token_response(db, user, org, role)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(payload: RefreshIn, db: AsyncSession = Depends(get_db)) -> None:
    stored = (
        await db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == hash_token(payload.refresh_token))
        )
    ).scalar_one_or_none()
    if stored is not None:
        stored.revoked = True
        await db.commit()


@router.get("/me", response_model=MeOut)
async def me(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MeOut:
    rows = (
        await db.execute(
            select(Membership, Organization)
            .join(Organization, Organization.id == Membership.org_id)
            .where(Membership.user_id == user.id)
            .order_by(Membership.created_at)
        )
    ).all()
    orgs = [OrgOut.model_validate(row[1]) for row in rows]
    if user.is_super_admin:
        every_org = (
            await db.execute(select(Organization).order_by(Organization.created_at))
        ).scalars()
        orgs = [OrgOut.model_validate(org) for org in every_org]
    payload = getattr(user, "_token_payload", {})
    active_org_id = payload.get("org")
    if active_org_id is None and orgs and not user.is_super_admin:
        active_org_id = orgs[0].id
    role = payload.get("role") if active_org_id == payload.get("org") else None
    if role is None:
        for membership, org in rows:
            if org.id == active_org_id:
                role = membership.role
    if role is None and user.is_super_admin and active_org_id is not None:
        role = "super"
    return MeOut(user=UserOut.model_validate(user), orgs=orgs, active_org_id=active_org_id, role=role)


@router.post("/switch-org", response_model=TokenOut)
async def switch_org(
    payload: SwitchOrgIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TokenOut:
    org = await db.get(Organization, payload.org_id)
    if org is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tashkilot topilmadi")
    membership = await get_membership(db, user.id, org.id)
    if membership is None and not user.is_super_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Bu tashkilotga ruxsat yo'q")
    role = membership.role if membership else "super"
    return await _token_response(db, user, org, role)


@router.post("/forgot-password")
async def forgot_password(payload: ForgotIn, db: AsyncSession = Depends(get_db)) -> dict:
    user = (
        await db.execute(select(User).where(User.email == payload.email.lower().strip()))
    ).scalar_one_or_none()
    response: dict = {"message": "Agar email tizimda mavjud bo'lsa, tiklash havolasi yuboriladi"}
    if user is not None:
        raw = secrets.token_urlsafe(32)
        db.add(
            PasswordReset(
                user_id=user.id,
                token_hash=hash_token(raw),
                expires_at=utcnow() + timedelta(minutes=30),
            )
        )
        await db.commit()
        if settings.dev_mode:
            response["reset_token"] = raw
        else:
            response["message"] = "Tiklash havolasi emailingizga yuborildi"
    return response


@router.post("/reset-password")
async def reset_password(payload: ResetIn, db: AsyncSession = Depends(get_db)) -> dict:
    stored = (
        await db.execute(
            select(PasswordReset).where(PasswordReset.token_hash == hash_token(payload.token))
        )
    ).scalar_one_or_none()
    if stored is None or stored.used or stored.expires_at < utcnow():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Tiklash tokeni yaroqsiz yoki muddati tugagan")

    user = await db.get(User, stored.user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Foydalanuvchi topilmadi")

    try:
        user.password_hash = hash_password(payload.password)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    stored.used = True
    await db.execute(delete(RefreshToken).where(RefreshToken.user_id == user.id))
    await db.commit()
    return {"message": "Parol yangilandi. Qaytadan kiring."}
