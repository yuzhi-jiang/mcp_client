"""Tool executor for MCP Client."""

import json
import logging
from typing import Any, Dict

from ..config.models import Tool, ToolResult
from ..connection.manager import ConnectionManager
from ..exceptions import ToolExecutionError, ValidationError
from ..utils.retry import TOOL_EXECUTION_RETRY_POLICY


logger = logging.getLogger(__name__)


class ToolExecutor:
    """Executes tools on MCP servers with proper error handling and validation.
    
    This class handles the actual execution of tools, including argument validation,
    server routing, and result processing.
    """
    
    def __init__(self, connection_manager: ConnectionManager) -> None:
        """Initialize tool executor.
        
        Args:
            connection_manager: Connection manager instance
        """
        self.connection_manager = connection_manager
    
    async def execute_tool(self, tool: Tool, arguments: Dict[str, Any]) -> ToolResult:
        """Execute a tool with the given arguments.
        
        Args:
            tool: Tool to execute
            arguments: Arguments to pass to the tool
            
        Returns:
            Tool execution result
            
        Raises:
            ValidationError: If arguments are invalid
            ToolExecutionError: If tool execution fails
        """
        logger.info(f"Executing tool '{tool.name}' on server '{tool.server_name}'")
        logger.debug(f"Tool arguments: {arguments}")
        
        # Validate arguments against tool schema
        self._validate_arguments(tool, arguments)
        
        # Get session for the server
        session = self.connection_manager.get_session(tool.server_name)
        if not session:
            raise ToolExecutionError(
                f"No active session for server '{tool.server_name}'",
                tool_name=tool.name,
                server_name=tool.server_name
            )
        
        # Execute tool with retry policy
        try:
            result = await TOOL_EXECUTION_RETRY_POLICY.execute(
                self._execute_tool_internal,
                session,
                tool,
                arguments
            )
            
            logger.info(f"Successfully executed tool '{tool.name}'")
            logger.debug(f"Tool result: {result}")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to execute tool '{tool.name}': {e}")
            raise
    
    async def _execute_tool_internal(self, session, tool: Tool, arguments: Dict[str, Any]) -> ToolResult:
        """Internal method to execute a tool.
        
        Args:
            session: MCP client session
            tool: Tool to execute
            arguments: Tool arguments
            
        Returns:
            Tool execution result
            
        Raises:
            ToolExecutionError: If execution fails
        """
        try:
            # Call the tool on the MCP server
            mcp_result = await session.call_tool(tool.name, arguments)
            
            # Convert MCP result to our ToolResult format
            result = ToolResult(
                content=mcp_result.content,
                # mcp 1.x uses camelCase, mcp 2.x uses snake_case
                is_error=bool(
                    getattr(mcp_result, "isError", False)
                    or getattr(mcp_result, "is_error", False)
                ),
            )
            
            # Check if the result indicates an error
            if result.is_error:
                error_message = self._extract_error_message(result.content)
                result.error_message = error_message
                
                raise ToolExecutionError(
                    f"Tool '{tool.name}' returned an error: {error_message}",
                    tool_name=tool.name,
                    server_name=tool.server_name,
                    arguments=arguments
                )
            
            return result
            
        except ToolExecutionError:
            # Re-raise tool execution errors as-is
            raise
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to execute tool '{tool.name}' on server '{tool.server_name}': {e}",
                tool_name=tool.name,
                server_name=tool.server_name,
                arguments=arguments,
                cause=e
            )
    
    def _validate_arguments(self, tool: Tool, arguments: Dict[str, Any]) -> None:
        """Validate tool arguments against the tool's input schema.
        
        Args:
            tool: Tool definition
            arguments: Arguments to validate
            
        Raises:
            ValidationError: If arguments are invalid
        """
        if not isinstance(arguments, dict):
            raise ValidationError(
                f"Tool arguments must be a dictionary, got {type(arguments).__name__}",
                field_path=f"tools.{tool.name}.arguments",
                expected_type="dict",
                actual_value=arguments
            )
        
        schema = tool.input_schema
        
        # Basic schema validation
        if "type" in schema and schema["type"] == "object":
            # Validate required properties
            required_props = schema.get("required", [])
            for prop in required_props:
                if prop not in arguments:
                    raise ValidationError(
                        f"Required argument '{prop}' missing for tool '{tool.name}'",
                        field_path=f"tools.{tool.name}.arguments.{prop}",
                        expected_type="required"
                    )
            
            # Validate property types
            properties = schema.get("properties", {})
            for arg_name, arg_value in arguments.items():
                if arg_name in properties:
                    prop_schema = properties[arg_name]
                    self._validate_argument_type(tool.name, arg_name, arg_value, prop_schema)
                elif schema.get("additionalProperties") is False:
                    raise ValidationError(
                        f"Unknown argument '{arg_name}' for tool '{tool.name}'",
                        field_path=f"tools.{tool.name}.arguments.{arg_name}",
                        actual_value=arg_name
                    )
    
    def _validate_argument_type(self, tool_name: str, arg_name: str, value: Any, schema: Dict[str, Any]) -> None:
        """Validate a single argument against its schema.
        
        Args:
            tool_name: Name of the tool
            arg_name: Name of the argument
            value: Argument value
            schema: Argument schema
            
        Raises:
            ValidationError: If argument type is invalid
        """
        expected_type = schema.get("type")
        if not expected_type:
            return  # No type constraint
        
        # Type mapping from JSON Schema to Python types
        type_mapping = {
            "string": str,
            "number": (int, float),
            "integer": int,
            "boolean": bool,
            "array": list,
            "object": dict,
            "null": type(None)
        }
        
        if expected_type in type_mapping:
            expected_python_type = type_mapping[expected_type]
            
            if not isinstance(value, expected_python_type):
                raise ValidationError(
                    f"Argument '{arg_name}' for tool '{tool_name}' must be of type {expected_type}, "
                    f"got {type(value).__name__}",
                    field_path=f"tools.{tool_name}.arguments.{arg_name}",
                    expected_type=expected_type,
                    actual_value=value
                )
        
        # Additional validations
        if expected_type == "string":
            # Check string constraints
            if "minLength" in schema and len(value) < schema["minLength"]:
                raise ValidationError(
                    f"Argument '{arg_name}' for tool '{tool_name}' must be at least "
                    f"{schema['minLength']} characters long",
                    field_path=f"tools.{tool_name}.arguments.{arg_name}",
                    actual_value=value
                )
            
            if "maxLength" in schema and len(value) > schema["maxLength"]:
                raise ValidationError(
                    f"Argument '{arg_name}' for tool '{tool_name}' must be at most "
                    f"{schema['maxLength']} characters long",
                    field_path=f"tools.{tool_name}.arguments.{arg_name}",
                    actual_value=value
                )
            
            if "enum" in schema and value not in schema["enum"]:
                raise ValidationError(
                    f"Argument '{arg_name}' for tool '{tool_name}' must be one of {schema['enum']}, "
                    f"got '{value}'",
                    field_path=f"tools.{tool_name}.arguments.{arg_name}",
                    expected_type=f"one of {schema['enum']}",
                    actual_value=value
                )
        
        elif expected_type in ["number", "integer"]:
            # Check numeric constraints
            if "minimum" in schema and value < schema["minimum"]:
                raise ValidationError(
                    f"Argument '{arg_name}' for tool '{tool_name}' must be at least {schema['minimum']}",
                    field_path=f"tools.{tool_name}.arguments.{arg_name}",
                    actual_value=value
                )
            
            if "maximum" in schema and value > schema["maximum"]:
                raise ValidationError(
                    f"Argument '{arg_name}' for tool '{tool_name}' must be at most {schema['maximum']}",
                    field_path=f"tools.{tool_name}.arguments.{arg_name}",
                    actual_value=value
                )
        
        elif expected_type == "array":
            # Check array constraints
            if "minItems" in schema and len(value) < schema["minItems"]:
                raise ValidationError(
                    f"Argument '{arg_name}' for tool '{tool_name}' must have at least "
                    f"{schema['minItems']} items",
                    field_path=f"tools.{tool_name}.arguments.{arg_name}",
                    actual_value=value
                )
            
            if "maxItems" in schema and len(value) > schema["maxItems"]:
                raise ValidationError(
                    f"Argument '{arg_name}' for tool '{tool_name}' must have at most "
                    f"{schema['maxItems']} items",
                    field_path=f"tools.{tool_name}.arguments.{arg_name}",
                    actual_value=value
                )
            
            # Validate array items if schema is provided
            if "items" in schema:
                items_schema = schema["items"]
                for i, item in enumerate(value):
                    self._validate_argument_type(
                        tool_name, 
                        f"{arg_name}[{i}]", 
                        item, 
                        items_schema
                    )
    
    def _extract_error_message(self, content: list) -> str:
        """Extract error message from tool result content.
        
        Args:
            content: Tool result content
            
        Returns:
            Error message string
        """
        if not content:
            return "Unknown error"
        
        # Try to extract error message from content
        for item in content:
            if isinstance(item, dict):
                # Look for common error message fields
                for field in ["error", "message", "text", "content"]:
                    if field in item and isinstance(item[field], str):
                        return item[field]
                
                # If it's a structured error, convert to string
                if "type" in item and item["type"] == "text" and "text" in item:
                    return item["text"]
        
        # Fallback: convert entire content to string
        try:
            return json.dumps(content, indent=2)
        except Exception:
            return str(content)
    
    def validate_tool_result(self, result: ToolResult) -> bool:
        """Validate that a tool result is well-formed.
        
        Args:
            result: Tool result to validate
            
        Returns:
            True if result is valid, False otherwise
        """
        try:
            # Check that content is a list
            if not isinstance(result.content, list):
                logger.warning("Tool result content is not a list")
                return False
            
            # Check that each content item is a dictionary
            for i, item in enumerate(result.content):
                if not isinstance(item, dict):
                    logger.warning(f"Tool result content item {i} is not a dictionary")
                    return False
                
                # Check for required fields in content items
                if "type" not in item:
                    logger.warning(f"Tool result content item {i} missing 'type' field")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating tool result: {e}")
            return False