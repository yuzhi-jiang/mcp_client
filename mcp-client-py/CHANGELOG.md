# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Test suite under `tests/`: config/env resolution, transport validation, argument
  validation, retry policy, tool-calling loop, streaming fragment merging, CLI, and
  end-to-end stdio tests against a demo MCP server (`tests/mcp_demo_server.py`).
- `docs/architecture.md`: layer map, connect/call sequences, error model, extension
  points, and the task-affinity constraint behind sequential connect/disconnect.
- README rewritten around verified behaviour: compatibility matrix, real test/coverage
  numbers, and a documented list of limitations.

### Fixed
- **MCP SDK 2.x compatibility.** `ReadStream`/`WriteStream` are no longer exported from
  `mcp.types`; they are now resolved through `mcp_client/transport/streams.py`.
  Tool discovery read `inputSchema` and tool errors read `isError`, both renamed to
  snake_case in SDK 2.x — tool discovery failed and tool errors were silently treated as
  successes.
- **Streaming tool calls were lost on the final chunk.** Tool calls were only attached to
  chunks that carried a `delta`, so the terminating chunk (only `finish_reason`) reported
  `tool_calls=None`. They are now merged by stream index and attached to every chunk.
- **CancelledError / "cancel scope exited in a different task" on connect and
  disconnect.** Sessions were created inside `asyncio.gather()` child tasks, which cannot
  exit an anyio cancel scope, and the transport was closed before the session that reads
  from it. Connections are now established sequentially in the caller's task and sessions
  are closed before their transport.
- **`NameError` masked configuration errors.** `config/manager.py` used `ValidationError`
  without importing it, so any invalid configuration surfaced as `NameError`.
- **Default config required environment variables.** `create_default_config()` used
  `${API_TOKEN}` / `${OPENAI_API_KEY}` without defaults, so the shipped template failed to
  load on a clean machine.
- CLI printed non-text tool results with `json.dumps` on pydantic objects, which raised
  `TypeError`; content items are now rendered according to their actual shape.
- Replaced deprecated `asyncio.iscoroutinefunction` with `inspect.iscoroutinefunction`.

### Changed
- `requires-python` is now `>=3.10` (the MCP SDK's own floor); classifiers updated and
  stale `your-username` project URLs corrected.
- Early structural smoke tests moved to `tests/legacy/`.

### Added (existing)
- Initial release of MCP Client library
- Multi-server connection management
- Tool discovery and execution
- LLM integration with OpenAI-compatible APIs
- Async/await support throughout
- Comprehensive error handling
- Configuration management with environment variable support
- Automatic reconnection and retry policies
- Command-line interface
- Structured logging
- Type hints and runtime validation
- Extensible transport layer (STDIO, SSE)
- Conversation management
- Examples and documentation

### Features
- **MCPClient**: Main client interface for MCP operations
- **Configuration**: JSON-based configuration with validation
- **Transport Layer**: Pluggable transport system (STDIO, SSE)
- **Tool Management**: Automatic tool discovery and execution
- **LLM Integration**: OpenAI adapter with streaming support
- **Connection Management**: Health monitoring and auto-reconnect
- **CLI Tool**: Command-line interface for easy interaction
- **Error Handling**: Comprehensive exception hierarchy
- **Logging**: Structured logging with configurable levels
- **Validation**: Runtime validation with detailed error messages

### Technical Details
- Python 3.8+ support
- Fully async/await based
- Type hints throughout
- Comprehensive test suite
- Pre-commit hooks for code quality
- Modular architecture following SOLID principles
- Plugin system for extensibility

## [0.1.0] - 2024-01-XX

### Added
- Initial project structure
- Core MCP client functionality
- Basic documentation
- Example configurations
- MIT license

---

## Release Notes

### Version 0.1.0

This is the initial release of MCP Client, a Python library for connecting to Model Context Protocol servers with seamless LLM integration.

#### Key Features

1. **Multi-Server Support**: Connect to multiple MCP servers simultaneously with different transport types.

2. **Tool Management**: Automatic discovery and execution of tools from connected servers with comprehensive validation.

3. **LLM Integration**: Built-in support for OpenAI and compatible APIs with conversation management.

4. **Extensible Architecture**: Plugin system for custom transports and LLM providers.

5. **Robust Error Handling**: Comprehensive exception hierarchy with detailed error context.

6. **Configuration Management**: JSON-based configuration with environment variable support and validation.

7. **CLI Tool**: Command-line interface for easy interaction and testing.

#### Breaking Changes

None (initial release).

#### Migration Guide

This is the initial release, so no migration is needed.

#### Known Issues

- None at this time.

#### Deprecations

None (initial release).

---

## Development Notes

### Versioning Strategy

This project follows [Semantic Versioning](https://semver.org/):

- **MAJOR** version for incompatible API changes
- **MINOR** version for backwards-compatible functionality additions
- **PATCH** version for backwards-compatible bug fixes

### Release Process

1. Update version in `pyproject.toml`
2. Update `CHANGELOG.md` with release notes
3. Create release tag
4. Build and publish to PyPI
5. Update documentation

### Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on contributing to this project.