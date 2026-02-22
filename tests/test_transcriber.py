# -*- coding: utf-8 -*-
"""Tests for transcription and transcript markdown export."""

from __future__ import annotations

import json
from pathlib import Path

from screenreview.pipeline.transcriber import Transcriber


def _metadata() -> dict:
    return {
        "route": "/login.html",
        "viewport": "mobile",
        "viewport_size": {"w": 390, "h": 844},
        "timestamp_utc": "2026-02-21T21:43:57Z",
        "git": {"branch": "main", "commit": "8904800cd7d591afb43873fb76cb1fd5272ac957"},
        "playwright": {"browser": "chromium"},
    }


def _transcript_payload() -> dict:
    return {
        "text": "Der Login Button muss entfernt werden. Der Header passt.",
        "segments": [
            {"start": 5.0, "end": 8.0, "text": "Der Login Button muss entfernt werden"},
            {"start": 20.0, "end": 22.0, "text": "Der Header passt"},
        ],
    }


def test_transcribe_returns_text(sample_audio_5sec: Path, mock_openai) -> None:
    transcriber = Transcriber(openai_client=mock_openai)
    result = transcriber.transcribe(sample_audio_5sec, provider="openai_4o_transcribe", language="de")
    assert result["text"]


def test_transcribe_returns_segments_with_timestamps(sample_audio_5sec: Path, mock_openai) -> None:
    transcriber = Transcriber(openai_client=mock_openai)
    result = transcriber.transcribe(sample_audio_5sec, provider="openai_4o_transcribe", language="de")
    assert "segments" in result
    assert "start" in result["segments"][0]
    assert "end" in result["segments"][0]


def test_german_audio_transcribed_correctly(sample_audio_5sec: Path, mock_openai) -> None:
    transcriber = Transcriber(openai_client=mock_openai)
    result = transcriber.transcribe(sample_audio_5sec, provider="openai_4o_transcribe", language="de")
    assert "Login" in result["text"]


def test_save_markdown_includes_route_from_meta(tmp_path: Path) -> None:
    transcriber = Transcriber()
    target = tmp_path / "transcript.md"
    transcriber.save_to_markdown(_transcript_payload(), _metadata(), [], target)
    assert "Route: /login.html" in target.read_text(encoding="utf-8")


def test_save_markdown_includes_viewport_from_meta(tmp_path: Path) -> None:
    transcriber = Transcriber()
    target = tmp_path / "transcript.md"
    transcriber.save_to_markdown(_transcript_payload(), _metadata(), [], target)
    assert "Viewport: mobile" in target.read_text(encoding="utf-8")


def test_save_markdown_includes_viewport_size(tmp_path: Path) -> None:
    transcriber = Transcriber()
    target = tmp_path / "transcript.md"
    transcriber.save_to_markdown(_transcript_payload(), _metadata(), [], target)
    assert "Size: 390x844" in target.read_text(encoding="utf-8")


def test_save_markdown_includes_browser(tmp_path: Path) -> None:
    transcriber = Transcriber()
    target = tmp_path / "transcript.md"
    transcriber.save_to_markdown(_transcript_payload(), _metadata(), [], target)
    assert "Browser: chromium" in target.read_text(encoding="utf-8")


def test_save_markdown_includes_git_info(tmp_path: Path) -> None:
    transcriber = Transcriber()
    target = tmp_path / "transcript.md"
    transcriber.save_to_markdown(_transcript_payload(), _metadata(), [], target)
    content = target.read_text(encoding="utf-8")
    assert "Branch: main" in content
    assert "Commit: 8904800cd7d591afb43873fb76cb1fd5272ac957" in content


def test_save_markdown_includes_timestamp(tmp_path: Path) -> None:
    transcriber = Transcriber()
    target = tmp_path / "transcript.md"
    transcriber.save_to_markdown(_transcript_payload(), _metadata(), [], target)
    assert "Timestamp: 2026-02-21T21:43:57Z" in target.read_text(encoding="utf-8")


