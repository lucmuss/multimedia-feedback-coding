# -*- coding: utf-8 -*-
"""Tests for screenshot differ."""

from __future__ import annotations

from pathlib import Path

from screenreview.pipeline.differ import Differ


def _file(path: Path, data: bytes) -> Path:
    path.write_bytes(data)
    return path


def test_identical_images_zero_diff(tmp_path: Path) -> None:
    differ = Differ()
    a = _file(tmp_path / "a.png", b"abc")
    b = _file(tmp_path / "b.png", b"abc")
    _, ratio = differ.compute_diff(a, b)
    assert ratio == 0


def test_different_images_nonzero_diff(tmp_path: Path) -> None:
    differ = Differ()
    a = _file(tmp_path / "a.png", b"abc")
    b = _file(tmp_path / "b.png", b"abd")
    _, ratio = differ.compute_diff(a, b)
    assert ratio > 0


def test_diff_overlay_highlights_changes(tmp_path: Path) -> None:
    differ = Differ()
    a = _file(tmp_path / "a.png", b"abc")
    b = _file(tmp_path / "b.png", b"xyz")
    diff_image, _ = differ.compute_diff(a, b)
    assert diff_image


def test_diff_saved_as_image(tmp_path: Path) -> None:
    differ = Differ()
    a = _file(tmp_path / "a.png", b"abc")
    b = _file(tmp_path / "b.png", b"xyz")
    diff_image, _ = differ.compute_diff(a, b)
    out = tmp_path / "diff.png"
    differ.save_diff(diff_image, out)
    assert out.exists()


def test_has_changed_true_for_different(tmp_path: Path) -> None:
    differ = Differ()
    a = _file(tmp_path / "a.png", b"abc")
    b = _file(tmp_path / "b.png", b"abd")
    assert differ.has_changed(a, b) is True


def test_has_changed_false_for_identical(tmp_path: Path) -> None:
    differ = Differ()
    a = _file(tmp_path / "a.png", b"abc")
    b = _file(tmp_path / "b.png", b"abc")
    assert differ.has_changed(a, b) is False


def test_works_with_different_image_sizes(tmp_path: Path) -> None:
    differ = Differ()
    a = _file(tmp_path / "a.png", b"abc")
    b = _file(tmp_path / "b.png", b"abcdef")
    _, ratio = differ.compute_diff(a, b)
    assert ratio > 0

