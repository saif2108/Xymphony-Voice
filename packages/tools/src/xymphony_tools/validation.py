"""Deterministic parameter schema validation for tool arguments."""

from __future__ import annotations

from typing import Any

from xymphony_tools.errors import ToolArgumentValidationError

__all__ = [
    "validate_tool_arguments",
]

_TYPE_CHECKERS = {
    "string": lambda val: isinstance(val, str),
    "integer": lambda val: isinstance(val, int) and not isinstance(val, bool),
    "number": lambda val: isinstance(val, (int, float)) and not isinstance(val, bool),
    "boolean": lambda val: isinstance(val, bool),
    "array": lambda val: isinstance(val, list),
    "object": lambda val: isinstance(val, dict),
    "null": lambda val: val is None,
}


def _matches_type(val: Any, type_decl: str | list[str] | tuple[str, ...]) -> bool:
    if isinstance(type_decl, (list, tuple)):
        return any(_matches_type(val, t) for t in type_decl)
    checker = _TYPE_CHECKERS.get(type_decl)
    if checker is not None:
        return checker(val)
    return True


def validate_tool_arguments(schema: dict[str, Any], arguments: dict[str, Any]) -> None:
    """Validate argument dictionary against a JSON Schema object specification.

    Raises ToolArgumentValidationError if arguments violate the schema.
    """
    if not isinstance(arguments, dict):
        raise ToolArgumentValidationError(
            f"Arguments must be a JSON object (dict), got {type(arguments).__name__}."
        )

    # 1. Check required properties
    required_fields = schema.get("required")
    if isinstance(required_fields, (list, tuple)):
        for req in required_fields:
            if req not in arguments:
                raise ToolArgumentValidationError(f"Missing required argument '{req}'.")

    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        properties = {}

    additional_allowed = schema.get("additionalProperties", True)

    # 2. Check property types, enums, and unexpected properties
    for key, val in arguments.items():
        if key in properties:
            prop_spec = properties[key]
            if isinstance(prop_spec, dict):
                # Type validation
                prop_type = prop_spec.get("type")
                if prop_type and not _matches_type(val, prop_type):
                    if isinstance(prop_type, (list, tuple)):
                        type_str = "/".join(prop_type)
                    else:
                        type_str = str(prop_type)
                    raise ToolArgumentValidationError(
                        f"Argument '{key}' expected type '{type_str}', got '{type(val).__name__}'."
                    )

                # Enum validation
                enum_values = prop_spec.get("enum")
                if isinstance(enum_values, (list, tuple)) and val not in enum_values:
                    allowed = list(enum_values)
                    raise ToolArgumentValidationError(
                        f"Argument '{key}' with value {val!r} is not one of allowed enum "
                        f"values: {allowed!r}."
                    )
        else:
            if additional_allowed is False:
                raise ToolArgumentValidationError(
                    f"Unexpected argument '{key}' is not permitted by parameter schema."
                )
