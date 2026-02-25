# -*- coding: utf-8 -*-
"""Speech-to-text orchestration and transcript markdown export."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Protocol

from screenreview.integrations.openai_client import OpenAIClient
from screenreview.pipeline.trigger_detector import TriggerDetector
from screenreview.utils.file_utils import write_text_file

logger = logging.getLogger(__name__)


class _TranscribeProvider(Protocol):
    def transcribe(self, audio_path: Path, language: str = "de") -> dict[str, Any]:
        ...


def _fmt_ts(seconds: float) -> str:
    seconds_int = max(0, int(seconds))
    minutes, secs = divmod(seconds_int, 60)
    return f"{minutes:02d}:{secs:02d}"


def _icon_for_event_type(event_type: str) -> str:
    icons = {
        "bug": "🔴 BUG",
        "ok": "✅ OK",
        "remove": "🔴 REMOVE",
        "resize": "🟡 RESIZE",
        "move": "🟡 MOVE",
        "restyle": "🟡 RESTYLE",
        "high_priority": "🔴 WICHTIG",
        "priority_high": "🔴 WICHTIG",
        "add": "🟢 ADD",
        "text": "📝 TEXT",
        "navigation": "🧭 NAV",
    }
    return icons.get(event_type, "📝")


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
        annotations: list[dict[str, Any]] | None = None,
        ocr_results: list[dict[str, Any]] | None = None,
        analysis_summary: str | None = None,
    ) -> Path:
        """Write comprehensive transcript markdown for AI analysis."""
        route = str(metadata.get("route", "-"))
        viewport = str(metadata.get("viewport", "-"))
        size = metadata.get("viewport_size", {}) or {}
        width = size.get("w", "?")
        height = size.get("h", "?")
        browser = str(metadata.get("playwright", {}).get("browser", "-"))
        branch = str(metadata.get("git", {}).get("branch", "-"))
        commit = str(metadata.get("git", {}).get("commit", "-"))
        timestamp = str(metadata.get("timestamp_utc", "-"))

        lines = [
            "# ScreenReview Transcript & Analysis",
            "## 🌍 Global Context",
            f"- **Route:** `{route}`",
            f"- **Viewport:** {viewport}",
            f"- **Resolution:** {width}x{height} (Reference for all coordinates)",
            f"- **Browser:** {browser}",
            f"- **Branch:** `{branch}`",
            f"- **Commit:** `{commit}`",
            f"- **Timestamp:** {timestamp}",
            "",
            "## 🗣️ Audio-Transkription",
            transcript.get("text", "(No speech detected)"),
            "",
            "## 📝 Detaillierte Segmente & Trigger",
        ]

        segments = transcript.get("segments", []) or []
        for segment in segments:
            seg_start = float(segment.get("start", 0.0))
            seg_end = float(segment.get("end", 0.0))
            text = str(segment.get("text", "")).strip()
            
            # Find matching trigger from trigger_events or use TriggerDetector as fallback
            matching_events = [e for e in trigger_events if abs(float(e.get("time", 0.0)) - seg_start) < 0.5]
            
            if matching_events:
                icon = _icon_for_event_type(str(matching_events[0].get("type", "")))
                lines.append(f"- `[{_fmt_ts(seg_start)} - {_fmt_ts(seg_end)}]` {icon}: \"{text}\"")
            else:
                lines.append(f"- `[{_fmt_ts(seg_start)} - {_fmt_ts(seg_end)}]` \"{text}\"")

        if annotations:
            lines.append("")
            lines.append("## 🤲 Gesten & Kontext (Annotationen)")
            for ann in annotations:
                icon = _icon_for_event_type(ann.get("trigger_type", ""))
                time_str = _fmt_ts(ann["timestamp"])
                ocr = ann.get("ocr_text", "N/A")
                spoken = ann.get("spoken_text", "")
                x, y = ann["position"]["x"], ann["position"]["y"]
                
                # Calculate relative percentage for AI context
                try:
                    rel_x = (x / int(width)) * 100 if width != "?" else 0
                    rel_y = (y / int(height)) * 100 if height != "?" else 0
                    pos_desc = f"x={x}, y={y} ({rel_x:.1f}% width, {rel_y:.1f}% height)"
                except Exception:
                    pos_desc = f"x={x}, y={y}"

                lines.append(f"### Annotation {ann['index']} ({icon})")
                lines.append(f"- **Zeitpunkt:** `{time_str}`")
                lines.append(f"- **Gesprochen:** \"{spoken}\"")
                lines.append(f"- **OCR am Zeigepunkt:** \"{ocr}\"")
                lines.append(f"- **Koordinaten:** {pos_desc}")
                lines.append(f"- **Dominante Farbe:** `{ann.get('dominant_color', '#N/A')}`")
                if ann.get("region_image"):
                    lines.append(f"- **Region-Bild:** `{ann['region_image']}`")
                lines.append("")

        if ocr_results:
            lines.append("## 🔍 Vollständiger Screenshot OCR")
            lines.append("| Text | Position (x, y) | Confidence |")
            lines.append("| :--- | :--- | :--- |")
            # Limit to 50 results to avoid huge files
            for item in ocr_results[:50]:
                text = item.get("text", "").replace("|", "\\|")
                bbox = item.get("bbox", {})
                tl = bbox.get("top_left", {"x": 0, "y": 0})
                br = bbox.get("bottom_right", {"x": 0, "y": 0})
                cx = (tl["x"] + br["x"]) // 2
                cy = (tl["y"] + br["y"]) // 2
                conf = item.get("confidence", 0.0)
                lines.append(f"| {text} | ({cx}, {cy}) | {conf:.2f} |")
            if len(ocr_results) > 50:
                lines.append(f"| ... | ... | (Total: {len(ocr_results)} elements) |")
            lines.append("")

        # Search for QA Reports in the same directory as the transcript
        qa_lines = []
        try:
            viewport_dir = output_path.parent
            # 1. UI Audit
            audit_file = viewport_dir / "ui-audit.json"
            if audit_file.exists():
                import json
                audit_data = json.loads(audit_file.read_text(encoding="utf-8"))
                qa_lines.append("### 🏗️ Layout Audit (Automated)")
                qa_lines.append(f"- **Score:** {audit_data.get('score', 'N/A')}")
                findings = audit_data.get("findings", [])
                for f in findings[:5]:
                    qa_lines.append(f"  - [ ] {f.get('message', 'Issue found')}")
            
            # 2. Link Check
            link_file = viewport_dir / "link-check-report.json"
            if link_file.exists():
                import json
                link_data = json.loads(link_file.read_text(encoding="utf-8"))
                qa_lines.append("### 🔗 Link Check")
                broken = link_data.get("broken_links", [])
                qa_lines.append(f"- **Broken Links:** {len(broken)}")
                for link in broken[:3]:
                    qa_lines.append(f"  - ❌ {link.get('url')} (Status: {link.get('status')})")
        except Exception as e:
            logger.warning(f"Failed to include QA reports: {e}")

        if qa_lines:
            lines.append("## 🧪 Automatisierte QA-Ergebnisse")
            lines.extend(qa_lines)
            lines.append("")

        if analysis_summary:
            lines.append("## 🤖 KI-Zusammenfassung & Empfehlungen")
            lines.append(analysis_summary)
            lines.append("")

        lines.append("## 🔢 Priorisierte Liste (Numbered refs)")
        ref_count = 0
        if annotations:
            for ann in annotations:
                if ann.get("trigger_type") in {"bug", "remove", "resize", "move", "restyle", "high_priority", "add"}:
                    ref_count += 1
                    icon = _icon_for_event_type(ann["trigger_type"])
                    ocr = ann.get("ocr_text", "N/A")
                    spoken = ann.get("spoken_text", "")
                    lines.append(f"{ref_count}: {icon} **{ocr}** – {spoken}")
        
        if ref_count == 0:
            lines.append("1. ")
            lines.append("2. ")
            lines.append("3. ")

        return write_text_file(output_path, "\n".join(lines))

