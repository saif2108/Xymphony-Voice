"""Provider-neutral tool domain models. No vendor SDKs."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from xymphony_contracts.llm import LLMToolDefinition

__all__ = [
    "Tool",
    "ToolExecutionContext",
    "ToolHandler",
]

ToolHandler = Callable[..., Any] | Callable[..., Awaitable[Any]]


class ToolExecutionContext(BaseModel):
    """Minimal provider-neutral context supplied to tool execution."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tool_call_id: str = Field(default="", max_length=128)
    session_id: str | None = Field(default=None, max_length=128)


class Tool:
    """A deterministic executable tool capability."""

    def __init__(
        self,
        *,
        name: str,
        description: str = "",
        parameters: dict[str, JsonValue] | None = None,
        handler: ToolHandler,
    ) -> None:
        if not name or not name.strip():
            raise ValueError("Tool name must not be empty.")
        if len(name) > 128:
            raise ValueError("Tool name must not exceed 128 characters.")
        if len(description) > 4000:
            raise ValueError("Tool description must not exceed 4000 characters.")

        self._name = name.strip()
        self._description = description
        self._parameters: dict[str, JsonValue] = (
            parameters if parameters is not None else {"type": "object", "properties": {}}
        )
        self._handler = handler

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def parameters(self) -> dict[str, JsonValue]:
        return self._parameters

    @property
    def handler(self) -> ToolHandler:
        return self._handler

    def to_definition(self) -> LLMToolDefinition:
        """Expose as provider-neutral LLMToolDefinition."""
        return LLMToolDefinition(
            name=self._name,
            description=self._description,
            parameters=self._parameters,
        )

    def __repr__(self) -> str:
        return f"Tool(name={self._name!r}, description={self._description!r})"
