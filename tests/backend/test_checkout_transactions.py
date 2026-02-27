from __future__ import annotations

import asyncio
import os
import subprocess
import time
from dataclasses import dataclass

import httpx
import pytest


BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:8000")


def _psql_scalar(sql: str) -> str:
    return subprocess.run(
        [
            "docker",
            "exec",
            "prodgrade-postgres",
            "psql",
            "-U",
            "prodgrade",
            "-d",
            "prodgrade",
            "-t",
            "-A",
            "-c",
            sql,
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _set_backend_payment_mode(mode: str) -> None:
    subprocess.run(
        f"PAYMENT_INTENT_MODE={mode} docker compose --env-file .env up -d backend",
        shell=True,
        cwd="/B52/workspace/valendo/fresh/sandbox_teds_vinicius/prodgrade",
        check=True,
        capture_output=True,
        text=True,
    )


@dataclass
class SessionContext:
    client: httpx.AsyncClient
    auth_headers: dict[str, str]
    user_id: int


async def _create_session_context(client: httpx.AsyncClient, tag: str) -> SessionContext:
    ts = int(time.time() * 1000)
    email = f"{tag}_{ts}@example.com"
    register = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "VeryStrongPass123!",
            "full_name": f"Test {tag}",
        },
    )
    register.raise_for_status()
    token = register.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    me = await client.get("/api/v1/me", headers=headers)
    me.raise_for_status()
    return SessionContext(client=client, auth_headers=headers, user_id=me.json()["id"])


async def _find_stocked_variant(client: httpx.AsyncClient, headers: dict[str, str], min_stock: int = 1) -> int:
    for variant_id in range(1, 500):
        response = await client.get(f"/api/v1/products/{variant_id}/stock", headers=headers)
        if response.status_code != 200:
            continue
        if int(response.json().get("available_stock", 0)) >= min_stock:
            return variant_id
    raise AssertionError("No stocked variant found for tests.")


async def _create_cart_with_item(ctx: SessionContext, variant_id: int, quantity: int) -> int:
    cart = await ctx.client.post(
        "/api/v1/carts",
        json={"user_id": ctx.user_id},
        headers=ctx.auth_headers,
    )
    cart.raise_for_status()
    cart_id = cart.json()["id"]
    item = await ctx.client.post(
        f"/api/v1/carts/{cart_id}/items",
        json={"product_variant_id": variant_id, "quantity": quantity},
        headers=ctx.auth_headers,
    )
    item.raise_for_status()
    return cart_id


@pytest.mark.asyncio
async def test_stock_validation_failure_rolls_back() -> None:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as client:
        ctx = await _create_session_context(client, "stock_fail")
        variant_id = await _find_stocked_variant(client, ctx.auth_headers)
        cart_id = await _create_cart_with_item(ctx, variant_id, 1)

        orders_before = int(_psql_scalar(f"SELECT COUNT(*) FROM orders WHERE user_id = {ctx.user_id};"))
        qty_before = int(_psql_scalar(f"SELECT quantity FROM inventories WHERE product_variant_id = {variant_id};"))

        _psql_scalar(f"UPDATE inventories SET reserved_quantity = quantity WHERE product_variant_id = {variant_id};")
        response = await client.post(
            "/api/v1/orders",
            json={"cart_id": cart_id, "currency": "USD"},
            headers=ctx.auth_headers,
        )
        _psql_scalar(f"UPDATE inventories SET reserved_quantity = 0 WHERE product_variant_id = {variant_id};")

        assert response.status_code == 400
        orders_after = int(_psql_scalar(f"SELECT COUNT(*) FROM orders WHERE user_id = {ctx.user_id};"))
        qty_after = int(_psql_scalar(f"SELECT quantity FROM inventories WHERE product_variant_id = {variant_id};"))
        assert orders_before == orders_after
        assert qty_before == qty_after


@pytest.mark.asyncio
async def test_payment_failure_rolls_back_all_changes() -> None:
    _set_backend_payment_mode("failure")
    try:
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as client:
            ctx = await _create_session_context(client, "payment_fail")
            variant_id = await _find_stocked_variant(client, ctx.auth_headers)
            cart_id = await _create_cart_with_item(ctx, variant_id, 1)

            orders_before = int(_psql_scalar(f"SELECT COUNT(*) FROM orders WHERE user_id = {ctx.user_id};"))
            payments_before = int(_psql_scalar("SELECT COUNT(*) FROM payments;"))
            qty_before = int(_psql_scalar(f"SELECT quantity FROM inventories WHERE product_variant_id = {variant_id};"))

            response = await client.post(
                "/api/v1/orders",
                json={"cart_id": cart_id, "currency": "USD"},
                headers=ctx.auth_headers,
            )
            assert response.status_code == 502

            orders_after = int(_psql_scalar(f"SELECT COUNT(*) FROM orders WHERE user_id = {ctx.user_id};"))
            payments_after = int(_psql_scalar("SELECT COUNT(*) FROM payments;"))
            qty_after = int(_psql_scalar(f"SELECT quantity FROM inventories WHERE product_variant_id = {variant_id};"))
            assert orders_before == orders_after
            assert payments_before == payments_after
            assert qty_before == qty_after
    finally:
        _set_backend_payment_mode("success")


@pytest.mark.asyncio
async def test_concurrent_checkouts_prevent_overselling() -> None:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as client:
        admin_ctx = await _create_session_context(client, "oversell_admin")
        variant_id = await _find_stocked_variant(client, admin_ctx.auth_headers, min_stock=1)

        _psql_scalar(
            f"UPDATE inventories SET quantity = 3, reserved_quantity = 0 WHERE product_variant_id = {variant_id};"
        )
        before_qty = int(_psql_scalar(f"SELECT quantity FROM inventories WHERE product_variant_id = {variant_id};"))

        async def one_checkout(i: int) -> int:
            ctx = await _create_session_context(client, f"oversell_{i}")
            cart_id = await _create_cart_with_item(ctx, variant_id, 1)
            response = await client.post(
                "/api/v1/orders",
                json={"cart_id": cart_id, "currency": "USD"},
                headers=ctx.auth_headers,
            )
            return response.status_code

        statuses = await asyncio.gather(*[one_checkout(i) for i in range(5)])
        success_count = sum(1 for status in statuses if status == 201)

        after_qty = int(_psql_scalar(f"SELECT quantity FROM inventories WHERE product_variant_id = {variant_id};"))
        assert success_count <= before_qty
        assert after_qty >= 0
        assert before_qty - after_qty == success_count


@pytest.mark.asyncio
async def test_webhook_invalid_signature_returns_400() -> None:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as client:
        payload = {
            "id": "evt_invalid_signature",
            "type": "payment_intent.succeeded",
            "data": {"object": {"id": "pi_fake"}},
        }
        response = await client.post(
            "/webhooks/stripe",
            json=payload,
            headers={"Stripe-Signature": "t=1,v1=invalid"},
        )
        assert response.status_code == 400
