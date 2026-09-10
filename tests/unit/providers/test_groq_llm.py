"""Groq adapter normalization tests (mocked SDK, no network)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from openai import (
    APIConnectionError,
    APIStatusError,
    AuthenticationError,
    RateLimitError,
)

from xymphony_contracts.llm import (
    LLMMessage,
    LLMRequest,
    LLMRole,
    LLMToolCall,
    LLMToolDefinition,
    ProviderError,
    ProviderErrorCode,
)
from xymphony_providers.groq_llm import (
    GroqLLMProvider,
    _normalize_groq_error,
    _to_groq_messages,
    _to_groq_tools,
)
from xymphony_providers.registry import create_llm_provider
from xymphony_runtime.cancellation import EventCancellationToken

_SECRET = "gsk-test-secret-do-not-log"


class _FakeStream:
    def __init__(self, chunks: list[object]) -> None:
        self._chunks = chunks

    def __aiter__(self) -> _FakeStream:
        return self

    async def __anext__(self) -> object:
        if not self._chunks:
            raise StopAsyncIteration
        return self._chunks.pop(0)


def _simple_request(**overrides: object) -> LLMRequest:
    defaults = {
        "provider_key": "groq",
        "model": "llama-3.3-70b-versatile",
        "messages": (LLMMessage(role=LLMRole.USER, content="hi"),),
    }
    defaults.update(overrides)
    return LLMRequest(**defaults)  # type: ignore[arg-type]


def test_groq_provider_key() -> None:
    client = MagicMock()
    provider = GroqLLMProvider(model="llama-3.3-70b-versatile", api_key=_SECRET, client=client)
    assert provider.provider_key == "groq"


def test_groq_missing_api_key_raises() -> None:
    with pytest.raises(ValueError, match="GROQ_API_KEY is required"):
        GroqLLMProvider(model="llama-3.3-70b-versatile", api_key="")


def test_groq_default_client_base_url() -> None:
    provider = GroqLLMProvider(model="llama-3.3-70b-versatile", api_key=_SECRET)
    # The AsyncOpenAI client base_url should point to Groq's OpenAI-compatible endpoint
    assert str(provider._client.base_url).rstrip("/").endswith("api.groq.com/openai/v1")


def test_registry_creates_groq_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", _SECRET)
    monkeypatch.delenv("GROQ_MODEL", raising=False)
    provider = create_llm_provider("groq", model="llama-3.3-70b-versatile")
    assert isinstance(provider, GroqLLMProvider)
    assert provider.provider_key == "groq"
    assert provider._model == "llama-3.3-70b-versatile"


def test_registry_groq_missing_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(ValueError, match="GROQ_API_KEY"):
        create_llm_provider("groq", model="llama-3.3-70b-versatile")


def test_registry_respects_groq_model_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", _SECRET)
    monkeypatch.setenv("GROQ_MODEL", "mixtral-8x7b-32768")
    provider = create_llm_provider("groq", model="llama-3.3-70b-versatile")
    assert isinstance(provider, GroqLLMProvider)
    assert provider._model == "mixtral-8x7b-32768"


@pytest.mark.asyncio
async def test_groq_stream_normalizes_text_chunks() -> None:
    client = MagicMock()
    client.chat.completions.create = AsyncMock(
        return_value=_FakeStream(
            [
                SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            delta=SimpleNamespace(content="Hel", tool_calls=None),
                            finish_reason=None,
                        )
                    ]
                ),
                SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            delta=SimpleNamespace(content="lo", tool_calls=None),
                            finish_reason="stop",
                        )
                    ]
                ),
            ]
        )
    )
    provider = GroqLLMProvider(model="llama-3.3-70b-versatile", api_key=_SECRET, client=client)
    request = _simple_request()
    chunks = [chunk async for chunk in provider.stream(request, cancel=EventCancellationToken())]
    assert [chunk.delta for chunk in chunks] == ["Hel", "lo"]
    assert chunks[-1].finish_reason == "stop"
    assert chunks[-1].tool_calls == ()


@pytest.mark.asyncio
async def test_groq_stream_passes_generation_parameters() -> None:
    client = MagicMock()
    client.chat.completions.create = AsyncMock(
        return_value=_FakeStream(
            [
                SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            delta=SimpleNamespace(content="ok", tool_calls=None),
                            finish_reason="stop",
                        )
                    ]
                )
            ]
        )
    )
    provider = GroqLLMProvider(model="llama-3.3-70b-versatile", api_key=_SECRET, client=client)
    request = _simple_request(
        temperature=0.7,
        top_p=0.9,
        max_output_tokens=256,
    )
    _ = [chunk async for chunk in provider.stream(request, cancel=EventCancellationToken())]

    assert client.chat.completions.create.call_count == 1
    call_kwargs = client.chat.completions.create.call_args.kwargs
    assert call_kwargs["temperature"] == 0.7
    assert call_kwargs["top_p"] == 0.9
    assert call_kwargs["max_completion_tokens"] == 256


@pytest.mark.asyncio
async def test_groq_stream_params_fallback() -> None:
    client = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=_FakeStream([]))
    provider = GroqLLMProvider(model="llama-3.3-70b-versatile", api_key=_SECRET, client=client)
    request = _simple_request(
        params={
            "temperature": 0.5,
            "top_p": 0.8,
            "max_output_tokens": 128,
        }
    )
    _ = [chunk async for chunk in provider.stream(request, cancel=EventCancellationToken())]

    call_kwargs = client.chat.completions.create.call_args.kwargs
    assert call_kwargs["temperature"] == 0.5
    assert call_kwargs["top_p"] == 0.8
    assert call_kwargs["max_completion_tokens"] == 128


@pytest.mark.asyncio
async def test_groq_stream_cancellation() -> None:
    client = MagicMock()
    stream_chunks = [
        SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(content="A", tool_calls=None),
                    finish_reason=None,
                )
            ]
        ),
        SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(content="B", tool_calls=None),
                    finish_reason="stop",
                )
            ]
        ),
    ]
    client.chat.completions.create = AsyncMock(return_value=_FakeStream(stream_chunks))
    provider = GroqLLMProvider(model="llama-3.3-70b-versatile", api_key=_SECRET, client=client)
    cancel = EventCancellationToken()
    cancel.cancel()

    collected = [chunk async for chunk in provider.stream(_simple_request(), cancel=cancel)]
    assert len(collected) == 0


def test_groq_message_translation() -> None:
    request = LLMRequest(
        provider_key="groq",
        model="llama-3.3-70b-versatile",
        system="You are a helpful assistant.",
        messages=(
            LLMMessage(role=LLMRole.USER, content="Hello"),
            LLMMessage(role=LLMRole.ASSISTANT, content="Hi there"),
        ),
    )
    messages = _to_groq_messages(request)
    assert len(messages) == 3
    assert messages[0] == {"role": "system", "content": "You are a helpful assistant."}
    assert messages[1] == {"role": "user", "content": "Hello"}
    assert messages[2] == {"role": "assistant", "content": "Hi there"}


def test_groq_tool_definition_translation() -> None:
    tool_def = LLMToolDefinition(
        name="get_weather",
        description="Get weather for city",
        parameters={
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
    )
    request = _simple_request(tools=(tool_def,))
    tools = _to_groq_tools(request)
    assert len(tools) == 1
    assert tools[0]["type"] == "function"
    assert tools[0]["function"]["name"] == "get_weather"
    assert tools[0]["function"]["description"] == "Get weather for city"
    assert tools[0]["function"]["parameters"] == tool_def.parameters


@pytest.mark.asyncio
async def test_groq_stream_single_tool_call() -> None:
    client = MagicMock()
    stream_chunks = [
        SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(
                        content=None,
                        tool_calls=[
                            SimpleNamespace(
                                index=0,
                                id="call_groq_1",
                                function=SimpleNamespace(
                                    name="get_weather",
                                    arguments='{"city":',
                                ),
                            )
                        ],
                    ),
                    finish_reason=None,
                )
            ]
        ),
        SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(
                        content=None,
                        tool_calls=[
                            SimpleNamespace(
                                index=0,
                                id=None,
                                function=SimpleNamespace(
                                    name=None,
                                    arguments='"Paris"}',
                                ),
                            )
                        ],
                    ),
                    finish_reason=None,
                )
            ]
        ),
        SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(content=None, tool_calls=None),
                    finish_reason="tool_calls",
                )
            ]
        ),
    ]
    client.chat.completions.create = AsyncMock(return_value=_FakeStream(stream_chunks))
    provider = GroqLLMProvider(model="llama-3.3-70b-versatile", api_key=_SECRET, client=client)
    request = _simple_request(
        tools=(
            LLMToolDefinition(
                name="get_weather",
                description="Get weather",
                parameters={"type": "object", "properties": {"city": {"type": "string"}}},
            ),
        )
    )

    chunks = [chunk async for chunk in provider.stream(request, cancel=EventCancellationToken())]
    final = chunks[-1]
    assert final.finish_reason == "tool_calls"
    assert len(final.tool_calls) == 1
    tc = final.tool_calls[0]
    assert isinstance(tc, LLMToolCall)
    assert tc.id == "call_groq_1"
    assert tc.name == "get_weather"
    assert tc.arguments == '{"city":"Paris"}'


@pytest.mark.asyncio
async def test_groq_stream_multiple_tool_calls() -> None:
    client = MagicMock()
    stream_chunks = [
        SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(
                        content=None,
                        tool_calls=[
                            SimpleNamespace(
                                index=0,
                                id="call_1",
                                function=SimpleNamespace(
                                    name="tool_a",
                                    arguments='{"x": 1}',
                                ),
                            ),
                            SimpleNamespace(
                                index=1,
                                id="call_2",
                                function=SimpleNamespace(
                                    name="tool_b",
                                    arguments='{"y": 2}',
                                ),
                            ),
                        ],
                    ),
                    finish_reason=None,
                )
            ]
        ),
        SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(content=None, tool_calls=None),
                    finish_reason="tool_calls",
                )
            ]
        ),
    ]
    client.chat.completions.create = AsyncMock(return_value=_FakeStream(stream_chunks))
    provider = GroqLLMProvider(model="llama-3.3-70b-versatile", api_key=_SECRET, client=client)
    chunks = [
        chunk async for chunk in provider.stream(_simple_request(), cancel=EventCancellationToken())
    ]
    final = chunks[-1]
    assert final.finish_reason == "tool_calls"
    assert len(final.tool_calls) == 2
    assert final.tool_calls[0].name == "tool_a"
    assert final.tool_calls[1].name == "tool_b"


def test_normalize_auth_error() -> None:
    err = AuthenticationError(
        message=f"invalid key {_SECRET}",
        response=MagicMock(status_code=401, request=MagicMock()),
        body=None,
    )
    normalized = _normalize_groq_error(err)
    assert normalized.code == ProviderErrorCode.AUTH
    assert normalized.provider_key == "groq"
    assert normalized.retryable is False
    assert _SECRET not in normalized.message


def test_normalize_rate_limit_error() -> None:
    err = RateLimitError(
        message="rate limit reached",
        response=MagicMock(status_code=429, request=MagicMock()),
        body=None,
    )
    normalized = _normalize_groq_error(err)
    assert normalized.code == ProviderErrorCode.RATE_LIMIT
    assert normalized.provider_key == "groq"
    assert normalized.retryable is True


def test_normalize_connection_error() -> None:
    err = APIConnectionError(request=MagicMock())
    normalized = _normalize_groq_error(err)
    assert normalized.code == ProviderErrorCode.TIMEOUT
    assert normalized.provider_key == "groq"
    assert normalized.retryable is True


def test_normalize_api_status_error() -> None:
    response = MagicMock(status_code=503, request=MagicMock())
    err = APIStatusError(message="service unavailable", response=response, body=None)
    normalized = _normalize_groq_error(err)
    assert normalized.code == ProviderErrorCode.PROVIDER
    assert normalized.provider_key == "groq"
    assert normalized.retryable is True


def test_normalize_unknown_error() -> None:
    err = RuntimeError("something unexpected")
    normalized = _normalize_groq_error(err)
    assert normalized.code == ProviderErrorCode.UNKNOWN
    assert normalized.provider_key == "groq"
    assert normalized.retryable is False
    assert "something unexpected" in normalized.message


@pytest.mark.asyncio
async def test_groq_stream_raises_normalized_error() -> None:
    client = MagicMock()
    client.chat.completions.create = AsyncMock(
        side_effect=AuthenticationError(
            message="unauthorized",
            response=MagicMock(status_code=401, request=MagicMock()),
            body=None,
        )
    )
    provider = GroqLLMProvider(model="llama-3.3-70b-versatile", api_key=_SECRET, client=client)
    with pytest.raises(ProviderError) as exc_info:
        async for _ in provider.stream(_simple_request(), cancel=EventCancellationToken()):
            pass
    assert exc_info.value.code == ProviderErrorCode.AUTH
    assert exc_info.value.provider_key == "groq"
