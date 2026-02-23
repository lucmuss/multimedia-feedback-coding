# -*- coding: utf-8 -*-
"""Trigger word detection for spoken feedback."""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class TriggerDetector:
    """Detect trigger words and classify feedback type."""

    # Trigger words for different feedback types
    TRIGGER_WORDS = {
        "bug": [
            "bug", "fehler", "falsch", "kaputt", "defekt", "funktioniert nicht",
            "geht nicht", "problem", "issue", "error", "broken"
        ],
        "ok": [
            "ok", "passt", "gut", "richtig", "perfekt", "super", "nice",
            "funktioniert", "geht", "korrekt", "fine", "good"
        ],
        "remove": [
            "entfernen", "weg", "löschen", "raus", "delete", "remove",
            "wegmachen", "nicht da", "nicht mehr", "hide"
        ],
        "resize": [
            "größer", "kleiner", "breiter", "höher", "schmaler", "länger",
            "bigger", "smaller", "wider", "taller", "resize", "scale"
        ],
        "move": [
            "verschieben", "bewegen", "andere position", "woanders",
            "move", "shift", "reposition", "relocate"
        ],
        "restyle": [
            "farbe", "style", "design", "aussehen", "color", "style",
            "design", "appearance", "look", "theme"
        ],
        "high_priority": [
            "wichtig", "dringend", "kritisch", "sofort", "urgent",
            "critical", "important", "priority", "asap"
        ],
        "add": [
            "hinzufügen", "add", "mehr", "plus", "extra", "additional"
        ],
        "text": [
            "text", "schrift", "beschriftung", "label", "caption",
            "writing", "font", "typography"
        ],
        "navigation": [
            "navigation", "menu", "link", "button", "click", "nav"
        ]
    }

    # Priority order for trigger types
    PRIORITY_ORDER = [
        "high_priority", "bug", "remove", "add", "resize", "move",
        "restyle", "text", "navigation", "ok"
    ]

    def __init__(self) -> None:
        self._compiled_patterns = self._compile_patterns()

    def _compile_patterns(self) -> dict[str, list[re.Pattern]]:
        """Compile regex patterns for trigger words."""
        patterns = {}
        for trigger_type, words in self.TRIGGER_WORDS.items():
            patterns[trigger_type] = []
            for word in words:
                # Create case-insensitive pattern with word boundaries
                pattern = re.compile(r'\b' + re.escape(word) + r'\b', re.IGNORECASE)
                patterns[trigger_type].append(pattern)
        return patterns

    def detect_triggers(self, text: str) -> list[dict[str, Any]]:
        """Detect all trigger words in text."""
        if not text or not text.strip():
            return []

        triggers = []
        text_lower = text.lower()

        for trigger_type in self.PRIORITY_ORDER:
            patterns = self._compiled_patterns.get(trigger_type, [])
            for pattern in patterns:
                matches = pattern.findall(text_lower)
                if matches:
                    for match in matches:
                        triggers.append({
                            "type": trigger_type,
                            "word": match,
                            "text": text.strip()
                        })

        return triggers

    def classify_feedback(self, text: str) -> str | None:
        """Classify feedback into primary trigger type."""
        triggers = self.detect_triggers(text)

        if not triggers:
            return None

        # Return highest priority trigger type
        return triggers[0]["type"]

    def process_transcript_segments(self, segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Process transcript segments and add trigger information."""
        processed_segments = []

        for segment in segments:
            text = segment.get("text", "")
            triggers = self.detect_triggers(text)

            processed_segment = segment.copy()
            processed_segment["triggers"] = triggers

            if triggers:
                processed_segment["primary_trigger"] = triggers[0]["type"]
            else:
                processed_segment["primary_trigger"] = None

            processed_segments.append(processed_segment)

        return processed_segments

    def get_trigger_summary(self, segments: list[dict[str, Any]]) -> dict[str, int]:
        """Get summary of trigger types found."""
        summary = {}

        for segment in segments:
            triggers = segment.get("triggers", [])
            for trigger in triggers:
                trigger_type = trigger["type"]
                summary[trigger_type] = summary.get(trigger_type, 0) + 1

        return summary

    def filter_segments_by_trigger(self, segments: list[dict[str, Any]],
                                 trigger_type: str) -> list[dict[str, Any]]:
        """Filter segments that contain specific trigger type."""
        filtered = []

        for segment in segments:
            triggers = segment.get("triggers", [])
            if any(t["type"] == trigger_type for t in triggers):
                filtered.append(segment)

        return filtered