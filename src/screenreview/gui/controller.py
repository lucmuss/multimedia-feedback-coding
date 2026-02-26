# -*- coding: utf-8 -*-
"""Application controller for phase 3 MVC refactoring."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from screenreview.core.folder_scanner import scan_project, resolve_routes_root
from screenreview.core.navigator import Navigator
from screenreview.models.screen_item import ScreenItem
from screenreview.pipeline.recorder import Recorder
from screenreview.pipeline.transcriber import Transcriber
from screenreview.pipeline.exporter import Exporter
from screenreview.pipeline.differ import Differ
from screenreview.utils.cost_calculator import CostCalculator
from screenreview.gui.workers import TranscriptionWorker, PipelineWorker

logger = logging.getLogger(__name__)


class AppController(QObject):
    """
    Central controller for application logic.
    Manages navigation, recording, and background processing.
    """
    project_loaded = pyqtSignal(list)
    screen_changed = pyqtSignal(ScreenItem, int, int)
    recording_status_changed = pyqtSignal(bool, bool, float)
    pipeline_progress = pyqtSignal(int, int, str)
    pipeline_finished = pyqtSignal(ScreenItem)
    error_occurred = pyqtSignal(str)
    cost_updated = pyqtSignal(float, float, float)

    def __init__(self, settings: dict[str, Any]) -> None:
        super().__init__()
        self.settings = settings
        self.project_dir: Path | None = None
        self.screens: list[ScreenItem] = []
        self.navigator: Navigator | None = None
        self.recorder = Recorder()
        self.cost_tracker = CostCalculator()
        self.differ = Differ()
        
        # Core Services
        from screenreview.integrations.openai_client import OpenAIClient
        openai_key = str(self.settings.get("api_keys", {}).get("openai", ""))
        self.transcriber = Transcriber(openai_client=OpenAIClient(api_key=openai_key))
        self.exporter = Exporter(transcriber=self.transcriber)
        
        # Thread Management
        self._active_threads: list[QThread] = []

    def _cleanup_threads(self) -> None:
        """Remove finished threads from the active list."""
        self._active_threads = [t for t in self._active_threads if t.isRunning()]

    def load_project(self, project_dir: Path) -> None:
        """Scan project directory and initialize navigation."""
        old_idx = self.navigator.current_index() if self.navigator else 0
        self.project_dir = project_dir
        viewport_mode = self.settings.get("viewport", {}).get("mode", "mobile")
        self.screens = scan_project(project_dir, viewport_mode=viewport_mode)
        self.navigator = Navigator(self.screens)
        if 0 <= old_idx < len(self.screens):
            self.navigator.go_to(old_idx)
        logger.info("Project loaded from %s. Total screens: %d", project_dir, len(self.screens))
        self.project_loaded.emit(self.screens)
        self.refresh_current_screen()

    def refresh_current_screen(self) -> None:
        if self.navigator:
            idx = self.navigator.current_index()
            screen = self.navigator.current()
            self.screen_changed.emit(screen, idx, len(self.screens))
            self._update_costs(screen)

    def go_next(self, save_drawing_callback=None) -> None:
        if not self.navigator: return
        
        was_recording = self.recorder.is_recording()
        if was_recording:
            self.stop_recording()
            
        current_screen = self.navigator.current()
        if save_drawing_callback:
            save_drawing_callback(current_screen)
            
        prev_idx = self.navigator.current_index()
        self.navigator.next()
        
        if self.navigator.current_index() != prev_idx:
            self.refresh_current_screen()
            if was_recording:
                self.start_recording()
        else:
            self.refresh_current_screen()

    def go_previous(self, save_drawing_callback=None) -> None:
        if not self.navigator: return
        if self.recorder.is_recording(): self.stop_recording()
        
        current_screen = self.navigator.current()
        if save_drawing_callback:
            save_drawing_callback(current_screen)
            
        self.navigator.previous()
        self.refresh_current_screen()

    def go_to_index(self, index: int, save_drawing_callback=None) -> None:
        if not self.navigator: return
        current_screen = self.navigator.current()
        if save_drawing_callback:
            save_drawing_callback(current_screen)
        
        self.navigator.go_to(index)
        self.refresh_current_screen()

    def start_recording(self) -> None:
        if not self.navigator: return
        screen = self.navigator.current()
        
        webcam = self.settings.get("webcam", {})
        self.recorder.set_output_dir(screen.extraction_dir)
        self.recorder.start(
            camera_index=int(webcam.get("camera_index", 0)),
            mic_index=int(webcam.get("microphone_index", 0)),
            resolution=str(webcam.get("resolution", "1080p")),
            custom_url=str(webcam.get("custom_url", "")),
        )
        screen.status = "recording"
        logger.info("Recording started for screen: %s (Cam: %s, Mic: %s, Res: %s)", 
                    screen.name, webcam.get("camera_index"), webcam.get("microphone_index"), 
                    webcam.get("resolution"))
        self.recording_status_changed.emit(True, False, 0.0)

    def stop_recording(self) -> None:
        if not self.recorder.is_recording(): return
        screen = self.navigator.current()
        video_path, audio_path = self.recorder.stop()
        duration = self.recorder.get_duration()
        screen.status = "processing"
        
        self.recording_status_changed.emit(False, False, duration)
        self._start_transcription(screen, video_path, audio_path, duration)

    def toggle_pause(self) -> None:
        if not self.recorder.is_recording(): return
        if self.recorder.is_paused():
            self.recorder.resume()
        else:
            self.recorder.pause()
        self.recording_status_changed.emit(True, self.recorder.is_paused(), self.recorder.get_duration())

    def _start_transcription(self, screen: ScreenItem, video_path: Path, audio_path: Path, duration: float) -> None:
        self._cleanup_threads()
        provider = str(self.settings.get("speech_to_text", {}).get("provider", "openai_4o_transcribe"))
        language = str(self.settings.get("speech_to_text", {}).get("language", "de"))
        
        self.pipeline_progress.emit(0, 9, "Transcribing audio...")
        
        # Use child of self to ensure it's not garbage collected too early
        thread = QThread(self)
        worker = TranscriptionWorker(self.transcriber, audio_path, provider, language)
        worker.moveToThread(thread)
        
        thread.started.connect(worker.run)
        worker.finished.connect(lambda segments: self._on_transcription_finished(screen, video_path, audio_path, duration, segments))
        worker.error.connect(lambda err: self._on_transcription_finished(screen, video_path, audio_path, duration, [{"start": 0.0, "end": duration, "text": f"(API Error: {err})"}]))
        
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        
        # Clean up the thread only when it's really done
        thread.finished.connect(thread.deleteLater)
        
        self._active_threads.append(thread)
        thread.start()

    def _on_transcription_finished(self, screen: ScreenItem, video_path: Path, audio_path: Path, duration: float, segments: list[dict[str, Any]]) -> None:
        self._cleanup_threads()
        # Update cost
        provider = str(self.settings.get("speech_to_text", {}).get("provider", "gpt-4o-mini-transcribe"))
        self.cost_tracker.add(provider, max(0.01, duration / 60.0), screen.name)
        self.cost_tracker.add("llama_32_vision", 6, screen.name)
        logger.debug("Transcription segments received for %s: %d items", screen.name, len(segments))
        self._update_costs(screen)

        # Start Pipeline
        thread = QThread(self)
        worker = PipelineWorker(screen, video_path, audio_path, segments, self.settings, self.transcriber, self.exporter)
        worker.moveToThread(thread)
        
        thread.started.connect(worker.run)
        worker.progress.connect(self.pipeline_progress.emit)
        worker.finished.connect(self._on_pipeline_finished)
        worker.error.connect(self.error_occurred.emit)
        
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        
        self._active_threads.append(thread)
        thread.start()

    def _on_pipeline_finished(self, screen: ScreenItem) -> None:
        screen.status = "pending"
        self.pipeline_finished.emit(screen)
        self.refresh_current_screen()

    def _update_costs(self, screen: ScreenItem) -> None:
        self.cost_updated.emit(
            self.cost_tracker.get_screen_cost(screen.name),
            self.cost_tracker.get_total(),
            float(self.settings.get("cost", {}).get("budget_limit_euro", 0.0))
        )

    def combine_transcripts(self) -> tuple[int, Path] | None:
        if not self.project_dir: return None
        
        viewport_mode = str(self.settings.get("viewport", {}).get("mode", "mobile"))
        routes_root = resolve_routes_root(self.project_dir)
        output_name = f"{viewport_mode.lower()}_final.md"
        output_path = self.project_dir / output_name
        
        combined_lines = [
            f"# ScreenReview Final Combined Transcript ({viewport_mode.capitalize()})",
            f"- **Project Root:** `{self.project_dir}`",
            f"- **Viewport:** {viewport_mode}",
            f"- **Generated:** {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "", "---", ""
        ]
        
        slug_dirs = sorted([p for p in routes_root.iterdir() if p.is_dir()], key=lambda p: p.name.lower())
        count = 0
        for slug_dir in slug_dirs:
            t_file = slug_dir / viewport_mode / "transcript.md"
            if t_file.exists():
                count += 1
                content = t_file.read_text(encoding="utf-8")
                combined_lines.extend([f"## 🌐 Screen: {slug_dir.name}", "", content, "", "---", ""])
        
        if count > 0:
            output_path.write_text("\n".join(combined_lines), encoding="utf-8")
            return count, output_path
        return None
