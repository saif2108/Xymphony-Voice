"""Minimal LLM/STT provider registry."""

from __future__ import annotations

import os

from xymphony_contracts.llm import LLMProvider
from xymphony_contracts.provider import ProviderError, ProviderErrorCode
from xymphony_contracts.stt import STTProvider
from xymphony_contracts.tts import TTSProvider
from xymphony_providers.assemblyai_stt import AssemblyAISTTProvider
from xymphony_providers.elevenlabs_tts import ElevenLabsTTSProvider
from xymphony_providers.openai_llm import OpenAILLMProvider

_LLM_SUPPORTED = frozenset({"openai"})
_STT_SUPPORTED = frozenset({"assemblyai"})
_TTS_SUPPORTED = frozenset({"elevenlabs"})
_LLM_ALIASES = {"openai_compatible": "openai"}


def normalize_llm_provider_key(provider_key: str) -> str:
    return _LLM_ALIASES.get(provider_key, provider_key)


def create_llm_provider(provider_key: str, *, model: str) -> LLMProvider:
    provider_key = normalize_llm_provider_key(provider_key)
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


def create_tts_provider(provider_key: str, *, voice_ref: str) -> TTSProvider:
    if provider_key not in _TTS_SUPPORTED:
        raise ProviderError(
            code=ProviderErrorCode.INVALID_REQUEST,
            message=f"unsupported tts provider_key: {provider_key}",
            provider_key=provider_key,
            retryable=False,
        )
    if provider_key == "elevenlabs":
        api_key = os.getenv("ELEVENLABS_API_KEY", "")
        configured_voice = os.getenv("ELEVENLABS_VOICE_ID", voice_ref)
        return ElevenLabsTTSProvider(api_key=api_key, default_voice_ref=configured_voice)
    raise ProviderError(
        code=ProviderErrorCode.INVALID_REQUEST,
        message=f"unsupported tts provider_key: {provider_key}",
        provider_key=provider_key,
        retryable=False,
    )
