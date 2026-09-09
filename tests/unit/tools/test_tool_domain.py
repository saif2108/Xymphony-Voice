"""Unit tests for tool domain, context, and argument schema validation."""

from __future__ import annotations

import pytest

from xymphony_contracts.llm import LLMToolDefinition
from xymphony_tools.domain import Tool, ToolExecutionContext
from xymphony_tools.errors import ToolArgumentValidationError
from xymphony_tools.validation import validate_tool_arguments


class TestToolDomain:
    def test_tool_creation_and_properties(self) -> None:
        def dummy_handler(city: str) -> str:
            return f"Weather for {city}"

        tool = Tool(
            name="get_weather",
            description="Get current weather",
            parameters={
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
            handler=dummy_handler,
        )

        assert tool.name == "get_weather"
        assert tool.description == "Get current weather"
        assert tool.parameters["type"] == "object"
        assert tool.handler is dummy_handler
        assert "get_weather" in repr(tool)

    def test_tool_name_validation(self) -> None:
        def dummy() -> None:
            pass

        with pytest.raises(ValueError, match="Tool name must not be empty"):
            Tool(name="", handler=dummy)

        with pytest.raises(ValueError, match="Tool name must not be empty"):
            Tool(name="   ", handler=dummy)

        with pytest.raises(ValueError, match="exceed 128 characters"):
            Tool(name="a" * 129, handler=dummy)

    def test_tool_description_validation(self) -> None:
        def dummy() -> None:
            pass

        with pytest.raises(ValueError, match="exceed 4000 characters"):
            Tool(name="valid_name", description="x" * 4001, handler=dummy)

    def test_tool_to_definition(self) -> None:
        tool = Tool(
            name="calculate",
            description="Perform calculation",
            parameters={
                "type": "object",
                "properties": {"expr": {"type": "string"}},
                "required": ["expr"],
            },
            handler=lambda expr: expr,
        )

        defn = tool.to_definition()
        assert isinstance(defn, LLMToolDefinition)
        assert defn.name == "calculate"
        assert defn.description == "Perform calculation"
        assert defn.parameters == {
            "type": "object",
            "properties": {"expr": {"type": "string"}},
            "required": ["expr"],
        }


class TestToolExecutionContext:
    def test_default_context(self) -> None:
        ctx = ToolExecutionContext()
        assert ctx.tool_call_id == ""
        assert ctx.session_id is None

    def test_custom_context(self) -> None:
        ctx = ToolExecutionContext(tool_call_id="call_123", session_id="sess_456")
        assert ctx.tool_call_id == "call_123"
        assert ctx.session_id == "sess_456"


class TestSchemaValidation:
    def test_non_dict_arguments_fails(self) -> None:
        schema = {"type": "object", "properties": {}}
        with pytest.raises(ToolArgumentValidationError, match="must be a JSON object"):
            validate_tool_arguments(schema, "not a dict")  # type: ignore[arg-type]

    def test_missing_required_fails(self) -> None:
        schema = {
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        }
        with pytest.raises(ToolArgumentValidationError, match="Missing required argument 'city'"):
            validate_tool_arguments(schema, {})

    def test_valid_required_passes(self) -> None:
        schema = {
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        }
        validate_tool_arguments(schema, {"city": "Cairo"})

    def test_string_type_validation(self) -> None:
        schema = {"properties": {"city": {"type": "string"}}}
        validate_tool_arguments(schema, {"city": "London"})

        with pytest.raises(ToolArgumentValidationError, match="expected type 'string', got 'int'"):
            validate_tool_arguments(schema, {"city": 123})

    def test_integer_type_validation_rejects_bool(self) -> None:
        schema = {"properties": {"count": {"type": "integer"}}}
        validate_tool_arguments(schema, {"count": 42})

        with pytest.raises(
            ToolArgumentValidationError, match="expected type 'integer', got 'bool'"
        ):
            validate_tool_arguments(schema, {"count": True})

        with pytest.raises(ToolArgumentValidationError, match="expected type 'integer', got 'str'"):
            validate_tool_arguments(schema, {"count": "42"})

    def test_number_type_validation(self) -> None:
        schema = {"properties": {"temperature": {"type": "number"}}}
        validate_tool_arguments(schema, {"temperature": 98.6})
        validate_tool_arguments(schema, {"temperature": 100})

        with pytest.raises(ToolArgumentValidationError, match="expected type 'number', got 'bool'"):
            validate_tool_arguments(schema, {"temperature": False})

    def test_boolean_type_validation(self) -> None:
        schema = {"properties": {"active": {"type": "boolean"}}}
        validate_tool_arguments(schema, {"active": True})
        validate_tool_arguments(schema, {"active": False})

        with pytest.raises(ToolArgumentValidationError, match="expected type 'boolean', got 'int'"):
            validate_tool_arguments(schema, {"active": 1})

    def test_array_and_object_type_validation(self) -> None:
        schema = {
            "properties": {
                "tags": {"type": "array"},
                "meta": {"type": "object"},
            }
        }
        validate_tool_arguments(schema, {"tags": ["a", "b"], "meta": {"k": "v"}})

        with pytest.raises(ToolArgumentValidationError, match="expected type 'array', got 'dict'"):
            validate_tool_arguments(schema, {"tags": {}})

        with pytest.raises(ToolArgumentValidationError, match="expected type 'object', got 'list'"):
            validate_tool_arguments(schema, {"meta": []})

    def test_enum_validation(self) -> None:
        schema = {
            "properties": {
                "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]}
            }
        }
        validate_tool_arguments(schema, {"unit": "celsius"})

        with pytest.raises(ToolArgumentValidationError, match="not one of allowed enum values"):
            validate_tool_arguments(schema, {"unit": "kelvin"})

    def test_additional_properties_forbidden(self) -> None:
        schema = {
            "properties": {"name": {"type": "string"}},
            "additionalProperties": False,
        }
        validate_tool_arguments(schema, {"name": "Alice"})

        with pytest.raises(ToolArgumentValidationError, match="Unexpected argument 'extra'"):
            validate_tool_arguments(schema, {"name": "Alice", "extra": 123})
