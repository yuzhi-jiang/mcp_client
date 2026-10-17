"""Streaming conversation state and history trimming."""

from __future__ import annotations

from typing import Any, AsyncIterator, Dict, List, Optional

import pytest

from mcp_client.config.models import Message, Tool, ToolCall, ToolResult
from mcp_client.llm.base import ChatResponse, LLMAdapterInterface, StreamingChatResponse
from mcp_client.llm.conversation import ConversationManager


class StreamingAdapter(LLMAdapterInterface):
    def __init__(self, chunks: List[StreamingChatResponse]) -> None:
        super().__init__(api_key="test", model="fake")
        self._chunks = chunks

    async def chat_completion(
        self,
        messages: List[Message],
        tools: Optional[List[Tool]] = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> Any:
        async def generator() -> AsyncIterator[StreamingChatResponse]:
            for chunk in self._chunks:
                yield chunk

        return generator()

    def format_tools(self, tools: List[Tool]) -> List[Dict[str, Any]]:
        return []

    def parse_tool_calls(self, response_data: Any) -> List[ToolCall]:
        return []


class StubToolManager:
    def get_tools(self, server_name: Optional[str] = None) -> List[Tool]:
        return []

    async def execute_tool(self, name: str, arguments: Dict[str, Any]) -> ToolResult:
        return ToolResult(content=[])


async def test_streaming_accumulates_content_and_tool_calls() -> None:
    call = ToolCall(id="call_1", name="add", arguments={"a": 1, "b": 2})
    chunks = [
        StreamingChatResponse(content="Hello "),
        StreamingChatResponse(content="world", tool_calls=[call]),
        StreamingChatResponse(content="", tool_calls=[call], finish_reason="stop", is_complete=True),
    ]
    conversation = ConversationManager(
        llm_adapter=StreamingAdapter(chunks),  # type: ignore[arg-type]
        tool_manager=StubToolManager(),  # type: ignore[arg-type]
    )

    returned = await conversation.send_message("hi", stream=True)

    assert len(returned) == 3
    assert conversation.messages[-1].role == "assistant"
    assert conversation.messages[-1].content == "Hello world"
    # Resent merged sets must not be duplicated in history
    assert conversation.messages[-1].tool_calls == [call]


async def test_history_is_trimmed_to_max_length() -> None:
    class EchoAdapter(LLMAdapterInterface):
        async def chat_completion(self, messages: List[Message], tools: Optional[List[Tool]] = None, stream: bool = False, **kwargs: Any) -> ChatResponse:
            return ChatResponse(content="ok")

        def format_tools(self, tools: List[Tool]) -> List[Dict[str, Any]]:
            return []

        def parse_tool_calls(self, response_data: Any) -> List[ToolCall]:
            return []

    conversation = ConversationManager(
        llm_adapter=EchoAdapter(api_key="k", model="m"),  # type: ignore[arg-type]
        tool_manager=StubToolManager(),  # type: ignore[arg-type]
        system_prompt="be brief",
        max_history_length=4,
    )
    for i in range(5):
        await conversation.send_message(f"message {i}", execute_tools=False)

    assert len(conversation.messages) <= 4
    assert conversation.messages[0].role == "system", "the system prompt must survive trimming"
