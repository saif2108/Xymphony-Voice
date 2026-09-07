"""ElevenLabs TTS adapter. Uses official SDK; credentials from configuration only."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Iterable
from typing import Any

from xymphony_contracts.provider import CancellationToken, ProviderError, ProviderErrorCode
from xymphony_contracts.tts import TTSRequest, TTSStreamChunk

_ELEVENLABS_PROVIDER_KEY = "elevenlabs"


StreamFactory = Callable[[str, TTSRequest], Iterable[bytes]]


class ElevenLabsTTSProvider:
    def __init__(
        self,
        *,
        api_key: str,
        default_voice_ref: str,
        stream_factory: StreamFactory | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("ELEVENLABS_API_KEY is required for ElevenLabs TTS provider")
        self._api_key = api_key
        self._default_voice_ref = default_voice_ref
        self._stream_factory = stream_factory or _default_stream_factory

    @property
    def provider_key(self) -> str:
        return _ELEVENLABS_PROVIDER_KEY

    async def stream(
        self,
        request: TTSRequest,
        *,
        cancel: CancellationToken,
    ) -> AsyncIterator[TTSStreamChunk]:
        voice_ref = request.voice_ref or self._default_voice_ref
        try:
            audio_stream = self._stream_factory(self._api_key, request)
            last_index = -1
            for index, _chunk_bytes in enumerate(audio_stream):
                if cancel.cancelled:
                    return
                last_index = index
                yield TTSStreamChunk(
                    audio_ref=f"elevenlabs:{voice_ref}:{index}",
                    index=index,
                    is_final=False,
                )
            if cancel.cancelled:
                return
            final_index = max(last_index, 0)
            yield TTSStreamChunk(
                audio_ref=f"elevenlabs:{voice_ref}:{final_index}:final",
                index=final_index,
                is_final=True,
            )
        except ProviderError:
            raise
        except Exception as exc:
            raise _normalize_elevenlabs_error(exc) from exc


def _default_stream_factory(api_key: str, request: TTSRequest) -> Iterable[bytes]:
    from elevenlabs.client import ElevenLabs

    voice_ref = request.voice_ref
    model_id = request.params.get("model_id")
    kwargs: dict[str, Any] = {
        "voice_id": voice_ref,
        "text": request.text,
    }
    if isinstance(model_id, str) and model_id:
        kwargs["model_id"] = model_id
    client = ElevenLabs(api_key=api_key)
    stream: Iterable[bytes] = client.text_to_speech.convert_as_stream(**kwargs)
    return stream


def _normalize_elevenlabs_error(exc: Exception) -> ProviderError:
    message = str(exc).lower()
    if "401" in message or "unauthorized" in message or "authentication" in message:
        return ProviderError(
            code=ProviderErrorCode.AUTH,
            message="authentication failed",
            provider_key=_ELEVENLABS_PROVIDER_KEY,
            retryable=False,
        )
    if "429" in message or "rate limit" in message:
        return ProviderError(
            code=ProviderErrorCode.RATE_LIMIT,
            message="rate limit exceeded",
            provider_key=_ELEVENLABS_PROVIDER_KEY,
            retryable=True,
        )
    if "timeout" in message or "connection" in message:
        return ProviderError(
            code=ProviderErrorCode.TIMEOUT,
            message="connection failed",
            provider_key=_ELEVENLABS_PROVIDER_KEY,
            retryable=True,
        )
    return ProviderError(
        code=ProviderErrorCode.UNKNOWN,
        message=str(exc),
        provider_key=_ELEVENLABS_PROVIDER_KEY,
        retryable=False,
    )
