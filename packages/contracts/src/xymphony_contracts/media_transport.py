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


class TransportAudioInputKind(StrEnum):
    STARTED = "started"
    ENDED = "ended"


class TransportAudioFrame(BaseModel):
    """Provider-neutral incoming audio from a remote participant."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    participant_identity: str = Field(min_length=1, max_length=256)
    room_name: str = Field(min_length=1, max_length=256)
    data: bytes = Field(max_length=65_536)
    sample_rate_hz: int = Field(default=16_000, ge=8_000, le=48_000)
    channels: int = Field(default=1, ge=1, le=2)
    duration_ms: int = Field(ge=0)


class TransportAudioInputEvent(BaseModel):
    """Minimal speech/audio boundary signal without VAD (Step 7)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: TransportAudioInputKind
    participant_identity: str = Field(min_length=1, max_length=256)
    room_name: str = Field(min_length=1, max_length=256)


class TransportAudioOutputFrame(BaseModel):
    """Provider-neutral outgoing assistant audio for transport publication (Step 8)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    room_name: str = Field(min_length=1, max_length=256)
    data: bytes = Field(max_length=65_536)
    sample_rate_hz: int = Field(default=16_000, ge=8_000, le=48_000)
    channels: int = Field(default=1, ge=1, le=2)
    duration_ms: int = Field(ge=0)
    chunk_index: int = Field(default=0, ge=0)
    is_final: bool = False
    turn_id: str | None = Field(default=None, max_length=36)


ParticipantEventHandler = Callable[[TransportParticipantEvent], Awaitable[None] | None]
ConnectionStateHandler = Callable[[TransportConnectionState], Awaitable[None] | None]
TransportErrorHandler = Callable[[TransportErrorEvent], Awaitable[None] | None]
AudioFrameHandler = Callable[[TransportAudioFrame], Awaitable[None] | None]
AudioInputHandler = Callable[[TransportAudioInputEvent], Awaitable[None] | None]


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

    def on_audio_frame(self, handler: AudioFrameHandler) -> None: ...

    def on_audio_input(self, handler: AudioInputHandler) -> None: ...

    async def publish_audio_output(self, frame: TransportAudioOutputFrame) -> None: ...
