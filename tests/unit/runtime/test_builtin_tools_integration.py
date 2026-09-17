"""Integration tests for built-in tools executed through AgentRuntime (Phase 4 Step 5)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
from tests.helpers import make_session

from xymphony_contracts import CreateSessionRequest, EventType, MessageRole, TurnStatus
from xymphony_contracts.events import LLMResponsePayload
from xymphony_contracts.llm import LLMToolCall
from xymphony_providers.fake_llm import FakeLLMProvider, FakeLLMResponse
from xymphony_providers.fake_tts import FakeTTSProvider
from xymphony_runtime import (
    AgentRuntime,
    InMemoryConversationRepository,
    InMemorySessionRepository,
    LLMRuntimeConfig,
    RuntimeContext,
    RuntimeInput,
    TTSRuntimeConfig,
)
from xymphony_runtime.conversation import message_text
from xymphony_runtime.turn import RuntimeTurnLifecycleState
from xymphony_tools import (
    ToolRegistry,
    create_current_time_tool,
    create_default_tool_registry,
)


def _build_test_runtime(
    *,
    llm_provider: FakeLLMProvider,
    tool_registry: ToolRegistry | None = None,
    tts_provider: FakeTTSProvider | None = None,
    sessions: InMemorySessionRepository | None = None,
    conversation: InMemoryConversationRepository | None = None,
    max_tool_iterations: int = 4,
) -> tuple[
    AgentRuntime,
    InMemorySessionRepository,
    InMemoryConversationRepository,
    FakeTTSProvider,
]:
    resolved_sessions = sessions or InMemorySessionRepository()
    resolved_conversation = conversation or InMemoryConversationRepository()
    resolved_tts = tts_provider or FakeTTSProvider(chunks=["tts-audio"])

    session_contract = make_session()
    assert session_contract.config_hash is not None
    resolved_sessions.create_session(
        CreateSessionRequest(
            session_id=session_contract.id,
            organization_id=session_contract.organization_id,
            project_id=session_contract.project_id,
            agent_id=session_contract.agent_id,
            agent_version_id=session_contract.agent_version_id,
            config_hash=session_contract.config_hash,
        )
    )

    context = RuntimeContext(
        session_id=session_contract.id,
        organization_id=session_contract.organization_id,
        project_id=session_contract.project_id,
        agent_id=session_contract.agent_id,
        agent_version_id=session_contract.agent_version_id,
        config_hash=session_contract.config_hash,
    )

    llm_config = LLMRuntimeConfig(
        provider_key="fake",
        model="fake-model",
        max_tool_iterations=max_tool_iterations,
    )
    tts_config = TTSRuntimeConfig(provider_key="fake", voice_ref="voice_default")

    runtime = AgentRuntime(
        context,
        llm_provider=llm_provider,
        llm_config=llm_config,
        tts_provider=resolved_tts,
        tts_config=tts_config,
        session_repository=resolved_sessions,
        conversation_repository=resolved_conversation,
        tool_registry=tool_registry,
    )
    return runtime, resolved_sessions, resolved_conversation, resolved_tts


@pytest.mark.asyncio
async def test_end_to_end_calculate_tool_calling_flow() -> None:
    """AgentRuntime executes the real calculate tool deterministically."""
    registry = create_default_tool_registry()

    llm = FakeLLMProvider(
        responses=[
            FakeLLMResponse(
                chunks=[],
                tool_calls=(
                    LLMToolCall(
                        id="call_calc_1",
                        name="calculate",
                        arguments='{"expression": "42 * 100"}',
                    ),
                ),
            ),
            FakeLLMResponse(chunks=["42 * 100 is 4200."]),
        ]
    )

    runtime, _, conversation, tts = _build_test_runtime(
        llm_provider=llm,
        tool_registry=registry,
    )
    await runtime.start()
    await runtime.handle_input(RuntimeInput.text_input("What is 42 times 100?"))

    assert len(runtime.turns) == 1
    turn = runtime.turns[0]
    assert turn.state == RuntimeTurnLifecycleState.COMPLETED
    assert turn.to_contract().status == TurnStatus.COMMITTED

    # LLM called twice: once for tool call, once with tool result
    assert len(llm.requests) == 2
    # Verify the second request contained the real tool result "4200"
    second_request = llm.requests[1]
    tool_messages = [m for m in second_request.messages if m.role.value == "tool"]
    assert len(tool_messages) == 1
    assert tool_messages[0].tool_call_id == "call_calc_1"
    assert tool_messages[0].content == "4200"

    # TTS only receives final assistant text
    assert len(tts.requests) == 1
    assert tts.requests[0].text == "42 * 100 is 4200."

    # Final assistant response event emitted
    resp_events = [e for e in runtime.admitted_events if e.type == EventType.LLM_RESPONSE]
    assert len(resp_events) == 1
    assert isinstance(resp_events[0].payload, LLMResponsePayload)
    assert resp_events[0].payload.text == "42 * 100 is 4200."

    # Persistence: only user and final assistant text
    messages = conversation.list_messages(runtime.context.session_id)
    assert len(messages) == 2
    assert messages[0].role == MessageRole.USER
    assert message_text(messages[0]) == "What is 42 times 100?"
    assert messages[1].role == MessageRole.ASSISTANT
    assert message_text(messages[1]) == "42 * 100 is 4200."


@pytest.mark.asyncio
async def test_end_to_end_current_time_tool_flow() -> None:
    """AgentRuntime executes real get_current_time tool with deterministic factory."""
    frozen_time = datetime(2026, 9, 17, 10, 0, 0, tzinfo=UTC)
    registry = ToolRegistry()
    registry.register(create_current_time_tool(now_factory=lambda: frozen_time))

    llm = FakeLLMProvider(
        responses=[
            FakeLLMResponse(
                chunks=[],
                tool_calls=(
                    LLMToolCall(
                        id="call_time_1",
                        name="get_current_time",
                        arguments='{"timezone": "UTC"}',
                    ),
                ),
            ),
            FakeLLMResponse(chunks=["It is currently 10:00:00 UTC."]),
        ]
    )

    runtime, _, conversation, _ = _build_test_runtime(
        llm_provider=llm,
        tool_registry=registry,
    )
    await runtime.start()
    await runtime.handle_input(RuntimeInput.text_input("What time is it?"))

    assert len(llm.requests) == 2
    tool_msg = next(m for m in llm.requests[1].messages if m.role.value == "tool")
    assert tool_msg.tool_call_id == "call_time_1"
    assert '"time": "10:00:00"' in tool_msg.content
    assert '"date": "2026-09-17"' in tool_msg.content


@pytest.mark.asyncio
async def test_multiple_builtin_tools_in_single_turn() -> None:
    """AgentRuntime handles multiple distinct tool calls in a single turn."""
    registry = create_default_tool_registry()

    llm = FakeLLMProvider(
        responses=[
            FakeLLMResponse(
                chunks=[],
                tool_calls=(
                    LLMToolCall(
                        id="call_calc",
                        name="calculate",
                        arguments='{"expression": "50 + 50"}',
                    ),
                    LLMToolCall(
                        id="call_stats",
                        name="text_stats",
                        arguments='{"text": "one two three"}',
                    ),
                ),
            ),
            FakeLLMResponse(chunks=["Calculation is 100 and word count is 3."]),
        ]
    )

    runtime, _, _, _ = _build_test_runtime(
        llm_provider=llm,
        tool_registry=registry,
    )
    await runtime.start()
    await runtime.handle_input(RuntimeInput.text_input("Calculate and count."))

    assert len(llm.requests) == 2
    tool_messages = [m for m in llm.requests[1].messages if m.role.value == "tool"]
    assert len(tool_messages) == 2
    assert tool_messages[0].tool_call_id == "call_calc"
    assert tool_messages[0].content == "100"
    assert tool_messages[1].tool_call_id == "call_stats"
    assert '"word_count": 3' in tool_messages[1].content


@pytest.mark.asyncio
async def test_tool_error_handled_in_runtime_loop() -> None:
    """AgentRuntime normalizes tool failure and passes error to LLM without crashing."""
    registry = create_default_tool_registry()

    llm = FakeLLMProvider(
        responses=[
            FakeLLMResponse(
                chunks=[],
                tool_calls=(
                    LLMToolCall(
                        id="call_div_zero",
                        name="calculate",
                        arguments='{"expression": "100 / 0"}',
                    ),
                ),
            ),
            FakeLLMResponse(chunks=["Division by zero is undefined."]),
        ]
    )

    runtime, _, _, _ = _build_test_runtime(
        llm_provider=llm,
        tool_registry=registry,
    )
    await runtime.start()
    await runtime.handle_input(RuntimeInput.text_input("Divide 100 by zero."))

    turn = runtime.turns[0]
    assert turn.state == RuntimeTurnLifecycleState.COMPLETED

    assert len(llm.requests) == 2
    tool_msg = next(m for m in llm.requests[1].messages if m.role.value == "tool")
    assert tool_msg.tool_call_id == "call_div_zero"
    # Contains normalized error string from ToolResult
    assert "Division by zero" in tool_msg.content


@pytest.mark.asyncio
async def test_tool_loop_cancellation_during_turn() -> None:
    """Cancelling a turn stops tool execution and fails/cancels the turn cleanly."""
    registry = create_default_tool_registry()

    llm = FakeLLMProvider(
        responses=[
            FakeLLMResponse(
                chunks=[],
                delay_seconds=0.05,
                tool_calls=(
                    LLMToolCall(
                        id="call_slow",
                        name="calculate",
                        arguments='{"expression": "1 + 1"}',
                    ),
                ),
            ),
        ]
    )

    runtime, _, conversation, _ = _build_test_runtime(
        llm_provider=llm,
        tool_registry=registry,
    )
    await runtime.start()
    turn_task = asyncio.create_task(
        runtime.handle_input(RuntimeInput.text_input("Start calculation"))
    )
    await asyncio.sleep(0.01)

    active_turn = runtime.current_turn
    assert active_turn is not None
    await runtime.handle_input(RuntimeInput.cancel_turn(active_turn.id))
    await turn_task

    assert active_turn.state == RuntimeTurnLifecycleState.CANCELLED
    persisted = conversation.list_messages(runtime.context.session_id)
    assert not any(m.role == MessageRole.ASSISTANT for m in persisted)
