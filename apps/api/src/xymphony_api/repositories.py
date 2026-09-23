from __future__ import annotations

from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from xymphony_api.models import (
    AgentRow,
    AgentVersionKnowledgeBaseRow,
    AgentVersionRow,
    AgentVersionToolRow,
    ConversationMessageRow,
    ConversationSummaryRow,
    DocumentChunkRow,
    DocumentRow,
    KnowledgeBaseRow,
    OrganizationRow,
    ProjectRow,
    SessionRow,
    ToolDefinitionRow,
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

    def list_in_project(
        self,
        *,
        project_id: UUID,
        organization_id: UUID,
        limit: int = 50,
    ) -> list[SessionRow]:
        stmt = (
            select(SessionRow)
            .where(
                SessionRow.project_id == project_id,
                SessionRow.organization_id == organization_id,
            )
            .order_by(SessionRow.started_at.desc(), SessionRow.id.desc())
            .limit(limit)
        )
        return list(self._session.scalars(stmt).all())

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


class ConversationSummaryRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_for_session(
        self,
        session_id: UUID,
        *,
        organization_id: UUID | None = None,
    ) -> ConversationSummaryRow | None:
        stmt = select(ConversationSummaryRow).where(ConversationSummaryRow.session_id == session_id)
        if organization_id is not None:
            stmt = stmt.where(ConversationSummaryRow.organization_id == organization_id)
        return self._session.scalar(stmt)

    def upsert(self, row: ConversationSummaryRow) -> ConversationSummaryRow:
        existing = self.get_for_session(row.session_id)
        if existing is None:
            self._session.add(row)
            self._session.flush()
            return row
        existing.organization_id = row.organization_id
        existing.agent_version_id = row.agent_version_id
        existing.through_sequence = row.through_sequence
        existing.summary_text = row.summary_text
        existing.source_message_count = row.source_message_count
        existing.created_at = row.created_at
        self._session.flush()
        return existing


class ToolDefinitionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, row: ToolDefinitionRow) -> ToolDefinitionRow:
        self._session.add(row)
        self._session.flush()
        return row

    def get(self, tool_id: UUID) -> ToolDefinitionRow | None:
        return self._session.get(ToolDefinitionRow, tool_id)

    def get_in_project(
        self, *, project_id: UUID, organization_id: UUID, tool_id: UUID
    ) -> ToolDefinitionRow | None:
        stmt = select(ToolDefinitionRow).where(
            ToolDefinitionRow.id == tool_id,
            ToolDefinitionRow.project_id == project_id,
            ToolDefinitionRow.organization_id == organization_id,
        )
        return self._session.scalar(stmt)

    def get_by_name_in_project(
        self, *, project_id: UUID, organization_id: UUID, name: str
    ) -> ToolDefinitionRow | None:
        stmt = select(ToolDefinitionRow).where(
            ToolDefinitionRow.project_id == project_id,
            ToolDefinitionRow.organization_id == organization_id,
            ToolDefinitionRow.name == name,
        )
        return self._session.scalar(stmt)

    def list_in_project(
        self,
        *,
        project_id: UUID,
        organization_id: UUID,
        limit: int,
        cursor: UUID | None,
    ) -> list[ToolDefinitionRow]:
        stmt = select(ToolDefinitionRow).where(
            ToolDefinitionRow.project_id == project_id,
            ToolDefinitionRow.organization_id == organization_id,
        )
        if cursor is not None:
            cursor_row = self.get(cursor)
            if cursor_row is not None:
                stmt = stmt.where(
                    (ToolDefinitionRow.created_at < cursor_row.created_at)
                    | (
                        (ToolDefinitionRow.created_at == cursor_row.created_at)
                        & (ToolDefinitionRow.id < cursor_row.id)
                    )
                )
        stmt = stmt.order_by(
            ToolDefinitionRow.created_at.desc(), ToolDefinitionRow.id.desc()
        ).limit(limit)
        return list(self._session.scalars(stmt).all())

    def delete(self, row: ToolDefinitionRow) -> None:
        self._session.delete(row)
        self._session.flush()


class AgentVersionToolRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def attach(
        self, *, agent_version_id: UUID, tool_definition_id: UUID, enabled: bool = True
    ) -> AgentVersionToolRow:
        existing = self.get(
            agent_version_id=agent_version_id,
            tool_definition_id=tool_definition_id,
        )
        if existing is not None:
            existing.enabled = enabled
            self._session.flush()
            return existing
        row = AgentVersionToolRow(
            agent_version_id=agent_version_id,
            tool_definition_id=tool_definition_id,
            enabled=enabled,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def get(
        self, *, agent_version_id: UUID, tool_definition_id: UUID
    ) -> AgentVersionToolRow | None:
        return self._session.get(AgentVersionToolRow, (agent_version_id, tool_definition_id))

    def detach(self, *, agent_version_id: UUID, tool_definition_id: UUID) -> bool:
        row = self.get(agent_version_id=agent_version_id, tool_definition_id=tool_definition_id)
        if row is None:
            return False
        self._session.delete(row)
        self._session.flush()
        return True

    def list_for_version(self, *, agent_version_id: UUID) -> list[AgentVersionToolRow]:
        stmt = (
            select(AgentVersionToolRow)
            .where(AgentVersionToolRow.agent_version_id == agent_version_id)
            .order_by(AgentVersionToolRow.created_at.asc())
        )
        return list(self._session.scalars(stmt).all())


class KnowledgeBaseRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        organization_id: UUID,
        project_id: UUID,
        name: str,
        description: str = "",
    ) -> KnowledgeBaseRow:
        row = KnowledgeBaseRow(
            organization_id=organization_id,
            project_id=project_id,
            name=name,
            description=description,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def get(self, knowledge_base_id: UUID) -> KnowledgeBaseRow | None:
        return self._session.get(KnowledgeBaseRow, knowledge_base_id)

    def list_in_project(
        self,
        *,
        project_id: UUID,
        organization_id: UUID,
    ) -> list[KnowledgeBaseRow]:
        stmt = (
            select(KnowledgeBaseRow)
            .where(
                KnowledgeBaseRow.project_id == project_id,
                KnowledgeBaseRow.organization_id == organization_id,
            )
            .order_by(KnowledgeBaseRow.created_at.desc())
        )
        return list(self._session.scalars(stmt).all())


class DocumentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        knowledge_base_id: UUID,
        name: str,
        content: str,
    ) -> DocumentRow:
        row = DocumentRow(
            knowledge_base_id=knowledge_base_id,
            name=name,
            content=content,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def get(self, document_id: UUID) -> DocumentRow | None:
        return self._session.get(DocumentRow, document_id)

    def list_in_knowledge_base(
        self,
        *,
        knowledge_base_id: UUID,
    ) -> list[DocumentRow]:
        stmt = (
            select(DocumentRow)
            .where(DocumentRow.knowledge_base_id == knowledge_base_id)
            .order_by(DocumentRow.created_at.desc())
        )
        return list(self._session.scalars(stmt).all())

    def delete(self, row: DocumentRow) -> None:
        self._session.delete(row)
        self._session.flush()


class DocumentChunkRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_many(
        self,
        *,
        document_id: UUID,
        chunks: list[tuple[int, str, list[float]]],
    ) -> list[DocumentChunkRow]:
        rows = [
            DocumentChunkRow(
                document_id=document_id,
                chunk_index=chunk_index,
                content=content,
                embedding=embedding,
            )
            for chunk_index, content, embedding in chunks
        ]
        self._session.add_all(rows)
        self._session.flush()
        return rows

    def list_for_document(
        self,
        *,
        document_id: UUID,
    ) -> list[DocumentChunkRow]:
        stmt = (
            select(DocumentChunkRow)
            .where(DocumentChunkRow.document_id == document_id)
            .order_by(DocumentChunkRow.chunk_index.asc())
        )
        return list(self._session.scalars(stmt).all())
    def search_hybrid(
        self,
        *,
        agent_version_id: UUID,
        query: str,
        query_embedding: list[float],
        limit: int = 5,
    ) -> list[DocumentChunkRow]:
        return [
            row
            for row, _score in self.search_hybrid_scored(
                agent_version_id=agent_version_id,
                query=query,
                query_embedding=query_embedding,
                limit=limit,
            )
        ]

    def search_hybrid_scored(
        self,
        *,
        agent_version_id: UUID,
        query: str,
        query_embedding: list[float],
        limit: int = 5,
    ) -> list[tuple[DocumentChunkRow, float]]:
        semantic_distance = DocumentChunkRow.embedding.cosine_distance(
            query_embedding
        )
        lexical_query = func.websearch_to_tsquery("english", query)

        semantic_score = 1 - semantic_distance
        lexical_score = func.coalesce(
            func.ts_rank_cd(
                DocumentChunkRow.search_vector,
                lexical_query,
            ),
            0,
        )

        combined_score = (
            (0.7 * semantic_score) +
            (0.3 * lexical_score)
        )

        stmt = (
            select(DocumentChunkRow, combined_score.label("score"))
            .join(
                DocumentRow,
                DocumentRow.id == DocumentChunkRow.document_id,
            )
            .join(
                AgentVersionKnowledgeBaseRow,
                AgentVersionKnowledgeBaseRow.knowledge_base_id
                == DocumentRow.knowledge_base_id,
            )
            .where(
                AgentVersionKnowledgeBaseRow.agent_version_id
                == agent_version_id,
                DocumentChunkRow.embedding.is_not(None),
            )
            .order_by(combined_score.desc())
            .limit(limit)
        )

        return [
            (row, float(score))
            for row, score in self._session.execute(stmt).all()
        ]




    def delete_for_document(self, *, document_id: UUID) -> None:
        stmt = select(DocumentChunkRow).where(DocumentChunkRow.document_id == document_id)
        for row in self._session.scalars(stmt).all():
            self._session.delete(row)
        self._session.flush()


class AgentVersionKnowledgeBaseRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def attach(
        self,
        *,
        agent_version_id: UUID,
        knowledge_base_id: UUID,
    ) -> AgentVersionKnowledgeBaseRow:
        existing = self.get(
            agent_version_id=agent_version_id,
            knowledge_base_id=knowledge_base_id,
        )
        if existing is not None:
            return existing

        row = AgentVersionKnowledgeBaseRow(
            agent_version_id=agent_version_id,
            knowledge_base_id=knowledge_base_id,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def get(
        self,
        *,
        agent_version_id: UUID,
        knowledge_base_id: UUID,
    ) -> AgentVersionKnowledgeBaseRow | None:
        return self._session.get(
            AgentVersionKnowledgeBaseRow,
            (agent_version_id, knowledge_base_id),
        )

    def detach(
        self,
        *,
        agent_version_id: UUID,
        knowledge_base_id: UUID,
    ) -> bool:
        row = self.get(
            agent_version_id=agent_version_id,
            knowledge_base_id=knowledge_base_id,
        )
        if row is None:
            return False

        self._session.delete(row)
        self._session.flush()
        return True
