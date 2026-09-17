from datetime import UTC, datetime
from uuid import uuid4

from xymphony_api.mapping import agent_to_contract, version_to_contract
from xymphony_api.models import AgentRow, AgentVersionRow


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
    assert version.tools == ()


def test_version_row_maps_tools_to_contract() -> None:
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
        tools=[
            {"tool_name": "lookup", "enabled": True, "params": {}},
            {"tool_name": "calc", "enabled": False, "params": {"precision": 2}},
        ],
        config_hash="a" * 64,
        created_at=now,
    )
    version = version_to_contract(row)
    assert len(version.tools) == 2
    assert version.tools[0].tool_name == "lookup"
    assert version.tools[0].enabled is True
    assert version.tools[1].tool_name == "calc"
    assert version.tools[1].enabled is False
    assert version.tools[1].params == {"precision": 2}

