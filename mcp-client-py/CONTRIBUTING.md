# Contributing to MCP Client

Thank you for your interest in contributing to MCP Client! This document provides guidelines and information for contributors.

## Code of Conduct

This project adheres to a code of conduct. By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainers.

## How to Contribute

### Reporting Issues

Before creating an issue, please:

1. **Search existing issues** to avoid duplicates
2. **Use the issue template** if available
3. **Provide detailed information** including:
   - Python version
   - MCP Client version
   - Operating system
   - Steps to reproduce
   - Expected vs actual behavior
   - Error messages and stack traces

### Suggesting Features

Feature requests are welcome! Please:

1. **Check existing feature requests** first
2. **Describe the use case** clearly
3. **Explain why this feature would be valuable**
4. **Consider implementation complexity**

### Contributing Code

#### Development Setup

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/your-username/mcp-client-py.git
   cd mcp-client-py
   ```

3. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

4. **Install development dependencies**:
   ```bash
   pip install -e ".[dev]"
   ```

5. **Install pre-commit hooks**:
   ```bash
   pre-commit install
   ```

#### Making Changes

1. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** following the coding standards below

3. **Write or update tests** for your changes

4. **Run the test suite**:
   ```bash
   pytest
   ```

5. **Run code quality checks**:
   ```bash
   black .
   isort .
   flake8
   mypy .
   ```

6. **Commit your changes**:
   ```bash
   git add .
   git commit -m "Add feature: your feature description"
   ```

7. **Push to your fork**:
   ```bash
   git push origin feature/your-feature-name
   ```

8. **Create a Pull Request** on GitHub

#### Pull Request Guidelines

- **Use a clear, descriptive title**
- **Reference related issues** using `#issue-number`
- **Describe your changes** in detail
- **Include tests** for new functionality
- **Update documentation** if needed
- **Ensure CI passes** before requesting review

## Coding Standards

### Python Style

