from __future__ import annotations

from typing import Protocol
from uuid import UUID

from xymphony_rag.retrieval import RetrievalResult, Retriever


class EmbeddingProvider(Protocol):
    def embed(self, text: str) -> list[float]:
        ...


class RetrievedChunk(Protocol):
    content: str
    document_id: UUID
    id: UUID


class ScoredChunkRepository(Protocol):
    def search_hybrid_scored(
        self,
        *,
        agent_version_id: UUID,
        query: str,
        query_embedding: list[float],
        limit: int = 5,
    ) -> list[tuple[RetrievedChunk, float]]:
        ...


class DatabaseRetriever(Retriever):
    def __init__(
        self,
        *,
        repository: ScoredChunkRepository,
        embedding_provider: EmbeddingProvider,
        agent_version_id: UUID,
    ) -> None:
        self._repository = repository
        self._embedding_provider = embedding_provider
        self._agent_version_id = agent_version_id

    def retrieve(
        self,
        *,
        query: str,
        limit: int = 5,
    ) -> list[RetrievalResult]:
        query_embedding = self._embedding_provider.embed(query)
        rows = self._repository.search_hybrid_scored(
            agent_version_id=self._agent_version_id,
            query=query,
            query_embedding=query_embedding,
            limit=limit,
        )

        return [
            RetrievalResult(
                content=row.content,
                score=score,
                document_id=str(row.document_id),
                chunk_id=str(row.id),
            )
            for row, score in rows
        ]
