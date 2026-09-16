"""Tests for live voice pipeline: in-call STT finalization, consecutive turns, and teardown resilience."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest
from tests.unit.runtime.bridge_helpers import bridge_transport_config
from tests.unit.runtime.voice_helpers import make_voice_bridge, make_voice_runtime

from xymphony_contracts.enums import EventType
from xymphony_contracts.provider import CancellationToken
from xymphony_contracts.stt import STTAudioFrame, STTRequest, STTTranscriptChunk
from xymphony_providers.fake_llm import FakeLLMProvider
from xymphony_providers.fake_tts import FakeTTSProvider
from xymphony_runtime.turn import RuntimeTurnLifecycleState


class _StreamingSTTProvider:
    provider_key = "fake"

    def __init__(self, turns_chunks: list[list[STTTranscriptChunk]]) -> None:
        self._turns_chunks = turns_chunks
        self._call_count = 0
        self.received_frames: list[STTAudioFrame] = []

    async def transcribe(
        self,
        request: STTRequest,
        audio: AsyncIterator[STTAudioFrame],
        *,
        cancel: CancellationToken,
    ) -> AsyncIterator[STTTranscriptChunk]:
        idx = self._call_count
        self._call_count += 1
        chunks = self._turns_chunks[idx] if idx < len(self._turns_chunks) else []

        async def _drain_audio() -> None:
            async for frame in audio:
                self.received_frames.append(frame)

        drain_task = asyncio.create_task(_drain_audio())
        try:
            for chunk in chunks:
                await asyncio.sleep(0.01)
                if cancel.cancelled:
                    return
                yield chunk
        finally:
            drain_task.cancel()


@pytest.mark.asyncio
async def test_live_speech_processing_runs_during_active_connection() -> None:
    """STT is_final triggers LLM, TTS, and audio publication while still connected (no ENDED event)."""
    stt = _StreamingSTTProvider([
        [
            STTTranscriptChunk(text="what time is it", is_final=True),
        ]
    ])
    llm = FakeLLMProvider(chunks=["it is noon"])
    tts = FakeTTSProvider(chunks=["chunk-1"], chunk_audio={"chunk-1": b"\x10\x20" * 80})
    runtime = make_voice_runtime(
        stt_provider=stt,  # type: ignore[arg-type]
        llm_provider=llm,
        tts_provider=tts,
    )
    bridge, _, transport = make_voice_bridge(runtime=runtime)
    run_task = asyncio.create_task(bridge.run(bridge_transport_config()))
    await asyncio.sleep(0.01)

    # 1. Transport emits STARTED when user track joins
    await transport.simulate_audio_input_started("browser-user")
    # 2. Audio frame arrives
    await transport.simulate_audio_frame("browser-user", b"\x01\x02" * 80, duration_ms=20)

    # Note: simulate_audio_input_ended is NEVER called!
    # Wait for turn pipeline to complete
    await asyncio.sleep(0.05)

    turn = bridge.runtime.turns[0]
    assert turn.state == RuntimeTurnLifecycleState.COMPLETED
    assert any(e.type == EventType.USER_SPEECH_ENDED for e in bridge.runtime_events)
    assert any(e.type == EventType.TRANSCRIPT_FRAME for e in bridge.runtime_events)
    assert any(e.type == EventType.LLM_RESPONSE for e in bridge.runtime_events)
    assert any(e.type == EventType.TTS_CHUNK for e in bridge.runtime_events)
    assert len(bridge.published_output_frames) == 1

    await bridge.shutdown()
    await run_task


@pytest.mark.asyncio
async def test_subsequent_turn_auto_starts_on_audio_frames() -> None:
    """After turn 1 completes via end-of-turn, incoming audio frame auto-starts turn 2."""
    stt = _StreamingSTTProvider([
        [STTTranscriptChunk(text="first query", is_final=True)],
        [STTTranscriptChunk(text="second query", is_final=True)],
    ])
    runtime = make_voice_runtime(stt_provider=stt)  # type: ignore[arg-type]
    bridge, _, transport = make_voice_bridge(runtime=runtime)
    run_task = asyncio.create_task(bridge.run(bridge_transport_config()))
    await asyncio.sleep(0.01)

    # Turn 1
    await transport.simulate_audio_input_started("browser-user")
    await transport.simulate_audio_frame("browser-user", b"\x01", duration_ms=20)
    await asyncio.sleep(0.05)
    assert bridge.runtime.turns[0].state == RuntimeTurnLifecycleState.COMPLETED

    # Turn 2: Audio frame arrives without transport STARTED event
    await transport.simulate_audio_frame("browser-user", b"\x02", duration_ms=20)
    await asyncio.sleep(0.05)
    assert len(bridge.runtime.turns) == 2
    assert bridge.runtime.turns[1].state == RuntimeTurnLifecycleState.COMPLETED

    await bridge.shutdown()
    await run_task


@pytest.mark.asyncio
async def test_late_audio_input_ended_on_disconnect_is_safe() -> None:
    """When turn already completed via is_final, transport ENDED on disconnect does not error."""
    stt = _StreamingSTTProvider([
        [STTTranscriptChunk(text="hello", is_final=True)],
    ])
    runtime = make_voice_runtime(stt_provider=stt)  # type: ignore[arg-type]
    bridge, _, transport = make_voice_bridge(runtime=runtime)
    run_task = asyncio.create_task(bridge.run(bridge_transport_config()))
    await asyncio.sleep(0.01)

    await transport.simulate_audio_input_started("browser-user")
    await transport.simulate_audio_frame("browser-user", b"\x01", duration_ms=20)
    await asyncio.sleep(0.05)
    assert bridge.runtime.turns[0].state == RuntimeTurnLifecycleState.COMPLETED

    # Now disconnect emits ENDED:
    await transport.simulate_audio_input_ended("browser-user")
    await asyncio.sleep(0.01)
    # No exception, errors list is empty
    assert len(bridge.errors) == 0

    await bridge.shutdown()
    await run_task


@pytest.mark.asyncio
async def test_teardown_cancels_background_tasks_cleanly() -> None:
    """Bridge teardown cancels all pending background tasks cleanly."""
    runtime = make_voice_runtime()
    bridge, _, transport = make_voice_bridge(runtime=runtime)
    run_task = asyncio.create_task(bridge.run(bridge_transport_config()))
    await asyncio.sleep(0.01)

    # Spawn a slow background task tracked by bridge
    async def _slow_task() -> None:
        await asyncio.sleep(10)

    bridge._track_task(asyncio.create_task(_slow_task()))  # noqa: SLF001

    await bridge.shutdown()
    await run_task
    assert len(bridge._background_tasks) == 0  # noqa: SLF001