def test_save_markdown_notes_section_populated(tmp_path: Path) -> None:
    transcriber = Transcriber()
    target = tmp_path / "transcript.md"
    transcriber.save_to_markdown(_transcript_payload(), _metadata(), [], target)
    content = target.read_text(encoding="utf-8")
    assert "## Notes" in content
    assert "[00:05]" in content


def test_save_markdown_numbered_refs_populated(tmp_path: Path) -> None:
    transcriber = Transcriber()
    target = tmp_path / "transcript.md"
    triggers = [{"time": 5.0, "type": "bug", "segment_text": "Der Login Button muss entfernt werden"}]
    transcriber.save_to_markdown(_transcript_payload(), _metadata(), triggers, target)
    content = target.read_text(encoding="utf-8")
    assert "## Numbered refs" in content
    assert "1: BUG" in content


def test_trigger_word_bug_detected(default_config: dict) -> None:
    transcriber = Transcriber()
    events = transcriber.detect_trigger_words(
        [{"start": 1.0, "end": 2.0, "text": "Das ist ein bug"}],
        default_config["trigger_words"],
    )
    assert any(event["type"] == "bug" for event in events)


def test_trigger_word_ok_detected(default_config: dict) -> None:
    transcriber = Transcriber()
    events = transcriber.detect_trigger_words(
        [{"start": 1.0, "end": 2.0, "text": "ok das passt"}],
        default_config["trigger_words"],
    )
    assert any(event["type"] == "ok" for event in events)


def test_trigger_word_hier_detected(default_config: dict) -> None:
    transcriber = Transcriber()
    events = transcriber.detect_trigger_words(
        [{"start": 1.0, "end": 2.0, "text": "hier bitte schauen"}],
        default_config["trigger_words"],
    )
    assert any(event["type"] == "extract_frame" for event in events)


def test_trigger_word_remove_detected(default_config: dict) -> None:
    transcriber = Transcriber()
    events = transcriber.detect_trigger_words(
        [{"start": 1.0, "end": 2.0, "text": "Das bitte entfernen"}],
        default_config["trigger_words"],
    )
    assert any(event["type"] == "remove" for event in events)


def test_trigger_word_resize_detected(default_config: dict) -> None:
    transcriber = Transcriber()
    events = transcriber.detect_trigger_words(
        [{"start": 1.0, "end": 2.0, "text": "Das Feld groesser machen"}],
        default_config["trigger_words"],
    )
    assert any(event["type"] == "resize" for event in events)


def test_trigger_word_priority_high_detected(default_config: dict) -> None:
    transcriber = Transcriber()
    events = transcriber.detect_trigger_words(
        [{"start": 1.0, "end": 2.0, "text": "Das ist kritisch"}],
        default_config["trigger_words"],
    )
    assert any(event["type"] == "priority_high" for event in events)


def test_empty_audio_returns_empty_text(sample_audio_5sec: Path) -> None:
    sidecar = sample_audio_5sec.with_suffix(sample_audio_5sec.suffix + ".transcript.json")
    sidecar.write_text(json.dumps({"text": "", "segments": []}), encoding="utf-8")
    transcriber = Transcriber()
    result = transcriber.transcribe(sample_audio_5sec, provider="openai_4o_transcribe", language="de")
    assert result["text"] == ""


def test_provider_openai_4o_called_correctly(sample_audio_5sec: Path, mock_openai) -> None:
    transcriber = Transcriber(openai_client=mock_openai)
    transcriber.transcribe(sample_audio_5sec, provider="openai_4o_transcribe", language="de")
    assert mock_openai.calls == [(sample_audio_5sec, "de")]


def test_provider_whisper_replicate_called_correctly(sample_audio_5sec: Path, mock_replicate) -> None:
    transcriber = Transcriber(replicate_provider=mock_replicate)
    transcriber.transcribe(sample_audio_5sec, provider="whisper_replicate", language="de")
    assert mock_replicate.calls == [(sample_audio_5sec, "de")]

