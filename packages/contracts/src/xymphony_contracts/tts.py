"""Provider-neutral TTS port types and protocol. No vendor SDKs."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from xymphony_contracts.provider import CancellationToken


class TTSTextRange(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    start: int = Field(ge=0)
    end: int = Field(ge=0)


class TTSRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider_key: str = Field(min_length=1, max_length=64)
    voice_ref: str = Field(min_length=1, max_length=256)
    text: str = Field(min_length=1, max_length=32_000)
    params: dict[str, JsonValue] = Field(default_factory=dict)


class TTSStreamChunk(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    audio_ref: str = Field(min_length=1, max_length=1024)
    index: int = Field(ge=0)
    is_final: bool = False
    text_range: TTSTextRange | None = None


class TTSResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    audio_ref: str = Field(min_length=1, max_length=1024)
    chunk_count: int = Field(ge=1)


class TTSProvider(Protocol):
    """TTS adapter port. Implementations live in packages/providers."""

    @property
    def provider_key(self) -> str: ...

    def stream(
        self,
        request: TTSRequest,
        *,
        cancel: CancellationToken,
    ) -> AsyncIterator[TTSStreamChunk]: ...


class TTSOutputAudioFrame(BaseModel):
    """Resolved PCM payload for a TTS audio_ref (transport layer only)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    data: bytes = Field(max_length=65_536)
    sample_rate_hz: int = Field(default=16_000, ge=8_000, le=48_000)
    channels: int = Field(default=1, ge=1, le=2)
    duration_ms: int = Field(ge=0)


class TTSOutputAudioResolver(Protocol):
    """Optional port for resolving TTS event audio_ref values to playable PCM."""

    def resolve_output_audio(self, audio_ref: str) -> TTSOutputAudioFrame | None: ...
