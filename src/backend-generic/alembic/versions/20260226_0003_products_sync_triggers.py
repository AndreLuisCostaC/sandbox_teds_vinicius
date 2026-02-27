"""add products sync queue and triggers

Revision ID: 20260226_0003
Revises: 20260225_0002
Create Date: 2026-02-26 00:30:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260226_0003"
down_revision: Union[str, None] = "20260225_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "products_sync_queue",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("operation", sa.String(length=16), nullable=False),
        sa.Column(
            "queued_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "operation IN ('create', 'update', 'delete')",
            name="ck_products_sync_queue_operation",
        ),
    )
    op.create_index(
        "ix_products_sync_queue_product_id",
        "products_sync_queue",
        ["product_id"],
    )
    op.create_index(
        "ix_products_sync_queue_queued_at",
        "products_sync_queue",
        ["queued_at"],
    )

    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION enqueue_product_sync() RETURNS trigger AS $$
            DECLARE
                product_id_to_queue integer;
                op_type text;
                payload text;
            BEGIN
                IF TG_OP = 'INSERT' THEN
                    product_id_to_queue := NEW.id;
                    op_type := 'create';
                ELSIF TG_OP = 'UPDATE' THEN
                    product_id_to_queue := NEW.id;
                    op_type := 'update';
                ELSE
                    product_id_to_queue := OLD.id;
                    op_type := 'delete';
                END IF;

                INSERT INTO products_sync_queue (product_id, operation)
                VALUES (product_id_to_queue, op_type);

                payload := json_build_object(
                    'product_id', product_id_to_queue,
                    'operation', op_type
                )::text;
                PERFORM pg_notify('products_sync', payload);

                RETURN COALESCE(NEW, OLD);
            END;
            $$ LANGUAGE plpgsql;
            """
        )
    )

    op.execute(
        sa.text(
            """
            CREATE TRIGGER products_sync_trigger
            AFTER INSERT OR UPDATE OR DELETE ON products
            FOR EACH ROW
            EXECUTE FUNCTION enqueue_product_sync();
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP TRIGGER IF EXISTS products_sync_trigger ON products;"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS enqueue_product_sync();"))
    op.drop_index("ix_products_sync_queue_queued_at", table_name="products_sync_queue")
    op.drop_index("ix_products_sync_queue_product_id", table_name="products_sync_queue")
    op.drop_table("products_sync_queue")
