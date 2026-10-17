"""Multi-round tool-calling loop, driven by a scripted fake adapter."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest

from mcp_client.config.models import Message, Tool, ToolCall, ToolResult
from mcp_client.llm.base import ChatResponse, LLMAdapterInterface
from mcp_client.llm.conversation import ConversationManager


class ScriptedAdapter(LLMAdapterInterface):
    """Returns a canned response per call and records what it received."""

    def __init__(self, responses: List[ChatResponse]) -> None:
        super().__init__(api_key="test", model="fake-model")
        self._responses = responses
        self.calls: List[Dict[str, Any]] = []

    async def chat_completion(
        self,
        messages: List[Message],
        tools: Optional[List[Tool]] = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> ChatResponse:
        self.calls.append({"messages": list(messages), "tools": tools, "stream": stream})
        if len(self.calls) <= len(self._responses):
            return self._responses[len(self.calls) - 1]
        return self._responses[-1]

    def format_tools(self, tools: List[Tool]) -> List[Dict[str, Any]]:
        return []

    def parse_tool_calls(self, response_data: Any) -> List[ToolCall]:
        return []


class FakeToolManager:
    def __init__(self) -> None:
        self.executed: List[tuple[str, Dict[str, Any]]] = []

    def get_tools(self, server_name: Optional[str] = None) -> List[Tool]:
        return [
            Tool(
                name="add",
                description="add two numbers",
                input_schema={"type": "object", "properties": {"a": {}, "b": {}}},
                server_name="demo",
            )
        ]

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> ToolResult:
        self.executed.append((tool_name, arguments))
        return ToolResult(content=[{"type": "text", "text": "5"}])


async def test_tool_call_is_executed_and_result_fed_back() -> None:
    call = ToolCall(id="call_1", name="add", arguments={"a": 2, "b": 3})
    adapter = ScriptedAdapter(
        [
            ChatResponse(content="", tool_calls=[call], finish_reason="tool_calls"),
            ChatResponse(content="The answer is 5", finish_reason="stop"),
        ]
    )
    tools = FakeToolManager()
    conversation = ConversationManager(llm_adapter=adapter, tool_manager=tools)  # type: ignore[arg-type]

    response = await conversation.send_message("what is 2 + 3?")

    assert response.content == "The answer is 5"
    assert tools.executed == [("add", {"a": 2, "b": 3})]
    assert len(adapter.calls) == 2, "the model must be called again with the tool result"

    roles = [m.role for m in conversation.messages]
    assert roles == ["user", "assistant", "tool", "assistant"]
    tool_message = conversation.messages[2]
    assert "5" in tool_message.content


async def test_execute_tools_false_does_not_run_tools() -> None:
    call = ToolCall(id="call_1", name="add", arguments={"a": 1, "b": 1})
    adapter = ScriptedAdapter([ChatResponse(content="", tool_calls=[call])])
    tools = FakeToolManager()
    conversation = ConversationManager(llm_adapter=adapter, tool_manager=tools)  # type: ignore[arg-type]

    response = await conversation.send_message("hi", execute_tools=False)

    assert response.tool_calls == [call]
    assert tools.executed == []
    assert len(adapter.calls) == 1


async def test_tool_loop_stops_at_iteration_limit() -> None:
    call = ToolCall(id="call_x", name="add", arguments={"a": 1, "b": 1})
    adapter = ScriptedAdapter([ChatResponse(content="", tool_calls=[call])])
    tools = FakeToolManager()
    conversation = ConversationManager(llm_adapter=adapter, tool_manager=tools)  # type: ignore[arg-type]

    await conversation.send_message("loop forever")

    assert len(adapter.calls) == 5, "the loop must be bounded"
    assert len(tools.executed) == 5
