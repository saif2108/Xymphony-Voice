"""Step 9 persistence contract validation."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from tests.helpers import make_session, utcnow
from xymphony_contracts import CreateSessionRequest, MessageRole, MessageStatus, SessionStatus
from xymphony_contracts.content import ContentPart
from xymphony_contracts.enums import ContentPartType
from xymphony_contracts.session import Message


def test_create_session_request_requires_config_hash() -> None:
    session = make_session()
    request = CreateSessionRequest(
        organization_id=session.organization_id,
        project_id=session.project_id,
        agent_id=session.agent_id,
        agent_version_id=session.agent_version_id,
        config_hash=session.config_hash,
    )
    assert request.agent_version_id == session.agent_version_id


def test_create_session_request_rejects_bad_config_hash() -> None:
    session = make_session()
    with pytest.raises(ValidationError):
        CreateSessionRequest(
            organization_id=session.organization_id,
            project_id=session.project_id,
            agent_id=session.agent_id,
            agent_version_id=session.agent_version_id,
            config_hash="not-a-hash",
        )


def test_session_contract_terminal_validation() -> None:
    with pytest.raises(ValidationError):
        make_session(status=SessionStatus.TERMINATED)


def test_message_requires_non_empty_parts() -> None:
    session = make_session()
    with pytest.raises(ValidationError):
        Message(
            id=uuid4(),
            session_id=session.id,
            turn_id=uuid4(),
            organization_id=session.organization_id,
            role=MessageRole.USER,
            status=MessageStatus.COMMITTED,
            parts=(),
            created_at=utcnow(),
        )


def test_message_text_part_round_trip() -> None:
    session = make_session()
    message = Message(
        id=uuid4(),
        session_id=session.id,
        turn_id=uuid4(),
        organization_id=session.organization_id,
        role=MessageRole.ASSISTANT,
        status=MessageStatus.COMMITTED,
        parts=(ContentPart(type=ContentPartType.TEXT, payload={"text": "Hello"}),),
        created_at=utcnow(),
    )
    assert message.parts[0].payload["text"] == "Hello"
