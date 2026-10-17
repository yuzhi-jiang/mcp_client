"""A tiny MCP server used by the integration tests.

Runs over stdio in a subprocess so the client is exercised end to end:
spawn -> initialize -> tools/list -> tools/call.
"""

from __future__ import annotations

import asyncio

try:  # MCP SDK >= 2.0 renamed FastMCP to MCPServer
    from mcp.server.mcpserver import MCPServer
except ImportError:  # pragma: no cover - MCP SDK 1.x
    from mcp.server.fastmcp import FastMCP as MCPServer  # type: ignore[assignment,no-redef]

server = MCPServer("demo-server")


@server.tool()
def add(a: float, b: float) -> float:
    """Add two numbers and return the sum."""
    return a + b


@server.tool()
def echo(text: str) -> str:
    """Return the given text, prefixed with ``echo:``."""
    return f"echo: {text}"


@server.tool()
def boom(message: str = "kaboom") -> str:
    """Always raise, to exercise error propagation."""
    raise ValueError(message)


@server.tool()
async def slow(seconds: float = 0.2) -> str:
    """Sleep for a moment, then return."""
    await asyncio.sleep(seconds)
    return f"slept {seconds}"


if __name__ == "__main__":
    server.run(transport="stdio")
