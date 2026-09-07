from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from xymphony_api.errors import ConflictError, NotFoundError
from xymphony_api.logging import get_logger
from xymphony_api.mapping import (
    agent_to_contract,
    message_to_contract,
    session_to_contract,
    version_to_contract,
)
from xymphony_api.models import AgentRow, AgentVersionRow, ProjectRow, SessionRow
from xymphony_api.repositories import (
    AgentRepository,
    AgentVersionRepository,
    ConversationRepository,
    SessionRepository,
    TenantRepository,
)
from xymphony_api.schemas import (
    AgentCreateRequest,
    AgentUpdateRequest,
    AgentVersionCreateRequest,
    AgentVersionUpdateRequest,
    SessionCreateRequest,
)
from xymphony_contracts import (
    Agent,
    AgentVersion,
    AgentVersionStatus,
    Message,
    SessionStatus,
)
from xymphony_contracts.session import Session as SessionContract

logger = get_logger(__name__)


class AgentService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._tenants = TenantRepository(session)
        self._agents = AgentRepository(session)
        self._versions = AgentVersionRepository(session)

    def require_project(self, project_id: UUID) -> ProjectRow:
        project = self._tenants.get_project(project_id)
        if project is None:
            raise NotFoundError("Project not found")
        return project

    def create_agent(self, project_id: UUID, body: AgentCreateRequest) -> Agent:
        project = self.require_project(project_id)
        now = datetime.now(tz=UTC)
        row = AgentRow(
            id=uuid4(),
            organization_id=project.organization_id,
            project_id=project.id,
            name=body.name,
            description=body.description,
            status=body.status.value,
            tags=list(body.tags),
            created_at=now,
            updated_at=now,
        )
        self._agents.add(row)
        logger.info(
            "agent_created",
            extra={"agent_id": str(row.id), "project_id": str(project.id)},
        )
        return agent_to_contract(row)

    def list_agents(
        self, project_id: UUID, *, limit: int, cursor: UUID | None
    ) -> tuple[list[Agent], str | None]:
        project = self.require_project(project_id)
        rows = self._agents.list_in_project(
            project_id=project.id,
            organization_id=project.organization_id,
            limit=limit + 1,
            cursor=cursor,
        )
        next_cursor: str | None = None
        if len(rows) > limit:
            rows = rows[:limit]
            next_cursor = str(rows[-1].id)
        return [agent_to_contract(row) for row in rows], next_cursor

    def get_agent(self, project_id: UUID, agent_id: UUID) -> Agent:
        project = self.require_project(project_id)
        row = self._agents.get_in_project(
            project_id=project.id, organization_id=project.organization_id, agent_id=agent_id
        )
        if row is None:
            raise NotFoundError("Agent not found")
        return agent_to_contract(row)

    def update_agent(self, project_id: UUID, agent_id: UUID, body: AgentUpdateRequest) -> Agent:
        project = self.require_project(project_id)
        row = self._agents.get_in_project(
            project_id=project.id, organization_id=project.organization_id, agent_id=agent_id
        )
        if row is None:
            raise NotFoundError("Agent not found")
        if body.name is not None:
            row.name = body.name
        if body.description is not None:
            row.description = body.description
        if body.status is not None:
            row.status = body.status.value
        if body.tags is not None:
            row.tags = list(body.tags)
        row.updated_at = datetime.now(tz=UTC)
        self._session.flush()
        return agent_to_contract(row)

    def delete_agent(self, project_id: UUID, agent_id: UUID) -> None:
        project = self.require_project(project_id)
        row = self._agents.get_in_project(
            project_id=project.id, organization_id=project.organization_id, agent_id=agent_id
        )
        if row is None:
            raise NotFoundError("Agent not found")
        self._agents.delete(row)

    def create_version(
        self, project_id: UUID, agent_id: UUID, body: AgentVersionCreateRequest
    ) -> AgentVersion:
        project = self.require_project(project_id)
        agent = self._agents.get_in_project(
            project_id=project.id, organization_id=project.organization_id, agent_id=agent_id
        )
        if agent is None:
            raise NotFoundError("Agent not found")
        now = datetime.now(tz=UTC)
        version_n = self._versions.next_version_n(agent.id)
        snapshot = AgentVersion(
            id=uuid4(),
            organization_id=project.organization_id,
            project_id=project.id,
            agent_id=agent.id,
            version_n=version_n,
            status=AgentVersionStatus.DRAFT,
            instructions=body.instructions,
            personality=body.personality,
            locale=body.locale,
            llm=body.llm,
            stt=body.stt,
            tts=body.tts,
            created_at=now,
        ).with_config_hash()
        assert snapshot.config_hash is not None
        row = AgentVersionRow(
            id=snapshot.id,
            organization_id=snapshot.organization_id,
            project_id=snapshot.project_id,
            agent_id=snapshot.agent_id,
            version_n=snapshot.version_n,
            status=snapshot.status.value,
            instructions=snapshot.instructions,
            personality=snapshot.personality,
            locale=snapshot.locale,
            llm=snapshot.llm.model_dump(mode="json"),
            stt=snapshot.stt.model_dump(mode="json"),
            tts=snapshot.tts.model_dump(mode="json"),
            config_hash=snapshot.config_hash,
            created_at=snapshot.created_at,
            published_at=None,
        )
        self._versions.add(row)
        logger.info("agent_version_created", extra={"agent_id": str(agent.id)})
        return version_to_contract(row)

    def list_versions(self, project_id: UUID, agent_id: UUID, *, limit: int) -> list[AgentVersion]:
        project = self.require_project(project_id)
        agent = self._agents.get_in_project(
            project_id=project.id, organization_id=project.organization_id, agent_id=agent_id
        )
        if agent is None:
            raise NotFoundError("Agent not found")
        rows = self._versions.list_for_agent(
            agent_id=agent.id,
            organization_id=project.organization_id,
            project_id=project.id,
            limit=limit,
        )
        return [version_to_contract(row) for row in rows]

    def get_version(self, project_id: UUID, agent_id: UUID, version_id: UUID) -> AgentVersion:
        project = self.require_project(project_id)
        row = self._versions.get_for_agent(
            agent_id=agent_id,
            organization_id=project.organization_id,
            project_id=project.id,
            version_id=version_id,
        )
        if row is None:
            raise NotFoundError("Agent version not found")
        return version_to_contract(row)

    def update_version(
        self,
        project_id: UUID,
        agent_id: UUID,
        version_id: UUID,
        body: AgentVersionUpdateRequest,
    ) -> AgentVersion:
        project = self.require_project(project_id)
        row = self._versions.get_for_agent(
            agent_id=agent_id,
            organization_id=project.organization_id,
            project_id=project.id,
            version_id=version_id,
        )
        if row is None:
            raise NotFoundError("Agent version not found")
        if row.status != AgentVersionStatus.DRAFT.value:
            raise ConflictError(
                "conflict_published_immutable",
                "Published AgentVersion cannot be mutated; create a new version",
            )
        current = version_to_contract(row)
        updated = current.model_copy(
            update={
                key: value
                for key, value in {
                    "instructions": body.instructions,
                    "personality": body.personality,
                    "locale": body.locale,
                    "llm": body.llm,
                    "stt": body.stt,
                    "tts": body.tts,
                }.items()
                if value is not None
            }
        ).with_config_hash()
        assert updated.config_hash is not None
        row.instructions = updated.instructions
        row.personality = updated.personality
        row.locale = updated.locale
        row.llm = updated.llm.model_dump(mode="json")
        row.stt = updated.stt.model_dump(mode="json")
        row.tts = updated.tts.model_dump(mode="json")
        row.config_hash = updated.config_hash
        self._session.flush()
        return version_to_contract(row)

    def publish_version(self, project_id: UUID, agent_id: UUID, version_id: UUID) -> AgentVersion:
        project = self.require_project(project_id)
        row = self._versions.get_for_agent(
            agent_id=agent_id,
            organization_id=project.organization_id,
            project_id=project.id,
            version_id=version_id,
        )
        if row is None:
            raise NotFoundError("Agent version not found")
        if row.status == AgentVersionStatus.PUBLISHED.value:
            return version_to_contract(row)
        row.status = AgentVersionStatus.PUBLISHED.value
        row.published_at = datetime.now(tz=UTC)
        self._session.flush()
        return version_to_contract(row)


