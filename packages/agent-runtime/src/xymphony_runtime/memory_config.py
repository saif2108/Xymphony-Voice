"""Provider-independent recall contract and context formatting for long-term memory.

The runtime supplies agent/session identity, query text, and a recall limit. The
adapter owns persistence and extraction/writes, authorization and privacy checks,
tenant or other cross-session scope enforcement, retention/deletion, and
provider-specific filtering. A session identifier alone does not define safe
cross-session scope. ``recall`` may be synchronous or asynchronous; the runtime
supports both. This contract intentionally exposes no writeback operation.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class MemoryEntry:
    """A recalled memory with source-stable identity, content, and relevance.

    ``memory_id`` is assigned by the adapter and stable within its store.
    ``score`` is an optional provider-neutral relevance value (higher is more
    relevant); the runtime displays content and does not interpret the score.
    """

    content: str
    """Human-readable statement, e.g. ``'User prefers brief answers.'``"""

    memory_id: str
    """Stable identifier assigned by the storage adapter or source."""

    score: float = 1.0
    """Relevance score returned by the memory store (higher = more relevant)."""


class MemoryStore(Protocol):
    """Recall-only adapter boundary for runtime orchestration.

    The request identifies the current agent and session and supplies the current
    user query and maximum result count. Adapters must enforce authorization and
    all tenant/user/project and cross-session scope rules; ``session_id`` alone
    must not be treated as sufficient isolation. Storage, extraction, writes,
    retention, and deletion belong to the adapter. No transcript or write API is
    part of this contract.

    Implementations may return directly or asynchronously; both forms are
    supported by ``AgentRuntime``.
    """

    def recall(
        self,
        *,
        agent_id: UUID,
        session_id: UUID,
        query: str,
        limit: int = 10,
    ) -> list[MemoryEntry]:
        """Return the most relevant memories for *query*."""
        ...


@dataclass(frozen=True)
class MemoryRuntimeConfig:
    """Tuning parameters for the memory recall integration."""

    enabled: bool = True
    """Set to ``False`` to disable memory for a session without removing the store."""

    recall_limit: int = 10
    """Maximum number of memory entries retrieved per turn."""

    recall_timeout_seconds: float = 1.5
    """Async timeout (seconds) for ``MemoryStore.recall``."""

    def __post_init__(self) -> None:
        if self.recall_limit < 1:
            raise ValueError("recall_limit must be a positive integer")
        if self.recall_timeout_seconds <= 0:
            raise ValueError("recall_timeout_seconds must be positive")


def format_memory_context(entries: Sequence[MemoryEntry]) -> str:
    """Render remembered facts as a numbered context block for the system prompt."""
    parts: list[str] = []
    for i, entry in enumerate(entries, 1):
        content = entry.content.strip()
        if content:
            parts.append(f"[{i}] {content}")
    return "\n\n".join(parts)
