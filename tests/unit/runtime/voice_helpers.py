"""Shared helpers for speech→STT→runtime bridge integration tests."""

from __future__ import annotations

from tests.unit.runtime.pipeline_helpers import (
    pipeline_context,
    pipeline_llm_config,
    pipeline_tts_config,
)

from xymphony_providers.fake_llm import FakeLLMProvider
from xymphony_providers.fake_stt import FakeSTTProvider
from xymphony_providers.fake_tts import FakeTTSProvider
from xymphony_realtime import FakeMediaTransport
from xymphony_runtime import AgentRuntime, RuntimeMediaBridge, STTRuntimeConfig


def make_voice_runtime(
    *,
    llm_provider: FakeLLMProvider | None = None,
    stt_provider: FakeSTTProvider | None = None,
    tts_provider: FakeTTSProvider | None = None,
    llm_chunks: list[str] | None = None,
    stt_chunks: object = None,
    stt_delay_seconds: float = 0,
    stt_fail_with: object = None,
    tts_chunks: list[str] | None = None,
) -> AgentRuntime:
    if llm_provider is None:
        llm_provider = FakeLLMProvider(chunks=llm_chunks or ["assistant reply"])
    if stt_provider is None:
        stt_kwargs: dict[str, object] = {}
        if stt_chunks is not None:
            stt_kwargs["chunks"] = stt_chunks
        if stt_delay_seconds:
            stt_kwargs["delay_seconds"] = stt_delay_seconds
        if stt_fail_with is not None:
            stt_kwargs["fail_with"] = stt_fail_with
        stt_provider = FakeSTTProvider(**stt_kwargs)

    kwargs: dict[str, object] = {
        "llm_provider": llm_provider,
        "llm_config": pipeline_llm_config(),
        "stt_provider": stt_provider,
        "stt_config": STTRuntimeConfig(provider_key="fake", model="fake-model"),
    }
    if tts_provider is not None or tts_chunks is not None:
        kwargs["tts_provider"] = tts_provider or FakeTTSProvider(chunks=tts_chunks or ["audio"])
        kwargs["tts_config"] = pipeline_tts_config()

    return AgentRuntime(pipeline_context(), **kwargs)


def make_voice_bridge(
    *,
    runtime: AgentRuntime | None = None,
    transport: FakeMediaTransport | None = None,
    stt_provider: FakeSTTProvider | None = None,
    **runtime_kwargs: object,
) -> tuple[RuntimeMediaBridge, FakeSTTProvider, FakeMediaTransport]:
    stt = stt_provider or FakeSTTProvider()
    resolved_runtime = runtime or make_voice_runtime(stt_provider=stt, **runtime_kwargs)
    resolved_transport = transport or FakeMediaTransport()
    return (
        RuntimeMediaBridge(runtime=resolved_runtime, transport=resolved_transport),
        stt,
        resolved_transport,
    )
