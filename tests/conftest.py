# -*- coding: utf-8 -*-
"""Shared pytest fixtures for phase 1."""

from __future__ import annotations

import base64
import json
import sys
import wave
from pathlib import Path

import pytest


SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


PNG_1X1_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7+fJ8AAAAASUVORK5CYII="
)


@pytest.fixture
def sample_meta() -> dict:
    return {
        "route": "/login.html",
        "slug": "login_html",
        "url": "http://127.0.0.1:8085/login.html",
        "viewport": "mobile",
        "viewport_size": {"w": 390, "h": 844},
        "timestamp_utc": "2026-02-21T21:43:57Z",
        "git": {
            "branch": "main",
            "commit": "8904800cd7d591afb43873fb76cb1fd5272ac957",
        },
        "playwright": {"browser": "chromium", "test": "login.html"},
    }


def _write_png(path: Path) -> None:
    path.write_bytes(PNG_1X1_BYTES)


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _write_transcript(path: Path, route: str, viewport: str) -> None:
    path.write_text(
        (
            "# Transcript (Voice -> Text)\n"
            f"Route: {route}\n"
            f"Viewport: {viewport}\n\n"
            "## Notes\n"
            "- (add voice transcription here)\n\n"
            "## Numbered refs (optional)\n"
            "1:\n2:\n3:\n"
        ),
        encoding="utf-8",
    )


@pytest.fixture
def tmp_project_dir(tmp_path: Path, sample_meta: dict) -> Path:
    pages = {
        "login_html": "/login.html",
        "dashboard_html": "/dashboard.html",
    }
    for page_name, route in pages.items():
        for viewport, size in (("mobile", {"w": 390, "h": 844}), ("desktop", {"w": 1440, "h": 900})):
            page_dir = tmp_path / page_name / viewport
            page_dir.mkdir(parents=True, exist_ok=True)
            meta = dict(sample_meta)
            meta["route"] = route
            meta["viewport"] = viewport
            meta["viewport_size"] = size
            _write_json(page_dir / "meta.json", meta)
            _write_png(page_dir / "screenshot.png")
            _write_transcript(page_dir / "transcript.md", route, viewport)
    return tmp_path


@pytest.fixture
def default_config() -> dict:
    from screenreview.config import get_default_config

    return get_default_config()


@pytest.fixture
def sample_screenshot(tmp_path: Path) -> Path:
    path = tmp_path / "sample_screenshot.png"
    _write_png(path)
    return path


@pytest.fixture
def sample_audio_5sec(tmp_path: Path) -> Path:
    path = tmp_path / "sample_audio_5sec.wav"
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(16000)
        wav_file.writeframes(b"\x00\x00" * 16000 * 5)
    return path


@pytest.fixture
def sample_video_5sec(tmp_path: Path) -> Path:
    path = tmp_path / "sample_video_5sec.srvideo.json"
    manifest = {
        "fps": 1.0,
        "duration_seconds": 5,
        "frames": [{"png_base64": base64.b64encode(PNG_1X1_BYTES).decode("ascii")} for _ in range(6)],
    }
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return path


class _MockProvider:
    def __init__(self, response: dict) -> None:
        self.response = response
        self.calls: list[tuple[Path, str]] = []

    def transcribe(self, audio_path: Path, language: str = "de") -> dict:
        self.calls.append((audio_path, language))
        return dict(self.response)


@pytest.fixture
def mock_openai() -> _MockProvider:
    return _MockProvider(
        {
            "text": "Der Login Button muss entfernt werden",
            "segments": [
                {
                    "start": 5.0,
                    "end": 8.0,
                    "text": "Der Login Button muss entfernt werden",
                }
            ],
        }
    )


@pytest.fixture
def mock_replicate() -> _MockProvider:
    return _MockProvider(
        {
            "text": "Das Feld soll groesser sein",
            "segments": [{"start": 12.0, "end": 15.0, "text": "Das Feld soll groesser sein"}],
        }
    )


@pytest.fixture
def cost_tracker():
    from screenreview.utils.cost_calculator import CostCalculator

    return CostCalculator()
