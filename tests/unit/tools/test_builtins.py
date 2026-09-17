"""Unit tests for built-in deterministic tools (Phase 4 Step 5)."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from xymphony_contracts import AgentToolBinding
from xymphony_contracts.llm import LLMToolCall, LLMToolDefinition
from xymphony_contracts.tools import ToolErrorCode, ToolResult
from xymphony_runtime.cancellation import EventCancellationToken
from xymphony_tools import (
    ToolAlreadyRegisteredError,
    ToolRegistry,
    build_agent_tool_registry,
    calculate_handler,
    create_builtin_tools,
    create_calculator_tool,
    create_current_time_tool,
    create_default_tool_registry,
    current_time_handler,
    text_stats_handler,
)
from xymphony_tools.executor import ToolExecutor


class TestBuiltinToolRegistrationAndDiscovery:
    def test_create_builtin_tools_returns_all_tools(self) -> None:
        tools = create_builtin_tools()
        assert len(tools) == 3
        tool_names = [t.name for t in tools]
        assert "calculate" in tool_names
        assert "get_current_time" in tool_names
        assert "text_stats" in tool_names

    def test_create_default_tool_registry_populates_all_tools(self) -> None:
        registry = create_default_tool_registry()
        assert len(registry) == 3
        assert registry.has("calculate")
        assert registry.has("get_current_time")
        assert registry.has("text_stats")

    def test_deterministic_tool_discovery_order(self) -> None:
        registry = create_default_tool_registry()
        listed = registry.list_tools()
        names = [t.name for t in listed]
        assert names == ["calculate", "get_current_time", "text_stats"]

    def test_deterministic_definitions_order(self) -> None:
        registry = create_default_tool_registry()
        defs = registry.get_definitions()
        assert len(defs) == 3
        assert all(isinstance(d, LLMToolDefinition) for d in defs)
        assert [d.name for d in defs] == ["calculate", "get_current_time", "text_stats"]

    def test_duplicate_registration_raises_error(self) -> None:
        registry = create_default_tool_registry()
        calc = create_calculator_tool()
        with pytest.raises(ToolAlreadyRegisteredError) as exc_info:
            registry.register(calc)
        assert exc_info.value.name == "calculate"

    def test_build_agent_tool_registry_with_builtins(self) -> None:
        catalog = create_default_tool_registry()
        bindings = (
            AgentToolBinding(tool_name="calculate", enabled=True),
            AgentToolBinding(tool_name="text_stats", enabled=True),
            AgentToolBinding(tool_name="get_current_time", enabled=False),
        )
        restricted = build_agent_tool_registry(catalog, bindings)
        assert len(restricted) == 2
        assert restricted.has("calculate")
        assert restricted.has("text_stats")
        assert not restricted.has("get_current_time")


class TestCalculatorTool:
    @pytest.mark.parametrize(
        ("expr", "expected"),
        [
            ("2 + 2", 4),
            ("100 - 45", 55),
            ("12 * 8", 96),
            ("7 / 2", 3.5),
            ("7 // 2", 3),
            ("10 % 3", 1),
            ("2 ** 8", 256),
            ("2 + 3 * 4", 14),
            ("(2 + 3) * 4", 20),
            ("-5 + +3", -2),
            ("2.5 * 4", 10.0),
            ("(10 + 5) * (8 - 2) / 3", 30.0),
        ],
    )
    def test_calculate_handler_valid(self, expr: str, expected: int | float) -> None:
        result = calculate_handler(expr)
        assert result == expected

    @pytest.mark.asyncio
    async def test_calculate_executor_valid(self) -> None:
        registry = create_default_tool_registry()
        executor = ToolExecutor(registry)
        call = LLMToolCall(
            id="call_calc_1",
            name="calculate",
            arguments='{"expression": "(15 * 4) + 2"}',
        )
        res = await executor.execute(call)
        assert isinstance(res, ToolResult)
        assert res.success is True
        assert res.tool_name == "calculate"
        assert res.output == "62"
        assert res.result == 62
        assert res.error is None
        assert res.error_code is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("expr", "match_str"),
        [
            ("10 / 0", "Division by zero"),
            ("10 // 0", "Division by zero"),
            ("10 % 0", "Division by zero"),
            ("2 + ", "Invalid mathematical syntax"),
            ("", "Expression cannot be empty"),
            ("   ", "Expression cannot be empty"),
            ("x + 1", "Unsupported expression syntax: Name"),
            ("print('hello')", "Unsupported expression syntax: Call"),
            ("__import__('os')", "Unsupported expression syntax: Call"),
            ("2 ** 1001", "Exponent exceeds maximum allowed limit"),
            ("a" * 300, "Expression exceeds maximum length"),
        ],
    )
    async def test_calculate_error_containment(self, expr: str, match_str: str) -> None:
        registry = create_default_tool_registry()
        executor = ToolExecutor(registry)
        call = LLMToolCall(
            id="call_calc_err",
            name="calculate",
            arguments=json.dumps({"expression": expr}),
        )
        res = await executor.execute(call)
        assert res.success is False
        assert res.error_code == ToolErrorCode.EXECUTION_FAILED
        assert res.error is not None
        assert match_str in res.error

    @pytest.mark.asyncio
    async def test_calculate_missing_required_argument(self) -> None:
        registry = create_default_tool_registry()
        executor = ToolExecutor(registry)
        call = LLMToolCall(id="call_calc_miss", name="calculate", arguments="{}")
        res = await executor.execute(call)
        assert res.success is False
        assert res.error_code == ToolErrorCode.VALIDATION_FAILED
        assert "Missing required argument 'expression'" in (res.error or "")

    @pytest.mark.asyncio
    async def test_calculate_invalid_argument_type(self) -> None:
        registry = create_default_tool_registry()
        executor = ToolExecutor(registry)
        call = LLMToolCall(
            id="call_calc_type",
            name="calculate",
            arguments='{"expression": 123}',
        )
        res = await executor.execute(call)
        assert res.success is False
        assert res.error_code == ToolErrorCode.VALIDATION_FAILED
        assert "expected type 'string'" in (res.error or "")

    @pytest.mark.asyncio
    async def test_calculate_unexpected_extra_argument(self) -> None:
        registry = create_default_tool_registry()
        executor = ToolExecutor(registry)
        call = LLMToolCall(
            id="call_calc_extra",
            name="calculate",
            arguments='{"expression": "2+2", "extra": "forbidden"}',
        )
        res = await executor.execute(call)
        assert res.success is False
        assert res.error_code == ToolErrorCode.VALIDATION_FAILED
        assert "Unexpected argument 'extra'" in (res.error or "")


class TestCurrentTimeTool:
    def test_current_time_handler_utc_default(self) -> None:
        res = current_time_handler()
        assert res["timezone"] == "UTC"
        assert len(res["date"]) == 10  # YYYY-MM-DD
        assert len(res["time"]) == 8  # HH:MM:SS
        assert res["day_of_week"] in (
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        )

    def test_current_time_handler_deterministic_factory(self) -> None:
        frozen = datetime(2026, 9, 17, 14, 30, 0, tzinfo=UTC)
        res = current_time_handler("UTC", now_factory=lambda: frozen)
        assert res["date"] == "2026-09-17"
        assert res["time"] == "14:30:00"
        assert res["timezone"] == "UTC"
        assert res["day_of_week"] == "Thursday"
        assert res["iso"] == "2026-09-17T14:30:00+00:00"

    def test_current_time_handler_timezone_conversion(self) -> None:
        # 14:30 UTC = 10:30 EDT (UTC-4)
        frozen = datetime(2026, 9, 17, 14, 30, 0, tzinfo=UTC)
        res = current_time_handler("America/New_York", now_factory=lambda: frozen)
        assert res["timezone"] == "America/New_York"
        assert res["date"] == "2026-09-17"
        assert res["time"] == "10:30:00"

    @pytest.mark.asyncio
    async def test_current_time_executor_valid(self) -> None:
        frozen = datetime(2026, 9, 17, 12, 0, 0, tzinfo=UTC)
        registry = ToolRegistry()
        registry.register(create_current_time_tool(now_factory=lambda: frozen))
        executor = ToolExecutor(registry)

        call = LLMToolCall(
            id="call_time_1",
            name="get_current_time",
            arguments='{"timezone": "UTC"}',
        )
        res = await executor.execute(call)
        assert res.success is True
        assert res.tool_name == "get_current_time"
        assert isinstance(res.result, dict)
        assert res.result["date"] == "2026-09-17"
        assert res.result["time"] == "12:00:00"

    @pytest.mark.asyncio
    async def test_current_time_invalid_timezone_fails_safely(self) -> None:
        registry = create_default_tool_registry()
        executor = ToolExecutor(registry)
        call = LLMToolCall(
            id="call_time_err",
            name="get_current_time",
            arguments='{"timezone": "Invalid/Nonexistent_TZ"}',
        )
        res = await executor.execute(call)
        assert res.success is False
        assert res.error_code == ToolErrorCode.EXECUTION_FAILED
        assert "Unknown or invalid timezone" in (res.error or "")

    @pytest.mark.asyncio
    async def test_current_time_invalid_arg_type(self) -> None:
        registry = create_default_tool_registry()
        executor = ToolExecutor(registry)
        call = LLMToolCall(
            id="call_time_type",
            name="get_current_time",
            arguments='{"timezone": 123}',
        )
        res = await executor.execute(call)
        assert res.success is False
        assert res.error_code == ToolErrorCode.VALIDATION_FAILED


class TestTextStatsTool:
    def test_text_stats_handler_regular_text(self) -> None:
        text = "Hello world\nSecond line here"
        res = text_stats_handler(text)
        assert res["character_count"] == len(text)
        assert res["character_count_no_spaces"] == len("HelloworldSecondlinehere")
        assert res["word_count"] == 5
        assert res["line_count"] == 2

    def test_text_stats_handler_empty_text(self) -> None:
        res = text_stats_handler("")
        assert res["character_count"] == 0
        assert res["character_count_no_spaces"] == 0
        assert res["word_count"] == 0
        assert res["line_count"] == 0

    @pytest.mark.asyncio
    async def test_text_stats_executor_valid(self) -> None:
        registry = create_default_tool_registry()
        executor = ToolExecutor(registry)
        call = LLMToolCall(
            id="call_stats_1",
            name="text_stats",
            arguments='{"text": "The quick brown fox jumps"}',
        )
        res = await executor.execute(call)
        assert res.success is True
        assert res.tool_name == "text_stats"
        assert isinstance(res.result, dict)
        assert res.result["word_count"] == 5
        assert res.result["line_count"] == 1

    @pytest.mark.asyncio
    async def test_text_stats_missing_required_text(self) -> None:
        registry = create_default_tool_registry()
        executor = ToolExecutor(registry)
        call = LLMToolCall(id="call_stats_miss", name="text_stats", arguments="{}")
        res = await executor.execute(call)
        assert res.success is False
        assert res.error_code == ToolErrorCode.VALIDATION_FAILED
        assert "Missing required argument 'text'" in (res.error or "")

    @pytest.mark.asyncio
    async def test_text_stats_invalid_type(self) -> None:
        registry = create_default_tool_registry()
        executor = ToolExecutor(registry)
        call = LLMToolCall(
            id="call_stats_type",
            name="text_stats",
            arguments='{"text": 999}',
        )
        res = await executor.execute(call)
        assert res.success is False
        assert res.error_code == ToolErrorCode.VALIDATION_FAILED


class TestToolCancellation:
    @pytest.mark.asyncio
    async def test_cancellation_token_cancels_execution(self) -> None:
        registry = create_default_tool_registry()
        executor = ToolExecutor(registry)
        token = EventCancellationToken()
        token.cancel()

        call = LLMToolCall(
            id="call_cancelled",
            name="calculate",
            arguments='{"expression": "1 + 1"}',
        )
        res = await executor.execute(call, cancel=token)
        assert res.success is False
        assert res.error_code == ToolErrorCode.CANCELLED
        assert "cancelled" in (res.error or "").lower()
