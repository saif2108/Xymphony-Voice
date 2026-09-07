"""Phase 2 Step 3 AgentRuntime + STT provider integration tests."""

from __future__ import annotations

import asyncio

import pytest
from tests.helpers import make_session

from xymphony_contracts.enums import EventSource, EventType, TurnStatus
from xymphony_contracts.provider import ProviderError, ProviderErrorCode
from xymphony_contracts.stt import STTTranscriptChunk
from xymphony_providers.fake_stt import FakeSTTProvider
from xymphony_runtime import AgentRuntime, RuntimeContext, RuntimeInput, STTRuntimeConfig
from xymphony_runtime.dispatch import transcript_frame_event
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


def stt_config() -> STTRuntimeConfig:
    return STTRuntimeConfig(provider_key="fake", model="fake-model")


async def _speech_with_audio(
    runtime: AgentRuntime,
    *,
    audio: bytes = b"\x00\x01",
    duration_ms: int = 10,
) -> None:
    await runtime.handle_input(RuntimeInput.user_speech_started())
    await runtime.handle_input(RuntimeInput.audio_frame(audio, duration_ms=duration_ms))
    await runtime.handle_input(RuntimeInput.user_speech_ended())


@pytest.mark.asyncio
async def test_fake_stt_emits_transcript_frame_events() -> None:
    provider = FakeSTTProvider()
    runtime = AgentRuntime(runtime_context(), stt_provider=provider, stt_config=stt_config())
    await runtime.start()
    await _speech_with_audio(runtime)

    turn = runtime.turns[0]
    transcript_events = [
        event for event in runtime.admitted_events if event.type == EventType.TRANSCRIPT_FRAME
    ]
    assert len(transcript_events) == 2
    assert all(event.turn_id == turn.id for event in transcript_events)
    assert all(event.source == EventSource.STT for event in transcript_events)
    assert transcript_events[-1].payload.is_final is True
    assert turn.state == RuntimeTurnLifecycleState.COMPLETED


@pytest.mark.asyncio
async def test_stt_provider_is_injected_not_constructed_by_runtime() -> None:
    provider = FakeSTTProvider()
    runtime = AgentRuntime(runtime_context(), stt_provider=provider, stt_config=stt_config())
    await runtime.start()
    await _speech_with_audio(runtime)
    assert len(provider.requests) == 1
    assert len(provider.received_frames) == 1


@pytest.mark.asyncio
async def test_stt_provider_failure_emits_error_and_fails_turn() -> None:
    provider = FakeSTTProvider(
        fail_with=ProviderError(
            code=ProviderErrorCode.PROVIDER,
            message="stt unavailable",
            provider_key="fake",
        )
    )
    runtime = AgentRuntime(runtime_context(), stt_provider=provider, stt_config=stt_config())
    await runtime.start()
    await _speech_with_audio(runtime)

    turn = runtime.turns[0]
    assert turn.state == RuntimeTurnLifecycleState.FAILED
    assert turn.to_contract().status == TurnStatus.FAILED
    error_events = [event for event in runtime.admitted_events if event.type == EventType.ERROR]
    assert len(error_events) == 1
    assert "sk-" not in error_events[0].payload.message


@pytest.mark.asyncio
async def test_stt_cancellation_stops_remaining_transcript_chunks() -> None:
    provider = FakeSTTProvider(delay_seconds=0.05)
    runtime = AgentRuntime(runtime_context(), stt_provider=provider, stt_config=stt_config())
    await runtime.start()
    await runtime.handle_input(RuntimeInput.user_speech_started())
    await runtime.handle_input(RuntimeInput.audio_frame(b"\x00", duration_ms=10))

    async def _finish_speech() -> None:
        await runtime.handle_input(RuntimeInput.user_speech_ended())

    finish_task = asyncio.create_task(_finish_speech())
    await asyncio.sleep(0.06)
    await runtime.handle_input(RuntimeInput.cancel_turn())
    await finish_task

    turn = runtime.turns[0]
    assert turn.state == RuntimeTurnLifecycleState.CANCELLED
    transcript_events = [
        event for event in runtime.admitted_events if event.type == EventType.TRANSCRIPT_FRAME
    ]
    assert len(transcript_events) < 2


@pytest.mark.asyncio
async def test_stale_transcript_cannot_affect_new_turn() -> None:
    runtime = AgentRuntime(
        runtime_context(),
        stt_provider=FakeSTTProvider(
            chunks=[STTTranscriptChunk(text="ok", is_final=True)],
        ),
        stt_config=stt_config(),
    )
    await runtime.start()
    await runtime.handle_input(RuntimeInput.user_speech_started())
    cancelled_turn_id = runtime.current_turn_id
    assert cancelled_turn_id is not None
    await runtime.handle_input(RuntimeInput.cancel_turn())

    stale = transcript_frame_event(
        runtime.context,
        turn_id=cancelled_turn_id,
        text="stale",
        is_final=False,
    )
    assert runtime.admit_event(stale) is False

    await _speech_with_audio(runtime)
    second_turn = runtime.turns[1]
    transcript_events = [
        event
        for event in runtime.admitted_events
        if event.type == EventType.TRANSCRIPT_FRAME and event.turn_id == second_turn.id
    ]
    assert len(transcript_events) == 1


@pytest.mark.asyncio
async def test_multiple_sequential_speech_turns_with_stt() -> None:
    runtime = AgentRuntime(
        runtime_context(),
        stt_provider=FakeSTTProvider(
            chunks=[STTTranscriptChunk(text="ok", is_final=True)],
        ),
        stt_config=stt_config(),
    )
    await runtime.start()
    for _ in range(3):
        await _speech_with_audio(runtime)
    assert len(runtime.turns) == 3
    assert all(turn.state == RuntimeTurnLifecycleState.COMPLETED for turn in runtime.turns)


@pytest.mark.asyncio
async def test_speech_without_stt_provider_preserves_immediate_completion() -> None:
    runtime = AgentRuntime(runtime_context())
    await runtime.start()
    await runtime.handle_input(RuntimeInput.user_speech_started())
    await runtime.handle_input(RuntimeInput.user_speech_ended())
    assert runtime.turns[0].state == RuntimeTurnLifecycleState.COMPLETED
    assert not any(
        event.type == EventType.TRANSCRIPT_FRAME for event in runtime.admitted_events
    )
