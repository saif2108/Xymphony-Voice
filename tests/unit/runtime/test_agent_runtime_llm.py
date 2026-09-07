"""Phase 2 Step 2 AgentRuntime + LLM provider integration tests."""

from __future__ import annotations

import asyncio

import pytest
from tests.helpers import make_session

from xymphony_contracts.enums import EventType, TurnStatus
from xymphony_contracts.llm import LLMMessage, LLMRequest, LLMRole, ProviderError, ProviderErrorCode
from xymphony_providers.fake_llm import FakeLLMProvider
from xymphony_runtime import AgentRuntime, LLMRuntimeConfig, RuntimeContext, RuntimeInput
from xymphony_runtime.cancellation import EventCancellationToken
from xymphony_runtime.dispatch import llm_token_event
from xymphony_runtime.turn import RuntimeTurnLifecycleState


def runtime_context() -> RuntimeContext:
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


def llm_config() -> LLMRuntimeConfig:
    return LLMRuntimeConfig(
        provider_key="fake",
        model="fake-model",
        system_instructions="be helpful",
    )


@pytest.mark.asyncio
async def test_fake_provider_streams_llm_token_events() -> None:
    provider = FakeLLMProvider(chunks=["hello", " world"])
    runtime = AgentRuntime(
        runtime_context(),
        llm_provider=provider,
        llm_config=llm_config(),
    )
    await runtime.start()
    await runtime.handle_input(RuntimeInput.text_input("hi"))

    turn = runtime.turns[0]
    token_events = [
        event for event in runtime.admitted_events if event.type == EventType.LLM_TOKEN
    ]
    assert [event.payload.delta for event in token_events] == ["hello", " world"]
    assert all(event.turn_id == turn.id for event in token_events)
    assert all(event.session_id == runtime.context.session_id for event in token_events)
    assert turn.state == RuntimeTurnLifecycleState.COMPLETED
    assert any(event.type == EventType.LLM_RESPONSE for event in runtime.admitted_events)


@pytest.mark.asyncio
async def test_provider_is_injected_not_constructed_by_runtime() -> None:
    provider = FakeLLMProvider(chunks=["ok"])
    runtime = AgentRuntime(
        runtime_context(),
        llm_provider=provider,
        llm_config=llm_config(),
    )
    await runtime.start()
    await runtime.handle_input(RuntimeInput.text_input("ping"))
    assert len(provider.requests) == 1
    assert provider.requests[0].messages[0].content == "ping"


@pytest.mark.asyncio
async def test_provider_failure_emits_error_and_fails_turn() -> None:
    provider = FakeLLMProvider(
        fail_with=ProviderError(
            code=ProviderErrorCode.PROVIDER,
            message="provider unavailable",
            provider_key="fake",
        )
    )
    runtime = AgentRuntime(
        runtime_context(),
        llm_provider=provider,
        llm_config=llm_config(),
    )
    await runtime.start()
    await runtime.handle_input(RuntimeInput.text_input("fail"))

    turn = runtime.turns[0]
    assert turn.state == RuntimeTurnLifecycleState.FAILED
    assert turn.to_contract().status == TurnStatus.FAILED
    error_events = [event for event in runtime.admitted_events if event.type == EventType.ERROR]
    assert len(error_events) == 1
    assert error_events[0].payload.code == ProviderErrorCode.PROVIDER.value
    assert "sk-" not in error_events[0].payload.message


@pytest.mark.asyncio
async def test_cancellation_stops_remaining_llm_chunks() -> None:
    provider = FakeLLMProvider(chunks=["a", "b", "c"], delay_seconds=0.05)
    runtime = AgentRuntime(
        runtime_context(),
        llm_provider=provider,
        llm_config=llm_config(),
    )
    await runtime.start()

    async def _run_turn() -> None:
        await runtime.handle_input(RuntimeInput.text_input("stream"))

    task = asyncio.create_task(_run_turn())
    await asyncio.sleep(0.06)
    await runtime.handle_input(RuntimeInput.cancel_turn())
    await task

    turn = runtime.turns[0]
    assert turn.state == RuntimeTurnLifecycleState.CANCELLED
    token_events = [
        event for event in runtime.admitted_events if event.type == EventType.LLM_TOKEN
    ]
    assert len(token_events) < 3


@pytest.mark.asyncio
async def test_stale_chunks_cannot_affect_new_turn() -> None:
    runtime = AgentRuntime(
        runtime_context(),
        llm_provider=FakeLLMProvider(chunks=["x"]),
        llm_config=llm_config(),
    )
    await runtime.start()
    await runtime.handle_input(RuntimeInput.user_speech_started())
    cancelled_turn_id = runtime.current_turn_id
    assert cancelled_turn_id is not None
    await runtime.handle_input(RuntimeInput.cancel_turn())

    stale = llm_token_event(runtime.context, turn_id=cancelled_turn_id, delta="stale")
    assert runtime.admit_event(stale) is False

    await runtime.handle_input(RuntimeInput.text_input("fresh"))
    second_turn = runtime.turns[1]
    token_events = [
        event
        for event in runtime.admitted_events
        if event.type == EventType.LLM_TOKEN and event.turn_id == second_turn.id
    ]
    assert len(token_events) == 1
    assert token_events[0].payload.delta == "x"


@pytest.mark.asyncio
async def test_multiple_sequential_llm_turns() -> None:
    runtime = AgentRuntime(
        runtime_context(),
        llm_provider=FakeLLMProvider(chunks=["ok"]),
        llm_config=llm_config(),
    )
    await runtime.start()
    for idx in range(3):
        await runtime.handle_input(RuntimeInput.text_input(f"msg-{idx}"))
    assert len(runtime.turns) == 3
    assert all(turn.state == RuntimeTurnLifecycleState.COMPLETED for turn in runtime.turns)


@pytest.mark.asyncio
async def test_cancellation_token_stops_fake_provider_directly() -> None:
    provider = FakeLLMProvider(chunks=["a", "b"], delay_seconds=0.05)
    request = LLMRequest(
        provider_key="fake",
        model="fake-model",
        messages=(LLMMessage(role=LLMRole.USER, content="hi"),),
    )
    cancel = EventCancellationToken()

    async def _consume() -> list[str]:
        deltas: list[str] = []
        async for chunk in provider.stream(request, cancel=cancel):
            deltas.append(chunk.delta)
        return deltas

    task = asyncio.create_task(_consume())
    await asyncio.sleep(0.06)
    cancel.cancel()
    deltas = await task
    assert len(deltas) < 2
