"""Minimal LLM/STT provider registry."""

from __future__ import annotations

import os

from xymphony_contracts.llm import LLMProvider
from xymphony_contracts.provider import ProviderError, ProviderErrorCode
from xymphony_contracts.stt import STTProvider
from xymphony_providers.assemblyai_stt import AssemblyAISTTProvider
from xymphony_providers.openai_llm import OpenAILLMProvider

_LLM_SUPPORTED = frozenset({"openai"})
_STT_SUPPORTED = frozenset({"assemblyai"})


def create_llm_provider(provider_key: str, *, model: str) -> LLMProvider:
    if provider_key not in _LLM_SUPPORTED:
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


def create_stt_provider(provider_key: str, *, model: str) -> STTProvider:
    if provider_key not in _STT_SUPPORTED:
        raise ProviderError(
            code=ProviderErrorCode.INVALID_REQUEST,
            message=f"unsupported stt provider_key: {provider_key}",
            provider_key=provider_key,
            retryable=False,
        )
    if provider_key == "assemblyai":
        api_key = os.getenv("ASSEMBLYAI_API_KEY", "")
        configured_model = os.getenv("ASSEMBLYAI_MODEL", model)
        return AssemblyAISTTProvider(api_key=api_key, model=configured_model)
    raise ProviderError(
        code=ProviderErrorCode.INVALID_REQUEST,
        message=f"unsupported stt provider_key: {provider_key}",
        provider_key=provider_key,
        retryable=False,
    )
