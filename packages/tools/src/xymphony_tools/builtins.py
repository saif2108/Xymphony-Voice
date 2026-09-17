"""Built-in deterministic tools for Xymphony Voice."""

from __future__ import annotations

import ast
import operator
import zoneinfo
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from pydantic import JsonValue

from xymphony_tools.domain import Tool
from xymphony_tools.registry import ToolRegistry

__all__ = [
    "CALCULATOR_PARAMETERS",
    "CURRENT_TIME_PARAMETERS",
    "TEXT_STATS_PARAMETERS",
    "calculate_handler",
    "create_builtin_tools",
    "create_calculator_tool",
    "create_current_time_tool",
    "create_default_tool_registry",
    "create_text_stats_tool",
    "current_time_handler",
    "text_stats_handler",
]

_SAFE_OPERATORS: dict[type[ast.AST], Callable[..., Any]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

_MAX_EXPRESSION_LENGTH = 256
_MAX_EXPONENT = 1000
_MAX_ABS_VALUE = 1e100


def _evaluate_ast_node(node: ast.AST) -> int | float:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            msg = f"Unsupported constant type: {type(node.value).__name__}"
            raise ValueError(msg)
        return node.value

    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _SAFE_OPERATORS:
            msg = f"Unsupported unary operator: {op_type.__name__}"
            raise ValueError(msg)
        operand = _evaluate_ast_node(node.operand)
        return _SAFE_OPERATORS[op_type](operand)

    if isinstance(node, ast.BinOp):
        bin_op_type = type(node.op)
        if bin_op_type not in _SAFE_OPERATORS:
            msg = f"Unsupported binary operator: {bin_op_type.__name__}"
            raise ValueError(msg)
        left = _evaluate_ast_node(node.left)
        right = _evaluate_ast_node(node.right)

        if bin_op_type in (ast.Div, ast.FloorDiv, ast.Mod) and right == 0:
            msg = "Division by zero"
            raise ValueError(msg)

        if bin_op_type is ast.Pow:
            if abs(right) > _MAX_EXPONENT:
                msg = f"Exponent exceeds maximum allowed limit of {_MAX_EXPONENT}"
                raise ValueError(msg)
            if abs(left) > 1 and right > 500:
                msg = "Calculation result exceeds maximum allowed magnitude"
                raise ValueError(msg)

        res = _SAFE_OPERATORS[bin_op_type](left, right)
        if isinstance(res, complex) or abs(res) > _MAX_ABS_VALUE:
            msg = "Calculation result exceeds maximum allowed magnitude"
            raise ValueError(msg)
        return res

    msg = f"Unsupported expression syntax: {type(node).__name__}"
    raise ValueError(msg)


def calculate_handler(expression: str) -> int | float:
    """Safely evaluate a mathematical expression without eval()."""
    if not isinstance(expression, str):
        msg = f"Expression must be a string, got {type(expression).__name__}"
        raise ValueError(msg)
    cleaned = expression.strip()
    if not cleaned:
        msg = "Expression cannot be empty"
        raise ValueError(msg)
    if len(cleaned) > _MAX_EXPRESSION_LENGTH:
        msg = f"Expression exceeds maximum length of {_MAX_EXPRESSION_LENGTH} characters"
        raise ValueError(msg)

    try:
        tree = ast.parse(cleaned, mode="eval")
    except SyntaxError as exc:
        msg = f"Invalid mathematical syntax: {exc}"
        raise ValueError(msg) from exc

    return _evaluate_ast_node(tree.body)


def current_time_handler(
    timezone: str = "UTC",
    *,
    now_factory: Callable[[], datetime] | None = None,
) -> dict[str, str]:
    """Return the current date, time, and timezone information."""
    if not isinstance(timezone, str) or not timezone.strip():
        msg = "Timezone must be a non-empty string"
        raise ValueError(msg)
    tz_str = timezone.strip()
    try:
        tz = zoneinfo.ZoneInfo(tz_str)
    except (zoneinfo.ZoneInfoNotFoundError, KeyError, ValueError) as exc:
        msg = f"Unknown or invalid timezone: '{tz_str}'"
        raise ValueError(msg) from exc

    if now_factory is not None:
        base_now = now_factory()
        if base_now.tzinfo is None:
            base_now = base_now.replace(tzinfo=UTC)
        now = base_now.astimezone(tz)
    else:
        now = datetime.now(tz)

    return {
        "iso": now.isoformat(),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "timezone": tz_str,
        "day_of_week": now.strftime("%A"),
    }


def text_stats_handler(text: str) -> dict[str, int]:
    """Compute length, word count, and line count statistics for text."""
    if not isinstance(text, str):
        msg = f"Expected text to be a string, got {type(text).__name__}"
        raise ValueError(msg)
    words = text.split()
    lines = text.splitlines()
    return {
        "character_count": len(text),
        "character_count_no_spaces": len("".join(words)),
        "word_count": len(words),
        "line_count": len(lines) if text else 0,
    }


CALCULATOR_PARAMETERS: dict[str, JsonValue] = {
    "type": "object",
    "properties": {
        "expression": {
            "type": "string",
            "description": "Mathematical expression to evaluate, e.g. '(15 * 4) + 2'.",
        },
    },
    "required": ["expression"],
    "additionalProperties": False,
}

CURRENT_TIME_PARAMETERS: dict[str, JsonValue] = {
    "type": "object",
    "properties": {
        "timezone": {
            "type": "string",
            "description": (
                "Optional IANA timezone name (e.g. 'UTC', 'America/New_York'). Defaults to 'UTC'."
            ),
        },
    },
    "additionalProperties": False,
}

TEXT_STATS_PARAMETERS: dict[str, JsonValue] = {
    "type": "object",
    "properties": {
        "text": {
            "type": "string",
            "description": "Text to analyze for statistics.",
        },
    },
    "required": ["text"],
    "additionalProperties": False,
}


def create_calculator_tool() -> Tool:
    """Create the built-in deterministic calculator tool."""
    return Tool(
        name="calculate",
        description=(
            "Evaluate a mathematical expression deterministically. "
            "Supports +, -, *, /, %, ** and parentheses."
        ),
        parameters=CALCULATOR_PARAMETERS,
        handler=calculate_handler,
    )


def create_current_time_tool(
    *,
    now_factory: Callable[[], datetime] | None = None,
) -> Tool:
    """Create the built-in deterministic current time tool."""

    def _handler(timezone: str = "UTC") -> dict[str, str]:
        return current_time_handler(timezone=timezone, now_factory=now_factory)

    return Tool(
        name="get_current_time",
        description="Get the current date and time. Optionally specify an IANA timezone name.",
        parameters=CURRENT_TIME_PARAMETERS,
        handler=_handler,
    )


def create_text_stats_tool() -> Tool:
    """Create the built-in deterministic text analysis tool."""
    return Tool(
        name="text_stats",
        description="Compute text statistics including character count, word count, and lines.",
        parameters=TEXT_STATS_PARAMETERS,
        handler=text_stats_handler,
    )


def create_builtin_tools(
    *,
    now_factory: Callable[[], datetime] | None = None,
) -> tuple[Tool, ...]:
    """Create all built-in deterministic tools."""
    return (
        create_calculator_tool(),
        create_current_time_tool(now_factory=now_factory),
        create_text_stats_tool(),
    )


def create_default_tool_registry(
    *,
    now_factory: Callable[[], datetime] | None = None,
) -> ToolRegistry:
    """Create a ToolRegistry pre-populated with all built-in deterministic tools."""
    registry = ToolRegistry()
    for tool in create_builtin_tools(now_factory=now_factory):
        registry.register(tool)
    return registry
