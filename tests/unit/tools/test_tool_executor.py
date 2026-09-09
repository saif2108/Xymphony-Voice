"""Unit tests for ToolExecutor boundary, execution, error containment, and cancellation."""

from __future__ import annotations

import asyncio

import pytest

from xymphony_contracts.llm import LLMToolCall
from xymphony_contracts.tools import ToolErrorCode, ToolResult
from xymphony_runtime.cancellation import EventCancellationToken
from xymphony_tools.domain import Tool, ToolExecutionContext
from xymphony_tools.executor import ToolExecutor
from xymphony_tools.registry import ToolRegistry


class TestToolExecutorSyncAndAsync:
    @pytest.mark.asyncio
    async def test_execute_sync_tool(self) -> None:
        def sync_add(a: int, b: int) -> int:
            return a + b

        registry = ToolRegistry()
        registry.register(
            Tool(
                name="add",
                description="Add two numbers",
                parameters={
                    "type": "object",
                    "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
                    "required": ["a", "b"],
                },
                handler=sync_add,
            )
        )

        executor = ToolExecutor(registry)
        tool_call = LLMToolCall(id="call_1", name="add", arguments='{"a": 10, "b": 25}')

        result = await executor.execute(tool_call)

        assert isinstance(result, ToolResult)
        assert result.tool_call_id == "call_1"
        assert result.tool_name == "add"
        assert result.success is True
        assert result.output == "35"
        assert result.result == 35
        assert result.error is None
        assert result.error_code is None

    @pytest.mark.asyncio
    async def test_execute_async_tool(self) -> None:
        async def async_fetch_weather(city: str) -> dict[str, object]:
            await asyncio.sleep(0.01)
            return {"city": city, "temp_c": 22}

        registry = ToolRegistry()
        registry.register(
            Tool(
                name="get_weather",
                description="Get weather",
                parameters={
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                    "required": ["city"],
                },
                handler=async_fetch_weather,
            )
        )

        executor = ToolExecutor(registry)
        tool_call = LLMToolCall(
            id="call_weather_1",
            name="get_weather",
            arguments='{"city": "Tokyo"}',
        )

        result = await executor.execute(tool_call)

        assert result.success is True
        assert result.tool_call_id == "call_weather_1"
        assert result.tool_name == "get_weather"
        assert result.result == {"city": "Tokyo", "temp_c": 22}
        assert '"city": "Tokyo"' in result.output
        assert '"temp_c": 22' in result.output


class TestToolExecutorArgumentHandling:
    @pytest.mark.asyncio
    async def test_empty_arguments_string_treated_as_empty_dict(self) -> None:
        called = False

        def no_args_tool() -> str:
            nonlocal called
            called = True
            return "ok"

        registry = ToolRegistry()
        registry.register(Tool(name="ping", handler=no_args_tool))
        executor = ToolExecutor(registry)

        tool_call = LLMToolCall(id="call_p", name="ping", arguments="")
        result = await executor.execute(tool_call)

        assert called is True
        assert result.success is True
        assert result.output == "ok"

    @pytest.mark.asyncio
    async def test_malformed_json_arguments_fails_without_executing(self) -> None:
        called = False

        def my_tool(x: int) -> int:
            nonlocal called
            called = True
            return x

        registry = ToolRegistry()
        registry.register(
            Tool(
                name="test_tool",
                parameters={"properties": {"x": {"type": "integer"}}},
                handler=my_tool,
            )
        )
        executor = ToolExecutor(registry)

        tool_call = LLMToolCall(id="call_bad", name="test_tool", arguments='{not json}')
        result = await executor.execute(tool_call)

        assert called is False
        assert result.success is False
        assert result.error_code == ToolErrorCode.INVALID_ARGUMENTS
        assert "Malformed JSON" in str(result.error)

    @pytest.mark.asyncio
    async def test_non_dict_json_fails_without_executing(self) -> None:
        called = False

        def my_tool() -> str:
            nonlocal called
            called = True
            return "done"

        registry = ToolRegistry()
        registry.register(Tool(name="test_tool", handler=my_tool))
        executor = ToolExecutor(registry)

        tool_call = LLMToolCall(id="call_list", name="test_tool", arguments='[1, 2, 3]')
        result = await executor.execute(tool_call)

        assert called is False
        assert result.success is False
        assert result.error_code == ToolErrorCode.INVALID_ARGUMENTS
        assert "must be a JSON object" in str(result.error)

    @pytest.mark.asyncio
    async def test_missing_required_argument_fails_before_execution(self) -> None:
        called = False

        def my_tool(req: str) -> str:
            nonlocal called
            called = True
            return req

        registry = ToolRegistry()
        registry.register(
            Tool(
                name="test_tool",
                parameters={
                    "type": "object",
                    "properties": {"req": {"type": "string"}},
                    "required": ["req"],
                },
                handler=my_tool,
            )
        )
        executor = ToolExecutor(registry)

        tool_call = LLMToolCall(id="call_missing", name="test_tool", arguments='{}')
        result = await executor.execute(tool_call)

        assert called is False
        assert result.success is False
        assert result.error_code == ToolErrorCode.VALIDATION_FAILED
        assert "Missing required argument 'req'" in str(result.error)

    @pytest.mark.asyncio
    async def test_invalid_argument_type_fails_before_execution(self) -> None:
        called = False

        def my_tool(count: int) -> int:
            nonlocal called
            called = True
            return count

        registry = ToolRegistry()
        registry.register(
            Tool(
                name="counter",
                parameters={
                    "type": "object",
                    "properties": {"count": {"type": "integer"}},
                    "required": ["count"],
                },
                handler=my_tool,
            )
        )
        executor = ToolExecutor(registry)

        # Pass string instead of int
        tool_call = LLMToolCall(id="call_type", name="counter", arguments='{"count": "five"}')
        result = await executor.execute(tool_call)

        assert called is False
        assert result.success is False
        assert result.error_code == ToolErrorCode.VALIDATION_FAILED
        assert "expected type 'integer'" in str(result.error)


