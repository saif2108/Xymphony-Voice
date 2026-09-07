"""Session, Turn, and Message contracts. Barge-in does not end a Session."""

from __future__ import annotations

from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    field_validator,
    model_validator,
)

from xymphony_contracts.content import ContentPart
from xymphony_contracts.enums import (
    Channel,
    MessageRole,
    MessageStatus,
    SessionEndReason,
    SessionStatus,
    TurnStatus,
)
from xymphony_contracts.usage import Usage


class Session(BaseModel):
    """One conversation instance pinned to an AgentVersion snapshot."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    organization_id: UUID
    project_id: UUID
    agent_id: UUID
    agent_version_id: UUID
    deployment_id: UUID | None = None
    status: SessionStatus = SessionStatus.INITIALIZING
    channel: Channel = Channel.PLAYGROUND
    livekit_room: str | None = Field(default=None, max_length=256)
    config_hash: str = Field(min_length=64, max_length=64)
    started_at: AwareDatetime
    ended_at: AwareDatetime | None = None
    end_reason: SessionEndReason | None = None
    usage: Usage | None = None
    error_code: str | None = Field(default=None, max_length=128)

    @field_validator("config_hash")
    @classmethod
    def config_hash_is_sha256_hex(cls, value: str) -> str:
        if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            msg = "config_hash must be a lowercase SHA-256 hex digest"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def terminal_fields_match_status(self) -> Session:
        terminal = {
            SessionStatus.COMPLETED,
            SessionStatus.FAILED,
            SessionStatus.TERMINATED,
        }
        if self.status in terminal:
            if self.ended_at is None:
                msg = "terminal session requires ended_at"
                raise ValueError(msg)
        elif self.ended_at is not None:
            msg = "non-terminal session must not set ended_at"
            raise ValueError(msg)
        if self.status != SessionStatus.FAILED and self.error_code is not None:
            msg = "error_code is only valid when status is failed"
            raise ValueError(msg)
        if self.status == SessionStatus.FAILED and self.error_code is None:
            msg = "failed session requires error_code"
            raise ValueError(msg)
        return self


class Turn(BaseModel):
    """Bounded interaction cycle. Cancellation is turn-scoped; Session stays active."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    session_id: UUID
    organization_id: UUID
    sequence: int = Field(ge=1)
    status: TurnStatus = TurnStatus.IN_PROGRESS
    started_at: AwareDatetime
    ended_at: AwareDatetime | None = None
    interrupted: bool = False

    @model_validator(mode="after")
    def interrupt_matches_status(self) -> Turn:
        if self.interrupted and self.status != TurnStatus.CANCELLED:
            msg = "interrupted turns must have status cancelled"
            raise ValueError(msg)
        if self.status in {TurnStatus.COMMITTED, TurnStatus.CANCELLED, TurnStatus.FAILED}:
            if self.ended_at is None:
                msg = "finished turn requires ended_at"
                raise ValueError(msg)
        return self


class Message(BaseModel):
    """Durable transcript utterance. Distinct from Event (execution log)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    session_id: UUID
    turn_id: UUID
    organization_id: UUID
    role: MessageRole
    status: MessageStatus = MessageStatus.COMMITTED
    parts: tuple[ContentPart, ...]
    created_at: AwareDatetime
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def parts_not_empty(self) -> Message:
        if len(self.parts) < 1:
            msg = "message requires at least one content part"
            raise ValueError(msg)
        return self
