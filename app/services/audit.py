from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog


async def log_action(
    db: AsyncSession,
    *,
    action: str,
    org_id: str | None = None,
    user_id: str | None = None,
    entity: str = "",
    meta: dict[str, Any] | None = None,
    ip: str = "",
) -> None:
    db.add(
        AuditLog(
            org_id=org_id,
            user_id=user_id,
            action=action,
            entity=entity,
            meta=meta or {},
            ip=ip[:64],
        )
    )
