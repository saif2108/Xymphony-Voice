"""Safe AST-based arithmetic calculator tool."""

from __future__ import annotations

import ast
import operator
from typing import Any

from xymphony_tools.domain import Tool

_OPERATORS = {
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

_MAX_EXPONENT = 1000


def _safe_eval_node(node: ast.AST) -> float | int:
    if isinstance(node, ast.Expression):
        return _safe_eval_node(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        raise ValueError(f"Unsupported constant type: {type(node.value).__name__}")
    if isinstance(node, ast.UnaryOp):
        op_func = _OPERATORS.get(type(node.op))
        if op_func is None:
            raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
        operand = _safe_eval_node(node.operand)
        return op_func(operand)  # type: ignore[operator]
    if isinstance(node, ast.BinOp):
        op_func = _OPERATORS.get(type(node.op))
        if op_func is None:
            raise ValueError(f"Unsupported binary operator: {type(node.op).__name__}")
        left = _safe_eval_node(node.left)
        right = _safe_eval_node(node.right)

        if isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)) and right == 0:
            raise ValueError("Division by zero")

        if isinstance(node.op, ast.Pow):
            if isinstance(right, (int, float)) and right > _MAX_EXPONENT:
                raise ValueError(f"Exponent exceeds maximum allowed limit ({_MAX_EXPONENT})")

        return op_func(left, right)  # type: ignore[operator]

    raise ValueError(f"Unsupported expression element: {type(node).__name__}")


def calculate(expression: str) -> dict[str, Any]:
    """Safely evaluate a mathematical arithmetic expression."""
    clean_expr = expression.strip()
    if not clean_expr:
        raise ValueError("Expression cannot be empty")
    try:
        tree = ast.parse(clean_expr, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"Invalid arithmetic expression: {clean_expr}") from exc

    result = _safe_eval_node(tree)
    # Convert float like 4.0 to int 4 if integer
    if isinstance(result, float) and result.is_integer():
        result = int(result)
    return {
        "expression": clean_expr,
        "result": result,
    }


def create_calculator_tool() -> Tool:
    """Create a configured Tool instance for the calculator."""
    return Tool(
        name="calculator",
        description="Safely evaluates a mathematical arithmetic expression and returns the result.",
        parameters={
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "The arithmetic expression to evaluate (e.g., '14 * 6 + 5').",
                }
            },
            "required": ["expression"],
            "additionalProperties": False,
        },
        handler=calculate,
    )
