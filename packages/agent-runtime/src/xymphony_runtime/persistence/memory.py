"""In-memory persistence adapters for unit tests."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from xymphony_contracts.enums import SessionStatus
from xymphony_contracts.persistence import CreateSessionRequest
from xymphony_contracts.session import Message, Session
from xymphony_contracts.summary import ConversationSummary


class InMemorySessionRepository:
    def __init__(self) -> None:
        self.sessions: dict[UUID, Session] = {}

    def create_session(self, request: CreateSessionRequest) -> Session:
        now = datetime.now(tz=UTC)
        session = Session(
            id=request.session_id or uuid4(),
            organization_id=request.organization_id,
            project_id=request.project_id,
            agent_id=request.agent_id,
            agent_version_id=request.agent_version_id,
            deployment_id=request.deployment_id,
            status=SessionStatus.INITIALIZING,
            channel=request.channel,
            livekit_room=request.livekit_room,
            config_hash=request.config_hash,
            started_at=now,
        )
        self.sessions[session.id] = session
        return session

    def get_session(
        self,
        session_id: UUID,
        *,
        organization_id: UUID | None = None,
        project_id: UUID | None = None,
    ) -> Session | None:
        session = self.sessions.get(session_id)
        if session is None:
            return None
        if organization_id is not None and session.organization_id != organization_id:
            return None
        if project_id is not None and session.project_id != project_id:
            return None
        return session

    def update_session(self, session: Session) -> Session:
        self.sessions[session.id] = session
        return session


class InMemoryConversationRepository:
    def __init__(self) -> None:
        self.messages_by_session: dict[UUID, list[Message]] = {}

    def append_message(self, message: Message) -> Message:
        bucket = self.messages_by_session.setdefault(message.session_id, [])
        sequence = len(bucket) + 1
        stored = message.model_copy(
            update={"metadata": {**dict(message.metadata), "sequence": sequence}}
        )
        bucket.append(stored)
        return stored

    def list_messages(
        self,
        session_id: UUID,
        *,
        organization_id: UUID | None = None,
    ) -> tuple[Message, ...]:
        messages = list(self.messages_by_session.get(session_id, ()))
        if organization_id is not None:
            messages = [m for m in messages if m.organization_id == organization_id]
        return tuple(messages)

    def next_sequence(self, session_id: UUID) -> int:
        return len(self.messages_by_session.get(session_id, ())) + 1


class InMemoryConversationSummaryRepository:
    """One active rolling summary per session."""

    def __init__(self) -> None:
        self.summaries: dict[UUID, ConversationSummary] = {}

    def get_latest(
        self,
        session_id: UUID,
        *,
        organization_id: UUID | None = None,
    ) -> ConversationSummary | None:
        summary = self.summaries.get(session_id)
        if summary is None:
            return None
        if organization_id is not None and summary.organization_id != organization_id:
            return None
        return summary

    def upsert(self, summary: ConversationSummary) -> ConversationSummary:
        self.summaries[summary.session_id] = summary
        return summary
