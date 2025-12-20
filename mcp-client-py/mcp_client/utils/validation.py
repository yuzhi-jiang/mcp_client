"""Validation utilities for MCP Client."""

import json
from typing import Any, Dict, List, Optional

from ..exceptions import ValidationError


def validate_json_schema(
    data: Any,
    schema: Dict[str, Any],
    field_path: str = "root"
) -> None:
    """Validate data against a JSON schema.
    
    This is a basic JSON schema validator. For production use,
    consider using a full JSON schema library like jsonschema.
    
    Args:
        data: Data to validate
        schema: JSON schema to validate against
        field_path: Path to the field being validated (for error reporting)
        
    Raises:
        ValidationError: If validation fails
    """
    schema_type = schema.get("type")
    
    if schema_type:
        _validate_type(data, schema_type, field_path)
    
    if schema_type == "object" and isinstance(data, dict):
        _validate_object(data, schema, field_path)
    elif schema_type == "array" and isinstance(data, list):
        _validate_array(data, schema, field_path)
    elif schema_type == "string" and isinstance(data, str):
        _validate_string(data, schema, field_path)
    elif schema_type in ["number", "integer"] and isinstance(data, (int, float)):
        _validate_number(data, schema, field_path)


def _validate_type(data: Any, expected_type: str, field_path: str) -> None:
    """Validate data type."""
    type_mapping = {
        "string": str,
        "number": (int, float),
        "integer": int,
        "boolean": bool,
        "array": list,
        "object": dict,
        "null": type(None)
    }
    
    expected_python_type = type_mapping.get(expected_type)
    if expected_python_type and not isinstance(data, expected_python_type):
        raise ValidationError(
            f"Expected {expected_type}, got {type(data).__name__}",
            field_path=field_path,
            expected_type=expected_type,
            actual_value=data
        )


def _validate_object(data: Dict[str, Any], schema: Dict[str, Any], field_path: str) -> None:
    """Validate object against schema."""
    # Check required properties
    required = schema.get("required", [])
    for prop in required:
        if prop not in data:
            raise ValidationError(
                f"Required property '{prop}' is missing",
                field_path=f"{field_path}.{prop}"
            )
    
    # Validate properties
    properties = schema.get("properties", {})
    for prop_name, prop_value in data.items():
        if prop_name in properties:
            validate_json_schema(
                prop_value,
                properties[prop_name],
                f"{field_path}.{prop_name}"
            )
        elif not schema.get("additionalProperties", True):
            raise ValidationError(
                f"Additional property '{prop_name}' not allowed",
                field_path=f"{field_path}.{prop_name}"
            )


def _validate_array(data: List[Any], schema: Dict[str, Any], field_path: str) -> None:
    """Validate array against schema."""
    # Check array length constraints
    min_items = schema.get("minItems")
    if min_items is not None and len(data) < min_items:
        raise ValidationError(
            f"Array must have at least {min_items} items, got {len(data)}",
            field_path=field_path
        )
    
    max_items = schema.get("maxItems")
    if max_items is not None and len(data) > max_items:
        raise ValidationError(
            f"Array must have at most {max_items} items, got {len(data)}",
            field_path=field_path
        )
    
    # Validate items
    items_schema = schema.get("items")
    if items_schema:
        for i, item in enumerate(data):
            validate_json_schema(item, items_schema, f"{field_path}[{i}]")


def _validate_string(data: str, schema: Dict[str, Any], field_path: str) -> None:
    """Validate string against schema."""
    # Check length constraints
    min_length = schema.get("minLength")
    if min_length is not None and len(data) < min_length:
        raise ValidationError(
            f"String must be at least {min_length} characters long, got {len(data)}",
            field_path=field_path
        )
    
    max_length = schema.get("maxLength")
    if max_length is not None and len(data) > max_length:
        raise ValidationError(
            f"String must be at most {max_length} characters long, got {len(data)}",
            field_path=field_path
        )
    
    # Check enum constraint
    enum_values = schema.get("enum")
    if enum_values is not None and data not in enum_values:
        raise ValidationError(
            f"String must be one of {enum_values}, got '{data}'",
            field_path=field_path,
            expected_type=f"one of {enum_values}",
            actual_value=data
        )
    
    # Check pattern constraint (basic regex support)
    pattern = schema.get("pattern")
    if pattern:
        import re
        if not re.match(pattern, data):
            raise ValidationError(
                f"String does not match pattern '{pattern}'",
                field_path=field_path,
                actual_value=data
            )


