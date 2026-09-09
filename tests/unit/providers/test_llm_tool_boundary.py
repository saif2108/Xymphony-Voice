"""Phase 4 Step 1: LLM tool-calling provider boundary tests.

Covers tool-definition translation, streamed tool-call delta accumulation,
ordinary text streaming preservation, cancellation, and error normalization.
No real network calls — all tests use mocked SDK or FakeLLMProvider.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from openai import AuthenticationError

from xymphony_contracts.llm import (
    LLMMessage,
    LLMRequest,
    LLMRole,
    LLMStreamChunk,
    LLMToolCall,
    LLMToolDefinition,
    ProviderError,
    ProviderErrorCode,
)
from xymphony_providers.fake_llm import FakeLLMProvider
from xymphony_providers.openai_llm import OpenAILLMProvider, _to_openai_tools
from xymphony_runtime.cancellation import EventCancellationToken

_SECRET = "sk-test-secret-do-not-log"


def _simple_request(**overrides: object) -> LLMRequest:
    defaults = {
        "provider_key": "openai",
        "model": "gpt-4o-mini",
        "messages": (LLMMessage(role=LLMRole.USER, content="hi"),),
    }
    defaults.update(overrides)
    return LLMRequest(**defaults)  # type: ignore[arg-type]


def _weather_tool() -> LLMToolDefinition:
    return LLMToolDefinition(
        name="get_weather",
        description="Get current weather for a city.",
        parameters={
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name"},
            },
            "required": ["city"],
        },
    )


def _search_tool() -> LLMToolDefinition:
    return LLMToolDefinition(
        name="web_search",
        description="Search the web.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
            },
            "required": ["query"],
        },
    )


# ---------------------------------------------------------------------------
# 1. Request with no tools behaves exactly as before
# ---------------------------------------------------------------------------
class TestNoToolsPreservation:
    @pytest.mark.asyncio
    async def test_openai_text_only_request_unchanged(self) -> None:
        """Requests without tools produce text chunks exactly as before."""
        client = MagicMock()

        class FakeStream:
            def __init__(self) -> None:
                self._chunks = [
                    SimpleNamespace(
                        choices=[
                            SimpleNamespace(
                                delta=SimpleNamespace(content="Hello", tool_calls=None),
                                finish_reason=None,
                            )
                        ]
                    ),
                    SimpleNamespace(
                        choices=[
                            SimpleNamespace(
                                delta=SimpleNamespace(content=" world", tool_calls=None),
                                finish_reason="stop",
                            )
                        ]
                    ),
                ]

            def __aiter__(self) -> FakeStream:
                return self

            async def __anext__(self) -> object:
                if not self._chunks:
                    raise StopAsyncIteration
                return self._chunks.pop(0)

        client.chat.completions.create = AsyncMock(return_value=FakeStream())
        provider = OpenAILLMProvider(model="gpt-4o-mini", api_key=_SECRET, client=client)
        request = _simple_request()

        chunks = [c async for c in provider.stream(request, cancel=EventCancellationToken())]
        assert [c.delta for c in chunks] == ["Hello", " world"]
        assert chunks[-1].finish_reason == "stop"
        assert chunks[-1].tool_calls == ()

        # No tools kwarg sent to OpenAI
        call_kwargs = client.chat.completions.create.call_args.kwargs
        assert "tools" not in call_kwargs

    @pytest.mark.asyncio
    async def test_fake_text_only_unchanged(self) -> None:
        """FakeLLM text-only output unchanged."""
        provider = FakeLLMProvider(chunks=["a", "b", "c"])
        request = _simple_request(provider_key="fake", model="fake-model")
        chunks = [c async for c in provider.stream(request, cancel=EventCancellationToken())]
        assert [c.delta for c in chunks] == ["a", "b", "c"]
        assert chunks[-1].finish_reason == "stop"
        assert chunks[-1].tool_calls == ()

    def test_stream_chunk_defaults_empty_tool_calls(self) -> None:
        """LLMStreamChunk.tool_calls defaults to empty tuple."""
        chunk = LLMStreamChunk(delta="hi")
        assert chunk.tool_calls == ()

        chunk_with_finish = LLMStreamChunk(delta="", finish_reason="stop")
        assert chunk_with_finish.tool_calls == ()


# ---------------------------------------------------------------------------
# 2. Tool definitions translate correctly
# ---------------------------------------------------------------------------
class TestToolDefinitionTranslation:
    def test_single_tool_translates_to_openai_format(self) -> None:
        request = _simple_request(tools=(_weather_tool(),))
        result = _to_openai_tools(request)
        assert len(result) == 1
        assert result[0]["type"] == "function"
        func = result[0]["function"]
        assert func["name"] == "get_weather"
        assert func["description"] == "Get current weather for a city."
        assert func["parameters"]["type"] == "object"
        assert "city" in func["parameters"]["properties"]

    def test_multiple_tools_translate(self) -> None:
        request = _simple_request(tools=(_weather_tool(), _search_tool()))
        result = _to_openai_tools(request)
        assert len(result) == 2
        assert result[0]["function"]["name"] == "get_weather"
        assert result[1]["function"]["name"] == "web_search"

    def test_empty_tools_not_sent_to_openai(self) -> None:
        request = _simple_request(tools=())
        result = _to_openai_tools(request)
        assert result == []

    @pytest.mark.asyncio
    async def test_openai_sends_tools_kwarg_when_present(self) -> None:
        client = MagicMock()

        class EmptyStream:
            def __aiter__(self) -> EmptyStream:
                return self

            async def __anext__(self) -> object:
                raise StopAsyncIteration

        client.chat.completions.create = AsyncMock(return_value=EmptyStream())
        provider = OpenAILLMProvider(model="gpt-4o-mini", api_key=_SECRET, client=client)
        request = _simple_request(tools=(_weather_tool(),))
        _ = [c async for c in provider.stream(request, cancel=EventCancellationToken())]

        call_kwargs = client.chat.completions.create.call_args.kwargs
        assert "tools" in call_kwargs
        assert len(call_kwargs["tools"]) == 1
        assert call_kwargs["tools"][0]["function"]["name"] == "get_weather"


# ---------------------------------------------------------------------------
# 3. Single tool call normalized correctly
# ---------------------------------------------------------------------------
class TestSingleToolCall:
    @pytest.mark.asyncio
    async def test_openai_single_tool_call(self) -> None:
        """Single tool call streamed across chunks is accumulated and normalized."""
        client = MagicMock()

        # OpenAI sends: first chunk has tool_call id+name, second has args, third has finish
        stream_chunks = [
            SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(
                            content=None,
                            tool_calls=[
                                SimpleNamespace(
                                    index=0,
                                    id="call_abc123",
                                    function=SimpleNamespace(
                                        name="get_weather",
                                        arguments="",
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
                                        arguments='"London"}',
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

        class FakeStream:
            def __init__(self) -> None:
                self._items = list(stream_chunks)

            def __aiter__(self) -> FakeStream:
                return self

            async def __anext__(self) -> object:
                if not self._items:
                    raise StopAsyncIteration
                return self._items.pop(0)

        client.chat.completions.create = AsyncMock(return_value=FakeStream())
        provider = OpenAILLMProvider(model="gpt-4o-mini", api_key=_SECRET, client=client)
        request = _simple_request(tools=(_weather_tool(),))

        chunks = [c async for c in provider.stream(request, cancel=EventCancellationToken())]

        # Final chunk should have tool_calls
        final = chunks[-1]
        assert final.finish_reason == "tool_calls"
        assert len(final.tool_calls) == 1
        tc = final.tool_calls[0]
        assert tc.id == "call_abc123"
        assert tc.name == "get_weather"
        assert tc.arguments == '{"city":"London"}'

    @pytest.mark.asyncio
    async def test_fake_single_tool_call(self) -> None:
        tool_call = LLMToolCall(id="tc_1", name="get_weather", arguments='{"city":"NYC"}')
        provider = FakeLLMProvider(chunks=[""], tool_calls=[tool_call])
        request = _simple_request(provider_key="fake", model="fake-model")

        chunks = [c async for c in provider.stream(request, cancel=EventCancellationToken())]
        assert len(chunks) == 1
        assert chunks[0].finish_reason == "tool_calls"
        assert len(chunks[0].tool_calls) == 1
        assert chunks[0].tool_calls[0].name == "get_weather"


# ---------------------------------------------------------------------------
# 4. Multiple tool calls normalized correctly
# ---------------------------------------------------------------------------
class TestMultipleToolCalls:
    @pytest.mark.asyncio
    async def test_openai_multiple_tool_calls(self) -> None:
        """Two parallel tool calls streamed by OpenAI are accumulated correctly."""
        client = MagicMock()

        stream_chunks = [
            # First tool call starts
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
                                        name="get_weather",
                                        arguments='{"city":"London"}',
                                    ),
                                )
                            ],
                        ),
                        finish_reason=None,
                    )
                ]
            ),
            # Second tool call starts
            SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(
                            content=None,
                            tool_calls=[
                                SimpleNamespace(
                                    index=1,
                                    id="call_2",
                                    function=SimpleNamespace(
                                        name="web_search",
                                        arguments='{"query":"weather"}',
                                    ),
                                )
                            ],
                        ),
                        finish_reason=None,
                    )
                ]
            ),
            # Finish
            SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(content=None, tool_calls=None),
                        finish_reason="tool_calls",
                    )
                ]
            ),
        ]

        class FakeStream:
            def __init__(self) -> None:
                self._items = list(stream_chunks)

            def __aiter__(self) -> FakeStream:
                return self

            async def __anext__(self) -> object:
                if not self._items:
                    raise StopAsyncIteration
                return self._items.pop(0)

        client.chat.completions.create = AsyncMock(return_value=FakeStream())
        provider = OpenAILLMProvider(model="gpt-4o-mini", api_key=_SECRET, client=client)
        request = _simple_request(tools=(_weather_tool(), _search_tool()))

        chunks = [c async for c in provider.stream(request, cancel=EventCancellationToken())]
        final = chunks[-1]
        assert final.finish_reason == "tool_calls"
        assert len(final.tool_calls) == 2
        assert final.tool_calls[0].id == "call_1"
        assert final.tool_calls[0].name == "get_weather"
        assert final.tool_calls[1].id == "call_2"
        assert final.tool_calls[1].name == "web_search"

    @pytest.mark.asyncio
    async def test_fake_multiple_tool_calls(self) -> None:
        tcs = [
            LLMToolCall(id="tc_1", name="get_weather", arguments='{"city":"NYC"}'),
            LLMToolCall(id="tc_2", name="web_search", arguments='{"query":"test"}'),
        ]
        provider = FakeLLMProvider(chunks=["thinking..."], tool_calls=tcs)
        request = _simple_request(provider_key="fake", model="fake-model")

        chunks = [c async for c in provider.stream(request, cancel=EventCancellationToken())]
        assert chunks[-1].finish_reason == "tool_calls"
        assert len(chunks[-1].tool_calls) == 2
        assert chunks[-1].tool_calls[0].name == "get_weather"
        assert chunks[-1].tool_calls[1].name == "web_search"


# ---------------------------------------------------------------------------
# 5. Streamed tool-call argument fragments accumulated correctly
# ---------------------------------------------------------------------------
class TestToolCallArgumentAccumulation:
    @pytest.mark.asyncio
    async def test_fragmented_arguments_joined(self) -> None:
        """Arguments arriving in 4 separate fragments are correctly concatenated."""
        client = MagicMock()

        fragments = ['{"ci', "ty", '":"Lo', 'ndon"}']
        stream_items: list[object] = []

        # First chunk: id + name + first fragment
        stream_items.append(
            SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(
                            content=None,
                            tool_calls=[
                                SimpleNamespace(
                                    index=0,
                                    id="call_frag",
                                    function=SimpleNamespace(
                                        name="get_weather",
                                        arguments=fragments[0],
                                    ),
                                )
                            ],
                        ),
                        finish_reason=None,
                    )
                ]
            )
        )

        # Middle fragments
        for frag in fragments[1:]:
            stream_items.append(
                SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            delta=SimpleNamespace(
                                content=None,
                                tool_calls=[
                                    SimpleNamespace(
                                        index=0,
                                        id=None,
                                        function=SimpleNamespace(name=None, arguments=frag),
                                    )
                                ],
                            ),
                            finish_reason=None,
                        )
                    ]
                )
            )

        # Finish
        stream_items.append(
            SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(content=None, tool_calls=None),
                        finish_reason="tool_calls",
                    )
                ]
            )
        )

        class FakeStream:
            def __init__(self) -> None:
                self._items = list(stream_items)

            def __aiter__(self) -> FakeStream:
                return self

            async def __anext__(self) -> object:
                if not self._items:
                    raise StopAsyncIteration
                return self._items.pop(0)

        client.chat.completions.create = AsyncMock(return_value=FakeStream())
        provider = OpenAILLMProvider(model="gpt-4o-mini", api_key=_SECRET, client=client)
        request = _simple_request(tools=(_weather_tool(),))

        chunks = [c async for c in provider.stream(request, cancel=EventCancellationToken())]
        final = chunks[-1]
        assert len(final.tool_calls) == 1
        assert final.tool_calls[0].arguments == '{"city":"London"}'


# ---------------------------------------------------------------------------
# 6. Ordinary text streaming remains correct
# ---------------------------------------------------------------------------
class TestTextStreamingPreserved:
    @pytest.mark.asyncio
    async def test_openai_text_deltas_pass_through(self) -> None:
        """Text deltas still arrive as individual chunks."""
        client = MagicMock()

        class FakeStream:
            def __init__(self) -> None:
                self._chunks = [
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
                                finish_reason=None,
                            )
                        ]
                    ),
                    SimpleNamespace(
                        choices=[
                            SimpleNamespace(
                                delta=SimpleNamespace(content="C", tool_calls=None),
                                finish_reason="stop",
                            )
                        ]
                    ),
                ]

            def __aiter__(self) -> FakeStream:
                return self

            async def __anext__(self) -> object:
                if not self._chunks:
                    raise StopAsyncIteration
                return self._chunks.pop(0)

        client.chat.completions.create = AsyncMock(return_value=FakeStream())
        provider = OpenAILLMProvider(model="gpt-4o-mini", api_key=_SECRET, client=client)
        request = _simple_request()

        chunks = [c async for c in provider.stream(request, cancel=EventCancellationToken())]
        text = "".join(c.delta for c in chunks)
        assert text == "ABC"
        assert chunks[-1].finish_reason == "stop"
        assert all(c.tool_calls == () for c in chunks)


# ---------------------------------------------------------------------------
# 7. Cancellation stops processing correctly
# ---------------------------------------------------------------------------
class TestCancellation:
    @pytest.mark.asyncio
    async def test_openai_cancellation_during_tool_streaming(self) -> None:
        """Cancelling mid-stream stops yielding chunks."""
        client = MagicMock()

        class SlowStream:
            def __init__(self) -> None:
                self._items = [
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
                                    content="text",
                                    tool_calls=None,
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

            def __aiter__(self) -> SlowStream:
                return self

            async def __anext__(self) -> object:
                if not self._items:
                    raise StopAsyncIteration
                await asyncio.sleep(0.02)
                return self._items.pop(0)

        client.chat.completions.create = AsyncMock(return_value=SlowStream())
        provider = OpenAILLMProvider(model="gpt-4o-mini", api_key=_SECRET, client=client)
        request = _simple_request(tools=(_weather_tool(),))
        cancel = EventCancellationToken()

        collected: list[LLMStreamChunk] = []

        async def consume() -> None:
            async for chunk in provider.stream(request, cancel=cancel):
                collected.append(chunk)

        task = asyncio.create_task(consume())
        await asyncio.sleep(0.05)
        cancel.cancel()
        await task

        # Should not have received all chunks
        assert len(collected) < 3

    @pytest.mark.asyncio
    async def test_fake_cancellation_with_tool_calls(self) -> None:
        """FakeLLM cancellation during tool-call streaming."""
        tool_call = LLMToolCall(id="tc_1", name="get_weather", arguments="{}")
        provider = FakeLLMProvider(
            chunks=["a", "b", "c"],
            tool_calls=[tool_call],
            delay_seconds=0.05,
        )
        request = _simple_request(provider_key="fake", model="fake-model")
        cancel = EventCancellationToken()

        collected: list[str] = []

        async def consume() -> None:
            async for chunk in provider.stream(request, cancel=cancel):
                collected.append(chunk.delta)

        task = asyncio.create_task(consume())
        await asyncio.sleep(0.06)
        cancel.cancel()
        await task
        assert len(collected) < 3


# ---------------------------------------------------------------------------
# 8. Provider errors remain normalized
# ---------------------------------------------------------------------------
class TestErrorNormalization:
    @pytest.mark.asyncio
    async def test_openai_error_with_tools_still_normalized(self) -> None:
        """Provider errors are normalized even when tools are configured."""
        client = MagicMock()
        client.chat.completions.create = AsyncMock(
            side_effect=AuthenticationError(
                message="bad key",
                response=MagicMock(status_code=401, request=MagicMock()),
                body=None,
            )
        )
        provider = OpenAILLMProvider(model="gpt-4o-mini", api_key=_SECRET, client=client)
        request = _simple_request(tools=(_weather_tool(),))

        with pytest.raises(ProviderError) as exc_info:
            async for _ in provider.stream(request, cancel=EventCancellationToken()):
                pass

        assert exc_info.value.code == ProviderErrorCode.AUTH
        assert exc_info.value.provider_key == "openai"

    @pytest.mark.asyncio
    async def test_fake_error_with_tool_calls_configured(self) -> None:
        """FakeLLM raises configured error even with tool_calls set."""
        provider = FakeLLMProvider(
            tool_calls=[LLMToolCall(id="tc_1", name="fn", arguments="{}")],
            fail_with=ProviderError(
                code=ProviderErrorCode.PROVIDER,
                message="boom",
                provider_key="fake",
            ),
        )
        request = _simple_request(provider_key="fake", model="fake-model")

        with pytest.raises(ProviderError) as exc_info:
            async for _ in provider.stream(request, cancel=EventCancellationToken()):
                pass
        assert exc_info.value.code == ProviderErrorCode.PROVIDER


# ---------------------------------------------------------------------------
# 9. Provider SDK types do not leak
# ---------------------------------------------------------------------------
class TestNoLeakage:
    def test_tool_call_is_provider_neutral(self) -> None:
        """LLMToolCall is from contracts, not from any SDK."""
        tc = LLMToolCall(id="call_1", name="fn", arguments='{"x":1}')
        assert tc.__class__.__module__ == "xymphony_contracts.llm"

    def test_tool_definition_is_provider_neutral(self) -> None:
        """LLMToolDefinition is from contracts, not from any SDK."""
        td = _weather_tool()
        assert td.__class__.__module__ == "xymphony_contracts.llm"

    def test_stream_chunk_tool_calls_are_contract_types(self) -> None:
        """Tool calls in LLMStreamChunk are LLMToolCall, not SDK types."""
        tc = LLMToolCall(id="call_1", name="fn", arguments="{}")
        chunk = LLMStreamChunk(delta="", finish_reason="tool_calls", tool_calls=(tc,))
        assert chunk.tool_calls[0].__class__.__module__ == "xymphony_contracts.llm"

    def test_openai_adapter_does_not_import_into_contracts(self) -> None:
        """The contracts package should not import anything from openai."""
        import xymphony_contracts.llm as llm_mod

        source_file = llm_mod.__file__
        assert source_file is not None
        with open(source_file) as f:
            source = f.read()
        assert "openai" not in source
        assert "from openai" not in source
