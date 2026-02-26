# -*- coding: utf-8 -*-
"""Settings persistence and validation."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from screenreview.constants import DEFAULT_HOTKEYS, DEFAULT_SETTINGS_FILE
from screenreview.utils.file_utils import read_json_file, write_json_file


DEFAULT_CONFIG: dict[str, Any] = {
    "api_keys": {"openai": "USE_ENV_FILE", "replicate": "USE_ENV_FILE", "openrouter": "USE_ENV_FILE"},
    "viewport": {"mode": "mobile"},
    "webcam": {"camera_index": 0, "resolution": "1080p", "microphone_index": 0, "custom_url": ""},
    "speech_to_text": {"provider": "openai_4o_transcribe", "language": "de"},
    "frame_extraction": {
        "method": "time_based",
        "interval_seconds": 2,
        "max_frames_per_screen": 20,
        "save_dir": ".extraction",
    },
    "smart_selector": {
        "enabled": True,
        "use_gesture": True,
        "use_audio_level": True,
        "use_pixel_diff": True,
    },
    "gesture_detection": {"enabled": True, "engine": "mediapipe", "sensitivity": 0.8},
    "ocr": {"enabled": True, "engine": "easyocr"},
    "analysis": {"provider": "replicate", "model": "llama_32_vision", "trigger": "per_screen"},
    "cost": {"budget_limit_euro": 1.0, "warning_at_euro": 0.8, "auto_stop_at_limit": True},
    "recording": {"overwrite_recordings": True},
    "hotkeys": deepcopy(DEFAULT_HOTKEYS),
    "export": {"format": "markdown", "auto_export_after_analysis": True},
    "trigger_words": {
        "extract_frame": ["hier", "da", "dort", "schau", "guck"],
        "mark_bug": ["bug", "fehler", "falsch", "kaputt", "broken"],
        "mark_ok": ["ok", "passt", "gut", "richtig", "korrekt"],
        "action_remove": ["entfernen", "weg", "loeschen", "raus"],
        "action_resize": ["groesser", "kleiner", "breiter", "schmaler"],
        "action_move": ["verschieben", "bewegen", "nach oben", "nach unten"],
        "action_restyle": ["farbe", "style", "design", "aussehen"],
        "priority_high": ["wichtig", "dringend", "kritisch", "sofort"],
    },
}


class ConfigError(ValueError):
    """Raised when settings are invalid."""


def get_default_config() -> dict[str, Any]:
    """Return a deep copy of the default config."""
    return deepcopy(DEFAULT_CONFIG)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _load_env_file(env_path: Path) -> dict[str, str]:
    """Load a simple .env file (KEY=VALUE)."""
    values: dict[str, str] = {}
    if not env_path.exists():
        return values

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        values[key] = value
    return values


def _apply_env_overrides(config: dict[str, Any], env_values: dict[str, str]) -> dict[str, Any]:
    """Apply environment-based overrides to runtime config."""
    merged = deepcopy(config)
    openai_key = env_values.get("OPENAI_API_KEY", "").strip()
    replicate_key = env_values.get("REPLICATE_API_KEY", "").strip()
    openrouter_key = env_values.get("OPENROUTER_API_KEY", "").strip()

    if openai_key:
        merged.setdefault("api_keys", {})
        merged["api_keys"]["openai"] = openai_key
    if replicate_key:
        merged.setdefault("api_keys", {})
        merged["api_keys"]["replicate"] = replicate_key
    if openrouter_key:
        merged.setdefault("api_keys", {})
        merged["api_keys"]["openrouter"] = openrouter_key
    return merged


def validate_config(config: dict[str, Any]) -> None:
    """Validate critical config fields used in phase 1."""
    viewport_mode = config.get("viewport", {}).get("mode")
    if viewport_mode not in {"mobile", "desktop"}:
        raise ConfigError("viewport.mode must be 'mobile' or 'desktop'")

    interval = config.get("frame_extraction", {}).get("interval_seconds")
    if not isinstance(interval, int) or not (1 <= interval <= 3600):
        raise ConfigError("frame_extraction.interval_seconds must be an int in range 1..3600")

    sensitivity = config.get("gesture_detection", {}).get("sensitivity")
    if not isinstance(sensitivity, (float, int)) or not (0 <= float(sensitivity) <= 1):
        raise ConfigError("gesture_detection.sensitivity must be in range 0..1")


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Load config from JSON and merge into defaults."""
    config_path = Path(path or DEFAULT_SETTINGS_FILE)
    env_values = _load_env_file(config_path.parent / ".env")
    if not config_path.exists():
        return _apply_env_overrides(get_default_config(), env_values)

    loaded = read_json_file(config_path)
    merged = _deep_merge(get_default_config(), loaded)
    merged = _apply_env_overrides(merged, env_values)
    validate_config(merged)
    return merged


def _strip_api_keys(config: dict[str, Any]) -> dict[str, Any]:
    """Remove actual API keys from config before saving to disk."""
    config_copy = deepcopy(config)
    api_keys = config_copy.get("api_keys", {})
    
    # List of environment variable names for API keys
    env_key_names = {
        "openai": "OPENAI_API_KEY",
        "replicate": "REPLICATE_API_KEY",
        "openrouter": "OPENROUTER_API_KEY"
    }
    
    for key_name, env_var in env_key_names.items():
        if key_name in api_keys:
            current_value = api_keys[key_name]
            # If the value looks like a real API key (long string), replace with placeholder
            if current_value and len(current_value) > 20:
                api_keys[key_name] = "USE_ENV_FILE"
    
    return config_copy


def save_config(config: dict[str, Any], path: str | Path | None = None) -> Path:
    """Validate and save config as JSON, but without real API keys.
    
    API keys should be stored in .env file, not in settings.json.
    """
    validate_config(config)
    config_path = Path(path or DEFAULT_SETTINGS_FILE)
    
    # Strip API keys before saving to disk
    config_to_save = _strip_api_keys(config)
    
    write_json_file(config_path, config_to_save)
    return config_path
