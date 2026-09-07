"""Provider-neutral LLM port types and protocol. No vendor SDKs."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from xymphony_contracts.usage import Usage


class LLMRole(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ProviderErrorCode(StrEnum):
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    RATE_LIMIT = "rate_limit"
    AUTH = "auth"
    INVALID_REQUEST = "invalid_request"
    PROVIDER = "provider"
    UNKNOWN = "unknown"


class ProviderError(Exception):
    """Normalized provider failure surfaced to the runtime."""

    def __init__(
        self,
        *,
        code: ProviderErrorCode,
        message: str,
        provider_key: str,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.provider_key = provider_key
        self.retryable = retryable


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


class CancellationToken(Protocol):
    @property
    def cancelled(self) -> bool: ...


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
