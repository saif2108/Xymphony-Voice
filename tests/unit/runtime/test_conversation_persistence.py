"""Phase 2 Step 9 — session and conversation persistence runtime tests."""

from __future__ import annotations

import asyncio

import pytest
from tests.helpers import ORG, PROJECT, make_session
from tests.unit.runtime.bridge_helpers import bridge_transport_config, make_bridge
from tests.unit.runtime.pipeline_helpers import (
    make_pipeline_runtime,
    pipeline_llm_config,
    pipeline_tts_config,
)
from tests.unit.runtime.voice_helpers import make_voice_bridge, make_voice_runtime

from xymphony_contracts import CreateSessionRequest, EventType, MessageRole, SessionStatus
from xymphony_contracts.llm import LLMRole
from xymphony_contracts.stt import STTTranscriptChunk
from xymphony_providers.fake_llm import FakeLLMProvider
from xymphony_providers.fake_tts import FakeTTSProvider
from xymphony_realtime import FakeMediaTransport
from xymphony_runtime import (
    AgentRuntime,
    InMemoryConversationRepository,
    InMemorySessionRepository,
    RuntimeContext,
    RuntimeInput,
)
from xymphony_runtime.conversation import message_text
from xymphony_runtime.input import RuntimeInputKind


def _seed_session(sessions: InMemorySessionRepository) -> object:
    contract = make_session()
    assert contract.config_hash is not None
    return sessions.create_session(
        CreateSessionRequest(
            session_id=contract.id,
            organization_id=contract.organization_id,
            project_id=contract.project_id,
            agent_id=contract.agent_id,
            agent_version_id=contract.agent_version_id,
            config_hash=contract.config_hash,
        )
    )


def make_conversation_runtime(
    *,
    llm_provider: FakeLLMProvider | None = None,
    sessions: InMemorySessionRepository | None = None,
    conversation: InMemoryConversationRepository | None = None,
) -> tuple[AgentRuntime, InMemorySessionRepository, InMemoryConversationRepository]:
    resolved_sessions = sessions or InMemorySessionRepository()
    resolved_conversation = conversation or InMemoryConversationRepository()
    seeded = _seed_session(resolved_sessions)
    context = RuntimeContext(
        session_id=seeded.id,
        organization_id=seeded.organization_id,
        project_id=seeded.project_id,
        agent_id=seeded.agent_id,
        agent_version_id=seeded.agent_version_id,
        config_hash=seeded.config_hash,
    )
    runtime = AgentRuntime(
        context,
        llm_provider=llm_provider or FakeLLMProvider(chunks=["Hello there."]),
        llm_config=pipeline_llm_config(),
        tts_provider=FakeTTSProvider(chunks=["audio"]),
        tts_config=pipeline_tts_config(),
        session_repository=resolved_sessions,
        conversation_repository=resolved_conversation,
    )
    return runtime, resolved_sessions, resolved_conversation


@pytest.mark.asyncio
async def test_runtime_persists_user_and_assistant_messages() -> None:
    runtime, _sessions, conversation = make_conversation_runtime()
    await runtime.start()
    await runtime.handle_input(RuntimeInput(kind=RuntimeInputKind.TEXT_INPUT, text="Hi"))
    await runtime.stop()

    messages = conversation.list_messages(runtime.context.session_id, organization_id=ORG)
    assert len(messages) == 2
    assert message_text(messages[0]) == "Hi"
    assert messages[0].role == MessageRole.USER
    assert message_text(messages[1]) == "Hello there."
    assert messages[1].role == MessageRole.ASSISTANT


@pytest.mark.asyncio
async def test_multiple_turns_persist_in_order() -> None:
    runtime, _sessions, conversation = make_conversation_runtime()
    await runtime.start()
    await runtime.handle_input(RuntimeInput(kind=RuntimeInputKind.TEXT_INPUT, text="First"))
    await runtime.handle_input(RuntimeInput(kind=RuntimeInputKind.TEXT_INPUT, text="Second"))
    await runtime.stop()

    messages = conversation.list_messages(runtime.context.session_id, organization_id=ORG)
    assert len(messages) == 4
    assert message_text(messages[0]) == "First"
    assert message_text(messages[2]) == "Second"


@pytest.mark.asyncio
async def test_llm_receives_prior_conversation_history() -> None:
    llm = FakeLLMProvider(chunks=["Hello there."])
    runtime, _sessions, conversation = make_conversation_runtime(llm_provider=llm)
    await runtime.start()
    await runtime.handle_input(RuntimeInput(kind=RuntimeInputKind.TEXT_INPUT, text="First"))
    await runtime.handle_input(RuntimeInput(kind=RuntimeInputKind.TEXT_INPUT, text="Second"))
    await runtime.stop()

    assert len(llm.requests) == 2
    second_request = llm.requests[1]
    roles = [message.role for message in second_request.messages]
    contents = [message.content for message in second_request.messages]
    assert roles == [LLMRole.USER, LLMRole.ASSISTANT, LLMRole.USER]
    assert contents == ["First", "Hello there.", "Second"]
    assert len(conversation.list_messages(runtime.context.session_id)) == 4


