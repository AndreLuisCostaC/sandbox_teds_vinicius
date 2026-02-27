from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.inventory import Inventory
from app.models.product_variant import ProductVariant


def get_variant_or_404(db: Session, product_variant_id: int) -> ProductVariant:
    variant = db.get(ProductVariant, product_variant_id)
    if variant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product variant not found")
    return variant


def get_available_stock(db: Session, product_variant_id: int) -> int:
    inventory = (
        db.query(Inventory).filter(Inventory.product_variant_id == product_variant_id).one_or_none()
    )
    if inventory is None:
        return 0
    return max(inventory.quantity - inventory.reserved_quantity, 0)


def validate_requested_quantity(
    db: Session,
    product_variant_id: int,
    requested_quantity: int,
) -> None:
    available = get_available_stock(db, product_variant_id)
    if requested_quantity > available:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Insufficient stock for variant {product_variant_id}. "
                f"Requested={requested_quantity}, available={available}"
            ),
        )
