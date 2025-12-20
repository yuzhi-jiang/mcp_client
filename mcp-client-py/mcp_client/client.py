"""Main MCP Client implementation."""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .config.manager import ConfigManager
from .config.models import Config, Tool, ToolResult
from .connection.manager import ConnectionManager
from .exceptions import ConfigurationError, ValidationError
from .llm.base import LLMAdapterFactory
from .llm.conversation import ConversationManager
from .tools.manager import ToolManager
from .utils.logging import configure_logging


logger = logging.getLogger(__name__)


class MCPClient:
    """Main client interface for MCP operations.
    
    This is the primary interface for interacting with MCP servers,
    providing a unified API for connection management, tool execution,
    and LLM integration.
    """
    
    def __init__(self, config: Optional[Config] = None) -> None:
        """Initialize MCP client.
        
        Args:
            config: Optional configuration. If not provided, will attempt to load from default location.
        """
        # Load configuration if not provided
        if config is None:
            try:
                config = ConfigManager.load_config("mcp_config.json")
            except Exception as e:
                raise ConfigurationError(
                    "No configuration provided and failed to load default config: "
                    "Please provide a Config instance or ensure mcp_config.json exists",
                    cause=e
                )
        
        self.config = config
        
        # Configure logging
        configure_logging(level=config.log_level)
        
        # Initialize managers
        self.connection_manager = ConnectionManager(config)
        self.tool_manager = ToolManager(self.connection_manager)
        
        # LLM integration (optional)
        self._llm_adapter = None
        self._conversation_manager = None
        
        # Initialize LLM adapter if configured
        if config.llm_api_key:
            try:
                self._llm_adapter = LLMAdapterFactory.create_adapter(
                    provider_name=config.llm_provider,
                    api_key=config.llm_api_key,
                    base_url=config.llm_base_url,
                    model=config.llm_model
                )
                logger.info(f"Initialized {config.llm_provider} LLM adapter with model {config.llm_model}")
            except Exception as e:
                logger.warning(f"Failed to initialize LLM adapter: {e}")
        
        self._is_connected = False
        
        logger.info("MCP Client initialized")
    
    @classmethod
    def from_config_file(cls, config_path: Union[str, Path]) -> "MCPClient":
        """Create MCP client from configuration file.
        
        Args:
            config_path: Path to configuration file
            
        Returns:
            MCPClient instance
        """
        config = ConfigManager.load_config(config_path)
        return cls(config)
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "MCPClient":
        """Create MCP client from configuration dictionary.
        
        Args:
            config_dict: Configuration dictionary
            
        Returns:
            MCPClient instance
        """
        config = ConfigManager.from_dict(config_dict)
        return cls(config)
    
    async def connect(self) -> None:
        """Establish connections to configured servers.
        
        This method connects to all enabled servers and discovers available tools.
        
        Raises:
            ConnectionError: If no servers could be connected
        """
        if self._is_connected:
            logger.warning("Client is already connected")
            return
        
        logger.info("Connecting to MCP servers")
        
        # Connect to all servers
        await self.connection_manager.connect_all()
        
        # Discover tools from connected servers
        await self.tool_manager.discover_tools()
        
        # Initialize conversation manager if LLM adapter is available
        if self._llm_adapter:
            self._conversation_manager = ConversationManager(
                llm_adapter=self._llm_adapter,
                tool_manager=self.tool_manager
            )
            logger.info("Conversation manager initialized")
        
        self._is_connected = True
        
        # Log connection summary
        connected_servers = self.connection_manager.get_connected_servers()
        tool_count = len(self.tool_manager.get_tools())
        
        logger.info(
            f"MCP Client connected successfully. "
            f"Servers: {len(connected_servers)}, Tools: {tool_count}"
        )
    
    async def disconnect(self) -> None:
        """Close all connections and cleanup resources."""
        if not self._is_connected:
            return
        
        logger.info("Disconnecting MCP client")
        
        # Clear tool cache
        self.tool_manager.clear_cache()
        
        # Disconnect from all servers
        await self.connection_manager.disconnect_all()
        
        # Clear conversation manager
        self._conversation_manager = None
        
        self._is_connected = False
        
        logger.info("MCP Client disconnected")
    
    def is_connected(self) -> bool:
        """Check if client is connected to any servers.
        
        Returns:
            True if connected to at least one server, False otherwise
        """
        return self._is_connected and self.connection_manager.get_connection_count() > 0
    
    def get_connected_servers(self) -> List[str]:
        """Get list of connected server names.
        
        Returns:
            List of connected server names
        """
        return self.connection_manager.get_connected_servers()
    
    def get_tools(self, server_name: Optional[str] = None) -> List[Tool]:
        """Get available tools from all servers or a specific server.
        
        Args:
            server_name: Optional name of a specific server to get tools from
            
        Returns:
            List of available tools
        """
        return self.tool_manager.get_tools(server_name)
    
    def get_tool_names(self, server_name: Optional[str] = None) -> List[str]:
        """Get names of available tools.
        
        Args:
            server_name: Optional name of a specific server
            
        Returns:
            List of tool names
        """
        return self.tool_manager.get_tool_names(server_name)
    
    def has_tool(self, tool_name: str) -> bool:
        """Check if a tool is available.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            True if tool is available, False otherwise
        """
        return self.tool_manager.has_tool(tool_name)
    
    def get_tool(self, tool_name: str) -> Optional[Tool]:
        """Get a specific tool by name.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            Tool instance if found, None otherwise
        """
        return self.tool_manager.get_tool(tool_name)
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> ToolResult:
        """Execute a tool by name.
        
        Args:
            tool_name: Name of the tool to execute
            arguments: Arguments to pass to the tool
            
        Returns:
            Tool execution result
            
        Raises:
            ValidationError: If tool is not found
            ToolExecutionError: If tool execution fails
        """
        if not self._is_connected:
            raise ValidationError("Client is not connected. Call connect() first.")
        
        return await self.tool_manager.execute_tool(tool_name, arguments)
    
    async def refresh_tools(self, server_name: Optional[str] = None) -> None:
        """Refresh tool cache for all servers or a specific server.
        
        Args:
            server_name: Optional name of specific server to refresh
        """
        await self.tool_manager.refresh_tools(server_name)
    
    def get_client_stats(self) -> Dict[str, Any]:
        """Get comprehensive client statistics.
        
        Returns:
            Dictionary containing client statistics
        """
        stats = {
            "is_connected": self._is_connected,
            "connected_servers": self.get_connected_servers(),
            "connection_count": self.connection_manager.get_connection_count(),
            "tool_statistics": self.tool_manager.get_tool_statistics(),
            "llm_adapter": {
                "available": self._llm_adapter is not None,
                "provider": self._llm_adapter.get_provider_name() if self._llm_adapter else None,
                "model": self._llm_adapter.get_model() if self._llm_adapter else None,
            },
            "conversation_manager": {
                "available": self._conversation_manager is not None,
                "stats": self._conversation_manager.get_conversation_stats() if self._conversation_manager else None,
            }
        }
        
        return stats
    
    # LLM Integration Methods
    
    def has_llm_integration(self) -> bool:
        """Check if LLM integration is available.
        
        Returns:
            True if LLM integration is configured and available
        """
        return self._llm_adapter is not None
    
    def get_conversation_manager(self) -> Optional[ConversationManager]:
        """Get the conversation manager instance.
        
        Returns:
            ConversationManager if available, None otherwise
        """
        return self._conversation_manager
    
    async def chat(
        self,
        message: str,
        execute_tools: bool = True,
        stream: bool = False,
        **llm_kwargs
    ) -> Any:
        """Send a chat message with automatic tool execution.
        
        Args:
            message: User message content
            execute_tools: Whether to execute tool calls automatically
            stream: Whether to stream the response
            **llm_kwargs: Additional arguments for LLM completion
            
        Returns:
            Chat response (format depends on streaming mode)
            
        Raises:
            ValidationError: If LLM integration is not available
        """
        if not self._conversation_manager:
            raise ValidationError(
                "LLM integration not available. Ensure LLM configuration is provided."
            )
        
        if not self._is_connected:
            raise ValidationError("Client is not connected. Call connect() first.")
        
        return await self._conversation_manager.send_message(
            content=message,
            execute_tools=execute_tools,
            stream=stream,
            **llm_kwargs
        )
    
    def set_system_prompt(self, prompt: str) -> None:
        """Set system prompt for conversations.
        
        Args:
            prompt: System prompt content
            
        Raises:
            ValidationError: If conversation manager is not available
        """
        if not self._conversation_manager:
            raise ValidationError(
                "Conversation manager not available. Ensure LLM configuration is provided."
            )
        
        self._conversation_manager.set_system_prompt(prompt)
    
    def clear_conversation_history(self, keep_system: bool = True) -> None:
        """Clear conversation history.
        
        Args:
            keep_system: Whether to keep system messages
            
        Raises:
            ValidationError: If conversation manager is not available
        """
        if not self._conversation_manager:
            raise ValidationError(
                "Conversation manager not available. Ensure LLM configuration is provided."
            )
        
        self._conversation_manager.clear_history(keep_system)
    
    def save_conversation(self, file_path: Union[str, Path]) -> None:
        """Save conversation to file.
        
        Args:
            file_path: Path to save the conversation
            
        Raises:
            ValidationError: If conversation manager is not available
        """
        if not self._conversation_manager:
            raise ValidationError(
                "Conversation manager not available. Ensure LLM configuration is provided."
            )
        
        self._conversation_manager.save_conversation(file_path)
    
    def load_conversation(self, file_path: Union[str, Path]) -> None:
        """Load conversation from file.
        
        Args:
            file_path: Path to load the conversation from
            
        Raises:
            ValidationError: If conversation manager is not available
        """
        if not self._conversation_manager:
            raise ValidationError(
                "Conversation manager not available. Ensure LLM configuration is provided."
            )
        
        self._conversation_manager.load_conversation(file_path)
    
    # Context Manager Support
    
    async def __aenter__(self) -> "MCPClient":
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.disconnect()
    
    # Server Management Methods
    
    async def connect_server(self, server_name: str) -> None:
        """Connect to a specific server.
        
        Args:
            server_name: Name of the server to connect to
            
        Raises:
            ValidationError: If server is not configured
            ConnectionError: If connection fails
        """
        await self.connection_manager.connect_server(server_name)
        
        # Refresh tools after connecting new server
        await self.tool_manager.refresh_tools(server_name)
    
    async def disconnect_server(self, server_name: str) -> None:
        """Disconnect from a specific server.
        
        Args:
            server_name: Name of the server to disconnect from
        """
        await self.connection_manager.disconnect_server(server_name)
        
        # Refresh tools after disconnecting server
        await self.tool_manager.refresh_tools()
    
    def get_server_info(self, server_name: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific server.
        
        Args:
            server_name: Name of the server
            
        Returns:
            Server information if connected, None otherwise
        """
        if not self.connection_manager.is_connected(server_name):
            return None
        
        transport_info = self.connection_manager.get_transport_info(server_name)
        server_tools = self.tool_manager.get_tool_names(server_name)
        
        return {
            "server_name": server_name,
            "is_connected": True,
            "transport_info": transport_info,
            "tool_count": len(server_tools),
            "tools": server_tools,
            "config": self.config.get_server_config(server_name)
        }