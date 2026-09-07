"""Runtime session/turn context shared during orchestration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from uuid import UUID

from xymphony_contracts.enums import Channel, SessionStatus


@dataclass
class RuntimeContext:
    session_id: UUID
    organization_id: UUID
    project_id: UUID
    agent_id: UUID
    agent_version_id: UUID
    config_hash: str
    deployment_id: UUID | None = None
    channel: Channel = Channel.PLAYGROUND
    session_status: SessionStatus = SessionStatus.ACTIVE
    _shutdown: asyncio.Event = field(default_factory=asyncio.Event)
    _cancelled_turn_ids: set[UUID] = field(default_factory=set)
    _sequence: int = 0
    _turn_sequence: int = 0

    def next_event_sequence(self) -> int:
        self._sequence += 1
        return self._sequence

    def next_turn_sequence(self) -> int:
        self._turn_sequence += 1
        return self._turn_sequence

    def request_shutdown(self) -> None:
        self._shutdown.set()

    @property
    def shutdown_requested(self) -> bool:
        return self._shutdown.is_set()

    def cancel_turn(self, turn_id: UUID) -> None:
        self._cancelled_turn_ids.add(turn_id)

    @property
    def cancelled_turn_ids(self) -> frozenset[UUID]:
        return frozenset(self._cancelled_turn_ids)

    def is_turn_cancelled(self, turn_id: UUID) -> bool:
        return turn_id in self._cancelled_turn_ids
