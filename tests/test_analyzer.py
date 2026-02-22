# -*- coding: utf-8 -*-
"""Tests for analyzer prompting and parsing."""

from __future__ import annotations

import json
from pathlib import Path

from screenreview.models.extraction_result import ExtractionResult
from screenreview.models.screen_item import ScreenItem
from screenreview.pipeline.analyzer import Analyzer


class _FakeReplicateClient:
    def __init__(self, raw_response: str) -> None:
        self.raw_response = raw_response
        self.calls: list[dict] = []

    def run_vision_model(self, model_name: str, images: list[Path], prompt: str) -> str:
        self.calls.append({"model_name": model_name, "images": images, "prompt": prompt})
        return self.raw_response


class _FakeCostTracker:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int, str]] = []

    def add(self, provider: str, units: int, screen_name: str) -> None:
        self.calls.append((provider, units, screen_name))


class _FakeOpenRouterClient(_FakeReplicateClient):
    pass


def _screen(tmp_path: Path) -> ScreenItem:
    screen_dir = tmp_path / "login_html" / "mobile"
    screen_dir.mkdir(parents=True, exist_ok=True)
    screenshot = screen_dir / "screenshot.png"
    screenshot.write_bytes(b"\x89PNG\r\n\x1a\nshot")
    transcript = screen_dir / "transcript.md"
    transcript.write_text("", encoding="utf-8")
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
        extraction_dir=screen_dir / ".extraction",
    )


def _extraction(tmp_path: Path) -> ExtractionResult:
    screen = _screen(tmp_path)
    screen.extraction_dir.mkdir(parents=True, exist_ok=True)
    frame = screen.extraction_dir / "frame_0001.png"
    region = screen.extraction_dir / "region_001.png"
    frame.write_bytes(b"\x89PNG\r\n\x1a\nframe")
    region.write_bytes(b"\x89PNG\r\n\x1a\nregion")
    return ExtractionResult(
        screen=screen,
        video_path=screen.extraction_dir / "raw_video.mp4",
        audio_path=screen.extraction_dir / "raw_audio.wav",
        all_frames=[frame],
        selected_frames=[frame],
        gesture_positions=[{"timestamp": 5.0, "x": 195, "y": 420}],
        gesture_regions=[region],
        ocr_results=[{"frame": frame.name, "texts": [{"text": "Anmelden"}]}],
        transcript_text="Der Login Button muss entfernt werden",
        transcript_segments=[{"start": 5.0, "end": 8.0, "text": "Der Login Button muss entfernt werden"}],
        trigger_events=[{"time": 5.0, "type": "bug", "word": "bug"}],
    )


def _raw_single_bug() -> str:
    return json.dumps(
        [
            {
                "id": 1,
                "element": "Login-Button",
                "position": {"x": 195, "y": 420},
                "ocr_text": "Anmelden",
                "issue": "Button soll entfernt werden",
                "action": "REMOVE",
                "priority": "high",
                "reviewer_quote": "Der Login Button muss entfernt werden",
            }
        ]
    )


def test_analyze_returns_analysis_result(tmp_path: Path) -> None:
    analyzer = Analyzer(replicate_client=_FakeReplicateClient(_raw_single_bug()))
    result = analyzer.analyze(_extraction(tmp_path), {"analysis": {"model": "llama_32_vision"}})
    assert result.model_used == "llama_32_vision"


def test_analyze_finds_single_bug(tmp_path: Path) -> None:
    analyzer = Analyzer(replicate_client=_FakeReplicateClient(_raw_single_bug()))
    result = analyzer.analyze(_extraction(tmp_path), {"analysis": {"model": "llama_32_vision"}})
    assert len(result.bugs) == 1


def test_analyze_finds_multiple_bugs(tmp_path: Path) -> None:
    raw = json.dumps([json.loads(_raw_single_bug())[0], {**json.loads(_raw_single_bug())[0], "id": 2}])
    analyzer = Analyzer(replicate_client=_FakeReplicateClient(raw))
    result = analyzer.analyze(_extraction(tmp_path), {"analysis": {"model": "llama_32_vision"}})
    assert len(result.bugs) == 2


def test_prompt_includes_route_from_meta(tmp_path: Path) -> None:
    analyzer = Analyzer(replicate_client=_FakeReplicateClient(_raw_single_bug()))
    prompt = analyzer.build_prompt(_extraction(tmp_path))
    assert "/login.html" in prompt


def test_prompt_includes_viewport_from_meta(tmp_path: Path) -> None:
    analyzer = Analyzer(replicate_client=_FakeReplicateClient(_raw_single_bug()))
    prompt = analyzer.build_prompt(_extraction(tmp_path))
    assert "mobile" in prompt


def test_prompt_includes_viewport_size(tmp_path: Path) -> None:
    analyzer = Analyzer(replicate_client=_FakeReplicateClient(_raw_single_bug()))
    prompt = analyzer.build_prompt(_extraction(tmp_path))
    assert "390x844" in prompt


