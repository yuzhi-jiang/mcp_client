"""Basic usage example for MCP Client."""

import asyncio
import json
from pathlib import Path

from mcp_client import MCPClient, Config


async def basic_example():
    """Basic example showing how to use MCP Client."""
    
    # Example 1: Create client from configuration file
    print("=== Example 1: Loading from config file ===")
    
    # Create a sample configuration
    config_data = {
        "servers": {
            "example_server": {
                "transport": "stdio",
                "command": "python",
                "args": ["-c", "print('Hello from MCP server!')"],
                "disabled": True  # Disabled for this example
            }
        },
        "default_timeout": 30.0,
        "log_level": "INFO"
    }
    
    # Save sample config
    config_path = Path("example_config.json")
    with open(config_path, 'w') as f:
        json.dump(config_data, f, indent=2)
    
    try:
        # Load client from config file
        client = MCPClient.from_config_file(config_path)
        print(f"Client created with {len(client.config.servers)} configured servers")
        
        # Since our example server is disabled, we won't actually connect
        print("Example server is disabled, so no actual connection will be made")
        
    finally:
        # Clean up
        config_path.unlink(missing_ok=True)
    
    print("\n=== Example 2: Creating client from dictionary ===")
    
    # Example 2: Create client from dictionary
    config_dict = {
        "servers": {
            "mock_server": {
                "transport": "stdio", 
                "command": "echo",
                "args": ["Mock server response"],
                "disabled": True  # Disabled for this example
            }
        },
        "log_level": "DEBUG"
    }
    
    client = MCPClient.from_dict(config_dict)
    print(f"Client created from dictionary with {len(client.config.servers)} servers")
    
    # Get client statistics
    stats = client.get_client_stats()
    print(f"Client stats: {json.dumps(stats, indent=2)}")
    
    print("\n=== Example 3: Using async context manager ===")
    
    # Example 3: Using async context manager (recommended)
    config = Config.from_dict(config_dict)
    
    # Note: Since we don't have real MCP servers running, 
    # we'll just demonstrate the API without actually connecting
    try:
        async with MCPClient(config) as client:
            print("Client created and would connect here")
            print(f"Connected servers: {client.get_connected_servers()}")
            print(f"Available tools: {client.get_tool_names()}")
            
            # Example tool operations (would work with real servers)
            # tools = client.get_tools()
            # result = await client.call_tool("example_tool", {"param": "value"})
            
    except Exception as e:
        print(f"Expected error (no real servers): {e}")
    
    print("\nBasic usage examples completed!")


async def llm_integration_example():
    """Example showing LLM integration (requires API key)."""
    
    print("\n=== LLM Integration Example ===")
    
    # Configuration with LLM settings
    config_dict = {
        "servers": {
            # Add your MCP servers here
        },
        "llm_provider": "openai",
        "llm_api_key": "${OPENAI_API_KEY}",  # Set this environment variable
        "llm_model": "gpt-4",
        "log_level": "INFO"
    }
    
    try:
        client = MCPClient.from_dict(config_dict)
        
        if client.has_llm_integration():
            print("LLM integration is available")
            
            # Set a system prompt
            client.set_system_prompt("You are a helpful assistant with access to MCP tools.")
            
            # Example chat (would work with proper API key and MCP servers)
            # response = await client.chat("Hello! What tools do you have available?")
            # print(f"Assistant: {response.content}")
            
        else:
            print("LLM integration not available (API key not configured)")
            
    except Exception as e:
        print(f"LLM integration example failed: {e}")


if __name__ == "__main__":
    asyncio.run(basic_example())
    asyncio.run(llm_integration_example())