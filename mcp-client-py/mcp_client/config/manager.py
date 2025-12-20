"""Configuration manager for MCP Client."""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, Union

from .models import Config
from .validator import ConfigValidator
from ..exceptions import ConfigurationError


class ConfigManager:
    """Manages loading and validating MCP client configurations.
    
    This class provides methods for loading configurations from various sources,
    validating them, and resolving environment variables.
    """
    
    @staticmethod
    def load_config(
        config_path: Union[str, Path], 
        validate: bool = True,
        resolve_env: bool = True
    ) -> Config:
        """Load and validate configuration from a file.
        
        Args:
            config_path: Path to the configuration file
            validate: Whether to validate the configuration
            resolve_env: Whether to resolve environment variables
            
        Returns:
            Config instance
            
        Raises:
            ConfigurationError: If file cannot be loaded or parsed
            ValidationError: If configuration is invalid
        """
        config_path = Path(config_path)
        
        if not config_path.exists():
            raise ConfigurationError(
                f"Configuration file not found: {config_path}",
                config_path=str(config_path)
            )
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ConfigurationError(
                f"Invalid JSON in configuration file: {e}",
                config_path=str(config_path),
                cause=e
            )
        except Exception as e:
            raise ConfigurationError(
                f"Failed to read configuration file: {e}",
                config_path=str(config_path),
                cause=e
            )
        
        return ConfigManager.from_dict(
            data, 
            config_path=str(config_path),
            validate=validate,
            resolve_env=resolve_env
        )
    
    @staticmethod
    def from_dict(
        data: Dict[str, Any], 
        config_path: str = "",
        validate: bool = True,
        resolve_env: bool = True
    ) -> Config:
        """Create Config from dictionary.
        
        Args:
            data: Configuration dictionary
            config_path: Path to config file (for error context)
            validate: Whether to validate the configuration
            resolve_env: Whether to resolve environment variables
            
        Returns:
            Config instance
            
        Raises:
            ValidationError: If configuration is invalid
            ConfigurationError: If configuration cannot be processed
        """
        try:
            # Make a copy to avoid modifying the original
            config_data = data.copy()
            
            # Resolve environment variables if requested
            if resolve_env:
                config_data = ConfigManager.resolve_environment_variables(config_data)
            
            # Validate configuration if requested
            if validate:
                ConfigValidator.validate_config(config_data, config_path)
            
            # Create Config instance
            return Config.from_dict(config_data, config_path)
            
        except Exception as e:
            if isinstance(e, (ConfigurationError, ValidationError)):
                raise
            raise ConfigurationError(
                f"Failed to process configuration: {e}",
                config_path=config_path,
                cause=e
            )
    
    @staticmethod
    def resolve_environment_variables(data: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve environment variables in configuration values.
        
        Supports the following formats:
        - ${VAR}: Replace with environment variable value (error if not found)
        - ${VAR:default}: Replace with environment variable value or default
        - $VAR: Simple variable substitution (error if not found)
        
        Args:
            data: Configuration dictionary
            
        Returns:
            Dictionary with environment variables resolved
            
        Raises:
            ConfigurationError: If required environment variable is not found
        """
        return ConfigManager._resolve_env_recursive(data, [])
    
    @staticmethod
    def _resolve_env_recursive(data: Any, path: list) -> Any:
        """Recursively resolve environment variables in nested data structures.
        
        Args:
            data: Data to process (can be dict, list, or primitive)
            path: Current path in the data structure (for error reporting)
            
        Returns:
            Data with environment variables resolved
            
        Raises:
            ConfigurationError: If required environment variable is not found
        """
        if isinstance(data, dict):
            resolved = {}
            for key, value in data.items():
                current_path = path + [key]
                resolved[key] = ConfigManager._resolve_env_recursive(value, current_path)
            return resolved
        
        elif isinstance(data, list):
            resolved = []
            for i, item in enumerate(data):
                current_path = path + [f"[{i}]"]
                resolved.append(ConfigManager._resolve_env_recursive(item, current_path))
            return resolved
        
        elif isinstance(data, str):
            return ConfigManager._resolve_env_string(data, path)
        
        else:
            # Primitive types (int, float, bool, None) are returned as-is
            return data
    
    @staticmethod
    def _resolve_env_string(value: str, path: list) -> str:
        """Resolve environment variables in a string value.
        
        Args:
            value: String value to process
            path: Current path in the data structure (for error reporting)
            
        Returns:
            String with environment variables resolved
            
        Raises:
            ConfigurationError: If required environment variable is not found
        """
        # Handle ${VAR} and ${VAR:default} format
        if value.startswith("${") and value.endswith("}"):
            env_expr = value[2:-1]  # Remove ${ and }
            
            # Check for default value syntax: VAR:default
            if ":" in env_expr:
                env_var, default_value = env_expr.split(":", 1)
            else:
                env_var = env_expr
                default_value = None
            
            # Get environment variable value
            resolved_value = os.getenv(env_var.strip())
            
            if resolved_value is None:
                if default_value is not None:
                    return default_value
                else:
                    field_path = ".".join(str(p) for p in path)
                    raise ConfigurationError(
                        f"Environment variable '{env_var}' not found and no default provided",
                        field_name=field_path
                    )
            
            return resolved_value
        
        # Handle $VAR format (simple substitution)
        elif value.startswith("$") and not value.startswith("${"):
            env_var = value[1:]  # Remove $
            resolved_value = os.getenv(env_var)
            
            if resolved_value is None:
                field_path = ".".join(str(p) for p in path)
                raise ConfigurationError(
                    f"Environment variable '{env_var}' not found",
                    field_name=field_path
                )
            
            return resolved_value
        
        # Handle strings with embedded variables: "prefix${VAR}suffix"
        else:
            import re
            
            def replace_var(match):
                env_expr = match.group(1)
                
                # Check for default value syntax
                if ":" in env_expr:
                    env_var, default_value = env_expr.split(":", 1)
                else:
                    env_var = env_expr
                    default_value = None
                
                resolved_value = os.getenv(env_var.strip())
                
                if resolved_value is None:
                    if default_value is not None:
                        return default_value
                    else:
                        field_path = ".".join(str(p) for p in path)
                        raise ConfigurationError(
                            f"Environment variable '{env_var}' not found in embedded expression",
                            field_name=field_path
                        )
                
                return resolved_value
            
            # Replace all ${VAR} and ${VAR:default} patterns
            pattern = r'\$\{([^}]+)\}'
            try:
                return re.sub(pattern, replace_var, value)
            except ConfigurationError:
                raise
            except Exception as e:
                field_path = ".".join(str(p) for p in path)
                raise ConfigurationError(
                    f"Failed to resolve environment variables in '{value}': {e}",
                    field_name=field_path,
                    cause=e
                )
    
    @staticmethod
    def create_default_config() -> Dict[str, Any]:
        """Create a default configuration template.
        
        Returns:
            Dictionary with default configuration structure
        """
        return {
            "servers": {
                "example_stdio": {
                    "transport": "stdio",
                    "command": "python",
                    "args": ["-m", "example_server"],
                    "env": {
                        "EXAMPLE_VAR": "value"
                    },
                    "disabled": True
                },
                "example_sse": {
                    "transport": "sse",
                    "url": "https://api.example.com/mcp",
                    "headers": {
                        "Authorization": "Bearer ${API_TOKEN}"
                    },
                    "timeout": 30.0,
                    "disabled": True
                }
            },
            "default_timeout": 30.0,
            "max_retries": 3,
            "log_level": "INFO",
            "llm_provider": "openai",
            "llm_api_key": "${OPENAI_API_KEY}",
            "llm_model": "gpt-4",
            "max_concurrent_connections": 10,
            "connection_pool_size": 5
        }
    
    @staticmethod
    def save_config(config: Config, config_path: Union[str, Path]) -> None:
        """Save configuration to a file.
        
        Args:
            config: Config instance to save
            config_path: Path where to save the configuration
            
        Raises:
            ConfigurationError: If configuration cannot be saved
        """
        config_path = Path(config_path)
        
        try:
            # Convert Config to dictionary
            config_dict = ConfigManager._config_to_dict(config)
            
            # Ensure parent directory exists
            config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write configuration file
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            raise ConfigurationError(
                f"Failed to save configuration to {config_path}: {e}",
                config_path=str(config_path),
                cause=e
            )
    
    @staticmethod
    def _config_to_dict(config: Config) -> Dict[str, Any]:
        """Convert Config instance to dictionary.
        
        Args:
            config: Config instance to convert
            
        Returns:
            Dictionary representation of the configuration
        """
        # Convert server configurations
        servers = {}
        for name, server_config in config.servers.items():
            server_dict = {
                "transport": server_config.transport,
                "disabled": server_config.disabled,
                "auto_reconnect": server_config.auto_reconnect,
                "max_retries": server_config.max_retries,
            }
            
            # Add transport-specific fields
            if server_config.transport == "stdio":
                server_dict.update({
                    "command": server_config.command,
                    "args": server_config.args,
                    "encoding": server_config.encoding,
                    "encoding_error_handler": server_config.encoding_error_handler,
                })
                if server_config.env:
                    server_dict["env"] = server_config.env
                if server_config.cwd:
                    server_dict["cwd"] = server_config.cwd
            
            elif server_config.transport == "sse":
                server_dict["url"] = server_config.url
                if server_config.headers:
                    server_dict["headers"] = server_config.headers
                if server_config.sse_read_timeout:
                    server_dict["sse_read_timeout"] = server_config.sse_read_timeout
            
            # Add optional common fields
            if server_config.timeout:
                server_dict["timeout"] = server_config.timeout
            if server_config.session_kwargs:
                server_dict["session_kwargs"] = server_config.session_kwargs
            
            servers[name] = server_dict
        
        # Build complete configuration
        config_dict = {
            "servers": servers,
            "default_timeout": config.default_timeout,
            "max_retries": config.max_retries,
            "log_level": config.log_level,
            "llm_provider": config.llm_provider,
            "llm_model": config.llm_model,
            "max_concurrent_connections": config.max_concurrent_connections,
            "connection_pool_size": config.connection_pool_size,
        }
        
        # Add optional LLM fields
        if config.llm_api_key:
            config_dict["llm_api_key"] = config.llm_api_key
        if config.llm_base_url:
            config_dict["llm_base_url"] = config.llm_base_url
        
        return config_dict
    
    @staticmethod
    def merge_configs(base_config: Dict[str, Any], override_config: Dict[str, Any]) -> Dict[str, Any]:
        """Merge two configuration dictionaries.
        
        The override_config takes precedence over base_config.
        Server configurations are merged at the individual server level.
        
        Args:
            base_config: Base configuration dictionary
            override_config: Override configuration dictionary
            
        Returns:
            Merged configuration dictionary
        """
        merged = base_config.copy()
        
        for key, value in override_config.items():
            if key == "servers" and isinstance(value, dict) and isinstance(merged.get(key), dict):
                # Merge server configurations
                merged_servers = merged[key].copy()
                for server_name, server_config in value.items():
                    if server_name in merged_servers and isinstance(server_config, dict):
                        # Merge individual server configuration
                        merged_servers[server_name] = {
                            **merged_servers[server_name],
                            **server_config
                        }
                    else:
                        # Add new server or replace completely
                        merged_servers[server_name] = server_config
                merged[key] = merged_servers
            else:
                # Replace value completely
                merged[key] = value
        
        return merged