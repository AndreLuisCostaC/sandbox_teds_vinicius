from __future__ import annotations

import asyncio
import os
import time
from statistics import quantiles
from typing import Any

import httpx


def _base_url() -> str:
    return os.getenv("LOAD_TEST_BASE_URL", "http://localhost:8000")


def _query() -> str:
    return os.getenv("LOAD_TEST_QUERY", "comfortable running shoes")


def _concurrency() -> int:
    return int(os.getenv("LOAD_TEST_CONCURRENCY", "100"))


def _timeout_seconds() -> float:
    return float(os.getenv("LOAD_TEST_TIMEOUT_SECONDS", "180"))


async def _single_request(client: httpx.AsyncClient, query: str) -> dict[str, Any]:
    start = time.perf_counter()
    try:
        response = await client.get(
            "/api/v1/search",
            params={"query": query, "limit": 20, "offset": 0},
            timeout=_timeout_seconds(),
        )
        response.raise_for_status()
        _ = response.json()
        return {"ok": True, "latency_ms": (time.perf_counter() - start) * 1000}
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "latency_ms": (time.perf_counter() - start) * 1000,
            "error": str(exc),
        }


async def main() -> int:
    concurrency = _concurrency()
    query = _query()
    base_url = _base_url()

    async with httpx.AsyncClient(base_url=base_url) as client:
        results = await asyncio.gather(
            *[_single_request(client, query) for _ in range(concurrency)]
        )

    successes = [item for item in results if item["ok"]]
    failures = [item for item in results if not item["ok"]]
    durations = [item["latency_ms"] for item in successes]

    if not durations:
        print(f"Requests: {len(results)}")
        print(f"Failures: {len(failures)}")
        if failures:
            print("Sample failure:", failures[0]["error"])
        print("No successful requests. Load test failed.")
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
    print("P95 target:", "PASS (<200ms)" if p95 < 200 else "WARN (>=200ms)")
    if failures:
        print("Sample failure:", failures[0]["error"])

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
