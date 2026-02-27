from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models.category import Category
from app.models.inventory import Inventory
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.models.user import User
from app.schemas.product import (
    ProductCreate,
    ProductListQuery,
    ProductListResponse,
    ProductResponse,
    ProductUpdate,
)
from app.security import get_current_user_with_role
from app.security_hardening import sanitize_text
from app.services.stock import get_available_stock, get_variant_or_404
from app.services.vector_store import ProductVectorStoreService


router = APIRouter(prefix="/products", tags=["products"])
vector_store = ProductVectorStoreService()


def _get_product_or_404(db: Session, product_id: int) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )
    return product


def _ensure_category_exists(db: Session, category_id: int) -> None:
    category = db.execute(
        select(Category).where(Category.id == category_id)
    ).scalar_one_or_none()
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid category_id",
        )


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    payload: ProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_with_role("admin")),
) -> Product:
    _ = current_user
    _ensure_category_exists(db, payload.category_id)
    name = sanitize_text(payload.name)
    if not name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="name cannot be empty",
        )
    product = Product(
        name=name,
        description=sanitize_text(payload.description),
        price=payload.price,
        category_id=payload.category_id,
        is_active=payload.status == "active",
    )
    db.add(product)
    db.flush()
    variant = ProductVariant(
        product_id=product.id,
        sku=f"PROD-{product.id}-default",
        name=name,
        price=payload.price,
        is_active=payload.status == "active",
    )
    db.add(variant)
    db.flush()
    db.add(Inventory(product_variant_id=variant.id, quantity=0, reserved_quantity=0))
    db.commit()
    db.refresh(product)
    db.refresh(product, ["variants"])
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
        db.execute(
            base_stmt.options(selectinload(Product.variants))
            .order_by(Product.id.asc())
            .offset(query.offset)
            .limit(query.limit)
        )
        .scalars()
        .all()
    )

    return ProductListResponse(
        items=items,
        total=total,
        limit=query.limit,
        offset=query.offset,
    )


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(product_id: int, db: Session = Depends(get_db)) -> Product:
    product = (
        db.execute(
            select(Product)
            .where(Product.id == product_id)
            .options(selectinload(Product.variants))
        )
        .scalar_one_or_none()
    )
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )
    return product


@router.get("/{product_variant_id}/stock")
async def get_product_variant_stock(
    product_variant_id: int,
    db: Session = Depends(get_db),
) -> dict[str, int]:
    _ = get_variant_or_404(db, product_variant_id)
    available = get_available_stock(db, product_variant_id)
    return {
        "product_variant_id": product_variant_id,
        "available_stock": available,
    }


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
    if "name" in update_data:
        sanitized_name = sanitize_text(str(update_data["name"]))
        if not sanitized_name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="name cannot be empty",
            )
        update_data["name"] = sanitized_name
    if "description" in update_data:
        update_data["description"] = sanitize_text(update_data["description"])

    for field, value in update_data.items():
        setattr(product, field, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid update",
        ) from exc

    db.refresh(product)
    try:
        vector_store.reindex_product(product)
    except Exception:  # noqa: BLE001
        # Index sync failures should not block product updates.
        pass
    return product


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_with_role("admin")),
) -> Response:
    _ = current_user
    product = _get_product_or_404(db, product_id)
    try:
        vector_store.delete_product(product.id)
    except Exception:  # noqa: BLE001
        # Index cleanup failures should not block product deletion.
        pass
    db.delete(product)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{product_id}/index-vector")
async def index_product_vector(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_with_role("admin")),
) -> dict[str, str]:
    _ = current_user
    product = _get_product_or_404(db, product_id)
    try:
        vector_id = vector_store.index_product(product)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to index product vector: {exc}",
        ) from exc

    return {
        "status": "indexed",
        "product_id": str(product_id),
        "vector_id": vector_id,
    }


@router.put("/{product_id}/index-vector")
async def reindex_product_vector(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_with_role("admin")),
) -> dict[str, str]:
    _ = current_user
    product = _get_product_or_404(db, product_id)
    try:
        vector_id = vector_store.reindex_product(product)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reindex product vector: {exc}",
        ) from exc

    return {
        "status": "reindexed",
        "product_id": str(product_id),
        "vector_id": vector_id,
    }


@router.delete("/{product_id}/index-vector")
async def delete_product_vector(
    product_id: int,
    current_user: User = Depends(get_current_user_with_role("admin")),
) -> dict[str, str]:
    _ = current_user
    try:
        vector_id = vector_store.delete_product(product_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete product vector: {exc}",
        ) from exc

    return {
        "status": "deleted",
        "product_id": str(product_id),
        "vector_id": vector_id,
    }
