from uuid import uuid4

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from xymphony_api.models import AgentRow, AgentVersionRow, OrganizationRow, ProjectRow


def test_expected_tables_exist(test_engine: Engine) -> None:
    names = set(inspect(test_engine).get_table_names())
    expected = {
        "organizations",
        "projects",
        "agents",
        "agent_versions",
        "sessions",
        "conversation_messages",
        "conversation_summaries",
    }
    assert expected.issubset(names)


def test_unique_agent_version_n(db_session: Session) -> None:
    org = OrganizationRow(id=uuid4(), name="O", slug=f"o-{uuid4().hex[:8]}")
    db_session.add(org)
    db_session.flush()
    project = ProjectRow(id=uuid4(), organization_id=org.id, name="P", slug=f"p-{uuid4().hex[:8]}")
    db_session.add(project)
    db_session.flush()
    agent = AgentRow(
        id=uuid4(),
        organization_id=org.id,
        project_id=project.id,
        name="A",
        description="",
        status="draft",
        tags=[],
    )
    db_session.add(agent)
    db_session.flush()
    payload = {"provider_key": "openai_compatible", "model": "m", "params": {}}
    tts = {"provider_key": "piper", "voice_ref": "v", "params": {}}
    row = AgentVersionRow(
        id=uuid4(),
        organization_id=org.id,
        project_id=project.id,
        agent_id=agent.id,
        version_n=1,
        status="draft",
        instructions="x",
        personality="",
        locale="en",
        llm=payload,
        stt=payload,
        tts=tts,
        config_hash="a" * 64,
    )
    db_session.add(row)
    db_session.flush()
    dup = AgentVersionRow(
        id=uuid4(),
        organization_id=org.id,
        project_id=project.id,
        agent_id=agent.id,
        version_n=1,
        status="draft",
        instructions="y",
        personality="",
        locale="en",
        llm=payload,
        stt=payload,
        tts=tts,
        config_hash="b" * 64,
    )
    db_session.add(dup)
    try:
        db_session.flush()
        raise AssertionError("expected unique constraint on (agent_id, version_n)")
    except IntegrityError:
        db_session.rollback()


def test_select_one_against_migrated_db(test_engine: Engine) -> None:
    with test_engine.connect() as conn:
        conn.execute(text("SELECT 1"))
