# -*- coding: utf-8 -*-
"""Tests for exporter output files."""

from __future__ import annotations

import json
from pathlib import Path

from screenreview.models.extraction_result import ExtractionResult
from screenreview.models.screen_item import ScreenItem
from screenreview.pipeline.exporter import Exporter


def _make_screen(tmp_path: Path) -> ScreenItem:
    screen_dir = tmp_path / "login_html" / "mobile"
    extraction_dir = screen_dir / ".extraction"
    extraction_dir.mkdir(parents=True, exist_ok=True)
    screenshot = screen_dir / "screenshot.png"
    screenshot.write_bytes(b"\x89PNG\r\n\x1a\nplaceholder")
    transcript = screen_dir / "transcript.md"
    transcript.write_text("existing transcript\n", encoding="utf-8")
    meta = screen_dir / "meta.json"
    meta.write_text("{}", encoding="utf-8")
    return ScreenItem(
        name="login_html",
        route="/login.html",
        viewport="mobile",
        viewport_size={"w": 390, "h": 844},
        timestamp_utc="2026-02-21T21:43:57Z",
        git_branch="main",
        git_commit="8904800cd7d591afb43873fb76cb1fd5272ac957",
        browser="chromium",
        screenshot_path=screenshot,
        transcript_path=transcript,
        metadata_path=meta,
        extraction_dir=extraction_dir,
    )


def _metadata() -> dict:
    return {
        "route": "/login.html",
        "viewport": "mobile",
        "viewport_size": {"w": 390, "h": 844},
        "timestamp_utc": "2026-02-21T21:43:57Z",
        "git": {"branch": "main", "commit": "8904800cd7d591afb43873fb76cb1fd5272ac957"},
        "playwright": {"browser": "chromium"},
    }


def _make_extraction(tmp_path: Path) -> ExtractionResult:
    screen = _make_screen(tmp_path)
    source_region = tmp_path / "region_source.png"
    source_region.write_bytes(b"\x89PNG\r\n\x1a\nregion")
    frame_path = screen.extraction_dir / "frame_0001.png"
    frame_path.write_bytes(b"\x89PNG\r\n\x1a\nframe")
    return ExtractionResult(
        screen=screen,
        video_path=screen.extraction_dir / "raw_video.mp4",
        audio_path=screen.extraction_dir / "raw_audio.wav",
        all_frames=[frame_path],
        selected_frames=[frame_path],
        gesture_positions=[{"timestamp": 5.0, "x": 195, "y": 420}],
        gesture_regions=[source_region],
        ocr_results=[{"frame": "frame_0001.png", "texts": [{"text": "Anmelden", "confidence": 0.9}]}],
        transcript_text="Der Login Button muss entfernt werden",
        transcript_segments=[{"start": 5.0, "end": 8.0, "text": "Der Login Button muss entfernt werden"}],
        trigger_events=[{"time": 5.0, "type": "bug", "segment_text": "Der Login Button muss entfernt werden"}],
    )


def test_export_writes_transcript_md(tmp_path: Path) -> None:
    exporter = Exporter()
    extraction = _make_extraction(tmp_path)
    exporter.export(extraction, metadata=_metadata(), analysis_data={"summary": "ok"})
    assert extraction.screen.transcript_path.exists()


def test_transcript_header_has_metadata(tmp_path: Path) -> None:
    exporter = Exporter()
    extraction = _make_extraction(tmp_path)
    exporter.export(extraction, metadata=_metadata(), analysis_data={})
    content = extraction.screen.transcript_path.read_text(encoding="utf-8")
    assert "Route: /login.html" in content
    assert "Viewport: mobile" in content
    assert "Browser: chromium" in content


def test_transcript_notes_have_timestamps(tmp_path: Path) -> None:
    exporter = Exporter()
    extraction = _make_extraction(tmp_path)
    exporter.export(extraction, metadata=_metadata(), analysis_data={})
    content = extraction.screen.transcript_path.read_text(encoding="utf-8")
    assert "[00:05]" in content


def test_transcript_notes_have_trigger_icons(tmp_path: Path) -> None:
    exporter = Exporter()
    extraction = _make_extraction(tmp_path)
    exporter.export(extraction, metadata=_metadata(), analysis_data={})
    content = extraction.screen.transcript_path.read_text(encoding="utf-8")
    assert "[BUG]" in content


def test_transcript_numbered_refs_populated(tmp_path: Path) -> None:
    exporter = Exporter()
    extraction = _make_extraction(tmp_path)
    exporter.export(extraction, metadata=_metadata(), analysis_data={})
    content = extraction.screen.transcript_path.read_text(encoding="utf-8")
    assert "## Numbered refs" in content
    assert "1: BUG" in content


def test_analysis_json_saved_in_extraction_dir(tmp_path: Path) -> None:
    exporter = Exporter()
    extraction = _make_extraction(tmp_path)
    exporter.export(extraction, metadata=_metadata(), analysis_data={"summary": "hello"})
    analysis_path = extraction.screen.extraction_dir / "analysis.json"
    assert analysis_path.exists()
    assert json.loads(analysis_path.read_text(encoding="utf-8"))["summary"] == "hello"


def test_ocr_json_saved_per_frame(tmp_path: Path) -> None:
    exporter = Exporter()
    extraction = _make_extraction(tmp_path)
    exporter.export(extraction, metadata=_metadata(), analysis_data={})
    ocr_path = extraction.screen.extraction_dir / "frame_0001_ocr.json"
    assert ocr_path.exists()
    payload = json.loads(ocr_path.read_text(encoding="utf-8"))
    assert payload["frame"] == "frame_0001.png"


def test_gesture_regions_saved(tmp_path: Path) -> None:
    exporter = Exporter()
    extraction = _make_extraction(tmp_path)
    exporter.export(extraction, metadata=_metadata(), analysis_data={})
    target = extraction.screen.extraction_dir / "gesture_regions" / "region_001.png"
    assert target.exists()


def test_export_json_format_valid(tmp_path: Path) -> None:
    exporter = Exporter()
    extraction = _make_extraction(tmp_path)
    exporter.export(extraction, metadata=_metadata(), analysis_data={"bugs": []})
    analysis_path = extraction.screen.extraction_dir / "analysis.json"
    payload = json.loads(analysis_path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)


def test_export_does_not_overwrite_existing_data(tmp_path: Path) -> None:
    exporter = Exporter()
    extraction = _make_extraction(tmp_path)
    analysis_path = extraction.screen.extraction_dir / "analysis.json"
    analysis_path.write_text(json.dumps({"keep": 1}), encoding="utf-8")
    exporter.export(extraction, metadata=_metadata(), analysis_data={"summary": "new"})
    payload = json.loads(analysis_path.read_text(encoding="utf-8"))
    assert payload["keep"] == 1
    assert payload["summary"] == "new"
