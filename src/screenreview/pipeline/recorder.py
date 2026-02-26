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

_CAMERA_INIT_LOCK = threading.RLock()

def _open_camera(camera_source: int | str) -> Any:
    """Safely open OpenCV VideoCapture, using DShow on Windows for local indices, protected by a lock."""
    import sys
    
    # Bypass lock for network streams as they don't collide with hardware drivers
    # and can block for a long time.
    if isinstance(camera_source, str) and (camera_source.startswith("udp://") or camera_source.startswith("http")):
        logger.debug("Opening custom camera stream: %s", camera_source)
        # Try CAP_FFMPEG first for network streams as it handles UDP/HTTP much better
        cap = cv2.VideoCapture(camera_source, cv2.CAP_FFMPEG)
        if cap is not None and cap.isOpened():
            return cap
        logger.debug("CAP_FFMPEG failed for stream, trying default backend for: %s", camera_source)
        return cv2.VideoCapture(camera_source)

    acquired = _CAMERA_INIT_LOCK.acquire(timeout=5.0)
    if not acquired:
        logger.error("Timeout retrieving global camera lock for source %s", camera_source)
        return None
    try:
        source_idx = int(camera_source)
        if sys.platform == "win32":
            logger.debug("Using cv2.CAP_DSHOW for Camera %s to avoid MSMF freeze", source_idx)
            return cv2.VideoCapture(source_idx, cv2.CAP_DSHOW)
        return cv2.VideoCapture(source_idx)
    finally:
        _CAMERA_INIT_LOCK.release()


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
        self._custom_url = ""
        self._resolution = "1080p"
        self._capture: Any = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._last_frame: Any = None
        self._last_error = ""
        self._running = False

    def start(self, camera_index: int, resolution: str, custom_url: str = "") -> None:
        logger.info(
            "CameraPreviewMonitor.start requested for camera_index=%s, resolution=%s, custom_url=%s",
            camera_index, resolution, custom_url
        )
        self.stop()
        self._camera_index = int(camera_index)
        self._custom_url = str(custom_url or "").strip()
        self._resolution = str(resolution or "1080p")
        if cv2 is None:
            logger.error("OpenCV is not installed. CameraPreviewMonitor cannot start.")
            self._last_error = "OpenCV is not installed."
            return
        
        self._stop_event.clear()
        self._running = True
        self._last_error = ""
        self._capture = None
        logger.debug("Starting CameraPreviewMonitor background thread.")
        self._thread = threading.Thread(
            target=self._loop,
            name="screenreview-camera-preview-monitor",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        logger.debug("CameraPreviewMonitor.stop requested. running=%s", self._running)
        self._stop_event.set()
        thread = self._thread
        self._thread = None
        if thread is not None and thread.is_alive():
            logger.debug("Waiting for CameraPreviewMonitor thread to join...")
            thread.join(timeout=1.5)
            logger.debug("CameraPreviewMonitor thread joined.")
        if self._capture is not None:
            logger.debug("Releasing CameraPreviewMonitor cv2 capture.")
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
        source = self._custom_url if self._custom_url else self._camera_index
        logger.info("CameraPreviewMonitor _loop started for source=%s", source)
        try:
            logger.debug("Calling _open_camera(%s)...", source)
            capture = _open_camera(source)
            if capture is None or not capture.isOpened():
                err_msg = f"Camera source {source} could not be opened."
                logger.error(err_msg)
                with self._lock:
                    self._last_error = err_msg
                if capture is not None:
                    try:
                        logger.debug("Releasing failed capture.")
                        capture.release()
                    except Exception as exc:
                        logger.error("Error releasing failed capture: %s", exc)
                self._running = False
                return
            
            logger.debug("cv2.VideoCapture opened successfully for camera_index=%s", self._camera_index)
            width, height = _resolution_size(self._resolution)
            logger.debug("Setting camera properties: width=%s, height=%s, fps=20", width, height)
            try:
                capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
                capture.set(cv2.CAP_PROP_FPS, 20)
            except Exception as e:
                logger.warning("Failed to set camera properties in preview monitor: %s", e)
            self._capture = capture
        except Exception as exc:
            logger.exception("Failed to initialize camera in CameraPreviewMonitor.")
            with self._lock:
                self._last_error = f"Failed to initialize camera: {exc}"
            self._running = False
            return

        while not self._stop_event.is_set():
            try:
                ok, frame = capture.read()
            except Exception as exc:  # pragma: no cover - hardware/runtime path
                logger.exception("Camera preview monitor read failed continuously")
                with self._lock:
                    self._last_error = str(exc)
                break
            if ok and frame is not None:
                with self._lock:
                    self._last_frame = frame.copy() if hasattr(frame, "copy") else frame
                    self._last_error = ""
            else:
                with self._lock:
                    if self._last_error != "No frame received from camera.":
                        logger.warning("CameraPreviewMonitor: No frame received from camera index %s", self._camera_index)
                    self._last_error = "No frame received from camera."
                time.sleep(0.03)
                continue
            time.sleep(0.01)
        logger.info("CameraPreviewMonitor _loop exiting for camera_index=%s", self._camera_index)
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
        logger.info("AudioLevelMonitor.start requested for mic_index=%s", mic_index)
        self.stop()
        self._mic_index = int(mic_index)
        if sd is None or np is None:
            logger.error("sounddevice/numpy not installed. AudioLevelMonitor cannot start.")
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

            logger.debug("Opening sd.InputStream for mic_index=%s, samplerate=%s", self._mic_index, self._sample_rate)
            self._stream = sd.InputStream(
                samplerate=self._sample_rate,
                channels=self._channels,
                dtype="float32",
                device=self._mic_index,
                callback=_callback,
            )
            logger.debug("Starting AudioLevelMonitor stream...")
            self._stream.start()
            logger.info("AudioLevelMonitor started successfully for mic_index=%s", self._mic_index)
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
        logger.debug("AudioLevelMonitor.stop requested. running=%s", self._running)
        if self._stream is not None:
            logger.debug("Stopping and closing AudioLevelMonitor stream.")
            try:
                self._stream.stop()
            except Exception as exc:
                logger.error("Error stopping audio stream: %s", exc)
            try:
                self._stream.close()
            except Exception as exc:
                logger.error("Error closing audio stream: %s", exc)
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
        custom_url: str = "",
    ) -> dict[str, Any]:
        """Capture one webcam frame for preview diagnostics."""
        source: int | str = str(custom_url).strip() if custom_url else int(camera_index)
        logger.info("Recorder.capture_single_frame called for source=%s, resolution=%s", source, resolution)
        if cv2 is None:
            logger.error("cv2 is missing, cannot capture frame.")
            return {"ok": False, "message": "OpenCV is not installed.", "frame": None}
        width, height = _resolution_size(resolution)
        capture = None
        started = time.monotonic()
        try:
            logger.debug("Opening _open_camera(%s)...", source)
            capture = _open_camera(source)
            if not capture or not capture.isOpened():
                return {
                    "ok": False,
                    "message": f"Camera source {source} could not be opened.",
                    "frame": None,
                }
            
            # First attempt with requested resolution
            try:
                capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            except Exception as e:
                logger.warning("Failed to set resolution for single frame capture: %s", e)

            frame = None
            logger.debug("Attempting to read frame from capture (timeout=%s sec)...", timeout_seconds)
            while time.monotonic() - started < max(0.2, float(timeout_seconds)):
                ok, current = capture.read()
                if ok and current is not None:
                    logger.debug("Successfully read a frame (pass 1).")
                    frame = current
                    break
                time.sleep(0.03)
                
            # If failed, attempt without requesting a specific resolution (camera default)
            if frame is None:
                logger.warning("Timed out waiting for frame at %sx%s, trying fallback default resolution...", width, height)
                try:
                    capture.release()
                except Exception:
                    pass
                capture = _open_camera(int(camera_index))
                if capture and capture.isOpened():
                    started_fallback = time.monotonic()
                    while time.monotonic() - started_fallback < max(0.2, float(timeout_seconds)):
                        ok, current = capture.read()
                        if ok and current is not None:
                            logger.debug("Successfully read a frame (pass 2 - fallback).")
                            frame = current
                            break
                        time.sleep(0.03)

            if frame is None:
                logger.error("Timed out waiting for frame from camera_index=%s on all passes", camera_index)
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
        logger.info("Recorder.sample_audio_input_level called for mic_index=%s, duration=%s", mic_index, duration_seconds)
        if sd is None or np is None:
            logger.error("Missing sounddevice or numpy, cannot sample audio.")
            return {
                "ok": False,
                "message": "sounddevice/numpy not installed.",
                "level": 0.0,
                "peak": 0.0,
            }
        try:
            frames = max(1, int(float(duration_seconds) * int(sample_rate)))
            logger.debug("Calling sd.rec for %s frames...", frames)
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
    def detect_gopro_url(cls) -> dict[str, Any]:
        """Scan common subnets for a GoPro (RNDIS) and return the stream URL if found."""
        import urllib.request
        import subprocess
        import threading

        subnets = set(["172.20.187", "172.21.187", "172.22.187", "172.23.187", "172.24.187", 
                       "172.25.187", "172.26.187", "172.27.187", "172.28.187", "172.29.187"])
        
        try:
            output = subprocess.check_output("ipconfig", shell=True).decode("cp850")
            for line in output.split("\n"):
                if "IPv4" in line and "172." in line:
                    ip_part = line.split(":")[-1].strip()
                    sub = ".".join(ip_part.split(".")[:3])
                    subnets.add(sub)
        except:
            pass

        found_url = ""
        def _check_ip(ip):
            nonlocal found_url
            if found_url: return
            paths = ["/gopro/camera/keep_alive", "/gopro/webcam/status"]
            for path in paths:
                url = f"http://{ip}:8080{path}"
                try:
                    with urllib.request.urlopen(url, timeout=0.4) as response:
                        if response.status in [200, 404]:
                            found_url = f"udp://@{ip}:8554"
                            return
                except:
                    pass

        threads = []
        for subnet in subnets:
            t = threading.Thread(target=_check_ip, args=(f"{subnet}.51",))
            threads.append(t)
            t.start()
        for t in threads: t.join(timeout=0.8)
            
        if found_url:
            # Optimize URL for Hero 8+ and better performance
            opt_url = f"{found_url}?overrun_nonfatal=1&fifo_size=50000000"
            return {"ok": True, "url": opt_url, "message": f"GoPro detected: {opt_url}"}
        return {"ok": False, "message": "No GoPro found via RNDIS."}

    @classmethod
    def probe_camera_resolution_options(
        cls,
        camera_index: int,
        candidate_labels: list[str] | None = None,
        custom_url: str = "",
    ) -> dict[str, Any]:
        """Probe a camera and return a device-specific list of supported resolution labels."""
        source: int | str = str(custom_url).strip() if custom_url else int(camera_index)
        logger.info("Recorder.probe_camera_resolution_options called for %s", source)
        
        labels_to_probe = candidate_labels or ["480p", "720p", "1080p", "1440p", "4k"]
        if cv2 is None:
            logger.error("OpenCV is missing for resolution probe")
            return {
                "ok": False,
                "options": ["720p", "1080p", "4k"],
                "message": "OpenCV is not installed. Using default resolution presets.",
            }
        capture = None
        supported: list[str] = []
        actual_sizes: dict[str, str] = {}
        try:
            capture = _open_camera(source)
            if capture is None or not capture.isOpened():
                return {
                    "ok": False,
                    "options": ["720p", "1080p", "4k"],
                    "message": f"Camera source {source} could not be opened. Using default presets.",
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
                logger.warning("No standard resolutions could be verified for camera_index=%s, leaving empty list.", camera_index)
                return {
                    "ok": False,
                    "options": [],
                    "message": "Could not verify camera resolutions. Suggest trying another camera or default presets.",
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

    def start(self, camera_index: int, mic_index: int, resolution: str, custom_url: str = "") -> None:
        logger.info(
            "Recorder.start called with camera_index=%s, mic_index=%s, resolution=%s, custom_url=%s",
            camera_index, mic_index, resolution, custom_url
        )
        if self._recording:
            logger.error("Attempted to start Recorder while already recording.")
            raise RuntimeError("Recorder is already active")
        if self._output_dir is None:
            logger.error("Recorder output_dir is None.")
            raise ValueError("Recorder output_dir is not set")
        ensure_dir(self._output_dir)
        # Use AVI container universally — mp4v in OpenCV on Windows often produces
        # broken/unplayable files. XVID/MJPG in AVI works reliably on all platforms.
        self._video_path = self._output_dir / "raw_video.avi"
        self._audio_path = self._output_dir / "raw_audio.wav"
        self._camera_index = int(camera_index)
        self._custom_url = str(custom_url or "").strip()
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

        logger.debug("Starting live backends...")
        self._start_live_backends()
        logger.info("Recorder started with backend_mode=%s", self._backend_mode)

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
        """Start video and audio backends in parallel to minimize startup delay."""
        self._backend_mode = "initializing"

        def _init_live_capture() -> None:
            logger.debug("Inside _init_live_capture thread...")
            
            # Start backends in parallel threads
            results = {"video": False, "audio": False}
            
            def run_video():
                results["video"] = self._start_live_video_backend()
                
            def run_audio():
                results["audio"] = self._start_live_audio_backend()
                
            t_video = threading.Thread(target=run_video, daemon=True)
            t_audio = threading.Thread(target=run_audio, daemon=True)
            
            t_video.start()
            t_audio.start()
            
            # Wait for both to finish (with safety timeout)
            t_video.join(timeout=5.0)
            t_audio.join(timeout=5.0)
            
            video_started = results["video"]
            audio_started = results["audio"]
            
            with self._state_lock:
                if not self._recording:
                    logger.debug("Recording stopped while initializing backends, aborting.")
                    return
                if video_started and audio_started:
                    self._backend_mode = "live"
                elif video_started or audio_started:
                    self._backend_mode = "mixed"
                    self._backend_notes.append("Partial live capture active; missing streams use placeholders.")
                else:
                    self._backend_mode = "placeholder"
                    self._backend_notes.append("No live capture backend available; placeholder files will be written.")
            logger.info("Recorder init finished with mode=%s", self._backend_mode)

        init_thread = threading.Thread(
            target=_init_live_capture,
            name="screenreview-recorder-init",
            daemon=True,
        )
        init_thread.start()

    def _start_live_video_backend(self) -> bool:
        """Open the camera, pre-warm it, then launch the capture loop thread."""
        source: int | str = self._custom_url if self._custom_url else self._camera_index
        logger.info("Starting live video backend for source=%s", source)
        if cv2 is None:
            logger.error("OpenCV not installed.")
            self._backend_notes.append("OpenCV not installed (video capture unavailable).")
            return False
        if self._video_path is None:
            return False
        try:
            width, height = _resolution_size(self._active_resolution)
            logger.debug("Opening _open_camera(%s)...", source)
            capture = _open_camera(source)
            if capture is None or not capture.isOpened():
                logger.error("Failed to open camera source %s", source)
                self._backend_notes.append(f"Camera source {source} could not be opened.")
                try:
                    if capture is not None:
                        capture.release()
                except Exception:
                    pass
                return False

            # Request resolution — DShow/MSMF may ignore and return nearest supported.
            logger.debug("Requesting camera size %sx%s @ 20fps", width, height)
            try:
                capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
                capture.set(cv2.CAP_PROP_FPS, 20)
            except Exception as e:
                logger.warning("Failed to set camera properties for recording: %s", e)

            # Pre-warm: discard the first few frames (cameras often return black/noise
            # frames on Windows until the sensor stabilises after opening).
            logger.debug("Pre-warming camera (discarding first frames)...")
            warmup_ok = False
            prewarm_deadline = time.monotonic() + 1.0  # max 1s warmup (reduced from 3s)
            prewarm_frames = 0
            while time.monotonic() < prewarm_deadline and not self._stop_event.is_set():
                ok, frame = capture.read()
                if ok and frame is not None:
                    prewarm_frames += 1
                    if prewarm_frames >= 2: # Reduced from 5 to speed up start
                        warmup_ok = True
                        logger.debug("Camera pre-warm complete after %s frames", prewarm_frames)
                        break
                else:
                    time.sleep(0.05)

            if not warmup_ok:
                logger.warning("Camera pre-warm timed out (got %s frames); proceeding anyway", prewarm_frames)

            if self._stop_event.is_set():
                logger.info("Recording stopped during camera warm-up; aborting video backend.")
                try:
                    capture.release()
                except Exception:
                    pass
                return False

            # Detect what resolution the camera actually delivered.
            actual_w = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_h = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
            logger.info("Camera opened: requested=%sx%s actual=%sx%s", width, height, actual_w, actual_h)

            self._capture = capture
            self._video_opened = True
            self._video_thread = threading.Thread(
                target=self._video_capture_loop,
                name="screenreview-video-capture",
                daemon=True,
            )
            self._video_thread.start()
            self._backend_notes.append(
                f"Live webcam capture started (camera={self._camera_index}, {actual_w}x{actual_h})."
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
        logger.info("Starting live audio backend for mic_index=%s", self._mic_index)
        if sd is None or np is None:
            logger.error("Missing sounddevice or numpy.")
            self._backend_notes.append("sounddevice/numpy not installed (audio capture unavailable).")
            return False
        if self._audio_path is None:
            return False
        try:
            self._audio_sample_rate = 16000
            self._audio_channels = 1
            logger.debug("Opening wave file %s", self._audio_path)
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

            logger.debug("Opening sd.InputStream for mic_index=%s", self._mic_index)
            self._audio_stream = sd.InputStream(
                samplerate=self._audio_sample_rate,
                channels=self._audio_channels,
                dtype="float32",
                device=self._mic_index,
                callback=_callback,
            )
            logger.debug("Starting audio stream...")
            self._audio_stream.start()
            logger.info("Live audio capture started completely.")
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

    _TARGET_FPS = 20.0
    _FRAME_INTERVAL = 1.0 / _TARGET_FPS

    def _video_capture_loop(self) -> None:
        """Capture frames from the webcam and write them to the video file.

        Uses wall-clock throttling to stay close to _TARGET_FPS rather than
        relying on camera-side timing, which is unreliable on Windows DShow.
        """
        capture = self._capture
        if capture is None:
            return

        next_write_at = time.monotonic()
        consecutive_failures = 0
        MAX_FAILURES = 60  # give up after ~2s of no frames

        while not self._stop_event.is_set():
            now = time.monotonic()
            # Throttle: don't read faster than the target FPS
            if now < next_write_at:
                time.sleep(min(next_write_at - now, self._FRAME_INTERVAL))
                continue

            try:
                ok, frame = capture.read()
            except Exception as exc:  # pragma: no cover - hardware/runtime path
                logger.exception("Video capture read failed")
                self._backend_notes.append(f"Video read error: {exc}")
                break

            if not ok or frame is None:
                consecutive_failures += 1
                if consecutive_failures >= MAX_FAILURES:
                    logger.error("Camera stopped delivering frames after %s attempts; giving up.", consecutive_failures)
                    self._backend_notes.append("Camera stopped delivering frames; video stream ended.")
                    break
                time.sleep(0.03)
                continue

            consecutive_failures = 0
            next_write_at = time.monotonic() + self._FRAME_INTERVAL

            with self._state_lock:
                self._last_preview_frame = frame.copy() if hasattr(frame, "copy") else frame

            if self._paused:
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

        logger.info("Video capture loop exited. Frames written: %s", self._video_frames_written)

    def _ensure_video_writer(self, frame: Any) -> None:
        """Create the VideoWriter on the first valid frame.

        Codec priority (Windows-safe order):
          1. XVID  — reliable AVI on all platforms, widely playable
          2. MJPG  — Motion JPEG, always works in OpenCV
          3. mp4v  — fallback for Linux/Mac .avi
        We write .avi throughout to avoid the mp4/H.264 codec issues on
        Windows OpenCV builds that don't include the H.264 encoder.
        """
        if self._writer is not None or self._video_path is None or cv2 is None:
            return
        if not hasattr(frame, "shape"):
            return
        try:
            height = int(frame.shape[0])
            width = int(frame.shape[1])
        except Exception:
            return
        fps = self._TARGET_FPS
        # Always use .avi extension — the path was set to .avi in start()
        candidates = ["XVID", "MJPG", "mp4v"]
        for codec_name in candidates:
            writer = None
            try:
                fourcc = cv2.VideoWriter_fourcc(*codec_name)
                writer = cv2.VideoWriter(
                    str(self._video_path),
                    fourcc,
                    fps,
                    (width, height),
                )
            except Exception as exc:
                logger.warning("VideoWriter codec %s raised: %s", codec_name, exc)
                writer = None
            if writer is not None and writer.isOpened():
                self._writer = writer
                logger.info("VideoWriter opened with codec=%s size=%sx%s fps=%s path=%s",
                            codec_name, width, height, fps, self._video_path)
                self._backend_notes.append(
                    f"Video writer: codec={codec_name} {width}x{height}@{fps:.0f}fps -> {self._video_path.name}"
                )
                return
            try:
                if writer is not None:
                    writer.release()
            except Exception:
                pass
        logger.error("No working video codec found (tried %s)", candidates)
        self._backend_notes.append("No working video codec found for OpenCV writer; placeholder will be used.")

    def _stop_live_backends(self) -> None:
        """Stop all capture threads and flush output files."""
        # Signal threads to stop
        # Join the video capture thread with enough time for warmup + final flush.
        video_thread = self._video_thread
        self._video_thread = None
        if video_thread is not None and video_thread.is_alive():
            logger.debug("Waiting for video capture thread to exit...")
            video_thread.join(timeout=5.0)
            if video_thread.is_alive():
                logger.warning("Video capture thread did not exit in time; forcing ahead.")

        # Release the writer BEFORE releasing the capture to flush pending frames.
        if self._writer is not None:
            logger.debug("Releasing VideoWriter (%s frames written)...", self._video_frames_written)
            try:
                self._writer.release()
            except Exception as exc:
                logger.error("Error releasing video writer: %s", exc)
            self._writer = None
            # Log resulting file size so the bug is easy to spot in logs.
            if self._video_path is not None and self._video_path.exists():
                size_kb = self._video_path.stat().st_size / 1024
                logger.info("Video file written: %s size=%.1f KB (%s frames)",
                            self._video_path.name, size_kb, self._video_frames_written)

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
        # Write a minimal valid AVI RIFF header stub so files aren't totally empty.
        # Downstream code should treat any video under ~1KB as a placeholder.
        path.write_bytes(b"SCREENREVIEW_PLACEHOLDER_AVI")

    def _write_placeholder_audio(self, path: Path) -> None:
        with wave.open(str(path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(16000)
            wav_file.writeframes(b"\x00\x00" * 1600)
