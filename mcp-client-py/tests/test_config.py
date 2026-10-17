"""Configuration loading, validation and env-var resolution."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

from mcp_client.config.manager import ConfigManager
from mcp_client.exceptions import ConfigurationError, ValidationError


def _write(tmp_path: Path, data: Dict[str, Any]) -> str:
    path = tmp_path / "config.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def test_default_config_loads_without_environment_variables(tmp_path: Path) -> None:
    """Regression: the shipped template must load on a clean machine.

    It used to require API_TOKEN/OPENAI_API_KEY and died with a NameError
    instead of a useful ConfigurationError.
    """
    config = ConfigManager.load_config(_write(tmp_path, ConfigManager.create_default_config()))
    assert config.servers, "default config should define example servers"


def test_env_variable_is_resolved(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMO_TOKEN", "secret-value")
    data = {
        "servers": {
            "remote": {
                "transport": "sse",
                "url": "https://example.com/mcp",
                "headers": {"Authorization": "Bearer ${DEMO_TOKEN}"},
                "disabled": True,
            }
        }
    }
    config = ConfigManager.load_config(_write(tmp_path, data))
    assert config.servers["remote"].headers["Authorization"] == "Bearer secret-value"


def test_env_variable_default_value_is_used(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MISSING_TOKEN", raising=False)
    data = {
        "servers": {
            "remote": {
                "transport": "sse",
                "url": "https://example.com/mcp",
                "headers": {"Authorization": "Bearer ${MISSING_TOKEN:fallback}"},
                "disabled": True,
            }
        }
    }
    config = ConfigManager.load_config(_write(tmp_path, data))
    assert config.servers["remote"].headers["Authorization"] == "Bearer fallback"


def test_missing_env_variable_raises_configuration_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: a missing variable must raise ConfigurationError, not NameError."""
    monkeypatch.delenv("ABSENT_TOKEN", raising=False)
    data = {
        "servers": {
            "remote": {
                "transport": "sse",
                "url": "https://example.com/mcp",
                "headers": {"Authorization": "Bearer ${ABSENT_TOKEN}"},
                "disabled": True,
            }
        }
    }
    with pytest.raises(ConfigurationError):
        ConfigManager.load_config(_write(tmp_path, data))


def test_env_resolution_is_recursive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NESTED", "yes")
    data = {
        "level1": {"level2": {"value": "${NESTED}"}},
        "items": ["${NESTED}", {"deep": "${NESTED}"}],
    }
    resolved = ConfigManager.resolve_environment_variables(data)
    assert resolved["level1"]["level2"]["value"] == "yes"
    assert resolved["items"][0] == "yes"
    assert resolved["items"][1]["deep"] == "yes"


def test_unknown_transport_is_rejected(tmp_path: Path) -> None:
    data = {
        "servers": {
            "bad": {"transport": "carrier-pigeon", "command": "x", "args": []}
        }
    }
    with pytest.raises((ValidationError, ConfigurationError)):
        ConfigManager.load_config(_write(tmp_path, data))


def test_save_and_reload_roundtrip(tmp_path: Path) -> None:
    data = {
        "servers": {
            "local": {
                "transport": "stdio",
                "command": "python",
                "args": ["-m", "demo"],
                "disabled": True,
            }
        },
        "log_level": "INFO",
    }
    config = ConfigManager.load_config(_write(tmp_path, data))
    target = tmp_path / "saved.json"
    ConfigManager.save_config(config, str(target))
    reloaded = ConfigManager.load_config(str(target))
    assert set(reloaded.servers) == set(config.servers)
    assert reloaded.log_level == "INFO"
