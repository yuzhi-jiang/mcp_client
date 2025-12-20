"""Exception classes for MCP Client."""

from typing import Any, Dict, Optional


class MCPClientError(Exception):
    """Base exception for all MCP client errors.
    
    This is the base class for all exceptions raised by the MCP client library.
    It provides a consistent interface for error handling and includes optional
    context information for debugging.
    """
    
    def __init__(
        self, 
        message: str, 
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ) -> None:
        """Initialize the exception.
        
        Args:
            message: Human-readable error message
            context: Optional dictionary with additional context information
            cause: Optional underlying exception that caused this error
        """
        super().__init__(message)
        self.message = message
        self.context = context or {}
        self.cause = cause
    
    def __str__(self) -> str:
        """Return string representation of the error."""
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{self.message} (context: {context_str})"
        return self.message
    
    def __repr__(self) -> str:
        """Return detailed representation of the error."""
        return (
            f"{self.__class__.__name__}("
            f"message={self.message!r}, "
            f"context={self.context!r}, "
            f"cause={self.cause!r})"
        )


class ConfigurationError(MCPClientError):
    """Raised when there are configuration-related errors.
    
    This exception is raised when:
    - Configuration files cannot be loaded or parsed
    - Required configuration parameters are missing
    - Configuration values are invalid or malformed
    - Environment variable resolution fails
    """
    
    def __init__(
        self, 
        message: str, 
        config_path: Optional[str] = None,
        field_name: Optional[str] = None,
        **kwargs
    ) -> None:
        """Initialize configuration error.
        
        Args:
            message: Error message
            config_path: Path to the configuration file that caused the error
            field_name: Name of the configuration field that caused the error
            **kwargs: Additional context passed to parent class
        """
        context = kwargs.get("context", {})
        if config_path:
            context["config_path"] = config_path
        if field_name:
            context["field_name"] = field_name
        kwargs["context"] = context
        super().__init__(message, **kwargs)


class ConnectionError(MCPClientError):
    """Raised when connection-related errors occur.
    
    This exception is raised when:
    - Cannot establish connection to MCP server
    - Connection is lost unexpectedly
    - Transport-specific errors occur
    - Authentication or authorization fails
    """
    
    def __init__(
        self, 
        message: str, 
        server_name: Optional[str] = None,
        transport_type: Optional[str] = None,
        **kwargs
    ) -> None:
        """Initialize connection error.
        
        Args:
            message: Error message
            server_name: Name of the server that caused the error
            transport_type: Type of transport (stdio, sse, etc.)
            **kwargs: Additional context passed to parent class
        """
        context = kwargs.get("context", {})
        if server_name:
            context["server_name"] = server_name
        if transport_type:
            context["transport_type"] = transport_type
        kwargs["context"] = context
        super().__init__(message, **kwargs)


class ToolExecutionError(MCPClientError):
    """Raised when tool execution fails.
    
    This exception is raised when:
    - Tool cannot be found on any connected server
    - Tool arguments are invalid or malformed
    - Tool execution fails on the server side
    - Tool response cannot be parsed or processed
    """
    
    def __init__(
        self, 
        message: str, 
        tool_name: Optional[str] = None,
        server_name: Optional[str] = None,
        arguments: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> None:
        """Initialize tool execution error.
        
        Args:
            message: Error message
            tool_name: Name of the tool that failed
            server_name: Name of the server where the tool failed
            arguments: Arguments passed to the tool
            **kwargs: Additional context passed to parent class
        """
        context = kwargs.get("context", {})
        if tool_name:
            context["tool_name"] = tool_name
        if server_name:
            context["server_name"] = server_name
        if arguments:
            context["arguments"] = arguments
        kwargs["context"] = context
        super().__init__(message, **kwargs)


class ValidationError(MCPClientError):
    """Raised when data validation fails.
    
    This exception is raised when:
    - Input data doesn't match expected schema
    - Required fields are missing
    - Data types are incorrect
    - Value constraints are violated
    """
    
    def __init__(
        self, 
        message: str, 
        field_path: Optional[str] = None,
        expected_type: Optional[str] = None,
        actual_value: Optional[Any] = None,
        **kwargs
    ) -> None:
        """Initialize validation error.
        
        Args:
            message: Error message
            field_path: Path to the field that failed validation (e.g., "servers.calculator.command")
            expected_type: Expected data type or format
            actual_value: The actual value that failed validation
            **kwargs: Additional context passed to parent class
        """
        context = kwargs.get("context", {})
        if field_path:
            context["field_path"] = field_path
        if expected_type:
            context["expected_type"] = expected_type
        if actual_value is not None:
            context["actual_value"] = actual_value
        kwargs["context"] = context
        super().__init__(message, **kwargs)


class TimeoutError(MCPClientError):
    """Raised when operations timeout.
    
    This exception is raised when:
    - Connection attempts timeout
    - Tool execution takes too long
    - Server responses are not received within expected time
    """
    
    def __init__(
        self, 
        message: str, 
        timeout_seconds: Optional[float] = None,
        operation: Optional[str] = None,
        **kwargs
    ) -> None:
        """Initialize timeout error.
        
        Args:
            message: Error message
            timeout_seconds: The timeout value that was exceeded
            operation: Description of the operation that timed out
            **kwargs: Additional context passed to parent class
        """
        context = kwargs.get("context", {})
        if timeout_seconds:
            context["timeout_seconds"] = timeout_seconds
        if operation:
            context["operation"] = operation
        kwargs["context"] = context
        super().__init__(message, **kwargs)


class AuthenticationError(MCPClientError):
    """Raised when authentication fails.
    
    This exception is raised when:
    - API keys are invalid or expired
    - Authentication tokens cannot be obtained
    - Authorization is denied for requested operations
    """
    
    def __init__(
        self, 
        message: str, 
        auth_type: Optional[str] = None,
        **kwargs
    ) -> None:
        """Initialize authentication error.
        
        Args:
            message: Error message
            auth_type: Type of authentication that failed (api_key, token, etc.)
            **kwargs: Additional context passed to parent class
        """
        context = kwargs.get("context", {})
        if auth_type:
            context["auth_type"] = auth_type
        kwargs["context"] = context
        super().__init__(message, **kwargs)


class ServerError(MCPClientError):
    """Raised when MCP server returns an error.
    
    This exception is raised when:
    - MCP server returns an error response
    - Server-side tool execution fails
    - Server becomes unavailable or unresponsive
    """
    
    def __init__(
        self, 
        message: str, 
        server_name: Optional[str] = None,
        error_code: Optional[str] = None,
        **kwargs
    ) -> None:
        """Initialize server error.
        
        Args:
            message: Error message
            server_name: Name of the server that returned the error
            error_code: Server-specific error code
            **kwargs: Additional context passed to parent class
        """
        context = kwargs.get("context", {})
        if server_name:
            context["server_name"] = server_name
        if error_code:
            context["error_code"] = error_code
        kwargs["context"] = context
        super().__init__(message, **kwargs)