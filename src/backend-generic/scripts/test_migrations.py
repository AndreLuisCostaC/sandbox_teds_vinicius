from __future__ import annotations

import os
import sys
from collections.abc import Iterable
from uuid import uuid4

from sqlalchemy import create_engine, exc, inspect, text


def require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def index_exists(indexes: Iterable[dict], expected_name: str, expected_columns: list[str]) -> bool:
    for idx in indexes:
        if idx.get("name") == expected_name and idx.get("column_names") == expected_columns:
            return True
    return False


def assert_raises_integrity(connection, statement: str, params: dict | None = None) -> None:
    try:
        connection.execute(text(statement), params or {})
        raise AssertionError(f"Expected integrity failure for statement: {statement}")
    except exc.IntegrityError:
        connection.rollback()


def main() -> int:
    database_url = require("DATABASE_URL")
    engine = create_engine(database_url, future=True)
    unique = uuid4().hex[:8]
    seeded_email = f"seed-test-{unique}@example.com"

    with engine.connect() as conn:
        inspector = inspect(conn)

        # Seed data check.
        roles = {
            row[0]
            for row in conn.execute(text("SELECT name FROM roles WHERE name IN ('admin', 'employee')"))
        }
        assert roles == {"admin", "employee"}, "Seed roles admin/employee were not created."

        # Index checks required by subtask 2.3.
        product_indexes = inspector.get_indexes("products")
        order_indexes = inspector.get_indexes("orders")
        inventory_indexes = inspector.get_indexes("inventories")

        assert index_exists(product_indexes, "ix_products_category_id", ["category_id"])
        assert index_exists(order_indexes, "ix_orders_status", ["status"])
        assert index_exists(inventory_indexes, "ix_inventories_quantity", ["quantity"])

        # Foreign key enforcement check.
        assert_raises_integrity(
            conn,
            """
            INSERT INTO products (name, description, price, is_active, category_id, created_at, updated_at)
            VALUES ('fk-test-product', NULL, 10.00, true, 999999, NOW(), NOW())
            """,
        )

        # Unique email check.
        admin_role_id = conn.execute(
            text("SELECT id FROM roles WHERE name = 'admin' LIMIT 1")
        ).scalar_one()
        conn.execute(
            text(
                """
                INSERT INTO users (email, hashed_password, full_name, is_active, role_id, created_at, updated_at)
                VALUES (:email, :pwd, :name, true, :role_id, NOW(), NOW())
                """
            ),
            {
                "email": seeded_email,
                "pwd": "hashed",
                "name": "Seed Test",
                "role_id": admin_role_id,
            },
        )
        conn.commit()

        assert_raises_integrity(
            conn,
            """
            INSERT INTO users (email, hashed_password, full_name, is_active, role_id, created_at, updated_at)
            VALUES (:email, 'hashed', 'Duplicate', true, :role_id, NOW(), NOW())
            """,
            {"role_id": admin_role_id, "email": seeded_email},
        )

        # Quantity constraint checks.
        category_id = conn.execute(
            text(
                """
                INSERT INTO categories (name, description, created_at, updated_at)
                VALUES (:name, NULL, NOW(), NOW())
                RETURNING id
                """
            ),
            {"name": f"seed-test-category-{unique}"},
        ).scalar_one()
        product_id = conn.execute(
            text(
                """
                INSERT INTO products (name, description, price, is_active, category_id, created_at, updated_at)
                VALUES ('seed-test-product-ok', NULL, 12.50, true, :category_id, NOW(), NOW())
                RETURNING id
                """
            ),
            {"category_id": category_id},
        ).scalar_one()
        variant_id = conn.execute(
            text(
                """
                INSERT INTO product_variants (product_id, sku, name, price, is_active, created_at, updated_at)
                VALUES (:product_id, :sku, 'default', 12.50, true, NOW(), NOW())
                RETURNING id
                """
            ),
            {"product_id": product_id, "sku": f"seed-test-sku-{unique}"},
        ).scalar_one()
        conn.commit()

        assert_raises_integrity(
            conn,
            """
            INSERT INTO inventories (product_variant_id, quantity, reserved_quantity, created_at, updated_at)
            VALUES (:variant_id, -1, 0, NOW(), NOW())
            """,
            {"variant_id": variant_id},
        )

        # Sync queue/trigger checks.
        trigger_category_id = conn.execute(
            text(
                """
                INSERT INTO categories (name, description, created_at, updated_at)
                VALUES (:name, NULL, NOW(), NOW())
                RETURNING id
                """
            ),
            {"name": f"trigger-test-category-{unique}"},
        ).scalar_one()
        trigger_product_id = conn.execute(
            text(
                """
                INSERT INTO products (name, description, price, is_active, category_id, created_at, updated_at)
                VALUES ('trigger-test-product', NULL, 99.00, true, :category_id, NOW(), NOW())
                RETURNING id
                """
            ),
            {"category_id": trigger_category_id},
        ).scalar_one()
        conn.commit()

        op_create = conn.execute(
            text(
                """
                SELECT operation
                FROM products_sync_queue
                WHERE product_id = :product_id
                ORDER BY id DESC
                LIMIT 1
                """
            ),
            {"product_id": trigger_product_id},
        ).scalar_one()
        assert op_create == "create", "Expected create operation in products_sync_queue."

        conn.execute(
            text("UPDATE products SET price = 109.00 WHERE id = :product_id"),
            {"product_id": trigger_product_id},
        )
        conn.commit()
        op_update = conn.execute(
            text(
                """
                SELECT operation
                FROM products_sync_queue
                WHERE product_id = :product_id
                ORDER BY id DESC
                LIMIT 1
                """
            ),
            {"product_id": trigger_product_id},
        ).scalar_one()
        assert op_update == "update", "Expected update operation in products_sync_queue."

        conn.execute(text("DELETE FROM products WHERE id = :product_id"), {"product_id": trigger_product_id})
        conn.commit()
        op_delete = conn.execute(
            text(
                """
                SELECT operation
                FROM products_sync_queue
                WHERE product_id = :product_id
                ORDER BY id DESC
                LIMIT 1
                """
            ),
            {"product_id": trigger_product_id},
        ).scalar_one()
        assert op_delete == "delete", "Expected delete operation in products_sync_queue."

        print(
            "Migration validation passed: seeds, indexes, FK, uniqueness, constraints, and sync triggers are OK."
        )

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc_info:  # noqa: BLE001
        print(f"Migration validation failed: {exc_info}", file=sys.stderr)
        raise

