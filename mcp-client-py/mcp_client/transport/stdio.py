"""STDIO transport implementation for MCP Client."""

import os
import asyncio
from typing import Dict, List, Optional, Tuple
from contextlib import AsyncExitStack

from mcp import StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import ReadStream, WriteStream

from .base import BaseTransport, TransportFactory
from ..config.models import ServerConfig
from ..exceptions import ConnectionError, ValidationError, TimeoutError


class StdioTransport(BaseTransport):
    """STDIO transport implementation for MCP servers.
    
    This transport connects to MCP servers that communicate via standard
    input/output streams, typically by launching a subprocess.
    """
    
    def __init__(self, server_name: str, config: ServerConfig) -> None:
        """Initialize STDIO transport.
        
        Args:
            server_name: Name of the server
            config: Server configuration
            
        Raises:
            ValidationError: If configuration is invalid for STDIO transport
        """
        super().__init__(server_name, config)
        self._exit_stack: Optional[AsyncExitStack] = None
        self._process_info: Dict[str, any] = {}
    
    def _validate_config(self) -> None:
        """Validate STDIO transport configuration.
        
        Raises:
            ValidationError: If configuration is invalid
        """
        if self.config.transport != "stdio":
            raise ValidationError(
                f"Invalid transport type for StdioTransport: {self.config.transport}",
                expected_type="stdio",
                actual_value=self.config.transport
            )
        
        if not self.config.command:
            raise ValidationError(
                "Command is required for STDIO transport",
                field_path=f"servers.{self.server_name}.command"
            )
        
        if not self.config.args:
            raise ValidationError(
                "Args are required for STDIO transport",
                field_path=f"servers.{self.server_name}.args"
            )
        
        if not isinstance(self.config.args, list):
            raise ValidationError(
                "Args must be a list for STDIO transport",
                field_path=f"servers.{self.server_name}.args",
                expected_type="list",
                actual_value=type(self.config.args).__name__
            )
    
    async def _do_connect(self) -> Tuple[ReadStream, WriteStream]:
        """Establish STDIO connection to MCP server.
        
        Returns:
            Tuple of (read_stream, write_stream)
            
        Raises:
            ConnectionError: If connection fails
            TimeoutError: If connection times out
        """
        try:
            # Create exit stack for resource management
            self._exit_stack = AsyncExitStack()
            
            # Prepare environment variables
            env = self._prepare_environment()
            
            # Create server parameters
            server_params = StdioServerParameters(
                command=self.config.command,
                args=self.config.args,
                env=env,
                encoding=self.config.encoding,
                encoding_error_handler=self.config.encoding_error_handler,
            )
            
            # Apply timeout if configured
            timeout = self.config.timeout
            if timeout:
                try:
                    # Connect with timeout
                    stdio_transport = await asyncio.wait_for(
                        self._exit_stack.enter_async_context(stdio_client(server_params)),
                        timeout=timeout
                    )
                except asyncio.TimeoutError:
                    await self._cleanup_exit_stack()
                    raise TimeoutError(
                        f"Connection to server '{self.server_name}' timed out after {timeout} seconds",
                        timeout_seconds=timeout,
                        operation="stdio_connect"
                    )
            else:
                # Connect without timeout
                stdio_transport = await self._exit_stack.enter_async_context(
                    stdio_client(server_params)
                )
            
            # Extract read and write streams
            read_stream, write_stream = stdio_transport
            
            # Store process information for metadata
            self._process_info = {
                "command": self.config.command,
                "args": self.config.args,
                "env_vars_count": len(env),
                "encoding": self.config.encoding,
                "encoding_error_handler": self.config.encoding_error_handler,
            }
            
            # Update metadata
            self._update_metadata(
                process_info=self._process_info,
                connection_method="stdio",
            )
            
            return read_stream, write_stream
            
        except (ConnectionError, TimeoutError):
            await self._cleanup_exit_stack()
            raise
        except Exception as e:
            await self._cleanup_exit_stack()
            raise ConnectionError(
                f"Failed to establish STDIO connection to server '{self.server_name}': {e}",
                server_name=self.server_name,
                transport_type="stdio",
                context={"command": self.config.command, "args": self.config.args},
                cause=e
            )
    
    async def _do_disconnect(self) -> None:
        """Disconnect from STDIO server.
        
        Raises:
            ConnectionError: If disconnection fails
        """
        try:
            await self._cleanup_exit_stack()
            self._process_info.clear()
        except Exception as e:
            raise ConnectionError(
                f"Failed to disconnect STDIO transport for server '{self.server_name}': {e}",
                server_name=self.server_name,
                transport_type="stdio",
                cause=e
            )
    
    def _prepare_environment(self) -> Dict[str, str]:
        """Prepare environment variables for the subprocess.
        
        Returns:
            Dictionary of environment variables
        """
        # Start with current environment
        env = os.environ.copy()
        
        # Add configured environment variables
        if self.config.env:
            env.update(self.config.env)
        
        # Ensure PATH is set
        if "PATH" not in env:
            env["PATH"] = os.environ.get("PATH", "")
        
        return env
    
    async def _cleanup_exit_stack(self) -> None:
        """Clean up the exit stack and associated resources."""
        if self._exit_stack:
            try:
                await self._exit_stack.aclose()
            except Exception:
                # Ignore cleanup errors to avoid masking original exceptions
                pass
            finally:
                self._exit_stack = None
    
    def get_process_info(self) -> Dict[str, any]:
        """Get information about the connected process.
        
        Returns:
            Dictionary containing process information
        """
        return self._process_info.copy()
    
    def is_process_running(self) -> bool:
        """Check if the subprocess is still running.
        
        Returns:
            True if process is running, False otherwise
        """
        # For STDIO transport, we consider the process running if we're connected
        # The actual process monitoring is handled by the MCP library
        return self.is_connected()


# Register the STDIO transport with the factory
TransportFactory.register_transport("stdio", StdioTransport)