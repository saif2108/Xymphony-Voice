"""Provider-neutral tool domain and execution errors."""

from __future__ import annotations

__all__ = [
    "ToolAlreadyRegisteredError",
    "ToolArgumentError",
    "ToolArgumentValidationError",
    "ToolError",
    "ToolExecutionError",
    "ToolNotFoundError",
]


class ToolError(Exception):
    """Base error for the tool domain and execution subsystem."""


class ToolNotFoundError(ToolError):
    """Raised when a requested tool name is not found in the registry."""

    def __init__(self, name: str) -> None:
        super().__init__(f"Tool '{name}' is not registered.")
        self.name = name


class ToolAlreadyRegisteredError(ToolError):
    """Raised when attempting to register a tool with an existing name."""

    def __init__(self, name: str) -> None:
        super().__init__(f"Tool '{name}' is already registered.")
        self.name = name


class ToolArgumentError(ToolError):
    """Raised when raw tool arguments cannot be parsed as JSON or are not a JSON object."""


class ToolArgumentValidationError(ToolError):
    """Raised when tool arguments fail parameter schema validation."""


class ToolExecutionError(ToolError):
    """Raised when a tool handler encounters an unhandled exception during execution."""

    def __init__(self, name: str, original_error: Exception) -> None:
        err_type = type(original_error).__name__
        super().__init__(f"Tool '{name}' execution failed: {err_type}: {original_error}")
        self.name = name
        self.original_error = original_error
