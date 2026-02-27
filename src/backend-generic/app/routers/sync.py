from __future__ import annotations

from fastapi import APIRouter, Depends

from app.models.user import User
from app.security import get_current_user_with_role
from app.services.sync_processor import ProductSyncProcessor


def create_sync_router(sync_processor: ProductSyncProcessor) -> APIRouter:
    router = APIRouter(prefix="/admin/sync", tags=["sync"])

    @router.get("/status")
    async def sync_status(
        current_user: User = Depends(get_current_user_with_role("admin")),
    ) -> dict[str, object]:
        _ = current_user
        return sync_processor.status()

    return router
