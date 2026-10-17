"""Base transport interface for MCP Client."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Tuple


from .streams import ReadStream, WriteStream

from ..config.models import ServerConfig
from ..exceptions import ConnectionError, ValidationError


class TransportInterface(ABC):
    """Abstract base class for MCP transports.
    
    This interface defines the contract that all MCP transport implementations
    must follow. It provides methods for establishing connections, managing
    the connection lifecycle, and accessing connection metadata.
    """
    
    def __init__(self, server_name: str, config: ServerConfig) -> None:
        """Initialize the transport.
        
        Args:
            server_name: Name of the server this transport connects to
            config: Server configuration
            
        Raises:
            ValidationError: If configuration is invalid for this transport
        """
        self.server_name = server_name
        self.config = config
        self._is_connected = False
        self._connection_metadata: Dict[str, Any] = {}
        
        # Validate configuration for this transport type
        self._validate_config()
    
    @abstractmethod
    def _validate_config(self) -> None:
        """Validate that the configuration is appropriate for this transport.
        
        Raises:
            ValidationError: If configuration is invalid
        """
        pass
    
    @abstractmethod
    async def connect(self) -> Tuple[ReadStream, WriteStream]:
        """Establish connection and return read/write streams.
        
        This method should establish the connection to the MCP server
        and return the streams that can be used for communication.
        
        Returns:
            Tuple of (read_stream, write_stream) for MCP communication
            
        Raises:
            ConnectionError: If connection cannot be established
            TimeoutError: If connection times out
        """
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Close the connection and clean up resources.
        
        This method should gracefully close the connection and clean up
        any resources associated with the transport.
        
        Raises:
            ConnectionError: If disconnection fails
        """
        pass
    
    def is_connected(self) -> bool:
        """Check if transport is currently connected.
        
        Returns:
            True if connected, False otherwise
        """
        return self._is_connected
    
    def get_connection_metadata(self) -> Dict[str, Any]:
        """Get metadata about the current connection.
        
        Returns:
            Dictionary containing connection metadata such as:
            - connection_time: When the connection was established
            - transport_type: Type of transport (stdio, sse, etc.)
            - server_info: Information about the connected server
            - performance_stats: Connection performance statistics
        """
        return self._connection_metadata.copy()
    
    def get_server_name(self) -> str:
        """Get the name of the server this transport connects to.
        
        Returns:
            Server name
        """
        return self.server_name
    
    def get_config(self) -> ServerConfig:
        """Get the configuration for this transport.
        
        Returns:
            Server configuration
        """
        return self.config
    
    async def __aenter__(self) -> Tuple[ReadStream, WriteStream]:
        """Async context manager entry.
        
        Returns:
            Tuple of (read_stream, write_stream)
        """
        return await self.connect()
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.disconnect()
    
    def _set_connected(self, connected: bool) -> None:
        """Set the connection status.
        
        Args:
            connected: Whether the transport is connected
        """
        self._is_connected = connected
    
    def _update_metadata(self, **metadata: Any) -> None:
        """Update connection metadata.
        
        Args:
            **metadata: Metadata key-value pairs to update
        """
        self._connection_metadata.update(metadata)
    
    def _clear_metadata(self) -> None:
        """Clear all connection metadata."""
        self._connection_metadata.clear()


