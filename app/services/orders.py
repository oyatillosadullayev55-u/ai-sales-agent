from __future__ import annotations

import secrets
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Order, Organization, Product


class OrderError(ValueError):
    pass


async def build_items(
    db: AsyncSession, org_id: str, inputs: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    if not inputs:
        raise OrderError("Buyurtma uchun kamida bitta mahsulot kerak")

    items: list[dict[str, Any]] = []
    for raw in inputs:
        product_id = str(raw.get("product_id") or "")
        qty = int(raw.get("qty") or 1)
        if qty < 1:
            raise OrderError("Miqdor noto'g'ri")
        product = await db.get(Product, product_id)
        if product is None or product.org_id != org_id:
            raise OrderError("Mahsulot topilmadi")
        if not product.in_stock or product.stock_qty < qty:
            raise OrderError(f"{product.name} omborda yetarli emas")
        items.append(
            {
                "product_id": product.id,
                "name": product.name,
                "price": product.price,
                "qty": qty,
                "currency": product.currency,
            }
        )
    return items


def generate_number(org: Organization) -> str:
    prefix = "".join(ch for ch in org.slug.upper() if ch.isalnum())[:3] or "ORD"
    return f"{prefix}-{datetime.now():%y%m%d}-{secrets.token_hex(2).upper()}"


async def create_order(
    db: AsyncSession,
    org: Organization,
    *,
    customer_name: str,
    customer_phone: str,
    items: list[dict[str, Any]],
    source: str = "ai",
    conversation_id: str | None = None,
    note: str = "",
) -> Order:
    if not customer_name.strip():
        raise OrderError("Mijoz ismi kerak")
    if not customer_phone.strip():
        raise OrderError("Telefon raqami kerak")

    total = sum(float(item["price"]) * int(item["qty"]) for item in items)
    order = Order(
        org_id=org.id,
        number=generate_number(org),
        customer_name=customer_name.strip()[:160],
        customer_phone=customer_phone.strip()[:40],
        items=items,
        total=round(total, 2),
        status="pending",
        source=source,
        note=note[:1000],
        conversation_id=conversation_id,
    )
    db.add(order)
    await db.flush()

    for item in items:
        product = await db.get(Product, item["product_id"])
        if product is not None:
            product.stock_qty = max(0, product.stock_qty - int(item["qty"]))
    await db.flush()
    return order


async def org_revenue(db: AsyncSession, org_id: str) -> float:
    value = await db.scalar(
        select(func.coalesce(func.sum(Order.total), 0)).where(
            Order.org_id == org_id, Order.status != "cancelled"
        )
    )
    return float(value or 0)
