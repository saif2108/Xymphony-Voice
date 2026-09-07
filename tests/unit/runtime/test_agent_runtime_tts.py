"""Phase 2 Step 4 AgentRuntime + TTS provider integration tests."""

from __future__ import annotations

import asyncio

import pytest
from tests.helpers import make_session

from xymphony_contracts.enums import EventSource, EventType, TurnStatus
from xymphony_contracts.provider import ProviderError, ProviderErrorCode
from xymphony_providers.fake_llm import FakeLLMProvider
from xymphony_providers.fake_tts import FakeTTSProvider
from xymphony_runtime import (
    AgentRuntime,
    LLMRuntimeConfig,
    RuntimeContext,
    RuntimeInput,
    TTSRuntimeConfig,
)
from xymphony_runtime.dispatch import tts_chunk_event
from xymphony_runtime.turn import RuntimeTurnLifecycleState


def runtime_context() -> RuntimeContext:
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


def llm_config() -> LLMRuntimeConfig:
    return LLMRuntimeConfig(provider_key="fake", model="fake-model")


def tts_config() -> TTSRuntimeConfig:
    return TTSRuntimeConfig(provider_key="fake", voice_ref="voice_default")


@pytest.mark.asyncio
async def test_text_path_streams_tts_chunk_events_after_llm() -> None:
    runtime = AgentRuntime(
        runtime_context(),
        llm_provider=FakeLLMProvider(chunks=["hello"]),
        llm_config=llm_config(),
        tts_provider=FakeTTSProvider(),
        tts_config=tts_config(),
    )
    await runtime.start()
    await runtime.handle_input(RuntimeInput.text_input("hi"))

    turn = runtime.turns[0]
    tts_events = [event for event in runtime.admitted_events if event.type == EventType.TTS_CHUNK]
    assert len(tts_events) == 2
    assert all(event.turn_id == turn.id for event in tts_events)
    assert all(event.source == EventSource.TTS for event in tts_events)
    assert turn.state == RuntimeTurnLifecycleState.COMPLETED
    assert any(event.type == EventType.LLM_RESPONSE for event in runtime.admitted_events)


@pytest.mark.asyncio
async def test_tts_provider_is_injected_not_constructed_by_runtime() -> None:
    tts = FakeTTSProvider()
    runtime = AgentRuntime(
        runtime_context(),
        llm_provider=FakeLLMProvider(chunks=["ok"]),
        llm_config=llm_config(),
        tts_provider=tts,
        tts_config=tts_config(),
    )
    await runtime.start()
    await runtime.handle_input(RuntimeInput.text_input("ping"))
    assert len(tts.requests) == 1
    assert tts.requests[0].text == "ok"


@pytest.mark.asyncio
async def test_tts_provider_failure_emits_error_and_fails_turn() -> None:
    runtime = AgentRuntime(
        runtime_context(),
        llm_provider=FakeLLMProvider(chunks=["hello"]),
        llm_config=llm_config(),
        tts_provider=FakeTTSProvider(
            fail_with=ProviderError(
                code=ProviderErrorCode.PROVIDER,
                message="tts unavailable",
                provider_key="fake",
            )
        ),
        tts_config=tts_config(),
    )
    await runtime.start()
    await runtime.handle_input(RuntimeInput.text_input("fail"))

    turn = runtime.turns[0]
    assert turn.state == RuntimeTurnLifecycleState.FAILED
    assert turn.to_contract().status == TurnStatus.FAILED
    error_events = [event for event in runtime.admitted_events if event.type == EventType.ERROR]
    assert len(error_events) == 1


@pytest.mark.asyncio
async def test_tts_cancellation_stops_remaining_chunks() -> None:
    runtime = AgentRuntime(
        runtime_context(),
        llm_provider=FakeLLMProvider(chunks=["hello"]),
        llm_config=llm_config(),
        tts_provider=FakeTTSProvider(delay_seconds=0.05),
        tts_config=tts_config(),
    )
    await runtime.start()

    async def _run_turn() -> None:
        await runtime.handle_input(RuntimeInput.text_input("stream"))

    task = asyncio.create_task(_run_turn())
    await asyncio.sleep(0.06)
    await runtime.handle_input(RuntimeInput.cancel_turn())
    await task

    turn = runtime.turns[0]
    assert turn.state == RuntimeTurnLifecycleState.CANCELLED
    tts_events = [event for event in runtime.admitted_events if event.type == EventType.TTS_CHUNK]
    assert len(tts_events) < 2


@pytest.mark.asyncio
async def test_stale_tts_chunks_cannot_affect_new_turn() -> None:
    runtime = AgentRuntime(
        runtime_context(),
        llm_provider=FakeLLMProvider(chunks=["x"]),
        llm_config=llm_config(),
        tts_provider=FakeTTSProvider(chunks=["audio"]),
        tts_config=tts_config(),
    )
    await runtime.start()
    await runtime.handle_input(RuntimeInput.user_speech_started())
    cancelled_turn_id = runtime.current_turn_id
    assert cancelled_turn_id is not None
    await runtime.handle_input(RuntimeInput.cancel_turn())

    stale = tts_chunk_event(
        runtime.context,
        turn_id=cancelled_turn_id,
        audio_ref="stale-audio",
    )
    assert runtime.admit_event(stale) is False

    await runtime.handle_input(RuntimeInput.text_input("fresh"))
    second_turn = runtime.turns[1]
    tts_events = [
        event
        for event in runtime.admitted_events
        if event.type == EventType.TTS_CHUNK and event.turn_id == second_turn.id
    ]
    assert len(tts_events) == 1


@pytest.mark.asyncio
async def test_session_remains_usable_after_tts_turn_cancellation() -> None:
    runtime = AgentRuntime(
        runtime_context(),
        llm_provider=FakeLLMProvider(chunks=["a"]),
        llm_config=llm_config(),
        tts_provider=FakeTTSProvider(delay_seconds=0.05),
        tts_config=tts_config(),
    )
    await runtime.start()

    task = asyncio.create_task(runtime.handle_input(RuntimeInput.text_input("one")))
    await asyncio.sleep(0.06)
    await runtime.handle_input(RuntimeInput.cancel_turn())
    await task

    assert runtime.running is True
    await runtime.handle_input(RuntimeInput.text_input("two"))
    assert runtime.turns[1].state == RuntimeTurnLifecycleState.COMPLETED


@pytest.mark.asyncio
async def test_llm_only_path_unchanged_without_tts_provider() -> None:
    runtime = AgentRuntime(
        runtime_context(),
        llm_provider=FakeLLMProvider(chunks=["hello"]),
        llm_config=llm_config(),
    )
    await runtime.start()
    await runtime.handle_input(RuntimeInput.text_input("hi"))
    assert not any(event.type == EventType.TTS_CHUNK for event in runtime.admitted_events)
    assert runtime.turns[0].state == RuntimeTurnLifecycleState.COMPLETED
