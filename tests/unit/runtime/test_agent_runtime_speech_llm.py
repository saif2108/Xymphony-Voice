"""Phase 2 Step 7 speech→STT→LLM runtime integration tests."""

from __future__ import annotations

import pytest
from tests.unit.runtime.pipeline_helpers import pipeline_context
from tests.unit.runtime.voice_helpers import make_voice_runtime

from xymphony_contracts.enums import EventType
from xymphony_contracts.provider import ProviderError, ProviderErrorCode
from xymphony_contracts.stt import STTTranscriptChunk
from xymphony_providers.fake_llm import FakeLLMProvider
from xymphony_providers.fake_stt import FakeSTTProvider
from xymphony_runtime import RuntimeInput, STTRuntimeConfig
from xymphony_runtime.turn import RuntimeTurnLifecycleState


async def _speech_with_audio(
    runtime: object,
    *,
    audio: bytes = b"\x00\x01",
    duration_ms: int = 10,
) -> None:
    await runtime.handle_input(RuntimeInput.user_speech_started())  # type: ignore[attr-defined]
    await runtime.handle_input(RuntimeInput.audio_frame(audio, duration_ms=duration_ms))  # type: ignore[attr-defined]
    await runtime.handle_input(RuntimeInput.user_speech_ended())  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_final_transcript_reuses_existing_llm_path() -> None:
    llm = FakeLLMProvider(chunks=["answer"])
    stt = FakeSTTProvider(
        chunks=[STTTranscriptChunk(text="user question", is_final=True)],
    )
    runtime = make_voice_runtime(llm_provider=llm, stt_provider=stt)
    await runtime.start()
    await _speech_with_audio(runtime)

    turn = runtime.turns[0]
    assert turn.state == RuntimeTurnLifecycleState.COMPLETED
    assert len(stt.received_frames) == 1
    assert len(llm.requests) == 1
    assert llm.requests[0].messages[0].content == "user question"
    assert any(event.type == EventType.TRANSCRIPT_FRAME for event in runtime.admitted_events)
    assert any(event.type == EventType.LLM_RESPONSE for event in runtime.admitted_events)


@pytest.mark.asyncio
async def test_speech_without_llm_still_completes_after_stt_only() -> None:
    from xymphony_runtime import AgentRuntime

    runtime = AgentRuntime(
        pipeline_context(),
        stt_provider=FakeSTTProvider(
            chunks=[STTTranscriptChunk(text="hello", is_final=True)],
        ),
        stt_config=STTRuntimeConfig(provider_key="fake", model="fake-model"),
    )
    await runtime.start()
    await _speech_with_audio(runtime)
    assert runtime.turns[0].state == RuntimeTurnLifecycleState.COMPLETED
    assert not any(event.type == EventType.LLM_RESPONSE for event in runtime.admitted_events)


@pytest.mark.asyncio
async def test_recovery_after_stt_failure_on_next_speech_turn() -> None:
    failing_stt = FakeSTTProvider(
        fail_with=ProviderError(
            code=ProviderErrorCode.PROVIDER,
            message="stt unavailable",
            provider_key="fake",
        )
    )
    runtime = make_voice_runtime(stt_provider=failing_stt)
    await runtime.start()
    await _speech_with_audio(runtime)
    assert runtime.turns[0].state == RuntimeTurnLifecycleState.FAILED

    failing_stt.fail_with = None
    failing_stt.chunks = [STTTranscriptChunk(text="recovered", is_final=True)]
    await _speech_with_audio(runtime)
    assert runtime.turns[1].state == RuntimeTurnLifecycleState.COMPLETED
