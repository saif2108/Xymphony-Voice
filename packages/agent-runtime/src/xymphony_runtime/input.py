"""Runtime input events accepted by AgentRuntime."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class RuntimeInputKind(StrEnum):
    TEXT_INPUT = "text_input"
    USER_SPEECH_STARTED = "user_speech_started"
    USER_SPEECH_ENDED = "user_speech_ended"
    AUDIO_FRAME = "audio_frame"
    CANCEL_TURN = "cancel_turn"
    SHUTDOWN = "shutdown"
    ERROR = "error"


@dataclass(frozen=True)
class RuntimeInput:
    kind: RuntimeInputKind
    text: str | None = None
    turn_id: UUID | None = None
    error_code: str | None = None
    error_message: str | None = None
    audio_data: bytes | None = None
    audio_duration_ms: int | None = None
    audio_sample_rate_hz: int | None = None
    audio_channels: int | None = None

    @classmethod
    def text_input(cls, value: str) -> RuntimeInput:
        return cls(kind=RuntimeInputKind.TEXT_INPUT, text=value)

    @classmethod
    def user_speech_started(cls) -> RuntimeInput:
        return cls(kind=RuntimeInputKind.USER_SPEECH_STARTED)

    @classmethod
    def user_speech_ended(cls) -> RuntimeInput:
        return cls(kind=RuntimeInputKind.USER_SPEECH_ENDED)

    @classmethod
    def audio_frame(
        cls,
        data: bytes,
        *,
        duration_ms: int,
        sample_rate_hz: int = 16_000,
        channels: int = 1,
    ) -> RuntimeInput:
        return cls(
            kind=RuntimeInputKind.AUDIO_FRAME,
            audio_data=data,
            audio_duration_ms=duration_ms,
            audio_sample_rate_hz=sample_rate_hz,
            audio_channels=channels,
        )

    @classmethod
    def cancel_turn(cls, turn_id: UUID | None = None) -> RuntimeInput:
        return cls(kind=RuntimeInputKind.CANCEL_TURN, turn_id=turn_id)

    @classmethod
    def shutdown(cls) -> RuntimeInput:
        return cls(kind=RuntimeInputKind.SHUTDOWN)

    @classmethod
    def error(cls, *, code: str, message: str) -> RuntimeInput:
        return cls(kind=RuntimeInputKind.ERROR, error_code=code, error_message=message)
