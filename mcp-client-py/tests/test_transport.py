"""Transport factory and configuration validation."""

from __future__ import annotations

import pytest

from mcp_client.config.models import ServerConfig
from mcp_client.exceptions import ValidationError
from mcp_client.transport.base import TransportFactory
from mcp_client.transport.streams import ReadStream, WriteStream


def test_factory_exposes_stdio_and_sse() -> None:
    supported = TransportFactory.get_supported_transports()
    assert "stdio" in supported
    assert "sse" in supported


def test_is_transport_supported() -> None:
    assert TransportFactory.is_transport_supported("stdio") is True
    assert TransportFactory.is_transport_supported("carrier-pigeon") is False


def test_stdio_requires_command_and_args() -> None:
    with pytest.raises(ValidationError):
        ServerConfig(transport="stdio", args=["x"])

    with pytest.raises(ValidationError):
        ServerConfig(transport="stdio", command="python", args=[])


def test_sse_requires_url() -> None:
    with pytest.raises(ValidationError):
        ServerConfig(transport="sse")


def test_unsupported_transport_is_rejected_at_config_level() -> None:
    with pytest.raises(ValidationError):
        ServerConfig(transport="carrier-pigeon")


def test_stream_types_are_importable() -> None:
    """The compat shim must work on both MCP SDK 1.x and 2.x."""
    assert ReadStream is not None
    assert WriteStream is not None
