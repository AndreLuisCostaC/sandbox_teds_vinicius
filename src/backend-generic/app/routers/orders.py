from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from functools import wraps
from typing import ParamSpec, TypeVar

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models.cart import Cart
from app.models.inventory import Inventory
from app.models.inventory_movement import InventoryMovement
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.payment import Payment
from app.models.user import User
from app.schemas.order import (
    OrderCreateRequest,
    OrderListQuery,
    OrderListResponse,
    OrderResponse,
    OrderStatusUpdateRequest,
)
from app.security import get_current_user, get_current_user_optional, get_current_user_with_role
from app.services.payments import PaymentIntentError, PaymentService


router = APIRouter(prefix="/orders", tags=["orders"])
payment_service = PaymentService()
P = ParamSpec("P")
R = TypeVar("R")
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"paid", "cancelled"},
    "paid": {"shipped", "cancelled"},
    "shipped": set(),
    "cancelled": set(),
}


def transactional(func: Callable[P, R]) -> Callable[P, R]:
    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        db: Session | None = kwargs.get("db")
        if db is None:
            raise RuntimeError(
                "transactional function requires 'db' keyword argument"
            )
        try:
            result = func(*args, **kwargs)
            db.commit()
            return result
        except Exception:
            db.rollback()
            raise

    return wrapper


def _resolve_checkout_user(
    *,
    current_user: User | None,
    guest_token: str | None,
    cart: Cart,
) -> tuple[User | None, str]:
    """Resolve user for checkout. Returns (user_for_order, error_detail). Guest returns (None, '')."""
    if cart.user_id is not None:
        if current_user is None:
            return None, "Authentication required for this cart"
        if current_user.id != cart.user_id:
            return None, "Cart does not belong to current user"
        return current_user, ""
    if cart.guest_token is not None:
        if not guest_token or guest_token != cart.guest_token:
            return None, "Invalid guest token"
        return None, ""
    return None, "Cart ownership is not valid"


