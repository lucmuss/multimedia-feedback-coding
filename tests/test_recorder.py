# -*- coding: utf-8 -*-
"""Tests for recorder live-capture fallback behavior."""

from __future__ import annotations

from pathlib import Path

from screenreview.pipeline import recorder as recorder_mod
from screenreview.pipeline.recorder import Recorder


def test_recorder_falls_back_to_placeholder_files_when_live_backends_missing(tmp_path: Path) -> None:
    original_cv2 = recorder_mod.cv2
    original_sd = recorder_mod.sd
    original_np = recorder_mod.np
    recorder_mod.cv2 = None
    recorder_mod.sd = None
    recorder_mod.np = None
    try:
        rec = Recorder(output_dir=tmp_path)
        rec.start(camera_index=0, mic_index=0, resolution="1080p")
        video_path, audio_path = rec.stop()
    finally:
        recorder_mod.cv2 = original_cv2
        recorder_mod.sd = original_sd
        recorder_mod.np = original_np

    assert video_path.exists()
    assert audio_path.exists()
    assert video_path.read_bytes().startswith(b"SCREENREVIEW_PLACEHOLDER_MP4")
    assert audio_path.stat().st_size > 44
    assert rec.get_backend_mode() == "placeholder"
    assert any("placeholder" in note.lower() or "not installed" in note.lower() for note in rec.get_backend_notes())


def test_capture_capabilities_report_reflects_optional_dependency_flags(monkeypatch) -> None:
    monkeypatch.setattr(recorder_mod, "cv2", None)
    monkeypatch.setattr(recorder_mod, "sd", None)
    monkeypatch.setattr(recorder_mod, "np", None)

    caps = Recorder.capture_capabilities()

    assert caps["opencv_available"] is False
    assert caps["sounddevice_available"] is False
    assert caps["live_video_supported"] is False
    assert caps["live_audio_supported"] is False


def test_preview_probe_returns_clear_message_without_opencv(monkeypatch) -> None:
    monkeypatch.setattr(recorder_mod, "cv2", None)
    result = Recorder.capture_single_frame(camera_index=0)
    assert result["ok"] is False
    assert "OpenCV" in str(result["message"])


def test_audio_probe_returns_clear_message_without_sounddevice_or_numpy(monkeypatch) -> None:
    monkeypatch.setattr(recorder_mod, "sd", None)
    monkeypatch.setattr(recorder_mod, "np", None)
    result = Recorder.sample_audio_input_level(mic_index=0)
    assert result["ok"] is False
    assert "sounddevice" in str(result["message"])


def test_camera_resolution_probe_returns_defaults_without_opencv(monkeypatch) -> None:
    monkeypatch.setattr(recorder_mod, "cv2", None)
    result = Recorder.probe_camera_resolution_options(camera_index=0)
    assert result["ok"] is False
    assert result["options"] == ["720p", "1080p", "4k"]


def test_resolution_parser_accepts_custom_wxh_string() -> None:
    assert recorder_mod._resolution_size("1600x900") == (1600, 900)
