from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from tests.helpers import SESSION_ID, make_agent_version, make_session, utcnow
from xymphony_contracts import (
    ContentPart,
    ContentPartType,
    Message,
    MessageRole,
    MessageStatus,
    SessionStatus,
    Turn,
    TurnStatus,
)


def test_active_session_does_not_end_on_construction() -> None:
    session = make_session(status=SessionStatus.ACTIVE)
    assert session.ended_at is None
    assert session.deployment_id is None
    assert session.status == SessionStatus.ACTIVE


def test_session_cannot_use_interrupted_status() -> None:
    with pytest.raises(ValidationError):
        make_session(status="interrupted")


def test_failed_session_requires_error_code() -> None:
    with pytest.raises(ValidationError):
        make_session(status=SessionStatus.FAILED, ended_at=utcnow())


def test_failed_session_ok() -> None:
    session = make_session(
        status=SessionStatus.FAILED,
        ended_at=utcnow(),
        error_code="stt_failed",
        end_reason="provider_failed",
    )
    assert session.status == SessionStatus.FAILED


def test_turn_interrupt_does_not_imply_session_ended() -> None:
    session = make_session(status=SessionStatus.ACTIVE)
    turn = Turn(
        id=uuid4(),
        session_id=session.id,
        organization_id=session.organization_id,
        sequence=1,
        status=TurnStatus.CANCELLED,
        started_at=utcnow(),
        ended_at=utcnow(),
        interrupted=True,
    )
    assert session.status == SessionStatus.ACTIVE
    assert turn.status == TurnStatus.CANCELLED
    assert turn.interrupted is True


def test_interrupted_flag_requires_cancelled_status() -> None:
    with pytest.raises(ValidationError):
        Turn(
            id=uuid4(),
            session_id=SESSION_ID,
            organization_id=uuid4(),
            sequence=1,
            status=TurnStatus.COMMITTED,
            started_at=utcnow(),
            ended_at=utcnow(),
            interrupted=True,
        )


def test_message_interrupted_is_not_session_status() -> None:
    message = Message(
        id=uuid4(),
        session_id=SESSION_ID,
        turn_id=uuid4(),
        organization_id=make_agent_version().organization_id,
        role=MessageRole.ASSISTANT,
        status=MessageStatus.INTERRUPTED,
        parts=(
            ContentPart(
                type=ContentPartType.TEXT,
                payload={"text": "Hello"},
            ),
        ),
        created_at=datetime.now(tz=UTC),
    )
    session = make_session(status=SessionStatus.ACTIVE)
    assert message.status == MessageStatus.INTERRUPTED
    assert session.status == SessionStatus.ACTIVE


def test_naive_datetime_rejected_on_session() -> None:
    with pytest.raises(ValidationError):
        make_session(started_at=datetime(2026, 9, 7, 12, 0, 0))