@transactional
def _create_order_transaction(
    *,
    payload: OrderCreateRequest,
    current_user: User | None,
    guest_token: str | None,
    db: Session,
) -> Order:
    cart = (
        db.execute(
            select(Cart)
            .where(Cart.id == payload.cart_id)
            .options(selectinload(Cart.items))
        )
        .scalar_one_or_none()
    )
    if cart is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cart not found",
        )
    checkout_user, err = _resolve_checkout_user(
        current_user=current_user,
        guest_token=guest_token,
        cart=cart,
    )
    if err:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=err,
        )
    if not cart.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cart is empty",
        )

    variant_ids = [item.product_variant_id for item in cart.items]
    inventory_rows = (
        db.execute(
            select(Inventory)
            .where(Inventory.product_variant_id.in_(variant_ids))
            .with_for_update()
        )
        .scalars()
        .all()
    )
    inventory_by_variant = {row.product_variant_id: row for row in inventory_rows}

    for cart_item in cart.items:
        inventory = inventory_by_variant.get(cart_item.product_variant_id)
        available = (
            0
            if inventory is None
            else max(inventory.quantity - inventory.reserved_quantity, 0)
        )
        if cart_item.quantity > available:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Insufficient stock for variant {cart_item.product_variant_id}. "
                    f"Requested={cart_item.quantity}, available={available}"
                ),
            )

    order_user_id = checkout_user.id if checkout_user else None
    order = Order(
        user_id=order_user_id,
        status="pending",
        currency=payload.currency.upper(),
        total_amount=Decimal("0"),
    )
    db.add(order)
    db.flush()

    total = Decimal("0")
    order_items: list[OrderItem] = []
    for cart_item in cart.items:
        variant = cart_item.product_variant
        if variant is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid cart variant reference",
            )
        unit_price = Decimal(variant.price)
        line_total = unit_price * cart_item.quantity
        total += line_total
        order_items.append(
            OrderItem(
                order_id=order.id,
                product_variant_id=cart_item.product_variant_id,
                quantity=cart_item.quantity,
                unit_price=unit_price,
                line_total=line_total,
            )
        )

    db.add_all(order_items)

    # Reserve stock atomically inside the same transaction.
    # This protects against race conditions before the order is shipped.
    inventory_movements: list[InventoryMovement] = []
    for cart_item in cart.items:
        reserve_update = db.execute(
            update(Inventory)
            .where(
                Inventory.product_variant_id == cart_item.product_variant_id,
                (Inventory.quantity - Inventory.reserved_quantity) >= cart_item.quantity,
            )
            .values(reserved_quantity=Inventory.reserved_quantity + cart_item.quantity)
        )
        if reserve_update.rowcount != 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Insufficient stock for variant {cart_item.product_variant_id}. "
                    "Could not complete inventory deduction."
                ),
            )
        inventory = inventory_by_variant.get(cart_item.product_variant_id)
        if inventory is not None:
            inventory_movements.append(
                InventoryMovement(
                    inventory_id=inventory.id,
                    product_variant_id=cart_item.product_variant_id,
                    user_id=order_user_id,
                    movement_type="order_reserved",
                    delta_quantity=0,
                    reason=f"Order #{order.id} reservation",
                )
            )
    if inventory_movements:
        db.add_all(inventory_movements)

    order.total_amount = total
    # Keep payment provider integration in a nested transaction/savepoint.
    # If payment intent creation fails we re-raise so the outer transaction
    # rolls back everything (order/items/inventory updates) atomically.
    with db.begin_nested():
        payment_intent = payment_service.create_payment_intent(
            amount=total,
            currency=payload.currency.upper(),
            order_id=order.id,
        )
        payment = Payment(
            order_id=order.id,
            provider=payment_intent.provider,
            status="pending",
            amount=total,
            external_id=payment_intent.external_id,
            client_secret=payment_intent.client_secret,
        )
        db.add(payment)
    db.flush()
    db.refresh(order)
    return (
        db.execute(
            select(Order)
            .where(Order.id == order.id)
            .options(selectinload(Order.items), selectinload(Order.payments))
        )
        .scalar_one()
    )


def _order_with_details_or_404(db: Session, order_id: int) -> Order:
    order = (
        db.execute(
            select(Order)
            .where(Order.id == order_id)
            .options(selectinload(Order.items), selectinload(Order.payments))
        )
        .scalar_one_or_none()
    )
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )
    return order


