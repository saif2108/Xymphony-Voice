"""Built-in deterministic tool handlers for Xymphony Voice."""

from xymphony_tools.handlers.calculator import (
    calculate,
    create_calculator_tool,
)
from xymphony_tools.handlers.catalog import (
    get_builtin_tools,
    register_builtin_tools,
)
from xymphony_tools.handlers.customer_lookup import (
    create_customer_lookup_tool,
    lookup_customer,
)
from xymphony_tools.handlers.weather_lookup import (
    create_weather_lookup_tool,
    lookup_weather,
)

__all__ = [
    "calculate",
    "create_calculator_tool",
    "create_customer_lookup_tool",
    "create_weather_lookup_tool",
    "get_builtin_tools",
    "lookup_customer",
    "lookup_weather",
    "register_builtin_tools",
]
