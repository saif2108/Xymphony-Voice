"""Phase 3 Step 2 — context budget / history selection tests."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from tests.helpers import ORG, SESSION_ID
from tests.unit.runtime.pipeline_helpers import make_pipeline_runtime

from xymphony_contracts.content import ContentPart
from xymphony_contracts.enums import ContentPartType, EventType, MessageRole, MessageStatus
from xymphony_contracts.llm import LLMMessage, LLMRole
from xymphony_contracts.session import Message
from xymphony_runtime import (
    ContextBudgetExceededError,
    ContextBudgetPolicy,
    LLMContextAssembler,
    LLMRuntimeConfig,
    RuntimeInput,
    approximate_token_count,
)
from xymphony_runtime.turn import RuntimeTurnLifecycleState


def _message(*, role: MessageRole, text: str) -> Message:
    return Message(
        id=uuid4(),
        session_id=SESSION_ID,
        turn_id=uuid4(),
        organization_id=ORG,
        role=role,
        status=MessageStatus.COMMITTED,
        parts=(ContentPart(type=ContentPartType.TEXT, payload={"text": text}),),
        created_at=datetime(2026, 9, 8, 12, 0, 0, tzinfo=UTC),
    )


def _llm(role: LLMRole, text: str) -> LLMMessage:
    return LLMMessage(role=role, content=text)


def _config(**overrides: object) -> LLMRuntimeConfig:
    data: dict[str, object] = {
        "provider_key": "openai",
        "model": "gpt-4o-mini",
        "system_instructions": "sys",
        "params": {},
    }
    data.update(overrides)
    return LLMRuntimeConfig(**data)  # type: ignore[arg-type]


def test_approximate_token_count_is_deterministic() -> None:
    assert approximate_token_count("") == 0
    assert approximate_token_count("abcd") == 1
    assert approximate_token_count("abcdefgh") == 2
    assert approximate_token_count("a") == 1
    assert approximate_token_count("hello world") == approximate_token_count("hello world")


def test_history_comfortably_fits() -> None:
    history = (
        _llm(LLMRole.USER, "aaaa"),
        _llm(LLMRole.ASSISTANT, "bbbb"),
    )
    selected = ContextBudgetPolicy().select_history(
        history,
        current_user_text="curr",
        system_instructions="sys",
        max_input_tokens=10,
    )
    assert selected == history


def test_history_exactly_reaches_budget() -> None:
    history = (
        _llm(LLMRole.USER, "aaaa"),
        _llm(LLMRole.ASSISTANT, "bbbb"),
    )
    # system 1 + current 1 + hist 1+1 = 4
    selected = ContextBudgetPolicy().select_history(
        history,
        current_user_text="curr",
        system_instructions="sys",
        max_input_tokens=4,
    )
    assert selected == history


def test_oldest_messages_removed_first_newest_retained() -> None:
    history = (
        _llm(LLMRole.USER, "U1xx"),
        _llm(LLMRole.ASSISTANT, "A1xx"),
        _llm(LLMRole.USER, "U2xx"),
        _llm(LLMRole.ASSISTANT, "A2xx"),
        _llm(LLMRole.USER, "U3xx"),
        _llm(LLMRole.ASSISTANT, "A3xx"),
    )
    # each hist msg = 1 token; reserve system+user = 2; remaining 4 → keep last 4
    selected = ContextBudgetPolicy().select_history(
        history,
        current_user_text="curr",
        system_instructions="sys",
        max_input_tokens=6,
    )
    assert [message.content for message in selected] == ["U2xx", "A2xx", "U3xx", "A3xx"]


def test_selected_history_is_suffix_preserving_order() -> None:
    history = (
        _llm(LLMRole.USER, "one!"),
        _llm(LLMRole.ASSISTANT, "two!"),
        _llm(LLMRole.USER, "thr!"),
    )
    selected = ContextBudgetPolicy().select_history(
        history,
        current_user_text="now!",
        system_instructions="s",
        max_input_tokens=4,
    )
    assert list(selected) == list(history[-len(selected) :])


def test_empty_and_one_message_history() -> None:
    empty = ContextBudgetPolicy().select_history(
        (),
        current_user_text="hi",
        system_instructions="",
        max_input_tokens=5,
    )
    assert empty == ()

    one = (_llm(LLMRole.USER, "only"),)
    selected = ContextBudgetPolicy().select_history(
        one,
        current_user_text="now",
        system_instructions="",
        max_input_tokens=5,
    )
    assert selected == one


def test_current_user_and_system_always_reserved() -> None:
    history = (_llm(LLMRole.USER, "old!"), _llm(LLMRole.ASSISTANT, "ans!"))
    selected = ContextBudgetPolicy().select_history(
        history,
        current_user_text="brand new",
        system_instructions="be brief please",
        max_input_tokens=approximate_token_count("be brief please")
        + approximate_token_count("brand new"),
    )
    assert selected == ()


def test_oversized_current_user_raises() -> None:
    with pytest.raises(ContextBudgetExceededError, match="current user message"):
        ContextBudgetPolicy().select_history(
            (),
            current_user_text="x" * 100,
            system_instructions="",
            max_input_tokens=5,
        )


def test_oversized_system_instructions_raises() -> None:
    with pytest.raises(ContextBudgetExceededError, match="system instructions"):
        ContextBudgetPolicy().select_history(
            (),
            current_user_text="hi",
            system_instructions="s" * 100,
            max_input_tokens=5,
        )


def test_system_consumes_most_budget_drops_history() -> None:
    system = "s" * 40  # 10 tokens
    history = (_llm(LLMRole.USER, "hist"),)
    selected = ContextBudgetPolicy().select_history(
        history,
        current_user_text="u",
        system_instructions=system,
        max_input_tokens=11,
    )
    assert selected == ()


def test_assembler_budget_disabled_preserves_full_history() -> None:
    history = (
        _message(role=MessageRole.USER, text="First"),
        _message(role=MessageRole.ASSISTANT, text="Reply"),
    )
    request = LLMContextAssembler().assemble(
        history=history,
        current_user_text="Now",
        config=_config(max_input_tokens=None),
    )
    assert [message.content for message in request.messages] == ["First", "Reply", "Now"]
    assert request.system == "sys"


def test_assembler_applies_budget_and_appends_current_once() -> None:
    history = [
        _message(role=MessageRole.USER, text="U1xx"),
        _message(role=MessageRole.ASSISTANT, text="A1xx"),
        _message(role=MessageRole.USER, text="U2xx"),
        _message(role=MessageRole.ASSISTANT, text="A2xx"),
    ]
    snapshot = list(history)
    request = LLMContextAssembler().assemble(
        history=history,
        current_user_text="curr",
        config=_config(system_instructions="sys", max_input_tokens=4),
    )
    assert history == snapshot
    assert [message.content for message in request.messages] == ["U2xx", "A2xx", "curr"]
    assert sum(1 for message in request.messages if message.content == "curr") == 1
    assert request.system == "sys"
    assert request.messages[-1].role == LLMRole.USER


def test_assembler_budget_is_deterministic() -> None:
    history = (
        _message(role=MessageRole.USER, text="U1xx"),
        _message(role=MessageRole.ASSISTANT, text="A1xx"),
        _message(role=MessageRole.USER, text="U2xx"),
        _message(role=MessageRole.ASSISTANT, text="A2xx"),
    )
    config = _config(system_instructions="sys", max_input_tokens=4)
    assembler = LLMContextAssembler()
    first = assembler.assemble(history=history, current_user_text="curr", config=config)
    second = assembler.assemble(history=history, current_user_text="curr", config=config)
    assert first.messages == second.messages


@pytest.mark.asyncio
async def test_runtime_oversized_user_fails_turn_without_llm() -> None:
    runtime = make_pipeline_runtime()
    runtime._llm_config = LLMRuntimeConfig(  # noqa: SLF001
        provider_key="fake",
        model="fake-model",
        system_instructions="",
        max_input_tokens=2,
    )
    await runtime.start()
    await runtime.handle_input(RuntimeInput.text_input("x" * 100))
    turn = runtime.turns[0]
    assert turn.state == RuntimeTurnLifecycleState.FAILED
    assert any(event.type == EventType.ERROR for event in runtime.admitted_events)
    assert not any(event.type == EventType.LLM_RESPONSE for event in runtime.admitted_events)
    await runtime.stop()


@pytest.mark.asyncio
async def test_runtime_without_budget_unchanged() -> None:
    runtime = make_pipeline_runtime()
    await runtime.start()
    await runtime.handle_input(RuntimeInput.text_input("hello"))
    assert runtime.turns[0].state == RuntimeTurnLifecycleState.COMPLETED
    assert any(event.type == EventType.LLM_RESPONSE for event in runtime.admitted_events)
    await runtime.stop()
