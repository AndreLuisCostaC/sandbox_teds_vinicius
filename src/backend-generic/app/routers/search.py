from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from fastapi import APIRouter, Depends
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models.product import Product
from app.schemas.search import HybridSearchResponse, SearchQueryParams, SearchResultItem
from app.services.vector_store import ProductVectorStoreService


router = APIRouter(prefix="/search", tags=["search"])
vector_store = ProductVectorStoreService()


@dataclass
class _ScoreBucket:
    semantic: float = 0.0
    keyword: float = 0.0


def _keyword_search(
    db: Session,
    params: SearchQueryParams,
    candidate_limit: int,
) -> list[tuple[int, float]]:
    tsv = func.to_tsvector(
        "english",
        func.concat(func.coalesce(Product.name, ""), " ", func.coalesce(Product.description, "")),
    )
    tsq = func.plainto_tsquery("english", params.query)
    rank = func.ts_rank_cd(tsv, tsq).label("rank")

    stmt = select(Product.id, rank).where(tsv.op("@@")(tsq))

    if params.category_id is not None:
        stmt = stmt.where(Product.category_id == params.category_id)
    if params.status is not None:
        stmt = stmt.where(Product.is_active == (params.status.value == "active"))
    if params.price_min is not None:
        stmt = stmt.where(Product.price >= params.price_min)
    if params.price_max is not None:
        stmt = stmt.where(Product.price <= params.price_max)

    stmt = stmt.order_by(desc(rank), Product.id.asc()).limit(candidate_limit)

    rows = db.execute(stmt).all()

    results: list[tuple[int, float]] = []
    for row in rows:
        product_id = int(row[0])
        score = float(row[1] or 0.0)
        results.append((product_id, score))
    return results


def _normalize_scores(items: list[tuple[int, float]]) -> dict[int, float]:
    if not items:
        return {}
    max_score = max(score for _, score in items) or 1.0
    return {product_id: (score / max_score) for product_id, score in items}


@router.get("", response_model=HybridSearchResponse)
def search_products(
    params: SearchQueryParams = Depends(),
    db: Session = Depends(get_db),
) -> HybridSearchResponse:
    candidate_limit = min(params.limit + params.offset + 40, 100)

    semantic_results: list[tuple[int, float]] = []
    try:
        semantic_results = vector_store.semantic_search(
            params.query,
            candidate_limit,
            category_id=params.category_id,
            status=params.status.value if params.status else None,
        )
    except Exception:  # noqa: BLE001
        semantic_results = []

    keyword_results = _keyword_search(db, params, candidate_limit)

    semantic_norm = _normalize_scores(semantic_results)
    keyword_norm = _normalize_scores(keyword_results)

    buckets: dict[int, _ScoreBucket] = defaultdict(_ScoreBucket)
    for product_id, score in semantic_norm.items():
        buckets[product_id].semantic = score
    for product_id, score in keyword_norm.items():
        buckets[product_id].keyword = score

    ranked: list[tuple[int, float, str]] = []
    for product_id, score_bucket in buckets.items():
        hybrid_score = (0.65 * score_bucket.semantic) + (0.35 * score_bucket.keyword)
        if score_bucket.semantic > 0 and score_bucket.keyword > 0:
            matched_by = "hybrid"
        elif score_bucket.semantic > 0:
            matched_by = "semantic"
        else:
            matched_by = "keyword"
        ranked.append((product_id, hybrid_score, matched_by))

    ranked.sort(key=lambda item: (-item[1], item[0]))

    total = len(ranked)
    window = ranked[params.offset : params.offset + params.limit]
    ordered_ids = [product_id for product_id, _, _ in window]
    if not ordered_ids:
        return HybridSearchResponse(
            query=params.query,
            total=total,
            limit=params.limit,
            offset=params.offset,
            items=[],
        )

    products = (
        db.execute(
            select(Product)
            .where(Product.id.in_(ordered_ids))
            .options(selectinload(Product.variants))
        )
        .scalars()
        .all()
    )
    by_id = {product.id: product for product in products}

    items: list[SearchResultItem] = []
    for product_id, score, matched_by in window:
        product = by_id.get(product_id)
        if product is None:
            continue
        items.append(
            SearchResultItem(
                product=product,
                score=round(score, 6),
                matched_by=matched_by,
            )
        )

    return HybridSearchResponse(
        query=params.query,
        total=total,
        limit=params.limit,
        offset=params.offset,
        items=items,
    )
