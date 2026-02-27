from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CartCreateRequest(BaseModel):
    user_id: int | None = Field(default=None, gt=0)
    guest_token: str | None = Field(default=None, min_length=8, max_length=120)


class CartItemCreateRequest(BaseModel):
    product_variant_id: int = Field(gt=0)
    quantity: int = Field(gt=0, le=999)


class CartItemUpdateRequest(BaseModel):
    quantity: int = Field(gt=0, le=999)


class CartItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cart_id: int
    product_variant_id: int
    quantity: int
    created_at: datetime
    updated_at: datetime


class CartResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int | None
    guest_token: str | None
    status: str
    created_at: datetime
    updated_at: datetime
    items: list[CartItemResponse] = []
