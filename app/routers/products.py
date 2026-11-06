from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Product
from app.schemas import ProductIn, ProductOut, ProductUpdateIn
from app.security import Context, get_context, require_roles
from app.services.audit import log_action

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=list[ProductOut])
async def list_products(
    q: str | None = Query(default=None, max_length=120),
    category: str | None = Query(default=None, max_length=80),
    limit: int = Query(default=200, ge=1, le=500),
    ctx: Context = Depends(get_context),
    db: AsyncSession = Depends(get_db),
) -> list[ProductOut]:
    stmt = select(Product).where(Product.org_id == ctx.org_id)
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Product.name.ilike(pattern),
                Product.description.ilike(pattern),
                Product.sku.ilike(pattern),
                Product.category.ilike(pattern),
            )
        )
    if category:
        stmt = stmt.where(Product.category == category)
    rows = (
        await db.execute(stmt.order_by(Product.created_at.desc()).limit(limit))
    ).scalars().all()
    return [ProductOut.model_validate(row) for row in rows]


@router.post("", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
async def create_product(
    payload: ProductIn,
    ctx: Context = Depends(require_roles("manager")),
    db: AsyncSession = Depends(get_db),
) -> ProductOut:
    product = Product(org_id=ctx.org_id, **payload.model_dump())
    db.add(product)
    await db.flush()
    await log_action(
        db, action="product.create", org_id=ctx.org_id, user_id=ctx.user.id,
        entity="product", meta={"product_id": product.id, "name": product.name},
    )
    await db.commit()
    return ProductOut.model_validate(product)


@router.patch("/{product_id}", response_model=ProductOut)
async def update_product(
    product_id: str,
    payload: ProductUpdateIn,
    ctx: Context = Depends(require_roles("manager")),
    db: AsyncSession = Depends(get_db),
) -> ProductOut:
    product = await db.get(Product, product_id)
    if product is None or product.org_id != ctx.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Mahsulot topilmadi")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(product, field, value)
    await log_action(
        db, action="product.update", org_id=ctx.org_id, user_id=ctx.user.id,
        entity="product", meta={"product_id": product.id},
    )
    await db.commit()
    return ProductOut.model_validate(product)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: str,
    ctx: Context = Depends(require_roles("manager")),
    db: AsyncSession = Depends(get_db),
) -> None:
    product = await db.get(Product, product_id)
    if product is None or product.org_id != ctx.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Mahsulot topilmadi")
    await db.delete(product)
    await log_action(
        db, action="product.delete", org_id=ctx.org_id, user_id=ctx.user.id,
        entity="product", meta={"product_id": product_id, "name": product.name},
    )
    await db.commit()
