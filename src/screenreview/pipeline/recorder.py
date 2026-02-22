# -*- coding: utf-8 -*-
"""Recorder with optional live camera/audio capture and placeholder fallback."""

from __future__ import annotations

import logging
import threading
import time
import wave
from pathlib import Path
from typing import Any

from screenreview.utils.file_utils import ensure_dir

try:  # Optional runtime dependency for webcam capture + preview
    import cv2  # type: ignore[import-not-found]
except Exception:  # pragma: no cover - depends on local environment
    cv2 = None  # type: ignore[assignment]

try:  # Optional runtime dependency used by sounddevice callbacks
    import numpy as np  # type: ignore[import-not-found]
except Exception:  # pragma: no cover - depends on local environment
    np = None  # type: ignore[assignment]

try:  # Optional runtime dependency for microphone capture/monitoring
    import sounddevice as sd  # type: ignore[import-not-found]
except Exception:  # pragma: no cover - depends on local environment
    sd = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

RESOLUTION_PRESETS: dict[str, tuple[int, int]] = {
    "480p": (640, 480),
    "720p": (1280, 720),
    "1080p": (1920, 1080),
    "1440p": (2560, 1440),
    "4k": (3840, 2160),
}


def _resolution_size(resolution: str) -> tuple[int, int]:
    raw = str(resolution).strip().lower()
    if raw in RESOLUTION_PRESETS:
        return RESOLUTION_PRESETS[raw]
    if "x" in raw:
        left, right = raw.split("x", 1)
        try:
            width = max(1, int(left))
            height = max(1, int(right))
            return (width, height)
        except ValueError:
            pass
    return RESOLUTION_PRESETS["1080p"]


def _match_resolution_label(width: int, height: int) -> str:
    for label, (rw, rh) in RESOLUTION_PRESETS.items():
        if abs(width - rw) <= 32 and abs(height - rh) <= 32:
            return label
    return f"{width}x{height}"


class CameraPreviewMonitor:
    """Continuous webcam preview monitor for settings diagnostics."""

    def __init__(self) -> None:
        self._camera_index = 0
        self._resolution = "1080p"
        self._capture: Any = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._last_frame: Any = None
        self._last_error = ""
        self._running = False

    def start(self, camera_index: int, resolution: str) -> None:
        self.stop()
        self._camera_index = int(camera_index)
        self._resolution = str(resolution or "1080p")
        if cv2 is None:
            self._last_error = "OpenCV is not installed."
            return
        try:
            capture = cv2.VideoCapture(self._camera_index)
            if capture is None or not capture.isOpened():
                self._last_error = f"Camera index {self._camera_index} could not be opened."
                try:
                    if capture is not None:
                        capture.release()
                except Exception:
                    pass
                return
            width, height = _resolution_size(self._resolution)
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            capture.set(cv2.CAP_PROP_FPS, 20)
            self._capture = capture
            self._stop_event.clear()
            self._running = True
            self._last_error = ""
            self._thread = threading.Thread(
                target=self._loop,
                name="screenreview-camera-preview-monitor",
                daemon=True,
            )
            self._thread.start()
        except Exception as exc:  # pragma: no cover - hardware/runtime path
            logger.exception("Failed to start camera preview monitor")
            self._last_error = str(exc)
            self._running = False
            try:
                if self._capture is not None:
                    self._capture.release()
            except Exception:
                pass
            self._capture = None

    def stop(self) -> None:
        self._stop_event.set()
        thread = self._thread
        self._thread = None
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.5)
        if self._capture is not None:
            try:
                self._capture.release()
            except Exception:
                pass
            self._capture = None
        self._running = False

    def is_running(self) -> bool:
        return bool(self._running)

    def get_last_frame(self) -> Any:
        with self._lock:
            frame = self._last_frame
            if frame is None:
                return None
            try:
                return frame.copy()
            except Exception:
                return frame

    def get_last_error(self) -> str:
        with self._lock:
            return str(self._last_error)

    def _loop(self) -> None:
        capture = self._capture
        if capture is None:
            return
        while not self._stop_event.is_set():
            try:
                ok, frame = capture.read()
            except Exception as exc:  # pragma: no cover - hardware/runtime path
                logger.exception("Camera preview monitor read failed")
                with self._lock:
                    self._last_error = str(exc)
                break
            if ok and frame is not None:
                with self._lock:
                    self._last_frame = frame.copy() if hasattr(frame, "copy") else frame
                    self._last_error = ""
            else:
                with self._lock:
                    self._last_error = "No frame received from camera."
                time.sleep(0.03)
                continue
            time.sleep(0.01)
        self._running = False


