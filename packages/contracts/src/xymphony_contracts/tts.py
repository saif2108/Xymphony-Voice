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
