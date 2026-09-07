"""Fake STT provider unit tests."""

from __future__ import annotations

import pytest

from xymphony_contracts.provider import ProviderError, ProviderErrorCode
from xymphony_contracts.stt import STTAudioFrame, STTRequest, STTTranscriptChunk
from xymphony_providers.fake_stt import FakeSTTProvider
from xymphony_runtime.cancellation import EventCancellationToken


async def _audio_frames(*frames: STTAudioFrame):
    for frame in frames:
        yield frame


@pytest.mark.asyncio
async def test_fake_stt_streams_partial_and_final_chunks() -> None:
    provider = FakeSTTProvider()
    request = STTRequest(provider_key="fake", model="fake-model")
    cancel = EventCancellationToken()
    chunks = [
        chunk
        async for chunk in provider.transcribe(
            request,
            _audio_frames(STTAudioFrame(data=b"\x00\x01", duration_ms=10)),
            cancel=cancel,
        )
    ]
    assert len(chunks) == 2
    assert chunks[0].is_final is False
    assert chunks[-1].is_final is True


@pytest.mark.asyncio
async def test_fake_stt_honours_cancellation() -> None:
    provider = FakeSTTProvider(delay_seconds=0.05)
    request = STTRequest(provider_key="fake", model="fake-model")
    cancel = EventCancellationToken()

    async def _consume() -> list[STTTranscriptChunk]:
        collected: list[STTTranscriptChunk] = []
        async for chunk in provider.transcribe(
            request,
            _audio_frames(STTAudioFrame(data=b"\x00", duration_ms=10)),
            cancel=cancel,
        ):
            collected.append(chunk)
        return collected

    import asyncio

    task = asyncio.create_task(_consume())
    await asyncio.sleep(0.06)
    cancel.cancel()
    collected = await task
    assert len(collected) < 2


@pytest.mark.asyncio
async def test_fake_stt_raises_configured_error() -> None:
    provider = FakeSTTProvider(
        fail_with=ProviderError(
            code=ProviderErrorCode.PROVIDER,
            message="boom",
            provider_key="fake",
        )
    )
    request = STTRequest(provider_key="fake", model="fake-model")
    with pytest.raises(ProviderError) as exc_info:
        async for _ in provider.transcribe(
            request,
            _audio_frames(STTAudioFrame(data=b"\x00", duration_ms=10)),
            cancel=EventCancellationToken(),
        ):
            pass
    assert exc_info.value.code == ProviderErrorCode.PROVIDER
