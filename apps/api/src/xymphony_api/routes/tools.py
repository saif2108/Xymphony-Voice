from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from xymphony_api.deps import get_tool_service, optional_cursor, pagination_limit
from xymphony_api.schemas import (
    ToolCreateRequest,
    ToolListResponse,
    ToolUpdateRequest,
    VersionToolListResponse,
)
from xymphony_api.services import ToolService
from xymphony_contracts import ToolDefinition

router = APIRouter(prefix="/v1/projects/{project_id}", tags=["tools"])


@router.post("/tools", response_model=ToolDefinition, status_code=status.HTTP_201_CREATED)
def create_tool(
    project_id: UUID,
    body: ToolCreateRequest,
    service: ToolService = Depends(get_tool_service),
) -> ToolDefinition:
    return service.create_tool(project_id, body)


@router.get("/tools", response_model=ToolListResponse)
def list_tools(
    project_id: UUID,
    service: ToolService = Depends(get_tool_service),
    limit: int = Depends(pagination_limit),
    cursor: UUID | None = Depends(optional_cursor),
) -> ToolListResponse:
    items, next_cursor = service.list_tools(project_id, limit=limit, cursor=cursor)
    return ToolListResponse(items=items, next_cursor=next_cursor)


@router.get("/tools/{tool_id}", response_model=ToolDefinition)
def get_tool(
    project_id: UUID,
    tool_id: UUID,
    service: ToolService = Depends(get_tool_service),
) -> ToolDefinition:
    return service.get_tool(project_id, tool_id)


@router.patch("/tools/{tool_id}", response_model=ToolDefinition)
def update_tool(
    project_id: UUID,
    tool_id: UUID,
    body: ToolUpdateRequest,
    service: ToolService = Depends(get_tool_service),
) -> ToolDefinition:
    return service.update_tool(project_id, tool_id, body)


@router.delete("/tools/{tool_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tool(
    project_id: UUID,
    tool_id: UUID,
    service: ToolService = Depends(get_tool_service),
) -> Response:
    service.delete_tool(project_id, tool_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/agents/{agent_id}/versions/{version_id}/tools/{tool_id}",
    response_model=ToolDefinition,
    status_code=status.HTTP_201_CREATED,
)
def attach_tool(
    project_id: UUID,
    agent_id: UUID,
    version_id: UUID,
    tool_id: UUID,
    service: ToolService = Depends(get_tool_service),
) -> ToolDefinition:
    return service.attach_tool(project_id, agent_id, version_id, tool_id)


@router.delete(
    "/agents/{agent_id}/versions/{version_id}/tools/{tool_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def detach_tool(
    project_id: UUID,
    agent_id: UUID,
    version_id: UUID,
    tool_id: UUID,
    service: ToolService = Depends(get_tool_service),
) -> Response:
    service.detach_tool(project_id, agent_id, version_id, tool_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/agents/{agent_id}/versions/{version_id}/tools",
    response_model=VersionToolListResponse,
)
def list_version_tools(
    project_id: UUID,
    agent_id: UUID,
    version_id: UUID,
    service: ToolService = Depends(get_tool_service),
) -> VersionToolListResponse:
    items = service.list_version_tools(project_id, agent_id, version_id)
    return VersionToolListResponse(items=items)