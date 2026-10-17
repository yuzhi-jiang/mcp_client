"""Shared fixtures for the test suite."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

DEMO_SERVER = Path(__file__).with_name("mcp_demo_server.py")


def demo_config(server_names: tuple[str, ...] = ("demo",)) -> Dict[str, Any]:
    """Build a client config that launches the demo server over stdio."""
    return {
        "servers": {
            name: {
                "transport": "stdio",
                "command": sys.executable,
                "args": [str(DEMO_SERVER)],
                "timeout": 30.0,
            }
            for name in server_names
        },
        "log_level": "WARNING",
        "default_timeout": 30.0,
        "max_retries": 1,
    }


@pytest.fixture
def demo_server_path() -> Path:
    """Path to the demo MCP server script."""
    return DEMO_SERVER


@pytest.fixture
def config_dict() -> Dict[str, Any]:
    """Config for a single demo server."""
    return demo_config()


@pytest.fixture
def config_file(tmp_path: Path, config_dict: Dict[str, Any]) -> str:
    """Config for a single demo server, written to a temp file."""
    path = tmp_path / "mcp_config.json"
    path.write_text(json.dumps(config_dict), encoding="utf-8")
    return str(path)
