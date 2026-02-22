# -*- coding: utf-8 -*-
"""Multimodal analyzer orchestration."""

from __future__ import annotations

import json
from typing import Any

from screenreview.integrations.openrouter_client import OpenRouterClient
from screenreview.integrations.replicate_client import ReplicateClient
from screenreview.models.analysis_result import AnalysisResult
from screenreview.models.extraction_result import ExtractionResult


MODEL_PRICE_EURO = {
    "llama_32_vision": 0.002,
    "qwen_vl": 0.001,
    "gpt4o_vision": 0.01,
}


class Analyzer:
    """Build prompts, call a vision model, and parse bug reports."""

    def __init__(
        self,
        replicate_client: ReplicateClient | None = None,
        openrouter_client: OpenRouterClient | None = None,
        cost_tracker: Any | None = None,
    ) -> None:
        self.replicate_client = replicate_client or ReplicateClient()
        self.openrouter_client = openrouter_client or OpenRouterClient()
        self.cost_tracker = cost_tracker

    def analyze(self, extraction: ExtractionResult, settings: dict[str, Any]) -> AnalysisResult:
        analysis_settings = settings.get("analysis", {})
        provider = str(analysis_settings.get("provider", "replicate"))
        model_name = str(settings.get("analysis", {}).get("model", "llama_32_vision"))
        prompt = self.build_prompt(extraction)
        images = self._collect_images(extraction)
        if provider == "openrouter":
            self.openrouter_client.api_key = str(settings.get("api_keys", {}).get("openrouter", "")).strip()
            raw_response = self.openrouter_client.run_vision_model(model_name, images, prompt)
            tracked_model_key = f"openrouter:{model_name}"
        else:
            raw_response = self.replicate_client.run_vision_model(model_name, images, prompt)
            tracked_model_key = model_name
        bugs = self.parse_response(raw_response)
        summary = self._build_summary(bugs)
        cost_euro = round(len(images) * MODEL_PRICE_EURO.get(model_name, 0.0), 6)

        if self.cost_tracker is not None and hasattr(self.cost_tracker, "add"):
            try:
                self.cost_tracker.add(tracked_model_key, len(images), extraction.screen.name)
            except Exception:
                pass

        return AnalysisResult(
            screen=extraction.screen,
            bugs=bugs,
            summary=summary,
            raw_response=raw_response,
            model_used=model_name,
            cost_euro=cost_euro,
        )

    def build_prompt(self, extraction: ExtractionResult) -> str:
        screen = extraction.screen
        size = screen.viewport_size or {}
        ocr_lines = []
        for item in extraction.ocr_results:
            texts = [str(x.get("text", "")) for x in item.get("texts", [])]
            ocr_lines.append(f"- {item.get('frame')}: {', '.join(texts)}")
        gesture_lines = [
            f"- t={g.get('timestamp', 0)} -> ({g.get('x', 0)}, {g.get('y', 0)})"
            for g in extraction.gesture_positions
        ]
        transcript_lines = [
            f"[{seg.get('start', 0):.1f}-{seg.get('end', 0):.1f}] {seg.get('text', '')}"
            for seg in extraction.transcript_segments
        ]

        return (
            "You are a QA and UI review assistant.\n\n"
            "## Page Information\n"
            f"- Route: {screen.route}\n"
            f"- Viewport: {screen.viewport}\n"
            f"- Viewport Size: {size.get('w', '?')}x{size.get('h', '?')}\n"
            f"- Browser: {screen.browser}\n"
            f"- Git: {screen.git_branch} @ {screen.git_commit}\n\n"
            "## Transcript\n"
            + ("\n".join(transcript_lines) if transcript_lines else "(none)")
            + "\n\n## Gesture Positions\n"
            + ("\n".join(gesture_lines) if gesture_lines else "(none)")
            + "\n\n## OCR Results\n"
            + ("\n".join(ocr_lines) if ocr_lines else "(none)")
            + "\n\nReturn a JSON array of issues."
        )

    def parse_response(self, raw_response: str) -> list[dict[str, Any]]:
        try:
            parsed = json.loads(raw_response)
        except json.JSONDecodeError:
            return [
                {
                    "id": 1,
                    "element": "Unknown",
                    "position": {"x": 0, "y": 0},
                    "ocr_text": "",
                    "issue": raw_response.strip() or "Unparseable response",
                    "action": "NOTE",
                    "priority": "low",
                    "reviewer_quote": "",
                }
            ]

        if isinstance(parsed, dict) and isinstance(parsed.get("bugs"), list):
            parsed = parsed["bugs"]
        if not isinstance(parsed, list):
            return []

        bugs: list[dict[str, Any]] = []
        for idx, item in enumerate(parsed, start=1):
            if not isinstance(item, dict):
                continue
            normalized = dict(item)
            normalized.setdefault("id", idx)
            normalized.setdefault("element", "")
            normalized.setdefault("position", {"x": 0, "y": 0})
            normalized.setdefault("ocr_text", "")
            normalized.setdefault("issue", "")
            normalized.setdefault("action", "NOTE")
            normalized.setdefault("priority", "low")
            normalized.setdefault("reviewer_quote", "")
            bugs.append(normalized)
        return bugs

    def _collect_images(self, extraction: ExtractionResult) -> list:
        images = list(extraction.selected_frames)
        images.extend(extraction.gesture_regions)
        images.append(extraction.screen.screenshot_path)
        # Keep order stable and remove duplicates.
        unique = []
        seen = set()
        for path in images:
            marker = str(path)
            if marker in seen:
                continue
            seen.add(marker)
            unique.append(path)
        return unique

    def _build_summary(self, bugs: list[dict[str, Any]]) -> str:
        if not bugs:
            return "No issues detected."
        return f"{len(bugs)} issue(s) detected."