class TestToolExecutorErrorsAndContainment:
    @pytest.mark.asyncio
    async def test_unknown_tool_returns_tool_not_found(self) -> None:
        registry = ToolRegistry()
        executor = ToolExecutor(registry)

        tool_call = LLMToolCall(id="call_unk", name="unregistered_tool", arguments='{}')
        result = await executor.execute(tool_call)

        assert result.success is False
        assert result.error_code == ToolErrorCode.TOOL_NOT_FOUND
        assert "not registered" in str(result.error)

    @pytest.mark.asyncio
    async def test_sync_handler_exception_contained(self) -> None:
        def failing_tool() -> None:
            raise ZeroDivisionError("division by zero in tool")

        registry = ToolRegistry()
        registry.register(Tool(name="divide", handler=failing_tool))
        executor = ToolExecutor(registry)

        tool_call = LLMToolCall(id="call_div", name="divide", arguments='{}')
        result = await executor.execute(tool_call)

        assert result.success is False
        assert result.error_code == ToolErrorCode.EXECUTION_FAILED
        assert "ZeroDivisionError" in str(result.error)
        assert "division by zero in tool" in str(result.error)

    @pytest.mark.asyncio
    async def test_async_handler_exception_contained(self) -> None:
        async def failing_async_tool() -> None:
            await asyncio.sleep(0.01)
            raise ConnectionResetError("network connection reset")

        registry = ToolRegistry()
        registry.register(Tool(name="fetch", handler=failing_async_tool))
        executor = ToolExecutor(registry)

        tool_call = LLMToolCall(id="call_fetch", name="fetch", arguments='{}')
        result = await executor.execute(tool_call)

        assert result.success is False
        assert result.error_code == ToolErrorCode.EXECUTION_FAILED
        assert "ConnectionResetError" in str(result.error)
        assert "network connection reset" in str(result.error)


class TestToolExecutorCancellation:
    @pytest.mark.asyncio
    async def test_pre_execution_cancellation(self) -> None:
        called = False

        def my_tool() -> str:
            nonlocal called
            called = True
            return "done"

        registry = ToolRegistry()
        registry.register(Tool(name="task", handler=my_tool))
        executor = ToolExecutor(registry)

        cancel = EventCancellationToken()
        cancel.cancel()

        tool_call = LLMToolCall(id="call_cancel", name="task", arguments='{}')
        result = await executor.execute(tool_call, cancel=cancel)

        assert called is False
        assert result.success is False
        assert result.error_code == ToolErrorCode.CANCELLED
        assert "cancelled before start" in str(result.error)

    @pytest.mark.asyncio
    async def test_post_execution_cancellation_during_async(self) -> None:
        async def slow_tool(cancel: EventCancellationToken) -> str:
            cancel.cancel()
            await asyncio.sleep(0.01)
            return "slow result"

        registry = ToolRegistry()
        registry.register(Tool(name="slow", handler=slow_tool))
        executor = ToolExecutor(registry)

        cancel = EventCancellationToken()
        tool_call = LLMToolCall(id="call_slow", name="slow", arguments='{}')

        result = await executor.execute(tool_call, cancel=cancel)

        assert result.success is False
        assert result.error_code == ToolErrorCode.CANCELLED


class TestToolExecutorContextInjection:
    @pytest.mark.asyncio
    async def test_context_passed_to_handler_when_requested(self) -> None:
        received_ctx: ToolExecutionContext | None = None

        def context_aware_tool(user_name: str, context: ToolExecutionContext) -> str:
            nonlocal received_ctx
            received_ctx = context
            return f"Hello {user_name}, call {context.tool_call_id}"

        registry = ToolRegistry()
        registry.register(
            Tool(
                name="greet",
                parameters={
                    "type": "object",
                    "properties": {"user_name": {"type": "string"}},
                    "required": ["user_name"],
                },
                handler=context_aware_tool,
            )
        )
        executor = ToolExecutor(registry)

        ctx = ToolExecutionContext(tool_call_id="call_ctx_99", session_id="sess_abc")
        tool_call = LLMToolCall(
            id="call_ctx_99",
            name="greet",
            arguments='{"user_name": "Antigravity"}',
        )

        result = await executor.execute(tool_call, context=ctx)

        assert result.success is True
        assert received_ctx is ctx
        assert received_ctx.tool_call_id == "call_ctx_99"
        assert result.output == "Hello Antigravity, call call_ctx_99"


class TestToolSubsystemIsolation:
    def test_no_vendor_sdk_imports_in_tools_package(self) -> None:
        import sys

        import xymphony_tools

        assert xymphony_tools is not None
        tool_pkg_modules = [m for m in sys.modules if m.startswith("xymphony_tools")]
        for mod_name in tool_pkg_modules:
            mod = sys.modules[mod_name]
            file_path = getattr(mod, "__file__", None)
            if file_path:
                with open(file_path, encoding="utf-8") as f:
                    content = f.read()
                assert "openai" not in content
                assert "anthropic" not in content
                assert "gemini" not in content
                assert "livekit" not in content
