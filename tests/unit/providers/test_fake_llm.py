"""Fake LLM provider unit tests."""

from __future__ import annotations

import pytest

from xymphony_contracts.llm import LLMMessage, LLMRequest, LLMRole, ProviderError, ProviderErrorCode
from xymphony_providers.fake_llm import FakeLLMProvider
from xymphony_runtime.cancellation import EventCancellationToken


@pytest.mark.asyncio
async def test_fake_provider_streams_multiple_chunks() -> None:
    provider = FakeLLMProvider(chunks=["a", "b", "c"])
    request = LLMRequest(
        provider_key="fake",
        model="fake-model",
        messages=(LLMMessage(role=LLMRole.USER, content="hi"),),
    )
    cancel = EventCancellationToken()
    chunks = [chunk async for chunk in provider.stream(request, cancel=cancel)]
    assert [chunk.delta for chunk in chunks] == ["a", "b", "c"]
    assert chunks[-1].finish_reason == "stop"


@pytest.mark.asyncio
async def test_fake_provider_honours_cancellation() -> None:
    provider = FakeLLMProvider(chunks=["one", "two", "three"], delay_seconds=0.05)
    request = LLMRequest(
        provider_key="fake",
        model="fake-model",
        messages=(LLMMessage(role=LLMRole.USER, content="hi"),),
    )
    cancel = EventCancellationToken()
    collected: list[str] = []

    async def _consume() -> None:
        async for chunk in provider.stream(request, cancel=cancel):
            collected.append(chunk.delta)

    import asyncio

    task = asyncio.create_task(_consume())
    await asyncio.sleep(0.06)
    cancel.cancel()
    await task
    assert len(collected) < 3


@pytest.mark.asyncio
async def test_fake_provider_raises_configured_error() -> None:
    provider = FakeLLMProvider(
        fail_with=ProviderError(
            code=ProviderErrorCode.PROVIDER,
            message="boom",
            provider_key="fake",
        )
    )
    request = LLMRequest(
        provider_key="fake",
        model="fake-model",
        messages=(LLMMessage(role=LLMRole.USER, content="hi"),),
    )
    with pytest.raises(ProviderError) as exc_info:
        async for _ in provider.stream(request, cancel=EventCancellationToken()):
            pass
    assert exc_info.value.code == ProviderErrorCode.PROVIDER
