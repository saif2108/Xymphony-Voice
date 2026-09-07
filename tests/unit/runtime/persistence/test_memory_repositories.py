from uuid import uuid4

from tests.helpers import AGENT_ID, ORG, PROJECT, VERSION_ID, make_agent_version, utcnow

from xymphony_contracts import CreateSessionRequest, MessageRole, SessionStatus
from xymphony_contracts.persistence import ConversationRepository, SessionRepository
from xymphony_runtime.conversation import build_text_message, message_text
from xymphony_runtime.persistence import InMemoryConversationRepository, InMemorySessionRepository


def test_session_repository_create_and_get() -> None:
    version = make_agent_version()
    assert version.config_hash is not None
    repo: SessionRepository = InMemorySessionRepository()
    session = repo.create_session(
        CreateSessionRequest(
            organization_id=ORG,
            project_id=PROJECT,
            agent_id=AGENT_ID,
            agent_version_id=VERSION_ID,
            config_hash=version.config_hash,
        )
    )
    fetched = repo.get_session(session.id, organization_id=ORG, project_id=PROJECT)
    assert fetched is not None
    assert fetched.agent_version_id == VERSION_ID
    assert fetched.status == SessionStatus.INITIALIZING


def test_session_repository_update_status() -> None:
    version = make_agent_version()
    assert version.config_hash is not None
    repo = InMemorySessionRepository()
    session = repo.create_session(
        CreateSessionRequest(
            organization_id=ORG,
            project_id=PROJECT,
            agent_id=AGENT_ID,
            agent_version_id=VERSION_ID,
            config_hash=version.config_hash,
        )
    )
    updated = repo.update_session(session.model_copy(update={"status": SessionStatus.ACTIVE}))
    assert updated.status == SessionStatus.ACTIVE


def test_conversation_repository_append_and_list_ordered() -> None:
    version = make_agent_version()
    assert version.config_hash is not None
    sessions = InMemorySessionRepository()
    conversation: ConversationRepository = InMemoryConversationRepository()
    session = sessions.create_session(
        CreateSessionRequest(
            organization_id=ORG,
            project_id=PROJECT,
            agent_id=AGENT_ID,
            agent_version_id=VERSION_ID,
            config_hash=version.config_hash,
        )
    )
    turn_id = uuid4()
    first = build_text_message(
        session_id=session.id,
        turn_id=turn_id,
        organization_id=ORG,
        role=MessageRole.USER,
        text="Hi",
        created_at=utcnow(),
    )
    second = build_text_message(
        session_id=session.id,
        turn_id=turn_id,
        organization_id=ORG,
        role=MessageRole.ASSISTANT,
        text="Hello",
        created_at=utcnow(),
    )
    conversation.append_message(first)
    conversation.append_message(second)
    messages = conversation.list_messages(session.id, organization_id=ORG)
    assert len(messages) == 2
    assert message_text(messages[0]) == "Hi"
    assert message_text(messages[1]) == "Hello"
    assert conversation.next_sequence(session.id) == 3


def test_session_pins_immutable_agent_version() -> None:
    version = make_agent_version()
    assert version.config_hash is not None
    repo = InMemorySessionRepository()
    session = repo.create_session(
        CreateSessionRequest(
            organization_id=ORG,
            project_id=PROJECT,
            agent_id=AGENT_ID,
            agent_version_id=VERSION_ID,
            config_hash=version.config_hash,
        )
    )
    other_version_id = uuid4()
    updated = repo.update_session(session.model_copy(update={"status": SessionStatus.ACTIVE}))
    assert updated.agent_version_id == VERSION_ID
    assert updated.agent_version_id != other_version_id
    assert updated.config_hash == version.config_hash
