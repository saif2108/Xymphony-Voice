"""Phase 2 Step 5 end-to-end text→LLM→TTS runtime pipeline integration tests."""

from __future__ import annotations

import asyncio

import pytest
from tests.unit.runtime.pipeline_helpers import (
    assert_pipeline_event_order,
    assert_turn_event_metadata,
    make_pipeline_runtime,
    turn_scoped_events,
)

from xymphony_contracts.enums import EventType, TurnStatus
from xymphony_contracts.provider import ProviderError, ProviderErrorCode
from xymphony_providers.fake_llm import FakeLLMProvider
from xymphony_providers.fake_tts import FakeTTSProvider
from xymphony_runtime import RuntimeInput
from xymphony_runtime.dispatch import llm_token_event, tts_chunk_event
from xymphony_runtime.turn import RuntimeTurnLifecycleState


@pytest.mark.asyncio
async def test_end_to_end_text_llm_tts_pipeline() -> None:
    llm = ["Hello", " world"]
    tts = FakeTTSProvider(chunks=["audio-a", "audio-b"])
    runtime = make_pipeline_runtime(
        llm_provider=FakeLLMProvider(chunks=llm),
        tts_provider=tts,
    )
    await runtime.start()
    await runtime.handle_input(RuntimeInput.text_input("user message"))

    turn = runtime.turns[0]
    assert turn.state == RuntimeTurnLifecycleState.COMPLETED
    assert turn.to_contract().status == TurnStatus.COMMITTED

    events = turn_scoped_events(runtime, turn.id)
    assert [event.type for event in events if event.type == EventType.LLM_TOKEN]
    assert any(event.type == EventType.LLM_RESPONSE for event in events)
    assert len([event for event in events if event.type == EventType.TTS_CHUNK]) == 2
    assert len(tts.requests) == 1
    assert tts.requests[0].text == "Hello world"


@pytest.mark.asyncio
async def test_pipeline_event_ordering_guarantees() -> None:
    runtime = make_pipeline_runtime(
        llm_chunks=["one", " two"],
        tts_chunks=["chunk-0", "chunk-1"],
    )
    await runtime.start()
    await runtime.handle_input(RuntimeInput.text_input("order"))

    turn = runtime.turns[0]
    events = turn_scoped_events(runtime, turn.id)
    assert_pipeline_event_order(events)
    assert_turn_event_metadata(runtime, turn.id)


@pytest.mark.asyncio
async def test_multiple_sequential_text_pipeline_turns() -> None:
    runtime = make_pipeline_runtime(
        llm_chunks=["ok"],
        tts_chunks=["audio"],
    )
    await runtime.start()
    for idx in range(3):
        await runtime.handle_input(RuntimeInput.text_input(f"message-{idx}"))

    assert len(runtime.turns) == 3
    assert all(turn.state == RuntimeTurnLifecycleState.COMPLETED for turn in runtime.turns)
    for turn in runtime.turns:
        events = turn_scoped_events(runtime, turn.id)
        assert any(event.type == EventType.LLM_RESPONSE for event in events)
        assert any(event.type == EventType.TTS_CHUNK for event in events)


@pytest.mark.asyncio
async def test_cancellation_during_llm_prevents_tts() -> None:
    runtime = make_pipeline_runtime(llm_chunks=["a", "b", "c"], llm_delay_seconds=0.05)
    await runtime.start()

    task = asyncio.create_task(runtime.handle_input(RuntimeInput.text_input("cancel-me")))
    await asyncio.sleep(0.06)
    await runtime.handle_input(RuntimeInput.cancel_turn())
    await task

    turn = runtime.turns[0]
    assert turn.state == RuntimeTurnLifecycleState.CANCELLED
    assert not any(
        event.type == EventType.TTS_CHUNK and event.turn_id == turn.id
        for event in runtime.admitted_events
    )


@pytest.mark.asyncio
async def test_cancellation_during_tts_stops_remaining_output() -> None:
    runtime = make_pipeline_runtime(
        llm_chunks=["hello"],
        tts_delay_seconds=0.05,
    )
    await runtime.start()

    task = asyncio.create_task(runtime.handle_input(RuntimeInput.text_input("stream")))
    await asyncio.sleep(0.06)
    await runtime.handle_input(RuntimeInput.cancel_turn())
    await task

    turn = runtime.turns[0]
    assert turn.state == RuntimeTurnLifecycleState.CANCELLED
    tts_events = [
        event for event in runtime.admitted_events if event.type == EventType.TTS_CHUNK
    ]
    assert len(tts_events) < 2