class TransportFactory:
    """Factory for creating transport instances.
    
    This factory provides a centralized way to create transport instances
    based on configuration, supporting the open-closed principle by allowing
    new transport types to be registered without modifying existing code.
    """
    
    _transport_classes: Dict[str, type] = {}
    
    @classmethod
    def register_transport(cls, transport_type: str, transport_class: type) -> None:
        """Register a transport class for a given transport type.
        
        Args:
            transport_type: Name of the transport type (e.g., "stdio", "sse")
            transport_class: Transport class that implements TransportInterface
            
        Raises:
            ValidationError: If transport_class doesn't implement TransportInterface
        """
        if not issubclass(transport_class, TransportInterface):
            raise ValidationError(
                f"Transport class must implement TransportInterface, got {transport_class.__name__}"
            )
        
        cls._transport_classes[transport_type] = transport_class
    
    @classmethod
    def create_transport(cls, server_name: str, config: ServerConfig) -> TransportInterface:
        """Create a transport instance based on configuration.
        
        Args:
            server_name: Name of the server
            config: Server configuration
            
        Returns:
            Transport instance
            
        Raises:
            ValidationError: If transport type is not supported
            ConnectionError: If transport cannot be created
        """
        transport_type = config.transport
        
        if transport_type not in cls._transport_classes:
            raise ValidationError(
                f"Unsupported transport type: {transport_type}",
                field_path=f"servers.{server_name}.transport",
                expected_type=f"one of {list(cls._transport_classes.keys())}",
                actual_value=transport_type
            )
        
        transport_class = cls._transport_classes[transport_type]
        
        try:
            return transport_class(server_name, config)
        except Exception as e:
            raise ConnectionError(
                f"Failed to create {transport_type} transport for server '{server_name}': {e}",
                server_name=server_name,
                transport_type=transport_type,
                cause=e
            )
    
    @classmethod
    def get_supported_transports(cls) -> list[str]:
        """Get list of supported transport types.
        
        Returns:
            List of supported transport type names
        """
        return list(cls._transport_classes.keys())
    
    @classmethod
    def is_transport_supported(cls, transport_type: str) -> bool:
        """Check if a transport type is supported.
        
        Args:
            transport_type: Transport type to check
            
        Returns:
            True if supported, False otherwise
        """
        return transport_type in cls._transport_classes


class BaseTransport(TransportInterface):
    """Base implementation of TransportInterface with common functionality.
    
    This class provides common functionality that can be shared across
    different transport implementations, reducing code duplication.
    """
    
    def __init__(self, server_name: str, config: ServerConfig) -> None:
        """Initialize the base transport.
        
        Args:
            server_name: Name of the server
            config: Server configuration
        """
        super().__init__(server_name, config)
        self._read_stream: Optional[ReadStream] = None
        self._write_stream: Optional[WriteStream] = None
        self._connection_start_time: Optional[float] = None
    
    async def connect(self) -> Tuple[ReadStream, WriteStream]:
        """Establish connection and return streams.
        
        This method handles common connection logic and delegates
        the actual connection establishment to _do_connect().
        
        Returns:
            Tuple of (read_stream, write_stream)
            
        Raises:
            ConnectionError: If already connected or connection fails
        """
        if self._is_connected:
            raise ConnectionError(
                f"Transport for server '{self.server_name}' is already connected",
                server_name=self.server_name,
                transport_type=self.config.transport
            )
        
        try:
            import time
            self._connection_start_time = time.time()
            
            # Delegate to subclass implementation
            self._read_stream, self._write_stream = await self._do_connect()
            
            # Update connection state and metadata
            self._set_connected(True)
            self._update_metadata(
                connection_time=self._connection_start_time,
                transport_type=self.config.transport,
                server_name=self.server_name
            )
            
            return self._read_stream, self._write_stream
            
        except Exception as e:
            self._set_connected(False)
            self._clear_metadata()
            
            if isinstance(e, (ConnectionError, TimeoutError)):
                raise
            
            raise ConnectionError(
                f"Failed to connect to server '{self.server_name}': {e}",
                server_name=self.server_name,
                transport_type=self.config.transport,
                cause=e
            )
    
    async def disconnect(self) -> None:
        """Disconnect and clean up resources.
        
        This method handles common disconnection logic and delegates
        the actual disconnection to _do_disconnect().
        
        Raises:
            ConnectionError: If disconnection fails
        """
        if not self._is_connected:
            return  # Already disconnected
        
        try:
            # Delegate to subclass implementation
            await self._do_disconnect()
            
        except Exception as e:
            raise ConnectionError(
                f"Failed to disconnect from server '{self.server_name}': {e}",
                server_name=self.server_name,
                transport_type=self.config.transport,
                cause=e
            )
        finally:
            # Always clean up state
            self._set_connected(False)
            self._clear_metadata()
            self._read_stream = None
            self._write_stream = None
            self._connection_start_time = None
    
    @abstractmethod
    async def _do_connect(self) -> Tuple[ReadStream, WriteStream]:
        """Perform the actual connection establishment.
        
        Subclasses must implement this method to handle transport-specific
        connection logic.
        
        Returns:
            Tuple of (read_stream, write_stream)
            
        Raises:
            ConnectionError: If connection fails
            TimeoutError: If connection times out
        """
        pass
    
    @abstractmethod
    async def _do_disconnect(self) -> None:
        """Perform the actual disconnection.
        
        Subclasses must implement this method to handle transport-specific
        disconnection logic.
        
        Raises:
            ConnectionError: If disconnection fails
        """
        pass