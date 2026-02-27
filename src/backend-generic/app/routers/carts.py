from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models.cart import Cart
from app.models.cart_item import CartItem
from app.models.user import User
from app.schemas.cart import (
    CartCreateRequest,
    CartItemCreateRequest,
    CartItemResponse,
    CartItemUpdateRequest,
    CartResponse,
)
from app.security import decode_access_token
from app.services.stock import get_variant_or_404, validate_requested_quantity


router = APIRouter(prefix="/carts", tags=["carts"])


def _resolve_optional_user(request: Request, db: Session) -> User | None:
    auth_header = request.headers.get("authorization")
    if not auth_header:
        return None
    if not auth_header.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authorization header")

    token = auth_header.split(" ", 1)[1].strip()
    try:
        payload = decode_access_token(token)
        user_id = int(payload.get("sub"))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token") from exc

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token")
    return user


def _get_cart_or_404(db: Session, cart_id: int) -> Cart:
    cart = (
        db.execute(
            select(Cart)
            .where(Cart.id == cart_id)
            .options(selectinload(Cart.items))
        )
        .scalar_one_or_none()
    )
    if cart is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart not found")
    return cart


def _assert_cart_access(cart: Cart, current_user: User | None, guest_token: str | None) -> None:
    if cart.user_id is not None:
        if current_user is None or current_user.id != cart.user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied for this cart")
        return
    if cart.guest_token is not None:
        if guest_token != cart.guest_token:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid guest token")
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cart ownership is not valid")


@router.post("", response_model=CartResponse, status_code=status.HTTP_201_CREATED)
async def create_cart(
    payload: CartCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> Cart:
    current_user = _resolve_optional_user(request, db)

    if payload.user_id is not None and payload.guest_token is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide either user_id or guest_token, not both",
        )

    if current_user is not None:
        user_id = payload.user_id if payload.user_id is not None else current_user.id
        if user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot create cart for another user")
        guest_token = None
    else:
        if payload.user_id is not None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required for user cart")
        user_id = None
        guest_token = payload.guest_token or str(uuid4())

    cart = Cart(user_id=user_id, guest_token=guest_token, status="active")
    db.add(cart)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cart already exists for this guest token",
        ) from exc

    db.refresh(cart)
    return cart


@router.get("/{cart_id}", response_model=CartResponse)
async def get_cart(
    cart_id: int,
    request: Request,
    guest_token: str | None = Header(default=None, alias="x-guest-token"),
    db: Session = Depends(get_db),
) -> Cart:
    current_user = _resolve_optional_user(request, db)
    cart = _get_cart_or_404(db, cart_id)
    _assert_cart_access(cart, current_user, guest_token)
    return cart


@router.post("/{cart_id}/items", response_model=CartItemResponse, status_code=status.HTTP_201_CREATED)
async def add_cart_item(
    cart_id: int,
    payload: CartItemCreateRequest,
    request: Request,
    guest_token: str | None = Header(default=None, alias="x-guest-token"),
    db: Session = Depends(get_db),
) -> CartItem:
    current_user = _resolve_optional_user(request, db)
    cart = _get_cart_or_404(db, cart_id)
    _assert_cart_access(cart, current_user, guest_token)

    get_variant_or_404(db, payload.product_variant_id)
    existing = (
        db.execute(
            select(CartItem).where(
                CartItem.cart_id == cart.id,
                CartItem.product_variant_id == payload.product_variant_id,
            )
        )
        .scalar_one_or_none()
    )

    final_quantity = payload.quantity if existing is None else existing.quantity + payload.quantity
    validate_requested_quantity(db, payload.product_variant_id, final_quantity)

    if existing is None:
        item = CartItem(
            cart_id=cart.id,
            product_variant_id=payload.product_variant_id,
            quantity=payload.quantity,
        )
        db.add(item)
    else:
        existing.quantity = final_quantity
        item = existing

    db.commit()
    db.refresh(item)
    return item


@router.patch("/{cart_id}/items/{item_id}", response_model=CartItemResponse)
async def update_cart_item(
    cart_id: int,
    item_id: int,
    payload: CartItemUpdateRequest,
    request: Request,
    guest_token: str | None = Header(default=None, alias="x-guest-token"),
    db: Session = Depends(get_db),
) -> CartItem:
    current_user = _resolve_optional_user(request, db)
    cart = _get_cart_or_404(db, cart_id)
    _assert_cart_access(cart, current_user, guest_token)

    item = db.get(CartItem, item_id)
    if item is None or item.cart_id != cart.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart item not found")

    validate_requested_quantity(db, item.product_variant_id, payload.quantity)
    item.quantity = payload.quantity
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{cart_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cart_item(
    cart_id: int,
    item_id: int,
    request: Request,
    guest_token: str | None = Header(default=None, alias="x-guest-token"),
    db: Session = Depends(get_db),
) -> Response:
    current_user = _resolve_optional_user(request, db)
    cart = _get_cart_or_404(db, cart_id)
    _assert_cart_access(cart, current_user, guest_token)

    item = db.get(CartItem, item_id)
    if item is None or item.cart_id != cart.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart item not found")

    db.delete(item)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
