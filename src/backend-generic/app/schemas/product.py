from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ProductStatus(str, Enum):
    active = "active"
    inactive = "inactive"


class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    category_id: int = Field(gt=0)
    status: ProductStatus = ProductStatus.active

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("name cannot be empty")
        return stripped


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    price: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    category_id: int | None = Field(default=None, gt=0)
    status: ProductStatus | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        stripped = value.strip()
        if not stripped:
            raise ValueError("name cannot be empty")
        return stripped


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    price: Decimal
    category_id: int
    is_active: bool
    status: ProductStatus
    variant_id: int | None = None

    @model_validator(mode="before")
    @classmethod
    def derive_status(cls, value: object) -> object:
        if isinstance(value, dict):
            if "status" not in value and "is_active" in value:
                value["status"] = ProductStatus.active if value["is_active"] else ProductStatus.inactive
            return value

        is_active = getattr(value, "is_active", None)
        if is_active is not None and not hasattr(value, "status"):
            variants = getattr(value, "variants", None) or []
            first_variant = next((v for v in variants if getattr(v, "is_active", True)), None)
            first_variant = first_variant or (variants[0] if variants else None)
            variant_id = first_variant.id if first_variant else None
            return {
                "id": getattr(value, "id"),
                "name": getattr(value, "name"),
                "description": getattr(value, "description"),
                "price": getattr(value, "price"),
                "category_id": getattr(value, "category_id"),
                "is_active": is_active,
                "status": ProductStatus.active if is_active else ProductStatus.inactive,
                "variant_id": variant_id,
            }
        return value


class ProductListQuery(BaseModel):
    category: int | None = Field(default=None, gt=0)
    price_min: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    price_max: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    status: ProductStatus | None = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_price_range(self) -> Self:
        if self.price_min is not None and self.price_max is not None and self.price_min > self.price_max:
            raise ValueError("price_min must be less than or equal to price_max")
        return self


class ProductListResponse(BaseModel):
    items: list[ProductResponse]
    total: int
    limit: int
    offset: int

