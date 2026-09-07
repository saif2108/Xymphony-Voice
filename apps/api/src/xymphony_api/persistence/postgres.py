"""PostgreSQL adapters implementing provider-neutral persistence ports."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from xymphony_api.mapping import message_to_contract, session_to_contract
from xymphony_api.models import ConversationMessageRow, SessionRow
from xymphony_api.repositories import ConversationRepository as SqlConversationRepository
from xymphony_api.repositories import SessionRepository as SqlSessionRepository
from xymphony_contracts.enums import SessionStatus
from xymphony_contracts.persistence import CreateSessionRequest
from xymphony_contracts.session import Message, Session


class PostgresSessionRepository:
    """Contract port adapter backed by SQLAlchemy session rows."""

    def __init__(self, sql: SqlSessionRepository) -> None:
        self._sql = sql

    def create_session(self, request: CreateSessionRequest) -> Session:
        now = datetime.now(tz=UTC)
        row = SessionRow(
            id=request.session_id or uuid4(),
            organization_id=request.organization_id,
            project_id=request.project_id,
            agent_id=request.agent_id,
            agent_version_id=request.agent_version_id,
            deployment_id=request.deployment_id,
            status=SessionStatus.INITIALIZING.value,
            channel=request.channel.value,
            livekit_room=request.livekit_room,
            config_hash=request.config_hash,
            started_at=now,
            updated_at=now,
        )
        self._sql.create(row)
        return session_to_contract(row)

    def get_session(
        self,
        session_id: UUID,
        *,
        organization_id: UUID | None = None,
        project_id: UUID | None = None,
    ) -> Session | None:
        row = self._sql.get(
            session_id,
            organization_id=organization_id,
            project_id=project_id,
        )
        if row is None:
            return None
        return session_to_contract(row)

    def update_session(self, session: Session) -> Session:
        row = self._sql.get(
            session.id,
            organization_id=session.organization_id,
            project_id=session.project_id,
        )
        if row is None:
            msg = f"session not found: {session.id}"
            raise LookupError(msg)
        row.status = session.status.value
        row.channel = session.channel.value
        row.livekit_room = session.livekit_room
        row.config_hash = session.config_hash
        row.ended_at = session.ended_at
        row.end_reason = session.end_reason.value if session.end_reason else None
        row.error_code = session.error_code
        row.updated_at = datetime.now(tz=UTC)
        if session.usage is not None:
            row.usage = session.usage.model_dump(mode="json")
        self._sql.update(row)
        return session_to_contract(row)


class PostgresConversationRepository:
    """Contract port adapter for ordered conversation messages."""

    def __init__(self, sql: SqlConversationRepository) -> None:
        self._sql = sql

    def append_message(self, message: Message) -> Message:
        sequence = self._sql.next_sequence(message.session_id)
        row = ConversationMessageRow(
            id=message.id,
            session_id=message.session_id,
            turn_id=message.turn_id,
            organization_id=message.organization_id,
            role=message.role.value,
            status=message.status.value,
            parts=[part.model_dump(mode="json") for part in message.parts],
            sequence=sequence,
            created_at=message.created_at,
        )
        self._sql.append(row)
        return message_to_contract(row)

    def list_messages(
        self,
        session_id: UUID,
        *,
        organization_id: UUID | None = None,
    ) -> tuple[Message, ...]:
        rows = self._sql.list_for_session(session_id, organization_id=organization_id)
        return tuple(message_to_contract(row) for row in rows)

    def next_sequence(self, session_id: UUID) -> int:
        return self._sql.next_sequence(session_id)
