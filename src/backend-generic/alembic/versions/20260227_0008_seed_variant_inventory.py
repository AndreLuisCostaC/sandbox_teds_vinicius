"""seed inventory for variants without inventory

Revision ID: 20260227_0008
Revises: 20260227_0007
Create Date: 2026-02-27 15:00:00

"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260227_0008"
down_revision: Union[str, None] = "20260227_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    now = datetime.now(timezone.utc)
    conn = op.get_bind()
    conn.execute(
        sa.text("""
            INSERT INTO inventories (product_variant_id, quantity, reserved_quantity, created_at, updated_at)
            SELECT pv.id, 10, 0, :now, :now
            FROM product_variants pv
            LEFT JOIN inventories i ON i.product_variant_id = pv.id
            WHERE i.id IS NULL
        """),
        {"now": now},
    )


def downgrade() -> None:
    pass
