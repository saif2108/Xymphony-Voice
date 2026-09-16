"""AssemblyAI STT adapter normalization tests (mocked session, no network)."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from xymphony_contracts.provider import ProviderErrorCode
from xymphony_contracts.stt import STTAudioFrame, STTRequest, STTTranscriptChunk
from xymphony_providers.assemblyai_stt import (
    AssemblyAISTTProvider,
    _normalize_assemblyai_error,
)
from xymphony_runtime.cancellation import EventCancellationToken

_SECRET = "secret-api-key-do-not-log"


class _MockSession:
    def __init__(self, chunks: list[STTTranscriptChunk] | None = None) -> None:
        self.chunks = chunks or [
            STTTranscriptChunk(text="hel", is_final=False),
            STTTranscriptChunk(text="hello", is_final=True),
        ]
        self.sent: list[STTAudioFrame] = []

    async def start(self, *, model: str, sample_rate_hz: int) -> None:
        _ = model, sample_rate_hz

    async def send(self, frame: STTAudioFrame) -> None:
        self.sent.append(frame)

    async def finish(self) -> None:
        return None

    async def transcripts(self) -> AsyncIterator[STTTranscriptChunk]:
        for chunk in self.chunks:
            yield chunk

    async def close(self) -> None:
        return None


async def _audio(
    frame_count: int = 10,
    *,
    duration_ms: int = 10,
) -> AsyncIterator[STTAudioFrame]:
    for _ in range(frame_count):
        yield STTAudioFrame(
            data=b"\x00\x01",
            duration_ms=duration_ms,
        )


@pytest.mark.asyncio
async def test_assemblyai_adapter_normalizes_transcript_chunks() -> None:
    session = _MockSession()
    provider = AssemblyAISTTProvider(
        api_key=_SECRET,
        model="universal-streaming",
        session_factory=lambda _key: session,
    )
    request = STTRequest(provider_key="assemblyai", model="universal-streaming")
    chunks = [
        chunk
        async for chunk in provider.transcribe(
            request,
            _audio(),
            cancel=EventCancellationToken(),
        )
    ]
    assert [chunk.text for chunk in chunks] == ["hel", "hello"]
    assert len(session.sent) == 1
    assert session.sent[0].duration_ms == 100
    assert session.sent[0].data == b"\x00\x01" * 10

@pytest.mark.asyncio
async def test_assemblyai_adapter_does_not_send_chunks_below_minimum() -> None:
    session = _MockSession()
    provider = AssemblyAISTTProvider(
        api_key=_SECRET,
        model="universal-streaming",
        session_factory=lambda _key: session,
    )
    request = STTRequest(provider_key="assemblyai", model="universal-streaming")

    async def short_audio() -> AsyncIterator[STTAudioFrame]:
        for _ in range(4):
            yield STTAudioFrame(data=b"\x00\x01", duration_ms=10)

    _ = [
        chunk
        async for chunk in provider.transcribe(
            request,
            short_audio(),
            cancel=EventCancellationToken(),
        )
    ]

    assert session.sent == []

def test_normalize_auth_error_does_not_leak_key() -> None:
    normalized = _normalize_assemblyai_error(Exception(f"401 unauthorized {_SECRET}"))
    assert normalized.code == ProviderErrorCode.AUTH
    assert _SECRET not in normalized.message


def test_normalize_rate_limit_error() -> None:
    normalized = _normalize_assemblyai_error(Exception("429 rate limit exceeded"))
    assert normalized.code == ProviderErrorCode.RATE_LIMIT
    assert normalized.retryable is True


def test_provider_requires_api_key() -> None:
    with pytest.raises(ValueError, match="ASSEMBLYAI_API_KEY"):
        AssemblyAISTTProvider(api_key="", model="universal-streaming")
