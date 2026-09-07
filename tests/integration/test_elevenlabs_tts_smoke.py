"""Optional ElevenLabs TTS smoke test — skipped unless ELEVENLABS_INTEGRATION=1."""

from __future__ import annotations

import os

import pytest

from xymphony_contracts.tts import TTSRequest
from xymphony_providers.registry import create_tts_provider
from xymphony_runtime.cancellation import EventCancellationToken

pytestmark = pytest.mark.elevenlabs


def _integration_enabled() -> bool:
    return os.getenv("ELEVENLABS_INTEGRATION") == "1" and bool(os.getenv("ELEVENLABS_API_KEY"))


@pytest.mark.asyncio
@pytest.mark.skipif(
    not _integration_enabled(),
    reason="Set ELEVENLABS_INTEGRATION=1 and ELEVENLABS_API_KEY",
)
async def test_elevenlabs_stream_smoke() -> None:
    voice_ref = os.getenv("ELEVENLABS_VOICE_ID", "voice_default")
    provider = create_tts_provider("elevenlabs", voice_ref=voice_ref)
    request = TTSRequest(
        provider_key="elevenlabs",
        voice_ref=voice_ref,
        text="Hello",
    )
    chunks = [chunk async for chunk in provider.stream(request, cancel=EventCancellationToken())]
    api_key = os.environ["ELEVENLABS_API_KEY"]
    for chunk in chunks:
        assert api_key not in chunk.audio_ref
