"""Phase 2 Step 10 — full realtime voice worker integration tests."""

from __future__ import annotations

import asyncio

import pytest
from tests.helpers import make_agent_version, make_session
from tests.unit.runtime.bridge_helpers import bridge_transport_config
from tests.unit.runtime.voice_helpers import make_voice_bridge

from xymphony_contracts import CreateSessionRequest, EventType, MessageRole
from xymphony_contracts.provider import ProviderError, ProviderErrorCode
from xymphony_contracts.stt import STTTranscriptChunk
from xymphony_providers.fake_llm import FakeLLMProvider
from xymphony_providers.fake_stt import FakeSTTProvider
from xymphony_providers.fake_tts import FakeTTSProvider
from xymphony_providers.registry import normalize_llm_provider_key
from xymphony_realtime import FakeMediaTransport
from xymphony_runtime import (
    InMemoryConversationRepository,
    InMemorySessionRepository,
    RuntimeInput,
    RuntimeSessionLifecycleState,
    RuntimeWorkerSession,
)
from xymphony_runtime.conversation import message_text
from xymphony_runtime_worker.bootstrap import (
    VoiceWorkerComponents,
    build_voice_worker,
    runtime_configs_from_version,
    runtime_context_from_session,
)


def _seed_repos() -> tuple[InMemorySessionRepository, InMemoryConversationRepository, object]:
    sessions = InMemorySessionRepository()
    conversation = InMemoryConversationRepository()
    contract = make_session()
    assert contract.config_hash is not None
    seeded = sessions.create_session(
        CreateSessionRequest(
            session_id=contract.id,
            organization_id=contract.organization_id,
            project_id=contract.project_id,
            agent_id=contract.agent_id,
            agent_version_id=contract.agent_version_id,
            config_hash=contract.config_hash,
        )
    )
    return sessions, conversation, seeded


def _make_worker(
    *,
    llm_provider: FakeLLMProvider | None = None,
    stt_provider: FakeSTTProvider | None = None,
    tts_provider: FakeTTSProvider | None = None,
    transport: FakeMediaTransport | None = None,
    llm_chunks: list[str] | None = None,
    stt_chunks: object = None,
    tts_chunks: list[str] | None = None,
    tts_chunk_audio: dict[str, bytes] | None = None,
) -> VoiceWorkerComponents:
    sessions, conversation, seeded = _seed_repos()
    version = make_agent_version(id=seeded.agent_version_id)
    return build_voice_worker(
        session=seeded,
        agent_version=version,
        session_repository=sessions,
        conversation_repository=conversation,
        transport=transport or FakeMediaTransport(),
        llm_provider=llm_provider
        or FakeLLMProvider(chunks=llm_chunks or ["Hello from the assistant."]),
        stt_provider=stt_provider
        or FakeSTTProvider(
            chunks=stt_chunks or [STTTranscriptChunk(text="hello user", is_final=True)],
        ),
        tts_provider=tts_provider
        or FakeTTSProvider(
            chunks=tts_chunks or ["out-0", "out-1"],
            chunk_audio=tts_chunk_audio,
        ),
    )


def test_worker_builds_runtime_with_injected_providers() -> None:
    llm = FakeLLMProvider(chunks=["ok"])
    stt = FakeSTTProvider()
    tts = FakeTTSProvider(chunks=["a"])
    components = _make_worker(llm_provider=llm, stt_provider=stt, tts_provider=tts)
    assert components.runtime._llm_provider is llm  # noqa: SLF001
    assert components.runtime._stt_provider is stt  # noqa: SLF001
    assert components.runtime._tts_provider is tts  # noqa: SLF001


def test_worker_builds_runtime_media_bridge() -> None:
    components = _make_worker()
    assert components.bridge.runtime is components.runtime
    assert components.bridge.transport is not None


def test_session_pinned_to_agent_version() -> None:
    components = _make_worker()
    assert components.runtime.context.agent_version_id == components.agent_version.id
    assert components.session.agent_version_id == components.agent_version.id


