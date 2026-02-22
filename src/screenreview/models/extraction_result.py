# -*- coding: utf-8 -*-
"""Extraction result data model."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from screenreview.models.screen_item import ScreenItem


@dataclass
class ExtractionResult:
    """Container for extracted artifacts produced by the phase 2 pipeline."""

    screen: ScreenItem
    video_path: Path
    audio_path: Path
    all_frames: list[Path] = field(default_factory=list)
    selected_frames: list[Path] = field(default_factory=list)
    gesture_positions: list[dict[str, Any]] = field(default_factory=list)
    gesture_regions: list[Path] = field(default_factory=list)
    ocr_results: list[dict[str, Any]] = field(default_factory=list)
    transcript_text: str = ""
    transcript_segments: list[dict[str, Any]] = field(default_factory=list)
    trigger_events: list[dict[str, Any]] = field(default_factory=list)

