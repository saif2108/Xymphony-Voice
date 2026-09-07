"""Provider registry unit tests."""

from __future__ import annotations

import pytest

from xymphony_contracts.llm import ProviderError, ProviderErrorCode
from xymphony_providers.registry import create_llm_provider


def test_registry_rejects_unknown_provider() -> None:
    with pytest.raises(ProviderError) as exc_info:
        create_llm_provider("anthropic", model="claude-3")
    assert exc_info.value.code == ProviderErrorCode.INVALID_REQUEST


def test_registry_creates_openai_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        create_llm_provider("openai", model="gpt-4o-mini")
