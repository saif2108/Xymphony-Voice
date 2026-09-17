from __future__ import annotations

import logging
from collections.abc import Sequence

from xymphony_contracts import AgentToolBinding
from xymphony_contracts.llm import LLMToolDefinition
from xymphony_tools.domain import Tool
from xymphony_tools.errors import ToolAlreadyRegisteredError, ToolNotFoundError

logger = logging.getLogger(__name__)

__all__ = [
    "ToolRegistry",
    "build_agent_tool_registry",
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

    def create_restricted(
        self,
        bindings: Sequence[AgentToolBinding],
        *,
        strict: bool = True,
    ) -> ToolRegistry:
        """Create an agent-specific restricted ToolRegistry from tool bindings."""
        return build_agent_tool_registry(self, bindings, strict=strict)


def build_agent_tool_registry(
    catalog: ToolRegistry,
    tool_bindings: Sequence[AgentToolBinding],
    *,
    strict: bool = True,
) -> ToolRegistry:
    """Build an agent-specific restricted ToolRegistry from persisted tool bindings.

    - Disabled bindings (enabled=False) are excluded.
    - Resolves tools only from the provided approved tool registry (catalog).
    - If strict=True (default), raises ToolNotFoundError if an enabled tool binding is not in
      catalog.
    - If strict=False, logs a warning and skips unknown tools.
    - Disabled or unconfigured tools in the catalog are never registered in the resulting registry.
    """
    agent_registry = ToolRegistry()
    for binding in tool_bindings:
        if not binding.enabled:
            continue
        tool = catalog.get(binding.tool_name)
        if tool is None:
            if strict:
                raise ToolNotFoundError(binding.tool_name)
            logger.warning(
                "agent_tool_unresolved",
                extra={"tool_name": binding.tool_name},
            )
            continue
        agent_registry.register(tool)

    return agent_registry


