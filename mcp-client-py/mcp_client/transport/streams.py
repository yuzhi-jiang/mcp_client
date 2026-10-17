"""Version-tolerant access to the MCP SDK stream types.

``ReadStream`` / ``WriteStream`` lived in :mod:`mcp.types` in older MCP SDK
releases.  Newer releases (2.x) moved them to a private module, so a plain
``from mcp.types import ReadStream`` breaks on upgrade.  Import through this
module instead so the library keeps working across SDK versions.
"""

from __future__ import annotations

from typing import Any, Tuple

try:  # MCP SDK 1.x
    from mcp.types import ReadStream, WriteStream  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover - depends on installed SDK version
    try:  # MCP SDK 2.x
        from mcp.shared._stream_protocols import (  # type: ignore[import-not-found]
            ReadStream,
            WriteStream,
        )
    except ImportError:  # last resort: keep annotations usable
        ReadStream = Any  # type: ignore[misc,assignment]
        WriteStream = Any  # type: ignore[misc,assignment]

TransportStreams = Tuple[ReadStream, WriteStream]

__all__ = ["ReadStream", "WriteStream", "TransportStreams"]
