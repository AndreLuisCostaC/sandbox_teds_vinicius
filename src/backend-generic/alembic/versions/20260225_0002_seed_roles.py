"""seed initial roles

Revision ID: 20260225_0002
Revises: 20260225_0001
Create Date: 2026-02-25 00:10:00
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260225_0002"
down_revision: Union[str, None] = "20260225_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    roles_table = sa.table(
        "roles",
        sa.column("name", sa.String(length=64)),
        sa.column("description", sa.String(length=255)),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )

    now = datetime.now(timezone.utc)

    op.bulk_insert(
        roles_table,
        [
            {
                "name": "admin",
                "description": "System administrator with full access.",
                "created_at": now,
                "updated_at": now,
            },
            {
                "name": "employee",
                "description": "Operational user with restricted access.",
                "created_at": now,
                "updated_at": now,
            },
        ],
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM roles WHERE name IN ('admin', 'employee')"))

