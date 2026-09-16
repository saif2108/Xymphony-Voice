"""Unit tests for built-in tool handlers and catalog."""

from __future__ import annotations

import json
import pytest
from xymphony_contracts.llm import LLMToolCall
from xymphony_contracts.tools import ToolErrorCode
from xymphony_tools import (
    ToolExecutor,
    ToolRegistry,
    calculate,
    create_calculator_tool,
    create_customer_lookup_tool,
    create_weather_lookup_tool,
    get_builtin_tools,
    lookup_customer,
    lookup_weather,
    register_builtin_tools,
)


# --- Calculator Tests ---


def test_calculate_basic_arithmetic() -> None:
    res = calculate("2 + 3 * 4")
    assert res["result"] == 14
    assert res["expression"] == "2 + 3 * 4"

    res_div = calculate("10 / 4")
    assert res_div["result"] == 2.5

    res_whole_div = calculate("8 / 2")
    assert res_whole_div["result"] == 4
    assert isinstance(res_whole_div["result"], int)

    res_pow = calculate("2 ** 3")
    assert res_pow["result"] == 8

    res_neg = calculate("-5 + 10")
    assert res_neg["result"] == 5


def test_calculate_division_by_zero() -> None:
    with pytest.raises(ValueError, match="Division by zero"):
        calculate("10 / 0")

    with pytest.raises(ValueError, match="Division by zero"):
        calculate("10 // 0")

    with pytest.raises(ValueError, match="Division by zero"):
        calculate("10 % 0")


def test_calculate_invalid_or_unsafe_expressions() -> None:
    with pytest.raises(ValueError, match="Expression cannot be empty"):
        calculate("   ")

    with pytest.raises(ValueError, match="Invalid arithmetic expression"):
        calculate("2 + + + *")

    with pytest.raises(ValueError, match="Unsupported expression element"):
        calculate("__import__('os').system('ls')")

    with pytest.raises(ValueError, match="Unsupported expression element"):
        calculate("x + 5")


@pytest.mark.asyncio
async def test_calculator_tool_via_executor() -> None:
    tool = create_calculator_tool()
    registry = ToolRegistry()
    registry.register(tool)
    executor = ToolExecutor(registry)

    call = LLMToolCall(
        id="call_1",
        name="calculator",
        arguments=json.dumps({"expression": "100 / 4 + 7"}),
    )
    result = await executor.execute(call)
    assert result.success is True
    assert result.error is None
    assert result.result == {"expression": "100 / 4 + 7", "result": 32}

    # Test execution error inside tool (division by zero)
    call_err = LLMToolCall(
        id="call_2",
        name="calculator",
        arguments=json.dumps({"expression": "42 / 0"}),
    )
    err_res = await executor.execute(call_err)
    assert err_res.success is False
    assert err_res.error_code == ToolErrorCode.EXECUTION_FAILED
    assert "Division by zero" in (err_res.error or "")


# --- Customer Lookup Tests ---


def test_lookup_customer_by_id_email_phone() -> None:
    # By ID
    res_id = lookup_customer("cust_101", lookup_by="id")
    assert res_id["found"] is True
    assert res_id["customer"]["name"] == "Alice Johnson"

    # By Email
    res_email = lookup_customer("alice@example.com", lookup_by="email")
    assert res_email["found"] is True
    assert res_email["customer"]["id"] == "cust_101"

    # By Phone
    res_phone = lookup_customer("+1-555-0101", lookup_by="phone")
    assert res_phone["found"] is True
    assert res_phone["customer"]["id"] == "cust_101"

    # Auto-detect without explicit lookup_by
    res_auto = lookup_customer("bob@example.com")
    assert res_auto["found"] is True
    assert res_auto["customer"]["id"] == "cust_102"


def test_lookup_customer_not_found() -> None:
    res = lookup_customer("unknown_user_999")
    assert res["found"] is False
    assert "not found" in res["message"]


def test_custom_customer_database() -> None:
    custom_db = [
        {"id": "c_99", "name": "Custom User", "email": "custom@test.com", "phone": "123"}
    ]
    res = lookup_customer("c_99", customers=custom_db)
    assert res["found"] is True
    assert res["customer"]["name"] == "Custom User"


@pytest.mark.asyncio
async def test_customer_lookup_tool_via_executor() -> None:
    tool = create_customer_lookup_tool()
    registry = ToolRegistry()
    registry.register(tool)
    executor = ToolExecutor(registry)

    call = LLMToolCall(
        id="call_crm_1",
        name="customer_lookup",
        arguments=json.dumps({"query": "cust_102", "lookup_by": "id"}),
    )
    res = await executor.execute(call)
    assert res.success is True
    assert isinstance(res.result, dict)
    assert res.result["found"] is True
    assert res.result["customer"]["name"] == "Bob Smith"


# --- Weather Lookup Tests ---


def test_lookup_weather_known_cities() -> None:
    res_c = lookup_weather("San Francisco", units="celsius")
    assert res_c["city"] == "San Francisco"
    assert res_c["units"] == "celsius"
    assert res_c["temperature"] == 16
    assert res_c["condition"] == "Foggy"

    res_f = lookup_weather("San Francisco", units="fahrenheit")
    assert res_f["units"] == "fahrenheit"
    assert res_f["temperature"] == 60.8


def test_lookup_weather_deterministic_fallback() -> None:
    res1 = lookup_weather("Berlin")
    res2 = lookup_weather("Berlin")
    assert res1["city"] == "Berlin"
    assert res1["temperature"] == res2["temperature"]
    assert res1["condition"] == res2["condition"]


def test_lookup_weather_invalid_args() -> None:
    with pytest.raises(ValueError, match="City name cannot be empty"):
        lookup_weather("   ")

    with pytest.raises(ValueError, match="Unsupported units"):
        lookup_weather("London", units="kelvin")


@pytest.mark.asyncio
async def test_weather_lookup_tool_via_executor() -> None:
    tool = create_weather_lookup_tool()
    registry = ToolRegistry()
    registry.register(tool)
    executor = ToolExecutor(registry)

    call = LLMToolCall(
        id="call_w_1",
        name="weather_lookup",
        arguments=json.dumps({"city": "Tokyo", "units": "celsius"}),
    )
    res = await executor.execute(call)
    assert res.success is True
    assert isinstance(res.result, dict)
    assert res.result["city"] == "Tokyo"
    assert res.result["temperature"] == 24


# --- Catalog & Registration Tests ---


def test_get_and_register_builtin_tools() -> None:
    tools = get_builtin_tools()
    assert len(tools) == 3
    names = {t.name for t in tools}
    assert names == {"calculator", "customer_lookup", "weather_lookup"}

    registry = ToolRegistry()
    register_builtin_tools(registry)
    assert registry.has("calculator")
    assert registry.has("customer_lookup")
    assert registry.has("weather_lookup")
