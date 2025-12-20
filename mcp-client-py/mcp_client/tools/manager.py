"""Tool manager for MCP Client."""

import logging
from typing import Any, Dict, List, Optional

from ..config.models import Tool, ToolResult
from ..connection.manager import ConnectionManager
from ..exceptions import ToolExecutionError, ValidationError
from .executor import ToolExecutor


logger = logging.getLogger(__name__)


class ToolManager:
    """Manages tool discovery and execution across MCP servers.
    
    This class provides a unified interface for discovering tools from
    connected servers and executing them with proper error handling.
    """
    
    def __init__(self, connection_manager: ConnectionManager) -> None:
        """Initialize tool manager.
        
        Args:
            connection_manager: Connection manager instance
        """
        self.connection_manager = connection_manager
        self.executor = ToolExecutor(connection_manager)
        self._tools_cache: Dict[str, List[Tool]] = {}
        self._tool_registry: Dict[str, Tool] = {}  # tool_name -> Tool
        self._server_tools: Dict[str, List[str]] = {}  # server_name -> [tool_names]
    
    async def discover_tools(self) -> None:
        """Discover tools from all connected servers.
        
        This method queries all connected servers for their available tools
        and builds an internal registry for fast lookup.
        
        Raises:
            ToolExecutionError: If tool discovery fails
        """
        logger.info("Discovering tools from connected servers")
        
        connected_servers = self.connection_manager.get_connected_servers()
        if not connected_servers:
            logger.warning("No connected servers found for tool discovery")
            return
        
        # Clear existing cache
        self._tools_cache.clear()
        self._tool_registry.clear()
        self._server_tools.clear()
        
        total_tools = 0
        
        for server_name in connected_servers:
            try:
                tools = await self._discover_server_tools(server_name)
                self._tools_cache[server_name] = tools
                
                # Update registry and server mapping
                server_tool_names = []
                for tool in tools:
                    # Handle tool name conflicts
                    if tool.name in self._tool_registry:
                        existing_tool = self._tool_registry[tool.name]
                        logger.warning(
                            f"Tool name conflict: '{tool.name}' exists on both "
                            f"'{existing_tool.server_name}' and '{server_name}'. "
                            f"Using tool from '{existing_tool.server_name}'"
                        )
                        continue
                    
                    self._tool_registry[tool.name] = tool
                    server_tool_names.append(tool.name)
                
                self._server_tools[server_name] = server_tool_names
                total_tools += len(server_tool_names)
                
                logger.info(
                    f"Discovered {len(tools)} tools from server '{server_name}': "
                    f"{[tool.name for tool in tools]}"
                )
                
            except Exception as e:
                logger.error(f"Failed to discover tools from server '{server_name}': {e}")
                # Continue with other servers
        
        logger.info(f"Tool discovery complete. Total tools: {total_tools}")
    
    async def _discover_server_tools(self, server_name: str) -> List[Tool]:
        """Discover tools from a specific server.
        
        Args:
            server_name: Name of the server
            
        Returns:
            List of tools from the server
            
        Raises:
            ToolExecutionError: If tool discovery fails
        """
        session = self.connection_manager.get_session(server_name)
        if not session:
            raise ToolExecutionError(
                f"No active session for server '{server_name}'",
                server_name=server_name
            )
        
        try:
            response = await session.list_tools()
            tools = []
            
            for mcp_tool in response.tools:
                tool = Tool(
                    name=mcp_tool.name,
                    description=mcp_tool.description,
                    input_schema=mcp_tool.inputSchema,
                    server_name=server_name
                )
                tools.append(tool)
            
            return tools
            
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to list tools from server '{server_name}': {e}",
                server_name=server_name,
                cause=e
            )
    
    def get_tools(self, server_name: Optional[str] = None) -> List[Tool]:
        """Get available tools from all servers or a specific server.
        
        Args:
            server_name: Optional name of a specific server to get tools from
            
        Returns:
            List of available tools
        """
        if server_name:
            if server_name not in self._tools_cache:
                logger.warning(f"No tools cached for server '{server_name}'")
                return []
            return self._tools_cache[server_name].copy()
        
        # Return all tools from all servers
        all_tools = []
        for tools in self._tools_cache.values():
            all_tools.extend(tools)
        return all_tools
    
    def get_tool(self, tool_name: str) -> Optional[Tool]:
        """Get a specific tool by name.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            Tool instance if found, None otherwise
        """
        return self._tool_registry.get(tool_name)
    
    def get_tool_names(self, server_name: Optional[str] = None) -> List[str]:
        """Get names of available tools.
        
        Args:
            server_name: Optional name of a specific server
            
        Returns:
            List of tool names
        """
        if server_name:
            return self._server_tools.get(server_name, []).copy()
        
        return list(self._tool_registry.keys())
    
    def get_server_for_tool(self, tool_name: str) -> Optional[str]:
        """Get the server name that provides a specific tool.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            Server name if tool exists, None otherwise
        """
        tool = self._tool_registry.get(tool_name)
        return tool.server_name if tool else None
    
    def has_tool(self, tool_name: str) -> bool:
        """Check if a tool is available.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            True if tool is available, False otherwise
        """
        return tool_name in self._tool_registry
    
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> ToolResult:
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
        if not self.has_tool(tool_name):
            raise ValidationError(
                f"Tool '{tool_name}' not found. Available tools: {list(self._tool_registry.keys())}",
                field_path="tool_name",
                actual_value=tool_name
            )
        
        tool = self._tool_registry[tool_name]
        return await self.executor.execute_tool(tool, arguments)
    
    def format_tools_for_llm(self, provider: str = "openai") -> List[Dict[str, Any]]:
        """Format tools for LLM API consumption.
        
        Args:
            provider: LLM provider name (e.g., "openai", "anthropic")
            
        Returns:
            List of tool definitions formatted for the specified provider
        """
        if provider.lower() == "openai":
            return self._format_tools_openai()
        elif provider.lower() == "anthropic":
            return self._format_tools_anthropic()
        else:
            # Default to OpenAI format
            logger.warning(f"Unknown provider '{provider}', using OpenAI format")
            return self._format_tools_openai()
    
    def _format_tools_openai(self) -> List[Dict[str, Any]]:
        """Format tools for OpenAI API.
        
        Returns:
            List of tool definitions in OpenAI format
        """
        formatted_tools = []
        
        for tool in self._tool_registry.values():
            tool_def = {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.input_schema
                }
            }
            formatted_tools.append(tool_def)
        
        return formatted_tools
    
    def _format_tools_anthropic(self) -> List[Dict[str, Any]]:
        """Format tools for Anthropic API.
        
        Returns:
            List of tool definitions in Anthropic format
        """
        formatted_tools = []
        
        for tool in self._tool_registry.values():
            tool_def = {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema
            }
            formatted_tools.append(tool_def)
        
        return formatted_tools
    
    def get_tool_statistics(self) -> Dict[str, Any]:
        """Get statistics about available tools.
        
        Returns:
            Dictionary containing tool statistics
        """
        total_tools = len(self._tool_registry)
        servers_with_tools = len([s for s in self._server_tools.values() if s])
        
        server_stats = {}
        for server_name, tool_names in self._server_tools.items():
            server_stats[server_name] = {
                "tool_count": len(tool_names),
                "tools": tool_names.copy()
            }
        
        return {
            "total_tools": total_tools,
            "servers_with_tools": servers_with_tools,
            "total_servers": len(self._tools_cache),
            "server_statistics": server_stats,
            "tool_names": list(self._tool_registry.keys())
        }
    
    async def refresh_tools(self, server_name: Optional[str] = None) -> None:
        """Refresh tool cache for all servers or a specific server.
        
        Args:
            server_name: Optional name of specific server to refresh
        """
        if server_name:
            if server_name in self.connection_manager.get_connected_servers():
                logger.info(f"Refreshing tools for server '{server_name}'")
                
                # Remove existing tools for this server
                if server_name in self._server_tools:
                    for tool_name in self._server_tools[server_name]:
                        self._tool_registry.pop(tool_name, None)
                
                # Rediscover tools for this server
                try:
                    tools = await self._discover_server_tools(server_name)
                    self._tools_cache[server_name] = tools
                    
                    server_tool_names = []
                    for tool in tools:
                        self._tool_registry[tool.name] = tool
                        server_tool_names.append(tool.name)
                    
                    self._server_tools[server_name] = server_tool_names
                    
                    logger.info(f"Refreshed {len(tools)} tools for server '{server_name}'")
                    
                except Exception as e:
                    logger.error(f"Failed to refresh tools for server '{server_name}': {e}")
            else:
                logger.warning(f"Server '{server_name}' is not connected")
        else:
            # Refresh all tools
            await self.discover_tools()
    
    def clear_cache(self) -> None:
        """Clear the tool cache."""
        logger.info("Clearing tool cache")
        self._tools_cache.clear()
        self._tool_registry.clear()
        self._server_tools.clear()