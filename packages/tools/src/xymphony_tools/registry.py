"""Provider-neutral tool registry."""

from __future__ import annotations

from xymphony_contracts.llm import LLMToolDefinition
from xymphony_tools.domain import Tool
from xymphony_tools.errors import ToolAlreadyRegisteredError

__all__ = [
    "ToolRegistry",
]


class ToolRegistry:
    """Registry maintaining registered tools and exposing definitions deterministically."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool.

        Raises ToolAlreadyRegisteredError if a tool with the same name exists.
        """
        if tool.name in self._tools:
            raise ToolAlreadyRegisteredError(tool.name)
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        """Look up a tool by stable name, returning None if not found."""
        return self._tools.get(name)

    def has(self, name: str) -> bool:
        """Return True if a tool with the given name is registered."""
        return name in self._tools

    def unregister(self, name: str) -> bool:
        """Unregister a tool by name. Returns True if removed, False if not found."""
        if name in self._tools:
            del self._tools[name]
            return True
        return False

    def list_tools(self) -> tuple[Tool, ...]:
        """Return all registered tools, sorted deterministically by name."""
        return tuple(self._tools[name] for name in sorted(self._tools))

    def get_definitions(self) -> tuple[LLMToolDefinition, ...]:
        """Expose all tool definitions sorted deterministically by name for LLM requests."""
        return tuple(self._tools[name].to_definition() for name in sorted(self._tools))

    def __contains__(self, name: str) -> bool:
        return self.has(name)

    def __len__(self) -> int:
        return len(self._tools)
