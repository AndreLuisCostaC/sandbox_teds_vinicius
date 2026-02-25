from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Inventory(TimestampMixin, Base):
    __tablename__ = "inventories"
    __table_args__ = (
        Index("ix_inventories_quantity", "quantity"),
        CheckConstraint("quantity >= 0", name="quantity_non_negative"),
        CheckConstraint("reserved_quantity >= 0", name="reserved_quantity_non_negative"),
        CheckConstraint("reserved_quantity <= quantity", name="reserved_quantity_lte_quantity"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    product_variant_id: Mapped[int] = mapped_column(
        ForeignKey("product_variants.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    quantity: Mapped[int] = mapped_column(nullable=False, default=0)
    reserved_quantity: Mapped[int] = mapped_column(nullable=False, default=0)

    product_variant = relationship("ProductVariant", back_populates="inventory")
    movements: Mapped[list["InventoryMovement"]] = relationship(
        back_populates="inventory", cascade="all, delete-orphan"
    )