def test_runtime_configs_use_pinned_version_instructions() -> None:
    version = make_agent_version(instructions="Speak briefly.")
    llm_config, _, _ = runtime_configs_from_version(version)
    assert llm_config.system_instructions == "Speak briefly."


def test_openai_compatible_alias_normalizes() -> None:
    assert normalize_llm_provider_key("openai_compatible") == "openai"
    assert normalize_llm_provider_key("openai") == "openai"


@pytest.mark.asyncio
async def test_fake_voice_path_end_to_end() -> None:
    transport = FakeMediaTransport()
    components = _make_worker(transport=transport, tts_chunk_audio={"out-0": b"\x01\x00" * 80})
    run_task = asyncio.create_task(components.bridge.run(bridge_transport_config()))
    await asyncio.sleep(0)

    await transport.simulate_speech_utterance("browser-user", b"\x00\x01", duration_ms=20)
    await asyncio.sleep(0)

    transcript_events = [
        event for event in components.bridge.runtime_events
        if event.type == EventType.TRANSCRIPT_FRAME
    ]
    assert transcript_events
    assert any(
        event.type == EventType.LLM_RESPONSE for event in components.bridge.runtime_events
    )
    assert len(components.bridge.published_output_frames) >= 1

    await components.bridge.shutdown()
    await run_task


@pytest.mark.asyncio
async def test_multiple_conversational_turns() -> None:
    transport = FakeMediaTransport()
    components = _make_worker(
        transport=transport,
        llm_chunks=["one", "two"],
        stt_chunks=[STTTranscriptChunk(text="first", is_final=True)],
    )
    components.runtime._stt_provider = FakeSTTProvider(  # noqa: SLF001
        chunks=[STTTranscriptChunk(text="first", is_final=True)]
    )
    run_task = asyncio.create_task(components.bridge.run(bridge_transport_config()))
    await asyncio.sleep(0)

    await transport.simulate_speech_utterance("user", b"\x01", duration_ms=10)
    await asyncio.sleep(0)
    components.runtime._stt_provider = FakeSTTProvider(  # noqa: SLF001
        chunks=[STTTranscriptChunk(text="second", is_final=True)]
    )
    await transport.simulate_speech_utterance("user", b"\x02", duration_ms=10)
    await asyncio.sleep(0)

    assert len(components.runtime.turns) == 2
    await components.bridge.shutdown()
    await run_task


@pytest.mark.asyncio
async def test_conversation_history_reaches_llm() -> None:
    sessions, conversation, seeded = _seed_repos()
    version = make_agent_version(id=seeded.agent_version_id)
    llm = FakeLLMProvider(chunks=["reply"])

    seed_runtime = build_voice_worker(
        session=seeded,
        agent_version=version,
        session_repository=sessions,
        conversation_repository=conversation,
        llm_provider=llm,
        stt_provider=FakeSTTProvider(),
        tts_provider=FakeTTSProvider(chunks=["audio"]),
    )
    await seed_runtime.runtime.start()
    await seed_runtime.runtime.handle_input(RuntimeInput.text_input("seed history"))
    await asyncio.sleep(0)
    await seed_runtime.runtime.stop()

    transport = FakeMediaTransport()
    components = build_voice_worker(
        session=seeded,
        agent_version=version,
        session_repository=sessions,
        conversation_repository=conversation,
        transport=transport,
        llm_provider=llm,
        stt_provider=FakeSTTProvider(
            chunks=[STTTranscriptChunk(text="follow up", is_final=True)],
        ),
        tts_provider=FakeTTSProvider(chunks=["audio"]),
    )
    run_task = asyncio.create_task(components.bridge.run(bridge_transport_config()))
    await asyncio.sleep(0)
    await transport.simulate_speech_utterance("user", b"\x01", duration_ms=10)
    await asyncio.sleep(0)

    assert len(llm.requests) >= 2
    last_messages = llm.requests[-1].messages
    assert any(message.content == "seed history" for message in last_messages)

    await components.bridge.shutdown()
    await run_task


