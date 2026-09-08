"""Phase 3 Step 1 — LLMContextAssembler unit tests."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from tests.helpers import ORG, SESSION_ID

from xymphony_contracts.content import ContentPart
from xymphony_contracts.enums import ContentPartType, MessageRole, MessageStatus
from xymphony_contracts.llm import LLMRole
from xymphony_contracts.session import Message
from xymphony_runtime import LLMContextAssembler, LLMRuntimeConfig


def _message(
    *,
    role: MessageRole,
    text: str,
    status: MessageStatus = MessageStatus.COMMITTED,
) -> Message:
    return Message(
        id=uuid4(),
        session_id=SESSION_ID,
        turn_id=uuid4(),
        organization_id=ORG,
        role=role,
        status=status,
        parts=(ContentPart(type=ContentPartType.TEXT, payload={"text": text}),),
        created_at=datetime(2026, 9, 8, 12, 0, 0, tzinfo=UTC),
    )


def _config(**overrides: object) -> LLMRuntimeConfig:
    data: dict[str, object] = {
        "provider_key": "openai",
        "model": "gpt-4o-mini",
        "system_instructions": "You are helpful.",
        "params": {"temperature": 0.2},
    }
    data.update(overrides)
    return LLMRuntimeConfig(**data)  # type: ignore[arg-type]


def test_empty_history_plus_current_user_message() -> None:
    request = LLMContextAssembler().assemble(
        history=(),
        current_user_text="hello",
        config=_config(),
    )
    assert len(request.messages) == 1
    assert request.messages[0].role == LLMRole.USER
    assert request.messages[0].content == "hello"


def test_prior_user_assistant_messages_preserve_order() -> None:
    history = (
        _message(role=MessageRole.USER, text="First"),
        _message(role=MessageRole.ASSISTANT, text="Reply one"),
        _message(role=MessageRole.USER, text="Second"),
        _message(role=MessageRole.ASSISTANT, text="Reply two"),
    )
    request = LLMContextAssembler().assemble(
        history=history,
        current_user_text="Third",
        config=_config(),
    )
    assert [message.content for message in request.messages] == [
        "First",
        "Reply one",
        "Second",
        "Reply two",
        "Third",
    ]
    assert [message.role for message in request.messages] == [
        LLMRole.USER,
        LLMRole.ASSISTANT,
        LLMRole.USER,
        LLMRole.ASSISTANT,
        LLMRole.USER,
    ]


def test_system_history_message_is_preserved() -> None:
    history = (
        _message(role=MessageRole.SYSTEM, text="Prior system note"),
        _message(role=MessageRole.USER, text="Hi"),
        _message(role=MessageRole.ASSISTANT, text="Hello"),
    )
    request = LLMContextAssembler().assemble(
        history=history,
        current_user_text="Again",
        config=_config(),
    )
    assert request.messages[0].role == LLMRole.SYSTEM
    assert request.messages[0].content == "Prior system note"
    assert request.messages[-1].content == "Again"


def test_current_user_message_appended_after_history() -> None:
    history = (_message(role=MessageRole.USER, text="Earlier"),)
    request = LLMContextAssembler().assemble(
        history=history,
        current_user_text="Now",
        config=_config(),
    )
    assert request.messages[-1].role == LLMRole.USER
    assert request.messages[-1].content == "Now"
    assert request.messages[0].content == "Earlier"


def test_system_instructions_map_to_llm_request_system() -> None:
    request = LLMContextAssembler().assemble(
        history=(),
        current_user_text="hi",
        config=_config(system_instructions="Speak briefly."),
    )
    assert request.system == "Speak briefly."


def test_provider_key_model_params_preserved() -> None:
    config = _config(
        provider_key="openai",
        model="gpt-4o",
        params={"temperature": 0.7, "top_p": 0.9},
    )
    request = LLMContextAssembler().assemble(
        history=(),
        current_user_text="hi",
        config=config,
    )
    assert request.provider_key == "openai"
    assert request.model == "gpt-4o"
    assert request.params == {"temperature": 0.7, "top_p": 0.9}


def test_input_history_is_not_mutated() -> None:
    history = [
        _message(role=MessageRole.USER, text="One"),
        _message(role=MessageRole.ASSISTANT, text="Two"),
    ]
    snapshot = list(history)
    LLMContextAssembler().assemble(
        history=history,
        current_user_text="Three",
        config=_config(),
    )
    assert history == snapshot
    assert len(history) == 2


def test_empty_and_whitespace_current_user_text_pass_through() -> None:
    """Assembler mirrors prior inline behavior: content is used as supplied."""
    empty = LLMContextAssembler().assemble(
        history=(),
        current_user_text="",
        config=_config(),
    )
    assert empty.messages[0].content == ""

    whitespace = LLMContextAssembler().assemble(
        history=(),
        current_user_text="   ",
        config=_config(),
    )
    assert whitespace.messages[0].content == "   "


def test_no_duplicate_current_user_message() -> None:
    history = (_message(role=MessageRole.USER, text="Already said"),)
    request = LLMContextAssembler().assemble(
        history=history,
        current_user_text="New utterance",
        config=_config(),
    )
    assert [message.content for message in request.messages] == [
        "Already said",
        "New utterance",
    ]
    assert sum(1 for message in request.messages if message.content == "New utterance") == 1


def test_non_committed_messages_are_skipped() -> None:
    history = (
        _message(role=MessageRole.USER, text="Keep"),
        _message(
            role=MessageRole.ASSISTANT,
            text="Skip me",
            status=MessageStatus.INTERRUPTED,
        ),
        _message(role=MessageRole.ASSISTANT, text="Keep too"),
    )
    request = LLMContextAssembler().assemble(
        history=history,
        current_user_text="Next",
        config=_config(),
    )
    assert [message.content for message in request.messages] == ["Keep", "Keep too", "Next"]
