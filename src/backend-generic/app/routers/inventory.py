from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.inventory import Inventory
from app.models.inventory_movement import InventoryMovement
from app.models.user import User
from app.schemas.inventory import (
    InventoryMovementListQuery,
    InventoryMovementListResponse,
    InventoryStockItem,
    InventoryStockListResponse,
    InventoryStockUpdateRequest,
)
from app.security import get_current_user
from app.services.stock import get_variant_or_404


router = APIRouter(prefix="/inventory", tags=["inventory"])


def _assert_inventory_role_access(current_user: User) -> None:
    role_name = current_user.role.name if current_user.role else None
    if role_name not in {"admin", "employee"}:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )


@router.get("/movements", response_model=InventoryMovementListResponse)
async def list_inventory_movements(
    query: InventoryMovementListQuery = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InventoryMovementListResponse:
    _assert_inventory_role_access(current_user)

    filters = []
    if query.variant_id is not None:
        filters.append(InventoryMovement.product_variant_id == query.variant_id)
    if query.movement_type:
        filters.append(InventoryMovement.movement_type == query.movement_type)

    stmt = select(InventoryMovement)
    count_stmt = select(func.count(InventoryMovement.id))
    if filters:
        stmt = stmt.where(*filters)
        count_stmt = count_stmt.where(*filters)

    total = db.execute(count_stmt).scalar_one()
    items = (
        db.execute(
            stmt.order_by(InventoryMovement.id.desc())
            .offset(query.offset)
            .limit(query.limit)
        )
        .scalars()
        .all()
    )
    return InventoryMovementListResponse(
        items=items,
        total=total,
        limit=query.limit,
        offset=query.offset,
    )


@router.get("/stock", response_model=InventoryStockListResponse)
async def list_inventory_stock(
    variant_ids: str = Query(min_length=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InventoryStockListResponse:
    _assert_inventory_role_access(current_user)
    parsed_ids = []
    for raw in variant_ids.split(","):
        raw = raw.strip()
        if not raw:
            continue
        parsed_ids.append(int(raw))

    if not parsed_ids:
        return InventoryStockListResponse(items=[])

    inventories = db.execute(
        select(Inventory).where(Inventory.product_variant_id.in_(parsed_ids))
    ).scalars().all()
    items = [
        InventoryStockItem(
            product_variant_id=inventory.product_variant_id,
            quantity=inventory.quantity,
            reserved_quantity=inventory.reserved_quantity,
            available_stock=max(
                inventory.quantity - inventory.reserved_quantity,
                0,
            ),
        )
        for inventory in inventories
    ]
    return InventoryStockListResponse(items=items)


@router.patch("/stock/{variant_id}", response_model=InventoryStockItem)
async def update_inventory_stock(
    variant_id: int,
    payload: InventoryStockUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InventoryStockItem:
    _assert_inventory_role_access(current_user)
    _ = get_variant_or_404(db, variant_id)

    inventory = (
        db.execute(
            select(Inventory).where(Inventory.product_variant_id == variant_id)
        )
        .scalar_one_or_none()
    )
    if inventory is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inventory not found for this variant",
        )

    old_quantity = inventory.quantity
    new_quantity = payload.quantity
    if new_quantity < inventory.reserved_quantity:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Quantity cannot be less than reserved quantity",
        )

    delta = new_quantity - old_quantity
    inventory.quantity = new_quantity
    db.add(
        InventoryMovement(
            inventory_id=inventory.id,
            product_variant_id=variant_id,
            user_id=current_user.id,
            movement_type="adjustment",
            delta_quantity=delta,
            reason="Manual stock adjustment",
        )
    )
    db.commit()
    db.refresh(inventory)
    return InventoryStockItem(
        product_variant_id=inventory.product_variant_id,
        quantity=inventory.quantity,
        reserved_quantity=inventory.reserved_quantity,
        available_stock=max(inventory.quantity - inventory.reserved_quantity, 0),
    )