@pytest.mark.asyncio
async def test_barge_in_cancels_stale_output() -> None:
    slow_tts = FakeTTSProvider(chunks=["slow-0", "slow-1"], delay_seconds=0.15)
    transport = FakeMediaTransport()
    components = _make_worker(
        transport=transport,
        tts_provider=slow_tts,
        llm_chunks=["long reply"],
    )
    run_task = asyncio.create_task(components.bridge.run(bridge_transport_config()))
    await asyncio.sleep(0)

    text_task = asyncio.create_task(
        components.runtime.handle_input(RuntimeInput.text_input("trigger slow tts"))
    )
    await asyncio.sleep(0.05)
    active_turn = components.runtime.current_turn
    assert active_turn is not None
    await transport.simulate_audio_input_started("user")
    await asyncio.sleep(0.3)
    await text_task

    assert active_turn.state.value == "cancelled"
    frames_for_turn = [
        frame
        for frame in transport.published_output_frames
        if frame.turn_id == str(active_turn.id)
    ]
    assert len(frames_for_turn) <= 2

    await components.bridge.shutdown()
    await run_task


@pytest.mark.asyncio
async def test_new_turn_works_after_cancellation() -> None:
    transport = FakeMediaTransport()
    components = _make_worker(transport=transport)
    run_task = asyncio.create_task(components.bridge.run(bridge_transport_config()))
    await asyncio.sleep(0)

    await transport.simulate_speech_utterance("user", b"\x01", duration_ms=10)
    await asyncio.sleep(0)
    first_turn = components.runtime.turns[0]
    await components.runtime.handle_input(RuntimeInput.cancel_turn(first_turn.id))
    components.runtime._stt_provider = FakeSTTProvider(  # noqa: SLF001
        chunks=[STTTranscriptChunk(text="after cancel", is_final=True)],
    )
    await transport.simulate_speech_utterance("user", b"\x02", duration_ms=10)
    await asyncio.sleep(0)

    assert len(components.runtime.turns) == 2
    assert components.runtime.turns[1].state.value == "completed"

    await components.bridge.shutdown()
    await run_task


@pytest.mark.asyncio
async def test_tts_chunks_preserve_order() -> None:
    transport = FakeMediaTransport()
    components = _make_worker(
        transport=transport,
        tts_chunks=["a", "b", "c"],
        tts_chunk_audio={"a": b"\x01", "b": b"\x02", "c": b"\x03"},
    )
    run_task = asyncio.create_task(components.bridge.run(bridge_transport_config()))
    await asyncio.sleep(0)
    await transport.simulate_speech_utterance("user", b"\x01", duration_ms=10)
    await asyncio.sleep(0)

    indexes = [frame.chunk_index for frame in transport.published_output_frames]
    assert indexes == sorted(indexes)

    await components.bridge.shutdown()
    await run_task


@pytest.mark.asyncio
async def test_transport_disconnect_cleans_up_runtime() -> None:
    transport = FakeMediaTransport()
    components = _make_worker(transport=transport)
    run_task = asyncio.create_task(components.bridge.run(bridge_transport_config()))
    await asyncio.sleep(0)
    await transport.disconnect()
    await run_task

    assert components.bridge.lifecycle_state == RuntimeSessionLifecycleState.STOPPED
    assert not components.runtime.running


@pytest.mark.asyncio
async def test_provider_failure_does_not_complete_turn_as_success() -> None:
    failing_llm = FakeLLMProvider(
        fail_with=ProviderError(
            code=ProviderErrorCode.UNKNOWN,
            message="llm failed",
            provider_key="fake",
            retryable=False,
        )
    )
    transport = FakeMediaTransport()
    components = _make_worker(
        transport=transport,
        llm_provider=failing_llm,
        stt_provider=FakeSTTProvider(
            chunks=[STTTranscriptChunk(text="hello", is_final=True)],
        ),
    )
    run_task = asyncio.create_task(components.bridge.run(bridge_transport_config()))
    await asyncio.sleep(0)
    await transport.simulate_speech_utterance("user", b"\x01", duration_ms=10)
    await asyncio.sleep(0)

    turn = components.runtime.turns[0]
    assert turn.state.value == "failed"
    llm_responses = [
        event for event in components.bridge.runtime_events
        if event.type == EventType.LLM_RESPONSE
    ]
    assert not llm_responses

    await components.bridge.shutdown()
    await run_task


