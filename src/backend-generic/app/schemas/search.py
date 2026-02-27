from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.product import ProductResponse, ProductStatus


class SearchResultItem(BaseModel):
    product: ProductResponse
    score: float = Field(ge=0)
    matched_by: str


class HybridSearchResponse(BaseModel):
    query: str
    total: int
    limit: int
    offset: int
    items: list[SearchResultItem]


class SearchQueryParams(BaseModel):
    query: str = Field(min_length=1, max_length=255)
    category_id: int | None = Field(default=None, gt=0)
    status: ProductStatus | None = None
    price_min: float | None = Field(default=None, ge=0)
    price_max: float | None = Field(default=None, ge=0)
    limit: int = Field(default=20, ge=1, le=20)
    offset: int = Field(default=0, ge=0)
