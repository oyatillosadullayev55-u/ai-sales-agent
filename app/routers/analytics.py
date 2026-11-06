from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import AuditLog
from app.schemas import AnalyticsOut
from app.security import Context, get_context, require_roles
from app.services import analytics

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview", response_model=AnalyticsOut)
async def overview(
    days: int = Query(default=30, ge=1, le=365),
    ctx: Context = Depends(get_context),
    db: AsyncSession = Depends(get_db),
) -> AnalyticsOut:
    data = await analytics.overview(db, ctx.org_id, days)
    return AnalyticsOut(**data)


@router.get("/audit-logs")
async def audit_logs(
    limit: int = Query(default=50, ge=1, le=300),
    ctx: Context = Depends(require_roles("manager")),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    rows = (
        await db.execute(
            select(AuditLog)
            .where(AuditLog.org_id == ctx.org_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return [
        {
            "id": row.id,
            "action": row.action,
            "entity": row.entity,
            "user_id": row.user_id,
            "meta": row.meta,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]
