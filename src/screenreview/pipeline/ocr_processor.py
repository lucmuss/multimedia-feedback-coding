# -*- coding: utf-8 -*-
"""OCR processing for screenshots in the feedback pipeline."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from screenreview.pipeline.ocr_engine import OcrEngine

logger = logging.getLogger(__name__)


class OcrProcessor:
    """Processes OCR on screenshots and saves results in .extraction folders."""

    def __init__(self, engine: str = "auto", languages: list[str] | None = None) -> None:
        self.ocr_engine = OcrEngine(languages=languages, engine=engine)

    def process_route_screenshots(self, routes_dir: Path) -> dict[str, Any]:
        """Process all screenshots in a routes directory."""
        logger.info(f"[B4] Starting OCR processing for routes directory: {routes_dir}")
        results = {}

        for route_dir in sorted(routes_dir.iterdir()):
            if not route_dir.is_dir():
                continue

            route_slug = route_dir.name
            logger.debug(f"[B4] Processing route: {route_slug}")
            results[route_slug] = {}

            for viewport in ['mobile', 'desktop']:
                viewport_dir = route_dir / viewport
                screenshot_path = viewport_dir / "screenshot.png"

                if not screenshot_path.exists():
                    logger.debug(f"[B4] No screenshot found: {screenshot_path}")
                    continue

                logger.info(f"[B4] Processing OCR: {route_slug} ({viewport}) - {screenshot_path}")

                # Validate screenshot file
                file_size = screenshot_path.stat().st_size
                logger.debug(f"[B4] Screenshot file size: {file_size} bytes")

                # Process full screenshot
                logger.debug(f"[B4] Extracting text from screenshot...")
                ocr_results = self.ocr_engine.extract_text(screenshot_path)
                logger.debug(f"[B4] Raw OCR results: {len(ocr_results)} detections")

                # Save results
                extraction_dir = viewport_dir / ".extraction"
                logger.debug(f"[B4] Creating extraction directory: {extraction_dir}")
                extraction_dir.mkdir(exist_ok=True)

                ocr_data = []
                for entry in ocr_results:
                    ocr_data.append({
                        "text": entry["text"],
                        "bbox": {
                            "top_left": {"x": entry["bbox"][0], "y": entry["bbox"][1]},
                            "bottom_right": {"x": entry["bbox"][2], "y": entry["bbox"][3]}
                        },
                        "confidence": round(entry["confidence"], 3)
                    })

                ocr_path = extraction_dir / "screenshot_ocr.json"
                logger.debug(f"[B4] Writing OCR results to: {ocr_path}")
                ocr_path.write_text(
                    json.dumps(ocr_data, indent=2, ensure_ascii=False),
                    encoding="utf-8"
                )

                results[route_slug][viewport] = {
                    "screenshot_path": str(screenshot_path),
                    "ocr_path": str(ocr_path),
                    "text_count": len(ocr_data),
                    "texts": [item["text"] for item in ocr_data]
                }

                logger.info(f"[B4] ✓ {len(ocr_data)} text elements found and saved")

        return results

    def process_gesture_region(self, screenshot_path: Path, gesture_x: int, gesture_y: int,
                              region_size: int = 100) -> list[dict[str, Any]]:
        """Extract OCR from a region around a gesture position."""
        from PIL import Image

        screenshot = Image.open(screenshot_path)

        # Calculate region bounds
        left = max(0, gesture_x - region_size)
        top = max(0, gesture_y - region_size)
        right = min(screenshot.width, gesture_x + region_size)
        bottom = min(screenshot.height, gesture_y + region_size)

        # Crop region
        region = screenshot.crop((left, top, right, bottom))

        # Save region temporarily
        temp_region_path = screenshot_path.parent / ".extraction" / f"gesture_region_{gesture_x}_{gesture_y}.png"
        temp_region_path.parent.mkdir(exist_ok=True)
        region.save(temp_region_path)

        # Process OCR on region
        ocr_results = self.ocr_engine.extract_text(temp_region_path)

        # Adjust bbox coordinates back to original screenshot coordinates
        adjusted_results = []
        for entry in ocr_results:
            adjusted_entry = entry.copy()
            # Shift bbox back to original coordinates
            adjusted_entry["bbox"] = [
                entry["bbox"][0] + left,  # x1
                entry["bbox"][1] + top,   # y1
                entry["bbox"][2] + left,  # x2
                entry["bbox"][3] + top    # y2
            ]
            adjusted_results.append(adjusted_entry)

        # Clean up temp file
        temp_region_path.unlink(missing_ok=True)

        return adjusted_results

    def get_ocr_context_for_prompt(self, viewport_dir: Path) -> str:
        """Get OCR results formatted for AI analysis prompts."""
        ocr_path = viewport_dir / ".extraction" / "screenshot_ocr.json"

        if not ocr_path.exists():
            return "(No OCR data available)"

        try:
            ocr_data = json.loads(ocr_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Failed to load OCR data: {e}")
            return "(OCR data corrupted)"

        if not ocr_data:
            return "(No text found in screenshot)"

        # Format for AI prompt
        text_entries = []
        for item in ocr_data:
            text = item["text"]
            bbox = item["bbox"]
            x = (bbox["top_left"]["x"] + bbox["bottom_right"]["x"]) // 2
            y = (bbox["top_left"]["y"] + bbox["bottom_right"]["y"]) // 2
            confidence = item.get("confidence", 0.8)
            text_entries.append(f'"{text}" at ({x}, {y})')

        return f"OCR Text Elements: {', '.join(text_entries)}"

    def find_text_at_position(self, viewport_dir: Path, x: int, y: int,
                            tolerance: int = 20) -> list[dict[str, Any]]:
        """Find OCR text elements near a given position."""
        ocr_path = viewport_dir / ".extraction" / "screenshot_ocr.json"

        if not ocr_path.exists():
            return []

        try:
            ocr_data = json.loads(ocr_path.read_text(encoding="utf-8"))
        except Exception:
            return []

        matches = []
        for item in ocr_data:
            bbox = item["bbox"]
            text_x = (bbox["top_left"]["x"] + bbox["bottom_right"]["x"]) // 2
            text_y = (bbox["top_left"]["y"] + bbox["bottom_right"]["y"]) // 2

            if (abs(text_x - x) <= tolerance and abs(text_y - y) <= tolerance):
                matches.append(item)

        return matches

    def process_gesture_annotations(
        self,
        screen_dir: Path,
        gesture_events: list[dict[str, Any]],
        transcript_segments: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Process gesture events with OCR and transcript matching."""
        screenshot_path = screen_dir / "screenshot.png"
        extraction_dir = screen_dir / ".extraction"
        gesture_regions_dir = extraction_dir / "gesture_regions"
        gesture_regions_dir.mkdir(parents=True, exist_ok=True)

        annotations = []

        for i, event in enumerate(gesture_events):
            sx = event["screenshot_position"]["x"]
            sy = event["screenshot_position"]["y"]
            timestamp = event["timestamp"]

            # OCR on gesture region
            ocr_result = self.process_gesture_region(screenshot_path, sx, sy, region_size=100)

            # Find matching transcript segment
            matching_text = self._find_matching_transcript(timestamp, transcript_segments)

            # Detect trigger type
            trigger_type = self._detect_trigger_type(matching_text)

            annotation = {
                "index": i + 1,
                "timestamp": timestamp,
                "position": {"x": sx, "y": sy},
                "ocr_text": ocr_result[0]["text"] if ocr_result else None,
                "ocr_details": ocr_result,
                "spoken_text": matching_text,
                "trigger_type": trigger_type,
                "region_image": f"gesture_regions/region_{sx}_{sy}.png",
            }
            annotations.append(annotation)

        # Save annotations
        annotations_path = extraction_dir / "gesture_annotations.json"
        annotations_path.write_text(
            json.dumps(annotations, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

        return annotations

    def _find_matching_transcript(self, timestamp: float, transcript_segments: list[dict[str, Any]]) -> str:
        """Find transcript segment that matches the timestamp."""
        for segment in transcript_segments:
            start = segment.get("start", 0)
            end = segment.get("end", 0)
            if start <= timestamp <= end:
                return segment.get("text", "")
        return ""

    def _detect_trigger_type(self, text: str) -> str | None:
        """Detect trigger type from spoken text."""
        text_lower = text.lower()
        triggers = {
            "bug": ["bug", "fehler", "falsch", "kaputt", "defekt"],
            "ok": ["ok", "passt", "gut", "richtig", "perfekt"],
            "remove": ["entfernen", "weg", "löschen", "raus"],
            "resize": ["größer", "kleiner", "breiter", "höher"],
            "move": ["verschieben", "bewegen", "andere position"],
            "restyle": ["farbe", "style", "design", "aussehen"],
            "high_priority": ["wichtig", "dringend", "kritisch", "sofort"]
        }

        for trigger_type, words in triggers.items():
            for word in words:
                if word in text_lower:
                    return trigger_type
        return None
