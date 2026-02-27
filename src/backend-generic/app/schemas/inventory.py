from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class InventoryMovementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    inventory_id: int
    product_variant_id: int
    user_id: int | None
    movement_type: str
    delta_quantity: int
    reason: str | None
    created_at: datetime
    updated_at: datetime


class InventoryMovementListResponse(BaseModel):
    items: list[InventoryMovementResponse]
    total: int
    limit: int
    offset: int


class InventoryMovementListQuery(BaseModel):
    variant_id: int | None = Field(default=None, gt=0)
    movement_type: str | None = None
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class InventoryStockItem(BaseModel):
    product_variant_id: int
    quantity: int
    reserved_quantity: int
    available_stock: int


class InventoryStockListResponse(BaseModel):
    items: list[InventoryStockItem]


class InventoryStockUpdateRequest(BaseModel):
    quantity: int = Field(ge=0, le=999_999)
