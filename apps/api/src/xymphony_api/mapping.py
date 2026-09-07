from __future__ import annotations

from xymphony_api.models import AgentRow, AgentVersionRow, ConversationMessageRow, SessionRow
from xymphony_contracts import (
    Agent,
    AgentStatus,
    AgentVersion,
    AgentVersionStatus,
    Channel,
    ContentPart,
    LLMBinding,
    Message,
    MessageRole,
    MessageStatus,
    Session,
    SessionEndReason,
    SessionStatus,
    STTBinding,
    TTSBinding,
)


def agent_to_contract(row: AgentRow) -> Agent:
    tags = tuple(row.tags or ())
    return Agent(
        id=row.id,
        organization_id=row.organization_id,
        project_id=row.project_id,
        name=row.name,
        description=row.description,
        status=AgentStatus(row.status),
        tags=tags,
        created_by=row.created_by,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def version_to_contract(row: AgentVersionRow) -> AgentVersion:
    return AgentVersion(
        id=row.id,
        organization_id=row.organization_id,
        project_id=row.project_id,
        agent_id=row.agent_id,
        version_n=row.version_n,
        status=AgentVersionStatus(row.status),
        instructions=row.instructions,
        personality=row.personality,
        locale=row.locale,
        llm=LLMBinding.model_validate(row.llm),
        stt=STTBinding.model_validate(row.stt),
        tts=TTSBinding.model_validate(row.tts),
        config_hash=row.config_hash,
        created_by=row.created_by,
        created_at=row.created_at,
        published_at=row.published_at,
    )


def session_to_contract(row: SessionRow) -> Session:
    usage = None
    if row.usage is not None:
        from xymphony_contracts import Usage

        usage = Usage.model_validate(row.usage)
    return Session(
        id=row.id,
        organization_id=row.organization_id,
        project_id=row.project_id,
        agent_id=row.agent_id,
        agent_version_id=row.agent_version_id,
        deployment_id=row.deployment_id,
        status=SessionStatus(row.status),
        channel=Channel(row.channel),
        livekit_room=row.livekit_room,
        config_hash=row.config_hash,
        started_at=row.started_at,
        ended_at=row.ended_at,
        end_reason=SessionEndReason(row.end_reason) if row.end_reason else None,
        usage=usage,
        error_code=row.error_code,
    )


def message_to_contract(row: ConversationMessageRow) -> Message:
    parts = tuple(ContentPart.model_validate(part) for part in row.parts)
    return Message(
        id=row.id,
        session_id=row.session_id,
        turn_id=row.turn_id,
        organization_id=row.organization_id,
        role=MessageRole(row.role),
        status=MessageStatus(row.status),
        parts=parts,
        created_at=row.created_at,
        metadata={"sequence": row.sequence},
    )
