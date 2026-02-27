"""seed default admin user

Revision ID: 20260227_0006
Revises: 20260227_0005
Create Date: 2026-02-27 12:00:00
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from passlib.context import CryptContext

# revision identifiers, used by Alembic.
revision: str = "20260227_0006"
down_revision: Union[str, None] = "20260227_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Default admin credentials (change after first login in production)
DEFAULT_ADMIN_EMAIL = "admin@example.com"
DEFAULT_ADMIN_PASSWORD = "YourSecurePassword123!"


def upgrade() -> None:
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    hashed = pwd_context.hash(DEFAULT_ADMIN_PASSWORD)
    now = datetime.now(timezone.utc)

    conn = op.get_bind()
    admin_role_id = conn.execute(
        sa.text("SELECT id FROM roles WHERE name = 'admin' LIMIT 1")
    ).scalar_one()
    conn.execute(
        sa.text("""
            INSERT INTO users (email, hashed_password, full_name, is_active, role_id, created_at, updated_at)
            VALUES (:email, :hashed, 'Admin', true, :role_id, :now, :now)
            ON CONFLICT (email) DO UPDATE SET
                hashed_password = EXCLUDED.hashed_password,
                role_id = EXCLUDED.role_id,
                updated_at = EXCLUDED.updated_at
        """),
        {
            "email": DEFAULT_ADMIN_EMAIL,
            "hashed": hashed,
            "role_id": admin_role_id,
            "now": now,
        },
    )


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM users WHERE email = :e").bindparams(e=DEFAULT_ADMIN_EMAIL)
    )
