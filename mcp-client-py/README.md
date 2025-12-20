# MCP Client

A Python library for connecting to Model Context Protocol (MCP) servers with seamless LLM integration.

## Features

- 🔌 **Multi-Server Support**: Connect to multiple MCP servers simultaneously
- 🛠️ **Tool Management**: Automatic tool discovery and execution with validation
- 🤖 **LLM Integration**: Built-in adapters for OpenAI and compatible APIs
- ⚡ **Async/Await**: Full async support for high performance
- 🔧 **Extensible**: Plugin architecture for custom transports and LLM providers
- 📝 **Type Safe**: Complete type hints and runtime validation
- 🔄 **Auto-Reconnect**: Automatic reconnection with configurable retry policies
- 🧪 **Well Tested**: Comprehensive test suite with >90% coverage
- 📊 **Monitoring**: Built-in logging and connection health monitoring
- 🎯 **CLI Tool**: Command-line interface for easy interaction

## Quick Start

### Installation

```bash
pip install mcp-client
```

### Basic Usage

```python
import asyncio
from mcp_client import MCPClient

async def main():
    # Create client from config file
    client = MCPClient.from_config_file("mcp_config.json")
    
    # Use async context manager for automatic cleanup
    async with client:
        # Get available tools
        tools = client.get_tools()
        print(f"Available tools: {[tool.name for tool in tools]}")
        
        # Call a tool
        result = await client.call_tool("calculator", {
            "operation": "add", 
            "a": 5, 
            "b": 3
        })
        print(f"Result: {result.content}")
        
        # Chat with LLM integration (if configured)
        if client.has_llm_integration():
            response = await client.chat("What tools do you have available?")
            print(f"Assistant: {response.content}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Configuration

Create a `mcp_config.json` file:

```json
{
  "servers": {
    "calculator": {
      "transport": "stdio",
      "command": "python",
      "args": ["-m", "calculator_server"],
      "env": {
        "CALCULATOR_MODE": "advanced"
      }
    },
    "web_search": {
      "transport": "sse",
      "url": "https://api.example.com/mcp",
      "headers": {
        "Authorization": "Bearer ${API_TOKEN}"
      }
    }
  },
  "llm_provider": "openai",
  "llm_api_key": "${OPENAI_API_KEY}",
  "llm_model": "gpt-4",
  "log_level": "INFO"
}
```

### Command Line Interface

```bash
# Create a sample configuration
mcp-client create-config

# List configured servers
mcp-client list-servers

# List available tools
mcp-client list-tools

# Call a tool
mcp-client call-tool calculator '{"operation": "add", "a": 5, "b": 3}'

# Interactive chat (requires LLM configuration)
mcp-client chat

# Show status
mcp-client status
```

## Advanced Usage

### Custom Transport

```python
from mcp_client import TransportInterface, TransportFactory

class CustomTransport(TransportInterface):
    async def connect(self):
        # Implement custom connection logic
        pass
    
    async def disconnect(self):
        # Implement cleanup
        pass

# Register custom transport
TransportFactory.register_transport("custom", CustomTransport)
```

### Custom LLM Adapter

```python
from mcp_client import LLMAdapterInterface, LLMAdapterFactory

class CustomLLMAdapter(LLMAdapterInterface):
    async def chat_completion(self, messages, tools=None, **kwargs):
        # Implement custom LLM integration
        pass

# Register custom adapter
LLMAdapterFactory.register_adapter("custom_llm", CustomLLMAdapter)
```

### Environment Variables

The library supports environment variable substitution in configuration:

```json
{
  "servers": {
    "secure_server": {
      "transport": "sse",
      "url": "${SERVER_URL}",
      "headers": {
        "Authorization": "Bearer ${API_TOKEN:default_token}"
      }
    }
  },
  "llm_api_key": "${OPENAI_API_KEY}"
}
```

### Conversation Management

```python
async with MCPClient.from_config_file("config.json") as client:
    # Set system prompt
    client.set_system_prompt("You are a helpful assistant with access to tools.")
    
    # Chat with automatic tool execution
    response = await client.chat("Calculate 15 * 23 and then search for information about the result")
    
    # Save conversation
    client.save_conversation("conversation.json")
    
    # Load conversation later
    client.load_conversation("conversation.json")
```

## Configuration Reference

### Server Configuration

| Field | Type | Description |
|-------|------|-------------|
| `transport` | string | Transport type: "stdio" or "sse" |
| `command` | string | Command to execute (stdio only) |
| `args` | array | Command arguments (stdio only) |
| `url` | string | Server URL (sse only) |
| `env` | object | Environment variables |
| `headers` | object | HTTP headers (sse only) |
| `timeout` | number | Connection timeout in seconds |
| `disabled` | boolean | Whether server is disabled |
| `auto_reconnect` | boolean | Enable automatic reconnection |
| `max_retries` | number | Maximum retry attempts |

### Global Configuration

| Field | Type | Description |
|-------|------|-------------|
| `default_timeout` | number | Default timeout for operations |
| `max_retries` | number | Default max retries |
| `log_level` | string | Logging level |
| `llm_provider` | string | LLM provider name |
| `llm_api_key` | string | LLM API key |
| `llm_base_url` | string | LLM API base URL |
| `llm_model` | string | LLM model name |

## Error Handling

The library provides comprehensive error handling with specific exception types:

```python
from mcp_client import (
    MCPClientError,
    ConnectionError,
    ToolExecutionError,
    ValidationError,
    TimeoutError,
    AuthenticationError
)

try:
    async with MCPClient.from_config_file("config.json") as client:
        result = await client.call_tool("nonexistent_tool", {})
except ValidationError as e:
    print(f"Validation error: {e}")
except ToolExecutionError as e:
    print(f"Tool execution failed: {e}")
except ConnectionError as e:
    print(f"Connection error: {e}")
except MCPClientError as e:
    print(f"General MCP error: {e}")
```

## Development

### Setup

```bash
git clone https://github.com/your-username/mcp-client-py
cd mcp-client-py
pip install -e ".[dev]"
pre-commit install
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=mcp_client --cov-report=html

# Run specific test file
pytest tests/test_client.py
```

### Code Quality

```bash
# Format code
black .
isort .

# Lint code
flake8
mypy .

# Run all quality checks
pre-commit run --all-files
```

### Project Structure

```
mcp-client-py/
├── mcp_client/           # Main package
│   ├── __init__.py      # Package exports
│   ├── client.py        # Main MCPClient class
│   ├── config/          # Configuration management
│   ├── connection/      # Connection management
│   ├── transport/       # Transport layer
│   ├── tools/           # Tool management
│   ├── llm/            # LLM integration
│   ├── utils/          # Utilities
│   └── exceptions.py   # Exception classes
├── examples/           # Usage examples
├── tests/             # Test suite
├── docs/              # Documentation
└── pyproject.toml     # Project configuration
```

## Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Areas for Contribution

- Additional LLM provider adapters
- New transport implementations
- Performance optimizations
- Documentation improvements
- Test coverage expansion
- Bug fixes and feature requests

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for a list of changes and releases.

## Support

- 📖 [Documentation](docs/)
- 🐛 [Issue Tracker](https://github.com/your-username/mcp-client-py/issues)
- 💬 [Discussions](https://github.com/your-username/mcp-client-py/discussions)
- 📧 [Email Support](mailto:contact@example.com)