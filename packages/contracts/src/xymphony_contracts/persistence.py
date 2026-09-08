"""Provider-neutral persistence ports for sessions and conversation history."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from xymphony_contracts.enums import Channel
from xymphony_contracts.session import Message, Session
from xymphony_contracts.summary import ConversationSummary


class CreateSessionRequest(BaseModel):
    """Parameters for creating a durable session row."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    organization_id: UUID
    project_id: UUID
    agent_id: UUID
    agent_version_id: UUID
    config_hash: str = Field(min_length=64, max_length=64)
    channel: Channel = Channel.PLAYGROUND
    deployment_id: UUID | None = None
    livekit_room: str | None = Field(default=None, max_length=256)
    session_id: UUID | None = None


class SessionRepository(Protocol):
    """Port for durable session metadata (PostgreSQL adapter lives outside runtime)."""

    def create_session(self, request: CreateSessionRequest) -> Session: ...

    def get_session(
        self,
        session_id: UUID,
        *,
        organization_id: UUID | None = None,
        project_id: UUID | None = None,
    ) -> Session | None: ...

    def update_session(self, session: Session) -> Session: ...


class ConversationRepository(Protocol):
    """Port for ordered conversation messages (no raw PCM/audio)."""

    def append_message(self, message: Message) -> Message: ...

    def list_messages(
        self,
        session_id: UUID,
        *,
        organization_id: UUID | None = None,
    ) -> tuple[Message, ...]: ...

    def next_sequence(self, session_id: UUID) -> int: ...


class ConversationSummaryRepository(Protocol):
    """Port for one active rolling summary per session (derived state)."""

    def get_latest(
        self,
        session_id: UUID,
        *,
        organization_id: UUID | None = None,
    ) -> ConversationSummary | None: ...

    def upsert(self, summary: ConversationSummary) -> ConversationSummary: ...
