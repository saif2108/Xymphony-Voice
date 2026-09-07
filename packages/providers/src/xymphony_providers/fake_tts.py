"""In-memory TTS provider for unit tests."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from xymphony_contracts.provider import CancellationToken, ProviderError
from xymphony_contracts.tts import TTSOutputAudioFrame, TTSRequest, TTSStreamChunk


class FakeTTSProvider:
    provider_key = "fake"

    def __init__(
        self,
        *,
        chunks: list[str] | None = None,
        chunk_audio: dict[str, bytes] | None = None,
        fail_with: ProviderError | None = None,
        delay_seconds: float = 0,
    ) -> None:
        self.chunks = chunks or ["fake-audio-0", "fake-audio-1"]
        self.chunk_audio = chunk_audio or {}
        self.fail_with = fail_with
        self.delay_seconds = delay_seconds
        self.requests: list[TTSRequest] = []

    def resolve_output_audio(self, audio_ref: str) -> TTSOutputAudioFrame | None:
        data = self.chunk_audio.get(audio_ref)
        if data is None:
            if audio_ref not in self.chunks:
                return None
            data = self._synthetic_pcm_for_ref(audio_ref)
        duration_ms = max(1, len(data) // (2 * 1) * 1000 // 16_000)
        return TTSOutputAudioFrame(
            data=data,
            sample_rate_hz=16_000,
            channels=1,
            duration_ms=duration_ms,
        )

    @staticmethod
    def _synthetic_pcm_for_ref(audio_ref: str) -> bytes:
        seed = sum(audio_ref.encode()) % 256
        sample_count = 160
        return bytes([seed, 0] * sample_count)

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
