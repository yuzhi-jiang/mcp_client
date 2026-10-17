# MCP Client

A Python client for the [Model Context Protocol](https://modelcontextprotocol.io) (MCP) that
connects to several MCP servers at once, discovers their tools, and drives the whole
tool-calling loop against an OpenAI-compatible model.

It is meant to be the piece that is usually missing when you want to *use* MCP from a
script or a terminal: a small library plus a CLI that speaks the protocol directly,
instead of relying on a desktop app.

```text
$ mcp-client --config mcp_config.json list-tools
calculator.add
calculator.divide
filesystem.read_file
```

## Why

Most MCP tooling in early 2025 was either a desktop client or a single-server demo.
Wiring a model to several servers meant writing the same glue every time: spawn the
server, initialize a session, list tools, translate the schema into the model's `tools`
parameter, run the call, feed the result back, repeat. This project packages that loop
once.

## Features

- **Multi-server** — connect to any number of MCP servers in one client; sessions are
  tracked per server and a failing server does not take the others down.
- **Two transports** — `stdio` (subprocess) and `sse` (HTTP), behind a common
  `BaseTransport` interface and factory.
- **Tool discovery + argument validation** — tools are read from `tools/list` and their
  JSON Schema is enforced client-side (required fields, types, nested objects/arrays,
  `additionalProperties: false`) *before* anything is sent to the server.
- **Retries for transient failures** — connection/timeout errors are retried with
  exponential backoff and jitter; validation and tool errors fail fast.
- **LLM integration** — OpenAI-compatible adapter with a bounded multi-round
  tool-calling loop (default max 5 iterations), so the model can chain tool calls.
- **Streaming** — `tool_calls` fragments are merged by stream `index` (the name arrives
  in the first fragment, arguments arrive as string chunks).
- **Configuration** — JSON files, pydantic models, `${VAR}` / `${VAR:default}`
  environment interpolation.
- **CLI** — `list-servers`, `list-tools`, `call-tool`, `chat`, `status`,
  `create-config`.
- **Type hints** — ships `py.typed`.

## Installation

Requires **Python 3.10+** (the MCP SDK requires it). The package is not published on
PyPI yet — install from source:

```bash
git clone https://github.com/yuzhi-jiang/mcp_client.git
cd mcp_client/mcp-client-py
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Quick start

### 1. Configuration

`mcp_config.json`:

```json
{
  "servers": {
    "calculator": {
      "transport": "stdio",
      "command": "python",
      "args": ["-m", "my_calculator_server"]
    },
    "search": {
      "transport": "sse",
      "url": "https://api.example.com/mcp",
      "headers": {"Authorization": "Bearer ${API_TOKEN}"}
    }
  },
  "max_retries": 3,
  "log_level": "INFO",
  "llm_provider": "openai",
  "llm_api_key": "${OPENAI_API_KEY}",
  "llm_model": "gpt-4o-mini"
}
```

Environment variables support a default: `${API_TOKEN:dev-token}`.

### 2. Call a tool

```python
import asyncio
from mcp_client import MCPClient

async def main() -> None:
    client = MCPClient.from_config_file("mcp_config.json")
    async with client:
        print([tool.name for tool in client.get_tools()])
        result = await client.call_tool("add", {"a": 2, "b": 3})
        print(result.content)

asyncio.run(main())
```

### 3. Let a model drive the tools

```python
async with MCPClient.from_config_file("mcp_config.json") as client:
    answer = await client.chat("What is 2 + 3? Use the available tools.")
    print(answer.content)
```

The conversation manager sends the tool schemas to the model, executes the returned
calls, feeds the results back, and repeats until the model stops requesting tools or the
iteration cap is hit.

## CLI

| Command | Description |
| --- | --- |
| `mcp-client --config FILE list-servers` | Show configured servers |
| `mcp-client --config FILE list-tools` | List discovered tools |
| `mcp-client --config FILE call-tool NAME '{"k": "v"}'` | Call one tool and print the result |
| `mcp-client --config FILE chat "question"` | Chat through the configured LLM (`--stream` for streaming) |
| `mcp-client --config FILE status` | Connection and tool statistics |
| `mcp-client create-config -o FILE` | Write a sample configuration |

## Architecture

```text
        ┌─────────────────────────────┐
        │           CLI (click)       │
        └──────────────┬──────────────┘
                       │
        ┌──────────────▼──────────────┐      ┌──────────────────────┐
        │          MCPClient          │─────▶│ ConversationManager  │
        │  connect / call_tool / chat │      │  tool-calling loop   │
        └──────┬───────────────┬──────┘      └──────────┬───────────┘
               │               │                        │
   ┌───────────▼──────┐  ┌─────▼─────────┐      ┌───────▼────────┐
   │ ConnectionManager│  │  ToolManager  │      │  LLM adapter   │
   │  per-server      │  │  discovery +  │      │  (OpenAI-API)  │
   │  sessions        │  │  registry     │      └────────────────┘
   └───────────┬──────┘  └─────┬─────────┘
               │               │
   ┌───────────▼──────┐  ┌─────▼─────────┐
   │ TransportFactory │  │ ToolExecutor  │
   │  stdio │ sse     │  │ validate/call │
   └───────────┬──────┘  └───────────────┘
               │
   ┌───────────▼──────────────┐
   │  MCP SDK (mcp package)   │
   └──────────────────────────┘
```

See [docs/architecture.md](docs/architecture.md) for the connection sequence, the
tool-calling loop, the error model and the extension points.

## Compatibility

| Component | Supported | Notes |
| --- | --- | --- |
| Python | 3.10 – 3.14 | Test suite runs on 3.14.7 |
| `mcp` SDK | 1.x and 2.x | Stream types go through a compatibility shim; `Tool.input_schema` vs `inputSchema` and `CallToolResult.is_error` vs `isError` are both handled |
| LLM providers | OpenAI-compatible APIs | Anything exposing `/chat/completions` with tool calling |

The SDK 2.x migration renamed `FastMCP` to `MCPServer`, moved the stream protocols and
switched several result fields to snake_case. This project hides those differences;
`tests/mcp_demo_server.py` shows the version-tolerant import for servers.

## Testing

```bash
pytest                      # unit + integration (spawns a real MCP server)
pytest -m "not integration" # fast unit tests only
pytest -m integration       # end-to-end stdio tests
pytest --cov=mcp_client     # coverage
```

Current state: **72 tests passing, 67% line coverage** (Python 3.14.7, `mcp` 2.3.0).
The integration tests start `tests/mcp_demo_server.py` as a subprocess and exercise the
real `initialize → tools/list → tools/call` path over stdio, including error propagation
and partial-failure behaviour.

| Suite | Covers |
| --- | --- |
| `test_config.py` | config loading, env interpolation, validation errors |
| `test_transport.py` | factory, per-transport config validation, stream shim |
| `test_tool_executor.py` | argument validation, result/error mapping |
| `test_retry.py` | retry policy: transient vs permanent failures |
| `test_llm_tool_loop.py` | multi-round tool-calling loop, iteration cap |
| `test_conversation_stream.py` | streaming accumulation, history trimming |
| `test_openai_stream.py` | `tool_calls` fragment merging by index |
| `test_e2e_stdio.py` | real server: discovery, calls, errors, multi-server |
| `test_cli.py` | CLI commands against a real server |
| `test_validation_utils.py` | JSON Schema and scalar validators |

`tests/legacy/` keeps the early structural smoke tests.

## Known limitations

- **Streaming does not execute tools.** Streaming returns the calls for inspection; the
  automatic loop is non-streaming only.
- **SSE transport has no live end-to-end test.** Only its configuration validation is
  covered; the client path needs a reachable SSE server.
- **Retries are narrow by design.** Only connection/timeout errors are retried; tool
  errors are surfaced immediately rather than retried.
- **No OAuth / mTLS.** Auth is limited to headers (Bearer tokens and similar).
- **Tool name collisions** across servers are resolved first-wins, with a warning.

## Development

```bash
pip install -e ".[dev]"
pre-commit install          # black, isort, flake8, mypy
pytest
```

Layout:

```text
mcp-client-py/
├── mcp_client/
│   ├── client.py            # MCPClient facade
│   ├── cli.py               # click commands
│   ├── config/              # pydantic models, manager, validator
│   ├── connection/manager.py# per-server sessions, health checks
│   ├── transport/           # base + factory, stdio, sse, stream shim
│   ├── tools/               # discovery/registry, executor
│   ├── llm/                 # adapter interface, OpenAI adapter, conversation
│   └── utils/               # retry, validation, logging
├── tests/                   # pytest suites (incl. demo MCP server)
├── examples/
└── docs/architecture.md
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Good first issues: additional LLM adapters, a
live SSE integration test, and streaming tool execution.

## License

MIT — see [LICENSE](LICENSE). Changelog in [CHANGELOG.md](CHANGELOG.md).
