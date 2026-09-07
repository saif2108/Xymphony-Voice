"""Phase 2 Step 6 RuntimeMediaBridge integration tests."""

from __future__ import annotations

import asyncio

import pytest
from tests.unit.runtime.bridge_helpers import bridge_transport_config, make_bridge

from xymphony_contracts.enums import EventType
from xymphony_contracts.media_transport import TransportConnectionState, TransportParticipantEvent
from xymphony_contracts.provider import ProviderError, ProviderErrorCode
from xymphony_providers.fake_llm import FakeLLMProvider
from xymphony_realtime import FakeMediaTransport
from xymphony_runtime import RuntimeInput, RuntimeMediaBridge, RuntimeSessionLifecycleState
from xymphony_runtime.dispatch import llm_token_event, tts_chunk_event
from xymphony_runtime.observations import LifecycleTransition
from xymphony_runtime.turn import RuntimeTurnLifecycleState


@pytest.mark.asyncio
async def test_bridge_starts_and_connects_transport() -> None:
    transport = FakeMediaTransport()
    bridge = make_bridge(transport=transport)

    run_task = asyncio.create_task(bridge.run(bridge_transport_config()))
    await asyncio.sleep(0)

    assert bridge.lifecycle_state == RuntimeSessionLifecycleState.CONNECTED
    assert bridge.runtime.running is True
    assert transport.connect_calls == 1
    assert TransportConnectionState.CONNECTED in bridge.connection_states
    assert any(event.type == EventType.SESSION_STARTED for event in bridge.runtime_events)

    await bridge.shutdown()
    await run_task

    assert bridge.lifecycle_state == RuntimeSessionLifecycleState.STOPPED
    assert bridge.runtime.running is False
    assert transport.disconnect_calls == 1


@pytest.mark.asyncio
async def test_bridge_records_transport_participant_observations() -> None:
    transport = FakeMediaTransport()
    transport.simulate_remote_join_identity = "browser-user"
    bridge = make_bridge(transport=transport)

    run_task = asyncio.create_task(bridge.run(bridge_transport_config()))
    await asyncio.sleep(0)

    participant_observations = [
        observation
        for observation in bridge.observations
        if isinstance(observation, TransportParticipantEvent)
    ]
    assert len(participant_observations) == 1
    assert participant_observations[0].identity == "browser-user"

    await bridge.shutdown()
    await run_task


@pytest.mark.asyncio
async def test_bridge_forwards_text_input_and_observes_runtime_events() -> None:
    bridge = make_bridge(llm_chunks=["hello"], tts_chunks=["audio-a", "audio-b"])

    run_task = asyncio.create_task(bridge.run(bridge_transport_config()))
    await asyncio.sleep(0)
    await bridge.handle_input(RuntimeInput.text_input("user message"))

    assert bridge.runtime.turns[0].state == RuntimeTurnLifecycleState.COMPLETED
    assert any(event.type == EventType.LLM_RESPONSE for event in bridge.runtime_events)
    assert any(event.type == EventType.TTS_CHUNK for event in bridge.runtime_events)
    assert len(bridge.assistant_output_events) >= 2

    await bridge.shutdown()
    await run_task


@pytest.mark.asyncio
async def test_bridge_runtime_events_are_not_duplicated() -> None:
    observed: list[EventType] = []
    bridge = make_bridge(llm_chunks=["ok"], tts_chunks=["audio"])
    bridge.on_runtime_event(lambda event: observed.append(event.type))

    run_task = asyncio.create_task(bridge.run(bridge_transport_config()))
    await asyncio.sleep(0)
    await bridge.handle_input(RuntimeInput.text_input("ping"))

    assert len(bridge.runtime_events) == len(bridge.runtime.admitted_events)
    assert len(observed) == len(bridge.runtime_events)

    await bridge.shutdown()
    await run_task


@pytest.mark.asyncio
async def test_transport_disconnect_causes_clean_shutdown() -> None:
    transport = FakeMediaTransport()
    bridge = make_bridge(transport=transport)

    run_task = asyncio.create_task(bridge.run(bridge_transport_config()))
    await asyncio.sleep(0)
    await transport.disconnect()
    await run_task

    assert bridge.lifecycle_state == RuntimeSessionLifecycleState.STOPPED
    assert bridge.runtime.running is False
    assert any(event.type == EventType.SESSION_ENDED for event in bridge.runtime_events)


@pytest.mark.asyncio
async def test_bridge_connect_failure_surfaces_runtime_error() -> None:
    transport = FakeMediaTransport()
    transport.fail_on_connect = True
    bridge = make_bridge(transport=transport)

    await bridge.run(bridge_transport_config())

    assert bridge.lifecycle_state == RuntimeSessionLifecycleState.FAILED
    assert bridge.runtime.running is False
    assert bridge.errors
    assert any(event.type == EventType.ERROR for event in bridge.runtime_events)


