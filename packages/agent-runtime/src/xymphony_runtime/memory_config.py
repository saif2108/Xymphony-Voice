"""Runtime memory configuration, protocol, and context formatting for recall.

Long-term memory is cross-session: facts about the user extracted during previous
conversations are retrieved to personalise future turns. This module provides a
recall-only port for the agent runtime; memory extraction, persistence, ownership,
privacy, and cross-session scoping are handled by external adapters or future milestones.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class MemoryEntry:
    """A single remembered fact about a user / agent context."""

    content: str
    """Human-readable statement, e.g. ``'User prefers brief answers.'``"""

    memory_id: str
    """Stable identifier assigned by the storage adapter or source."""

    score: float = 1.0
    """Relevance score returned by the memory store (higher = more relevant)."""


class MemoryStore(Protocol):
    """Port for retrieving cross-session memories during runtime orchestration.

    This interface only defines memory recall. Persistence, extraction, ownership,
    privacy, and cross-session scoping are handled by future adapters.
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


def format_memory_context(entries: Sequence[MemoryEntry]) -> str:
    """Render remembered facts as a numbered context block for the system prompt."""
    parts: list[str] = []
    for i, entry in enumerate(entries, 1):
        content = entry.content.strip()
        if content:
            parts.append(f"[{i}] {content}")
    return "\n\n".join(parts)
