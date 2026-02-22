# -*- coding: utf-8 -*-
"""Tests for OCR engine placeholder."""

from __future__ import annotations

import json
from pathlib import Path

from screenreview.pipeline.ocr_engine import OcrEngine


def _png(path: Path) -> Path:
    path.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    return path


def test_extract_text_from_button_image() -> None:
    engine = OcrEngine()
    texts = engine.extract_text({"texts": [{"text": "Login", "bbox": [1, 2, 3, 4], "confidence": 0.9}]})
    assert texts[0]["text"] == "Login"


def test_extract_text_from_input_field_image() -> None:
    engine = OcrEngine()
    texts = engine.extract_text({"texts": ["Passwort"]})
    assert texts[0]["text"] == "Passwort"


def test_extract_from_specific_region() -> None:
    engine = OcrEngine()
    texts = engine.extract_from_region({"texts": ["Anmelden"]}, 10, 20, 30, 40)
    assert texts[0]["bbox"] == [10, 20, 30, 40]


def test_german_text_recognized() -> None:
    engine = OcrEngine()
    texts = engine.extract_text({"texts": ["Anmelden"]})
    assert any(item["text"] == "Anmelden" for item in texts)


def test_english_text_recognized() -> None:
    engine = OcrEngine()
    texts = engine.extract_text({"texts": ["Password"]})
    assert any(item["text"] == "Password" for item in texts)


def test_empty_image_returns_empty_list() -> None:
    engine = OcrEngine()
    assert engine.extract_text({}) == []


def test_confidence_scores_present() -> None:
    engine = OcrEngine()
    texts = engine.extract_text({"texts": ["X"]})
    assert "confidence" in texts[0]


def test_bounding_boxes_returned() -> None:
    engine = OcrEngine()
    texts = engine.extract_text({"texts": ["X"]})
    assert "bbox" in texts[0]


def test_batch_process_multiple_frames(tmp_path: Path) -> None:
    engine = OcrEngine()
    frame_a = _png(tmp_path / "frame_0001.png")
    frame_b = _png(tmp_path / "frame_0002.png")
    (tmp_path / "frame_0001.png.ocr-source.json").write_text(
        json.dumps({"texts": [{"text": "A"}]}),
        encoding="utf-8",
    )
    (tmp_path / "frame_0002.png.ocr-source.json").write_text(
        json.dumps({"texts": [{"text": "B"}]}),
        encoding="utf-8",
    )
    results = engine.process_frames([frame_a, frame_b])
    assert len(results) == 2
    assert results[0]["texts"][0]["text"] == "A"


def test_ocr_result_saved_as_json(tmp_path: Path) -> None:
    engine = OcrEngine()
    frame = _png(tmp_path / "frame_0001.png")
    (tmp_path / "frame_0001.png.ocr-source.json").write_text(
        json.dumps({"texts": [{"text": "A"}]}),
        encoding="utf-8",
    )
    engine.process_frames([frame])
    assert (tmp_path / "frame_0001_ocr.json").exists()

