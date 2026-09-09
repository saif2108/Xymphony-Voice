"""Provider-neutral tool execution contracts. No vendor SDKs."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, JsonValue

__all__ = [
    "ToolErrorCode",
    "ToolResult",
]


class ToolErrorCode(StrEnum):
    TOOL_NOT_FOUND = "tool_not_found"
    INVALID_ARGUMENTS = "invalid_arguments"
    VALIDATION_FAILED = "validation_failed"
    EXECUTION_FAILED = "execution_failed"
    CANCELLED = "cancelled"


class ToolResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tool_call_id: str = Field(min_length=1, max_length=128)
    tool_name: str = Field(min_length=1, max_length=128)
    success: bool
    output: str = Field(default="", max_length=32_000)
    result: JsonValue | None = None
    error: str | None = Field(default=None, max_length=4000)
    error_code: ToolErrorCode | None = None

    @classmethod
    def success_result(
        cls,
        *,
        tool_call_id: str,
        tool_name: str,
        output: str,
        result: JsonValue | None = None,
    ) -> ToolResult:
        return cls(
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            success=True,
            output=output,
            result=result,
            error=None,
            error_code=None,
        )

    @classmethod
    def failure_result(
        cls,
        *,
        tool_call_id: str,
        tool_name: str,
        error: str,
        error_code: ToolErrorCode,
        output: str | None = None,
    ) -> ToolResult:
        return cls(
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            success=False,
            output=output if output is not None else f"Error: {error}",
            result=None,
            error=error,
            error_code=error_code,
        )
