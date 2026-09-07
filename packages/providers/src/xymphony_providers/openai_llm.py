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
        temperature = request.params.get("temperature")
        kwargs: dict[str, Any] = {
            "model": request.model or self._model,
            "messages": messages,
            "stream": True,
        }
        if isinstance(temperature, int | float):
            kwargs["temperature"] = float(temperature)

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
