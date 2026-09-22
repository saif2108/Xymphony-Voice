from __future__ import annotations

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