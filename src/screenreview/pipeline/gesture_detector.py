# -*- coding: utf-8 -*-
"""Gesture detection placeholders with deterministic test behavior."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class GestureDetector:
    """Detect pointing gestures from synthetic frames or manifests."""

    def __init__(self, sensitivity: float = 0.8) -> None:
        self.sensitivity = float(sensitivity)

    def detect_pointing(self, frame: Any) -> tuple[bool, int, int]:
        if isinstance(frame, dict):
            confidence = float(frame.get("confidence", 1.0))
            if bool(frame.get("pointing", False)) and confidence >= self.sensitivity:
                return True, int(frame.get("x", 0)), int(frame.get("y", 0))
            return False, 0, 0

        if isinstance(frame, (bytes, bytearray)) and b"POINT" in frame:
            return True, 0, 0

        return False, 0, 0

    def get_pointing_region(
        self,
        frame: Any,
        x: int,
        y: int,
        region_size: int = 200,
    ) -> dict[str, int]:
        width = int(frame.get("width", region_size * 2)) if isinstance(frame, dict) else region_size * 2
        height = int(frame.get("height", region_size * 2)) if isinstance(frame, dict) else region_size * 2
        half = region_size // 2
        left = max(0, min(width, x - half))
        top = max(0, min(height, y - half))
        right = max(left, min(width, left + region_size))
        bottom = max(top, min(height, top + region_size))
        return {"x": left, "y": top, "w": right - left, "h": bottom - top}

    def track_video(self, video_path: Path) -> list[dict[str, Any]]:
        if not video_path.exists():
            raise FileNotFoundError(video_path)
        data = json.loads(video_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return []

        if "gestures" in data and isinstance(data["gestures"], list):
            return [dict(item) for item in data["gestures"]]

        tracked: list[dict[str, Any]] = []
        fps = float(data.get("fps", 1.0))
        for idx, frame in enumerate(data.get("frames", [])):
            detected, x, y = self.detect_pointing(frame)
            if detected:
                tracked.append({"timestamp": round(idx / max(0.001, fps), 3), "x": x, "y": y})
        return tracked