@pytest.mark.asyncio
async def test_cancelled_turn_does_not_persist_assistant_message() -> None:
    llm = FakeLLMProvider(chunks=["Part 1", "Part 2"], delay_seconds=0.05)
    runtime, _sessions, conversation = make_conversation_runtime(llm_provider=llm)
    await runtime.start()
    turn_task = asyncio.create_task(
        runtime.handle_input(RuntimeInput(kind=RuntimeInputKind.TEXT_INPUT, text="Cancel me"))
    )
    await asyncio.sleep(0.01)
    turn_id = runtime.current_turn_id
    assert turn_id is not None
    await runtime.handle_input(RuntimeInput(kind=RuntimeInputKind.CANCEL_TURN, turn_id=turn_id))
    await turn_task
    await runtime.stop()

    messages = conversation.list_messages(runtime.context.session_id, organization_id=ORG)
    assert messages == ()


@pytest.mark.asyncio
async def test_new_turn_persists_after_cancellation() -> None:
    llm = FakeLLMProvider(chunks=["Hello there."], delay_seconds=0.05)
    runtime, _sessions, conversation = make_conversation_runtime(llm_provider=llm)
    await runtime.start()
    turn_task = asyncio.create_task(
        runtime.handle_input(RuntimeInput(kind=RuntimeInputKind.TEXT_INPUT, text="One"))
    )
    await asyncio.sleep(0.01)
    turn_id = runtime.current_turn_id
    assert turn_id is not None
    await runtime.handle_input(RuntimeInput(kind=RuntimeInputKind.CANCEL_TURN, turn_id=turn_id))
    await turn_task
    llm.delay_seconds = 0
    await runtime.handle_input(RuntimeInput(kind=RuntimeInputKind.TEXT_INPUT, text="Two"))
    await runtime.stop()

    messages = conversation.list_messages(runtime.context.session_id, organization_id=ORG)
    assert len(messages) == 2
    assert message_text(messages[0]) == "Two"
    assert message_text(messages[1]) == "Hello there."


@pytest.mark.asyncio
async def test_runtime_updates_session_status_on_start_and_stop() -> None:
    runtime, sessions, _conversation = make_conversation_runtime()
    await runtime.start()
    active = sessions.get_session(runtime.context.session_id, project_id=PROJECT)
    assert active is not None
    assert active.status == SessionStatus.ACTIVE
    await runtime.stop()
    ended = sessions.get_session(runtime.context.session_id, project_id=PROJECT)
    assert ended is not None
    assert ended.status == SessionStatus.TERMINATED
    assert ended.ended_at is not None


@pytest.mark.asyncio
async def test_existing_text_pipeline_still_works_without_conversation_repo() -> None:
    runtime = make_pipeline_runtime()
    await runtime.start()
    await runtime.handle_input(RuntimeInput(kind=RuntimeInputKind.TEXT_INPUT, text="Hi"))
    await runtime.stop()
    assert any(event.type == EventType.LLM_RESPONSE for event in runtime.admitted_events)


@pytest.mark.asyncio
async def test_existing_voice_pipeline_still_works_without_conversation_repo() -> None:
    bridge, _stt, transport = make_voice_bridge(
        runtime=make_voice_runtime(
            stt_chunks=[STTTranscriptChunk(text="hello there", is_final=True)],
        ),
    )
    run_task = asyncio.create_task(bridge.run(bridge_transport_config()))
    await asyncio.sleep(0)
    await transport.simulate_speech_utterance("browser-user", b"\x01\x02", duration_ms=20)
    await asyncio.sleep(0)
    await bridge.shutdown()
    await run_task
    assert any(event.type == EventType.LLM_RESPONSE for event in bridge.runtime_events)


@pytest.mark.asyncio
async def test_existing_tts_output_still_works_with_conversation_repo() -> None:
    runtime, _sessions, conversation = make_conversation_runtime()
    transport = FakeMediaTransport()
    bridge = make_bridge(runtime=runtime, transport=transport)

    run_task = asyncio.create_task(bridge.run(bridge_transport_config()))
    await asyncio.sleep(0)
    await bridge.handle_input(RuntimeInput.text_input("Speak this"))
    await asyncio.sleep(0)
    await bridge.shutdown()
    await run_task

    assert transport.published_output_frames
    assert len(conversation.list_messages(runtime.context.session_id)) == 2
