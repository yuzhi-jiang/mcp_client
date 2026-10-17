# Architecture

## Layers

```text
CLI ──▶ MCPClient ──▶ ConnectionManager ──▶ TransportFactory ──▶ stdio / sse
                 ├──▶ ToolManager ──▶ ToolExecutor ─────────────┘
                 └──▶ ConversationManager ──▶ LLM adapter (OpenAI-compatible)
```

| Layer | Responsibility | Key types |
| --- | --- | --- |
| Facade | lifecycle, convenience API | `MCPClient` |
| Connection | one session per server, health checks, retry | `ConnectionManager` |
| Transport | wire protocol, stream handling | `BaseTransport`, `TransportFactory`, `StdioTransport`, `SseTransport` |
| Tools | discovery, registry, argument validation, execution | `ToolManager`, `ToolExecutor` |
| LLM | provider adaptation, message conversion, tool loop | `LLMAdapterInterface`, `OpenAIAdapter`, `ConversationManager` |
| Config | schema, defaults, env interpolation | `Config`, `ServerConfig`, `ConfigManager`, `ConfigValidator` |

Each layer depends only on the one below it; transports and LLM providers are plugged in
through an abstract interface plus a factory, so adding one does not touch the facade.

## Connection sequence

```text
client.connect()
  └─ ConnectionManager.connect_all()
       for each enabled server (sequential — see "Task affinity")
         ├─ TransportFactory.create_transport(server_name, config)
         ├─ transport.connect() ──▶ mcp.stdio_client / mcp.sse_client
         ├─ ClientSession(read, write)          # enters the session task group
         └─ session.initialize()
  └─ ToolManager.discover_tools()
       for each connected server
         ├─ session.list_tools()
         └─ Tool(name, description, input_schema, server_name) → registry
```

Failures are isolated per server: a server that cannot start is logged and skipped, and
`connect_all()` only raises when *no* server could be reached.

## Tool call sequence

```text
client.call_tool(name, args)
  └─ ToolManager.execute_tool()
       ├─ registry lookup (unknown tool → ValidationError)
       ├─ ToolExecutor._validate_arguments()   # JSON Schema, client side
       ├─ ConnectionManager.get_session(server)
       ├─ retry policy (transient errors only)
       └─ session.call_tool(name, args) → ToolResult(content, is_error)
```

Argument validation runs before the network hop, so a malformed call never reaches the
server. Both mcp 1.x (`inputSchema`, `isError`) and 2.x (`input_schema`, `is_error`)
field names are accepted.

## LLM tool-calling loop

```text
conversation.send_message(text, execute_tools=True)
  └─ messages += user message
  └─ loop (max 5 iterations)
       ├─ adapter.chat_completion(messages, tools)
       ├─ messages += assistant message (content + tool_calls)
       ├─ if no tool calls → return response
       └─ for each call: tool_manager.execute_tool(...)
            └─ messages += tool message with the result
```

The cap protects against a model that loops forever; on exhaustion the last response is
returned with a warning. Errors raised by a tool are converted into a tool message
rather than aborting the conversation, so the model can react to them.

## Streaming

The OpenAI adapter accumulates `delta.tool_calls` per stream `index`: the `id` and
`function.name` arrive in the first fragment and `function.arguments` arrives as string
chunks that must be concatenated before `json.loads`. Every emitted chunk carries the
**merged** tool calls so far, which means the final chunk (the one carrying only
`finish_reason`) still has the complete call. The conversation layer merges by call id,
so adapters that emit either deltas or full snapshots behave the same.

Streaming does not execute tools; it returns the calls for the caller to act on.

## Task affinity (why connections are sequential)

An MCP `ClientSession` enters an `anyio` task group, and a cancel scope can only be
exited by the task that entered it. Creating sessions inside `asyncio.gather()` child
tasks therefore produces
`RuntimeError: Attempted to exit cancel scope in a different task than it was entered in`
as soon as the client disconnects.

`connect_all()` and `disconnect_all()` therefore iterate sequentially in the caller's
task. Sessions are also closed *before* the transport that feeds them, otherwise closing
the streams cancels the session's reader task and the cancellation propagates into the
caller.

## Error model

| Exception | Raised by | Meaning |
| --- | --- | --- |
| `ConfigurationError` | config loading | unreadable/invalid config, unresolved env var |
| `ValidationError` | config, executor, client | schema violation, unknown tool, bad argument |
| `ConnectionError` | transport, manager | server unreachable or refused |
| `TimeoutError` (client) | transport | connect timeout |
| `ToolExecutionError` | executor | server returned `isError` or the call failed |
| `AuthenticationError` | LLM adapter | missing/invalid API key |
| `LLMError` | LLM adapter | provider call failed |

## Extension points

**A new transport.** Subclass `BaseTransport`, implement `_do_connect()` returning
`(read_stream, write_stream)` and `_do_disconnect()`, then register it with
`TransportFactory.register_transport(name, cls)`.

**A new LLM provider.** Subclass `LLMAdapterInterface` (`chat_completion`,
`format_tools`, `parse_tool_calls`), then `LLMAdapterFactory.register_adapter(name, cls)`.

**A new validation rule.** `ToolExecutor._validate_arguments()` walks the tool's JSON
Schema; rules live there rather than in the tool implementations, so servers stay
authoritative.

## Testing strategy

| Level | What it proves |
| --- | --- |
| Unit | config/env resolution, validators, retry policy, argument checking, stream merging |
| Fake-adapter | the tool loop, iteration cap, history trimming (no network) |
| Integration | real subprocess, real `initialize/list/call`, error propagation, partial failure |

Integration tests own the client lifecycle inside a single `async with` block in the test
task, for the same task-affinity reason described above.
