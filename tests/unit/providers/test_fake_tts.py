"""Fake TTS provider unit tests."""

from __future__ import annotations

import pytest

from xymphony_contracts.provider import ProviderError, ProviderErrorCode
from xymphony_contracts.tts import TTSRequest
from xymphony_providers.fake_tts import FakeTTSProvider
from xymphony_runtime.cancellation import EventCancellationToken


@pytest.mark.asyncio
async def test_fake_tts_streams_multiple_chunks() -> None:
    provider = FakeTTSProvider()
    request = TTSRequest(provider_key="fake", voice_ref="voice", text="hello")
    cancel = EventCancellationToken()
    chunks = [chunk async for chunk in provider.stream(request, cancel=cancel)]
    assert len(chunks) == 2
    assert chunks[-1].is_final is True


@pytest.mark.asyncio
async def test_fake_tts_honours_cancellation() -> None:
    provider = FakeTTSProvider(delay_seconds=0.05)
    request = TTSRequest(provider_key="fake", voice_ref="voice", text="hello")
    cancel = EventCancellationToken()

    async def _consume() -> list[str]:
        refs: list[str] = []
        async for chunk in provider.stream(request, cancel=cancel):
            refs.append(chunk.audio_ref)
        return refs

    import asyncio

    task = asyncio.create_task(_consume())
    await asyncio.sleep(0.06)
    cancel.cancel()
    refs = await task
    assert len(refs) < 2


@pytest.mark.asyncio
async def test_fake_tts_raises_configured_error() -> None:
    provider = FakeTTSProvider(
        fail_with=ProviderError(
            code=ProviderErrorCode.PROVIDER,
            message="boom",
            provider_key="fake",
        )
    )
    request = TTSRequest(provider_key="fake", voice_ref="voice", text="hello")
    with pytest.raises(ProviderError):
        async for _ in provider.stream(request, cancel=EventCancellationToken()):
            pass
