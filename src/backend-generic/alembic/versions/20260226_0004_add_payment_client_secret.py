"""add payment client_secret column

Revision ID: 20260226_0004
Revises: 20260226_0003
Create Date: 2026-02-26 03:20:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260226_0004"
down_revision: Union[str, None] = "20260226_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("payments", sa.Column("client_secret", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("payments", "client_secret")
