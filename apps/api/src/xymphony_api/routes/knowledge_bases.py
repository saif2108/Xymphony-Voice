from uuid import UUID

from fastapi import APIRouter, Depends, status

from xymphony_api.deps import get_knowledge_base_service
from xymphony_api.schemas import (
    KnowledgeBaseCreateRequest,
    KnowledgeBaseListResponse,
    KnowledgeBaseResponse,
)
from xymphony_api.services import KnowledgeBaseService

router = APIRouter(
    prefix="/v1/projects/{project_id}",
    tags=["knowledge-bases"],
)


@router.post(
    "/knowledge-bases",
    response_model=KnowledgeBaseResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_knowledge_base(
    project_id: UUID,
    body: KnowledgeBaseCreateRequest,
    service: KnowledgeBaseService = Depends(get_knowledge_base_service),
) -> KnowledgeBaseResponse:
    knowledge_base = service.create_knowledge_base(project_id, body)

    return KnowledgeBaseResponse(
        id=knowledge_base.id,
        project_id=knowledge_base.project_id,
        name=knowledge_base.name,
        description=knowledge_base.description,
        created_at=knowledge_base.created_at,
    )


@router.get(
    "/knowledge-bases",
    response_model=KnowledgeBaseListResponse
)
def list_knowledge_bases(
    project_id: UUID,
    service: KnowledgeBaseService = Depends(get_knowledge_base_service),
) -> list[KnowledgeBaseResponse]:
    knowledge_bases = service.list_knowledge_bases(project_id)

    return KnowledgeBaseListResponse(
    items=[
        KnowledgeBaseResponse(
            id=knowledge_base.id,
            project_id=knowledge_base.project_id,
            name=knowledge_base.name,
            description=knowledge_base.description,
            created_at=knowledge_base.created_at,
        )
        for knowledge_base in knowledge_bases
    ]
)