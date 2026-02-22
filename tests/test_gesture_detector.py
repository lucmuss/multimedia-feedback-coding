# -*- coding: utf-8 -*-
"""Tests for gesture detector placeholder."""

from __future__ import annotations

import json
from pathlib import Path

from screenreview.pipeline.gesture_detector import GestureDetector


def test_detect_hand_in_frame() -> None:
    detector = GestureDetector()
    detected, _, _ = detector.detect_pointing({"pointing": True, "x": 10, "y": 20, "confidence": 0.9})
    assert detected is True


def test_detect_no_hand_in_empty_frame() -> None:
    detector = GestureDetector()
    detected, _, _ = detector.detect_pointing({"pointing": False})
    assert detected is False


def test_pointing_coordinates_returned() -> None:
    detector = GestureDetector()
    detected, x, y = detector.detect_pointing({"pointing": True, "x": 111, "y": 222, "confidence": 1.0})
    assert detected is True
    assert (x, y) == (111, 222)


def test_crop_region_correct_size() -> None:
    detector = GestureDetector()
    region = detector.get_pointing_region({"width": 400, "height": 500}, 200, 250, region_size=200)
    assert region["w"] == 200
    assert region["h"] == 200


def test_region_size_configurable() -> None:
    detector = GestureDetector()
    region = detector.get_pointing_region({"width": 400, "height": 500}, 200, 250, region_size=120)
    assert region["w"] == 120
    assert region["h"] == 120


def test_sensitivity_affects_detection() -> None:
    detector = GestureDetector(sensitivity=0.9)
    detected, _, _ = detector.detect_pointing({"pointing": True, "confidence": 0.8, "x": 1, "y": 1})
    assert detected is False


def test_works_with_index_finger_pointing() -> None:
    detector = GestureDetector()
    detected, _, _ = detector.detect_pointing(
        {"pointing": True, "type": "index_finger", "x": 5, "y": 5, "confidence": 0.95}
    )
    assert detected is True


def test_returns_empty_for_no_gesture() -> None:
    detector = GestureDetector()
    manifest = Path("/tmp/nonexistent-manifest.json")
    try:
        detector.track_video(manifest)
    except FileNotFoundError:
        assert True
    else:
        assert False


def test_track_video_reads_gesture_list(tmp_path: Path) -> None:
    detector = GestureDetector()
    manifest = tmp_path / "video_manifest.json"
    manifest.write_text(
        json.dumps({"gestures": [{"timestamp": 1.0, "x": 10, "y": 20}]}),
        encoding="utf-8",
    )
    tracked = detector.track_video(manifest)
    assert tracked == [{"timestamp": 1.0, "x": 10, "y": 20}]

