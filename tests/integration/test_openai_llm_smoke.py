"""Optional OpenAI LLM smoke test — skipped unless OPENAI_INTEGRATION=1."""

from __future__ import annotations

import os

import pytest

from xymphony_contracts.llm import LLMMessage, LLMRequest, LLMRole
from xymphony_providers.registry import create_llm_provider
from xymphony_runtime.cancellation import EventCancellationToken

pytestmark = pytest.mark.openai


def _integration_enabled() -> bool:
    return os.getenv("OPENAI_INTEGRATION") == "1" and bool(os.getenv("OPENAI_API_KEY"))


@pytest.mark.asyncio
@pytest.mark.skipif(
    not _integration_enabled(),
    reason="Set OPENAI_INTEGRATION=1 and OPENAI_API_KEY",
)
async def test_openai_stream_smoke() -> None:
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    provider = create_llm_provider("openai", model=model)
    request = LLMRequest(
        provider_key="openai",
        model=model,
        messages=(LLMMessage(role=LLMRole.USER, content="Reply with exactly: pong"),),
    )
    chunks = [chunk async for chunk in provider.stream(request, cancel=EventCancellationToken())]
    text = "".join(chunk.delta for chunk in chunks)
    assert text.strip()
    api_key = os.environ["OPENAI_API_KEY"]
    assert api_key not in text
