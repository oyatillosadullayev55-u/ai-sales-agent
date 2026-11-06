from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import PLANS
from app.database import get_db
from app.models import Organization, Payment, utcnow
from app.schemas import BillingOut, PaymentOut, SubscribeIn
from app.security import Context, get_context, require_roles
from app.services.audit import log_action
from app.services.limits import usage_snapshot

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("", response_model=BillingOut)
async def get_billing(
    ctx: Context = Depends(get_context), db: AsyncSession = Depends(get_db)
) -> BillingOut:
    payments = (
        await db.execute(
            select(Payment)
            .where(Payment.org_id == ctx.org_id)
            .order_by(Payment.created_at.desc())
            .limit(50)
        )
    ).scalars().all()
    return BillingOut(
        plan=ctx.org.plan,
        plan_expires_at=ctx.org.plan_expires_at,
        plans=PLANS,
        usage=await usage_snapshot(db, ctx.org),
        payments=[PaymentOut.model_validate(payment) for payment in payments],
    )


@router.post("/subscribe", response_model=PaymentOut, status_code=status.HTTP_201_CREATED)
async def subscribe(
    payload: SubscribeIn,
    ctx: Context = Depends(require_roles("owner")),
    db: AsyncSession = Depends(get_db),
) -> PaymentOut:
    plan = PLANS[payload.plan]
    org = await db.get(Organization, ctx.org_id)
    if org is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tashkilot topilmadi")

    amount = float(plan["price"]) * payload.months
    payment = Payment(
        org_id=org.id,
        plan=payload.plan,
        months=payload.months,
        amount=amount,
        status="paid",
        provider="manual",
        created_by=ctx.user.id,
    )
    db.add(payment)

    now = utcnow()
    base = org.plan_expires_at if org.plan_expires_at and org.plan_expires_at > now else now
    org.plan = payload.plan
    org.plan_expires_at = base + timedelta(days=30 * payload.months)

    await log_action(
        db, action="billing.subscribe", org_id=org.id, user_id=ctx.user.id,
        entity="payment", meta={"plan": payload.plan, "months": payload.months, "amount": amount},
    )
    await db.commit()
    return PaymentOut.model_validate(payment)


@router.get("/payments", response_model=list[PaymentOut])
async def list_payments(
    ctx: Context = Depends(get_context), db: AsyncSession = Depends(get_db)
) -> list[PaymentOut]:
    rows = (
        await db.execute(
            select(Payment)
            .where(Payment.org_id == ctx.org_id)
            .order_by(Payment.created_at.desc())
            .limit(100)
        )
    ).scalars().all()
    return [PaymentOut.model_validate(row) for row in rows]
