"""Focused unit tests for runtime RAG retrieval integration."""

from __future__ import annotations

import time

import pytest
from tests.helpers import make_session

from xymphony_contracts.enums import EventType
from xymphony_providers.fake_llm import FakeLLMProvider
from xymphony_runtime import (
    AgentRuntime,
    LLMContextAssembler,
    LLMRuntimeConfig,
    RAGRuntimeConfig,
    RetrievalResult,
    RuntimeContext,
    RuntimeInput,
)
from xymphony_runtime.turn import RuntimeTurnLifecycleState


def make_context() -> RuntimeContext:
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


def make_llm_config(**overrides: object) -> LLMRuntimeConfig:
    data: dict[str, object] = {
        "provider_key": "fake",
        "model": "fake-model",
        "system_instructions": "You are a helpful assistant.",
    }
    data.update(overrides)
    return LLMRuntimeConfig(**data)  # type: ignore[arg-type]


class FakeRetriever:
    """Mock Retriever for testing runtime integration."""

    def __init__(
        self,
        *,
        results: list[RetrievalResult] | None = None,
        fail: bool = False,
        delay_seconds: float = 0.0,
    ) -> None:
        self.results = results if results is not None else []
        self.fail = fail
        self.delay_seconds = delay_seconds
        self.call_count = 0
        self.last_query: str | None = None

    def retrieve(self, *, query: str, limit: int = 5) -> list[RetrievalResult]:
        self.call_count += 1
        self.last_query = query
        if self.delay_seconds > 0:
            time.sleep(self.delay_seconds)
        if self.fail:
            raise RuntimeError("Database connection timed out during vector search")
        return self.results[:limit]


@pytest.mark.asyncio
async def test_successful_rag_retrieval_injected_into_llm_request() -> None:
    chunks = [
        RetrievalResult(
            content="Xymphony Voice is an open platform for realtime voice agents.",
            score=0.92,
            document_id="doc-1",
            chunk_id="chunk-1",
        ),
        RetrievalResult(
            content="Audio frames are processed via custom pipelines.",
            score=0.85,
            document_id="doc-1",
            chunk_id="chunk-2",
        ),
    ]
    retriever = FakeRetriever(results=chunks)
    llm = FakeLLMProvider(chunks=["Understood", " well."])
    runtime = AgentRuntime(
        make_context(),
        llm_provider=llm,
        llm_config=make_llm_config(),
        retriever=retriever,
    )
    assert runtime.rag_enabled is True

    await runtime.start()
    await runtime.handle_input(RuntimeInput.text_input("How does Xymphony work?"))

    assert retriever.call_count == 1
    assert retriever.last_query == "How does Xymphony work?"
    assert len(llm.requests) == 1
    req = llm.requests[0]

    # Verify context injection into system prompt
    assert "[Retrieved context]" in req.system
    assert "[1] Xymphony Voice is an open platform for realtime voice agents." in req.system
    assert "[2] Audio frames are processed via custom pipelines." in req.system
    assert "You are a helpful assistant." in req.system

    # Verify message ordering preserved
    assert len(req.messages) == 1
    assert req.messages[0].content == "How does Xymphony work?"

    # Turn completes normally
    turn = runtime.turns[0]
    assert turn.state == RuntimeTurnLifecycleState.COMPLETED
    assert any(event.type == EventType.LLM_RESPONSE for event in runtime.admitted_events)


@pytest.mark.asyncio
async def test_empty_rag_results_does_not_inject_context() -> None:
    retriever = FakeRetriever(results=[])
    llm = FakeLLMProvider(chunks=["No info", " found."])
    runtime = AgentRuntime(
        make_context(),
        llm_provider=llm,
        llm_config=make_llm_config(),
        retriever=retriever,
    )

    await runtime.start()
    await runtime.handle_input(RuntimeInput.text_input("Unknown topic"))

    assert retriever.call_count == 1
    assert len(llm.requests) == 1
    req = llm.requests[0]

    # No retrieved context section should be present
    assert "[Retrieved context]" not in req.system
    assert req.system == "You are a helpful assistant."
    assert req.messages[0].content == "Unknown topic"

    turn = runtime.turns[0]
    assert turn.state == RuntimeTurnLifecycleState.COMPLETED


