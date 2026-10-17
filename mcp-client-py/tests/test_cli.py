"""Smoke tests for the Click CLI."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from mcp_client.cli import cli, main


def test_help_lists_commands() -> None:
    result = CliRunner().invoke(cli, ["--help"])
    assert result.exit_code == 0
    for command in ("list-servers", "list-tools", "call-tool", "chat", "status"):
        assert command in result.output


def test_main_entry_point_is_callable() -> None:
    """The console-script entry point delegates to the click group."""
    assert callable(main)


def test_create_config_writes_loadable_file(tmp_path: Path) -> None:
    target = tmp_path / "mcp_config.json"
    result = CliRunner().invoke(cli, ["create-config", "-o", str(target)])
    assert result.exit_code == 0
    assert target.exists()
    data = json.loads(target.read_text(encoding="utf-8"))
    assert "servers" in data


def test_list_tools_against_demo_server(config_file: str) -> None:
    result = CliRunner().invoke(cli, ["--config", config_file, "list-tools"])
    assert result.exit_code == 0, result.output
    assert "add" in result.output


def test_call_tool_prints_result(config_file: str) -> None:
    result = CliRunner().invoke(
        cli, ["--config", config_file, "call-tool", "add", '{"a": 2, "b": 3}']
    )
    assert result.exit_code == 0, result.output
    assert "5" in result.output


def test_call_tool_rejects_invalid_json(config_file: str) -> None:
    result = CliRunner().invoke(cli, ["--config", config_file, "call-tool", "add", "{oops"])
    assert result.exit_code != 0
    assert "Invalid JSON" in result.output
