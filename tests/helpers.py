from datetime import UTC, datetime
from uuid import UUID, uuid4

from xymphony_contracts import (
    Agent,
    AgentStatus,
    AgentVersion,
    Channel,
    LLMBinding,
    Session,
    SessionStatus,
    STTBinding,
    TTSBinding,
)

ORG = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
PROJECT = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
AGENT_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
VERSION_ID = UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
SESSION_ID = UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")


def utcnow() -> datetime:
    return datetime(2026, 9, 7, 12, 0, 0, tzinfo=UTC)


def llm_binding(**overrides: object) -> LLMBinding:
    data: dict[str, object] = {
        "provider_key": "openai_compatible",
        "model": "gpt-4o-mini",
        "params": {},
    }
    data.update(overrides)
    return LLMBinding.model_validate(data)


def stt_binding(**overrides: object) -> STTBinding:
    data: dict[str, object] = {
        "provider_key": "assemblyai",
        "model": "universal-streaming",
        "params": {},
    }
    data.update(overrides)
    return STTBinding.model_validate(data)


def tts_binding(**overrides: object) -> TTSBinding:
    data: dict[str, object] = {
        "provider_key": "elevenlabs",
        "voice_ref": "voice_default",
        "params": {},
    }
    data.update(overrides)
    return TTSBinding.model_validate(data)


def make_agent_version(**overrides: object) -> AgentVersion:
    data: dict[str, object] = {
        "id": VERSION_ID,
        "organization_id": ORG,
        "project_id": PROJECT,
        "agent_id": AGENT_ID,
        "version_n": 1,
        "instructions": "You are a helpful voice agent.",
        "personality": "calm",
        "locale": "en",
        "llm": llm_binding(),
        "stt": stt_binding(),
        "tts": tts_binding(),
        "created_at": utcnow(),
    }
    data.update(overrides)
    version = AgentVersion.model_validate(data)
    if version.config_hash is None:
        version = version.with_config_hash()
    return version


def make_agent(**overrides: object) -> Agent:
    data: dict[str, object] = {
        "id": AGENT_ID,
        "organization_id": ORG,
        "project_id": PROJECT,
        "name": "Support",
        "status": AgentStatus.DRAFT,
        "created_at": utcnow(),
        "updated_at": utcnow(),
    }
    data.update(overrides)
    return Agent.model_validate(data)


def make_session(**overrides: object) -> Session:
    version = make_agent_version()
    if version.config_hash is None:
        version = version.with_config_hash()
    assert version.config_hash is not None
    data: dict[str, object] = {
        "id": SESSION_ID,
        "organization_id": ORG,
        "project_id": PROJECT,
        "agent_id": AGENT_ID,
        "agent_version_id": VERSION_ID,
        "deployment_id": None,
        "status": SessionStatus.ACTIVE,
        "channel": Channel.PLAYGROUND,
        "config_hash": version.config_hash,
        "started_at": utcnow(),
    }
    data.update(overrides)
    return Session.model_validate(data)


def new_id() -> UUID:
    return uuid4()
