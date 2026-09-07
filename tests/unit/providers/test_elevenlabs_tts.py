"""ElevenLabs TTS adapter normalization tests (mocked stream, no network)."""

from __future__ import annotations

import pytest

from xymphony_contracts.provider import ProviderErrorCode
from xymphony_contracts.tts import TTSRequest
from xymphony_providers.elevenlabs_tts import (
    ElevenLabsTTSProvider,
    _normalize_elevenlabs_error,
)
from xymphony_runtime.cancellation import EventCancellationToken

_SECRET = "secret-api-key-do-not-log"


class _MockStream:
    def __init__(self, chunks: list[bytes] | None = None) -> None:
        self._chunks = chunks or [b"\x00\x01", b"\x00\x02"]

    def __iter__(self):
        return iter(self._chunks)


@pytest.mark.asyncio
async def test_elevenlabs_adapter_normalizes_stream_chunks() -> None:
    provider = ElevenLabsTTSProvider(
        api_key=_SECRET,
        default_voice_ref="voice_default",
        stream_factory=lambda _key, _request: _MockStream(),
    )
    request = TTSRequest(
        provider_key="elevenlabs",
        voice_ref="voice_default",
        text="hello",
    )
    chunks = [chunk async for chunk in provider.stream(request, cancel=EventCancellationToken())]
    assert len(chunks) == 3
    assert chunks[0].is_final is False
    assert chunks[-1].is_final is True


def test_normalize_auth_error_does_not_leak_key() -> None:
    normalized = _normalize_elevenlabs_error(Exception(f"401 unauthorized {_SECRET}"))
    assert normalized.code == ProviderErrorCode.AUTH
    assert _SECRET not in normalized.message


def test_provider_requires_api_key() -> None:
    with pytest.raises(ValueError, match="ELEVENLABS_API_KEY"):
        ElevenLabsTTSProvider(api_key="", default_voice_ref="voice_default")
