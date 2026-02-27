from __future__ import annotations

import asyncio
import os
import random
import time
from statistics import quantiles
from typing import Any

import httpx


def _base_url() -> str:
    return os.getenv("DASHBOARD_LOAD_TEST_BASE_URL", "http://localhost:3001")


def _concurrency() -> int:
    return int(os.getenv("DASHBOARD_LOAD_TEST_CONCURRENCY", "100"))


def _timeout_seconds() -> float:
    return float(os.getenv("DASHBOARD_LOAD_TEST_TIMEOUT_SECONDS", "30"))


def _p95_target_ms() -> float:
    return float(os.getenv("DASHBOARD_P95_TARGET_MS", "500"))


def _endpoints() -> list[str]:
    raw = os.getenv(
        "DASHBOARD_LOAD_TEST_ENDPOINTS",
        "/api/sales,/api/products/top,/api/inventory/low",
    )
    endpoints = [item.strip() for item in raw.split(",") if item.strip()]
    return endpoints or [
        "/api/sales",
        "/api/products/top",
        "/api/inventory/low",
    ]


async def _single_request(
    client: httpx.AsyncClient,
    endpoint: str,
) -> dict[str, Any]:
    start = time.perf_counter()
    try:
        response = await client.get(endpoint, timeout=_timeout_seconds())
        response.raise_for_status()
        _ = response.json()
        return {
            "ok": True,
            "latency_ms": (time.perf_counter() - start) * 1000,
            "endpoint": endpoint,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "latency_ms": (time.perf_counter() - start) * 1000,
            "endpoint": endpoint,
            "error": str(exc),
        }


def _summarize(
    label: str,
    rows: list[dict[str, Any]],
    target_ms: float,
) -> None:
    successes = [item for item in rows if item["ok"]]
    failures = [item for item in rows if not item["ok"]]
    durations = [item["latency_ms"] for item in successes]

    print(f"{label}:")
    print(f"  Requests: {len(rows)}")
    print(f"  Successful: {len(successes)}")
    print(f"  Failures: {len(failures)}")
    if not durations:
        if failures:
            sample = failures[0].get("error", "unknown error")
            print(f"  Sample failure: {sample}")
        print("  P95 target: FAIL (no successful requests)")
        return

    if len(durations) >= 100:
        p95 = quantiles(durations, n=100)[94]
    else:
        p95 = max(durations)
    avg = sum(durations) / len(durations)
    worst = max(durations)
    print(f"  Average latency: {avg:.2f}ms")
    print(f"  P95 latency: {p95:.2f}ms")
    print(f"  Max latency: {worst:.2f}ms")
    print(
        "  P95 target:",
        (
            f"PASS (<{target_ms:.0f}ms)"
            if p95 < target_ms
            else f"FAIL (>={target_ms:.0f}ms)"
        ),
    )
    if failures:
        sample = failures[0].get("error", "unknown error")
        print(f"  Sample failure: {sample}")


async def main() -> int:
    concurrency = _concurrency()
    endpoints = _endpoints()
    target_ms = _p95_target_ms()
    base_url = _base_url()

    async with httpx.AsyncClient(base_url=base_url) as client:
        picks = [random.choice(endpoints) for _ in range(concurrency)]
        rows = await asyncio.gather(
            *[_single_request(client, endpoint) for endpoint in picks]
        )

    print(f"Dashboard load test base URL: {base_url}")
    _summarize("Overall", rows, target_ms)
    for endpoint in endpoints:
        scoped = [item for item in rows if item["endpoint"] == endpoint]
        if scoped:
            _summarize(f"Endpoint {endpoint}", scoped, target_ms)

    successes = [item for item in rows if item["ok"]]
    failures = [item for item in rows if not item["ok"]]
    if not successes:
        return 1
    durations = [item["latency_ms"] for item in successes]
    if len(durations) >= 100:
        p95 = quantiles(durations, n=100)[94]
    else:
        p95 = max(durations)
    if failures:
        return 1
    return 0 if p95 < target_ms else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
