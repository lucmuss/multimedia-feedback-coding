# -*- coding: utf-8 -*-
"""Frame extraction from video using FFmpeg."""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class FrameExtractor:
    """Extract frames from video files using FFmpeg."""

    def __init__(self, fps: float = 1.0) -> None:
        self.fps = fps  # Frames per second to extract

    def extract_frames(self, video_path: Path, output_dir: Path,
                      prefix: str = "frame_", start_time: float = 0.0) -> list[Path]:
        """Extract frames from video at specified intervals."""
        logger.info(f"[B1] Starting frame extraction for video: {video_path}")
        logger.debug(f"[B1] Output directory: {output_dir}")
        logger.debug(f"[B1] Prefix: {prefix}, start_time: {start_time}")

        if not video_path.exists():
            logger.error(f"[B1] Video file does not exist: {video_path}")
            raise FileNotFoundError(video_path)

        # Validate video file has minimum size (at least 1KB)
        file_size = video_path.stat().st_size
        logger.debug(f"[B1] Video file size: {file_size} bytes")
        if file_size < 1024:
            logger.warning(f"[B1] Video file too small ({file_size} bytes), skipping frame extraction")
            return []

        logger.debug(f"[B1] Creating output directory: {output_dir}")
        output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"[B1] Output directory created/verified: {output_dir}")

        # FFmpeg command to extract frames
        output_pattern = output_dir / f"{prefix}%04d.png"

        cmd = [
            "ffmpeg",
            "-i", str(video_path),  # Input video
            "-vf", f"fps={self.fps}",  # Extract at specified FPS
            "-start_number", "1",  # Start numbering from 1
            "-q:v", "2",  # Quality setting (2 = high quality)
            "-y",  # Overwrite output files
            str(output_pattern)
        ]

        logger.info(f"Extracting frames from {video_path} to {output_dir}")
        logger.debug(f"FFmpeg command: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            if result.returncode != 0:
                logger.error(f"FFmpeg failed: {result.stderr}")
                return []

            # Find extracted frames
            extracted_frames = []
            for frame_file in sorted(output_dir.glob(f"{prefix}*.png")):
                extracted_frames.append(frame_file)

            logger.info(f"Extracted {len(extracted_frames)} frames")
            return extracted_frames

        except subprocess.TimeoutExpired:
            logger.error("FFmpeg extraction timed out")
            return []
        except Exception as e:
            logger.error(f"Frame extraction failed: {e}")
            return []

    def get_video_info(self, video_path: Path) -> dict[str, Any]:
        """Get video information using FFmpeg."""
        if not video_path.exists():
            raise FileNotFoundError(video_path)

        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(video_path)
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                logger.error(f"FFprobe failed: {result.stderr}")
                return {}

            info = json.loads(result.stdout)

            # Extract relevant information
            video_info = {
                "duration": 0.0,
                "width": 0,
                "height": 0,
                "fps": 0.0,
                "codec": "unknown"
            }

            if "format" in info:
                video_info["duration"] = float(info["format"].get("duration", 0))

            for stream in info.get("streams", []):
                if stream.get("codec_type") == "video":
                    video_info["width"] = stream.get("width", 0)
                    video_info["height"] = stream.get("height", 0)
                    video_info["codec"] = stream.get("codec_name", "unknown")

                    # Calculate FPS
                    fps_parts = stream.get("r_frame_rate", "0/1").split("/")
                    if len(fps_parts) == 2 and fps_parts[1] != "0":
                        video_info["fps"] = float(fps_parts[0]) / float(fps_parts[1])

                    break

            return video_info

        except Exception as e:
            logger.error(f"Failed to get video info: {e}")
            return {}

    def smart_select_frames(self, frame_paths: list[Path], audio_levels: list[float] = None,
                           gesture_detected: list[bool] = None) -> list[Path]:
        """Smart selection of relevant frames based on audio and gestures."""
        if not frame_paths:
            return []

        selected = []

        for i, frame_path in enumerate(frame_paths):
            should_select = False

            # Always select first and last frame
            if i == 0 or i == len(frame_paths) - 1:
                should_select = True

            # Select if gesture detected
            if gesture_detected and i < len(gesture_detected) and gesture_detected[i]:
                should_select = True

            # Select if audio level is high
            if audio_levels and i < len(audio_levels) and audio_levels[i] > 0.1:
                should_select = True

            # Select every 3rd frame as fallback
            if i % 3 == 0:
                should_select = True

            if should_select:
                selected.append(frame_path)

        logger.info(f"Smart selected {len(selected)}/{len(frame_paths)} frames")
        return selected