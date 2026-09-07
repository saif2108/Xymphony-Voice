"""Provider-neutral STT port types and protocol. No vendor SDKs."""

from __future__ import annotations

from collections.abc import AsyncIterator
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from xymphony_contracts.provider import CancellationToken


class STTAudioFormat(StrEnum):
    PCM_S16LE = "pcm_s16le"


class STTAudioFrame(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    data: bytes = Field(max_length=65_536)
    sample_rate_hz: int = Field(default=16_000, ge=8_000, le=48_000)
    channels: int = Field(default=1, ge=1, le=2)
    duration_ms: int = Field(ge=0)


class STTRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider_key: str = Field(min_length=1, max_length=64)
    model: str = Field(min_length=1, max_length=256)
    language: str = Field(default="", max_length=32)
    params: dict[str, JsonValue] = Field(default_factory=dict)


class STTTranscriptChunk(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    text: str
    is_final: bool
    start_ms: int = Field(default=0, ge=0)
    end_ms: int = Field(default=0, ge=0)
    confidence: float | None = Field(default=None, ge=0, le=1)


class STTProvider(Protocol):
    """STT adapter port. Implementations live in packages/providers."""

    @property
    def provider_key(self) -> str: ...

    def transcribe(
        self,
        request: STTRequest,
        audio: AsyncIterator[STTAudioFrame],
        *,
        cancel: CancellationToken,
    ) -> AsyncIterator[STTTranscriptChunk]: ...
