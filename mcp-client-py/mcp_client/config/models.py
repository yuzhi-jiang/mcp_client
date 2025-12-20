"""Configuration data models for MCP Client."""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ..exceptions import ConfigurationError, ValidationError


@dataclass
class ServerConfig:
    """Configuration for a single MCP server.
    
    This class represents the configuration for connecting to an MCP server,
    including transport settings, authentication, and connection parameters.
    """
    
    # Transport configuration
    transport: str
    command: Optional[str] = None
    args: Optional[List[str]] = None
    url: Optional[str] = None
    
    # Environment and process configuration
    env: Optional[Dict[str, str]] = None
    cwd: Optional[str] = None
    
    # Connection configuration
    timeout: Optional[float] = None
    headers: Optional[Dict[str, str]] = None
    encoding: str = "utf-8"
    encoding_error_handler: str = "strict"
    
    # Session configuration
    session_kwargs: Optional[Dict[str, Any]] = None
    
    # Control flags
    disabled: bool = False
    auto_reconnect: bool = True
    max_retries: int = 3
    
    # SSE-specific configuration
    sse_read_timeout: Optional[float] = None
    
    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        self._validate()
    
    def _validate(self) -> None:
        """Validate the server configuration."""
        if not self.transport:
            raise ValidationError("Transport type is required", field_path="transport")
        
        if self.transport not in ["stdio", "sse"]:
            raise ValidationError(
                f"Unsupported transport type: {self.transport}",
                field_path="transport",
                expected_type="stdio or sse",
                actual_value=self.transport
            )
        
        if self.transport == "stdio":
            if not self.command:
                raise ValidationError(
                    "Command is required for stdio transport",
                    field_path="command"
                )
            if not self.args:
                raise ValidationError(
                    "Args are required for stdio transport", 
                    field_path="args"
                )
        
        elif self.transport == "sse":
            if not self.url:
                raise ValidationError(
                    "URL is required for SSE transport",
                    field_path="url"
                )
        
        if self.timeout is not None and self.timeout <= 0:
            raise ValidationError(
                "Timeout must be positive",
                field_path="timeout",
                actual_value=self.timeout
            )
        
        if self.max_retries < 0:
            raise ValidationError(
                "Max retries must be non-negative",
                field_path="max_retries",
                actual_value=self.max_retries
            )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], server_name: str = "") -> "ServerConfig":
        """Create ServerConfig from dictionary.
        
        Args:
            data: Configuration dictionary
            server_name: Name of the server (for error context)
            
        Returns:
            ServerConfig instance
            
        Raises:
            ValidationError: If configuration is invalid
        """
        try:
            # Create a copy to avoid modifying the original
            config_data = data.copy()
            
            # Resolve environment variables in string values
            config_data = cls._resolve_env_vars(config_data)
            
            return cls(**config_data)
        except TypeError as e:
            raise ValidationError(
                f"Invalid configuration for server '{server_name}': {e}",
                field_path=f"servers.{server_name}",
                cause=e
            )
    
    @staticmethod
    def _resolve_env_vars(data: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve environment variables in configuration values.
        
        Args:
            data: Configuration dictionary
            
        Returns:
            Dictionary with environment variables resolved
        """
        resolved = {}
        
        for key, value in data.items():
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                # Extract environment variable name
                env_var = value[2:-1]
                default_value = None
                
                # Check for default value syntax: ${VAR:default}
                if ":" in env_var:
                    env_var, default_value = env_var.split(":", 1)
                
                # Get environment variable value
                resolved_value = os.getenv(env_var, default_value)
                if resolved_value is None:
                    raise ConfigurationError(
                        f"Environment variable '{env_var}' not found and no default provided",
                        field_name=key
                    )
                resolved[key] = resolved_value
            elif isinstance(value, dict):
                resolved[key] = ServerConfig._resolve_env_vars(value)
            elif isinstance(value, list):
                resolved[key] = [
                    ServerConfig._resolve_env_vars(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                resolved[key] = value
        
        return resolved


@dataclass
class Config:
    """Main configuration container for MCP Client.
    
    This class holds the complete configuration for the MCP client,
    including server configurations and global settings.
    """
    
    servers: Dict[str, ServerConfig] = field(default_factory=dict)
    
    # Global settings
    default_timeout: float = 30.0
    max_retries: int = 3
    log_level: str = "INFO"
    
    # LLM integration settings
    llm_provider: str = "openai"
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None
    llm_model: str = "gpt-4"
    
    # Performance settings
    max_concurrent_connections: int = 10
    connection_pool_size: int = 5
    
    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        self._validate()
    
    def _validate(self) -> None:
        """Validate the complete configuration."""
        if not self.servers:
            raise ValidationError("At least one server must be configured")
        
        if self.default_timeout <= 0:
            raise ValidationError(
                "Default timeout must be positive",
                field_path="default_timeout",
                actual_value=self.default_timeout
            )
        
        if self.max_retries < 0:
            raise ValidationError(
                "Max retries must be non-negative",
                field_path="max_retries",
                actual_value=self.max_retries
            )
        
        if self.log_level not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            raise ValidationError(
                f"Invalid log level: {self.log_level}",
                field_path="log_level",
                expected_type="DEBUG, INFO, WARNING, ERROR, or CRITICAL",
                actual_value=self.log_level
            )
        
        if self.max_concurrent_connections <= 0:
            raise ValidationError(
                "Max concurrent connections must be positive",
                field_path="max_concurrent_connections",
                actual_value=self.max_concurrent_connections
            )
    
    @classmethod
    def from_file(cls, path: Union[str, Path]) -> "Config":
        """Load configuration from a JSON file.
        
        Args:
            path: Path to the configuration file
            
        Returns:
            Config instance
            
        Raises:
            ConfigurationError: If file cannot be loaded or parsed
            ValidationError: If configuration is invalid
        """
        path = Path(path)
        
        if not path.exists():
            raise ConfigurationError(
                f"Configuration file not found: {path}",
                config_path=str(path)
            )
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ConfigurationError(
                f"Invalid JSON in configuration file: {e}",
                config_path=str(path),
                cause=e
            )
        except Exception as e:
            raise ConfigurationError(
                f"Failed to read configuration file: {e}",
                config_path=str(path),
                cause=e
            )
        
        return cls.from_dict(data, str(path))
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], config_path: str = "") -> "Config":
        """Create Config from dictionary.
        
        Args:
            data: Configuration dictionary
            config_path: Path to config file (for error context)
            
        Returns:
            Config instance
            
        Raises:
            ValidationError: If configuration is invalid
        """
        try:
            # Extract server configurations
            servers_data = data.get("servers", data.get("mcpServers", {}))
            if not servers_data:
                raise ValidationError("No servers configured")
            
            # Create ServerConfig instances
            servers = {}
            for server_name, server_data in servers_data.items():
                if not isinstance(server_data, dict):
                    raise ValidationError(
                        f"Server configuration must be an object, got {type(server_data).__name__}",
                        field_path=f"servers.{server_name}"
                    )
                servers[server_name] = ServerConfig.from_dict(server_data, server_name)
            
            # Extract global settings
            config_kwargs = {
                "servers": servers,
                "default_timeout": data.get("default_timeout", 30.0),
                "max_retries": data.get("max_retries", 3),
                "log_level": data.get("log_level", "INFO"),
                "llm_provider": data.get("llm_provider", "openai"),
                "llm_api_key": data.get("llm_api_key"),
                "llm_base_url": data.get("llm_base_url"),
                "llm_model": data.get("llm_model", "gpt-4"),
                "max_concurrent_connections": data.get("max_concurrent_connections", 10),
                "connection_pool_size": data.get("connection_pool_size", 5),
            }
            
            return cls(**config_kwargs)
        
        except ValidationError:
            raise
        except Exception as e:
            raise ConfigurationError(
                f"Failed to parse configuration: {e}",
                config_path=config_path,
                cause=e
            )
    
    def get_server_config(self, server_name: str) -> ServerConfig:
        """Get configuration for a specific server.
        
        Args:
            server_name: Name of the server
            
        Returns:
            ServerConfig for the specified server
            
        Raises:
            ValidationError: If server is not configured
        """
        if server_name not in self.servers:
            raise ValidationError(
                f"Server '{server_name}' not found in configuration",
                field_path=f"servers.{server_name}"
            )
        return self.servers[server_name]
    
    def list_servers(self, include_disabled: bool = False) -> List[str]:
        """List configured server names.
        
        Args:
            include_disabled: Whether to include disabled servers
            
        Returns:
            List of server names
        """
        if include_disabled:
            return list(self.servers.keys())
        return [
            name for name, config in self.servers.items()
            if not config.disabled
        ]


@dataclass
class Tool:
    """Represents an MCP tool.
    
    This class encapsulates information about a tool available
    from an MCP server, including its schema and metadata.
    """
    
    name: str
    description: str
    input_schema: Dict[str, Any]
    server_name: str
    
    def __post_init__(self) -> None:
        """Validate tool after initialization."""
        if not self.name:
            raise ValidationError("Tool name is required")
        if not self.server_name:
            raise ValidationError("Server name is required")
        if not isinstance(self.input_schema, dict):
            raise ValidationError("Input schema must be a dictionary")


@dataclass
class ToolResult:
    """Result of a tool execution.
    
    This class represents the result returned from executing
    an MCP tool, including content and error information.
    """
    
    content: List[Dict[str, Any]]
    is_error: bool = False
    error_message: Optional[str] = None
    
    def __post_init__(self) -> None:
        """Validate tool result after initialization."""
        if not isinstance(self.content, list):
            raise ValidationError("Tool result content must be a list")


@dataclass
class ToolCall:
    """Represents a tool call in a message.
    
    This class encapsulates information about a tool call
    made by an LLM, including the tool name and arguments.
    """
    
    id: str
    name: str
    arguments: Dict[str, Any]
    
    def __post_init__(self) -> None:
        """Validate tool call after initialization."""
        if not self.id:
            raise ValidationError("Tool call ID is required")
        if not self.name:
            raise ValidationError("Tool call name is required")
        if not isinstance(self.arguments, dict):
            raise ValidationError("Tool call arguments must be a dictionary")


@dataclass
class Message:
    """Represents a conversation message.
    
    This class represents a message in a conversation,
    which can include text content and tool calls.
    """
    
    role: str
    content: str
    tool_calls: Optional[List[ToolCall]] = None
    
    def __post_init__(self) -> None:
        """Validate message after initialization."""
        if self.role not in ["system", "user", "assistant", "tool"]:
            raise ValidationError(
                f"Invalid message role: {self.role}",
                expected_type="system, user, assistant, or tool",
                actual_value=self.role
            )
        if not isinstance(self.content, str):
            raise ValidationError("Message content must be a string")
        if self.tool_calls is not None and not isinstance(self.tool_calls, list):
            raise ValidationError("Tool calls must be a list")