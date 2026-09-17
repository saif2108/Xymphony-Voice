"""Provider-neutral tool domain, registry, and execution subsystem for Xymphony Voice."""

from xymphony_contracts.tools import ToolErrorCode, ToolResult
from xymphony_tools.builtins import (
    CALCULATOR_PARAMETERS,
    CURRENT_TIME_PARAMETERS,
    TEXT_STATS_PARAMETERS,
    calculate_handler,
    create_builtin_tools,
    create_calculator_tool,
    create_current_time_tool,
    create_default_tool_registry,
    create_text_stats_tool,
    current_time_handler,
    text_stats_handler,
)
from xymphony_tools.domain import Tool, ToolExecutionContext, ToolHandler
from xymphony_tools.errors import (
    ToolAlreadyRegisteredError,
    ToolArgumentError,
    ToolArgumentValidationError,
    ToolError,
    ToolExecutionError,
    ToolNotFoundError,
)
from xymphony_tools.executor import ToolExecutor
from xymphony_tools.registry import (
    ToolRegistry,
    build_agent_tool_registry,
)
from xymphony_tools.validation import validate_tool_arguments

__all__ = [
    "CALCULATOR_PARAMETERS",
    "CURRENT_TIME_PARAMETERS",
    "TEXT_STATS_PARAMETERS",
    "Tool",
    "ToolAlreadyRegisteredError",
    "ToolArgumentError",
    "ToolArgumentValidationError",
    "ToolErrorCode",
    "ToolError",
    "ToolExecutionContext",
    "ToolExecutionError",
    "ToolExecutor",
    "ToolHandler",
    "ToolNotFoundError",
    "ToolRegistry",
    "ToolResult",
    "build_agent_tool_registry",
    "calculate_handler",
    "create_builtin_tools",
    "create_calculator_tool",
    "create_current_time_tool",
    "create_default_tool_registry",
    "create_text_stats_tool",
    "current_time_handler",
    "text_stats_handler",
    "validate_tool_arguments",
]
