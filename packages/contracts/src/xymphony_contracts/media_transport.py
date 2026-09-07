"""Media transport port types. LiveKit is one adapter; not the runtime."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field


class TransportParticipantEventKind(StrEnum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    LEFT = "left"


class TransportConnectionState(StrEnum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"


class MediaTransportConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    url: str = Field(min_length=1)
    room_name: str = Field(min_length=1)
    participant_identity: str = Field(min_length=1)
    token: str = Field(min_length=1)


class TransportParticipantEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: TransportParticipantEventKind
    identity: str
    room_name: str


class TransportErrorEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    message: str
    retryable: bool = False


ParticipantEventHandler = Callable[[TransportParticipantEvent], Awaitable[None] | None]
ConnectionStateHandler = Callable[[TransportConnectionState], Awaitable[None] | None]
TransportErrorHandler = Callable[[TransportErrorEvent], Awaitable[None] | None]


class MediaTransport(Protocol):
    """Minimal realtime media transport port (Step 3)."""

    @property
    def connection_state(self) -> TransportConnectionState: ...

    async def connect(self, config: MediaTransportConfig) -> None: ...

    async def disconnect(self) -> None: ...

    async def wait_until_disconnected(self) -> None: ...

    def on_participant_event(self, handler: ParticipantEventHandler) -> None: ...

    def on_connection_state(self, handler: ConnectionStateHandler) -> None: ...

    def on_error(self, handler: TransportErrorHandler) -> None: ...
