# mcp_client

A Python **Model Context Protocol (MCP)** client that connects to several MCP servers at
once, discovers their tools, and drives the tool-calling loop against an
OpenAI-compatible model — library plus CLI, no desktop app required.

**Status:** 72 tests passing (unit + real stdio end-to-end), 67% line coverage,
Python 3.10–3.14, `mcp` SDK 1.x / 2.x. MIT licensed. Not published on PyPI — install
from source.

```bash
git clone https://github.com/yuzhi-jiang/mcp_client.git
cd mcp_client/mcp-client-py
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

```bash
mcp-client --config mcp_config.json list-tools       # discover tools on every server
mcp-client --config mcp_config.json call-tool add '{"a": 2, "b": 3}'
mcp-client --config mcp_config.json chat "What is 2 + 3? Use the tools."
```

## What it does

- **Multi-server sessions** — one client, many MCP servers; a failing server does not take
  the others down.
- **Two transports** — `stdio` (subprocess) and `sse` (HTTP) behind a common
  `BaseTransport` + factory.
- **Schema-enforced tool calls** — arguments are validated against each tool's JSON Schema
  (required fields, types, nested objects/arrays, `additionalProperties: false`) *before*
  the call leaves the process.
- **Bounded tool-calling loop** — OpenAI-compatible adapter, tool schemas translated into
  the model's `tools` parameter, results fed back, iteration cap (default 5).
- **Streaming** — `tool_calls` fragments merged by stream `index` (name in the first
  fragment, arguments as string chunks).
- **Retries with backoff + jitter** for transient connection/timeout errors only;
  validation and tool errors fail fast.
- **Config** — JSON + pydantic models, `${VAR}` / `${VAR:default}` interpolation.

## Layout

```text
.
├── mcp-client-py/          # the package (library + CLI)
│   ├── mcp_client/         # client, transport, tools, llm, config, utils
│   ├── tests/              # 72 tests incl. tests/test_e2e_stdio.py
│   ├── docs/architecture.md
│   └── README.md           # full documentation: features, CLI, compat, limits
├── mcp_client.py           # single-file script version (early prototype)
└── .github/workflows/      # full-history secret scan
```

## Documentation

- **[mcp-client-py/README.md](mcp-client-py/README.md)** — quick start, CLI reference,
  architecture diagram, compatibility matrix, known limitations.
- **[docs/architecture.md](mcp-client-py/docs/architecture.md)** — layers, connect and
  tool-call sequences, task affinity (why sessions are sequential), error model,
  extension points.

## Design notes worth knowing

- **Task affinity:** MCP sessions are tied to the asyncio task that created them. The
  client therefore opens and closes each server session inside the caller's task instead
  of a background task — an earlier version leaked sessions across task exits under
  `anyio`. See `docs/architecture.md` → *Task affinity*.
- **Streaming is inspection-only:** streamed responses return the tool calls; the automatic
  tool loop is non-streaming.
- **Auth is header-based** — no OAuth / mTLS; tool-name collisions across servers resolve
  first-wins with a warning.

## Security

- No credentials in the repository: pass via argument or environment
  (`DEEPSEEK_API_KEY`, `OPENAI_API_KEY`, or `${VAR}` in config files); a missing key raises
  a clear error rather than falling back to a default.
- `.env*`, `mcp_config.json`, `secrets/` and key material are git-ignored; only
  `*.example` files are tracked.
- `pre-commit` runs gitleaks on staged changes, and a workflow scans the full history on
  every push.

## License

MIT — see [mcp-client-py/LICENSE](mcp-client-py/LICENSE).