def _assert_order_role_access(current_user: User) -> None:
    role_name = current_user.role.name if current_user.role else None
    if role_name not in {"admin", "employee"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    payload: OrderCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Order:
    try:
        return _create_order_transaction(
            payload=payload,
            current_user=current_user,
            guest_token=None,
            db=db,
        )
    except PaymentIntentError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.post("/checkout", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def checkout(
    payload: OrderCreateRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
    guest_token: str | None = Header(default=None, alias="x-guest-token"),
) -> Order:
    """Create order from cart. Supports both authenticated and guest checkout."""
    try:
        return _create_order_transaction(
            payload=payload,
            current_user=current_user,
            guest_token=guest_token,
            db=db,
        )
    except PaymentIntentError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.get("", response_model=OrderListResponse)
async def list_orders(
    query: OrderListQuery = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OrderListResponse:
    _assert_order_role_access(current_user)

    filters = []
    if query.status:
        filters.append(Order.status == query.status)

    stmt = select(Order).options(
        selectinload(Order.items),
        selectinload(Order.payments),
    )
    count_stmt = select(func.count(Order.id))
    if filters:
        stmt = stmt.where(*filters)
        count_stmt = count_stmt.where(*filters)

    total = db.execute(count_stmt).scalar_one()
    items = (
        db.execute(
            stmt.order_by(Order.id.desc()).offset(query.offset).limit(query.limit)
        )
        .scalars()
        .all()
    )
    return OrderListResponse(
        items=items,
        total=total,
        limit=query.limit,
        offset=query.offset,
    )


@router.patch("/{order_id}", response_model=OrderResponse)
@transactional
def update_order_status(
    order_id: int,
    payload: OrderStatusUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_with_role("admin")),
) -> Order:
    _ = current_user
    order = _order_with_details_or_404(db, order_id)
    current_status = order.status
    next_status = payload.status

    if next_status == current_status:
        return order

    if next_status not in ALLOWED_TRANSITIONS.get(current_status, set()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status transition: {current_status} -> {next_status}",
        )

    if next_status == "cancelled":
        variant_ids = [item.product_variant_id for item in order.items]
        inventory_rows = (
            db.execute(
                select(Inventory)
                .where(Inventory.product_variant_id.in_(variant_ids))
                .with_for_update()
            )
            .scalars()
            .all()
        )
        inventory_by_variant = {row.product_variant_id: row for row in inventory_rows}
        movements: list[InventoryMovement] = []
        for item in order.items:
            inventory = inventory_by_variant.get(item.product_variant_id)
            if inventory is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Inventory not found for variant {item.product_variant_id}"
                    ),
                )
            release_update = db.execute(
                update(Inventory)
                .where(Inventory.id == inventory.id)
                .where(Inventory.reserved_quantity >= item.quantity)
                .values(
                    reserved_quantity=Inventory.reserved_quantity - item.quantity
                )
            )
            if release_update.rowcount != 1:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Could not release reserved inventory for "
                        f"variant {item.product_variant_id}"
                    ),
                )
            movements.append(
                InventoryMovement(
                    inventory_id=inventory.id,
                    product_variant_id=item.product_variant_id,
                    user_id=current_user.id,
                    movement_type="order_cancelled_release",
                    delta_quantity=0,
                    reason=f"Order #{order.id} cancelled (release reservation)",
                )
            )
        if movements:
            db.add_all(movements)
        for payment in order.payments:
            payment.status = "cancelled"

    if next_status == "paid":
        for payment in order.payments:
            if payment.status == "pending":
                payment.status = "confirmed"

    if next_status == "shipped":
        variant_ids = [item.product_variant_id for item in order.items]
        inventory_rows = (
            db.execute(
                select(Inventory)
                .where(Inventory.product_variant_id.in_(variant_ids))
                .with_for_update()
            )
            .scalars()
            .all()
        )
        inventory_by_variant = {
            row.product_variant_id: row for row in inventory_rows
        }
        shipped_movements: list[InventoryMovement] = []
        for item in order.items:
            inventory = inventory_by_variant.get(item.product_variant_id)
            if inventory is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Inventory not found for variant {item.product_variant_id}"
                    ),
                )
            finalize_update = db.execute(
                update(Inventory)
                .where(
                    Inventory.id == inventory.id,
                    Inventory.reserved_quantity >= item.quantity,
                    Inventory.quantity >= item.quantity,
                )
                .values(
                    quantity=Inventory.quantity - item.quantity,
                    reserved_quantity=Inventory.reserved_quantity - item.quantity,
                )
            )
            if finalize_update.rowcount != 1:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Could not finalize inventory shipment for "
                        f"variant {item.product_variant_id}"
                    ),
                )
            shipped_movements.append(
                InventoryMovement(
                    inventory_id=inventory.id,
                    product_variant_id=item.product_variant_id,
                    user_id=current_user.id,
                    movement_type="order_shipped_deduct",
                    delta_quantity=-item.quantity,
                    reason=f"Order #{order.id} shipped",
                )
            )
        if shipped_movements:
            db.add_all(shipped_movements)
        for payment in order.payments:
            if payment.status != "confirmed":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Order cannot be shipped without confirmed payment.",
                )

    order.status = next_status
    db.flush()
    db.refresh(order)
    return _order_with_details_or_404(db, order.id)
