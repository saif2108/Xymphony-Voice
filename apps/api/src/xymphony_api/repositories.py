from __future__ import annotations

from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from xymphony_api.models import (
    AgentRow,
    AgentVersionRow,
    ConversationMessageRow,
    OrganizationRow,
    ProjectRow,
    SessionRow,
)


class TenantRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_organization(self, organization_id: UUID) -> OrganizationRow | None:
        return self._session.get(OrganizationRow, organization_id)

    def get_project(self, project_id: UUID) -> ProjectRow | None:
        return self._session.get(ProjectRow, project_id)

    def add_organization(self, row: OrganizationRow) -> OrganizationRow:
        self._session.add(row)
        self._session.flush()
        return row

    def add_project(self, row: ProjectRow) -> ProjectRow:
        self._session.add(row)
        self._session.flush()
        return row


class AgentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, agent_id: UUID) -> AgentRow | None:
        return self._session.get(AgentRow, agent_id)

    def get_in_project(
        self, *, project_id: UUID, organization_id: UUID, agent_id: UUID
    ) -> AgentRow | None:
        stmt: Select[tuple[AgentRow]] = select(AgentRow).where(
            AgentRow.id == agent_id,
            AgentRow.project_id == project_id,
            AgentRow.organization_id == organization_id,
        )
        return self._session.scalar(stmt)

    def list_in_project(
        self,
        *,
        project_id: UUID,
        organization_id: UUID,
        limit: int,
        cursor: UUID | None,
    ) -> list[AgentRow]:
        stmt = select(AgentRow).where(
            AgentRow.project_id == project_id,
            AgentRow.organization_id == organization_id,
        )
        if cursor is not None:
            cursor_row = self.get(cursor)
            if cursor_row is not None:
                stmt = stmt.where(
                    (AgentRow.created_at < cursor_row.created_at)
                    | (
                        (AgentRow.created_at == cursor_row.created_at)
                        & (AgentRow.id < cursor_row.id)
                    )
                )
        stmt = stmt.order_by(AgentRow.created_at.desc(), AgentRow.id.desc()).limit(limit)
        return list(self._session.scalars(stmt).all())

    def add(self, row: AgentRow) -> AgentRow:
        self._session.add(row)
        self._session.flush()
        return row

    def delete(self, row: AgentRow) -> None:
        self._session.delete(row)
        self._session.flush()


class AgentVersionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, version_id: UUID) -> AgentVersionRow | None:
        return self._session.get(AgentVersionRow, version_id)

    def get_for_agent(
        self, *, agent_id: UUID, organization_id: UUID, project_id: UUID, version_id: UUID
    ) -> AgentVersionRow | None:
        stmt = select(AgentVersionRow).where(
            AgentVersionRow.id == version_id,
            AgentVersionRow.agent_id == agent_id,
            AgentVersionRow.organization_id == organization_id,
            AgentVersionRow.project_id == project_id,
        )
        return self._session.scalar(stmt)

    def list_for_agent(
        self, *, agent_id: UUID, organization_id: UUID, project_id: UUID, limit: int
    ) -> list[AgentVersionRow]:
        stmt = (
            select(AgentVersionRow)
            .where(
                AgentVersionRow.agent_id == agent_id,
                AgentVersionRow.organization_id == organization_id,
                AgentVersionRow.project_id == project_id,
            )
            .order_by(AgentVersionRow.version_n.desc())
            .limit(limit)
        )
        return list(self._session.scalars(stmt).all())

    def next_version_n(self, agent_id: UUID) -> int:
        current = self._session.scalar(
            select(func.max(AgentVersionRow.version_n)).where(AgentVersionRow.agent_id == agent_id)
        )
        return int(current or 0) + 1

    def add(self, row: AgentVersionRow) -> AgentVersionRow:
        self._session.add(row)
        self._session.flush()
        return row

    def get_latest_published_for_agent(
        self,
        *,
        agent_id: UUID,
        organization_id: UUID,
        project_id: UUID,
    ) -> AgentVersionRow | None:
        stmt = (
            select(AgentVersionRow)
            .where(
                AgentVersionRow.agent_id == agent_id,
                AgentVersionRow.organization_id == organization_id,
                AgentVersionRow.project_id == project_id,
                AgentVersionRow.status == "published",
            )
            .order_by(AgentVersionRow.version_n.desc())
            .limit(1)
        )
        return self._session.scalar(stmt)


class SessionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, row: SessionRow) -> SessionRow:
        self._session.add(row)
        self._session.flush()
        return row

    def get(
        self,
        session_id: UUID,
        *,
        organization_id: UUID | None = None,
        project_id: UUID | None = None,
    ) -> SessionRow | None:
        stmt = select(SessionRow).where(SessionRow.id == session_id)
        if organization_id is not None:
            stmt = stmt.where(SessionRow.organization_id == organization_id)
        if project_id is not None:
            stmt = stmt.where(SessionRow.project_id == project_id)
        return self._session.scalar(stmt)

    def update(self, row: SessionRow) -> SessionRow:
        self._session.flush()
        return row


class ConversationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def append(self, row: ConversationMessageRow) -> ConversationMessageRow:
        self._session.add(row)
        self._session.flush()
        return row

    def list_for_session(
        self,
        session_id: UUID,
        *,
        organization_id: UUID | None = None,
    ) -> list[ConversationMessageRow]:
        stmt = (
            select(ConversationMessageRow)
            .where(ConversationMessageRow.session_id == session_id)
            .order_by(ConversationMessageRow.sequence.asc())
        )
        if organization_id is not None:
            stmt = stmt.where(ConversationMessageRow.organization_id == organization_id)
        return list(self._session.scalars(stmt).all())

    def next_sequence(self, session_id: UUID) -> int:
        current = self._session.scalar(
            select(func.max(ConversationMessageRow.sequence)).where(
                ConversationMessageRow.session_id == session_id
            )
        )
        return int(current or 0) + 1
