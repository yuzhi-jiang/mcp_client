"""
MCP Client - A Python library for connecting to Model Context Protocol servers.

This library provides a clean, modular interface for connecting to multiple MCP servers,
managing tools, and integrating with language models.
"""

__version__ = "0.1.0"
__author__ = "MCP Client Contributors"
__email__ = "contact@example.com"

# Main client interface
from .client import MCPClient

# Configuration models
from .config.models import Config, ServerConfig, Tool, ToolResult, Message, ToolCall
from .config.manager import ConfigManager

# Connection and tool management
from .connection.manager import ConnectionManager
from .tools.manager import ToolManager

# LLM integration
from .llm.base import LLMAdapterInterface, ChatResponse
from .llm.openai import OpenAIAdapter
from .llm.conversation import ConversationManager

# Transport layer
from .transport.base import TransportInterface, TransportFactory
from .transport.stdio import StdioTransport
from .transport.sse import SSETransport

# Exceptions
from .exceptions import (
    MCPClientError,
    ConfigurationError,
    ConnectionError,
    ToolExecutionError,
    ValidationError,
    TimeoutError,
    AuthenticationError,
    ServerError,
)

# Utilities
from .utils.logging import configure_logging
from .utils.retry import retry_with_backoff, RetryPolicy

__all__ = [
    # Main interface
    "MCPClient",
    
    # Configuration
    "Config",
    "ServerConfig", 
    "ConfigManager",
    
    # Data models
    "Tool",
    "ToolResult",
    "Message",
    "ToolCall",
    
    # Managers
    "ConnectionManager",
    "ToolManager",
    
    # LLM integration
    "LLMAdapterInterface",
    "OpenAIAdapter",
    "ConversationManager",
    "ChatResponse",
    
    # Transport layer
    "TransportInterface",
    "TransportFactory",
    "StdioTransport",
    "SSETransport",
    
    # Exceptions
    "MCPClientError",
    "ConfigurationError",
    "ConnectionError",
    "ToolExecutionError",
    "ValidationError",
    "TimeoutError",
    "AuthenticationError",
    "ServerError",
    
    # Utilities
    "configure_logging",
    "retry_with_backoff",
    "RetryPolicy",
]