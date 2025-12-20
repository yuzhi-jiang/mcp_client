"""Configuration validation for MCP Client."""

import re
from typing import Any, Dict, List, Optional, Set, Union
from urllib.parse import urlparse

from ..exceptions import ValidationError


class ConfigValidator:
    """Validates MCP client configurations.
    
    This class provides comprehensive validation for MCP client configurations,
    including schema validation, type checking, and business rule validation.
    """
    
    # Valid transport types
    VALID_TRANSPORTS = {"stdio", "sse"}
    
    # Valid log levels
    VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    
    # Valid message roles
    VALID_MESSAGE_ROLES = {"system", "user", "assistant", "tool"}
    
    # Valid encoding error handlers
    VALID_ENCODING_HANDLERS = {"strict", "ignore", "replace"}
    
    @classmethod
    def validate_config(cls, data: Dict[str, Any], config_path: str = "") -> None:
        """Validate complete configuration.
        
        Args:
            data: Configuration dictionary to validate
            config_path: Path to config file (for error context)
            
        Raises:
            ValidationError: If configuration is invalid
        """
        if not isinstance(data, dict):
            raise ValidationError(
                f"Configuration must be a dictionary, got {type(data).__name__}",
                field_path="root"
            )
        
        # Validate servers configuration
        servers_data = data.get("servers", data.get("mcpServers"))
        if not servers_data:
            raise ValidationError(
                "Configuration must contain 'servers' or 'mcpServers' key",
                field_path="servers"
            )
        
        cls._validate_servers(servers_data)
        
        # Validate global settings
        cls._validate_global_settings(data)
    
    @classmethod
    def _validate_servers(cls, servers_data: Any) -> None:
        """Validate servers configuration.
        
        Args:
            servers_data: Servers configuration data
            
        Raises:
            ValidationError: If servers configuration is invalid
        """
        if not isinstance(servers_data, dict):
            raise ValidationError(
                f"Servers configuration must be a dictionary, got {type(servers_data).__name__}",
                field_path="servers"
            )
        
        if not servers_data:
            raise ValidationError(
                "At least one server must be configured",
                field_path="servers"
            )
        
        server_names = set()
        for server_name, server_config in servers_data.items():
            # Validate server name
            cls._validate_server_name(server_name)
            
            # Check for duplicate names (case-insensitive)
            server_name_lower = server_name.lower()
            if server_name_lower in server_names:
                raise ValidationError(
                    f"Duplicate server name: {server_name}",
                    field_path=f"servers.{server_name}"
                )
            server_names.add(server_name_lower)
            
            # Validate individual server configuration
            cls._validate_server_config(server_config, server_name)
    
    @classmethod
    def _validate_server_name(cls, server_name: str) -> None:
        """Validate server name.
        
        Args:
            server_name: Server name to validate
            
        Raises:
            ValidationError: If server name is invalid
        """
        if not isinstance(server_name, str):
            raise ValidationError(
                f"Server name must be a string, got {type(server_name).__name__}",
                field_path="servers"
            )
        
        if not server_name.strip():
            raise ValidationError(
                "Server name cannot be empty",
                field_path="servers"
            )
        
        # Server names should be valid identifiers (alphanumeric + underscore/hyphen)
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9_-]*$', server_name):
            raise ValidationError(
                f"Invalid server name '{server_name}'. Must start with a letter and contain only letters, numbers, underscores, and hyphens",
                field_path=f"servers.{server_name}"
            )
    
    @classmethod
    def _validate_server_config(cls, config: Any, server_name: str) -> None:
        """Validate individual server configuration.
        
        Args:
            config: Server configuration data
            server_name: Name of the server
            
        Raises:
            ValidationError: If server configuration is invalid
        """
        if not isinstance(config, dict):
            raise ValidationError(
                f"Server configuration must be a dictionary, got {type(config).__name__}",
                field_path=f"servers.{server_name}"
            )
        
        # Validate transport type
        transport = config.get("transport")
        if not transport:
            raise ValidationError(
                "Transport type is required",
                field_path=f"servers.{server_name}.transport"
            )
        
        if transport not in cls.VALID_TRANSPORTS:
            raise ValidationError(
                f"Invalid transport type: {transport}",
                field_path=f"servers.{server_name}.transport",
                expected_type=f"one of {cls.VALID_TRANSPORTS}",
                actual_value=transport
            )
        
        # Validate transport-specific configuration
        if transport == "stdio":
            cls._validate_stdio_config(config, server_name)
        elif transport == "sse":
            cls._validate_sse_config(config, server_name)
        
        # Validate common optional fields
        cls._validate_common_server_fields(config, server_name)
    
    @classmethod
    def _validate_stdio_config(cls, config: Dict[str, Any], server_name: str) -> None:
        """Validate STDIO transport configuration.
        
        Args:
            config: Server configuration
            server_name: Name of the server
            
        Raises:
            ValidationError: If STDIO configuration is invalid
        """
        # Command is required
        command = config.get("command")
        if not command:
            raise ValidationError(
                "Command is required for stdio transport",
                field_path=f"servers.{server_name}.command"
            )
        
        if not isinstance(command, str):
            raise ValidationError(
                f"Command must be a string, got {type(command).__name__}",
                field_path=f"servers.{server_name}.command",
                actual_value=command
            )
        
        # Args are required
        args = config.get("args")
        if args is None:
            raise ValidationError(
                "Args are required for stdio transport",
                field_path=f"servers.{server_name}.args"
            )
        
        if not isinstance(args, list):
            raise ValidationError(
                f"Args must be a list, got {type(args).__name__}",
                field_path=f"servers.{server_name}.args",
                actual_value=args
            )
        
        # Validate each argument
        for i, arg in enumerate(args):
            if not isinstance(arg, str):
                raise ValidationError(
                    f"Argument {i} must be a string, got {type(arg).__name__}",
                    field_path=f"servers.{server_name}.args[{i}]",
                    actual_value=arg
                )
        
        # Validate environment variables
        env = config.get("env")
        if env is not None:
            cls._validate_environment_variables(env, server_name)
        
        # Validate encoding
        encoding = config.get("encoding", "utf-8")
        if not isinstance(encoding, str):
            raise ValidationError(
                f"Encoding must be a string, got {type(encoding).__name__}",
                field_path=f"servers.{server_name}.encoding",
                actual_value=encoding
            )
        
        # Validate encoding error handler
        error_handler = config.get("encoding_error_handler", "strict")
        if error_handler not in cls.VALID_ENCODING_HANDLERS:
            raise ValidationError(
                f"Invalid encoding error handler: {error_handler}",
                field_path=f"servers.{server_name}.encoding_error_handler",
                expected_type=f"one of {cls.VALID_ENCODING_HANDLERS}",
                actual_value=error_handler
            )
    
    @classmethod
    def _validate_sse_config(cls, config: Dict[str, Any], server_name: str) -> None:
        """Validate SSE transport configuration.
        
        Args:
            config: Server configuration
            server_name: Name of the server
            
        Raises:
            ValidationError: If SSE configuration is invalid
        """
        # URL is required
        url = config.get("url")
        if not url:
            raise ValidationError(
                "URL is required for SSE transport",
                field_path=f"servers.{server_name}.url"
            )
        
        if not isinstance(url, str):
            raise ValidationError(
                f"URL must be a string, got {type(url).__name__}",
                field_path=f"servers.{server_name}.url",
                actual_value=url
            )
        
        # Validate URL format
        try:
            parsed_url = urlparse(url)
            if not parsed_url.scheme or not parsed_url.netloc:
                raise ValidationError(
                    f"Invalid URL format: {url}",
                    field_path=f"servers.{server_name}.url",
                    actual_value=url
                )
            
            if parsed_url.scheme not in ["http", "https"]:
                raise ValidationError(
                    f"URL scheme must be http or https, got {parsed_url.scheme}",
                    field_path=f"servers.{server_name}.url",
                    actual_value=url
                )
        except Exception as e:
            raise ValidationError(
                f"Invalid URL: {e}",
                field_path=f"servers.{server_name}.url",
                actual_value=url,
                cause=e
            )
        
        # Validate headers
        headers = config.get("headers")
        if headers is not None:
            cls._validate_headers(headers, server_name)
        
        # Validate SSE read timeout
        sse_read_timeout = config.get("sse_read_timeout")
        if sse_read_timeout is not None:
            cls._validate_timeout(sse_read_timeout, f"servers.{server_name}.sse_read_timeout")
    
    @classmethod
    def _validate_common_server_fields(cls, config: Dict[str, Any], server_name: str) -> None:
        """Validate common server configuration fields.
        
        Args:
            config: Server configuration
            server_name: Name of the server
            
        Raises:
            ValidationError: If common fields are invalid
        """
        # Validate timeout
        timeout = config.get("timeout")
        if timeout is not None:
            cls._validate_timeout(timeout, f"servers.{server_name}.timeout")
        
        # Validate disabled flag
        disabled = config.get("disabled", False)
        if not isinstance(disabled, bool):
            raise ValidationError(
                f"Disabled flag must be a boolean, got {type(disabled).__name__}",
                field_path=f"servers.{server_name}.disabled",
                actual_value=disabled
            )
        
        # Validate auto_reconnect flag
        auto_reconnect = config.get("auto_reconnect", True)
        if not isinstance(auto_reconnect, bool):
            raise ValidationError(
                f"Auto reconnect flag must be a boolean, got {type(auto_reconnect).__name__}",
                field_path=f"servers.{server_name}.auto_reconnect",
                actual_value=auto_reconnect
            )
        
        # Validate max_retries
        max_retries = config.get("max_retries", 3)
        if not isinstance(max_retries, int) or max_retries < 0:
            raise ValidationError(
                f"Max retries must be a non-negative integer, got {max_retries}",
                field_path=f"servers.{server_name}.max_retries",
                actual_value=max_retries
            )
        
        # Validate session_kwargs
        session_kwargs = config.get("session_kwargs")
        if session_kwargs is not None and not isinstance(session_kwargs, dict):
            raise ValidationError(
                f"Session kwargs must be a dictionary, got {type(session_kwargs).__name__}",
                field_path=f"servers.{server_name}.session_kwargs",
                actual_value=session_kwargs
            )
    
    @classmethod
    def _validate_environment_variables(cls, env: Any, server_name: str) -> None:
        """Validate environment variables configuration.
        
        Args:
            env: Environment variables data
            server_name: Name of the server
            
        Raises:
            ValidationError: If environment variables are invalid
        """
        if not isinstance(env, dict):
            raise ValidationError(
                f"Environment variables must be a dictionary, got {type(env).__name__}",
                field_path=f"servers.{server_name}.env"
            )
        
        for key, value in env.items():
            if not isinstance(key, str):
                raise ValidationError(
                    f"Environment variable name must be a string, got {type(key).__name__}",
                    field_path=f"servers.{server_name}.env",
                    actual_value=key
                )
            
            if not isinstance(value, str):
                raise ValidationError(
                    f"Environment variable value must be a string, got {type(value).__name__}",
                    field_path=f"servers.{server_name}.env.{key}",
                    actual_value=value
                )
    
    @classmethod
    def _validate_headers(cls, headers: Any, server_name: str) -> None:
        """Validate HTTP headers configuration.
        
        Args:
            headers: Headers data
            server_name: Name of the server
            
        Raises:
            ValidationError: If headers are invalid
        """
        if not isinstance(headers, dict):
            raise ValidationError(
                f"Headers must be a dictionary, got {type(headers).__name__}",
                field_path=f"servers.{server_name}.headers"
            )
        
        for key, value in headers.items():
            if not isinstance(key, str):
                raise ValidationError(
                    f"Header name must be a string, got {type(key).__name__}",
                    field_path=f"servers.{server_name}.headers",
                    actual_value=key
                )
            
            if not isinstance(value, str):
                raise ValidationError(
                    f"Header value must be a string, got {type(value).__name__}",
                    field_path=f"servers.{server_name}.headers.{key}",
                    actual_value=value
                )
    
    @classmethod
    def _validate_timeout(cls, timeout: Any, field_path: str) -> None:
        """Validate timeout value.
        
        Args:
            timeout: Timeout value to validate
            field_path: Path to the field for error reporting
            
        Raises:
            ValidationError: If timeout is invalid
        """
        if not isinstance(timeout, (int, float)):
            raise ValidationError(
                f"Timeout must be a number, got {type(timeout).__name__}",
                field_path=field_path,
                actual_value=timeout
            )
        
        if timeout <= 0:
            raise ValidationError(
                f"Timeout must be positive, got {timeout}",
                field_path=field_path,
                actual_value=timeout
            )
    
    @classmethod
    def _validate_global_settings(cls, data: Dict[str, Any]) -> None:
        """Validate global configuration settings.
        
        Args:
            data: Configuration data
            
        Raises:
            ValidationError: If global settings are invalid
        """
        # Validate default timeout
        default_timeout = data.get("default_timeout", 30.0)
        if default_timeout is not None:
            cls._validate_timeout(default_timeout, "default_timeout")
        
        # Validate max retries
        max_retries = data.get("max_retries", 3)
        if not isinstance(max_retries, int) or max_retries < 0:
            raise ValidationError(
                f"Max retries must be a non-negative integer, got {max_retries}",
                field_path="max_retries",
                actual_value=max_retries
            )
        
        # Validate log level
        log_level = data.get("log_level", "INFO")
        if log_level not in cls.VALID_LOG_LEVELS:
            raise ValidationError(
                f"Invalid log level: {log_level}",
                field_path="log_level",
                expected_type=f"one of {cls.VALID_LOG_LEVELS}",
                actual_value=log_level
            )
        
        # Validate LLM settings
        llm_provider = data.get("llm_provider", "openai")
        if not isinstance(llm_provider, str):
            raise ValidationError(
                f"LLM provider must be a string, got {type(llm_provider).__name__}",
                field_path="llm_provider",
                actual_value=llm_provider
            )
        
        llm_model = data.get("llm_model", "gpt-4")
        if not isinstance(llm_model, str):
            raise ValidationError(
                f"LLM model must be a string, got {type(llm_model).__name__}",
                field_path="llm_model",
                actual_value=llm_model
            )
        
        # Validate performance settings
        max_concurrent = data.get("max_concurrent_connections", 10)
        if not isinstance(max_concurrent, int) or max_concurrent <= 0:
            raise ValidationError(
                f"Max concurrent connections must be a positive integer, got {max_concurrent}",
                field_path="max_concurrent_connections",
                actual_value=max_concurrent
            )
        
        pool_size = data.get("connection_pool_size", 5)
        if not isinstance(pool_size, int) or pool_size <= 0:
            raise ValidationError(
                f"Connection pool size must be a positive integer, got {pool_size}",
                field_path="connection_pool_size",
                actual_value=pool_size
            )