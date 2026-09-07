"""STT provider registry unit tests."""

from __future__ import annotations

import pytest

from xymphony_contracts.provider import ProviderError, ProviderErrorCode
from xymphony_providers.registry import create_stt_provider


def test_registry_rejects_unknown_stt_provider() -> None:
    with pytest.raises(ProviderError) as exc_info:
        create_stt_provider("deepgram", model="nova")
    assert exc_info.value.code == ProviderErrorCode.INVALID_REQUEST


def test_registry_creates_assemblyai_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ASSEMBLYAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="ASSEMBLYAI_API_KEY"):
        create_stt_provider("assemblyai", model="universal-streaming")