class AudioLevelMonitor:
    """Continuous microphone level monitor for settings diagnostics."""

    def __init__(self) -> None:
        self._mic_index = 0
        self._stream: Any = None
        self._lock = threading.Lock()
        self._level = 0.0
        self._last_error = ""
        self._running = False
        self._sample_rate = 16000
        self._channels = 1

    def start(self, mic_index: int) -> None:
        self.stop()
        self._mic_index = int(mic_index)
        if sd is None or np is None:
            self._last_error = "sounddevice/numpy not installed."
            return
        try:
            def _callback(indata, frames, time_info, status) -> None:  # pragma: no cover - callback
                del frames, time_info
                if status:
                    logger.warning("Audio level monitor callback status: %s", status)
                try:
                    rms = float(np.sqrt(np.mean(np.square(indata))))
                    level = max(0.0, min(1.0, rms * 6.0))
                    with self._lock:
                        self._level = level
                        self._last_error = ""
                except Exception as exc:
                    with self._lock:
                        self._last_error = str(exc)

            self._stream = sd.InputStream(
                samplerate=self._sample_rate,
                channels=self._channels,
                dtype="float32",
                device=self._mic_index,
                callback=_callback,
            )
            self._stream.start()
            with self._lock:
                self._level = 0.0
                self._last_error = ""
            self._running = True
        except Exception as exc:  # pragma: no cover - hardware/runtime path
            logger.exception("Failed to start audio level monitor")
            self._last_error = str(exc)
            self._running = False
            try:
                if self._stream is not None:
                    self._stream.stop()
                    self._stream.close()
            except Exception:
                pass
            self._stream = None

    def stop(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop()
            except Exception:
                pass
            try:
                self._stream.close()
            except Exception:
                pass
        self._stream = None
        self._running = False
        with self._lock:
            self._level = 0.0

    def is_running(self) -> bool:
        return bool(self._running)

    def get_level(self) -> float:
        with self._lock:
            return float(self._level)

    def get_last_error(self) -> str:
        with self._lock:
            return str(self._last_error)


class Recorder:
    """Recorder API used by the GUI.

    The recorder prefers live hardware capture (OpenCV + sounddevice) and falls back to
    placeholder files when optional dependencies or devices are unavailable.
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
        self._last_duration = 0.0
        self._audio_level = 0.0
        self._backend_mode = "placeholder"
        self._backend_notes: list[str] = []
        self._active_resolution = "1080p"
        self._camera_index = 0
        self._mic_index = 0

        self._stop_event = threading.Event()
        self._state_lock = threading.Lock()
        self._video_thread: threading.Thread | None = None
        self._capture: Any = None
        self._writer: Any = None
        self._last_preview_frame: Any = None
        self._video_frames_written = 0
        self._video_opened = False

        self._audio_stream: Any = None
        self._audio_wave: wave.Wave_write | None = None
        self._audio_frames_written = 0
        self._audio_sample_rate = 16000
        self._audio_channels = 1

    def set_output_dir(self, output_dir: Path) -> None:
        self._output_dir = output_dir

    @classmethod
    def capture_capabilities(cls) -> dict[str, Any]:
        """Return capability flags for diagnostics and UI messaging."""
        return {
            "opencv_available": cv2 is not None,
            "numpy_available": np is not None,
            "sounddevice_available": sd is not None,
            "live_video_supported": cv2 is not None,
            "live_audio_supported": sd is not None and np is not None,
        }

    @classmethod
    def capture_single_frame(
        cls,
        camera_index: int,
        resolution: str = "1080p",
        timeout_seconds: float = 1.0,
    ) -> dict[str, Any]:
        """Capture one webcam frame for preview diagnostics."""
        if cv2 is None:
            return {"ok": False, "message": "OpenCV is not installed.", "frame": None}
        width, height = _resolution_size(resolution)
        capture = None
        started = time.monotonic()
        try:
            capture = cv2.VideoCapture(int(camera_index))
            if not capture or not capture.isOpened():
                return {
                    "ok": False,
                    "message": f"Camera index {camera_index} could not be opened.",
                    "frame": None,
                }
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

            frame = None
            while time.monotonic() - started < max(0.2, float(timeout_seconds)):
                ok, current = capture.read()
                if ok and current is not None:
                    frame = current
                    break
                time.sleep(0.03)
            if frame is None:
                return {"ok": False, "message": "No frame received from camera.", "frame": None}
            frame_height = int(getattr(frame, "shape", [0, 0])[0]) if hasattr(frame, "shape") else 0
            frame_width = int(getattr(frame, "shape", [0, 0])[1]) if hasattr(frame, "shape") else 0
            return {
                "ok": True,
                "message": f"Preview frame captured ({frame_width}x{frame_height}).",
                "frame": frame,
                "width": frame_width,
                "height": frame_height,
            }
        except Exception as exc:  # pragma: no cover - hardware/runtime path
            logger.exception("Camera preview probe failed for index=%s", camera_index)
            return {"ok": False, "message": str(exc), "frame": None}
        finally:
            try:
                if capture is not None:
                    capture.release()
            except Exception:
                pass

    @classmethod
    def sample_audio_input_level(
        cls,
        mic_index: int,
        duration_seconds: float = 0.35,
        sample_rate: int = 16000,
    ) -> dict[str, Any]:
        """Record a short microphone sample and return a normalized level."""
        if sd is None or np is None:
            return {
                "ok": False,
                "message": "sounddevice/numpy not installed.",
                "level": 0.0,
                "peak": 0.0,
            }
        try:
            frames = max(1, int(float(duration_seconds) * int(sample_rate)))
            data = sd.rec(
                frames,
                samplerate=int(sample_rate),
                channels=1,
                dtype="float32",
                device=int(mic_index),
            )
            sd.wait()
            if data is None or len(data) == 0:
                return {"ok": False, "message": "No audio sample captured.", "level": 0.0, "peak": 0.0}
            rms = float(np.sqrt(np.mean(np.square(data))))
            peak = float(np.max(np.abs(data)))
            level = max(0.0, min(1.0, rms * 6.0))
            return {
                "ok": True,
                "message": f"Audio sample captured (rms={rms:.4f}, peak={peak:.4f}).",
                "level": level,
                "rms": rms,
                "peak": peak,
            }
        except Exception as exc:  # pragma: no cover - hardware/runtime path
            logger.exception("Audio probe failed for mic index=%s", mic_index)
            return {"ok": False, "message": str(exc), "level": 0.0, "peak": 0.0}

    @classmethod
    def probe_camera_resolution_options(
        cls,
        camera_index: int,
        candidate_labels: list[str] | None = None,
    ) -> dict[str, Any]:
        """Probe a camera and return a device-specific list of supported resolution labels."""
        labels_to_probe = candidate_labels or ["480p", "720p", "1080p", "1440p", "4k"]
        if cv2 is None:
            return {
                "ok": False,
                "options": ["720p", "1080p", "4k"],
                "message": "OpenCV is not installed. Using default resolution presets.",
            }
        capture = None
        supported: list[str] = []
        actual_sizes: dict[str, str] = {}
        try:
            capture = cv2.VideoCapture(int(camera_index))
            if capture is None or not capture.isOpened():
                return {
                    "ok": False,
                    "options": ["720p", "1080p", "4k"],
                    "message": f"Camera index {camera_index} could not be opened. Using default presets.",
                }
            for label in labels_to_probe:
                target_w, target_h = _resolution_size(label)
                try:
                    capture.set(cv2.CAP_PROP_FRAME_WIDTH, target_w)
                    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, target_h)
                except Exception:
                    continue
                frame = None
                for _ in range(4):
                    ok, current = capture.read()
                    if ok and current is not None:
                        frame = current
                        break
                    time.sleep(0.03)
                if frame is None or not hasattr(frame, "shape"):
                    continue
                try:
                    actual_h = int(frame.shape[0])
                    actual_w = int(frame.shape[1])
                except Exception:
                    continue
                # Accept if actual resolution matches requested closely.
                if abs(actual_w - target_w) <= 64 and abs(actual_h - target_h) <= 64:
                    if label not in supported:
                        supported.append(label)
                        actual_sizes[label] = f"{actual_w}x{actual_h}"
            if not supported:
                # Fall back to a single detected current size if probing does not match known presets.
                ok, frame = capture.read()
                if ok and frame is not None and hasattr(frame, "shape"):
                    actual_h = int(frame.shape[0])
                    actual_w = int(frame.shape[1])
                    inferred = _match_resolution_label(actual_w, actual_h)
                    supported = [inferred]
                    actual_sizes[inferred] = f"{actual_w}x{actual_h}"
            if not supported:
                supported = ["720p", "1080p", "4k"]
                return {
                    "ok": False,
                    "options": supported,
                    "message": "Could not verify camera resolutions. Using default presets.",
                }
            details = ", ".join(f"{label} ({actual_sizes.get(label, '')})".strip() for label in supported)
            return {
                "ok": True,
                "options": supported,
                "message": f"Detected supported resolutions: {details}",
            }
        except Exception as exc:  # pragma: no cover - hardware/runtime path
            logger.exception("Camera resolution probe failed for index=%s", camera_index)
            return {
                "ok": False,
                "options": ["720p", "1080p", "4k"],
                "message": str(exc),
            }
        finally:
            try:
                if capture is not None:
                    capture.release()
            except Exception:
                pass

    def start(self, camera_index: int, mic_index: int, resolution: str) -> None:
        if self._recording:
            raise RuntimeError("Recorder is already active")
        if self._output_dir is None:
            raise ValueError("Recorder output_dir is not set")
        ensure_dir(self._output_dir)
        self._video_path = self._output_dir / "raw_video.mp4"
        self._audio_path = self._output_dir / "raw_audio.wav"
        self._camera_index = int(camera_index)
        self._mic_index = int(mic_index)
        self._active_resolution = str(resolution or "1080p")
        self._recording = True
        self._paused = False
        self._paused_total = 0.0
        self._started_at = time.monotonic()
        self._last_duration = 0.0
        self._paused_at = 0.0
        self._audio_level = 0.0
        self._backend_mode = "placeholder"
        self._backend_notes = []
        self._video_frames_written = 0
        self._audio_frames_written = 0
        self._video_opened = False
        self._last_preview_frame = None
        self._stop_event.clear()

        self._start_live_backends()

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
        self._last_duration = max(0.0, time.monotonic() - self._started_at - self._paused_total)
        self._recording = False
        self._stop_event.set()
        self._stop_live_backends()
        self._ensure_output_files()
        self._audio_level = 0.0
        return self._video_path, self._audio_path

    def is_recording(self) -> bool:
        return self._recording

    def is_paused(self) -> bool:
        return self._paused

    def get_duration(self) -> float:
        if not self._recording:
            return self._last_duration
        now = self._paused_at if self._paused and self._paused_at else time.monotonic()
        return max(0.0, now - self._started_at - self._paused_total)

    def get_preview_frame(self) -> Any:
        """Return the latest preview frame if live video capture is active."""
        with self._state_lock:
            if self._last_preview_frame is None:
                return None
            frame = self._last_preview_frame
            try:
                if hasattr(frame, "copy"):
                    return frame.copy()
            except Exception:
                pass
            return frame

    def get_audio_level(self) -> float:
        """Return normalized current microphone level (0..1)."""
        with self._state_lock:
            return float(self._audio_level)

    def get_backend_mode(self) -> str:
        """Return runtime backend mode: live, mixed, or placeholder."""
        return self._backend_mode

    def get_backend_notes(self) -> list[str]:
        """Return runtime backend notes for diagnostics."""
        return list(self._backend_notes)

    def _start_live_backends(self) -> None:
        video_started = self._start_live_video_backend()
        audio_started = self._start_live_audio_backend()
        if video_started and audio_started:
            self._backend_mode = "live"
        elif video_started or audio_started:
            self._backend_mode = "mixed"
            self._backend_notes.append("Partial live capture active; missing streams use placeholders.")
        else:
            self._backend_mode = "placeholder"
            self._backend_notes.append("No live capture backend available; placeholder files will be written.")

    def _start_live_video_backend(self) -> bool:
        if cv2 is None:
            self._backend_notes.append("OpenCV not installed (video capture unavailable).")
            return False
        if self._video_path is None:
            return False
        try:
            width, height = _resolution_size(self._active_resolution)
            capture = cv2.VideoCapture(self._camera_index)
            if capture is None or not capture.isOpened():
                self._backend_notes.append(f"Camera index {self._camera_index} could not be opened.")
                try:
                    if capture is not None:
                        capture.release()
                except Exception:
                    pass
                return False
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            capture.set(cv2.CAP_PROP_FPS, 20)
            self._capture = capture
            self._video_opened = True
            self._video_thread = threading.Thread(
                target=self._video_capture_loop,
                name="screenreview-video-capture",
                daemon=True,
            )
            self._video_thread.start()
            self._backend_notes.append(
                f"Live webcam capture started (camera={self._camera_index}, target={width}x{height})."
            )
            return True
        except Exception as exc:  # pragma: no cover - hardware/runtime path
            logger.exception("Failed to start video capture backend")
            self._backend_notes.append(f"Video backend error: {exc}")
            self._video_opened = False
            try:
                if self._capture is not None:
                    self._capture.release()
            except Exception:
                pass
            self._capture = None
            return False

    def _start_live_audio_backend(self) -> bool:
        if sd is None or np is None:
            self._backend_notes.append("sounddevice/numpy not installed (audio capture unavailable).")
            return False
        if self._audio_path is None:
            return False
        try:
            self._audio_sample_rate = 16000
            self._audio_channels = 1
            wav_file = wave.open(str(self._audio_path), "wb")
            wav_file.setnchannels(self._audio_channels)
            wav_file.setsampwidth(2)
            wav_file.setframerate(self._audio_sample_rate)
            self._audio_wave = wav_file

            def _callback(indata, frames, time_info, status) -> None:  # pragma: no cover - callback
                del frames, time_info
                if status:
                    logger.warning("Audio callback status: %s", status)
                if not self._recording or self._audio_wave is None:
                    return
                if self._paused:
                    with self._state_lock:
                        self._audio_level = 0.0
                    return
                try:
                    rms = float(np.sqrt(np.mean(np.square(indata))))
                    normalized = max(0.0, min(1.0, rms * 6.0))
                    pcm = np.clip(indata, -1.0, 1.0)
                    pcm = (pcm * 32767.0).astype(np.int16)
                    with self._state_lock:
                        self._audio_level = normalized
                    self._audio_wave.writeframes(pcm.tobytes())
                    self._audio_frames_written += len(pcm)
                except Exception as exc:
                    logger.exception("Audio callback error")
                    self._backend_notes.append(f"Audio callback error: {exc}")

            self._audio_stream = sd.InputStream(
                samplerate=self._audio_sample_rate,
                channels=self._audio_channels,
                dtype="float32",
                device=self._mic_index,
                callback=_callback,
            )
            self._audio_stream.start()
            self._backend_notes.append(f"Live audio capture started (mic={self._mic_index}).")
            return True
        except Exception as exc:  # pragma: no cover - hardware/runtime path
            logger.exception("Failed to start audio capture backend")
            self._backend_notes.append(f"Audio backend error: {exc}")
            try:
                if self._audio_stream is not None:
                    self._audio_stream.stop()
                    self._audio_stream.close()
            except Exception:
                pass
            self._audio_stream = None
            if self._audio_wave is not None:
                try:
                    self._audio_wave.close()
                except Exception:
                    pass
            self._audio_wave = None
            return False

    def _video_capture_loop(self) -> None:
        capture = self._capture
        if capture is None:
            return
        while not self._stop_event.is_set():
            try:
                ok, frame = capture.read()
            except Exception as exc:  # pragma: no cover - hardware/runtime path
                logger.exception("Video capture read failed")
                self._backend_notes.append(f"Video read error: {exc}")
                break
            if not ok or frame is None:
                time.sleep(0.03)
                continue
            with self._state_lock:
                self._last_preview_frame = frame.copy() if hasattr(frame, "copy") else frame
            if self._paused:
                time.sleep(0.01)
                continue
            self._ensure_video_writer(frame)
            if self._writer is not None:
                try:
                    self._writer.write(frame)
                    self._video_frames_written += 1
                except Exception as exc:  # pragma: no cover - hardware/runtime path
                    logger.exception("Video writer failed")
                    self._backend_notes.append(f"Video writer error: {exc}")
                    break
            time.sleep(0.01)

    def _ensure_video_writer(self, frame: Any) -> None:
        if self._writer is not None or self._video_path is None or cv2 is None:
            return
        if not hasattr(frame, "shape"):
            return
        try:
            height = int(frame.shape[0])
            width = int(frame.shape[1])
        except Exception:
            return
        fps = 20.0
        candidates = ["mp4v", "avc1", "XVID", "MJPG"]
        for codec_name in candidates:
            try:
                writer = cv2.VideoWriter(
                    str(self._video_path),
                    cv2.VideoWriter_fourcc(*codec_name),
                    fps,
                    (width, height),
                )
            except Exception:
                writer = None
            if writer is not None and writer.isOpened():
                self._writer = writer
                self._backend_notes.append(
                    f"Video writer started with codec {codec_name} at {width}x{height}."
                )
                return
            try:
                if writer is not None:
                    writer.release()
            except Exception:
                pass
        self._backend_notes.append("No working video codec found for OpenCV writer; using placeholder video.")

    def _stop_live_backends(self) -> None:
        video_thread = self._video_thread
        self._video_thread = None
        if video_thread is not None and video_thread.is_alive():
            video_thread.join(timeout=2.0)

        if self._writer is not None:
            try:
                self._writer.release()
            except Exception:
                pass
            self._writer = None

        if self._capture is not None:
            try:
                self._capture.release()
            except Exception:
                pass
            self._capture = None

        if self._audio_stream is not None:
            try:
                self._audio_stream.stop()
            except Exception:
                pass
            try:
                self._audio_stream.close()
            except Exception:
                pass
            self._audio_stream = None

        if self._audio_wave is not None:
            try:
                self._audio_wave.close()
            except Exception:
                pass
            self._audio_wave = None

    def _ensure_output_files(self) -> None:
        if self._video_path is None or self._audio_path is None:
            return
        if not self._video_path.exists() or self._video_path.stat().st_size == 0:
            self._write_placeholder_video(self._video_path)
            if self._backend_mode != "placeholder":
                self._backend_notes.append("Video output missing; placeholder video written.")

        if not self._audio_path.exists():
            self._write_placeholder_audio(self._audio_path)
            if self._backend_mode != "placeholder":
                self._backend_notes.append("Audio output missing; placeholder audio written.")
            return
        if self._audio_frames_written <= 0:
            # Replace a header-only/empty wav with short silence.
            self._write_placeholder_audio(self._audio_path)
            if self._backend_mode != "placeholder":
                self._backend_notes.append("No audio samples captured; placeholder audio written.")

    def _write_placeholder_video(self, path: Path) -> None:
        # Placeholder container bytes; real recording is introduced when OpenCV is wired in.
        path.write_bytes(b"SCREENREVIEW_PLACEHOLDER_MP4")

    def _write_placeholder_audio(self, path: Path) -> None:
        with wave.open(str(path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(16000)
            wav_file.writeframes(b"\x00\x00" * 1600)