def test_prompt_includes_git_info(tmp_path: Path) -> None:
    analyzer = Analyzer(replicate_client=_FakeReplicateClient(_raw_single_bug()))
    prompt = analyzer.build_prompt(_extraction(tmp_path))
    assert "main @" in prompt


def test_prompt_includes_browser(tmp_path: Path) -> None:
    analyzer = Analyzer(replicate_client=_FakeReplicateClient(_raw_single_bug()))
    prompt = analyzer.build_prompt(_extraction(tmp_path))
    assert "chromium" in prompt


def test_prompt_includes_transcript_text(tmp_path: Path) -> None:
    analyzer = Analyzer(replicate_client=_FakeReplicateClient(_raw_single_bug()))
    prompt = analyzer.build_prompt(_extraction(tmp_path))
    assert "entfernt werden" in prompt


def test_prompt_includes_ocr_results(tmp_path: Path) -> None:
    analyzer = Analyzer(replicate_client=_FakeReplicateClient(_raw_single_bug()))
    prompt = analyzer.build_prompt(_extraction(tmp_path))
    assert "Anmelden" in prompt


def test_prompt_includes_gesture_positions(tmp_path: Path) -> None:
    analyzer = Analyzer(replicate_client=_FakeReplicateClient(_raw_single_bug()))
    prompt = analyzer.build_prompt(_extraction(tmp_path))
    assert "(195, 420)" in prompt


def test_output_has_bug_id(tmp_path: Path) -> None:
    analyzer = Analyzer(replicate_client=_FakeReplicateClient(_raw_single_bug()))
    result = analyzer.analyze(_extraction(tmp_path), {"analysis": {"model": "llama_32_vision"}})
    assert "id" in result.bugs[0]


def test_output_has_description(tmp_path: Path) -> None:
    analyzer = Analyzer(replicate_client=_FakeReplicateClient(_raw_single_bug()))
    result = analyzer.analyze(_extraction(tmp_path), {"analysis": {"model": "llama_32_vision"}})
    assert "issue" in result.bugs[0]


def test_output_has_position(tmp_path: Path) -> None:
    analyzer = Analyzer(replicate_client=_FakeReplicateClient(_raw_single_bug()))
    result = analyzer.analyze(_extraction(tmp_path), {"analysis": {"model": "llama_32_vision"}})
    assert "position" in result.bugs[0]


def test_output_has_priority(tmp_path: Path) -> None:
    analyzer = Analyzer(replicate_client=_FakeReplicateClient(_raw_single_bug()))
    result = analyzer.analyze(_extraction(tmp_path), {"analysis": {"model": "llama_32_vision"}})
    assert "priority" in result.bugs[0]


def test_output_has_action(tmp_path: Path) -> None:
    analyzer = Analyzer(replicate_client=_FakeReplicateClient(_raw_single_bug()))
    result = analyzer.analyze(_extraction(tmp_path), {"analysis": {"model": "llama_32_vision"}})
    assert "action" in result.bugs[0]


def test_model_llama_vision_called_correctly(tmp_path: Path) -> None:
    client = _FakeReplicateClient(_raw_single_bug())
    analyzer = Analyzer(replicate_client=client)
    analyzer.analyze(_extraction(tmp_path), {"analysis": {"model": "llama_32_vision"}})
    assert client.calls[0]["model_name"] == "llama_32_vision"


def test_model_qwen_vl_called_correctly(tmp_path: Path) -> None:
    client = _FakeReplicateClient(_raw_single_bug())
    analyzer = Analyzer(replicate_client=client)
    analyzer.analyze(_extraction(tmp_path), {"analysis": {"model": "qwen_vl"}})
    assert client.calls[0]["model_name"] == "qwen_vl"


def test_cost_tracked_after_analysis(tmp_path: Path) -> None:
    tracker = _FakeCostTracker()
    analyzer = Analyzer(replicate_client=_FakeReplicateClient(_raw_single_bug()), cost_tracker=tracker)
    result = analyzer.analyze(_extraction(tmp_path), {"analysis": {"model": "llama_32_vision"}})
    assert result.cost_euro > 0
    assert tracker.calls


def test_model_openrouter_provider_called_correctly(tmp_path: Path) -> None:
    rep_client = _FakeReplicateClient(_raw_single_bug())
    or_client = _FakeOpenRouterClient(_raw_single_bug())
    analyzer = Analyzer(replicate_client=rep_client, openrouter_client=or_client)
    analyzer.analyze(
        _extraction(tmp_path),
        {"analysis": {"provider": "openrouter", "model": "llama_32_vision"}},
    )
    assert or_client.calls
    assert not rep_client.calls
    assert or_client.calls[0]["model_name"] == "llama_32_vision"
