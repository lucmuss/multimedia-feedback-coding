# -*- coding: utf-8 -*-
"""Tests for frame extraction."""

from __future__ import annotations

from pathlib import Path

import pytest

from screenreview.pipeline.frame_extractor import FrameExtractor
from screenreview.utils.image_utils import is_png_bytes


def test_time_based_extraction_5sec(sample_video_5sec: Path, tmp_path: Path) -> None:
    extractor = FrameExtractor()
    output_dir = tmp_path / "out_5"
    frames = extractor.extract_time_based(sample_video_5sec, interval_seconds=5, output_dir=output_dir)
    assert len(frames) == 2


def test_time_based_extraction_3sec(sample_video_5sec: Path, tmp_path: Path) -> None:
    extractor = FrameExtractor()
    frames = extractor.extract_time_based(sample_video_5sec, interval_seconds=3, output_dir=tmp_path / "out_3")
    assert len(frames) == 2


def test_time_based_extraction_custom_interval(sample_video_5sec: Path, tmp_path: Path) -> None:
    extractor = FrameExtractor()
    frames = extractor.extract_time_based(sample_video_5sec, interval_seconds=2, output_dir=tmp_path / "out_2")
    assert len(frames) == 3


def test_correct_number_of_frames_extracted(sample_video_5sec: Path, tmp_path: Path) -> None:
    extractor = FrameExtractor()
    frames = extractor.extract_all(sample_video_5sec, fps=1.0, output_dir=tmp_path / "all")
    assert len(frames) == 6


def test_frames_saved_as_png_in_extraction_dir(sample_video_5sec: Path, tmp_path: Path) -> None:
    extractor = FrameExtractor()
    output_dir = tmp_path / ".extraction"
    frames = extractor.extract_time_based(sample_video_5sec, interval_seconds=5, output_dir=output_dir)
    assert all(path.parent == output_dir for path in frames)
    assert all(path.suffix == ".png" for path in frames)


def test_frame_naming_is_sequential(sample_video_5sec: Path, tmp_path: Path) -> None:
    extractor = FrameExtractor()
    frames = extractor.extract_all(sample_video_5sec, fps=1.0, output_dir=tmp_path / "seq")
    assert [path.name for path in frames[:3]] == ["frame_0001.png", "frame_0002.png", "frame_0003.png"]


def test_frames_are_valid_images(sample_video_5sec: Path, tmp_path: Path) -> None:
    extractor = FrameExtractor()
    frames = extractor.extract_time_based(sample_video_5sec, interval_seconds=5, output_dir=tmp_path / "img")
    assert all(is_png_bytes(path.read_bytes()) for path in frames)


def test_empty_video_returns_empty_list(tmp_path: Path) -> None:
    manifest = tmp_path / "empty.srvideo.json"
    manifest.write_text('{"fps": 1.0, "duration_seconds": 0, "frames": []}', encoding="utf-8")
    extractor = FrameExtractor()
    frames = extractor.extract_time_based(manifest, interval_seconds=5, output_dir=tmp_path / "empty-out")
    assert frames == []


def test_very_short_video_returns_at_least_one(tmp_path: Path, sample_video_5sec: Path) -> None:
    content = sample_video_5sec.read_text(encoding="utf-8").replace('"duration_seconds": 5', '"duration_seconds": 1')
    short_manifest = tmp_path / "short.srvideo.json"
    short_manifest.write_text(content, encoding="utf-8")
    extractor = FrameExtractor()
    frames = extractor.extract_time_based(short_manifest, interval_seconds=5, output_dir=tmp_path / "short-out")
    assert len(frames) >= 1


def test_invalid_video_path_raises_error(tmp_path: Path) -> None:
    extractor = FrameExtractor()
    with pytest.raises(FileNotFoundError):
        extractor.extract_time_based(tmp_path / "missing.srvideo.json", interval_seconds=5)

