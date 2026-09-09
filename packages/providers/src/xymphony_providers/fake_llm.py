"""In-memory LLM provider for unit tests."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from xymphony_contracts.llm import (
    CancellationToken,
    LLMRequest,
    LLMStreamChunk,
    LLMToolCall,
    ProviderError,
    ProviderErrorCode,
)


class FakeLLMProvider:
    provider_key = "fake"

    def __init__(
        self,
        *,
        chunks: list[str] | None = None,
        tool_calls: list[LLMToolCall] | None = None,
        fail_with: ProviderError | None = None,
        delay_seconds: float = 0,
    ) -> None:
        self.chunks = chunks or ["hello", " world"]
        self.tool_calls = tuple(tool_calls) if tool_calls else ()
        self.fail_with = fail_with
        self.delay_seconds = delay_seconds
        self.requests: list[LLMRequest] = []

    async def stream(
        self,
        request: LLMRequest,
        *,
        cancel: CancellationToken,
    ) -> AsyncIterator[LLMStreamChunk]:
        self.requests.append(request)
        if self.fail_with is not None:
            raise self.fail_with
        for index, delta in enumerate(self.chunks):
            if cancel.cancelled:
                return
            if self.delay_seconds:
                await asyncio.sleep(self.delay_seconds)
            if cancel.cancelled:
                return
            is_last = index == len(self.chunks) - 1
            finish_reason = (
                ("tool_calls" if self.tool_calls else "stop") if is_last else None
            )
            tool_calls = self.tool_calls if is_last else ()
            yield LLMStreamChunk(
                delta=delta,
                finish_reason=finish_reason,
                tool_calls=tool_calls,
            )


def cancelled_provider_error() -> ProviderError:
    return ProviderError(
        code=ProviderErrorCode.CANCELLED,
        message="cancelled",
        provider_key="fake",
        retryable=False,
    )
