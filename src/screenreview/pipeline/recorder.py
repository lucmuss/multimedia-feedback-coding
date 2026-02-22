# -*- coding: utf-8 -*-
"""Phase 2 recorder scaffold with file outputs and timing state."""

from __future__ import annotations

import time
import wave
from pathlib import Path

from screenreview.utils.file_utils import ensure_dir


class Recorder:
    """Recorder API scaffold used by the GUI in phase 2.

    This implementation writes placeholder files in environments without camera/audio deps.
    """

    def __init__(self, output_dir: Path | None = None) -> None:
        self._output_dir = output_dir
        self._recording = False
        self._paused = False
        self._started_at = 0.0
        self._paused_at = 0.0
        self._paused_total = 0.0
        self._video_path: Path | None = None
        self._audio_path: Path | None = None

    def set_output_dir(self, output_dir: Path) -> None:
        self._output_dir = output_dir

    def start(self, camera_index: int, mic_index: int, resolution: str) -> None:
        del camera_index, mic_index, resolution
        if self._output_dir is None:
            raise ValueError("Recorder output_dir is not set")
        ensure_dir(self._output_dir)
        self._video_path = self._output_dir / "raw_video.mp4"
        self._audio_path = self._output_dir / "raw_audio.wav"
        self._recording = True
        self._paused = False
        self._paused_total = 0.0
        self._started_at = time.monotonic()
        self._paused_at = 0.0

    def pause(self) -> None:
        if self._recording and not self._paused:
            self._paused = True
            self._paused_at = time.monotonic()

    def resume(self) -> None:
        if self._recording and self._paused:
            self._paused = False
            self._paused_total += time.monotonic() - self._paused_at
            self._paused_at = 0.0

    def stop(self) -> tuple[Path, Path]:
        if not self._recording or self._output_dir is None or self._video_path is None or self._audio_path is None:
            raise RuntimeError("Recorder is not active")
        if self._paused:
            self.resume()
        self._recording = False
        self._write_placeholder_video(self._video_path)
        self._write_placeholder_audio(self._audio_path)
        return self._video_path, self._audio_path

    def is_recording(self) -> bool:
        return self._recording

    def is_paused(self) -> bool:
        return self._paused

    def get_duration(self) -> float:
        if not self._recording:
            return 0.0
        now = self._paused_at if self._paused and self._paused_at else time.monotonic()
        return max(0.0, now - self._started_at - self._paused_total)

    def get_preview_frame(self):
        """Return a preview frame placeholder (None in fallback mode)."""
        return None

    def _write_placeholder_video(self, path: Path) -> None:
        # Placeholder container bytes; real recording is introduced when OpenCV is wired in.
        path.write_bytes(b"SCREENREVIEW_PLACEHOLDER_MP4")

    def _write_placeholder_audio(self, path: Path) -> None:
        with wave.open(str(path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(16000)
            wav_file.writeframes(b"\x00\x00" * 1600)

