"""SSE transport implementation for MCP Client."""

import asyncio
from typing import Dict, Optional, Tuple
from contextlib import AsyncExitStack
from urllib.parse import urlparse

from mcp.client.sse import sse_client
from mcp.types import ReadStream, WriteStream

from .base import BaseTransport, TransportFactory
from ..config.models import ServerConfig
from ..exceptions import ConnectionError, ValidationError, TimeoutError


class SSETransport(BaseTransport):
    """Server-Sent Events (SSE) transport implementation for MCP servers.
    
    This transport connects to MCP servers that communicate via HTTP
    Server-Sent Events, typically for web-based or remote servers.
    """
    
    def __init__(self, server_name: str, config: ServerConfig) -> None:
        """Initialize SSE transport.
        
        Args:
            server_name: Name of the server
            config: Server configuration
            
        Raises:
            ValidationError: If configuration is invalid for SSE transport
        """
        super().__init__(server_name, config)
        self._exit_stack: Optional[AsyncExitStack] = None
        self._connection_info: Dict[str, any] = {}
    
    def _validate_config(self) -> None:
        """Validate SSE transport configuration.
        
        Raises:
            ValidationError: If configuration is invalid
        """
        if self.config.transport != "sse":
            raise ValidationError(
                f"Invalid transport type for SSETransport: {self.config.transport}",
                expected_type="sse",
                actual_value=self.config.transport
            )
        
        if not self.config.url:
            raise ValidationError(
                "URL is required for SSE transport",
                field_path=f"servers.{self.server_name}.url"
            )
        
        # Validate URL format
        try:
            parsed_url = urlparse(self.config.url)
            if not parsed_url.scheme or not parsed_url.netloc:
                raise ValidationError(
                    f"Invalid URL format: {self.config.url}",
                    field_path=f"servers.{self.server_name}.url",
                    actual_value=self.config.url
                )
            
            if parsed_url.scheme not in ["http", "https"]:
                raise ValidationError(
                    f"URL scheme must be http or https, got {parsed_url.scheme}",
                    field_path=f"servers.{self.server_name}.url",
                    actual_value=self.config.url
                )
        except Exception as e:
            if isinstance(e, ValidationError):
                raise
            raise ValidationError(
                f"Invalid URL: {e}",
                field_path=f"servers.{self.server_name}.url",
                actual_value=self.config.url,
                cause=e
            )
    
    async def _do_connect(self) -> Tuple[ReadStream, WriteStream]:
        """Establish SSE connection to MCP server.
        
        Returns:
            Tuple of (read_stream, write_stream)
            
        Raises:
            ConnectionError: If connection fails
            TimeoutError: If connection times out
        """
        try:
            # Create exit stack for resource management
            self._exit_stack = AsyncExitStack()
            
            # Prepare connection parameters
            url = self.config.url
            headers = self._prepare_headers()
            timeout = self.config.timeout or 30.0  # Default HTTP timeout
            sse_read_timeout = self.config.sse_read_timeout or 300.0  # Default SSE read timeout
            
            # Apply connection timeout if configured
            if self.config.timeout:
                try:
                    # Connect with timeout
                    sse_transport = await asyncio.wait_for(
                        self._exit_stack.enter_async_context(
                            sse_client(url, headers, timeout, sse_read_timeout)
                        ),
                        timeout=self.config.timeout
                    )
                except asyncio.TimeoutError:
                    await self._cleanup_exit_stack()
                    raise TimeoutError(
                        f"Connection to server '{self.server_name}' timed out after {self.config.timeout} seconds",
                        timeout_seconds=self.config.timeout,
                        operation="sse_connect"
                    )
            else:
                # Connect without explicit timeout (uses default HTTP timeout)
                sse_transport = await self._exit_stack.enter_async_context(
                    sse_client(url, headers, timeout, sse_read_timeout)
                )
            
            # Extract read and write streams
            read_stream, write_stream = sse_transport
            
            # Store connection information for metadata
            parsed_url = urlparse(url)
            self._connection_info = {
                "url": url,
                "scheme": parsed_url.scheme,
                "host": parsed_url.netloc,
                "path": parsed_url.path,
                "headers_count": len(headers),
                "http_timeout": timeout,
                "sse_read_timeout": sse_read_timeout,
            }
            
            # Update metadata
            self._update_metadata(
                connection_info=self._connection_info,
                connection_method="sse",
            )
            
            return read_stream, write_stream
            
        except (ConnectionError, TimeoutError):
            await self._cleanup_exit_stack()
            raise
        except Exception as e:
            await self._cleanup_exit_stack()
            raise ConnectionError(
                f"Failed to establish SSE connection to server '{self.server_name}': {e}",
                server_name=self.server_name,
                transport_type="sse",
                context={"url": self.config.url},
                cause=e
            )
    
    async def _do_disconnect(self) -> None:
        """Disconnect from SSE server.
        
        Raises:
            ConnectionError: If disconnection fails
        """
        try:
            await self._cleanup_exit_stack()
            self._connection_info.clear()
        except Exception as e:
            raise ConnectionError(
                f"Failed to disconnect SSE transport for server '{self.server_name}': {e}",
                server_name=self.server_name,
                transport_type="sse",
                cause=e
            )
    
    def _prepare_headers(self) -> Dict[str, str]:
        """Prepare HTTP headers for the SSE connection.
        
        Returns:
            Dictionary of HTTP headers
        """
        headers = {}
        
        # Add configured headers
        if self.config.headers:
            headers.update(self.config.headers)
        
        # Ensure required SSE headers are present
        if "Accept" not in headers:
            headers["Accept"] = "text/event-stream"
        
        if "Cache-Control" not in headers:
            headers["Cache-Control"] = "no-cache"
        
        # Add user agent if not specified
        if "User-Agent" not in headers:
            headers["User-Agent"] = f"mcp-client-py/0.1.0 (server: {self.server_name})"
        
        return headers
    
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
    
    def get_connection_info(self) -> Dict[str, any]:
        """Get information about the SSE connection.
        
        Returns:
            Dictionary containing connection information
        """
        return self._connection_info.copy()
    
    def get_url(self) -> Optional[str]:
        """Get the URL of the connected server.
        
        Returns:
            Server URL if connected, None otherwise
        """
        return self._connection_info.get("url") if self.is_connected() else None
    
    def get_host(self) -> Optional[str]:
        """Get the host of the connected server.
        
        Returns:
            Server host if connected, None otherwise
        """
        return self._connection_info.get("host") if self.is_connected() else None
    
    def is_secure_connection(self) -> bool:
        """Check if the connection uses HTTPS.
        
        Returns:
            True if using HTTPS, False otherwise
        """
        return (
            self.is_connected() and 
            self._connection_info.get("scheme") == "https"
        )


# Register the SSE transport with the factory
TransportFactory.register_transport("sse", SSETransport)