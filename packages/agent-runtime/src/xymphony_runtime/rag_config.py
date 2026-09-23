"""Runtime RAG/retrieval configuration and context formatting."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    content: str
    score: float
    document_id: str
    chunk_id: str


class Retriever(Protocol):
    def retrieve(
        self,
        *,
        query: str,
        limit: int = 5,
    ) -> list[RetrievalResult]:
        ...


@dataclass(frozen=True)
class RAGRuntimeConfig:
    enabled: bool = True
    limit: int = 5
    timeout_seconds: float = 2.0


def format_retrieval_context(results: Sequence[RetrievalResult]) -> str:
    """Format retrieved knowledge chunks into a readable context block."""
    parts: list[str] = []
    for i, res in enumerate(results, 1):
        content = res.content.strip()
        if content:
            parts.append(f"[{i}] {content}")
    return "\n\n".join(parts)
