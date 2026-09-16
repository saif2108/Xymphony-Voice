"""In-memory LLM provider for unit tests."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from xymphony_contracts.llm import (
    CancellationToken,
    LLMRequest,
    LLMStreamChunk,
    LLMToolCall,
    ProviderError,
    ProviderErrorCode,
)


@dataclass(frozen=True)
class FakeLLMResponse:
    chunks: list[str] = field(default_factory=list)
    tool_calls: tuple[LLMToolCall, ...] = ()
    finish_reason: str | None = None
    fail_with: ProviderError | None = None
    delay_seconds: float = 0.0


class FakeLLMProvider:
    provider_key = "fake"

    def __init__(
        self,
        *,
        chunks: list[str] | None = None,
        tool_calls: list[LLMToolCall] | None = None,
        fail_with: ProviderError | None = None,
        delay_seconds: float = 0,
        responses: list[FakeLLMResponse] | None = None,
    ) -> None:
        self.chunks = chunks or ["hello", " world"]
        self.tool_calls = tuple(tool_calls) if tool_calls else ()
        self.fail_with = fail_with
        self.delay_seconds = delay_seconds
        self.responses = list(responses) if responses is not None else None
        self.requests: list[LLMRequest] = []
        self._call_count = 0

    async def stream(
        self,
        request: LLMRequest,
        *,
        cancel: CancellationToken,
    ) -> AsyncIterator[LLMStreamChunk]:
        self.requests.append(request)

        if self.responses is not None:
            if self._call_count < len(self.responses):
                resp = self.responses[self._call_count]
            else:
                resp = self.responses[-1] if self.responses else FakeLLMResponse(chunks=["ok"])
            self._call_count += 1

            if resp.fail_with is not None:
                raise resp.fail_with

            chunks = resp.chunks
            tool_calls = tuple(resp.tool_calls)
            delay = resp.delay_seconds or self.delay_seconds

            if not chunks:
                if cancel.cancelled:
                    return
                if delay:
                    await asyncio.sleep(delay)
                if cancel.cancelled:
                    return
                terminal_finish_reason = resp.finish_reason or (
                    "tool_calls" if tool_calls else "stop"
                )
                yield LLMStreamChunk(
                    delta="",
                    finish_reason=terminal_finish_reason,
                    tool_calls=tool_calls,
                )
                return

            for index, delta in enumerate(chunks):
                if cancel.cancelled:
                    return
                if delay:
                    await asyncio.sleep(delay)
                if cancel.cancelled:
                    return
                is_last = index == len(chunks) - 1
                chunk_finish_reason: str | None = (
                    resp.finish_reason or ("tool_calls" if tool_calls else "stop")
                    if is_last
                    else None
                )
                chunk_tool_calls = tool_calls if is_last else ()
                yield LLMStreamChunk(
                    delta=delta,
                    finish_reason=chunk_finish_reason,
                    tool_calls=chunk_tool_calls,
                )
            return

        if self.fail_with is not None:
            raise self.fail_with

        if not self.chunks:
            if cancel.cancelled:
                return
            if self.delay_seconds:
                await asyncio.sleep(self.delay_seconds)
            if cancel.cancelled:
                return
            default_finish_reason = "tool_calls" if self.tool_calls else "stop"
            yield LLMStreamChunk(
                delta="",
                finish_reason=default_finish_reason,
                tool_calls=self.tool_calls,
            )
            return

        for index, delta in enumerate(self.chunks):
            if cancel.cancelled:
                return
            if self.delay_seconds:
                await asyncio.sleep(self.delay_seconds)
            if cancel.cancelled:
                return
            is_last = index == len(self.chunks) - 1
            default_chunk_finish_reason: str | None = (
                ("tool_calls" if self.tool_calls else "stop") if is_last else None
            )
            tool_calls = self.tool_calls if is_last else ()
            yield LLMStreamChunk(
                delta=delta,
                finish_reason=default_chunk_finish_reason,
                tool_calls=tool_calls,
            )


def cancelled_provider_error() -> ProviderError:
    return ProviderError(
        code=ProviderErrorCode.CANCELLED,
        message="cancelled",
        provider_key="fake",
        retryable=False,
    )
