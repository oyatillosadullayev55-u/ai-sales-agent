from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Order, Product
from app.schemas import OrderIn, OrderOut, OrderStatusIn
from app.security import Context, get_context, require_roles
from app.services.audit import log_action
from app.services.orders import OrderError, build_items, create_order

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("", response_model=list[OrderOut])
async def list_orders(
    status_filter: str | None = Query(default=None, alias="status"),
    q: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=100, ge=1, le=500),
    ctx: Context = Depends(get_context),
    db: AsyncSession = Depends(get_db),
) -> list[OrderOut]:
    stmt = select(Order).where(Order.org_id == ctx.org_id)
    if status_filter:
        stmt = stmt.where(Order.status == status_filter)
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Order.customer_name.ilike(pattern),
                Order.customer_phone.ilike(pattern),
                Order.number.ilike(pattern),
            )
        )
    rows = (
        await db.execute(stmt.order_by(Order.created_at.desc()).limit(limit))
    ).scalars().all()
    return [OrderOut.model_validate(row) for row in rows]


@router.post("", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def create_manual_order(
    payload: OrderIn,
    ctx: Context = Depends(require_roles("operator")),
    db: AsyncSession = Depends(get_db),
) -> OrderOut:
    try:
        items = await build_items(db, ctx.org_id, [item.model_dump() for item in payload.items])
        order = await create_order(
            db,
            ctx.org,
            customer_name=payload.customer_name,
            customer_phone=payload.customer_phone,
            items=items,
            source="dashboard",
            note=payload.note,
        )
    except OrderError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    await log_action(
        db, action="order.create", org_id=ctx.org_id, user_id=ctx.user.id,
        entity="order", meta={"order_id": order.id, "number": order.number, "total": order.total},
    )
    await db.commit()
    return OrderOut.model_validate(order)


@router.get("/{order_id}", response_model=OrderOut)
async def get_order(
    order_id: str, ctx: Context = Depends(get_context), db: AsyncSession = Depends(get_db)
) -> OrderOut:
    order = await db.get(Order, order_id)
    if order is None or order.org_id != ctx.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Buyurtma topilmadi")
    return OrderOut.model_validate(order)


@router.patch("/{order_id}/status", response_model=OrderOut)
async def update_status(
    order_id: str,
    payload: OrderStatusIn,
    ctx: Context = Depends(require_roles("operator")),
    db: AsyncSession = Depends(get_db),
) -> OrderOut:
    order = await db.get(Order, order_id)
    if order is None or order.org_id != ctx.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Buyurtma topilmadi")

    if payload.status == "cancelled" and order.status != "cancelled":
        for item in order.items or []:
            product = await db.get(Product, item.get("product_id"))
            if product is not None and product.org_id == ctx.org_id:
                product.stock_qty += int(item.get("qty", 0))

    order.status = payload.status
    await log_action(
        db, action="order.status", org_id=ctx.org_id, user_id=ctx.user.id,
        entity="order", meta={"order_id": order.id, "status": payload.status},
    )
    await db.commit()
    return OrderOut.model_validate(order)
