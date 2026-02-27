from __future__ import annotations

import os
import time

from app.services.embeddings import EmbeddingService


SAMPLE_PRODUCTS = [
    "Comfortable running shoes with lightweight cushioning and breathable mesh upper.",
    "Wireless over-ear headphones with active noise cancellation and 30h battery life.",
    "Insulated steel water bottle, leak-proof cap, keeps drinks cold for 24 hours.",
    "Minimalist backpack with laptop sleeve and weather-resistant fabric.",
]


def main() -> int:
    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY is missing. Set it before running embedding checks.")
        return 1

    service = EmbeddingService()

    start = time.perf_counter()
    vectors = service.embed_texts(SAMPLE_PRODUCTS)
    total_ms = (time.perf_counter() - start) * 1000

    if not vectors:
        raise RuntimeError("No embeddings were returned.")

    dimensions = {len(vector) for vector in vectors}
    if len(dimensions) != 1:
        raise RuntimeError(f"Inconsistent embedding dimensions: {sorted(dimensions)}")

    dim = dimensions.pop()
    per_item_ms = total_ms / len(vectors)

    print(f"Model: {service.model_name}")
    print(f"Batch size: {service.batch_size}")
    print(f"Vectors returned: {len(vectors)}")
    print(f"Embedding dimension: {dim}")
    print(f"Total time: {total_ms:.2f}ms")
    print(f"Average time per product: {per_item_ms:.2f}ms")
    print(
        "Dimension validation:",
        "PASS (1536)" if dim == 1536 else f"WARN (expected 1536, got {dim})",
    )
    print(
        "Latency validation:",
        "PASS (<100ms/product)" if per_item_ms < 100 else "WARN (>=100ms/product)",
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