We follow [PEP 8](https://pep8.org/) with some modifications:

- **Line length**: 88 characters (Black default)
- **Import sorting**: Use `isort` with Black-compatible settings
- **Type hints**: Required for all public APIs
- **Docstrings**: Google-style docstrings for all public functions/classes

### Code Quality Tools

We use several tools to maintain code quality:

- **Black**: Code formatting
- **isort**: Import sorting
- **flake8**: Linting
- **mypy**: Type checking
- **pytest**: Testing
- **pre-commit**: Git hooks

### Architecture Principles

Follow these principles when contributing:

1. **SOLID Principles**: Especially Single Responsibility and Open-Closed
2. **Dependency Injection**: Use dependency injection for testability
3. **Error Handling**: Comprehensive error handling with specific exceptions
4. **Async/Await**: Use async/await for all I/O operations
5. **Type Safety**: Provide complete type hints
6. **Documentation**: Document all public APIs

### Testing Guidelines

#### Test Structure

```
tests/
├── unit/              # Unit tests
│   ├── test_config.py
│   ├── test_client.py
│   └── ...
├── integration/       # Integration tests
│   ├── test_workflows.py
│   └── ...
├── fixtures/          # Test fixtures
│   ├── configs/
│   └── mock_servers/
└── conftest.py       # Pytest configuration
```

#### Writing Tests

- **Use descriptive test names**: `test_should_connect_to_server_when_config_valid`
- **Follow AAA pattern**: Arrange, Act, Assert
- **Mock external dependencies**: Use `pytest-mock` for mocking
- **Test error conditions**: Include negative test cases
- **Use fixtures**: Create reusable test fixtures

#### Test Examples

```python
import pytest
from mcp_client import MCPClient, ConfigurationError

class TestMCPClient:
    def test_should_raise_error_when_config_file_missing(self):
        """Test that MCPClient raises ConfigurationError for missing config."""
        with pytest.raises(ConfigurationError, match="Configuration file not found"):
            MCPClient.from_config_file("nonexistent.json")
    
    @pytest.mark.asyncio
    async def test_should_connect_successfully_with_valid_config(self, valid_config):
        """Test successful connection with valid configuration."""
        client = MCPClient(valid_config)
        
        async with client:
            assert client.is_connected()
            assert len(client.get_connected_servers()) > 0
```

### Documentation

#### Code Documentation

- **Docstrings**: All public functions, classes, and methods
- **Type hints**: Complete type annotations
- **Comments**: Explain complex logic, not obvious code
- **Examples**: Include usage examples in docstrings

#### Documentation Format

Use Google-style docstrings:

```python
def example_function(param1: str, param2: int = 0) -> bool:
    """Brief description of the function.
    
    Longer description if needed, explaining the purpose,
    behavior, and any important details.
    
    Args:
        param1: Description of param1
        param2: Description of param2 with default value
        
    Returns:
        Description of return value
        
    Raises:
        ValueError: When param1 is empty
        ConnectionError: When connection fails
        
    Example:
        >>> result = example_function("test", 42)
        >>> print(result)
        True
    """
    pass
```

## Project Structure

Understanding the project structure helps with contributions:

```
mcp-client-py/
├── mcp_client/           # Main package
│   ├── __init__.py      # Package exports
│   ├── client.py        # Main MCPClient class
│   ├── config/          # Configuration management
│   │   ├── __init__.py
│   │   ├── manager.py   # ConfigManager
│   │   ├── models.py    # Data models
│   │   └── validator.py # Validation
│   ├── connection/      # Connection management
│   │   ├── __init__.py
│   │   └── manager.py   # ConnectionManager
│   ├── transport/       # Transport layer
│   │   ├── __init__.py
│   │   ├── base.py      # Interfaces
│   │   ├── stdio.py     # STDIO transport
│   │   └── sse.py       # SSE transport
│   ├── tools/           # Tool management
│   │   ├── __init__.py
│   │   ├── manager.py   # ToolManager
│   │   └── executor.py  # ToolExecutor
│   ├── llm/            # LLM integration
│   │   ├── __init__.py
│   │   ├── base.py      # Interfaces
│   │   ├── openai.py    # OpenAI adapter
│   │   └── conversation.py # ConversationManager
│   ├── utils/          # Utilities
│   │   ├── __init__.py
│   │   ├── logging.py   # Logging config
│   │   ├── retry.py     # Retry utilities
│   │   └── validation.py # Validation utils
│   ├── cli.py          # Command-line interface
│   └── exceptions.py   # Exception classes
├── examples/           # Usage examples
├── tests/             # Test suite
├── docs/              # Documentation
├── pyproject.toml     # Project configuration
├── README.md          # Project README
├── CHANGELOG.md       # Change log
├── CONTRIBUTING.md    # This file
└── LICENSE           # MIT license
```

## Areas for Contribution

We welcome contributions in these areas:

### High Priority
- **Additional LLM Providers**: Anthropic, Cohere, local models
- **Transport Implementations**: WebSocket, HTTP, custom protocols
- **Performance Optimizations**: Connection pooling, caching
- **Error Recovery**: Better retry strategies, circuit breakers

### Medium Priority
- **Monitoring**: Metrics collection, health checks
- **Security**: Authentication, encryption, sandboxing
- **Documentation**: Tutorials, API docs, examples
- **Testing**: More test coverage, integration tests

### Low Priority
- **CLI Enhancements**: Interactive mode, configuration wizard
- **Utilities**: Configuration migration, debugging tools
- **Examples**: Real-world use cases, integrations

## Release Process

For maintainers:

1. **Update version** in `pyproject.toml`
2. **Update CHANGELOG.md** with release notes
3. **Create release tag**: `git tag v0.1.0`
4. **Push tag**: `git push origin v0.1.0`
5. **GitHub Actions** will build and publish to PyPI
6. **Create GitHub release** with release notes

## Getting Help

If you need help:

1. **Check the documentation** first
2. **Search existing issues** and discussions
3. **Ask in GitHub Discussions** for general questions
4. **Create an issue** for bugs or feature requests
5. **Contact maintainers** for sensitive issues

## Recognition

Contributors will be recognized in:

- **CHANGELOG.md** for significant contributions
- **README.md** contributors section
- **GitHub contributors** page
- **Release notes** for major features

Thank you for contributing to MCP Client! 🎉