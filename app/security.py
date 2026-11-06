from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import Membership, Organization, RefreshToken, User, utcnow

ALGORITHM = "HS256"
bearer_scheme = HTTPBearer(auto_error=False)

ROLE_RANK = {"operator": 1, "manager": 2, "owner": 3, "super": 4}


def hash_password(password: str) -> str:
    if len(password.encode("utf-8")) > 72:
        raise ValueError("Parol 72 baytdan oshmasligi kerak")
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except (ValueError, TypeError):
        return False


def _create_token(user_id: str, org_id: str | None, role: str, is_super: bool, minutes: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "org": org_id,
        "role": role,
        "sa": is_super,
        "typ": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=minutes)).timestamp()),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def create_access_token(user: User, org_id: str | None, role: str) -> str:
    return _create_token(user.id, org_id, role, user.is_super_admin, settings.access_token_minutes)


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token muddati tugagan") from exc
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token yaroqsiz") from exc
    if payload.get("typ") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token turi noto'g'ri")
    return payload


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


async def issue_refresh_token(db: AsyncSession, user: User, org_id: str | None) -> str:
    raw = secrets.token_urlsafe(48)
    db.add(
        RefreshToken(
            user_id=user.id,
            org_id=org_id,
            token_hash=hash_token(raw),
            expires_at=utcnow() + timedelta(days=settings.refresh_token_days),
        )
    )
    await db.flush()
    return raw


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Avtorizatsiya talab qilinadi")
    payload = decode_token(credentials.credentials)
    user = await db.get(User, payload["sub"])
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Foydalanuvchi topilmadi")
    user._token_payload = payload  # type: ignore[attr-defined]
    return user


async def get_membership(db: AsyncSession, user_id: str, org_id: str) -> Membership | None:
    result = await db.execute(
        select(Membership).where(Membership.user_id == user_id, Membership.org_id == org_id)
    )
    return result.scalar_one_or_none()


class Context:
    """Authenticated request context: user + active organization + role."""

    def __init__(self, user: User, org: Organization, role: str, membership: Membership | None):
        self.user = user
        self.org = org
        self.role = role
        self.membership = membership

    @property
    def org_id(self) -> str:
        return self.org.id


async def get_context(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    x_org_id: str | None = Header(default=None, alias="X-Org-Id"),
) -> Context:
    payload = getattr(user, "_token_payload", {})
    org_id = x_org_id or payload.get("org")

    if not org_id:
        result = await db.execute(
            select(Membership).where(Membership.user_id == user.id).order_by(Membership.created_at)
        )
        membership = result.scalars().first()
        if membership is None and not user.is_super_admin:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Tashkilotga a'zo emassiz")
        org_id = membership.org_id if membership else None

    if not org_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Tashkilot tanlanmagan")

    org = await db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tashkilot topilmadi")

    membership = await get_membership(db, user.id, org_id)
    if membership is None:
        if user.is_super_admin:
            return Context(user, org, "super", None)
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Bu tashkilotga ruxsat yo'q")

    return Context(user, org, membership.role, membership)


def require_roles(*roles: str):
    """Allow the listed roles and any role above them in the hierarchy."""
    async def guard(ctx: Context = Depends(get_context)) -> Context:
        if ctx.role == "super":
            return ctx
        required = min(ROLE_RANK.get(r, 99) for r in roles)
        if ROLE_RANK.get(ctx.role, 0) < required:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Bu amal uchun ruxsat yo'q")
        return ctx

    return guard


async def require_super_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_super_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Super admin huquqi kerak")
    return user
