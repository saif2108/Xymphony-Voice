"""Built-in tool catalog and registration helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xymphony_tools.handlers.calculator import create_calculator_tool
from xymphony_tools.handlers.customer_lookup import create_customer_lookup_tool
from xymphony_tools.handlers.weather_lookup import create_weather_lookup_tool

if TYPE_CHECKING:
    from xymphony_tools.domain import Tool
    from xymphony_tools.registry import ToolRegistry


def get_builtin_tools() -> list[Tool]:
    """Return instances of all standard built-in deterministic tools."""
    return [
        create_calculator_tool(),
        create_customer_lookup_tool(),
        create_weather_lookup_tool(),
    ]


def register_builtin_tools(registry: ToolRegistry) -> None:
    """Register all standard built-in tools into a ToolRegistry."""
    for tool in get_builtin_tools():
        registry.register(tool)
