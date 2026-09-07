"""Phase 2 Step 8 voice output integration tests."""

from __future__ import annotations

import asyncio

import pytest
from tests.unit.runtime.bridge_helpers import bridge_transport_config, make_bridge
from tests.unit.runtime.voice_helpers import make_voice_bridge, make_voice_runtime

from xymphony_contracts.stt import STTTranscriptChunk
from xymphony_providers.fake_tts import FakeTTSProvider
from xymphony_realtime import FakeMediaTransport
from xymphony_runtime import RuntimeInput
from xymphony_runtime.dispatch import tts_chunk_event
from xymphony_runtime.turn import RuntimeTurnLifecycleState


@pytest.mark.asyncio
async def test_fake_transport_captures_outgoing_audio() -> None:
    transport = FakeMediaTransport()
    tts = FakeTTSProvider(
        chunks=["out-a"],
        chunk_audio={"out-a": b"\x01\x02\x03\x04"},
    )
    bridge = make_bridge(
        transport=transport,
        runtime=make_voice_runtime(tts_provider=tts, llm_chunks=["ok"]),
    )

    run_task = asyncio.create_task(bridge.run(bridge_transport_config()))
    await asyncio.sleep(0)
    await bridge.handle_input(RuntimeInput.text_input("hello"))
    await asyncio.sleep(0)

    assert len(transport.published_output_frames) == 1
    assert transport.published_output_frames[0].data == b"\x01\x02\x03\x04"

    await bridge.shutdown()
    await run_task


@pytest.mark.asyncio
async def test_bridge_publishes_assistant_tts_audio() -> None:
    bridge, _stt, transport = make_voice_bridge(
        runtime=make_voice_runtime(
            llm_chunks=["assistant"],
            tts_provider=FakeTTSProvider(
                chunks=["chunk-0", "chunk-1"],
                chunk_audio={"chunk-0": b"\x00", "chunk-1": b"\x01"},
            ),
        ),
    )

    run_task = asyncio.create_task(bridge.run(bridge_transport_config()))
    await asyncio.sleep(0)
    await bridge.handle_input(RuntimeInput.text_input("hello"))
    await asyncio.sleep(0)

    assert len(transport.published_output_frames) == 2
    assert [frame.data for frame in transport.published_output_frames] == [b"\x00", b"\x01"]

    await bridge.shutdown()
    await run_task


@pytest.mark.asyncio
async def test_cancelled_turn_does_not_publish_stale_tts_audio() -> None:
    tts = FakeTTSProvider(
        chunks=["chunk-0", "chunk-1"],
        chunk_audio={"chunk-0": b"\x00", "chunk-1": b"\x01"},
        delay_seconds=0.1,
    )
    transport = FakeMediaTransport()
    bridge = make_bridge(
        transport=transport,
        runtime=make_voice_runtime(tts_provider=tts, llm_chunks=["long"]),
    )

    run_task = asyncio.create_task(bridge.run(bridge_transport_config()))
    await asyncio.sleep(0)

    task = asyncio.create_task(bridge.handle_input(RuntimeInput.text_input("cancel-me")))
    await asyncio.sleep(0.05)
    await bridge.handle_input(RuntimeInput.cancel_turn())
    await task

    assert bridge.runtime.turns[0].state == RuntimeTurnLifecycleState.CANCELLED
    assert len(transport.published_output_frames) < 2

    await bridge.shutdown()
    await run_task


@pytest.mark.asyncio
async def test_new_turn_publishes_after_cancellation() -> None:
    tts = FakeTTSProvider(
        chunks=["one"],
        chunk_audio={"one": b"\x07"},
        delay_seconds=0.1,
    )
    transport = FakeMediaTransport()
    bridge = make_bridge(
        transport=transport,
        runtime=make_voice_runtime(tts_provider=tts, llm_chunks=["a"]),
    )

    run_task = asyncio.create_task(bridge.run(bridge_transport_config()))
    await asyncio.sleep(0)

    first = asyncio.create_task(bridge.handle_input(RuntimeInput.text_input("first")))
    await asyncio.sleep(0.05)
    await bridge.handle_input(RuntimeInput.cancel_turn())
    await first

    await bridge.handle_input(RuntimeInput.text_input("second"))
    await asyncio.sleep(0)

    second_frames = [
        frame
        for frame in transport.published_output_frames
        if frame.turn_id == str(bridge.runtime.turns[1].id)
    ]
    assert len(second_frames) == 1
    assert second_frames[0].data == b"\x07"

    await bridge.shutdown()
    await run_task


