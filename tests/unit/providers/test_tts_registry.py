"""TTS provider registry unit tests."""

from __future__ import annotations

import pytest

from xymphony_contracts.provider import ProviderError, ProviderErrorCode
from xymphony_providers.registry import create_tts_provider


def test_registry_rejects_unknown_tts_provider() -> None:
    with pytest.raises(ProviderError) as exc_info:
        create_tts_provider("cartesia", voice_ref="voice")
    assert exc_info.value.code == ProviderErrorCode.INVALID_REQUEST


def test_registry_creates_elevenlabs_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    with pytest.raises(ValueError, match="ELEVENLABS_API_KEY"):
        create_tts_provider("elevenlabs", voice_ref="voice_default")
