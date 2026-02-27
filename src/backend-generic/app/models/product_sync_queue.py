from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ProductSyncQueue(Base):
    __tablename__ = "products_sync_queue"
    __table_args__ = (
        CheckConstraint(
            "operation IN ('create', 'update', 'delete')",
            name="ck_products_sync_queue_operation",
        ),
        Index("ix_products_sync_queue_product_id", "product_id"),
        Index("ix_products_sync_queue_queued_at", "queued_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(Integer, nullable=False)
    operation: Mapped[str] = mapped_column(String(16), nullable=False)
    queued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )
