from __future__ import annotations

import asyncio
import os
import time
from statistics import quantiles
from typing import Any

import httpx


def _base_url() -> str:
    return os.getenv("LOAD_TEST_BASE_URL", "http://localhost:8000")


def _concurrency() -> int:
    return int(os.getenv("ORDER_LOAD_TEST_CONCURRENCY", "100"))


def _timeout_seconds() -> float:
    return float(os.getenv("ORDER_LOAD_TEST_TIMEOUT_SECONDS", "180"))


async def _register_and_get_headers(client: httpx.AsyncClient, idx: int) -> dict[str, str] | None:
    email = f"order-load-{int(time.time() * 1000)}-{idx}@example.com"
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "VeryStrongPass123!",
            "full_name": f"Load User {idx}",
        },
    )
    if response.status_code != 200:
        return None
    token = response.json().get("access_token")
    if not token:
        return None
    return {"Authorization": f"Bearer {token}"}


async def _find_stocked_variant(client: httpx.AsyncClient, headers: dict[str, str]) -> int | None:
    for variant_id in range(1, 500):
        response = await client.get(f"/api/v1/products/{variant_id}/stock", headers=headers)
        if response.status_code != 200:
            continue
        if int(response.json().get("available_stock", 0)) > 0:
            return variant_id
    return None


async def _single_checkout(client: httpx.AsyncClient, idx: int) -> dict[str, Any]:
    start = time.perf_counter()
    try:
        headers = await _register_and_get_headers(client, idx)
        if headers is None:
            raise RuntimeError("register failed")
        me = await client.get("/api/v1/me", headers=headers)
        me.raise_for_status()
        user_id = me.json()["id"]

        variant_id = await _find_stocked_variant(client, headers)
        if variant_id is None:
            raise RuntimeError("no stocked variant")

        cart = await client.post("/api/v1/carts", json={"user_id": user_id}, headers=headers)
        cart.raise_for_status()
        cart_id = cart.json()["id"]

        item = await client.post(
            f"/api/v1/carts/{cart_id}/items",
            json={"product_variant_id": variant_id, "quantity": 1},
            headers=headers,
        )
        item.raise_for_status()

        checkout = await client.post(
            "/api/v1/orders",
            json={"cart_id": cart_id, "currency": "USD"},
            headers=headers,
        )
        if checkout.status_code != 201:
            raise RuntimeError(f"checkout failed status={checkout.status_code}")

        return {"ok": True, "latency_ms": (time.perf_counter() - start) * 1000}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "latency_ms": (time.perf_counter() - start) * 1000, "error": str(exc)}


async def main() -> int:
    concurrency = _concurrency()
    base_url = _base_url()
    timeout = httpx.Timeout(_timeout_seconds())
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        results = await asyncio.gather(*[_single_checkout(client, i) for i in range(concurrency)])

    successes = [item for item in results if item["ok"]]
    failures = [item for item in results if not item["ok"]]
    durations = [item["latency_ms"] for item in successes]
    if not durations:
        print(f"Requests: {len(results)}")
        print(f"Failures: {len(failures)}")
        if failures:
            print("Sample failure:", failures[0]["error"])
        print("No successful orders. Load test failed.")
        return 1

    p95 = quantiles(durations, n=100)[94] if len(durations) >= 100 else max(durations)
    avg = sum(durations) / len(durations)
    worst = max(durations)

    print(f"Requests: {len(results)}")
    print(f"Successful: {len(successes)}")
    print(f"Failures: {len(failures)}")
    print(f"Average latency: {avg:.2f}ms")
    print(f"P95 latency: {p95:.2f}ms")
    print(f"Max latency: {worst:.2f}ms")
    if failures:
        print("Sample failure:", failures[0]["error"])
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
