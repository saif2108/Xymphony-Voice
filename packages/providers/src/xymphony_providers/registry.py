"""Minimal LLM provider registry."""

from __future__ import annotations

import os

from xymphony_contracts.llm import LLMProvider, ProviderError, ProviderErrorCode
from xymphony_providers.openai_llm import OpenAILLMProvider

_SUPPORTED = frozenset({"openai"})


def create_llm_provider(provider_key: str, *, model: str) -> LLMProvider:
    if provider_key not in _SUPPORTED:
        raise ProviderError(
            code=ProviderErrorCode.INVALID_REQUEST,
            message=f"unsupported llm provider_key: {provider_key}",
            provider_key=provider_key,
            retryable=False,
        )
    if provider_key == "openai":
        api_key = os.getenv("OPENAI_API_KEY", "")
        configured_model = os.getenv("OPENAI_MODEL", model)
        return OpenAILLMProvider(model=configured_model, api_key=api_key)
    raise ProviderError(
        code=ProviderErrorCode.INVALID_REQUEST,
        message=f"unsupported llm provider_key: {provider_key}",
        provider_key=provider_key,
        retryable=False,
    )
