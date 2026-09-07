"""In-memory TTS provider for unit tests."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from xymphony_contracts.provider import CancellationToken, ProviderError
from xymphony_contracts.tts import TTSRequest, TTSStreamChunk


class FakeTTSProvider:
    provider_key = "fake"

    def __init__(
        self,
        *,
        chunks: list[str] | None = None,
        fail_with: ProviderError | None = None,
        delay_seconds: float = 0,
    ) -> None:
        self.chunks = chunks or ["fake-audio-0", "fake-audio-1"]
        self.fail_with = fail_with
        self.delay_seconds = delay_seconds
        self.requests: list[TTSRequest] = []

    async def stream(
        self,
        request: TTSRequest,
        *,
        cancel: CancellationToken,
    ) -> AsyncIterator[TTSStreamChunk]:
        self.requests.append(request)
        if self.fail_with is not None:
            raise self.fail_with
        for index, audio_ref in enumerate(self.chunks):
            if cancel.cancelled:
                return
            if self.delay_seconds:
                await asyncio.sleep(self.delay_seconds)
            if cancel.cancelled:
                return
            is_final = index == len(self.chunks) - 1
            yield TTSStreamChunk(audio_ref=audio_ref, index=index, is_final=is_final)
