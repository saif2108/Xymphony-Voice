"""Unit tests for AgentRuntime tool-calling loop (Phase 4 Step 3)."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from tests.helpers import make_session

from xymphony_contracts import CreateSessionRequest, EventType, MessageRole, TurnStatus
from xymphony_contracts.events import ErrorPayload, LLMResponsePayload
from xymphony_contracts.llm import (
    LLMMessage,
    LLMRole,
    LLMToolCall,
)
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
from xymphony_tools import Tool, ToolRegistry


def _make_runtime_context() -> RuntimeContext:
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


def _build_test_runtime(
    *,
    llm_provider: FakeLLMProvider,
    tts_provider: FakeTTSProvider | None = None,
    tool_registry: ToolRegistry | None = None,
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
async def test_one_tool_call_followed_by_final_text() -> None:
    registry = ToolRegistry()

    def get_weather(city: str) -> dict[str, Any]:
        return {"city": city, "forecast": "sunny"}

    registry.register(
        Tool(
            name="get_weather",
            description="Get current weather for a city",
            parameters={
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
            handler=get_weather,
        )
    )

    llm = FakeLLMProvider(
        responses=[
            FakeLLMResponse(
                chunks=[],
                tool_calls=(
                    LLMToolCall(
                        id="call_weather_1",
                        name="get_weather",
                        arguments='{"city": "Tokyo"}',
                    ),
                ),
            ),
            FakeLLMResponse(chunks=["Tokyo ", "is sunny."]),
        ]
    )

    runtime, _, conversation, tts = _build_test_runtime(
        llm_provider=llm,
        tool_registry=registry,
    )
    await runtime.start()
    await runtime.handle_input(RuntimeInput.text_input("What is the weather in Tokyo?"))

    assert len(runtime.turns) == 1
    turn = runtime.turns[0]
    assert turn.state == RuntimeTurnLifecycleState.COMPLETED
    assert turn.to_contract().status == TurnStatus.COMMITTED

    assert len(llm.requests) == 2
    # TTS received final text only
    assert len(tts.requests) == 1
    assert tts.requests[0].text == "Tokyo is sunny."

    # Events
    response_events = [e for e in runtime.admitted_events if e.type == EventType.LLM_RESPONSE]
    assert len(response_events) == 1
    assert isinstance(response_events[0].payload, LLMResponsePayload)
    assert response_events[0].payload.text == "Tokyo is sunny."

    # Persistence: only user and final assistant text persisted, not intermediate tool messages
    persisted = conversation.list_messages(runtime.context.session_id)
    assert len(persisted) == 2
    assert persisted[0].role == MessageRole.USER
    assert message_text(persisted[0]) == "What is the weather in Tokyo?"
    assert persisted[1].role == MessageRole.ASSISTANT
    assert message_text(persisted[1]) == "Tokyo is sunny."


@pytest.mark.asyncio
async def test_multiple_tool_calls_executed_in_order() -> None:
    registry = ToolRegistry()
    execution_order: list[str] = []

    def record_first(step: int) -> dict[str, int]:
        execution_order.append(f"step_{step}")
        return {"step": step}

    def record_second(step: int) -> dict[str, int]:
        execution_order.append(f"step_{step}")
        return {"step": step}

    registry.register(
        Tool(
            name="record_first",
            parameters={"type": "object", "properties": {"step": {"type": "integer"}}},
            handler=record_first,
        )
    )
    registry.register(
        Tool(
            name="record_second",
            parameters={"type": "object", "properties": {"step": {"type": "integer"}}},
            handler=record_second,
        )
    )

    llm = FakeLLMProvider(
        responses=[
            FakeLLMResponse(
                chunks=[],
                tool_calls=(
                    LLMToolCall(id="c1", name="record_first", arguments='{"step": 1}'),
                    LLMToolCall(id="c2", name="record_second", arguments='{"step": 2}'),
                ),
            ),
            FakeLLMResponse(chunks=["Steps recorded."]),
        ]
    )

    runtime, _, _, _ = _build_test_runtime(
        llm_provider=llm,
        tool_registry=registry,
    )
    await runtime.start()
    await runtime.handle_input(RuntimeInput.text_input("Run steps"))

    assert execution_order == ["step_1", "step_2"]
    assert len(llm.requests) == 2

    # Verify second request received tool messages in order
    round2_messages = llm.requests[1].messages
    # Last three messages: assistant with tool calls, tool c1, tool c2
    assistant_msg = round2_messages[-3]
    assert assistant_msg.role == LLMRole.ASSISTANT
    assert len(assistant_msg.tool_calls) == 2
    assert assistant_msg.tool_calls[0].id == "c1"
    assert assistant_msg.tool_calls[1].id == "c2"

    tool_msg_1 = round2_messages[-2]
    assert tool_msg_1.role == LLMRole.TOOL
    assert tool_msg_1.tool_call_id == "c1"

    tool_msg_2 = round2_messages[-1]
    assert tool_msg_2.role == LLMRole.TOOL
    assert tool_msg_2.tool_call_id == "c2"


@pytest.mark.asyncio
async def test_tool_results_fed_back_as_provider_neutral_messages() -> None:
    registry = ToolRegistry()

    def calc(val: int) -> int:
        return val * 2

    registry.register(
        Tool(
            name="calc",
            parameters={"type": "object", "properties": {"val": {"type": "integer"}}},
            handler=calc,
        )
    )

    llm = FakeLLMProvider(
        responses=[
            FakeLLMResponse(
                chunks=["Thinking..."],
                tool_calls=(
                    LLMToolCall(id="calc_1", name="calc", arguments='{"val": 21}'),
                ),
            ),
            FakeLLMResponse(chunks=["The answer is 42."]),
        ]
    )

    runtime, _, _, _ = _build_test_runtime(
        llm_provider=llm,
        tool_registry=registry,
    )
    await runtime.start()
    await runtime.handle_input(RuntimeInput.text_input("Calculate 21 * 2"))

    assert len(llm.requests) == 2
    round2_request = llm.requests[1]

    # Verify provider-neutral messages structure
    # Should include user message, then assistant message with tool calls, then tool result
    extra = round2_request.messages[-2:]
    assistant_msg = extra[0]
    tool_msg = extra[1]

    assert isinstance(assistant_msg, LLMMessage)
    assert assistant_msg.role == LLMRole.ASSISTANT
    assert assistant_msg.content == "Thinking..."
    assert len(assistant_msg.tool_calls) == 1
    assert assistant_msg.tool_calls[0].id == "calc_1"

    assert isinstance(tool_msg, LLMMessage)
    assert tool_msg.role == LLMRole.TOOL
    assert tool_msg.tool_call_id == "calc_1"
    assert "42" in tool_msg.content


@pytest.mark.asyncio
async def test_tool_definitions_exposed_to_llm() -> None:
    registry = ToolRegistry()
    registry.register(
        Tool(
            name="search",
            description="Search knowledge base",
            parameters={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
            handler=lambda query: "found",
        )
    )
    registry.register(
        Tool(
            name="action",
            description="Execute action",
            parameters={"type": "object", "properties": {}},
            handler=lambda: "ok",
        )
    )

    llm = FakeLLMProvider(chunks=["Done"])
    runtime, _, _, _ = _build_test_runtime(
        llm_provider=llm,
        tool_registry=registry,
    )
    await runtime.start()
    await runtime.handle_input(RuntimeInput.text_input("Hello"))

    assert len(llm.requests) == 1
    request = llm.requests[0]
    definitions = request.tools
    assert len(definitions) == 2
    # Deterministic alphabetical ordering
    assert [d.name for d in definitions] == ["action", "search"]
    assert definitions[1].description == "Search knowledge base"
    assert definitions[1].parameters["required"] == ["query"]


@pytest.mark.asyncio
async def test_text_only_behavior_remains_unchanged_with_registry() -> None:
    registry = ToolRegistry()
    registry.register(
        Tool(
            name="dummy_tool",
            description="A dummy tool",
            handler=lambda: "dummy",
        )
    )

    llm = FakeLLMProvider(chunks=["Direct ", "text response."])
    runtime, _, conversation, tts = _build_test_runtime(
        llm_provider=llm,
        tool_registry=registry,
    )
    await runtime.start()
    await runtime.handle_input(RuntimeInput.text_input("Say hi"))

    turn = runtime.turns[0]
    assert turn.state == RuntimeTurnLifecycleState.COMPLETED
    assert len(llm.requests) == 1
    assert len(tts.requests) == 1
    assert tts.requests[0].text == "Direct text response."

    response_events = [e for e in runtime.admitted_events if e.type == EventType.LLM_RESPONSE]
    assert len(response_events) == 1
    assert isinstance(response_events[0].payload, LLMResponsePayload)
    assert response_events[0].payload.text == "Direct text response."


@pytest.mark.asyncio
async def test_no_registry_behavior_remains_unchanged() -> None:
    llm = FakeLLMProvider(chunks=["Standard ", "reply"])
    runtime, _, conversation, tts = _build_test_runtime(
        llm_provider=llm,
        tool_registry=None,
    )
    await runtime.start()
    await runtime.handle_input(RuntimeInput.text_input("Hello"))

    assert len(llm.requests) == 1
    assert llm.requests[0].tools == ()
    assert runtime.turns[0].state == RuntimeTurnLifecycleState.COMPLETED
    assert len(tts.requests) == 1
    assert tts.requests[0].text == "Standard reply"


@pytest.mark.asyncio
async def test_loop_limit_failure_with_error_code() -> None:
    registry = ToolRegistry()
    registry.register(
        Tool(
            name="ping",
            description="Ping tool",
            handler=lambda: "pong",
        )
    )

    # Always returns a tool call to exceed the limit of 4 iterations
    looping_responses = [
        FakeLLMResponse(
            chunks=[],
            tool_calls=(LLMToolCall(id=f"ping_{i}", name="ping", arguments="{}"),),
        )
        for i in range(5)
    ]
    llm = FakeLLMProvider(responses=looping_responses)

    runtime, _, conversation, tts = _build_test_runtime(
        llm_provider=llm,
        tool_registry=registry,
        max_tool_iterations=4,
    )
    await runtime.start()
    await runtime.handle_input(RuntimeInput.text_input("Keep looping"))

    turn = runtime.turns[0]
    assert turn.state == RuntimeTurnLifecycleState.FAILED
    assert turn.to_contract().status == TurnStatus.FAILED
    assert turn.error_code == "tool_loop_limit_exceeded"

    # Exactly max_tool_iterations calls were made
    assert len(llm.requests) == 4

    # Error event emitted
    error_events = [e for e in runtime.admitted_events if e.type == EventType.ERROR]
    assert any(
        isinstance(e.payload, ErrorPayload) and e.payload.code == "tool_loop_limit_exceeded"
        for e in error_events
    )

    # No TTS called
    assert len(tts.requests) == 0

    # No assistant message persisted
    persisted = conversation.list_messages(runtime.context.session_id)
    assert not any(m.role == MessageRole.ASSISTANT for m in persisted)


@pytest.mark.asyncio
async def test_cancellation_before_first_llm_call() -> None:
    llm = FakeLLMProvider(chunks=["Should not run"])
    runtime, _, conversation, tts = _build_test_runtime(
        llm_provider=llm,
        tool_registry=ToolRegistry(),
    )
    await runtime.start()

    # Pre-cancel turn before handling input
    await runtime.handle_input(RuntimeInput.user_speech_started())
    turn_id = runtime.current_turn_id
    assert turn_id is not None
    await runtime.handle_input(RuntimeInput.cancel_turn())

    assert len(llm.requests) == 0
    assert len(tts.requests) == 0


@pytest.mark.asyncio
async def test_cancellation_between_tool_rounds() -> None:
    registry = ToolRegistry()

    # Tool handler triggers turn cancellation on the runtime
    runtime_ref: list[AgentRuntime] = []

    async def cancel_on_call() -> str:
        # Cancel turn during tool execution
        await runtime_ref[0].handle_input(RuntimeInput.cancel_turn())
        return "cancelled_result"

    registry.register(
        Tool(
            name="trigger_cancel",
            handler=cancel_on_call,
        )
    )

    llm = FakeLLMProvider(
        responses=[
            FakeLLMResponse(
                chunks=[],
                tool_calls=(
                    LLMToolCall(id="tc_cancel", name="trigger_cancel", arguments="{}"),
                ),
            ),
            FakeLLMResponse(chunks=["Should not be reached"]),
        ]
    )

    runtime, _, conversation, tts = _build_test_runtime(
        llm_provider=llm,
        tool_registry=registry,
    )
    runtime_ref.append(runtime)

    await runtime.start()
    await runtime.handle_input(RuntimeInput.text_input("Run cancel tool"))

    turn = runtime.turns[0]
    assert turn.state == RuntimeTurnLifecycleState.CANCELLED

    # Only 1 LLM request was made; 2nd round was stopped by cancellation check
    assert len(llm.requests) == 1
    # No TTS called
    assert len(tts.requests) == 0
    # No assistant response persisted
    persisted = conversation.list_messages(runtime.context.session_id)
    assert not any(m.role == MessageRole.ASSISTANT for m in persisted)


@pytest.mark.asyncio
async def test_cancellation_before_individual_tool_execution() -> None:
    registry = ToolRegistry()
    second_tool_executed = False
    runtime_ref: list[AgentRuntime] = []

    async def first_tool() -> str:
        # Cancel the turn
        await runtime_ref[0].handle_input(RuntimeInput.cancel_turn())
        return "first_done"

    def second_tool() -> str:
        nonlocal second_tool_executed
        second_tool_executed = True
        return "second_done"

    registry.register(Tool(name="first_tool", handler=first_tool))
    registry.register(Tool(name="second_tool", handler=second_tool))

    llm = FakeLLMProvider(
        responses=[
            FakeLLMResponse(
                chunks=[],
                tool_calls=(
                    LLMToolCall(id="t1", name="first_tool", arguments="{}"),
                    LLMToolCall(id="t2", name="second_tool", arguments="{}"),
                ),
            ),
            FakeLLMResponse(chunks=["Unreachable"]),
        ]
    )

    runtime, _, conversation, tts = _build_test_runtime(
        llm_provider=llm,
        tool_registry=registry,
    )
    runtime_ref.append(runtime)

    await runtime.start()
    await runtime.handle_input(RuntimeInput.text_input("Run two tools"))

    turn = runtime.turns[0]
    assert turn.state == RuntimeTurnLifecycleState.CANCELLED
    # Crucial assertion: second tool was never invoked because cancellation check ran before it
    assert second_tool_executed is False
    assert len(llm.requests) == 1
    assert len(tts.requests) == 0


@pytest.mark.asyncio
async def test_no_tts_or_persistence_after_cancellation_or_loop_limit() -> None:
    # 1. Test loop limit
    llm_loop = FakeLLMProvider(
        responses=[
            FakeLLMResponse(
                chunks=[],
                tool_calls=(LLMToolCall(id=f"c_{i}", name="nonexistent", arguments="{}"),),
            )
            for i in range(5)
        ]
    )
    runtime_loop, _, conv_loop, tts_loop = _build_test_runtime(
        llm_provider=llm_loop,
        tool_registry=ToolRegistry(),
        max_tool_iterations=2,
    )
    await runtime_loop.start()
    await runtime_loop.handle_input(RuntimeInput.text_input("loop"))
    assert runtime_loop.turns[0].state == RuntimeTurnLifecycleState.FAILED
    assert len(tts_loop.requests) == 0
    assert not any(
        m.role == MessageRole.ASSISTANT
        for m in conv_loop.list_messages(runtime_loop.context.session_id)
    )

    # 2. Test cancellation
    llm_cancel = FakeLLMProvider(chunks=["slow ", "stream"], delay_seconds=0.05)
    runtime_cancel, _, conv_cancel, tts_cancel = _build_test_runtime(
        llm_provider=llm_cancel,
        tool_registry=ToolRegistry(),
    )
    await runtime_cancel.start()
    task = asyncio.create_task(runtime_cancel.handle_input(RuntimeInput.text_input("cancel me")))
    await asyncio.sleep(0.06)
    await runtime_cancel.handle_input(RuntimeInput.cancel_turn())
    await task

    assert runtime_cancel.turns[0].state == RuntimeTurnLifecycleState.CANCELLED
    assert len(tts_cancel.requests) == 0
    assert not any(
        m.role == MessageRole.ASSISTANT
        for m in conv_cancel.list_messages(runtime_cancel.context.session_id)
    )


@pytest.mark.asyncio
async def test_defensive_missing_registry_tool_call_handling() -> None:
    # Provider unexpectedly returns tool calls when no registry is configured
    llm = FakeLLMProvider(
        responses=[
            FakeLLMResponse(
                chunks=[],
                tool_calls=(
                    LLMToolCall(id="call_unexpected", name="some_tool", arguments="{}"),
                ),
            ),
            FakeLLMResponse(chunks=["I cannot run tools right now."]),
        ]
    )

    # Runtime with tool_registry=None
    runtime, _, conversation, tts = _build_test_runtime(
        llm_provider=llm,
        tool_registry=None,
    )
    await runtime.start()
    await runtime.handle_input(RuntimeInput.text_input("Trigger tool"))

    # Does not crash! Turn completes normally
    turn = runtime.turns[0]
    assert turn.state == RuntimeTurnLifecycleState.COMPLETED

    assert len(llm.requests) == 2
    # Second request received tool failure result with TOOL_NOT_FOUND
    second_request = llm.requests[1]
    tool_msg = second_request.messages[-1]
    assert tool_msg.role == LLMRole.TOOL
    assert tool_msg.tool_call_id == "call_unexpected"
    assert "no tool registry is configured" in tool_msg.content

    assert len(tts.requests) == 1
    assert tts.requests[0].text == "I cannot run tools right now."
