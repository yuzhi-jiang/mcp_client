"""Validators used by config and tool-call paths."""

from __future__ import annotations

import pytest

from mcp_client.exceptions import ValidationError
from mcp_client.utils.validation import (
    validate_email,
    validate_json_schema,
    validate_json_string,
    validate_non_empty_string,
    validate_positive_number,
    validate_url,
)

SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "count": {"type": "number"},
        "tags": {"type": "array"},
    },
    "required": ["name"],
}


def test_valid_object_passes() -> None:
    validate_json_schema({"name": "x", "count": 2, "tags": ["a"]}, SCHEMA)


def test_missing_required_field_is_rejected() -> None:
    with pytest.raises(ValidationError):
        validate_json_schema({"count": 2}, SCHEMA)


def test_wrong_type_is_rejected() -> None:
    with pytest.raises(ValidationError):
        validate_json_schema({"name": 123}, SCHEMA)


def test_url_validation() -> None:
    validate_url("https://example.com/mcp")
    with pytest.raises(ValidationError):
        validate_url("not-a-url")


def test_email_validation() -> None:
    validate_email("dev@example.com")
    with pytest.raises(ValidationError):
        validate_email("nope")


def test_json_string_roundtrip() -> None:
    assert validate_json_string('{"a": 1}') == {"a": 1}
    with pytest.raises(ValidationError):
        validate_json_string("{oops}")


def test_non_empty_string() -> None:
    validate_non_empty_string("value", "field")
    with pytest.raises(ValidationError):
        validate_non_empty_string("   ", "field")


def test_positive_number() -> None:
    validate_positive_number(1.5, "field")
    for bad in (0, -1):
        with pytest.raises(ValidationError):
            validate_positive_number(bad, "field")