@pytest.mark.asyncio
async def test_stale_pipeline_output_cannot_reach_new_turn() -> None:
    runtime = make_pipeline_runtime(llm_chunks=["x"], tts_chunks=["audio"])
    await runtime.start()
    await runtime.handle_input(RuntimeInput.user_speech_started())
    cancelled_turn_id = runtime.current_turn_id
    assert cancelled_turn_id is not None
    await runtime.handle_input(RuntimeInput.cancel_turn())

    assert runtime.admit_event(
        llm_token_event(runtime.context, turn_id=cancelled_turn_id, delta="stale")
    ) is False
    assert runtime.admit_event(
        tts_chunk_event(runtime.context, turn_id=cancelled_turn_id, audio_ref="stale")
    ) is False

    await runtime.handle_input(RuntimeInput.text_input("fresh"))
    second_turn = runtime.turns[1]
    assert second_turn.state == RuntimeTurnLifecycleState.COMPLETED
    assert all(
        event.turn_id == second_turn.id
        for event in turn_scoped_events(runtime, second_turn.id)
        if event.type in {EventType.LLM_TOKEN, EventType.LLM_RESPONSE, EventType.TTS_CHUNK}
    )


@pytest.mark.asyncio
async def test_session_remains_usable_after_pipeline_cancellation() -> None:
    runtime = make_pipeline_runtime(llm_chunks=["a"], tts_delay_seconds=0.05)
    await runtime.start()

    task = asyncio.create_task(runtime.handle_input(RuntimeInput.text_input("one")))
    await asyncio.sleep(0.06)
    await runtime.handle_input(RuntimeInput.cancel_turn())
    await task

    assert runtime.running is True
    await runtime.handle_input(RuntimeInput.text_input("two"))
    assert runtime.turns[1].state == RuntimeTurnLifecycleState.COMPLETED


@pytest.mark.asyncio
async def test_llm_failure_before_tts_does_not_invoke_tts() -> None:
    tts = FakeTTSProvider()
    runtime = make_pipeline_runtime(
        llm_fail_with=ProviderError(
            code=ProviderErrorCode.PROVIDER,
            message="llm unavailable",
            provider_key="fake",
        ),
        tts_provider=tts,
    )
    await runtime.start()
    await runtime.handle_input(RuntimeInput.text_input("fail"))

    turn = runtime.turns[0]
    assert turn.state == RuntimeTurnLifecycleState.FAILED
    assert tts.requests == []
    assert not any(event.type == EventType.TTS_CHUNK for event in runtime.admitted_events)


@pytest.mark.asyncio
async def test_tts_failure_after_successful_llm_response() -> None:
    runtime = make_pipeline_runtime(
        llm_chunks=["hello"],
        tts_fail_with=ProviderError(
            code=ProviderErrorCode.PROVIDER,
            message="tts unavailable",
            provider_key="fake",
        ),
    )
    await runtime.start()
    await runtime.handle_input(RuntimeInput.text_input("fail-tts"))

    turn = runtime.turns[0]
    assert turn.state == RuntimeTurnLifecycleState.FAILED
    assert any(event.type == EventType.LLM_RESPONSE for event in runtime.admitted_events)
    assert not any(event.type == EventType.TTS_CHUNK for event in runtime.admitted_events)
    assert any(event.type == EventType.ERROR for event in runtime.admitted_events)


@pytest.mark.asyncio
async def test_recovery_after_llm_failure() -> None:
    failing_llm = FakeLLMProvider(
        fail_with=ProviderError(
            code=ProviderErrorCode.PROVIDER,
            message="llm unavailable",
            provider_key="fake",
        )
    )
    runtime = make_pipeline_runtime(llm_provider=failing_llm)
    await runtime.start()
    await runtime.handle_input(RuntimeInput.text_input("fail"))
    assert runtime.turns[0].state == RuntimeTurnLifecycleState.FAILED

    failing_llm.fail_with = None
    failing_llm.chunks = ["ok"]
    await runtime.handle_input(RuntimeInput.text_input("recover"))
    assert runtime.turns[1].state == RuntimeTurnLifecycleState.COMPLETED


@pytest.mark.asyncio
async def test_recovery_after_tts_failure() -> None:
    failing_tts = FakeTTSProvider(
        fail_with=ProviderError(
            code=ProviderErrorCode.PROVIDER,
            message="tts unavailable",
            provider_key="fake",
        )
    )
    runtime = make_pipeline_runtime(
        llm_provider=FakeLLMProvider(chunks=["hello"]),
        tts_provider=failing_tts,
    )
    await runtime.start()
    await runtime.handle_input(RuntimeInput.text_input("fail"))
    assert runtime.turns[0].state == RuntimeTurnLifecycleState.FAILED

    failing_tts.fail_with = None
    failing_tts.chunks = ["audio"]
    await runtime.handle_input(RuntimeInput.text_input("recover"))
    assert runtime.turns[1].state == RuntimeTurnLifecycleState.COMPLETED
