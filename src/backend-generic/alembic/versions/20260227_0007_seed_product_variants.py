"""seed default variants for products without variants

Revision ID: 20260227_0007
Revises: 20260227_0006
Create Date: 2026-02-27 14:00:00

"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260227_0007"
down_revision: Union[str, None] = "20260227_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    now = datetime.now(timezone.utc)
    conn = op.get_bind()

    products_without_variants = conn.execute(
        sa.text("""
            SELECT p.id, p.name, p.price, p.is_active
            FROM products p
            LEFT JOIN product_variants pv ON pv.product_id = p.id
            WHERE pv.id IS NULL
        """)
    ).fetchall()

    for row in products_without_variants:
        product_id = row[0]
        name = row[1] or "Default"
        price = row[2]
        is_active = row[3]

        result = conn.execute(
            sa.text("""
                INSERT INTO product_variants (product_id, sku, name, price, is_active, created_at, updated_at)
                VALUES (:product_id, :sku, :name, :price, :is_active, :now, :now)
                RETURNING id
            """),
            {
                "product_id": product_id,
                "sku": f"PROD-{product_id}-default",
                "name": name,
                "price": price,
                "is_active": is_active,
                "now": now,
            },
        )
        variant_id = result.scalar_one()

        conn.execute(
            sa.text("""
                INSERT INTO inventories (product_variant_id, quantity, reserved_quantity, created_at, updated_at)
                VALUES (:variant_id, 0, 0, :now, :now)
            """),
            {"variant_id": variant_id, "now": now},
        )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("""
            DELETE FROM product_variants
            WHERE sku LIKE 'PROD-%-default'
        """)
    )
