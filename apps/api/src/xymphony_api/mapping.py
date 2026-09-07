from __future__ import annotations

from xymphony_api.models import AgentRow, AgentVersionRow
from xymphony_contracts import (
    Agent,
    AgentStatus,
    AgentVersion,
    AgentVersionStatus,
    LLMBinding,
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
