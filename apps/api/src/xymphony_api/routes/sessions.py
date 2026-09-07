from uuid import UUID

from fastapi import APIRouter, Depends, status

from xymphony_api.deps import get_session_service
from xymphony_api.schemas import MessageListResponse, SessionCreateRequest
from xymphony_api.services import SessionService
from xymphony_contracts.session import Session

router = APIRouter(prefix="/v1/projects/{project_id}", tags=["sessions"])


@router.post("/sessions", response_model=Session, status_code=status.HTTP_201_CREATED)
def create_session(
    project_id: UUID,
    body: SessionCreateRequest,
    service: SessionService = Depends(get_session_service),
) -> Session:
    return service.create_session(project_id, body)


@router.get("/sessions/{session_id}", response_model=Session)
def get_session(
    project_id: UUID,
    session_id: UUID,
    service: SessionService = Depends(get_session_service),
) -> Session:
    return service.get_session(project_id, session_id)


@router.get("/sessions/{session_id}/messages", response_model=MessageListResponse)
def list_session_messages(
    project_id: UUID,
    session_id: UUID,
    service: SessionService = Depends(get_session_service),
) -> MessageListResponse:
    items = service.list_messages(project_id, session_id)
    return MessageListResponse(items=items)
