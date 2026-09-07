"""Shared helpers for text→LLM→TTS runtime pipeline integration tests."""

from __future__ import annotations

from tests.helpers import make_session

from xymphony_contracts.enums import EventType
from xymphony_contracts.events import Event, validate_sequence_monotonic
from xymphony_providers.fake_llm import FakeLLMProvider
from xymphony_providers.fake_tts import FakeTTSProvider
from xymphony_runtime import (
    AgentRuntime,
    LLMRuntimeConfig,
    RuntimeContext,
    TTSRuntimeConfig,
)


def pipeline_context() -> RuntimeContext:
    session = make_session()
    assert session.config_hash is not None
    return RuntimeContext(
        session_id=session.id,
        organization_id=session.organization_id,
        project_id=session.project_id,
        agent_id=session.agent_id,
        agent_version_id=session.agent_version_id,
        config_hash=session.config_hash,
    )


def pipeline_llm_config() -> LLMRuntimeConfig:
    return LLMRuntimeConfig(provider_key="fake", model="fake-model")


def pipeline_tts_config() -> TTSRuntimeConfig:
    return TTSRuntimeConfig(provider_key="fake", voice_ref="voice_default")


def make_pipeline_runtime(
    *,
    llm_provider: FakeLLMProvider | None = None,
    tts_provider: FakeTTSProvider | None = None,
    llm_chunks: list[str] | None = None,
    llm_delay_seconds: float = 0,
    llm_fail_with: object = None,
    tts_chunks: list[str] | None = None,
    tts_delay_seconds: float = 0,
    tts_fail_with: object = None,
) -> AgentRuntime:
    if llm_provider is None:
        llm_kwargs: dict[str, object] = {}
        if llm_chunks is not None:
            llm_kwargs["chunks"] = llm_chunks
        if llm_delay_seconds:
            llm_kwargs["delay_seconds"] = llm_delay_seconds
        if llm_fail_with is not None:
            llm_kwargs["fail_with"] = llm_fail_with
        llm_provider = FakeLLMProvider(**llm_kwargs)

    if tts_provider is None:
        tts_kwargs: dict[str, object] = {}
        if tts_chunks is not None:
            tts_kwargs["chunks"] = tts_chunks
        if tts_delay_seconds:
            tts_kwargs["delay_seconds"] = tts_delay_seconds
        if tts_fail_with is not None:
            tts_kwargs["fail_with"] = tts_fail_with
        tts_provider = FakeTTSProvider(**tts_kwargs)

    return AgentRuntime(
        pipeline_context(),
        llm_provider=llm_provider,
        llm_config=pipeline_llm_config(),
        tts_provider=tts_provider,
        tts_config=pipeline_tts_config(),
    )


def turn_scoped_events(runtime: AgentRuntime, turn_id: object) -> list[Event]:
    return [event for event in runtime.admitted_events if event.turn_id == turn_id]


def assert_turn_event_metadata(runtime: AgentRuntime, turn_id: object) -> None:
    events = turn_scoped_events(runtime, turn_id)
    assert events, "expected turn-scoped events"
    for event in events:
        assert event.session_id == runtime.context.session_id
        assert event.turn_id == turn_id
    sequences = [event.sequence for event in runtime.admitted_events]
    assert validate_sequence_monotonic(sequences)


def assert_pipeline_event_order(events: list[Event]) -> None:
    llm_response_index = next(
        (index for index, event in enumerate(events) if event.type == EventType.LLM_RESPONSE),
        None,
    )
    assert llm_response_index is not None, "expected LLM response event"

    for index, event in enumerate(events):
        if event.type == EventType.LLM_TOKEN:
            assert index < llm_response_index
        if event.type == EventType.TTS_CHUNK:
            assert index > llm_response_index
