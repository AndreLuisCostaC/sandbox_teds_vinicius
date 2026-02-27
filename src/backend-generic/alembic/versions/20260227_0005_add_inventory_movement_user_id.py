"""add user_id to inventory movements

Revision ID: 20260227_0005
Revises: 20260226_0004
Create Date: 2026-02-27 03:05:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260227_0005"
down_revision: Union[str, None] = "20260226_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "inventory_movements",
        sa.Column("user_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_inventory_movements_user_id",
        "inventory_movements",
        ["user_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_inventory_movements_user_id",
        "inventory_movements",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_inventory_movements_user_id",
        "inventory_movements",
        type_="foreignkey",
    )
    op.drop_index("ix_inventory_movements_user_id", table_name="inventory_movements")
    op.drop_column("inventory_movements", "user_id")