@pytest.mark.asyncio
async def test_cancelled_turn_does_not_persist_assistant_message() -> None:
    sessions, conversation, seeded = _seed_repos()
    version = make_agent_version(id=seeded.agent_version_id)
    transport = FakeMediaTransport()
    components = build_voice_worker(
        session=seeded,
        agent_version=version,
        session_repository=sessions,
        conversation_repository=conversation,
        transport=transport,
        llm_provider=FakeLLMProvider(chunks=["should not persist"]),
        stt_provider=FakeSTTProvider(
            chunks=[STTTranscriptChunk(text="cancel me", is_final=True)],
        ),
        tts_provider=FakeTTSProvider(chunks=["audio"]),
    )
    await components.runtime.start()
    await components.runtime.handle_input(RuntimeInput.user_speech_started())
    turn = components.runtime.current_turn
    assert turn is not None
    await components.runtime.handle_input(RuntimeInput.cancel_turn(turn.id))
    await components.runtime.stop()

    messages = conversation.list_messages(seeded.id, organization_id=seeded.organization_id)
    assert not any(message.role == MessageRole.ASSISTANT for message in messages)


@pytest.mark.asyncio
async def test_worker_session_lifecycle_with_bridge() -> None:
    transport = FakeMediaTransport()
    components = _make_worker(transport=transport)
    worker = RuntimeWorkerSession(components.bridge)
    config = bridge_transport_config()
    run_task = asyncio.create_task(worker.run(config))
    await asyncio.sleep(0)
    await worker.shutdown()
    await run_task

    assert worker.lifecycle_state == RuntimeSessionLifecycleState.STOPPED
    assert transport.connect_calls == 1
    assert transport.disconnect_calls == 1


@pytest.mark.asyncio
async def test_existing_text_pipeline_still_works() -> None:
    components = _make_worker()
    await components.runtime.start()
    await components.runtime.handle_input(RuntimeInput.text_input("hello"))
    await asyncio.sleep(0)
    await components.runtime.stop()
    assert any(event.type == EventType.LLM_RESPONSE for event in components.runtime.admitted_events)


@pytest.mark.asyncio
async def test_existing_voice_bridge_helpers_still_work() -> None:
    bridge, _stt, transport = make_voice_bridge()
    run_task = asyncio.create_task(bridge.run(bridge_transport_config()))
    await asyncio.sleep(0)
    await transport.simulate_speech_utterance("browser-user", b"\x01", duration_ms=10)
    await asyncio.sleep(0)
    await bridge.shutdown()
    await run_task
    assert bridge.runtime.turns[0].state.value == "completed"


def test_runtime_context_from_session() -> None:
    session = make_session()
    context = runtime_context_from_session(session)
    assert context.session_id == session.id
    assert context.agent_version_id == session.agent_version_id


@pytest.mark.asyncio
async def test_persisted_messages_after_successful_turn() -> None:
    sessions, conversation, seeded = _seed_repos()
    version = make_agent_version(id=seeded.agent_version_id)
    components = build_voice_worker(
        session=seeded,
        agent_version=version,
        session_repository=sessions,
        conversation_repository=conversation,
        transport=FakeMediaTransport(),
        llm_provider=FakeLLMProvider(chunks=["saved reply"]),
        stt_provider=FakeSTTProvider(),
        tts_provider=FakeTTSProvider(chunks=["audio"]),
    )

    await components.runtime.start()
    await components.runtime.handle_input(RuntimeInput.text_input("hello there"))
    await asyncio.sleep(0)
    await components.runtime.stop()

    messages = conversation.list_messages(seeded.id, organization_id=seeded.organization_id)
    roles = [message.role for message in messages]
    assert MessageRole.USER in roles
    assert MessageRole.ASSISTANT in roles
    assistant = next(message for message in messages if message.role == MessageRole.ASSISTANT)
    assert message_text(assistant) == "saved reply"
