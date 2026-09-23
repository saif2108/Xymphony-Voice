"""Control-plane tool definition contract. No vendor SDKs."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from xymphony_contracts.enums import ToolType

__all__ = [
    "ToolDefinition",
]


class ToolDefinition(BaseModel):
    """API-facing representation of a tool definition managed via the control plane."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    organization_id: UUID
    project_id: UUID
    name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=4000)
    tool_type: ToolType = ToolType.FUNCTION
    parameters: dict[str, JsonValue] = Field(
        default_factory=lambda: {"type": "object", "properties": {}}
    )
    config: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    created_by: UUID | None = None
    created_at: datetime
    updated_at: datetime
