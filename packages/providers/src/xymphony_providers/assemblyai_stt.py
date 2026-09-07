"""AssemblyAI STT adapter. Uses official SDK; credentials from configuration only."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from typing import Any, Protocol

from xymphony_contracts.provider import CancellationToken, ProviderError, ProviderErrorCode
from xymphony_contracts.stt import STTAudioFrame, STTRequest, STTTranscriptChunk

_ASSEMBLYAI_PROVIDER_KEY = "assemblyai"


class _StreamingSession(Protocol):
    async def start(self, *, model: str, sample_rate_hz: int) -> None: ...

    async def send(self, frame: STTAudioFrame) -> None: ...

    async def finish(self) -> None: ...

    def transcripts(self) -> AsyncIterator[STTTranscriptChunk]: ...

    async def close(self) -> None: ...


SessionFactory = Callable[[str], _StreamingSession]


class AssemblyAISTTProvider:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        session_factory: SessionFactory | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("ASSEMBLYAI_API_KEY is required for AssemblyAI STT provider")
        self._api_key = api_key
        self._model = model
        self._session_factory = session_factory or _default_session_factory

    @property
    def provider_key(self) -> str:
        return _ASSEMBLYAI_PROVIDER_KEY

    async def transcribe(
        self,
        request: STTRequest,
        audio: AsyncIterator[STTAudioFrame],
        *,
        cancel: CancellationToken,
    ) -> AsyncIterator[STTTranscriptChunk]:
        model = request.model or self._model
        session = self._session_factory(self._api_key)
        sample_rate_hz = 16_000
        try:
            await session.start(model=model, sample_rate_hz=sample_rate_hz)
            async for frame in audio:
                if cancel.cancelled:
                    return
                sample_rate_hz = frame.sample_rate_hz
                await session.send(frame)
            await session.finish()

            async for chunk in session.transcripts():
                if cancel.cancelled:
                    return
                yield chunk
        except ProviderError:
            raise
        except Exception as exc:
            raise _normalize_assemblyai_error(exc) from exc
        finally:
            await session.close()


class _AssemblyAISession:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._queue: asyncio.Queue[STTTranscriptChunk | None] = asyncio.Queue()
        self._client: Any = None
        self._connected = False

    async def start(self, *, model: str, sample_rate_hz: int) -> None:
        from assemblyai.streaming.v3 import (
            AsyncRealTimeTranscriber,
            RealTimeEvents,
            RealTimeParameters,
            RealTimeTranscriberOptions,
        )

        speech_model = _resolve_speech_model(model)

        self._client = AsyncRealTimeTranscriber(
            RealTimeTranscriberOptions(),
            api_key=self._api_key,
        )

        async def on_turn(_client: Any, event: Any) -> None:
            text = getattr(event, "transcript", "") or ""
            if not text:
                return
            is_final = bool(getattr(event, "end_of_turn", False))
            await self._queue.put(
                STTTranscriptChunk(
                    text=text,
                    is_final=is_final,
                    start_ms=int(getattr(event, "start_ms", 0) or 0),
                    end_ms=int(getattr(event, "end_ms", 0) or 0),
                    confidence=_optional_confidence(event),
                )
            )

        async def on_error(_client: Any, event: Any) -> None:
            message = getattr(event, "error", None) or "provider error"
            await self._queue.put(None)
            raise ProviderError(
                code=ProviderErrorCode.PROVIDER,
                message=str(message),
                provider_key=_ASSEMBLYAI_PROVIDER_KEY,
                retryable=False,
            )

        self._client.on(RealTimeEvents.Turn, on_turn)
        self._client.on(RealTimeEvents.Error, on_error)
        await self._client.connect(
            RealTimeParameters(
                speech_model=speech_model,
                sample_rate=sample_rate_hz,
            )
        )
        self._connected = True

    async def send(self, frame: STTAudioFrame) -> None:
        if self._client is None or not self._connected:
            raise ProviderError(
                code=ProviderErrorCode.PROVIDER,
                message="stt session not connected",
                provider_key=_ASSEMBLYAI_PROVIDER_KEY,
                retryable=False,
            )
        await self._client.stream(frame.data)

    async def finish(self) -> None:
        if self._client is not None and self._connected:
            await self._client.disconnect(terminate=True)
            self._connected = False
        await self._queue.put(None)

    async def transcripts(self) -> AsyncIterator[STTTranscriptChunk]:
        while True:
            chunk = await self._queue.get()
            if chunk is None:
                return
            yield chunk

    async def close(self) -> None:
        if self._client is not None and self._connected:
            await self._client.disconnect(terminate=True)
            self._connected = False


def _default_session_factory(api_key: str) -> _StreamingSession:
    return _AssemblyAISession(api_key)


def _resolve_speech_model(model: str) -> Any:
    from assemblyai.streaming.v3 import SpeechModel

    aliases = {
        "universal-streaming": SpeechModel.universal_3_5_pro,
    }
    if model in aliases:
        return aliases[model]
    try:
        return SpeechModel(model)
    except ValueError:
        return SpeechModel.universal_3_5_pro


def _optional_confidence(event: Any) -> float | None:
    value = getattr(event, "confidence", None)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_assemblyai_error(exc: Exception) -> ProviderError:
    message = str(exc).lower()
    if "401" in message or "unauthorized" in message or "authentication" in message:
        return ProviderError(
            code=ProviderErrorCode.AUTH,
            message="authentication failed",
            provider_key=_ASSEMBLYAI_PROVIDER_KEY,
            retryable=False,
        )
    if "429" in message or "rate limit" in message:
        return ProviderError(
            code=ProviderErrorCode.RATE_LIMIT,
            message="rate limit exceeded",
            provider_key=_ASSEMBLYAI_PROVIDER_KEY,
            retryable=True,
        )
    if "timeout" in message or "connection" in message:
        return ProviderError(
            code=ProviderErrorCode.TIMEOUT,
            message="connection failed",
            provider_key=_ASSEMBLYAI_PROVIDER_KEY,
            retryable=True,
        )
    return ProviderError(
        code=ProviderErrorCode.UNKNOWN,
        message=str(exc),
        provider_key=_ASSEMBLYAI_PROVIDER_KEY,
        retryable=False,
    )
