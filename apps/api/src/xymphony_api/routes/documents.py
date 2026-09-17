from uuid import UUID

from fastapi import APIRouter, Depends, status

from xymphony_api.deps import get_document_service
from xymphony_api.schemas import (
    DocumentCreateRequest,
    KnowledgeBaseDocumentListResponse,
    KnowledgeBaseDocumentResponse,
)
from xymphony_api.services import DocumentService

router = APIRouter(
    prefix="/v1/knowledge-bases/{knowledge_base_id}",
    tags=["documents"],
)


@router.post(
    "/documents",
    response_model=KnowledgeBaseDocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_document(
    knowledge_base_id: UUID,
    body: DocumentCreateRequest,
    service: DocumentService = Depends(get_document_service),
) -> KnowledgeBaseDocumentResponse:
    document = service.create_document(
        knowledge_base_id=knowledge_base_id,
        body=body,
    )

    return KnowledgeBaseDocumentResponse(
        id=document.id,
        name=document.name,
        created_at=document.created_at,
    )


@router.get(
    "/documents",
    response_model=KnowledgeBaseDocumentListResponse,
)
def list_documents(
    knowledge_base_id: UUID,
    service: DocumentService = Depends(get_document_service),
) -> KnowledgeBaseDocumentListResponse:
    documents = service.list_documents(
        knowledge_base_id=knowledge_base_id,
    )

    return KnowledgeBaseDocumentListResponse(
        items=[
            KnowledgeBaseDocumentResponse(
                id=document.id,
                name=document.name,
                created_at=document.created_at,
            )
            for document in documents
        ],
    )