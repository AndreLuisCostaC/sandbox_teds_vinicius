from __future__ import annotations

import asyncio
import json
import os

import psycopg
import structlog
from psycopg import sql


def _database_url_for_psycopg(url: str) -> str:
    if url.startswith("postgresql+psycopg://"):
        return url.replace("postgresql+psycopg://", "postgresql://", 1)
    return url


class ProductSyncListener:
    """LISTEN worker for product sync notifications emitted by DB triggers."""

    def __init__(self) -> None:
        self._database_url = _database_url_for_psycopg(
            os.getenv(
                "DATABASE_URL",
                "postgresql://prodgrade:prodgrade@localhost:5432/prodgrade",
            )
        )
        self._channel = os.getenv("SYNC_NOTIFY_CHANNEL", "products_sync")
        self._enabled = os.getenv("ENABLE_PRODUCT_SYNC_LISTENER", "true").lower() == "true"
        self._task: asyncio.Task[None] | None = None
        self._logger = structlog.get_logger("product_sync_listener")

    async def start(self) -> None:
        if not self._enabled or self._task is not None:
            return
        self._task = asyncio.create_task(self._run(), name="product-sync-listener")

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
                await self._listen_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                self._logger.warning("product_sync_listener_reconnect", error=str(exc))
                await asyncio.sleep(2)

    async def _listen_once(self) -> None:
        async with await psycopg.AsyncConnection.connect(self._database_url, autocommit=True) as conn:
            await conn.execute(
                sql.SQL("LISTEN {}").format(sql.Identifier(self._channel))
            )
            self._logger.info("product_sync_listener_started", channel=self._channel)
            async for notify in conn.notifies():
                payload_raw = notify.payload or "{}"
                try:
                    payload = json.loads(payload_raw)
                except json.JSONDecodeError:
                    payload = {"raw": payload_raw}
                self._logger.info(
                    "product_sync_detected",
                    channel=notify.channel,
                    payload=payload,
                )
