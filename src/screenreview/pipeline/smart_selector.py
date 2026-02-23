# -*- coding: utf-8 -*-
"""Frame selection heuristics to reduce analysis cost."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class SmartSelector:
    """Apply local heuristics to choose relevant frames."""

    def select_frames(
        self,
        frame_paths: list[Path],
        settings: dict[str, Any],
        *,
        gesture_flags: list[bool] | None = None,
        audio_levels: list[float] | None = None,
        pixel_diffs: list[float] | None = None,
        frame_times: list[float] | None = None,
        trigger_events: list[dict[str, Any]] | None = None,
    ) -> list[Path]:
        logger.info(f"[B2] Starting smart frame selection for {len(frame_paths)} frames")

        if not frame_paths:
            logger.debug("[B2] No frames provided, returning empty list")
            return []

        smart_cfg = settings.get("smart_selector", {})
        frame_cfg = settings.get("frame_extraction", {})
        enabled = bool(smart_cfg.get("enabled", True))

        logger.debug(f"[B2] Smart selector enabled: {enabled}")
        if not enabled:
            max_frames = int(frame_cfg.get("max_frames_per_screen", len(frame_paths)))
            result = frame_paths[:max_frames]
            logger.info(f"[B2] Smart selector disabled, returning first {len(result)} frames")
            return result

        gesture_flags = gesture_flags or [False] * len(frame_paths)
        audio_levels = audio_levels or [0.0] * len(frame_paths)
        pixel_diffs = pixel_diffs or [0.0] * len(frame_paths)
        frame_times = frame_times or [float(i) for i in range(len(frame_paths))]
        trigger_events = trigger_events or []

        use_gesture = bool(smart_cfg.get("use_gesture", True))
        use_audio = bool(smart_cfg.get("use_audio_level", True))
        use_diff = bool(smart_cfg.get("use_pixel_diff", True))

        selected: list[Path] = [frame_paths[0]]
        max_frames = int(frame_cfg.get("max_frames_per_screen", len(frame_paths)))
        audio_threshold = float(settings.get("smart_selector", {}).get("audio_threshold", 0.2))
        diff_threshold = float(settings.get("smart_selector", {}).get("pixel_diff_threshold", 0.1))

        trigger_times = [float(event.get("time", 0.0)) for event in trigger_events]

        for index, frame_path in enumerate(frame_paths[1:], start=1):
            keep = False
            if use_gesture and index < len(gesture_flags) and gesture_flags[index]:
                keep = True
            if use_audio and index < len(audio_levels) and float(audio_levels[index]) > audio_threshold:
                keep = True
            if use_diff and index < len(pixel_diffs) and float(pixel_diffs[index]) > diff_threshold:
                keep = True

            frame_time = float(frame_times[index]) if index < len(frame_times) else float(index)
            if any(abs(frame_time - t) <= 0.6 for t in trigger_times):
                keep = True

            if keep:
                selected.append(frame_path)
            if len(selected) >= max_frames:
                break

        if not selected:
            selected = [frame_paths[0]]
        return selected[:max_frames]

    def calculate_cost_savings(
        self,
        total_frames: int,
        selected_frames: int,
        price_per_image: float,
    ) -> float:
        total_frames = max(0, int(total_frames))
        selected_frames = max(0, int(selected_frames))
        reduced = max(0, total_frames - selected_frames)
        return round(reduced * float(price_per_image), 6)

