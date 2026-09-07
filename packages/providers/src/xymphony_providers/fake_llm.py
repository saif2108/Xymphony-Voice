"""In-memory LLM provider for unit tests."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from xymphony_contracts.llm import (
    CancellationToken,
    LLMRequest,
    LLMStreamChunk,
    ProviderError,
    ProviderErrorCode,
)


class FakeLLMProvider:
    provider_key = "fake"

    def __init__(
        self,
        *,
        chunks: list[str] | None = None,
        fail_with: ProviderError | None = None,
        delay_seconds: float = 0,
    ) -> None:
        self.chunks = chunks or ["hello", " world"]
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
            finish_reason = "stop" if index == len(self.chunks) - 1 else None
            yield LLMStreamChunk(delta=delta, finish_reason=finish_reason)


def cancelled_provider_error() -> ProviderError:
    return ProviderError(
        code=ProviderErrorCode.CANCELLED,
        message="cancelled",
        provider_key="fake",
        retryable=False,
    )
