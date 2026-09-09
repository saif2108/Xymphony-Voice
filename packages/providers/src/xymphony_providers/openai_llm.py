"""OpenAI LLM adapter. Uses official SDK; credentials from configuration only."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from openai import (
    APIConnectionError,
    APIStatusError,
    AsyncOpenAI,
    AuthenticationError,
    RateLimitError,
)

from xymphony_contracts.enums import UsageUnit
from xymphony_contracts.llm import (
    CancellationToken,
    LLMRequest,
    LLMStreamChunk,
    LLMToolCall,
    ProviderError,
    ProviderErrorCode,
)
from xymphony_contracts.usage import Usage

_OPENAI_PROVIDER_KEY = "openai"


@dataclass
class _ToolCallAccumulator:
    """Accumulates streamed tool-call deltas for a single tool call."""

    id: str = ""
    name: str = ""
    arguments: str = ""


@dataclass
class _ToolCallCollector:
    """Collects all tool-call accumulators across streamed chunks."""

    _accumulators: dict[int, _ToolCallAccumulator] = field(default_factory=dict)

    def feed_delta(self, tool_call_delta: Any) -> None:
        """Process one tool-call delta from an OpenAI streamed chunk."""
        index: int = getattr(tool_call_delta, "index", 0)
        acc = self._accumulators.get(index)
        if acc is None:
            acc = _ToolCallAccumulator()
            self._accumulators[index] = acc

        tc_id = getattr(tool_call_delta, "id", None)
        if tc_id:
            acc.id = tc_id

        func = getattr(tool_call_delta, "function", None)
        if func is not None:
            fn_name = getattr(func, "name", None)
            if fn_name:
                acc.name += fn_name
            fn_args = getattr(func, "arguments", None)
            if fn_args:
                acc.arguments += fn_args

    def to_tool_calls(self) -> tuple[LLMToolCall, ...]:
        """Convert accumulated deltas to provider-neutral LLMToolCall objects."""
        if not self._accumulators:
            return ()
        result: list[LLMToolCall] = []
        for _index in sorted(self._accumulators):
            acc = self._accumulators[_index]
            result.append(
                LLMToolCall(
                    id=acc.id or f"call_{_index}",
                    name=acc.name,
                    arguments=acc.arguments or "{}",
                )
            )
        return tuple(result)

    @property
    def has_tool_calls(self) -> bool:
        return bool(self._accumulators)


class OpenAILLMProvider:
    def __init__(self, *, model: str, api_key: str, client: AsyncOpenAI | None = None) -> None:
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAI LLM provider")
        self._model = model
        self._client = client or AsyncOpenAI(api_key=api_key)

    @property
    def provider_key(self) -> str:
        return _OPENAI_PROVIDER_KEY

    async def stream(
        self,
        request: LLMRequest,
        *,
        cancel: CancellationToken,
    ) -> AsyncIterator[LLMStreamChunk]:
        messages = _to_openai_messages(request)
        kwargs: dict[str, Any] = {
            "model": request.model or self._model,
            "messages": messages,
            "stream": True,
        }
        temperature = request.temperature
        if temperature is None:
            raw_temp = request.params.get("temperature")
            if isinstance(raw_temp, int | float) and not isinstance(raw_temp, bool):
                temperature = float(raw_temp)
        if temperature is not None:
            kwargs["temperature"] = temperature

        top_p = request.top_p
        if top_p is None:
            raw_top_p = request.params.get("top_p")
            if isinstance(raw_top_p, int | float) and not isinstance(raw_top_p, bool):
                top_p = float(raw_top_p)
        if top_p is not None:
            kwargs["top_p"] = top_p

        max_output_tokens = request.max_output_tokens
        if max_output_tokens is None:
            raw_tokens = (
                request.params.get("max_output_tokens")
                or request.params.get("max_completion_tokens")
                or request.params.get("max_tokens")
            )
            if (
                isinstance(raw_tokens, int)
                and not isinstance(raw_tokens, bool)
                and raw_tokens >= 1
            ):
                max_output_tokens = raw_tokens
        if max_output_tokens is not None:
            kwargs["max_completion_tokens"] = max_output_tokens

        if request.tools:
            kwargs["tools"] = _to_openai_tools(request)

        tool_collector = _ToolCallCollector()

        try:
            stream = await self._client.chat.completions.create(**kwargs)
            async for chunk in stream:
                if cancel.cancelled:
                    return
                choice = chunk.choices[0] if chunk.choices else None
                if choice is None:
                    continue

                # Accumulate tool-call deltas if present
                delta_tool_calls = getattr(choice.delta, "tool_calls", None)
                if delta_tool_calls:
                    for tc_delta in delta_tool_calls:
                        tool_collector.feed_delta(tc_delta)

                delta = choice.delta.content or ""
                finish_reason = choice.finish_reason

                if delta or finish_reason:
                    # Attach accumulated tool calls on the final chunk
                    completed_tools = (
                        tool_collector.to_tool_calls()
                        if finish_reason
                        else ()
                    )
                    yield LLMStreamChunk(
                        delta=delta,
                        finish_reason=finish_reason,
                        tool_calls=completed_tools,
                    )
                elif delta_tool_calls and not delta and not finish_reason:
                    # Tool-call-only delta chunk (no text, no finish) — continue accumulating
                    continue
        except Exception as exc:
            raise _normalize_openai_error(exc) from exc


def _to_openai_messages(request: LLMRequest) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if request.system:
        messages.append({"role": "system", "content": request.system})
    for message in request.messages:
        messages.append({"role": message.role.value, "content": message.content})
    return messages


def _to_openai_tools(request: LLMRequest) -> list[dict[str, Any]]:
    """Translate provider-neutral LLMToolDefinition to OpenAI's tool format."""
    tools: list[dict[str, Any]] = []
    for tool_def in request.tools:
        tools.append({
            "type": "function",
            "function": {
                "name": tool_def.name,
                "description": tool_def.description,
                "parameters": tool_def.parameters,
            },
        })
    return tools


def _normalize_openai_error(exc: Exception) -> ProviderError:
    if isinstance(exc, AuthenticationError):
        return ProviderError(
            code=ProviderErrorCode.AUTH,
            message="authentication failed",
            provider_key=_OPENAI_PROVIDER_KEY,
            retryable=False,
        )
    if isinstance(exc, RateLimitError):
        return ProviderError(
            code=ProviderErrorCode.RATE_LIMIT,
            message="rate limit exceeded",
            provider_key=_OPENAI_PROVIDER_KEY,
            retryable=True,
        )
    if isinstance(exc, APIConnectionError):
        return ProviderError(
            code=ProviderErrorCode.TIMEOUT,
            message="connection failed",
            provider_key=_OPENAI_PROVIDER_KEY,
            retryable=True,
        )
    if isinstance(exc, APIStatusError):
        return ProviderError(
            code=ProviderErrorCode.PROVIDER,
            message=f"provider error status={exc.status_code}",
            provider_key=_OPENAI_PROVIDER_KEY,
            retryable=exc.status_code >= 500,
        )
    return ProviderError(
        code=ProviderErrorCode.UNKNOWN,
        message=str(exc),
        provider_key=_OPENAI_PROVIDER_KEY,
        retryable=False,
    )


def usage_from_openai(usage: Any) -> Usage | None:
    if usage is None:
        return None
    prompt = getattr(usage, "prompt_tokens", None)
    completion = getattr(usage, "completion_tokens", None)
    if prompt is None or completion is None:
        return None
    return Usage(input_units=int(prompt), output_units=int(completion), unit=UsageUnit.TOKENS)
