"""Basic functionality test for MCP Client."""

import asyncio
import json
import tempfile
from pathlib import Path

from mcp_client import MCPClient, Config, ConfigManager


def test_config_creation():
    """Test configuration creation and validation."""
    print("Testing configuration creation...")
    
    # Test creating config from dictionary
    config_dict = {
        "servers": {
            "test_server": {
                "transport": "stdio",
                "command": "echo",
                "args": ["hello"],
                "disabled": True
            }
        },
        "log_level": "INFO"
    }
    
    config = Config.from_dict(config_dict)
    assert len(config.servers) == 1
    assert "test_server" in config.servers
    assert config.servers["test_server"].transport == "stdio"
    assert config.log_level == "INFO"
    
    print("✓ Configuration creation works")


def test_config_file_operations():
    """Test configuration file operations."""
    print("Testing configuration file operations...")
    
    # Create temporary config file
    config_data = ConfigManager.create_default_config()
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(config_data, f, indent=2)
        temp_path = f.name
    
    try:
        # Test loading from file
        config = ConfigManager.load_config(temp_path)
        assert len(config.servers) > 0
        
        # Test saving config
        new_path = temp_path + ".new"
        ConfigManager.save_config(config, new_path)
        
        # Verify saved config can be loaded
        config2 = ConfigManager.load_config(new_path)
        assert len(config2.servers) == len(config.servers)
        
        Path(new_path).unlink()
        
    finally:
        Path(temp_path).unlink()
    
    print("✓ Configuration file operations work")


def test_client_creation():
    """Test MCP client creation."""
    print("Testing MCP client creation...")
    
    # Test creating client from config dict
    config_dict = {
        "servers": {
            "mock_server": {
                "transport": "stdio",
                "command": "echo",
                "args": ["test"],
                "disabled": True  # Disabled so we don't actually try to connect
            }
        },
        "log_level": "DEBUG"
    }
    
    client = MCPClient.from_dict(config_dict)
    assert client is not None
    assert len(client.config.servers) == 1
    assert not client.is_connected()
    
    print("✓ MCP client creation works")


async def test_client_lifecycle():
    """Test MCP client lifecycle without actual connections."""
    print("Testing MCP client lifecycle...")
    
    config_dict = {
        "servers": {
            "disabled_server": {
                "transport": "stdio",
                "command": "echo",
                "args": ["test"],
                "disabled": True
            }
        }
    }
    
    client = MCPClient.from_dict(config_dict)
    
    # Test that client starts disconnected
    assert not client.is_connected()
    assert len(client.get_connected_servers()) == 0
    
    # Test client stats
    stats = client.get_client_stats()
    assert "is_connected" in stats
    assert "connected_servers" in stats
    assert "tool_statistics" in stats
    
    print("✓ MCP client lifecycle works")


def test_transport_factory():
    """Test transport factory registration."""
    print("Testing transport factory...")
    
    from mcp_client.transport.base import TransportFactory
    from mcp_client.transport.stdio import StdioTransport
    from mcp_client.transport.sse import SSETransport
    
    # Test that built-in transports are registered
    supported = TransportFactory.get_supported_transports()
    assert "stdio" in supported
    assert "sse" in supported
    
    # Test transport creation
    from mcp_client.config.models import ServerConfig
    
    stdio_config = ServerConfig(
        transport="stdio",
        command="echo",
        args=["test"]
    )
    
    transport = TransportFactory.create_transport("test", stdio_config)
    assert isinstance(transport, StdioTransport)
    
    print("✓ Transport factory works")


def test_llm_adapter_factory():
    """Test LLM adapter factory."""
    print("Testing LLM adapter factory...")
    
    from mcp_client.llm.base import LLMAdapterFactory
    
    # Test that OpenAI adapter is registered
    supported = LLMAdapterFactory.get_supported_providers()
    assert "openai" in supported
    
    print("✓ LLM adapter factory works")


def test_exception_hierarchy():
    """Test exception hierarchy."""
    print("Testing exception hierarchy...")
    
    from mcp_client.exceptions import (
        MCPClientError,
        ConfigurationError,
        ConnectionError,
        ToolExecutionError,
        ValidationError
    )
    
    # Test exception creation with context
    error = ConfigurationError(
        "Test error",
        config_path="/test/path",
        field_name="test_field"
    )
    
    assert "config_path" in error.context
    assert "field_name" in error.context
    assert isinstance(error, MCPClientError)
    
    print("✓ Exception hierarchy works")


def run_all_tests():
    """Run all tests."""
    print("Running MCP Client basic functionality tests...\n")
    
    try:
        # Synchronous tests
        test_config_creation()
        test_config_file_operations()
        test_client_creation()
        test_transport_factory()
        test_llm_adapter_factory()
        test_exception_hierarchy()
        
        # Asynchronous tests
        asyncio.run(test_client_lifecycle())
        
        print("\n🎉 All tests passed! The MCP Client implementation is working correctly.")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)