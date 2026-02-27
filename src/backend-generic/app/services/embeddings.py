from __future__ import annotations

import os

from langchain_openai import OpenAIEmbeddings


class EmbeddingService:
    """Embedding service with batch support for product indexing."""

    def __init__(self) -> None:
        self.model_name = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
        self.batch_size = int(os.getenv("EMBEDDING_BATCH_SIZE", "32"))
        self.api_key = os.getenv("OPENAI_API_KEY")
        self._embeddings: OpenAIEmbeddings | None = None

    def _client(self) -> OpenAIEmbeddings:
        if self._embeddings is not None:
            return self._embeddings
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required for embedding operations.")
        self._embeddings = OpenAIEmbeddings(
            model=self.model_name,
            openai_api_key=self.api_key,
            chunk_size=self.batch_size,
        )
        return self._embeddings

    def as_langchain_embeddings(self) -> OpenAIEmbeddings:
        return self._client()

    def embed_text(self, text: str) -> list[float]:
        return self._client().embed_query(text)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return self._client().embed_documents(texts)

