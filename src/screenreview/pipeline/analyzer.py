# -*- coding: utf-8 -*-
"""Multimodal analyzer orchestration."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from screenreview.integrations.openrouter_client import OpenRouterClient
from screenreview.integrations.replicate_client import ReplicateClient
from screenreview.models.analysis_result import AnalysisResult
from screenreview.models.extraction_result import ExtractionResult

logger = logging.getLogger(__name__)


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
        self.replicate_client = replicate_client
        self.openrouter_client = openrouter_client
        self.cost_tracker = cost_tracker

    def analyze(self, extraction: ExtractionResult, settings: dict[str, Any]) -> AnalysisResult:
        logger.info(f"[B8] Starting AI analysis for screen: {extraction.screen.name}")
        analysis_settings = settings.get("analysis", {})
        provider = str(analysis_settings.get("provider", "replicate"))
        model_name = str(settings.get("analysis", {}).get("model", "llama_32_vision"))

        logger.debug(f"[B8] Analysis settings: enabled={analysis_settings.get('enabled', False)}, provider={provider}, model={model_name}")
        logger.debug(f"[B8] Extraction data: {len(extraction.selected_frames)} frames, {len(extraction.gesture_positions)} gestures, {len(extraction.transcript_segments)} transcript segments")

        # Check if AI analysis is enabled
        if not analysis_settings.get("enabled", False):
            logger.info("[B8] AI analysis disabled, using local analysis")
            return self._create_local_analysis_result(extraction, model_name)

        prompt = self.build_prompt(extraction)
        images = self._collect_images(extraction)
        
        logger.info(f"[B8] Prepared AI Request: Model={model_name}, Images={len(images)}, Prompt Length={len(prompt)}")
        
        # Save request prompt for debugging
        try:
            req_log_path = extraction.screen.extraction_dir / "ai_request_prompt.txt"
            req_log_path.write_text(prompt, encoding="utf-8")
        except Exception as e:
            logger.warning(f"[B8] Could not save ai_request_prompt.txt: {e}")

        # Check if required client is available
        if provider == "openrouter":
            if not self.openrouter_client:
                logger.warning("[B8] OpenRouter client not initialized.")
                return self._create_local_analysis_result(extraction, model_name)
            self.openrouter_client.api_key = str(settings.get("api_keys", {}).get("openrouter", "")).strip()
            if not self.openrouter_client.api_key:
                logger.warning("[B8] OpenRouter API key missing.")
                return self._create_local_analysis_result(extraction, model_name)
            try:
                logger.info(f"[B8] Sending request to OpenRouter API (Model: {model_name})...")
                raw_response = self.openrouter_client.run_vision_model(model_name, images, prompt)
                tracked_model_key = f"openrouter:{model_name}"
                logger.info(f"[B8] Successfully received response from OpenRouter ({len(raw_response)} chars).")
            except Exception as e:
                logger.error(f"[B8] OpenRouter API error: {e}")
                return self._create_local_analysis_result(extraction, model_name, f"OpenRouter error: {e}")
        else:  # replicate
            if not self.replicate_client:
                logger.warning("[B8] Replicate client not initialized.")
                return self._create_local_analysis_result(extraction, model_name)
            self.replicate_client.api_key = str(settings.get("api_keys", {}).get("replicate", "")).strip()
            if not self.replicate_client.api_key:
                logger.warning("[B8] Replicate API key missing.")
                return self._create_local_analysis_result(extraction, model_name)
            try:
                logger.info(f"[B8] Sending request to Replicate API (Model: {model_name})...")
                raw_response = self.replicate_client.run_vision_model(model_name, images, prompt)
                tracked_model_key = model_name
                logger.info(f"[B8] Successfully received response from Replicate ({len(raw_response)} chars).")
            except Exception as e:
                logger.error(f"[B8] Replicate API error: {e}")
                return self._create_local_analysis_result(extraction, model_name, f"Replicate error: {e}")

        # Save raw response for debugging
        try:
            resp_log_path = extraction.screen.extraction_dir / "ai_response_raw.txt"
            resp_log_path.write_text(raw_response, encoding="utf-8")
        except Exception as e:
            logger.warning(f"[B8] Could not save ai_response_raw.txt: {e}")

        bugs = self.parse_response(raw_response)
        logger.info(f"[B8] Parsed {len(bugs)} issues from AI response.")
        
        summary = self._build_summary(bugs)
        cost_euro = round(len(self._collect_images(extraction)) * MODEL_PRICE_EURO.get(model_name, 0.0), 6)

        if self.cost_tracker is not None and hasattr(self.cost_tracker, "add"):
            try:
                self.cost_tracker.add(tracked_model_key, len(self._collect_images(extraction)), extraction.screen.name)
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

    def _create_local_analysis_result(self, extraction: ExtractionResult, model_name: str, error_msg: str = "") -> AnalysisResult:
        """Create a local analysis result when AI is not available or disabled."""
        # Generate basic analysis from transcript and gestures
        bugs = self._generate_local_bugs(extraction)

        summary = f"Local analysis: {len(bugs)} issue(s) detected from transcript/gestures."
        if error_msg:
            summary += f" (AI disabled: {error_msg})"

        raw_response = "Local analysis - no AI model used"

        return AnalysisResult(
            screen=extraction.screen,
            bugs=bugs,
            summary=summary,
            raw_response=raw_response,
            model_used=f"local ({model_name})",
            cost_euro=0.0,
        )

    def _generate_local_bugs(self, extraction: ExtractionResult) -> list[dict[str, Any]]:
        """Generate basic bug reports from transcript and gesture data."""
        bugs = []

        # Process transcript segments for trigger words
        for i, segment in enumerate(extraction.transcript_segments):
            text = segment.get("text", "").lower()

            # Simple trigger detection
            if "bug" in text or "fehler" in text or "kaputt" in text:
                bugs.append({
                    "id": len(bugs) + 1,
                    "element": "Unknown",
                    "position": {"x": 0, "y": 0},
                    "ocr_text": "",
                    "issue": f"Bug mentioned: {segment.get('text', '')}",
                    "action": "BUG",
                    "priority": "high",
                    "reviewer_quote": segment.get("text", ""),
                })
            elif "größer" in text or "kleiner" in text or "resize" in text:
                bugs.append({
                    "id": len(bugs) + 1,
                    "element": "Unknown",
                    "position": {"x": 0, "y": 0},
                    "ocr_text": "",
                    "issue": f"Resize request: {segment.get('text', '')}",
                    "action": "RESIZE",
                    "priority": "medium",
                    "reviewer_quote": segment.get("text", ""),
                })

        # Add gesture-based issues
        for gesture in extraction.gesture_positions:
            bugs.append({
                "id": len(bugs) + 1,
                "element": "UI Element",
                "position": {"x": gesture.get("x", 0), "y": gesture.get("y", 0)},
                "ocr_text": "",
                "issue": f"Gesture at position ({gesture.get('x', 0)}, {gesture.get('y', 0)}) at t={gesture.get('timestamp', 0)}s",
                "action": "GESTURE",
                "priority": "low",
                "reviewer_quote": f"Pointed at ({gesture.get('x', 0)}, {gesture.get('y', 0)})",
            })

        return bugs

    def build_prompt(self, extraction: ExtractionResult) -> str:
        screen = extraction.screen
        size = screen.viewport_size or {}

        # Get OCR context from the viewport directory
        ocr_context = self._get_ocr_context(extraction)

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
            "## OCR Text Elements\n"
            f"{ocr_context}\n\n"
            "## Transcript\n"
            + ("\n".join(transcript_lines) if transcript_lines else "(none)")
            + "\n\n## Gesture Positions\n"
            + ("\n".join(gesture_lines) if gesture_lines else "(none)")
            + "\n\nReturn a JSON array of issues."
        )

    def _get_ocr_context(self, extraction: ExtractionResult) -> str:
        """Get OCR context from the viewport directory."""
        try:
            from screenreview.pipeline.ocr_processor import OcrProcessor
            processor = OcrProcessor()

            # Find viewport directory from screen path
            screen_path = Path(extraction.screen.screenshot_path)
            viewport_dir = screen_path.parent

            return processor.get_ocr_context_for_prompt(viewport_dir)
        except Exception as e:
            return f"(OCR loading failed: {e})"

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
