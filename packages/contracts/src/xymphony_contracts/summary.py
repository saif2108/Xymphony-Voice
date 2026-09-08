"""Conversation summary contracts (derived short-term context, not the ledger)."""

from __future__ import annotations

from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class ConversationSummary(BaseModel):
    """Session-scoped rolling summary of older conversation history.

    Derived state only. The conversation_messages ledger remains authoritative.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    session_id: UUID
    organization_id: UUID
    agent_version_id: UUID
    through_sequence: int = Field(ge=0)
    summary_text: str = Field(min_length=1, max_length=32_000)
    source_message_count: int = Field(default=0, ge=0)
    created_at: AwareDatetime
