"""In-memory STT provider for unit tests."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from xymphony_contracts.provider import CancellationToken, ProviderError
from xymphony_contracts.stt import STTAudioFrame, STTRequest, STTTranscriptChunk


class FakeSTTProvider:
    provider_key = "fake"

    def __init__(
        self,
        *,
        chunks: list[STTTranscriptChunk] | None = None,
        fail_with: ProviderError | None = None,
        delay_seconds: float = 0,
    ) -> None:
        self.chunks = chunks or [
            STTTranscriptChunk(text="hel", is_final=False, start_ms=0, end_ms=100),
            STTTranscriptChunk(text="hello", is_final=True, start_ms=0, end_ms=200),
        ]
        self.fail_with = fail_with
        self.delay_seconds = delay_seconds
        self.requests: list[STTRequest] = []
        self.received_frames: list[STTAudioFrame] = []

    async def transcribe(
        self,
        request: STTRequest,
        audio: AsyncIterator[STTAudioFrame],
        *,
        cancel: CancellationToken,
    ) -> AsyncIterator[STTTranscriptChunk]:
        self.requests.append(request)
        if self.fail_with is not None:
            raise self.fail_with
        async for frame in audio:
            if cancel.cancelled:
                return
            self.received_frames.append(frame)
        for chunk in self.chunks:
            if cancel.cancelled:
                return
            if self.delay_seconds:
                await asyncio.sleep(self.delay_seconds)
            if cancel.cancelled:
                return
            yield chunk
