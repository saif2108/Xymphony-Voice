from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from xymphony_api.deps import get_agent_service, optional_cursor, pagination_limit
from xymphony_api.schemas import (
    AgentCreateRequest,
    AgentListResponse,
    AgentUpdateRequest,
    AgentVersionCreateRequest,
    AgentVersionListResponse,
    AgentVersionUpdateRequest,
)
from xymphony_api.services import AgentService
from xymphony_contracts import Agent, AgentVersion

router = APIRouter(prefix="/v1/projects/{project_id}", tags=["agents"])


@router.post("/agents", response_model=Agent, status_code=status.HTTP_201_CREATED)
def create_agent(
    project_id: UUID,
    body: AgentCreateRequest,
    service: AgentService = Depends(get_agent_service),
) -> Agent:
    return service.create_agent(project_id, body)


@router.get("/agents", response_model=AgentListResponse)
def list_agents(
    project_id: UUID,
    service: AgentService = Depends(get_agent_service),
    limit: int = Depends(pagination_limit),
    cursor: UUID | None = Depends(optional_cursor),
) -> AgentListResponse:
    items, next_cursor = service.list_agents(project_id, limit=limit, cursor=cursor)
    return AgentListResponse(items=items, next_cursor=next_cursor)


@router.get("/agents/{agent_id}", response_model=Agent)
def get_agent(
    project_id: UUID,
    agent_id: UUID,
    service: AgentService = Depends(get_agent_service),
) -> Agent:
    return service.get_agent(project_id, agent_id)


@router.patch("/agents/{agent_id}", response_model=Agent)
def update_agent(
    project_id: UUID,
    agent_id: UUID,
    body: AgentUpdateRequest,
    service: AgentService = Depends(get_agent_service),
) -> Agent:
    return service.update_agent(project_id, agent_id, body)


@router.delete("/agents/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_agent(
    project_id: UUID,
    agent_id: UUID,
    service: AgentService = Depends(get_agent_service),
) -> Response:
    service.delete_agent(project_id, agent_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/agents/{agent_id}/versions",
    response_model=AgentVersion,
    status_code=status.HTTP_201_CREATED,
)
def create_version(
    project_id: UUID,
    agent_id: UUID,
    body: AgentVersionCreateRequest,
    service: AgentService = Depends(get_agent_service),
) -> AgentVersion:
    return service.create_version(project_id, agent_id, body)


@router.get("/agents/{agent_id}/versions", response_model=AgentVersionListResponse)
def list_versions(
    project_id: UUID,
    agent_id: UUID,
    service: AgentService = Depends(get_agent_service),
    limit: int = Depends(pagination_limit),
) -> AgentVersionListResponse:
    items = service.list_versions(project_id, agent_id, limit=limit)
    return AgentVersionListResponse(items=items, next_cursor=None)


@router.get("/agents/{agent_id}/versions/{version_id}", response_model=AgentVersion)
def get_version(
    project_id: UUID,
    agent_id: UUID,
    version_id: UUID,
    service: AgentService = Depends(get_agent_service),
) -> AgentVersion:
    return service.get_version(project_id, agent_id, version_id)


@router.patch("/agents/{agent_id}/versions/{version_id}", response_model=AgentVersion)
def update_version(
    project_id: UUID,
    agent_id: UUID,
    version_id: UUID,
    body: AgentVersionUpdateRequest,
    service: AgentService = Depends(get_agent_service),
) -> AgentVersion:
    return service.update_version(project_id, agent_id, version_id, body)


@router.post("/agents/{agent_id}/versions/{version_id}/publish", response_model=AgentVersion)
def publish_version(
    project_id: UUID,
    agent_id: UUID,
    version_id: UUID,
    service: AgentService = Depends(get_agent_service),
) -> AgentVersion:
    return service.publish_version(project_id, agent_id, version_id)
