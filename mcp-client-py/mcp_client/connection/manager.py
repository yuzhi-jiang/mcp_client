"""Connection manager for MCP Client."""

import asyncio
import logging
from typing import Dict, List, Optional, Set
from contextlib import AsyncExitStack

from mcp import ClientSession

from ..config.models import Config, ServerConfig
from ..transport.base import TransportFactory, TransportInterface
from ..exceptions import ConnectionError, ValidationError, TimeoutError
from ..utils.retry import retry_with_backoff


logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages connections to multiple MCP servers.
    
    This class handles the lifecycle of connections to MCP servers,
    including connection establishment, health monitoring, and cleanup.
    """
    
    def __init__(self, config: Config) -> None:
        """Initialize connection manager.
        
        Args:
            config: MCP client configuration
        """
        self.config = config
        self._sessions: Dict[str, ClientSession] = {}
        self._transports: Dict[str, TransportInterface] = {}
        self._exit_stack = AsyncExitStack()
        self._session_stacks: Dict[str, AsyncExitStack] = {}
        self._connection_locks: Dict[str, asyncio.Lock] = {}
        self._health_check_tasks: Dict[str, asyncio.Task] = {}
        self._is_shutdown = False
    
    async def connect_all(self) -> None:
        """Connect to all configured servers.
        
        This method attempts to connect to all enabled servers in the configuration.
        Failed connections are logged but don't prevent other connections from succeeding.
        
        Raises:
            ConnectionError: If no servers could be connected
        """
        if self._is_shutdown:
            raise ConnectionError("Connection manager has been shut down")
        
        enabled_servers = [
            name for name, config in self.config.servers.items()
            if not config.disabled
        ]
        
        if not enabled_servers:
            raise ValidationError("No enabled servers found in configuration")
        
        logger.info(f"Connecting to {len(enabled_servers)} servers: {enabled_servers}")
        
        # Connect sequentially instead of with asyncio.gather: an MCP
        # ClientSession enters an anyio task group bound to the task that
        # created it, so a session opened inside a gathered child task cannot be
        # closed from the caller's task ("cancel scope exited in a different
        # task"). Sequential setup keeps every session owned by this task.
        successful_connections = 0
        for server_name in enabled_servers:
            try:
                await self._connect_server_with_retry(server_name)
            except Exception as exc:
                logger.error(f"Failed to connect to server '{server_name}': {exc}")
            else:
                successful_connections += 1
                logger.info(f"Successfully connected to server '{server_name}'")
        
        if successful_connections == 0:
            raise ConnectionError(
                "Failed to connect to any servers",
                context={"attempted_servers": enabled_servers}
            )
        
        logger.info(f"Connected to {successful_connections}/{len(enabled_servers)} servers")
    
    async def connect_server(self, server_name: str) -> None:
        """Connect to a specific server.
        
        Args:
            server_name: Name of the server to connect to
            
        Raises:
            ValidationError: If server is not configured
            ConnectionError: If connection fails
        """
        if self._is_shutdown:
            raise ConnectionError("Connection manager has been shut down")
        
        if server_name not in self.config.servers:
            raise ValidationError(
                f"Server '{server_name}' not found in configuration",
                field_path=f"servers.{server_name}"
            )
        
        server_config = self.config.servers[server_name]
        if server_config.disabled:
            raise ValidationError(
                f"Server '{server_name}' is disabled",
                field_path=f"servers.{server_name}.disabled"
            )
        
        # Use lock to prevent concurrent connection attempts to the same server
        if server_name not in self._connection_locks:
            self._connection_locks[server_name] = asyncio.Lock()
        
        async with self._connection_locks[server_name]:
            if server_name in self._sessions:
                logger.warning(f"Server '{server_name}' is already connected")
                return
            
            await self._connect_server_internal(server_name, server_config)
    
    async def disconnect_server(self, server_name: str) -> None:
        """Disconnect from a specific server.
        
        Args:
            server_name: Name of the server to disconnect from
        """
        if server_name not in self._sessions:
            logger.warning(f"Server '{server_name}' is not connected")
            return
        
        # Use lock to prevent concurrent operations
        if server_name in self._connection_locks:
            async with self._connection_locks[server_name]:
                await self._disconnect_server_internal(server_name)
        else:
            await self._disconnect_server_internal(server_name)
    
    async def disconnect_all(self) -> None:
        """Disconnect from all servers and clean up resources."""
        logger.info("Disconnecting from all servers")
        
        # Cancel health check tasks
        for task in self._health_check_tasks.values():
            task.cancel()
        
        # Wait for health check tasks to complete
        if self._health_check_tasks:
            await asyncio.gather(*self._health_check_tasks.values(), return_exceptions=True)
        self._health_check_tasks.clear()
        
        # Disconnect sequentially for the same task-affinity reason as
        # connect_all(): the session's anyio task group must be exited by the
        # task that entered it.
        for server_name in list(self._sessions.keys()):
            try:
                await self._disconnect_server_internal(server_name)
            except Exception as exc:
                logger.error(f"Failed to disconnect from server '{server_name}': {exc}")
        
        # Clean up exit stack
        await self._exit_stack.aclose()
        
        # Clear state
        self._sessions.clear()
        self._transports.clear()
        self._connection_locks.clear()
        self._is_shutdown = True
        
        logger.info("All connections closed")
    
    def get_session(self, server_name: str) -> Optional[ClientSession]:
        """Get session for a server.
        
        Args:
            server_name: Name of the server
            
        Returns:
            ClientSession if connected, None otherwise
        """
        return self._sessions.get(server_name)
    
    def get_connected_servers(self) -> List[str]:
        """Get list of connected server names.
        
        Returns:
            List of connected server names
        """
        return list(self._sessions.keys())
    
    def is_connected(self, server_name: str) -> bool:
        """Check if a server is connected.
        
        Args:
            server_name: Name of the server
            
        Returns:
            True if connected, False otherwise
        """
        return server_name in self._sessions
    
    def get_connection_count(self) -> int:
        """Get number of active connections.
        
        Returns:
            Number of active connections
        """
        return len(self._sessions)
    
    def get_transport_info(self, server_name: str) -> Optional[Dict]:
        """Get transport information for a server.
        
        Args:
            server_name: Name of the server
            
        Returns:
            Transport metadata if connected, None otherwise
        """
        transport = self._transports.get(server_name)
        return transport.get_connection_metadata() if transport else None
    
    async def _connect_server_with_retry(self, server_name: str) -> None:
        """Connect to a server with retry logic.
        
        Args:
            server_name: Name of the server to connect to
        """
        server_config = self.config.servers[server_name]
        
        @retry_with_backoff(
            max_retries=server_config.max_retries,
            base_delay=1.0,
            max_delay=30.0,
            exceptions=(ConnectionError, TimeoutError)
        )
        async def _connect_with_retry():
            await self._connect_server_internal(server_name, server_config)
        
        try:
            await _connect_with_retry()
        except Exception as e:
            logger.error(f"Failed to connect to server '{server_name}' after retries: {e}")
            raise
    
    async def _connect_server_internal(self, server_name: str, server_config: ServerConfig) -> None:
        """Internal method to connect to a server.
        
        Args:
            server_name: Name of the server
            server_config: Server configuration
            
        Raises:
            ConnectionError: If connection fails
        """
        logger.info(f"Connecting to server '{server_name}' via {server_config.transport}")
        
        try:
            # Create transport
            transport = TransportFactory.create_transport(server_name, server_config)
            
            # Connect transport and get streams
            read_stream, write_stream = await transport.connect()
            
            # Create and initialize session
            session_kwargs = server_config.session_kwargs or {}
            session = ClientSession(read_stream, write_stream, **session_kwargs)
            
            # Register session with exit stack for cleanup
            # Each session gets its own exit stack so it can be closed before
            # the transport that feeds it (see _disconnect_server_internal).
            session_stack = AsyncExitStack()
            self._session_stacks[server_name] = session_stack
            session = await session_stack.enter_async_context(session)
            
            # Initialize the session
            await session.initialize()
            
            # Store session and transport
            self._sessions[server_name] = session
            self._transports[server_name] = transport
            
            # Start health monitoring if auto-reconnect is enabled
            if server_config.auto_reconnect:
                self._start_health_monitoring(server_name)
            
            logger.info(f"Successfully connected to server '{server_name}'")
            
        except Exception as e:
            logger.error(f"Failed to connect to server '{server_name}': {e}")
            
            # Clean up partial connection state
            if server_name in self._sessions:
                del self._sessions[server_name]
            if server_name in self._transports:
                try:
                    await self._transports[server_name].disconnect()
                except Exception:
                    pass  # Ignore cleanup errors
                del self._transports[server_name]
            
            raise ConnectionError(
                f"Failed to connect to server '{server_name}': {e}",
                server_name=server_name,
                transport_type=server_config.transport,
                cause=e
            )
    
    async def _disconnect_server_internal(self, server_name: str) -> None:
        """Internal method to disconnect from a server.
        
        Args:
            server_name: Name of the server to disconnect from
        """
        logger.info(f"Disconnecting from server '{server_name}'")
        
        # Cancel health monitoring
        if server_name in self._health_check_tasks:
            self._health_check_tasks[server_name].cancel()
            try:
                await self._health_check_tasks[server_name]
            except asyncio.CancelledError:
                pass
            del self._health_check_tasks[server_name]
        
        # Remove session (exit stack will handle cleanup)
        if server_name in self._sessions:
            del self._sessions[server_name]
        
        # Exit the session before closing the streams it reads from: closing
        # the transport first cancels the session's reader task and the anyio
        # cancel scope then propagates CancelledError into the caller.
        session_stack = self._session_stacks.pop(server_name, None)
        if session_stack is not None:
            try:
                await session_stack.aclose()
            except Exception as e:
                logger.warning(f"Error closing session for '{server_name}': {e}")

        # Disconnect transport
        if server_name in self._transports:
            try:
                await self._transports[server_name].disconnect()
            except Exception as e:
                logger.warning(f"Error disconnecting transport for '{server_name}': {e}")
            del self._transports[server_name]
        
        logger.info(f"Disconnected from server '{server_name}'")
    
    def _start_health_monitoring(self, server_name: str) -> None:
        """Start health monitoring for a server.
        
        Args:
            server_name: Name of the server to monitor
        """
        if server_name in self._health_check_tasks:
            return  # Already monitoring
        
        task = asyncio.create_task(
            self._health_monitor_loop(server_name),
            name=f"health_monitor_{server_name}"
        )
        self._health_check_tasks[server_name] = task
    
    async def _health_monitor_loop(self, server_name: str) -> None:
        """Health monitoring loop for a server.
        
        Args:
            server_name: Name of the server to monitor
        """
        logger.debug(f"Starting health monitoring for server '{server_name}'")
        
        try:
            while not self._is_shutdown and server_name in self._sessions:
                await asyncio.sleep(30)  # Check every 30 seconds
                
                # Check if transport is still connected
                transport = self._transports.get(server_name)
                if transport and not transport.is_connected():
                    logger.warning(f"Server '{server_name}' connection lost, attempting reconnect")
                    
                    # Remove from active sessions
                    if server_name in self._sessions:
                        del self._sessions[server_name]
                    
                    # Attempt reconnection
                    try:
                        server_config = self.config.servers[server_name]
                        await self._connect_server_internal(server_name, server_config)
                        logger.info(f"Successfully reconnected to server '{server_name}'")
                    except Exception as e:
                        logger.error(f"Failed to reconnect to server '{server_name}': {e}")
                        # Will retry on next health check
        
        except asyncio.CancelledError:
            logger.debug(f"Health monitoring cancelled for server '{server_name}'")
        except Exception as e:
            logger.error(f"Health monitoring error for server '{server_name}': {e}")
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect_all()