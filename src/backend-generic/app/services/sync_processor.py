from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import func, select

from app.db import SessionLocal
from app.models.product import Product
from app.models.product_sync_queue import ProductSyncQueue
from app.services.vector_store import ProductVectorStoreService


@dataclass
class SyncProcessorState:
    processed_count: int = 0
    failed_count: int = 0
    last_processed_at: datetime | None = None
    last_error: str | None = None


class ProductSyncProcessor:
    """Polls products_sync_queue and keeps vector index synchronized."""

    def __init__(self) -> None:
        self._enabled = os.getenv("ENABLE_PRODUCT_SYNC_WORKER", "true").lower() == "true"
        self._batch_size = int(os.getenv("SYNC_BATCH_SIZE", "50"))
        self._poll_interval = float(os.getenv("SYNC_POLL_INTERVAL_SECONDS", "1.0"))
        self._logger = structlog.get_logger("product_sync_processor")
        self._state = SyncProcessorState()
        self._task: asyncio.Task[None] | None = None
        self._vector_store = ProductVectorStoreService()

    async def start(self) -> None:
        if not self._enabled or self._task is not None:
            return
        self._task = asyncio.create_task(self._run(), name="product-sync-processor")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def _run(self) -> None:
        while True:
            try:
                processed = await asyncio.to_thread(self._process_batch)
                if processed == 0:
                    await asyncio.sleep(self._poll_interval)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                self._state.failed_count += 1
                self._state.last_error = str(exc)
                self._logger.warning("product_sync_processor_cycle_failed", error=str(exc))
                await asyncio.sleep(self._poll_interval)

    def _process_batch(self) -> int:
        processed = 0
        with SessionLocal() as db:
            queue_items = (
                db.execute(
                    select(ProductSyncQueue)
                    .order_by(ProductSyncQueue.id.asc())
                    .limit(self._batch_size)
                )
                .scalars()
                .all()
            )

            for item in queue_items:
                try:
                    self._process_item(db, item)
                    db.delete(item)
                    db.commit()
                    processed += 1
                    self._state.processed_count += 1
                    self._state.last_processed_at = datetime.now(UTC)
                    self._state.last_error = None
                except Exception as exc:  # noqa: BLE001
                    self._state.failed_count += 1
                    self._state.last_error = str(exc)
                    self._logger.warning(
                        "product_sync_item_failed",
                        queue_id=item.id,
                        product_id=item.product_id,
                        operation=item.operation,
                        error=str(exc),
                    )
                    # Keep item in queue for future retry.
                    db.rollback()
                    break

        return processed

    def _process_item(self, db, item: ProductSyncQueue) -> None:
        if item.operation in {"create", "update"}:
            product = db.get(Product, item.product_id)
            if product is None:
                self._vector_store.delete_product(item.product_id)
                return
            self._vector_store.reindex_product(product)
            return

        if item.operation == "delete":
            self._vector_store.delete_product(item.product_id)
            return

        raise RuntimeError(f"Unsupported sync operation: {item.operation}")

    def status(self) -> dict[str, Any]:
        now = datetime.now(UTC)
        with SessionLocal() as db:
            queue_count = db.execute(select(func.count(ProductSyncQueue.id))).scalar_one()
            oldest = db.execute(select(func.min(ProductSyncQueue.queued_at))).scalar_one()

        lag_seconds: float = 0.0
        if oldest is not None:
            lag_seconds = max((now - oldest).total_seconds(), 0.0)

        return {
            "enabled": self._enabled,
            "queue_count": int(queue_count),
            "oldest_queued_at": oldest.isoformat() if oldest else None,
            "queue_lag_seconds": round(lag_seconds, 3),
            "processed_count": self._state.processed_count,
            "failed_count": self._state.failed_count,
            "last_processed_at": (
                self._state.last_processed_at.isoformat()
                if self._state.last_processed_at
                else None
            ),
            "last_error": self._state.last_error,
            "poll_interval_seconds": self._poll_interval,
            "batch_size": self._batch_size,
        }
