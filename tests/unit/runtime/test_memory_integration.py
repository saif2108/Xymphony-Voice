"""Unit tests for memory recall and context injection in AgentRuntime.

Verifies:
- MemoryStore protocol integration (recall only; no writeback)
- Memory context formatting
- Recall failure / timeout graceful degradation
- Injection into LLM request system prompt alongside existing instructions
- Clean turn execution with recall-only store (no writeback required or performed)
- Normal runtime behavior when memory is not configured
"""

from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

import pytest
from tests.helpers import make_session

from xymphony_contracts.enums import EventType
from xymphony_providers.fake_llm import FakeLLMProvider
from xymphony_runtime import (
    AgentRuntime,
    LLMRuntimeConfig,
    MemoryEntry,
    MemoryRuntimeConfig,
    MemoryStore,
    RuntimeContext,
    RuntimeInput,
    format_memory_context,
)
from xymphony_runtime.cancellation import EventCancellationToken
from xymphony_runtime.turn import RuntimeTurnLifecycleState

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_context() -> RuntimeContext:
    session = make_session()
    assert session.config_hash is not None
    return RuntimeContext(
        session_id=session.id,
        organization_id=session.organization_id,
        project_id=session.project_id,
        agent_id=session.agent_id,
        agent_version_id=session.agent_version_id,
        config_hash=session.config_hash,
    )


def _make_llm_config(**overrides: object) -> LLMRuntimeConfig:
    data: dict[str, object] = {
        "provider_key": "fake",
        "model": "fake-model",
        "system_instructions": "You are a helpful assistant.",
    }
    data.update(overrides)
    return LLMRuntimeConfig(**data)  # type: ignore[arg-type]


def _make_runtime(
    memory_store: MemoryStore | None = None,
    memory_config: MemoryRuntimeConfig | None = None,
    llm_provider: FakeLLMProvider | None = None,
) -> AgentRuntime:
    return AgentRuntime(
        _make_context(),
        memory_store=memory_store,
        memory_config=memory_config,
        llm_provider=llm_provider,
        llm_config=_make_llm_config() if llm_provider is not None else None,
    )


class _SyncMemoryStore:
    """Synchronous in-process MemoryStore for testing."""

    def __init__(self, entries: list[MemoryEntry] | None = None) -> None:
        self.recalled: list[dict[str, object]] = []
        self._entries = entries or []

    def recall(
        self,
        *,
        agent_id: UUID,
        session_id: UUID,
        query: str,
        limit: int = 10,
    ) -> list[MemoryEntry]:
        self.recalled.append(
            {"agent_id": agent_id, "session_id": session_id, "query": query, "limit": limit}
        )
        return self._entries[:limit]


class _FailingMemoryStore:
    def recall(self, **_: object) -> list[MemoryEntry]:
        raise RuntimeError("store offline")


class _SlowMemoryStore:
    """Times out on every call."""

    async def recall(self, **_: object) -> list[MemoryEntry]:
        await asyncio.sleep(10)
        return []


# ---------------------------------------------------------------------------
# format_memory_context
# ---------------------------------------------------------------------------


def test_format_memory_context_empty() -> None:
    assert format_memory_context([]) == ""


def test_format_memory_context_single() -> None:
    entry = MemoryEntry(content="User prefers short answers.", memory_id="m1")
    result = format_memory_context([entry])
    assert "[1] User prefers short answers." in result


def test_format_memory_context_multiple() -> None:
    entries = [
        MemoryEntry(content="Fact A", memory_id="a"),
        MemoryEntry(content="Fact B", memory_id="b"),
    ]
    result = format_memory_context(entries)
    assert "[1] Fact A" in result
    assert "[2] Fact B" in result


def test_format_memory_context_skips_blank() -> None:
    entries = [
        MemoryEntry(content="   ", memory_id="blank"),
        MemoryEntry(content="Real fact", memory_id="real"),
    ]
    result = format_memory_context(entries)
    assert "   " not in result
    assert "Real fact" in result


# ---------------------------------------------------------------------------
# MemoryRuntimeConfig
# ---------------------------------------------------------------------------


def test_memory_config_defaults() -> None:
    cfg = MemoryRuntimeConfig()
    assert cfg.enabled is True
    assert cfg.recall_limit > 0
    assert cfg.recall_timeout_seconds > 0


def test_memory_config_disabled() -> None:
    cfg = MemoryRuntimeConfig(enabled=False)
    assert cfg.enabled is False


# ---------------------------------------------------------------------------
# _recall_memory
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recall_returns_formatted_text() -> None:
    entries = [MemoryEntry(content="User is a developer.", memory_id="m1")]
    store = _SyncMemoryStore(entries)
    runtime = _make_runtime(memory_store=store)
    await runtime.start()

    result = await runtime._recall_memory(
        text="tell me about myself",
        cancel=EventCancellationToken(),
        turn_id=uuid4(),
    )
    await runtime.stop()

    assert result is not None
    assert "User is a developer." in result
    assert len(store.recalled) == 1


@pytest.mark.asyncio
async def test_recall_empty_store_returns_none() -> None:
    store = _SyncMemoryStore([])
    runtime = _make_runtime(memory_store=store)
    await runtime.start()

    result = await runtime._recall_memory(
        text="anything",
        cancel=EventCancellationToken(),
        turn_id=uuid4(),
    )
    await runtime.stop()

    assert result is None


