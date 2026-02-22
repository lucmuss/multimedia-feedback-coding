# -*- coding: utf-8 -*-
"""Tests for config persistence and validation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from screenreview.config import (
    ConfigError,
    get_default_config,
    load_config,
    save_config,
    validate_config,
)


def test_default_config_has_all_keys() -> None:
    config = get_default_config()
    expected_keys = {
        "api_keys",
        "viewport",
        "webcam",
        "speech_to_text",
        "frame_extraction",
        "smart_selector",
        "gesture_detection",
        "ocr",
        "analysis",
        "cost",
        "hotkeys",
        "export",
        "trigger_words",
    }
    assert expected_keys.issubset(config.keys())


def test_save_config_creates_json_file(tmp_path: Path, default_config: dict) -> None:
    target = tmp_path / "settings.json"
    save_config(default_config, target)
    assert target.exists()


def test_load_config_reads_json_file(tmp_path: Path, default_config: dict) -> None:
    target = tmp_path / "settings.json"
    save_config(default_config, target)

    loaded = load_config(target)
    assert loaded["viewport"]["mode"] == default_config["viewport"]["mode"]


def test_api_keys_persisted(tmp_path: Path, default_config: dict) -> None:
    target = tmp_path / "settings.json"
    default_config["api_keys"]["openai"] = "abc"
    default_config["api_keys"]["replicate"] = "xyz"
    save_config(default_config, target)
    loaded = json.loads(target.read_text(encoding="utf-8"))
    assert loaded["api_keys"]["openai"] == "abc"
    assert loaded["api_keys"]["replicate"] == "xyz"


def test_viewport_mode_persisted(tmp_path: Path, default_config: dict) -> None:
    target = tmp_path / "settings.json"
    default_config["viewport"]["mode"] = "desktop"
    save_config(default_config, target)
    loaded = load_config(target)
    assert loaded["viewport"]["mode"] == "desktop"


def test_hotkeys_persisted(tmp_path: Path, default_config: dict) -> None:
    target = tmp_path / "settings.json"
    default_config["hotkeys"]["next"] = "Alt+N"
    save_config(default_config, target)
    loaded = load_config(target)
    assert loaded["hotkeys"]["next"] == "Alt+N"


def test_frame_interval_in_valid_range(default_config: dict) -> None:
    default_config["frame_extraction"]["interval_seconds"] = 10
    validate_config(default_config)


def test_invalid_interval_rejected(default_config: dict) -> None:
    default_config["frame_extraction"]["interval_seconds"] = 0
    with pytest.raises(ConfigError):
        validate_config(default_config)


def test_budget_limit_saved(tmp_path: Path, default_config: dict) -> None:
    target = tmp_path / "settings.json"
    default_config["cost"]["budget_limit_euro"] = 2.5
    save_config(default_config, target)
    loaded = load_config(target)
    assert loaded["cost"]["budget_limit_euro"] == 2.5


def test_trigger_words_customizable(tmp_path: Path, default_config: dict) -> None:
    target = tmp_path / "settings.json"
    default_config["trigger_words"]["mark_bug"] = ["issue", "broken"]
    save_config(default_config, target)
    loaded = load_config(target)
    assert loaded["trigger_words"]["mark_bug"] == ["issue", "broken"]


def test_model_selection_saved(tmp_path: Path, default_config: dict) -> None:
    target = tmp_path / "settings.json"
    default_config["analysis"]["model"] = "qwen_vl"
    save_config(default_config, target)
    loaded = load_config(target)
    assert loaded["analysis"]["model"] == "qwen_vl"


def test_smart_selector_settings_saved(tmp_path: Path, default_config: dict) -> None:
    target = tmp_path / "settings.json"
    default_config["smart_selector"]["enabled"] = False
    save_config(default_config, target)
    loaded = load_config(target)
    assert loaded["smart_selector"]["enabled"] is False


def test_gesture_sensitivity_saved(tmp_path: Path, default_config: dict) -> None:
    target = tmp_path / "settings.json"
    default_config["gesture_detection"]["sensitivity"] = 0.5
    save_config(default_config, target)
    loaded = load_config(target)
    assert loaded["gesture_detection"]["sensitivity"] == 0.5


def test_export_format_saved(tmp_path: Path, default_config: dict) -> None:
    target = tmp_path / "settings.json"
    default_config["export"]["format"] = "json"
    save_config(default_config, target)
    loaded = load_config(target)
    assert loaded["export"]["format"] == "json"


def test_analysis_provider_saved(tmp_path: Path, default_config: dict) -> None:
    target = tmp_path / "settings.json"
    default_config["analysis"]["provider"] = "openrouter"
    save_config(default_config, target)
    loaded = load_config(target)
    assert loaded["analysis"]["provider"] == "openrouter"


def test_load_config_returns_defaults_when_file_missing(tmp_path: Path) -> None:
    loaded = load_config(tmp_path / "missing.json")
    assert loaded["viewport"]["mode"] == "mobile"


def test_load_config_reads_openrouter_key_from_env(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("OPENROUTER_API_KEY=test-openrouter\n", encoding="utf-8")
    loaded = load_config(tmp_path / "settings.json")
    assert loaded["api_keys"]["openrouter"] == "test-openrouter"
