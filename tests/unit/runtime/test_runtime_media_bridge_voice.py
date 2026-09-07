"""Phase 2 Step 7 RuntimeMediaBridge voice input integration tests."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from tests.unit.runtime.bridge_helpers import bridge_transport_config
from tests.unit.runtime.voice_helpers import make_voice_bridge, make_voice_runtime

from xymphony_contracts.enums import EventType
from xymphony_contracts.provider import ProviderError, ProviderErrorCode
from xymphony_contracts.stt import STTTranscriptChunk
from xymphony_providers.fake_llm import FakeLLMProvider
from xymphony_providers.fake_stt import FakeSTTProvider
from xymphony_runtime import RuntimeInput
from xymphony_runtime.dispatch import transcript_frame_event
from xymphony_runtime.turn import RuntimeTurnLifecycleState


@pytest.mark.asyncio
async def test_transport_audio_reaches_stt_provider() -> None:
    bridge, stt, transport = make_voice_bridge()
    run_task = asyncio.create_task(bridge.run(bridge_transport_config()))
    await asyncio.sleep(0)

    await transport.simulate_speech_utterance("browser-user", b"\x01\x02", duration_ms=20)
    await asyncio.sleep(0)

    assert len(stt.received_frames) == 1
    assert stt.received_frames[0].data == b"\x01\x02"
    assert stt.received_frames[0].duration_ms == 20

    await bridge.shutdown()
    await run_task


@pytest.mark.asyncio
async def test_transport_speech_produces_transcript_and_llm_response() -> None:
    llm = FakeLLMProvider(chunks=["assistant"])
    bridge, _stt, transport = make_voice_bridge(
        runtime=make_voice_runtime(
            llm_provider=llm,
            stt_chunks=[STTTranscriptChunk(text="hello there", is_final=True)],
        ),
    )
    run_task = asyncio.create_task(bridge.run(bridge_transport_config()))
    await asyncio.sleep(0)

    await transport.simulate_speech_utterance("browser-user", b"\x00", duration_ms=10)
    await asyncio.sleep(0)

    turn = bridge.runtime.turns[0]
    assert turn.state == RuntimeTurnLifecycleState.COMPLETED
    assert any(event.type == EventType.TRANSCRIPT_FRAME for event in bridge.runtime_events)
    assert any(event.type == EventType.LLM_RESPONSE for event in bridge.runtime_events)
    assert llm.requests[0].messages[0].content == "hello there"

    await bridge.shutdown()
    await run_task


@pytest.mark.asyncio
async def test_multiple_transport_speech_turns() -> None:
    bridge, _stt, transport = make_voice_bridge(
        stt_chunks=[STTTranscriptChunk(text="ok", is_final=True)],
        llm_chunks=["a"],
    )
    run_task = asyncio.create_task(bridge.run(bridge_transport_config()))
    await asyncio.sleep(0)

    for idx in range(3):
        await transport.simulate_speech_utterance(
            "browser-user",
            bytes([idx]),
            duration_ms=10,
        )
        await asyncio.sleep(0)

    assert len(bridge.runtime.turns) == 3
    assert all(turn.state == RuntimeTurnLifecycleState.COMPLETED for turn in bridge.runtime.turns)

    await bridge.shutdown()
    await run_task


@pytest.mark.asyncio
async def test_cancelled_turn_rejects_late_stt_results() -> None:
    bridge, _stt, transport = make_voice_bridge(
        runtime=make_voice_runtime(
            stt_provider=FakeSTTProvider(
                chunks=[STTTranscriptChunk(text="hello", is_final=True)],
                delay_seconds=0.2,
            ),
        ),
    )
    run_task = asyncio.create_task(bridge.run(bridge_transport_config()))
    await asyncio.sleep(0)

    await transport.simulate_audio_input_started("browser-user")
    await transport.simulate_audio_frame("browser-user", b"\x00", duration_ms=10)

    end_task = asyncio.create_task(transport.simulate_audio_input_ended("browser-user"))
    await asyncio.sleep(0.05)
    await bridge.handle_input(RuntimeInput.cancel_turn())
    await end_task

    turn = bridge.runtime.turns[0]
    assert turn.state == RuntimeTurnLifecycleState.CANCELLED
    transcript_events = [
        event for event in bridge.runtime_events if event.type == EventType.TRANSCRIPT_FRAME
    ]
    assert len(transcript_events) < 2

    await bridge.shutdown()
    await run_task


@pytest.mark.asyncio
async def test_stale_transcript_cannot_affect_new_turn_through_bridge() -> None:
    bridge, _stt, transport = make_voice_bridge(
        stt_chunks=[STTTranscriptChunk(text="ok", is_final=True)],
    )
    run_task = asyncio.create_task(bridge.run(bridge_transport_config()))
    await asyncio.sleep(0)

    await transport.simulate_audio_input_started("browser-user")
    cancelled_turn_id = bridge.runtime.current_turn_id
    assert cancelled_turn_id is not None
    await bridge.handle_input(RuntimeInput.cancel_turn())

    assert bridge.runtime.admit_event(
        transcript_frame_event(
            bridge.runtime.context,
            turn_id=cancelled_turn_id,
            text="stale",
            is_final=True,
        )
    ) is False

    await transport.simulate_speech_utterance("browser-user", b"\x01", duration_ms=10)
    await asyncio.sleep(0)
    second_turn = bridge.runtime.turns[1]
    assert second_turn.state == RuntimeTurnLifecycleState.COMPLETED

    await bridge.shutdown()
    await run_task


@pytest.mark.asyncio
async def test_transport_disconnect_cleans_up_during_speech() -> None:
    bridge, _stt, transport = make_voice_bridge()
    run_task = asyncio.create_task(bridge.run(bridge_transport_config()))
    await asyncio.sleep(0)

    await transport.simulate_audio_input_started("browser-user")
    await transport.simulate_audio_frame("browser-user", b"\x00", duration_ms=10)
    await transport.disconnect()
    await run_task

    assert bridge.runtime.running is False


@pytest.mark.asyncio
async def test_bridge_shutdown_cleans_up_during_speech() -> None:
    bridge, _stt, transport = make_voice_bridge()
    before = {task for task in asyncio.all_tasks() if not task.done()}

    run_task = asyncio.create_task(bridge.run(bridge_transport_config()))
    await asyncio.sleep(0)
    await transport.simulate_audio_input_started("browser-user")
    await transport.simulate_audio_frame("browser-user", b"\x00", duration_ms=10)
    await bridge.shutdown()
    await run_task

    after = {task for task in asyncio.all_tasks() if not task.done()}
    assert run_task.done()
    assert not (after - before)


@pytest.mark.asyncio
async def test_stt_provider_failure_is_surfaced_and_runtime_recovers() -> None:
    failing_stt = FakeSTTProvider(
        fail_with=ProviderError(
            code=ProviderErrorCode.PROVIDER,
            message="stt unavailable",
            provider_key="fake",
        )
    )
    bridge, _stt, transport = make_voice_bridge(stt_provider=failing_stt)
    run_task = asyncio.create_task(bridge.run(bridge_transport_config()))
    await asyncio.sleep(0)

    await transport.simulate_speech_utterance("browser-user", b"\x00", duration_ms=10)
    await asyncio.sleep(0)
    assert bridge.runtime.turns[0].state == RuntimeTurnLifecycleState.FAILED
    assert any(event.type == EventType.ERROR for event in bridge.runtime_events)

    failing_stt.fail_with = None
    failing_stt.chunks = [STTTranscriptChunk(text="ok", is_final=True)]
    await transport.simulate_speech_utterance("browser-user", b"\x01", duration_ms=10)
    await asyncio.sleep(0)
    assert bridge.runtime.turns[1].state == RuntimeTurnLifecycleState.COMPLETED

    await bridge.shutdown()
    await run_task


def test_livekit_types_do_not_escape_runtime_boundary() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    runtime_files = [
        repo_root / "packages/agent-runtime/src/xymphony_runtime/bridge.py",
        repo_root / "packages/agent-runtime/src/xymphony_runtime/runtime.py",
        repo_root / "packages/agent-runtime/src/xymphony_runtime/input.py",
    ]
    for path in runtime_files:
        source = path.read_text(encoding="utf-8")
        assert "livekit" not in source.lower()


def test_fake_transport_audio_simulation_remains_usable() -> None:
    from xymphony_realtime import FakeMediaTransport

    transport = FakeMediaTransport()
    assert hasattr(transport, "simulate_speech_utterance")
    assert hasattr(transport, "on_audio_frame")
    assert hasattr(transport, "on_audio_input")
