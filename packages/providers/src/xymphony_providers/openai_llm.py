"""OpenAI LLM adapter. Uses official SDK; credentials from configuration only."""

from __future__ import annotations

from collections.abc import AsyncIterator
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
    ProviderError,
    ProviderErrorCode,
)
from xymphony_contracts.usage import Usage

_OPENAI_PROVIDER_KEY = "openai"


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

        try:
            stream = await self._client.chat.completions.create(**kwargs)
            async for chunk in stream:
                if cancel.cancelled:
                    return
                choice = chunk.choices[0] if chunk.choices else None
                if choice is None:
                    continue
                delta = choice.delta.content or ""
                finish_reason = choice.finish_reason
                if delta or finish_reason:
                    yield LLMStreamChunk(delta=delta, finish_reason=finish_reason)
        except Exception as exc:
            raise _normalize_openai_error(exc) from exc


def _to_openai_messages(request: LLMRequest) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if request.system:
        messages.append({"role": "system", "content": request.system})
    for message in request.messages:
        messages.append({"role": message.role.value, "content": message.content})
    return messages


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
