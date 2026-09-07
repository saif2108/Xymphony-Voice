"""MinimalTransportSession lifecycle with FakeMediaTransport."""

import asyncio

import pytest

from xymphony_contracts.media_transport import (
    MediaTransportConfig,
    TransportConnectionState,
    TransportErrorEvent,
    TransportParticipantEvent,
)
from xymphony_realtime import FakeMediaTransport
from xymphony_runtime import MinimalTransportSession, RuntimeSessionLifecycleState
from xymphony_runtime.observations import LifecycleTransition


def _config() -> MediaTransportConfig:
    return MediaTransportConfig(
        url="wss://example.livekit.cloud",
        room_name="dev-room",
        participant_identity="worker",
        token="token",
    )


@pytest.mark.asyncio
async def test_minimal_session_runs_until_shutdown() -> None:
    transport = FakeMediaTransport()
    transport.simulate_remote_join_identity = "browser-user"
    session = MinimalTransportSession(session_id="sess-1")

    run_task = asyncio.create_task(session.run(transport, _config()))
    await asyncio.sleep(0)
    await session.shutdown()
    await run_task

    assert transport.connect_calls == 1
    assert transport.disconnect_calls == 1
    assert session.lifecycle_state == RuntimeSessionLifecycleState.STOPPED
    assert TransportConnectionState.CONNECTED in session.connection_states
    assert any(e.identity == "browser-user" for e in session.participant_events)


@pytest.mark.asyncio
async def test_successful_lifecycle_transitions() -> None:
    transport = FakeMediaTransport()
    session = MinimalTransportSession(session_id="sess-2")

    run_task = asyncio.create_task(session.run(transport, _config()))
    await asyncio.sleep(0)
    await session.shutdown()
    await run_task

    lifecycle_states = [
        obs.state
        for obs in session.observations
        if isinstance(obs, LifecycleTransition)
    ]
    assert lifecycle_states[:3] == [
        RuntimeSessionLifecycleState.INITIALIZING,
        RuntimeSessionLifecycleState.CONNECTING,
        RuntimeSessionLifecycleState.CONNECTED,
    ]
    assert lifecycle_states[-1] == RuntimeSessionLifecycleState.STOPPED


@pytest.mark.asyncio
async def test_connect_failure_marks_failed_and_disconnects() -> None:
    transport = FakeMediaTransport()
    transport.fail_on_connect = True
    session = MinimalTransportSession(session_id="sess-3")

    await session.run(transport, _config())

    assert session.lifecycle_state == RuntimeSessionLifecycleState.FAILED
    assert transport.connect_calls == 1
    assert transport.disconnect_calls == 1
    assert any(isinstance(e, TransportErrorEvent) for e in session.errors)


@pytest.mark.asyncio
async def test_transport_disconnect_stops_session() -> None:
    transport = FakeMediaTransport()
    session = MinimalTransportSession(session_id="sess-4")

    run_task = asyncio.create_task(session.run(transport, _config()))
    await asyncio.sleep(0)
    await transport.disconnect()
    await run_task

    assert session.lifecycle_state == RuntimeSessionLifecycleState.STOPPED
    assert transport.disconnect_calls >= 1


@pytest.mark.asyncio
async def test_shutdown_during_connected_session() -> None:
    transport = FakeMediaTransport()
    session = MinimalTransportSession(session_id="sess-5")

    run_task = asyncio.create_task(session.run(transport, _config()))
    await asyncio.sleep(0)
    assert session.lifecycle_state == RuntimeSessionLifecycleState.CONNECTED
    await session.shutdown()
    await run_task

    assert session.lifecycle_state == RuntimeSessionLifecycleState.STOPPED


@pytest.mark.asyncio
async def test_participant_events_are_observable() -> None:
    transport = FakeMediaTransport()
    transport.simulate_remote_join_identity = "browser-user"
    session = MinimalTransportSession(session_id="sess-6")

    run_task = asyncio.create_task(session.run(transport, _config()))
    await asyncio.sleep(0)
    await transport.simulate_remote_leave("browser-user")
    await session.shutdown()
    await run_task

    participant_observations = [
        obs for obs in session.observations if isinstance(obs, TransportParticipantEvent)
    ]
    assert len(participant_observations) == 2
    assert participant_observations[0].identity == "browser-user"
    assert participant_observations[1].identity == "browser-user"


@pytest.mark.asyncio
async def test_no_dangling_tasks_after_shutdown() -> None:
    transport = FakeMediaTransport()
    session = MinimalTransportSession(session_id="sess-7")
    before = {task for task in asyncio.all_tasks() if not task.done()}

    run_task = asyncio.create_task(session.run(transport, _config()))
    await asyncio.sleep(0)
    await session.shutdown()
    await run_task

    after = {task for task in asyncio.all_tasks() if not task.done()}
    new_tasks = after - before
    assert run_task.done()
    assert not new_tasks
