"""OpenAI adapter normalization tests (mocked SDK, no network)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from openai import APIStatusError, AuthenticationError, RateLimitError

from xymphony_contracts.llm import LLMMessage, LLMRequest, LLMRole, ProviderErrorCode
from xymphony_providers.openai_llm import OpenAILLMProvider, _normalize_openai_error
from xymphony_runtime.cancellation import EventCancellationToken

_SECRET = "sk-test-secret-do-not-log"


class _FakeStream:
    def __init__(self, chunks: list[object]) -> None:
        self._chunks = chunks

    def __aiter__(self) -> _FakeStream:
        return self

    async def __anext__(self) -> object:
        if not self._chunks:
            raise StopAsyncIteration
        return self._chunks.pop(0)


@pytest.mark.asyncio
async def test_openai_stream_normalizes_chunks() -> None:
    client = MagicMock()
    client.chat.completions.create = AsyncMock(
        return_value=_FakeStream(
            [
                SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            delta=SimpleNamespace(content="Hel"),
                            finish_reason=None,
                        )
                    ]
                ),
                SimpleNamespace(
                    choices=[
                        SimpleNamespace(delta=SimpleNamespace(content="lo"), finish_reason="stop")
                    ]
                ),
            ]
        )
    )
    provider = OpenAILLMProvider(model="gpt-4o-mini", api_key=_SECRET, client=client)
    request = LLMRequest(
        provider_key="openai",
        model="gpt-4o-mini",
        messages=(LLMMessage(role=LLMRole.USER, content="hi"),),
    )
    chunks = [chunk async for chunk in provider.stream(request, cancel=EventCancellationToken())]
    assert [chunk.delta for chunk in chunks] == ["Hel", "lo"]
    assert chunks[-1].finish_reason == "stop"


def test_normalize_auth_error_does_not_leak_key() -> None:
    err = AuthenticationError(
        message=f"invalid key {_SECRET}",
        response=MagicMock(status_code=401, request=MagicMock()),
        body=None,
    )
    normalized = _normalize_openai_error(err)
    assert normalized.code == ProviderErrorCode.AUTH
    assert _SECRET not in normalized.message


def test_normalize_rate_limit_error() -> None:
    err = RateLimitError(
        message="rate limited",
        response=MagicMock(status_code=429, request=MagicMock()),
        body=None,
    )
    normalized = _normalize_openai_error(err)
    assert normalized.code == ProviderErrorCode.RATE_LIMIT
    assert normalized.retryable is True


def test_normalize_api_status_error() -> None:
    response = MagicMock(status_code=503, request=MagicMock())
    err = APIStatusError(message="unavailable", response=response, body=None)
    normalized = _normalize_openai_error(err)
    assert normalized.code == ProviderErrorCode.PROVIDER
    assert normalized.retryable is True
