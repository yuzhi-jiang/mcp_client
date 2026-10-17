"""End-to-end tests against a real MCP server subprocess (stdio)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, List

import pytest

from mcp_client.client import MCPClient
from mcp_client.exceptions import ToolExecutionError, ValidationError

pytestmark = pytest.mark.integration


def _texts(result: Any) -> List[str]:
    texts: List[str] = []
    for item in result.content:
        if isinstance(item, dict):
            texts.append(str(item.get("text", item)))
        else:
            texts.append(str(getattr(item, "text", item)))
    return texts


@asynccontextmanager
async def connected(config: Dict[str, Any]) -> AsyncIterator[MCPClient]:
    """Connect and disconnect inside the caller's task.

    The MCP session owns an anyio task group; entering it in a pytest fixture
    and exiting during teardown raises "cancel scope in a different task", so
    the lifecycle is managed with a plain async context manager instead.
    """
    client = MCPClient.from_dict(config)
    await client.connect()
    try:
        yield client
    finally:
        await client.disconnect()


async def test_discovers_tools_from_server(config_dict: Dict[str, Any]) -> None:
    async with connected(config_dict) as client:
        names = set(client.get_tool_names())
    assert {"add", "echo", "boom", "slow"} <= names


async def test_calls_tool_and_reads_result(config_dict: Dict[str, Any]) -> None:
    async with connected(config_dict) as client:
        result = await client.call_tool("add", {"a": 2, "b": 3})
    assert result.is_error is False
    assert "5" in " ".join(_texts(result))


async def test_passes_string_arguments(config_dict: Dict[str, Any]) -> None:
    async with connected(config_dict) as client:
        result = await client.call_tool("echo", {"text": "hello"})
    assert "echo: hello" in " ".join(_texts(result))


async def test_async_tool_is_awaited(config_dict: Dict[str, Any]) -> None:
    async with connected(config_dict) as client:
        result = await client.call_tool("slow", {"seconds": 0.01})
    assert "slept 0.01" in " ".join(_texts(result))


async def test_argument_validation_happens_client_side(config_dict: Dict[str, Any]) -> None:
    async with connected(config_dict) as client:
        with pytest.raises(ValidationError):
            await client.call_tool("add", {"a": 1})  # missing b


async def test_tool_error_is_surfaced(config_dict: Dict[str, Any]) -> None:
    async with connected(config_dict) as client:
        with pytest.raises(ToolExecutionError) as excinfo:
            await client.call_tool("boom", {"message": "kaboom"})
    assert "kaboom" in str(excinfo.value)


async def test_unknown_tool_is_rejected(config_dict: Dict[str, Any]) -> None:
    async with connected(config_dict) as client:
        with pytest.raises(ValidationError):
            await client.call_tool("does-not-exist", {})


async def test_two_servers_are_tracked_separately(config_dict: Dict[str, Any]) -> None:
    config = {
        **config_dict,
        "servers": {
            name: dict(config_dict["servers"]["demo"]) for name in ("demo_a", "demo_b")
        },
    }
    async with connected(config) as client:
        assert set(client.get_connected_servers()) == {"demo_a", "demo_b"}
        assert client.get_tool_names("demo_a"), "the first server registers the tools"
        # Both servers expose the same tool names, so the second one is skipped
        # by the documented conflict rule instead of overwriting the registry.
        assert client.get_tool_names("demo_b") == []
        assert not client.get_tool_names("unknown-server")


async def test_one_broken_server_does_not_block_the_healthy_one(
    config_dict: Dict[str, Any],
) -> None:
    config = {
        **config_dict,
        "servers": {
            "broken": {
                "transport": "stdio",
                "command": "/nonexistent/mcp-server",
                "args": ["--never-starts"],
                "timeout": 5.0,
            },
            "demo": config_dict["servers"]["demo"],
        },
    }
    async with connected(config) as client:
        assert "demo" in client.get_connected_servers()
        result = await client.call_tool("add", {"a": 1, "b": 1})
        assert "2" in " ".join(_texts(result))