@pytest.mark.asyncio
async def test_recall_failure_returns_none() -> None:
    runtime = _make_runtime(memory_store=_FailingMemoryStore())
    await runtime.start()

    result = await runtime._recall_memory(
        text="anything",
        cancel=EventCancellationToken(),
        turn_id=uuid4(),
    )
    await runtime.stop()

    assert result is None


@pytest.mark.asyncio
async def test_recall_timeout_returns_none() -> None:
    cfg = MemoryRuntimeConfig(recall_timeout_seconds=0.01)
    runtime = _make_runtime(memory_store=_SlowMemoryStore(), memory_config=cfg)
    await runtime.start()

    result = await runtime._recall_memory(
        text="anything",
        cancel=EventCancellationToken(),
        turn_id=uuid4(),
    )
    await runtime.stop()

    assert result is None


@pytest.mark.asyncio
async def test_recall_disabled_returns_none() -> None:
    store = _SyncMemoryStore([MemoryEntry(content="should not appear", memory_id="x")])
    cfg = MemoryRuntimeConfig(enabled=False)
    runtime = _make_runtime(memory_store=store, memory_config=cfg)
    await runtime.start()

    result = await runtime._recall_memory(
        text="anything",
        cancel=EventCancellationToken(),
        turn_id=uuid4(),
    )
    await runtime.stop()

    assert result is None
    assert not store.recalled  # store was never called


# ---------------------------------------------------------------------------
# End-to-end turn: context injection and no write-back
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_successful_memory_recall_injected_into_llm_request() -> None:
    entries = [
        MemoryEntry(
            content="User prefers concise answers.",
            memory_id="mem-1",
        ),
    ]
    store = _SyncMemoryStore(entries=entries)
    llm = FakeLLMProvider(chunks=["Understood", " concise reply."])
    runtime = _make_runtime(memory_store=store, llm_provider=llm)
    assert runtime.memory_enabled is True

    await runtime.start()
    await runtime.handle_input(RuntimeInput.text_input("Can you help me?"))

    assert len(store.recalled) == 1
    assert store.recalled[0]["query"] == "Can you help me?"
    assert len(llm.requests) == 1
    req = llm.requests[0]

    # Verify memory context injection into system prompt
    assert "[Agent memory]" in req.system
    assert "[1] User prefers concise answers." in req.system
    assert "You are a helpful assistant." in req.system

    # Verify user message ordering preserved
    assert len(req.messages) == 1
    assert req.messages[0].content == "Can you help me?"

    # Turn completes normally
    turn = runtime.turns[0]
    assert turn.state == RuntimeTurnLifecycleState.COMPLETED
    assert any(event.type == EventType.LLM_RESPONSE for event in runtime.admitted_events)
    await runtime.stop()


@pytest.mark.asyncio
async def test_turn_completion_is_recall_only_without_writeback() -> None:
    """Verifies that runtime operates in recall-only mode without any writeback.

    The store only provides recall(); no remember/writeback methods are expected or called.
    """
    store = _SyncMemoryStore([MemoryEntry(content="Known fact", memory_id="kf1")])
    assert not hasattr(store, "remember")
    llm = FakeLLMProvider(chunks=["I have processed your request."])
    runtime = _make_runtime(memory_store=store, llm_provider=llm)

    await runtime.start()
    await runtime.handle_input(RuntimeInput.text_input("My secret project name is Apollo"))

    # Turn completes normally using only recall during context assembly
    turn = runtime.turns[0]
    assert turn.state == RuntimeTurnLifecycleState.COMPLETED
    assert len(store.recalled) == 1
    assert store.recalled[0]["query"] == "My secret project name is Apollo"

    await runtime.stop()


@pytest.mark.asyncio
async def test_runtime_behavior_unaffected_when_memory_not_configured() -> None:
    """Verifies runtime operates normally when memory_store is None."""
    llm = FakeLLMProvider(chunks=["Standard response."])
    runtime = _make_runtime(memory_store=None, llm_provider=llm)
    assert runtime.memory_enabled is False

    await runtime.start()
    await runtime.handle_input(RuntimeInput.text_input("Hello there"))

    turn = runtime.turns[0]
    assert turn.state == RuntimeTurnLifecycleState.COMPLETED
    assert len(llm.requests) == 1
    req = llm.requests[0]
    assert "[Agent memory]" not in req.system

    await runtime.stop()


# ---------------------------------------------------------------------------
# memory_enabled property
# ---------------------------------------------------------------------------


def test_memory_enabled_with_store() -> None:
    runtime = _make_runtime(memory_store=_SyncMemoryStore())
    assert runtime.memory_enabled is True


def test_memory_enabled_without_store() -> None:
    runtime = _make_runtime()
    assert runtime.memory_enabled is False


def test_memory_enabled_store_but_disabled_config() -> None:
    cfg = MemoryRuntimeConfig(enabled=False)
    runtime = _make_runtime(memory_store=_SyncMemoryStore(), memory_config=cfg)
    assert runtime.memory_enabled is False
