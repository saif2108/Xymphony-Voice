"""Provider-neutral LLM port types and protocol. No vendor SDKs."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from xymphony_contracts.provider import CancellationToken, ProviderError, ProviderErrorCode
from xymphony_contracts.usage import Usage

__all__ = [
    "CancellationToken",
    "LLMMessage",
    "LLMProvider",
    "LLMRequest",
    "LLMResponse",
    "LLMRole",
    "LLMStreamChunk",
    "LLMToolCall",
    "LLMToolDefinition",
    "ProviderError",
    "ProviderErrorCode",
    "StreamHandler",
]


class LLMRole(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class LLMMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    role: LLMRole
    content: str = Field(min_length=0, max_length=32_000)


class LLMToolDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=4000)
    parameters: dict[str, JsonValue] = Field(default_factory=dict)


class LLMToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=128)
    arguments: str = Field(default="{}", max_length=16_000)


class LLMRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider_key: str = Field(min_length=1, max_length=64)
    model: str = Field(min_length=1, max_length=256)
    messages: tuple[LLMMessage, ...]
    system: str = Field(default="", max_length=32_000)
    params: dict[str, JsonValue] = Field(default_factory=dict)
    tools: tuple[LLMToolDefinition, ...] = ()
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_output_tokens: int | None = Field(default=None, ge=1)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)


class LLMStreamChunk(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    delta: str
    finish_reason: str | None = Field(default=None, max_length=64)


class LLMResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    text: str
    finish_reason: str = Field(min_length=1, max_length=64)
    usage: Usage | None = None
    tool_calls: tuple[LLMToolCall, ...] = ()


StreamHandler = Callable[[LLMStreamChunk], Awaitable[None] | None]


class LLMProvider(Protocol):
    """LLM adapter port. Implementations live in packages/providers."""

    @property
    def provider_key(self) -> str: ...

    def stream(
        self,
        request: LLMRequest,
        *,
        cancel: CancellationToken,
    ) -> AsyncIterator[LLMStreamChunk]: ...
