"""Argument validation and result/error mapping in ToolExecutor."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict, List, Tuple

import pytest

from mcp_client.config.models import Tool
from mcp_client.exceptions import ToolExecutionError, ValidationError
from mcp_client.tools.executor import ToolExecutor


SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "a": {"type": "number"},
        "b": {"type": "number"},
        "label": {"type": "string"},
    },
    "required": ["a", "b"],
}


class FakeSession:
    """Records calls and returns a canned MCP result."""

    def __init__(self, *, is_error: bool = False, text: str = "ok") -> None:
        self.calls: List[Tuple[str, Dict[str, Any]]] = []
        self._is_error = is_error
        self._text = text

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        self.calls.append((name, arguments))
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=self._text)],
            isError=self._is_error,
        )


class FakeConnectionManager:
    def __init__(self, session: FakeSession | None) -> None:
        self._session = session

    def get_session(self, server_name: str) -> Any:
        return self._session


def make_tool() -> Tool:
    return Tool(
        name="add",
        description="add two numbers",
        input_schema=SCHEMA,
        server_name="demo",
    )


async def test_executes_and_maps_result() -> None:
    session = FakeSession(text="5")
    executor = ToolExecutor(FakeConnectionManager(session))  # type: ignore[arg-type]

    result = await executor.execute_tool(make_tool(), {"a": 2, "b": 3})

    assert session.calls == [("add", {"a": 2, "b": 3})]
    assert len(result.content) == 1
    assert result.is_error is False


async def test_missing_required_argument_is_rejected_before_calling_server() -> None:
    session = FakeSession()
    executor = ToolExecutor(FakeConnectionManager(session))  # type: ignore[arg-type]

    with pytest.raises(ValidationError):
        await executor.execute_tool(make_tool(), {"a": 2})
    assert session.calls == [], "invalid arguments must never reach the server"


async def test_wrong_argument_type_is_rejected() -> None:
    session = FakeSession()
    executor = ToolExecutor(FakeConnectionManager(session))  # type: ignore[arg-type]

    with pytest.raises(ValidationError):
        await executor.execute_tool(make_tool(), {"a": "two", "b": 3})
    assert session.calls == []


async def test_extra_argument_is_allowed_unless_schema_forbids_it() -> None:
    """JSON Schema allows additional properties by default."""
    session = FakeSession()
    executor = ToolExecutor(FakeConnectionManager(session))  # type: ignore[arg-type]

    await executor.execute_tool(make_tool(), {"a": 1, "b": 2, "surprise": True})
    assert session.calls == [("add", {"a": 1, "b": 2, "surprise": True})]


async def test_unknown_argument_is_rejected_when_schema_sets_additional_properties_false() -> None:
    session = FakeSession()
    executor = ToolExecutor(FakeConnectionManager(session))  # type: ignore[arg-type]
    strict_schema = {**SCHEMA, "additionalProperties": False}
    tool = Tool(
        name="add",
        description="add two numbers",
        input_schema=strict_schema,
        server_name="demo",
    )

    with pytest.raises(ValidationError):
        await executor.execute_tool(tool, {"a": 1, "b": 2, "surprise": True})
    assert session.calls == []


async def test_server_error_becomes_tool_execution_error() -> None:
    session = FakeSession(is_error=True, text="kaboom")
    executor = ToolExecutor(FakeConnectionManager(session))  # type: ignore[arg-type]

    with pytest.raises(ToolExecutionError) as excinfo:
        await executor.execute_tool(make_tool(), {"a": 1, "b": 2})
    assert "kaboom" in str(excinfo.value)


async def test_missing_session_raises_tool_execution_error() -> None:
    executor = ToolExecutor(FakeConnectionManager(None))  # type: ignore[arg-type]
    with pytest.raises(ToolExecutionError):
        await executor.execute_tool(make_tool(), {"a": 1, "b": 2})
