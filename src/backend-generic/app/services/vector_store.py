from __future__ import annotations

import os
from urllib.parse import urlparse

import chromadb

from app.models.product import Product
from app.services.embeddings import EmbeddingService
from langchain_chroma import Chroma


class ProductVectorStoreService:
    """Handles product vector indexing operations using Chroma + LangChain."""

    def __init__(self) -> None:
        chroma_url = os.getenv("CHROMA_URL") or "http://chromadb:8000"
        parsed = urlparse(chroma_url)
        host = parsed.hostname or "chromadb"
        port = parsed.port or 8000
        ssl = parsed.scheme == "https"
        collection = os.getenv("CHROMA_COLLECTION") or "products"

        self._embeddings = EmbeddingService()
        self._client = chromadb.HttpClient(host=host, port=port, ssl=ssl)
        self._collection = collection
        self._vector_store: Chroma | None = None

    def _store(self) -> Chroma:
        if self._vector_store is None:
            self._vector_store = Chroma(
                client=self._client,
                collection_name=self._collection,
                embedding_function=self._embeddings.as_langchain_embeddings(),
            )
        return self._vector_store

    @staticmethod
    def _document_id(product_id: int) -> str:
        return f"product:{product_id}"

    @staticmethod
    def _to_document(product: Product) -> tuple[str, dict[str, str | float]]:
        description = product.description or ""
        text = f"{product.name}\n\n{description}\n\nPrice: {product.price}"
        metadata = {
            "product_id": str(product.id),
            "category_id": str(product.category_id),
            "status": "active" if product.is_active else "inactive",
            "name": product.name,
            "price": float(product.price),
        }
        return text, metadata

    def index_product(self, product: Product) -> str:
        doc_id = self._document_id(product.id)
        text, metadata = self._to_document(product)
        store = self._store()
        store.delete(ids=[doc_id])
        store.add_texts(texts=[text], metadatas=[metadata], ids=[doc_id])
        return doc_id

    def reindex_product(self, product: Product) -> str:
        return self.index_product(product)

    def delete_product(self, product_id: int) -> str:
        doc_id = self._document_id(product_id)
        self._store().delete(ids=[doc_id])
        return doc_id

    def semantic_search(
        self,
        query: str,
        limit: int,
        *,
        category_id: int | None = None,
        status: str | None = None,
    ) -> list[tuple[int, float]]:
        chroma_filter: dict[str, str] = {}
        if category_id is not None:
            chroma_filter["category_id"] = str(category_id)
        if status is not None:
            chroma_filter["status"] = status

        docs_with_scores = self._store().similarity_search_with_score(
            query,
            k=max(limit, 1),
            filter=chroma_filter or None,
        )

        results: list[tuple[int, float]] = []
        for doc, distance in docs_with_scores:
            raw_id = doc.metadata.get("product_id")
            if raw_id is None:
                continue
            try:
                product_id = int(raw_id)
                score = 1.0 / (1.0 + float(distance))
            except (TypeError, ValueError):
                continue
            results.append((product_id, score))
        return results
