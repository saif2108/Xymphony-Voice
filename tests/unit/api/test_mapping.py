from datetime import UTC, datetime
from uuid import uuid4

from xymphony_api.mapping import (
    agent_to_contract,
    tool_definition_to_contract,
    version_to_contract,
)
from xymphony_api.models import AgentRow, AgentVersionRow, ToolDefinitionRow
from xymphony_contracts import ToolType


def test_agent_row_maps_to_contract() -> None:
    now = datetime.now(tz=UTC)
    row = AgentRow(
        id=uuid4(),
        organization_id=uuid4(),
        project_id=uuid4(),
        name="Support",
        description="desc",
        status="draft",
        tags=["a"],
        created_at=now,
        updated_at=now,
    )
    agent = agent_to_contract(row)
    assert agent.name == "Support"
    assert agent.tags == ("a",)
    assert agent.status.value == "draft"


def test_version_row_maps_to_contract() -> None:
    now = datetime.now(tz=UTC)
    row = AgentVersionRow(
        id=uuid4(),
        organization_id=uuid4(),
        project_id=uuid4(),
        agent_id=uuid4(),
        version_n=1,
        status="draft",
        instructions="Be helpful.",
        personality="",
        locale="en",
        llm={"provider_key": "openai_compatible", "model": "gpt-4o-mini", "params": {}},
        stt={"provider_key": "assemblyai", "model": "nova", "params": {}},
        tts={"provider_key": "piper", "voice_ref": "en", "params": {}},
        config_hash="a" * 64,
        created_at=now,
    )
    version = version_to_contract(row)
    assert version.version_n == 1
    assert version.llm.provider_key == "openai_compatible"
    assert version.config_hash == "a" * 64


def test_tool_definition_row_maps_to_contract() -> None:
    now = datetime.now(tz=UTC)
    tool_id = uuid4()
    org_id = uuid4()
    proj_id = uuid4()
    creator_id = uuid4()
    row = ToolDefinitionRow(
        id=tool_id,
        organization_id=org_id,
        project_id=proj_id,
        name="calculator",
        description="Math calculator",
        tool_type="function",
        parameters={"type": "object", "properties": {"expr": {"type": "string"}}},
        config={"precision": 4},
        enabled=True,
        created_by=creator_id,
        created_at=now,
        updated_at=now,
    )
    tool_def = tool_definition_to_contract(row)
    assert tool_def.id == tool_id
    assert tool_def.organization_id == org_id
    assert tool_def.project_id == proj_id
    assert tool_def.name == "calculator"
    assert tool_def.description == "Math calculator"
    assert tool_def.tool_type == ToolType.FUNCTION
    assert tool_def.parameters == {"type": "object", "properties": {"expr": {"type": "string"}}}
    assert tool_def.config == {"precision": 4}
    assert tool_def.enabled is True
    assert tool_def.created_by == creator_id
    assert tool_def.created_at == now
    assert tool_def.updated_at == now
