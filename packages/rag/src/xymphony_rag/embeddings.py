from __future__ import annotations

from sentence_transformers import SentenceTransformer

DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"


class LocalEmbeddingProvider:
    def __init__(self, model_name: str = DEFAULT_MODEL) -> None:
        self._model = SentenceTransformer(model_name)

    def embed(self, text: str) -> list[float]:
        """Create an embedding for one piece of text."""
        return self._model.encode(
            text,
            normalize_embeddings=True,
        ).tolist()

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        """Create embeddings for multiple pieces of text."""
        if not texts:
            return []

        embeddings = self._model.encode(
            texts,
            normalize_embeddings=True,
        )

        return embeddings.tolist()
