"""Phase 2 Step 1 AgentRuntime unit tests."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import pytest
from tests.helpers import make_session

from xymphony_contracts.enums import EventType, SessionStatus, TurnStatus
from xymphony_runtime import (
    AgentRuntime,
    InvalidRuntimeInputError,
    InvalidStateTransitionError,
    RuntimeContext,
    RuntimeInput,
    RuntimeNotRunningError,
    RuntimeStreamChunk,
    StreamChunkKind,
)
from xymphony_runtime.dispatch import llm_token_event
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


@dataclass
class FakeOutputSink:
    chunks: list[RuntimeStreamChunk] = field(default_factory=list)

    async def emit(self, chunk: RuntimeStreamChunk) -> None:
        self.chunks.append(chunk)


@pytest.mark.asyncio
async def test_runtime_starts_and_stops_cleanly() -> None:
    runtime = AgentRuntime(runtime_context())
    await runtime.start()
    assert runtime.running is True
    assert runtime.context.session_status == SessionStatus.ACTIVE
    assert runtime.admitted_events[0].type == EventType.SESSION_STARTED

    await runtime.stop()
    assert runtime.running is False
    assert runtime.context.session_status == SessionStatus.TERMINATED
    assert runtime.admitted_events[-1].type == EventType.SESSION_ENDED


@pytest.mark.asyncio
async def test_text_input_creates_and_completes_turn() -> None:
    runtime = AgentRuntime(runtime_context())
    await runtime.start()
    await runtime.handle_input(RuntimeInput.text_input("hello"))

    assert len(runtime.turns) == 1
    turn = runtime.turns[0]
    assert turn.state == RuntimeTurnLifecycleState.COMPLETED
    assert turn.to_contract().status == TurnStatus.COMMITTED
    assert runtime.current_turn_id is None


@pytest.mark.asyncio
async def test_turn_can_be_cancelled() -> None:
    runtime = AgentRuntime(runtime_context())
    await runtime.start()
    await runtime.handle_input(RuntimeInput.user_speech_started())
    turn_id = runtime.current_turn_id
    assert turn_id is not None

    await runtime.handle_input(RuntimeInput.cancel_turn())
    turn = runtime.turns[0]
    assert turn.state == RuntimeTurnLifecycleState.CANCELLED
    assert turn_id in runtime.context.cancelled_turn_ids
    assert any(event.type == EventType.AGENT_INTERRUPTED for event in runtime.admitted_events)


@pytest.mark.asyncio
async def test_cancelled_turn_does_not_affect_next_turn() -> None:
    runtime = AgentRuntime(runtime_context())
    await runtime.start()

    await runtime.handle_input(RuntimeInput.user_speech_started())
    first_turn_id = runtime.current_turn_id
    assert first_turn_id is not None
    await runtime.handle_input(RuntimeInput.cancel_turn())

    await runtime.handle_input(RuntimeInput.text_input("second turn"))
    assert len(runtime.turns) == 2
    second_turn = runtime.turns[1]
    assert second_turn.state == RuntimeTurnLifecycleState.COMPLETED
    assert second_turn.id not in runtime.context.cancelled_turn_ids


@pytest.mark.asyncio
async def test_stale_events_from_cancelled_turn_are_rejected() -> None:
    runtime = AgentRuntime(runtime_context())
    await runtime.start()
    await runtime.handle_input(RuntimeInput.user_speech_started())
    turn_id = runtime.current_turn_id
    assert turn_id is not None
    await runtime.handle_input(RuntimeInput.cancel_turn())

    stale = llm_token_event(runtime.context, turn_id=turn_id, delta="stale")
    assert runtime.admit_event(stale) is False
    assert stale not in runtime.admitted_events


@pytest.mark.asyncio
async def test_session_remains_alive_after_turn_cancellation() -> None:
    runtime = AgentRuntime(runtime_context())
    await runtime.start()
    await runtime.handle_input(RuntimeInput.user_speech_started())
    await runtime.handle_input(RuntimeInput.cancel_turn())

    assert runtime.running is True
    assert runtime.context.session_status == SessionStatus.ACTIVE


@pytest.mark.asyncio
async def test_runtime_shutdown_cancels_active_turn() -> None:
    runtime = AgentRuntime(runtime_context())
    await runtime.start()
    await runtime.handle_input(RuntimeInput.user_speech_started())
    turn_id = runtime.current_turn_id
    assert turn_id is not None

    await runtime.stop()
    assert runtime.running is False
    assert runtime.turns[0].state == RuntimeTurnLifecycleState.CANCELLED
    assert turn_id in runtime.context.cancelled_turn_ids


@pytest.mark.asyncio
async def test_invalid_state_transition_is_deterministic() -> None:
    runtime = AgentRuntime(runtime_context())
    await runtime.start()
    await runtime.handle_input(RuntimeInput.text_input("done"))
    turn = runtime.turns[0]

    with pytest.raises(InvalidStateTransitionError):
        turn.complete()

    with pytest.raises(InvalidRuntimeInputError):
        await runtime.handle_input(RuntimeInput.user_speech_ended())


@pytest.mark.asyncio
async def test_multiple_sequential_turns() -> None:
    runtime = AgentRuntime(runtime_context())
    await runtime.start()

    for idx in range(3):
        await runtime.handle_input(RuntimeInput.text_input(f"message-{idx}"))

    assert len(runtime.turns) == 3
    assert all(turn.state == RuntimeTurnLifecycleState.COMPLETED for turn in runtime.turns)
    assert runtime.current_turn_id is None


@pytest.mark.asyncio
async def test_stream_chunks_ignore_cancelled_turn() -> None:
    sink = FakeOutputSink()
    runtime = AgentRuntime(runtime_context(), output_sink=sink)
    await runtime.start()
    await runtime.handle_input(RuntimeInput.user_speech_started())
    turn_id = runtime.current_turn_id
    assert turn_id is not None
    await runtime.handle_input(RuntimeInput.cancel_turn())

    accepted = await runtime.emit_stream_chunk(
        RuntimeStreamChunk(
            turn_id=turn_id,
            session_sequence=99,
            kind=StreamChunkKind.LLM_TOKEN,
            payload="ignored",
        )
    )
    assert accepted is False
    assert sink.chunks == []


@pytest.mark.asyncio
async def test_handle_input_requires_running_runtime() -> None:
    runtime = AgentRuntime(runtime_context())
    with pytest.raises(RuntimeNotRunningError):
        await runtime.handle_input(RuntimeInput.text_input("hello"))


@pytest.mark.asyncio
async def test_no_dangling_tasks_after_shutdown() -> None:
    runtime = AgentRuntime(runtime_context())
    before = {task for task in asyncio.all_tasks() if not task.done()}

    async def _worker() -> None:
        await runtime.start()
        await runtime.handle_input(RuntimeInput.user_speech_started())
        await asyncio.sleep(0)
        await runtime.stop()

    await _worker()
    after = {task for task in asyncio.all_tasks() if not task.done()}
    assert after.issubset(before)
