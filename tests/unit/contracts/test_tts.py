"""TTS contract unit tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from xymphony_contracts.tts import TTSRequest, TTSStreamChunk, TTSTextRange


def test_tts_request_round_trip() -> None:
    request = TTSRequest(
        provider_key="elevenlabs",
        voice_ref="voice_default",
        text="Hello there",
    )
    restored = TTSRequest.model_validate(request.model_dump(mode="json"))
    assert restored.provider_key == "elevenlabs"
    assert restored.text == "Hello there"


def test_tts_stream_chunk_supports_text_range() -> None:
    chunk = TTSStreamChunk(
        audio_ref="tts:0",
        index=0,
        is_final=False,
        text_range=TTSTextRange(start=0, end=5),
    )
    assert chunk.text_range is not None
    assert chunk.text_range.end == 5


def test_tts_request_rejects_empty_text() -> None:
    with pytest.raises(ValidationError):
        TTSRequest(provider_key="elevenlabs", voice_ref="voice", text="")
