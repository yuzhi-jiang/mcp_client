"""Streaming tool_calls arrive as fragments and must be merged by index."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

from mcp_client.config.models import Message
from mcp_client.llm.openai import OpenAIAdapter


def _chunk(
    content: str | None = None,
    tool_calls: List[Any] | None = None,
    finish_reason: str | None = None,
) -> Any:
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                delta=SimpleNamespace(content=content, tool_calls=tool_calls),
                finish_reason=finish_reason,
            )
        ]
    )


def _tc(index: int, *, id: str | None = None, name: str | None = None, args: str | None = None) -> Any:
    return SimpleNamespace(
        index=index,
        id=id,
        type="function" if id else None,
        function=SimpleNamespace(name=name, arguments=args),
    )


class FakeStream:
    def __init__(self, chunks: List[Any]) -> None:
        self._chunks = chunks

    def __aiter__(self) -> "FakeStream":
        self._iter = iter(self._chunks)
        return self

    async def __anext__(self) -> Any:
        try:
            return next(self._iter)
        except StopIteration:  # pragma: no cover - normal termination path
            raise StopAsyncIteration


class FakeCompletions:
    def __init__(self, chunks: List[Any]) -> None:
        self._chunks = chunks

    async def create(self, **kwargs: Any) -> FakeStream:
        return FakeStream(self._chunks)


class FakeClient:
    def __init__(self, chunks: List[Any]) -> None:
        self.chat = SimpleNamespace(completions=FakeCompletions(chunks))


async def test_fragmented_tool_call_arguments_are_merged_by_index() -> None:
    chunks = [
        _chunk(content="Let me compute. "),
        _chunk(tool_calls=[_tc(0, id="call_1", name="add", args='{"a": ')]),
        _chunk(tool_calls=[_tc(0, args="2, ")]),
        _chunk(tool_calls=[_tc(0, args='"b": 3}')]),
        _chunk(finish_reason="tool_calls"),
    ]
    adapter = OpenAIAdapter(api_key="sk-test", model="gpt-4o-mini")
    adapter.client = FakeClient(chunks)  # type: ignore[assignment]

    responses = [
        chunk
        async for chunk in await adapter.chat_completion(
            messages=[Message(role="user", content="2 + 3?")], stream=True
        )
    ]

    assert responses[-1].is_complete is True
    merged = responses[-1].tool_calls
    assert merged is not None and len(merged) == 1
    assert merged[0].name == "add"
    assert merged[0].arguments == {"a": 2, "b": 3}

    # content chunks are concatenated by the conversation layer, not dropped here
    assert "".join(r.content or "" for r in responses) == "Let me compute. "


async def test_two_parallel_tool_calls_keep_separate_slots() -> None:
    chunks = [
        _chunk(tool_calls=[_tc(0, id="call_a", name="add", args='{"a": 1, "b": 1}')]),
        _chunk(tool_calls=[_tc(1, id="call_b", name="echo", args='{"text": "hi"}')]),
        _chunk(finish_reason="tool_calls"),
    ]
    adapter = OpenAIAdapter(api_key="sk-test", model="gpt-4o-mini")
    adapter.client = FakeClient(chunks)  # type: ignore[assignment]

    responses = [
        chunk
        async for chunk in await adapter.chat_completion(
            messages=[Message(role="user", content="go")], stream=True
        )
    ]

    merged = {tc.name: tc.arguments for tc in (responses[-1].tool_calls or [])}
    assert merged == {"add": {"a": 1, "b": 1}, "echo": {"text": "hi"}}