class SessionService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._tenants = TenantRepository(session)
        self._agents = AgentRepository(session)
        self._versions = AgentVersionRepository(session)
        self._sessions = SessionRepository(session)
        self._conversation = ConversationRepository(session)

    def require_project(self, project_id: UUID) -> ProjectRow:
        project = self._tenants.get_project(project_id)
        if project is None:
            raise NotFoundError("Project not found")
        return project

    def create_session(self, project_id: UUID, body: SessionCreateRequest) -> SessionContract:
        project = self.require_project(project_id)
        agent = self._agents.get_in_project(
            project_id=project.id,
            organization_id=project.organization_id,
            agent_id=body.agent_id,
        )
        if agent is None:
            raise NotFoundError("Agent not found")

        version_row: AgentVersionRow | None
        if body.agent_version_id is not None:
            version_row = self._versions.get_for_agent(
                agent_id=agent.id,
                organization_id=project.organization_id,
                project_id=project.id,
                version_id=body.agent_version_id,
            )
            if version_row is None:
                raise NotFoundError("Agent version not found")
        else:
            version_row = self._versions.get_latest_published_for_agent(
                agent_id=agent.id,
                organization_id=project.organization_id,
                project_id=project.id,
            )
            if version_row is None:
                raise ConflictError(
                    "no_published_version",
                    "Agent has no published version; publish a version or specify agent_version_id",
                )

        now = datetime.now(tz=UTC)
        row = SessionRow(
            id=uuid4(),
            organization_id=project.organization_id,
            project_id=project.id,
            agent_id=agent.id,
            agent_version_id=version_row.id,
            deployment_id=None,
            status=SessionStatus.INITIALIZING.value,
            channel=body.channel.value,
            livekit_room=body.livekit_room,
            config_hash=version_row.config_hash,
            started_at=now,
            updated_at=now,
        )
        self._sessions.create(row)
        logger.info(
            "session_created",
            extra={
                "session_id": str(row.id),
                "agent_id": str(agent.id),
                "agent_version_id": str(version_row.id),
            },
        )
        return session_to_contract(row)

    def get_session(self, project_id: UUID, session_id: UUID) -> SessionContract:
        project = self.require_project(project_id)
        row = self._sessions.get(
            session_id,
            organization_id=project.organization_id,
            project_id=project.id,
        )
        if row is None:
            raise NotFoundError("Session not found")
        return session_to_contract(row)

    def update_session_status(
        self, project_id: UUID, session_id: UUID, status: SessionStatus
    ) -> SessionContract:
        project = self.require_project(project_id)
        row = self._sessions.get(
            session_id,
            organization_id=project.organization_id,
            project_id=project.id,
        )
        if row is None:
            raise NotFoundError("Session not found")
        row.status = status.value
        row.updated_at = datetime.now(tz=UTC)
        self._sessions.update(row)
        return session_to_contract(row)

    def list_messages(self, project_id: UUID, session_id: UUID) -> list[Message]:
        project = self.require_project(project_id)
        row = self._sessions.get(
            session_id,
            organization_id=project.organization_id,
            project_id=project.id,
        )
        if row is None:
            raise NotFoundError("Session not found")
        rows = self._conversation.list_for_session(
            session_id,
            organization_id=project.organization_id,
        )
        return [message_to_contract(item) for item in rows]
