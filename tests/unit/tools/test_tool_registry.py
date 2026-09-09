"""Unit tests for ToolRegistry."""

from __future__ import annotations

import pytest

from xymphony_contracts.llm import LLMToolDefinition
from xymphony_tools.domain import Tool
from xymphony_tools.errors import ToolAlreadyRegisteredError
from xymphony_tools.registry import ToolRegistry


def _dummy_tool(name: str, description: str = "") -> Tool:
    return Tool(
        name=name,
        description=description or f"Description for {name}",
        parameters={"type": "object", "properties": {}},
        handler=lambda: f"result from {name}",
    )


class TestToolRegistry:
    def test_register_and_lookup_single_tool(self) -> None:
        registry = ToolRegistry()
        tool = _dummy_tool("weather")

        registry.register(tool)

        assert registry.has("weather")
        assert "weather" in registry
        assert len(registry) == 1
        assert registry.get("weather") is tool

    def test_lookup_missing_tool_returns_none(self) -> None:
        registry = ToolRegistry()
        assert registry.get("nonexistent") is None
        assert not registry.has("nonexistent")
        assert "nonexistent" not in registry

    def test_duplicate_registration_fails(self) -> None:
        registry = ToolRegistry()
        tool1 = _dummy_tool("search")
        tool2 = _dummy_tool("search")

        registry.register(tool1)

        with pytest.raises(ToolAlreadyRegisteredError) as exc_info:
            registry.register(tool2)

        assert exc_info.value.name == "search"
        assert "already registered" in str(exc_info.value)
        # Original remains registered
        assert registry.get("search") is tool1

    def test_unregister(self) -> None:
        registry = ToolRegistry()
        tool = _dummy_tool("calc")

        registry.register(tool)
        assert registry.has("calc")

        assert registry.unregister("calc") is True
        assert not registry.has("calc")
        assert registry.get("calc") is None
        assert registry.unregister("calc") is False

    def test_list_tools_deterministic_order(self) -> None:
        registry = ToolRegistry()
        # Register in reverse alphabetical order
        registry.register(_dummy_tool("zebra"))
        registry.register(_dummy_tool("apple"))
        registry.register(_dummy_tool("mango"))

        tools = registry.list_tools()
        assert [t.name for t in tools] == ["apple", "mango", "zebra"]

    def test_get_definitions_deterministic_order(self) -> None:
        registry = ToolRegistry()
        registry.register(_dummy_tool("zebra", "Zebra tool"))
        registry.register(_dummy_tool("apple", "Apple tool"))

        defs = registry.get_definitions()
        assert len(defs) == 2
        assert isinstance(defs[0], LLMToolDefinition)
        assert isinstance(defs[1], LLMToolDefinition)
        assert defs[0].name == "apple"
        assert defs[1].name == "zebra"