@pytest.mark.asyncio
async def test_bridge_shutdown_cleans_up_background_tasks() -> None:
    transport = FakeMediaTransport()
    bridge = make_bridge(transport=transport)
    before = {task for task in asyncio.all_tasks() if not task.done()}

    run_task = asyncio.create_task(bridge.run(bridge_transport_config()))
    await asyncio.sleep(0)
    await bridge.shutdown()
    await run_task

    after = {task for task in asyncio.all_tasks() if not task.done()}
    new_tasks = after - before
    assert run_task.done()
    assert not new_tasks


@pytest.mark.asyncio
async def test_bridge_turn_cancellation_still_works() -> None:
    bridge = make_bridge(llm_chunks=["a", "b", "c"], llm_delay_seconds=0.05)

    run_task = asyncio.create_task(bridge.run(bridge_transport_config()))
    await asyncio.sleep(0)

    turn_task = asyncio.create_task(bridge.handle_input(RuntimeInput.text_input("cancel-me")))
    await asyncio.sleep(0.06)
    await bridge.handle_input(RuntimeInput.cancel_turn())
    await turn_task

    turn = bridge.runtime.turns[0]
    assert turn.state == RuntimeTurnLifecycleState.CANCELLED
    assert not any(
        event.type == EventType.TTS_CHUNK and event.turn_id == turn.id
        for event in bridge.runtime_events
    )

    await bridge.shutdown()
    await run_task


@pytest.mark.asyncio
async def test_bridge_stale_events_remain_suppressed() -> None:
    bridge = make_bridge(llm_chunks=["x"], tts_chunks=["audio"])

    run_task = asyncio.create_task(bridge.run(bridge_transport_config()))
    await asyncio.sleep(0)
    await bridge.handle_input(RuntimeInput.user_speech_started())
    cancelled_turn_id = bridge.runtime.current_turn_id
    assert cancelled_turn_id is not None
    await bridge.handle_input(RuntimeInput.cancel_turn())

    assert bridge.runtime.admit_event(
        llm_token_event(bridge.runtime.context, turn_id=cancelled_turn_id, delta="stale")
    ) is False
    assert bridge.runtime.admit_event(
        tts_chunk_event(bridge.runtime.context, turn_id=cancelled_turn_id, audio_ref="stale")
    ) is False

    await bridge.shutdown()
    await run_task


@pytest.mark.asyncio
async def test_bridge_recovery_after_runtime_provider_failure() -> None:
    failing_llm = FakeLLMProvider(
        fail_with=ProviderError(
            code=ProviderErrorCode.PROVIDER,
            message="llm unavailable",
            provider_key="fake",
        )
    )
    bridge = make_bridge(llm_provider=failing_llm)

    run_task = asyncio.create_task(bridge.run(bridge_transport_config()))
    await asyncio.sleep(0)
    await bridge.handle_input(RuntimeInput.text_input("fail"))
    assert bridge.runtime.turns[0].state == RuntimeTurnLifecycleState.FAILED

    failing_llm.fail_with = None
    failing_llm.chunks = ["ok"]
    await bridge.handle_input(RuntimeInput.text_input("recover"))
    assert bridge.runtime.turns[1].state == RuntimeTurnLifecycleState.COMPLETED

    await bridge.shutdown()
    await run_task


@pytest.mark.asyncio
async def test_bridge_lifecycle_transitions() -> None:
    bridge = make_bridge()

    run_task = asyncio.create_task(bridge.run(bridge_transport_config()))
    await asyncio.sleep(0)
    await bridge.shutdown()
    await run_task

    lifecycle_states = [
        observation.state
        for observation in bridge.observations
        if isinstance(observation, LifecycleTransition)
    ]
    assert lifecycle_states[:3] == [
        RuntimeSessionLifecycleState.INITIALIZING,
        RuntimeSessionLifecycleState.CONNECTING,
        RuntimeSessionLifecycleState.CONNECTED,
    ]
    assert lifecycle_states[-1] == RuntimeSessionLifecycleState.STOPPED


@pytest.mark.asyncio
async def test_bridge_uses_injected_runtime_and_transport() -> None:
    runtime = make_bridge(llm_chunks=["ok"]).runtime
    transport = FakeMediaTransport()
    bridge = RuntimeMediaBridge(runtime=runtime, transport=transport)

    assert bridge.runtime is runtime
    assert bridge.transport is transport

    run_task = asyncio.create_task(bridge.run(bridge_transport_config()))
    await asyncio.sleep(0)
    await bridge.shutdown()
    await run_task

    assert transport.connect_calls == 1