@pytest.mark.asyncio
async def test_rag_retrieval_failure_does_not_break_voice_turn() -> None:
    retriever = FakeRetriever(fail=True)
    llm = FakeLLMProvider(chunks=["Still", " functioning."])
    runtime = AgentRuntime(
        make_context(),
        llm_provider=llm,
        llm_config=make_llm_config(),
        retriever=retriever,
    )

    await runtime.start()
    await runtime.handle_input(RuntimeInput.text_input("Trigger error"))

    assert retriever.call_count == 1
    assert len(llm.requests) == 1
    req = llm.requests[0]

    # System prompt falls back gracefully without breaking
    assert "[Retrieved context]" not in req.system
    assert req.system == "You are a helpful assistant."

    turn = runtime.turns[0]
    assert turn.state == RuntimeTurnLifecycleState.COMPLETED


@pytest.mark.asyncio
async def test_rag_retrieval_timeout_does_not_break_voice_turn() -> None:
    # Retriever takes 0.3s, but timeout is set to 0.05s
    retriever = FakeRetriever(
        results=[RetrievalResult(content="Late chunk", score=0.8, document_id="d", chunk_id="c")],
        delay_seconds=0.3,
    )
    llm = FakeLLMProvider(chunks=["Recovered", " from timeout."])
    runtime = AgentRuntime(
        make_context(),
        llm_provider=llm,
        llm_config=make_llm_config(),
        retriever=retriever,
        rag_config=RAGRuntimeConfig(timeout_seconds=0.05),
    )

    await runtime.start()
    await runtime.handle_input(RuntimeInput.text_input("Slow retrieval query"))

    # Turn should still complete cleanly
    assert len(llm.requests) == 1
    req = llm.requests[0]
    assert "[Retrieved context]" not in req.system
    assert len(runtime.turns) > 0
    turn = runtime.turns[0]
    assert turn.state == RuntimeTurnLifecycleState.COMPLETED


@pytest.mark.asyncio
async def test_rag_disabled_mode_via_none_retriever() -> None:
    llm = FakeLLMProvider(chunks=["Hello!"])
    runtime = AgentRuntime(
        make_context(),
        llm_provider=llm,
        llm_config=make_llm_config(),
        retriever=None,
    )
    assert runtime.rag_enabled is False

    await runtime.start()
    await runtime.handle_input(RuntimeInput.text_input("Hello there"))

    assert len(llm.requests) == 1
    assert "[Retrieved context]" not in llm.requests[0].system
    assert runtime.turns[0].state == RuntimeTurnLifecycleState.COMPLETED


@pytest.mark.asyncio
async def test_rag_disabled_mode_via_config_flag() -> None:
    retriever = FakeRetriever(
        results=[RetrievalResult(content="Ignored", score=1.0, document_id="d", chunk_id="c")]
    )
    llm = FakeLLMProvider(chunks=["Hello!"])
    runtime = AgentRuntime(
        make_context(),
        llm_provider=llm,
        llm_config=make_llm_config(),
        retriever=retriever,
        rag_config=RAGRuntimeConfig(enabled=False),
    )
    assert runtime.rag_enabled is False

    await runtime.start()
    await runtime.handle_input(RuntimeInput.text_input("Should not retrieve"))

    assert retriever.call_count == 0
    assert len(llm.requests) == 1
    assert "[Retrieved context]" not in llm.requests[0].system


def test_context_assembler_soft_fails_oversized_knowledge() -> None:
    assembler = LLMContextAssembler()
    config = make_llm_config(
        max_input_tokens=50,
        system_instructions="Brief instructions.",
    )
    # Oversized knowledge text that would exceed 50 tokens
    huge_knowledge = " ".join(["knowledge"] * 80)
    request = assembler.assemble(
        history=(),
        current_user_text="User question",
        config=config,
        knowledge_text=huge_knowledge,
    )
    # The oversized knowledge was dropped to satisfy budget, allowing request to be assembled
    assert "[Retrieved context]" not in request.system
    assert request.messages[0].content == "User question"
