"""Conversation message helpers for runtime LLM history."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from xymphony_contracts.content import ContentPart
from xymphony_contracts.enums import ContentPartType, MessageRole, MessageStatus
from xymphony_contracts.llm import LLMMessage, LLMRole
from xymphony_contracts.session import Message


def text_content_part(text: str) -> ContentPart:
    return ContentPart(type=ContentPartType.TEXT, payload={"text": text})


def build_text_message(
    *,
    session_id: UUID,
    turn_id: UUID,
    organization_id: UUID,
    role: MessageRole,
    text: str,
    created_at: datetime | None = None,
) -> Message:
    return Message(
        id=uuid4(),
        session_id=session_id,
        turn_id=turn_id,
        organization_id=organization_id,
        role=role,
        status=MessageStatus.COMMITTED,
        parts=(text_content_part(text),),
        created_at=created_at or datetime.now(tz=UTC),
    )


def message_text(message: Message) -> str | None:
    parts: list[str] = []
    for part in message.parts:
        if part.type != ContentPartType.TEXT:
            continue
        text = part.payload.get("text")
        if isinstance(text, str) and text:
            parts.append(text)
    if not parts:
        return None
    return "".join(parts)


def message_to_llm(message: Message) -> LLMMessage | None:
    text = message_text(message)
    if text is None:
        return None
    role_map = {
        MessageRole.USER: LLMRole.USER,
        MessageRole.ASSISTANT: LLMRole.ASSISTANT,
        MessageRole.SYSTEM: LLMRole.SYSTEM,
    }
    llm_role = role_map.get(message.role)
    if llm_role is None:
        return None
    return LLMMessage(role=llm_role, content=text)


def committed_messages_to_llm(messages: tuple[Message, ...]) -> tuple[LLMMessage, ...]:
    llm_messages: list[LLMMessage] = []
    for message in messages:
        if message.status != MessageStatus.COMMITTED:
            continue
        converted = message_to_llm(message)
        if converted is not None:
            llm_messages.append(converted)
    return tuple(llm_messages)
