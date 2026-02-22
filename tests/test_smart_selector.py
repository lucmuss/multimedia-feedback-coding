# -*- coding: utf-8 -*-
"""Tests for smart frame selection."""

from __future__ import annotations

from pathlib import Path

from screenreview.pipeline.smart_selector import SmartSelector


def _frames(count: int) -> list[Path]:
    return [Path(f"/tmp/frame_{i:04d}.png") for i in range(count)]


def _settings(enabled: bool = True, max_frames: int = 10) -> dict:
    return {
        "frame_extraction": {"max_frames_per_screen": max_frames},
        "smart_selector": {
            "enabled": enabled,
            "use_gesture": True,
            "use_audio_level": True,
            "use_pixel_diff": True,
            "audio_threshold": 0.2,
            "pixel_diff_threshold": 0.1,
        },
    }


def test_filters_frames_with_gesture_detected() -> None:
    selector = SmartSelector()
    frames = _frames(5)
    selected = selector.select_frames(
        frames,
        _settings(),
        gesture_flags=[False, False, True, False, False],
    )
    assert frames[2] in selected


def test_filters_frames_with_audio_activity() -> None:
    selector = SmartSelector()
    frames = _frames(4)
    selected = selector.select_frames(
        frames,
        _settings(),
        audio_levels=[0.0, 0.1, 0.5, 0.0],
    )
    assert frames[2] in selected


def test_filters_frames_with_pixel_difference() -> None:
    selector = SmartSelector()
    frames = _frames(4)
    selected = selector.select_frames(
        frames,
        _settings(),
        pixel_diffs=[0.0, 0.05, 0.25, 0.0],
    )
    assert frames[2] in selected


def test_reduces_total_frame_count() -> None:
    selector = SmartSelector()
    frames = _frames(8)
    selected = selector.select_frames(frames, _settings(), pixel_diffs=[0.0] * 8)
    assert len(selected) < len(frames)


def test_keeps_at_least_one_frame() -> None:
    selector = SmartSelector()
    frames = _frames(8)
    selected = selector.select_frames(frames, _settings(), pixel_diffs=[0.0] * 8)
    assert selected == [frames[0]]


def test_respects_max_frames_setting() -> None:
    selector = SmartSelector()
    frames = _frames(20)
    selected = selector.select_frames(
        frames,
        _settings(max_frames=3),
        pixel_diffs=[0.5] * 20,
    )
    assert len(selected) == 3


def test_disabled_returns_all_frames() -> None:
    selector = SmartSelector()
    frames = _frames(5)
    selected = selector.select_frames(frames, _settings(enabled=False, max_frames=20))
    assert selected == frames


def test_calculates_cost_savings() -> None:
    selector = SmartSelector()
    assert selector.calculate_cost_savings(20, 5, 0.002) == 0.03


def test_combines_multiple_criteria() -> None:
    selector = SmartSelector()
    frames = _frames(6)
    selected = selector.select_frames(
        frames,
        _settings(),
        gesture_flags=[False, True, False, False, False, False],
        audio_levels=[0.0, 0.0, 0.3, 0.0, 0.0, 0.0],
        pixel_diffs=[0.0, 0.0, 0.0, 0.2, 0.0, 0.0],
        frame_times=[0, 1, 2, 3, 4, 5],
        trigger_events=[{"time": 4.0, "type": "bug"}],
    )
    assert frames[1] in selected
    assert frames[2] in selected
    assert frames[3] in selected
    assert frames[4] in selected


def test_no_gesture_no_audio_uses_pixel_diff() -> None:
    selector = SmartSelector()
    frames = _frames(4)
    settings = _settings()
    settings["smart_selector"]["use_gesture"] = False
    settings["smart_selector"]["use_audio_level"] = False
    selected = selector.select_frames(
        frames,
        settings,
        pixel_diffs=[0.0, 0.0, 0.3, 0.0],
    )
    assert selected == [frames[0], frames[2]]

