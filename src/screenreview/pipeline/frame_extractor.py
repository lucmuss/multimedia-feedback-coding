# -*- coding: utf-8 -*-
"""Frame extraction with a synthetic manifest fallback for tests."""

from __future__ import annotations

import base64
import json
import math
from pathlib import Path

from screenreview.utils.file_utils import ensure_dir
from screenreview.utils.image_utils import decode_base64_to_file


class FrameExtractor:
    """Extract frames from a synthetic manifest or a directory of PNG files."""

    def extract_time_based(
        self,
        video_path: Path,
        interval_seconds: int,
        output_dir: Path | None = None,
    ) -> list[Path]:
        """Extract a frame at a fixed time interval."""
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be > 0")

        manifest = self._load_manifest(video_path)
        frames = manifest["frames"]
        if not frames:
            return []

        duration = float(manifest.get("duration_seconds", 0))
        fps = float(manifest.get("fps", 1.0))
        timestamps: list[float] = []
        current = 0.0
        while current <= duration + 1e-9:
            timestamps.append(current)
            current += interval_seconds
        if not timestamps:
            timestamps = [0.0]
        if len(frames) and timestamps == [0.0]:
            pass

        selected_indices = []
        for ts in timestamps:
            index = min(len(frames) - 1, max(0, int(math.floor(ts * fps))))
            if index not in selected_indices:
                selected_indices.append(index)
        if not selected_indices and frames:
            selected_indices = [0]

        selected_frames = [frames[index] for index in selected_indices]
        return self.save_frames(selected_frames, output_dir or (video_path.parent / ".extraction"))

    def extract_all(
        self,
        video_path: Path,
        fps: float,
        output_dir: Path | None = None,
    ) -> list[Path]:
        """Extract all frames from the synthetic manifest."""
        del fps
        manifest = self._load_manifest(video_path)
        frames = manifest["frames"]
        if not frames:
            return []
        return self.save_frames(frames, output_dir or (video_path.parent / ".extraction"))

    def save_frames(self, frames: list[dict], output_dir: Path) -> list[Path]:
        """Persist frames as sequential PNG files."""
        ensure_dir(output_dir)
        saved_paths: list[Path] = []
        for index, frame in enumerate(frames, start=1):
            file_path = output_dir / f"frame_{index:04d}.png"
            if "png_base64" in frame:
                decode_base64_to_file(str(frame["png_base64"]), file_path)
            elif "bytes_hex" in frame:
                file_path.write_bytes(bytes.fromhex(str(frame["bytes_hex"])))
            else:
                file_path.write_bytes(b"")
            saved_paths.append(file_path)
        return saved_paths

    def _load_manifest(self, video_path: Path) -> dict:
        if not video_path.exists():
            raise FileNotFoundError(video_path)

        if video_path.is_dir():
            frames = []
            for frame_path in sorted(video_path.glob("*.png")):
                frames.append({"png_base64": base64.b64encode(frame_path.read_bytes()).decode("ascii")})
            return {"frames": frames, "fps": 1.0, "duration_seconds": max(0, len(frames) - 1)}

        if video_path.suffix in {".json", ".srvideo"} or video_path.name.endswith(".srvideo.json"):
            data = json.loads(video_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("Synthetic video manifest must be a JSON object")
            data.setdefault("frames", [])
            data.setdefault("fps", 1.0)
            data.setdefault("duration_seconds", 0.0)
            return data

        raise ValueError("Unsupported video format without OpenCV/FFmpeg in phase 2")
