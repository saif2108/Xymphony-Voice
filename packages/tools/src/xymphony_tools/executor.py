"""Deterministic tool execution boundary. No vendor SDKs."""

from __future__ import annotations

import inspect
import json
from typing import Any

from pydantic import JsonValue

from xymphony_contracts.llm import CancellationToken, LLMToolCall
from xymphony_contracts.tools import ToolErrorCode, ToolResult
from xymphony_tools.domain import ToolExecutionContext
from xymphony_tools.errors import ToolArgumentValidationError
from xymphony_tools.registry import ToolRegistry
from xymphony_tools.validation import validate_tool_arguments

__all__ = [
    "ToolExecutor",
]


class ToolExecutor:
    """Executes tool calls deterministically against registered tools."""

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    @property
    def registry(self) -> ToolRegistry:
        return self._registry

    async def execute(
        self,
        tool_call: LLMToolCall,
        *,
        context: ToolExecutionContext | None = None,
        cancel: CancellationToken | None = None,
    ) -> ToolResult:
        """Execute a tool call and return a normalized ToolResult.

        All execution errors, invalid arguments, schema violations, and cancellation
        are normalized into ToolResult failures and never leak raw exceptions.
        """
        # 1. Pre-execution cancellation check
        if cancel is not None and cancel.cancelled:
            return ToolResult.failure_result(
                tool_call_id=tool_call.id,
                tool_name=tool_call.name,
                error="Tool execution was cancelled before start.",
                error_code=ToolErrorCode.CANCELLED,
            )

        # 2. Tool resolution
        tool = self._registry.get(tool_call.name)
        if tool is None:
            return ToolResult.failure_result(
                tool_call_id=tool_call.id,
                tool_name=tool_call.name,
                error=f"Tool '{tool_call.name}' is not registered.",
                error_code=ToolErrorCode.TOOL_NOT_FOUND,
            )

        # 3. Argument JSON parsing
        raw_args_str = tool_call.arguments.strip()
        parsed_args: dict[str, Any]
        if not raw_args_str:
            parsed_args = {}
        else:
            try:
                parsed_val = json.loads(raw_args_str)
            except json.JSONDecodeError as exc:
                return ToolResult.failure_result(
                    tool_call_id=tool_call.id,
                    tool_name=tool_call.name,
                    error=f"Malformed JSON arguments: {exc}",
                    error_code=ToolErrorCode.INVALID_ARGUMENTS,
                )

            if not isinstance(parsed_val, dict):
                return ToolResult.failure_result(
                    tool_call_id=tool_call.id,
                    tool_name=tool_call.name,
                    error=f"Tool arguments must be a JSON object, got {type(parsed_val).__name__}.",
                    error_code=ToolErrorCode.INVALID_ARGUMENTS,
                )
            parsed_args = parsed_val

        # 4. Parameter schema validation (BEFORE execution)
        try:
            validate_tool_arguments(tool.parameters, parsed_args)
        except ToolArgumentValidationError as exc:
            return ToolResult.failure_result(
                tool_call_id=tool_call.id,
                tool_name=tool_call.name,
                error=str(exc),
                error_code=ToolErrorCode.VALIDATION_FAILED,
            )

        # 5. Pre-invocation cancellation check
        if cancel is not None and cancel.cancelled:
            return ToolResult.failure_result(
                tool_call_id=tool_call.id,
                tool_name=tool_call.name,
                error="Tool execution was cancelled.",
                error_code=ToolErrorCode.CANCELLED,
            )

        # 6. Prepare invocation kwargs
        kwargs = dict(parsed_args)
        try:
            sig = inspect.signature(tool.handler)
            param_names = set(sig.parameters.keys())
            has_var_keyword = any(
                p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
            )

            if context is not None and ("context" in param_names or has_var_keyword):
                if "context" not in kwargs:
                    kwargs["context"] = context

            if cancel is not None and ("cancel" in param_names or has_var_keyword):
                if "cancel" not in kwargs:
                    kwargs["cancel"] = cancel
        except (ValueError, TypeError):
            pass

        # 7. Execution (sync or async)
        try:
            if inspect.iscoroutinefunction(tool.handler):
                raw_output = await tool.handler(**kwargs)
            else:
                raw_output = tool.handler(**kwargs)
        except Exception as exc:
            return ToolResult.failure_result(
                tool_call_id=tool_call.id,
                tool_name=tool_call.name,
                error=f"{type(exc).__name__}: {exc}",
                error_code=ToolErrorCode.EXECUTION_FAILED,
            )

        # 8. Post-invocation cancellation check
        if cancel is not None and cancel.cancelled:
            return ToolResult.failure_result(
                tool_call_id=tool_call.id,
                tool_name=tool_call.name,
                error="Tool execution was cancelled.",
                error_code=ToolErrorCode.CANCELLED,
            )

        # 9. Normalize successful result
        output_str: str
        structured_result: JsonValue | None = None

        if raw_output is None:
            output_str = ""
        elif isinstance(raw_output, str):
            output_str = raw_output
        elif isinstance(raw_output, (dict, list, int, float, bool)):
            try:
                output_str = json.dumps(raw_output)
                structured_result = raw_output
            except Exception:
                output_str = str(raw_output)
        else:
            output_str = str(raw_output)

        return ToolResult.success_result(
            tool_call_id=tool_call.id,
            tool_name=tool_call.name,
            output=output_str,
            result=structured_result,
        )