def _validate_number(data: float, schema: Dict[str, Any], field_path: str) -> None:
    """Validate number against schema."""
    # Check range constraints
    minimum = schema.get("minimum")
    if minimum is not None and data < minimum:
        raise ValidationError(
            f"Number must be at least {minimum}, got {data}",
            field_path=field_path
        )
    
    maximum = schema.get("maximum")
    if maximum is not None and data > maximum:
        raise ValidationError(
            f"Number must be at most {maximum}, got {data}",
            field_path=field_path
        )
    
    exclusive_minimum = schema.get("exclusiveMinimum")
    if exclusive_minimum is not None and data <= exclusive_minimum:
        raise ValidationError(
            f"Number must be greater than {exclusive_minimum}, got {data}",
            field_path=field_path
        )
    
    exclusive_maximum = schema.get("exclusiveMaximum")
    if exclusive_maximum is not None and data >= exclusive_maximum:
        raise ValidationError(
            f"Number must be less than {exclusive_maximum}, got {data}",
            field_path=field_path
        )


def validate_url(url: str, field_path: str = "url") -> None:
    """Validate URL format.
    
    Args:
        url: URL to validate
        field_path: Field path for error reporting
        
    Raises:
        ValidationError: If URL is invalid
    """
    from urllib.parse import urlparse
    
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise ValidationError(
                f"Invalid URL format: {url}",
                field_path=field_path,
                actual_value=url
            )
    except Exception as e:
        raise ValidationError(
            f"Invalid URL: {e}",
            field_path=field_path,
            actual_value=url,
            cause=e
        )


def validate_email(email: str, field_path: str = "email") -> None:
    """Validate email format.
    
    Args:
        email: Email to validate
        field_path: Field path for error reporting
        
    Raises:
        ValidationError: If email is invalid
    """
    import re
    
    # Basic email regex pattern
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if not re.match(pattern, email):
        raise ValidationError(
            f"Invalid email format: {email}",
            field_path=field_path,
            actual_value=email
        )


def validate_json_string(json_str: str, field_path: str = "json") -> Any:
    """Validate and parse JSON string.
    
    Args:
        json_str: JSON string to validate
        field_path: Field path for error reporting
        
    Returns:
        Parsed JSON data
        
    Raises:
        ValidationError: If JSON is invalid
    """
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValidationError(
            f"Invalid JSON: {e}",
            field_path=field_path,
            actual_value=json_str,
            cause=e
        )


def validate_non_empty_string(value: str, field_path: str) -> None:
    """Validate that a string is not empty.
    
    Args:
        value: String to validate
        field_path: Field path for error reporting
        
    Raises:
        ValidationError: If string is empty
    """
    if not isinstance(value, str):
        raise ValidationError(
            f"Expected string, got {type(value).__name__}",
            field_path=field_path,
            expected_type="string",
            actual_value=value
        )
    
    if not value.strip():
        raise ValidationError(
            "String cannot be empty",
            field_path=field_path,
            actual_value=value
        )


def validate_positive_number(value: float, field_path: str) -> None:
    """Validate that a number is positive.
    
    Args:
        value: Number to validate
        field_path: Field path for error reporting
        
    Raises:
        ValidationError: If number is not positive
    """
    if not isinstance(value, (int, float)):
        raise ValidationError(
            f"Expected number, got {type(value).__name__}",
            field_path=field_path,
            expected_type="number",
            actual_value=value
        )
    
    if value <= 0:
        raise ValidationError(
            f"Number must be positive, got {value}",
            field_path=field_path,
            actual_value=value
        )