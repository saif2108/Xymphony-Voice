import pytest
from pydantic import ValidationError

from tests.helpers import make_agent_version, utcnow
from xymphony_contracts import AgentVersionStatus


def test_valid_agent_version_creation() -> None:
    version = make_agent_version()
    assert version.version_n == 1
    assert version.status == AgentVersionStatus.DRAFT
    assert version.llm.provider_key == "openai_compatible"
    assert version.stt.provider_key == "assemblyai"
    assert version.tts.voice_ref == "voice_default"
    assert version.config_hash is not None
    assert len(version.config_hash) == 64


def test_agent_version_is_frozen() -> None:
    version = make_agent_version()
    with pytest.raises(ValidationError):
        version.instructions = "mutated"  # type: ignore[misc]


def test_agent_version_copy_is_replacement_not_mutation() -> None:
    version = make_agent_version()
    updated = version.model_copy(update={"instructions": "New instructions."})
    assert version.instructions == "You are a helpful voice agent."
    assert updated.instructions == "New instructions."
    assert updated.id == version.id


def test_empty_instructions_rejected() -> None:
    with pytest.raises(ValidationError):
        make_agent_version(instructions="")


def test_published_requires_published_at() -> None:
    with pytest.raises(ValidationError):
        make_agent_version(status=AgentVersionStatus.PUBLISHED)


def test_published_with_timestamp_ok() -> None:
    version = make_agent_version(
        status=AgentVersionStatus.PUBLISHED,
        published_at=utcnow(),
    )
    assert version.published_at is not None


def test_config_hash_is_stable() -> None:
    a = make_agent_version()
    b = make_agent_version()
    assert a.compute_config_hash() == b.compute_config_hash()


def test_config_hash_changes_with_instructions() -> None:
    a = make_agent_version()
    b = make_agent_version(instructions="Different.")
    assert a.compute_config_hash() != b.compute_config_hash()


def test_invalid_config_hash_rejected() -> None:
    with pytest.raises(ValidationError):
        make_agent_version(config_hash="not-a-hash")



def test_compiled_system_prompt_joins_personality_before_instructions() -> None:
    version = make_agent_version(
        instructions="Answer billing questions.",
        personality="Friendly and concise.",
)
    assert (
        version.compiled_system_prompt()
        == "Friendly and concise.\n\nAnswer billing questions."
    )


def test_compiled_system_prompt_omits_blank_personality() -> None:
    version = make_agent_version(instructions="Answer billing questions.", personality="")
    assert version.compiled_system_prompt() == "Answer billing questions."


def test_compiled_system_prompt_treats_whitespace_personality_as_blank() -> None:
    version = make_agent_version(instructions="Answer billing questions.", personality="   \n  ")
    assert version.compiled_system_prompt() == "Answer billing questions."


def test_compiled_system_prompt_strips_surrounding_whitespace() -> None:
    version = make_agent_version(
        instructions="  Answer billing questions.  ",
        personality="  Friendly.  ",
)
    assert version.compiled_system_prompt() == "Friendly.\n\nAnswer billing questions."
