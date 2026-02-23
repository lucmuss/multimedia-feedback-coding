# -*- coding: utf-8 -*-
"""Speech-to-text orchestration and transcript markdown export."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Protocol

from screenreview.integrations.openai_client import OpenAIClient
from screenreview.utils.file_utils import write_text_file

logger = logging.getLogger(__name__)


class _TranscribeProvider(Protocol):
    def transcribe(self, audio_path: Path, language: str = "de") -> dict[str, Any]:
        ...


def _fmt_ts(seconds: float) -> str:
    seconds_int = max(0, int(seconds))
    minutes, secs = divmod(seconds_int, 60)
    return f"{minutes:02d}:{secs:02d}"


def _label_for_event_type(event_type: str) -> str:
    labels = {
        "bug": "[BUG]",
        "ok": "[OK]",
        "extract_frame": "[REF]",
        "remove": "[REMOVE]",
        "resize": "[RESIZE]",
        "move": "[MOVE]",
        "restyle": "[RESTYLE]",
        "priority_high": "[HIGH]",
    }
    return labels.get(event_type, f"[{event_type.upper()}]")


class Transcriber:
    """Transcription service with provider dispatch and markdown generation."""

    def __init__(
        self,
        openai_client: _TranscribeProvider | None = None,
        replicate_provider: _TranscribeProvider | None = None,
        local_provider: _TranscribeProvider | None = None,
    ) -> None:
        self.openai_client = openai_client or OpenAIClient()
        self.replicate_provider = replicate_provider
        self.local_provider = local_provider

    def transcribe(self, audio_path: Path, provider: str, language: str) -> dict[str, Any]:
        """Dispatch to the configured transcription provider."""
        logger.info(f"[B5] Starting audio transcription for: {audio_path}")
        logger.debug(f"[B5] Provider: {provider}, Language: {language}")

        if not audio_path.exists():
            logger.error(f"[B5] Audio file does not exist: {audio_path}")
            return {"text": "", "segments": [], "error": "Audio file not found"}

        # Validate audio file has minimum size (at least 1KB)
        file_size = audio_path.stat().st_size
        logger.debug(f"[B5] Audio file size: {file_size} bytes")
        if file_size < 1024:
            logger.warning(f"[B5] Audio file too small ({file_size} bytes), skipping transcription")
            return {"text": "", "segments": [], "error": f"Audio file too small ({file_size} bytes)"}

        logger.debug(f"[B5] Dispatching to provider: {provider}")

        if provider in ("openai_4o_transcribe", "gpt-4o-mini-transcribe"):
            return self.openai_client.transcribe(audio_path, language=language)

        if provider == "whisper_replicate":
            if self.replicate_provider is None:
                return {"text": "", "segments": [], "provider": provider}
            return self.replicate_provider.transcribe(audio_path, language=language)

        if provider == "whisper_local":
            if self.local_provider is None:
                return {"text": "", "segments": [], "provider": provider}
            return self.local_provider.transcribe(audio_path, language=language)

        raise ValueError(f"Unsupported provider: {provider}")

    def detect_trigger_words(
        self,
        segments: list[dict[str, Any]],
        trigger_config: dict[str, list[str]],
    ) -> list[dict[str, Any]]:
        """Detect trigger words in transcript segments."""
        category_to_type = {
            "extract_frame": "extract_frame",
            "mark_bug": "bug",
            "mark_ok": "ok",
            "action_remove": "remove",
            "action_resize": "resize",
            "action_move": "move",
            "action_restyle": "restyle",
            "priority_high": "priority_high",
        }

        events: list[dict[str, Any]] = []
        for segment in segments:
            raw_text = str(segment.get("text", ""))
            lower_text = raw_text.casefold()
            for category, words in trigger_config.items():
                event_type = category_to_type.get(category, category)
                for word in words:
                    pattern = r"\b" + re.escape(str(word).casefold()) + r"\b"
                    if re.search(pattern, lower_text):
                        events.append(
                            {
                                "time": float(segment.get("start", 0.0)),
                                "type": event_type,
                                "word": word,
                                "segment_text": raw_text,
                            }
                        )
        events.sort(key=lambda item: (float(item.get("time", 0.0)), str(item.get("type", ""))))
        return events

    def save_to_markdown(
        self,
        transcript: dict[str, Any],
        metadata: dict[str, Any],
        trigger_events: list[dict[str, Any]],
        output_path: Path,
    ) -> Path:
        """Write transcript markdown with metadata, notes, and numbered refs."""
        route = str(metadata.get("route", "-"))
        viewport = str(metadata.get("viewport", "-"))
        size = metadata.get("viewport_size", {}) or {}
        width = size.get("w", "?")
        height = size.get("h", "?")
        browser = str(metadata.get("playwright", {}).get("browser", "-"))
        branch = str(metadata.get("git", {}).get("branch", "-"))
        commit = str(metadata.get("git", {}).get("commit", "-"))
        timestamp = str(metadata.get("timestamp_utc", "-"))

        segments = transcript.get("segments", []) or []
        notes_lines: list[str] = []
        for segment in segments:
            seg_time = float(segment.get("start", 0.0))
            text = str(segment.get("text", "")).strip()
            matching_events = [e for e in trigger_events if float(e.get("time", 0.0)) == seg_time]
            if matching_events:
                label = _label_for_event_type(str(matching_events[0].get("type", "")))
                notes_lines.append(f"- [{_fmt_ts(seg_time)}] {label}: \"{text}\"")
            else:
                notes_lines.append(f"- [{_fmt_ts(seg_time)}] {text}")

        if not notes_lines:
            notes_lines = ["- (no speech detected)"]

        numbered_lines: list[str] = []
        ref_events = [
            event
            for event in trigger_events
            if str(event.get("type")) in {"bug", "remove", "resize", "move", "restyle", "ok"}
        ]
        for index, event in enumerate(ref_events, start=1):
            event_type = str(event.get("type", "")).upper()
            quote = str(event.get("segment_text", "")).strip()
            numbered_lines.append(f"{index}: {event_type} - {quote}")
        if not numbered_lines:
            numbered_lines = ["1:", "2:", "3:"]

        try:
            if output_path.exists():
                existing_content = output_path.read_text(encoding="utf-8")
            else:
                existing_content = (
                    "# Transcript\n"
                    f"Route: {route}\n"
                    f"Viewport: {viewport}\n"
                )
        except Exception:
            existing_content = ""

        # Remove old ## Notes and ## Numbered refs if they exist to replace them
        import re
        content_without_notes = re.split(r"\n## Notes\b", existing_content)[0].strip()

        new_content = (
            content_without_notes
            + "\n\n## Notes\n"
            + "\n".join(notes_lines)
            + "\n\n## Numbered refs\n"
            + "\n".join(numbered_lines)
            + "\n"
        )
        return write_text_file(output_path, new_content)

