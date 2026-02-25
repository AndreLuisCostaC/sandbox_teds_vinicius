from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.category import Category
from app.models.product import Product
from app.models.user import User
from app.schemas.product import (
    ProductCreate,
    ProductListQuery,
    ProductListResponse,
    ProductResponse,
    ProductUpdate,
)
from app.security import get_current_user_with_role


router = APIRouter(prefix="/products", tags=["products"])


def _get_product_or_404(db: Session, product_id: int) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


def _ensure_category_exists(db: Session, category_id: int) -> None:
    category = db.execute(select(Category).where(Category.id == category_id)).scalar_one_or_none()
    if category is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid category_id")


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    payload: ProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_with_role("admin")),
) -> Product:
    _ = current_user
    _ensure_category_exists(db, payload.category_id)
    product = Product(
        name=payload.name,
        description=payload.description,
        price=payload.price,
        category_id=payload.category_id,
        is_active=payload.status == "active",
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.get("", response_model=ProductListResponse)
async def list_products(
    query: ProductListQuery = Depends(),
    db: Session = Depends(get_db),
) -> ProductListResponse:
    filters = []

    if query.category is not None:
        filters.append(Product.category_id == query.category)
    if query.price_min is not None:
        filters.append(Product.price >= query.price_min)
    if query.price_max is not None:
        filters.append(Product.price <= query.price_max)
    if query.status is not None:
        filters.append(Product.is_active == (query.status == "active"))

    base_stmt = select(Product)
    count_stmt = select(func.count(Product.id))
    if filters:
        base_stmt = base_stmt.where(*filters)
        count_stmt = count_stmt.where(*filters)

    total = db.execute(count_stmt).scalar_one()
    items = (
        db.execute(base_stmt.order_by(Product.id.asc()).offset(query.offset).limit(query.limit))
        .scalars()
        .all()
    )

    return ProductListResponse(items=items, total=total, limit=query.limit, offset=query.offset)


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(product_id: int, db: Session = Depends(get_db)) -> Product:
    return _get_product_or_404(db, product_id)


@router.patch("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: int,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_with_role("admin")),
) -> Product:
    _ = current_user
    product = _get_product_or_404(db, product_id)

    update_data = payload.model_dump(exclude_unset=True)
    if "category_id" in update_data:
        _ensure_category_exists(db, int(update_data["category_id"]))
    if "status" in update_data:
        update_data["is_active"] = update_data.pop("status") == "active"

    for field, value in update_data.items():
        setattr(product, field, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid update") from exc

    db.refresh(product)
    return product


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_with_role("admin")),
) -> Response:
    _ = current_user
    product = _get_product_or_404(db, product_id)
    db.delete(product)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

