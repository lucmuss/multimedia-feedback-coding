# -*- coding: utf-8 -*-
import pytest
from pathlib import Path
from screenreview.models.extraction_result import ExtractionResult
from screenreview.models.screen_item import ScreenItem
from screenreview.pipeline.exporter import Exporter


def _make_screen(tmp_path: Path) -> ScreenItem:
    viewport_dir = tmp_path / "login_html" / "mobile"
    viewport_dir.mkdir(parents=True)
    return ScreenItem(
        name="login_html",
        route="/login.html",
        viewport="mobile",
        viewport_size={"w": 390, "h": 844},
        timestamp_utc="2026-02-24",
        git_branch="main",
        git_commit="abc",
        browser="chromium",
        screenshot_path=viewport_dir / "screenshot.png",
        transcript_path=viewport_dir / "transcript.md",
        metadata_path=viewport_dir / "meta.json",
        extraction_dir=viewport_dir / ".extraction",
    )


def _make_extraction(tmp_path: Path) -> ExtractionResult:
    screen = _make_screen(tmp_path)
    return ExtractionResult(
        screen=screen,
        video_path=tmp_path / "video.mp4",
        audio_path=tmp_path / "audio.wav",
        all_frames=[],
        selected_frames=[],
        gesture_positions=[],
        gesture_regions=[],
        ocr_results=[{"text": "Anmelden", "bbox": {"top_left": {"x": 10, "y": 10}, "bottom_right": {"x": 20, "y": 20}}}],
        transcript_text="Hallo Welt",
        transcript_segments=[{"start": 5.0, "end": 7.0, "text": "Hallo Welt"}],
        trigger_events=[{"time": 5.0, "type": "bug", "word": "fehler"}],
    )


def _metadata() -> dict:
    return {
        "route": "/login.html",
        "viewport": "mobile",
        "viewport_size": {"w": 390, "h": 844},
        "git": {"branch": "main", "commit": "abc"},
        "playwright": {"browser": "chromium"},
        "timestamp_utc": "2026-02-24"
    }


def test_exporter_creates_files(tmp_path: Path) -> None:
    exporter = Exporter()
    extraction = _make_extraction(tmp_path)
    
    # Create fake video/audio for exporter (though it only needs their paths)
    extraction.video_path.touch()
    extraction.audio_path.touch()
    extraction.screen.screenshot_path.touch()
    
    result = exporter.export(extraction, metadata=_metadata(), analysis_data={"summary": "Alles ok"})
    
    assert Path(result["transcript"]).exists()
    assert result["transcript"].name == "transcript.md"
    assert Path(result["analysis"]).exists()
    assert Path(result["ocr_dir"]).exists()


def test_transcript_header_has_metadata(tmp_path: Path) -> None:
    exporter = Exporter()
    extraction = _make_extraction(tmp_path)
    exporter.export(extraction, metadata=_metadata(), analysis_data={})
    content = Path(extraction.screen.transcript_path).read_text(encoding="utf-8")
    assert "- **Route:** `/login.html`" in content
    assert "- **Viewport:** mobile" in content


def test_transcript_notes_have_timestamps(tmp_path: Path) -> None:
    exporter = Exporter()
    extraction = _make_extraction(tmp_path)
    exporter.export(extraction, metadata=_metadata(), analysis_data={})
    content = Path(extraction.screen.transcript_path).read_text(encoding="utf-8")
    assert "[00:05 - 00:07]" in content


def test_transcript_notes_have_trigger_icons(tmp_path: Path) -> None:
    exporter = Exporter()
    extraction = _make_extraction(tmp_path)
    exporter.export(extraction, metadata=_metadata(), analysis_data={})
    content = Path(extraction.screen.transcript_path).read_text(encoding="utf-8")
    assert "🔴 BUG" in content


def test_transcript_numbered_refs_populated(tmp_path: Path) -> None:
    exporter = Exporter()
    extraction = _make_extraction(tmp_path)
    exporter.export(extraction, metadata=_metadata(), analysis_data={})
    content = Path(extraction.screen.transcript_path).read_text(encoding="utf-8")
    assert "## 🔢 Priorisierte Liste (Numbered refs)" in content
