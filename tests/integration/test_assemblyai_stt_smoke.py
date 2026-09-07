"""Optional AssemblyAI STT smoke test — skipped unless ASSEMBLYAI_INTEGRATION=1."""

from __future__ import annotations

import os

import pytest

from xymphony_contracts.stt import STTAudioFrame, STTRequest
from xymphony_providers.registry import create_stt_provider
from xymphony_runtime.cancellation import EventCancellationToken

pytestmark = pytest.mark.assemblyai


def _integration_enabled() -> bool:
    return os.getenv("ASSEMBLYAI_INTEGRATION") == "1" and bool(os.getenv("ASSEMBLYAI_API_KEY"))


async def _silence_audio():
    yield STTAudioFrame(data=b"\x00\x00" * 800, duration_ms=100)


@pytest.mark.asyncio
@pytest.mark.skipif(
    not _integration_enabled(),
    reason="Set ASSEMBLYAI_INTEGRATION=1 and ASSEMBLYAI_API_KEY",
)
async def test_assemblyai_stream_smoke() -> None:
    model = os.getenv("ASSEMBLYAI_MODEL", "universal-streaming")
    provider = create_stt_provider("assemblyai", model=model)
    request = STTRequest(provider_key="assemblyai", model=model)
    chunks = [
        chunk
        async for chunk in provider.transcribe(
            request,
            _silence_audio(),
            cancel=EventCancellationToken(),
        )
    ]
    api_key = os.environ["ASSEMBLYAI_API_KEY"]
    for chunk in chunks:
        assert api_key not in chunk.text