@pytest.mark.asyncio
async def test_multiple_tts_chunks_preserve_ordering() -> None:
    bridge, _stt, transport = make_voice_bridge(
        runtime=make_voice_runtime(
            llm_chunks=["ok"],
            tts_provider=FakeTTSProvider(
                chunks=["a", "b", "c"],
                chunk_audio={"a": b"\x01", "b": b"\x02", "c": b"\x03"},
            ),
        ),
    )

    run_task = asyncio.create_task(bridge.run(bridge_transport_config()))
    await asyncio.sleep(0)
    await bridge.handle_input(RuntimeInput.text_input("ordered"))
    await asyncio.sleep(0)

    indexes = [frame.chunk_index for frame in transport.published_output_frames]
    assert indexes == [0, 1, 2]
    data_frames = [frame.data for frame in transport.published_output_frames]
    assert data_frames == [b"\x01", b"\x02", b"\x03"]

    await bridge.shutdown()
    await run_task


@pytest.mark.asyncio
async def test_existing_text_pipeline_still_works_with_output() -> None:
    bridge = make_bridge(llm_chunks=["hello"], tts_chunks=["audio"])

    run_task = asyncio.create_task(bridge.run(bridge_transport_config()))
    await asyncio.sleep(0)
    await bridge.handle_input(RuntimeInput.text_input("text path"))
    await asyncio.sleep(0)

    assert bridge.runtime.turns[0].state == RuntimeTurnLifecycleState.COMPLETED
    assert len(bridge.published_output_frames) >= 1

    await bridge.shutdown()
    await run_task


@pytest.mark.asyncio
async def test_existing_incoming_voice_pipeline_still_works() -> None:
    bridge, _stt, transport = make_voice_bridge(
        stt_chunks=[STTTranscriptChunk(text="hello", is_final=True)],
        llm_chunks=["assistant"],
        tts_provider=FakeTTSProvider(
            chunks=["out"],
            chunk_audio={"out": b"\x99"},
        ),
    )

    run_task = asyncio.create_task(bridge.run(bridge_transport_config()))
    await asyncio.sleep(0)
    await transport.simulate_speech_utterance("browser-user", b"\x00", duration_ms=10)
    await asyncio.sleep(0)

    assert bridge.runtime.turns[0].state == RuntimeTurnLifecycleState.COMPLETED
    assert len(transport.published_output_frames) >= 1

    await bridge.shutdown()
    await run_task


@pytest.mark.asyncio
async def test_stale_tts_event_is_not_published_to_transport() -> None:
    transport = FakeMediaTransport()
    bridge = make_bridge(
        transport=transport,
        runtime=make_voice_runtime(
            tts_provider=FakeTTSProvider(chunks=["stale"], chunk_audio={"stale": b"\xff"}),
        ),
    )

    run_task = asyncio.create_task(bridge.run(bridge_transport_config()))
    await asyncio.sleep(0)
    await bridge.handle_input(RuntimeInput.user_speech_started())
    cancelled_turn_id = bridge.runtime.current_turn_id
    assert cancelled_turn_id is not None
    await bridge.handle_input(RuntimeInput.cancel_turn())

    assert bridge.runtime.admit_event(
        tts_chunk_event(
            bridge.runtime.context,
            turn_id=cancelled_turn_id,
            audio_ref="stale",
        )
    ) is False
    await asyncio.sleep(0)
    assert transport.published_output_frames == []

    await bridge.shutdown()
    await run_task


@pytest.mark.asyncio
async def test_transport_disconnect_does_not_leak_output_tasks() -> None:
    transport = FakeMediaTransport()
    bridge = make_bridge(transport=transport, llm_chunks=["a"], tts_chunks=["out"])
    before = {task for task in asyncio.all_tasks() if not task.done()}

    run_task = asyncio.create_task(bridge.run(bridge_transport_config()))
    await asyncio.sleep(0)
    await bridge.handle_input(RuntimeInput.text_input("play"))
    await asyncio.sleep(0)
    await transport.disconnect()
    await run_task

    after = {task for task in asyncio.all_tasks() if not task.done()}
    assert run_task.done()
    assert not (after - before)
