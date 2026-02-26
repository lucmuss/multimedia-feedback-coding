# -*- coding: utf-8 -*-
"""Main window for phase 3 MVC refactoring (View only)."""

from __future__ import annotations

import logging
import json
import time
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QTimer, Qt, QUrl
from PyQt6.QtGui import QAction, QDesktopServices, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
    QMenu,
    QToolButton,
)

from screenreview.constants import APP_NAME, APP_VERSION
from screenreview.config import save_config
from screenreview.gui.batch_overview_widget import BatchOverviewWidget
from screenreview.gui.comparison_widget import ComparisonWidget
from screenreview.gui.controls_widget import ControlsWidget
from screenreview.gui.cost_widget import CostWidget
from screenreview.gui.help_system import HelpSystem
from screenreview.gui.metadata_widget import MetadataWidget
from screenreview.gui.preflight_dialog import PreflightDialog
from screenreview.gui.progress_widget import ProgressWidget
from screenreview.gui.settings_dialog import SettingsDialog
from screenreview.gui.smart_hint_widget import SmartHintWidget
from screenreview.gui.transcript_live_widget import TranscriptLiveWidget
from screenreview.gui.viewer_widget import ViewerWidget
from screenreview.gui.controller import AppController
from screenreview.models.screen_item import ScreenItem

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """
    Phase 3 View: Manages UI components and visual updates.
    Delegates all logic to AppController.
    """

    def __init__(self, settings: dict[str, Any], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings = settings
        
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.resize(1320, 860)

        # 1. Initialize logic (MVC Controller)
        self.controller = AppController(settings)

        # 2. Build UI (creates widgets needed for connections)
        self._build_actions()
        self._build_ui()
        
        # 3. Setup connections (now widgets exist)
        self._setup_connections()

        self._apply_tooltips()
        self._apply_styles()
        self._bind_hotkeys()
        
        # Animation/Feedback Timer
        self._recording_ui_phase = 0
        self._recording_ui_timer = QTimer(self)
        self._recording_ui_timer.setInterval(500)
        self._recording_ui_timer.timeout.connect(self._on_recording_timer_tick)

        # NOTE: showMaximized() removed from constructor to prevent Wayland protocol errors.
        # Window mapping should happen in the main entry point (main.py).

    def load_project(self, project_dir: Path, show_file_report: bool = True) -> None:
        """Expose project loading to external callers."""
        self.controller.load_project(project_dir)
        self._add_to_recent_project(project_dir)

    def changeEvent(self, event: Any) -> None:
        """Handle window state changes for Wayland button sync."""
        if event is not None and event.type() == event.Type.WindowStateChange:
            is_fs = bool(self.windowState() & Qt.WindowState.WindowFullScreen)
            self.fullscreen_button.setText("Exit Fullscreen" if is_fs else "Fullscreen")
        super().changeEvent(event)

    def _setup_connections(self) -> None:
        self.controller.project_loaded.connect(self._on_project_loaded)
        self.controller.screen_changed.connect(self._on_screen_changed)
        self.controller.recording_status_changed.connect(self._on_recording_status_changed)
        self.controller.pipeline_progress.connect(self._on_pipeline_progress)
        self.controller.pipeline_finished.connect(self._on_pipeline_finished)
        self.controller.error_occurred.connect(self._on_error)
        self.controller.cost_updated.connect(self.cost_widget.set_costs)

    def _build_actions(self) -> None:
        self.open_project_action = QAction("Open Project", self)
        self.open_project_action.triggered.connect(self._choose_project_dir)
        self.settings_action = QAction("Settings", self)
        self.settings_action.triggered.connect(self._open_settings_dialog)
        self.preflight_action = QAction("Preflight Check", self)
        self.preflight_action.triggered.connect(self._open_preflight_dialog)
        self.combine_transcripts_action = QAction("Combine Transcripts", self)
        self.combine_transcripts_action.triggered.connect(self._combine_transcripts)

    def _build_ui(self) -> None:
        self.recent_projects_btn = QToolButton()
        self.recent_projects_btn.setText("Recent Projects")
        self.recent_projects_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.recent_projects_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.recent_menu = QMenu(self)
        self.recent_projects_btn.setMenu(self.recent_menu)
        self._update_recent_menu()

        toolbar = self.addToolBar("Main")
        toolbar.setMovable(False)
        toolbar.addWidget(self.recent_projects_btn)
        toolbar.addAction(self.open_project_action)
        toolbar.addAction(self.combine_transcripts_action)
        toolbar.addAction(self.preflight_action)
        toolbar.addAction(self.settings_action)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        self.project_label = QLabel("No project loaded")
        self.project_label.setObjectName("mutedText")
        
        self.route_label = QLabel("-")
        self.route_label.setObjectName("routeTitle")
        self.route_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.path_label = QLabel("Path:")
        self.path_label.setObjectName("sectionTitle")
        self.path_label.setFixedWidth(50)

        header_layout.addWidget(self.path_label)
        header_layout.addWidget(self.project_label, 1)
        header_layout.addWidget(self.route_label, 2, Qt.AlignmentFlag.AlignCenter)
        
        self.fullscreen_button = QPushButton("Fullscreen")
        self.fullscreen_button.setObjectName("secondaryButton")
        self.fullscreen_button.clicked.connect(self.toggle_fullscreen_mode)
        header_layout.addWidget(self.fullscreen_button)

        self.viewer_widget = ViewerWidget()
        self.viewer_widget.viewport_changed.connect(self._on_viewport_mode_changed)
        
        self.metadata_widget = MetadataWidget()
        self.smart_hint_widget = SmartHintWidget()
        self.comparison_widget = ComparisonWidget()
        self.cost_widget = CostWidget()
        
        self.batch_overview_widget = BatchOverviewWidget()
        self.batch_overview_widget.screen_selected.connect(self._go_to_index)
        
        self.transcript_live_widget = TranscriptLiveWidget()
        self.progress_widget = ProgressWidget()

        self.status_label = QLabel("Screen 0 of 0")
        self.status_label.setObjectName("statusBadge")

        left_panel = QVBoxLayout()
        left_panel.setSpacing(10)
        left_panel.addWidget(self.viewer_widget, 1)
        left_panel.addWidget(self.transcript_live_widget, 0)

        right_panel = QVBoxLayout()
        right_panel.setSpacing(12)
        right_panel.addWidget(self.metadata_widget, 0)
        
        cost_row = QHBoxLayout()
        cost_row.setSpacing(8)
        cost_row.addWidget(self.cost_widget, 1)
        cost_row.addWidget(self.progress_widget, 1)
        right_panel.addLayout(cost_row)
        
        hint_row = QHBoxLayout()
        hint_row.setSpacing(8)
        hint_row.addWidget(self.comparison_widget, 1)
        hint_row.addWidget(self.smart_hint_widget, 1)
        right_panel.addLayout(hint_row)
        
        right_panel.addWidget(self.status_label)
        right_panel.addWidget(self.batch_overview_widget, 1)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        left_cont = QWidget(); left_cont.setLayout(left_panel)
        right_cont = QWidget(); right_cont.setLayout(right_panel)
        splitter.addWidget(left_cont)
        splitter.addWidget(right_cont)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        self.controls_widget = ControlsWidget(hotkeys=self.settings.get("hotkeys", {}))
        self.controls_widget.back_requested.connect(self._go_previous)
        self.controls_widget.next_requested.connect(self._go_next)
        self.controls_widget.skip_requested.connect(self._go_next)
        self.controls_widget.record_requested.connect(self._toggle_record)
        self.controls_widget.pause_requested.connect(self.controller.toggle_pause)
        self.controls_widget.stop_requested.connect(self.controller.stop_recording)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)
        layout.addWidget(header)
        layout.addWidget(splitter, 1)
        layout.addWidget(self.controls_widget)

        self.setCentralWidget(central)
        self.setStatusBar(QStatusBar())

        # Performance & AI-Testability: Periodic GUI State Snapshot
        # This allows AI agents to "see" the app state by reading a JSON file.
        self._state_dump_timer = QTimer(self)
        self._state_dump_timer.timeout.connect(self._dump_gui_state)
        self._state_dump_timer.start(5000) # Every 5 seconds

    def _dump_gui_state(self) -> None:
        """Dumps the current GUI state to a JSON file for AI agents to analyze."""
        try:
            state = {
                "window": {
                    "title": self.windowTitle(),
                    "project": str(self.controller.project_dir) if self.controller.project_dir else None,
                    "screen_index": self.controller.navigator.current_index() if self.controller.navigator else 0,
                    "total_screens": len(self.controller.screens),
                },
                "status": self.status_label.text(),
                "recording": {
                    "active": self.controller.recorder.is_recording(),
                    "paused": self.controller.recorder.is_paused(),
                },
                "timestamp": time.time()
            }
            dump_path = Path.cwd() / "logs" / "gui_state_snapshot.json"
            dump_path.parent.mkdir(parents=True, exist_ok=True)
            dump_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
        except Exception:
            pass

    # --- Controller Delegation ---

    def _choose_project_dir(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "Select Project Directory")
        if selected:
            self.load_project(Path(selected))

    def _add_to_recent_project(self, path: Path) -> None:
        p_str = str(path.absolute())
        recents = self.settings.get("recent_projects", [])
        if p_str in recents:
            recents.remove(p_str)
        recents.insert(0, p_str)
        self.settings["recent_projects"] = recents[:10]
        save_config(self.settings)
        self._update_recent_menu()
        
    def _update_recent_menu(self) -> None:
        self.recent_menu.clear()
        recents = self.settings.get("recent_projects", [])
        if not recents:
            self.recent_menu.addAction("No recent projects").setEnabled(False)
            return
            
        for path_str in recents:
            action = QAction(path_str, self)
            action.triggered.connect(lambda checked, p=path_str: self.load_project(Path(p)))
            self.recent_menu.addAction(action)

    def _go_next(self) -> None:
        self.controller.go_next(save_drawing_callback=self._save_drawing)

    def _go_previous(self) -> None:
        self.controller.go_previous(save_drawing_callback=self._save_drawing)

    def _go_to_index(self, index: int) -> None:
        self.controller.go_to_index(index, save_drawing_callback=self._save_drawing)

    def _toggle_record(self) -> None:
        if self.controller.recorder.is_recording():
            self.controller.stop_recording()
        else:
            self.controller.start_recording()

    def _save_drawing(self, screen: ScreenItem) -> None:
        if not screen.extraction_dir.exists():
            from screenreview.utils.extraction_init import ExtractionInitializer
            ExtractionInitializer.ensure_structure(screen.extraction_dir)
        path = screen.extraction_dir / "annotation_overlay.png"
        self.viewer_widget.save_drawing(path)

    # --- Signal Handlers (View Updates) ---

    def _on_project_loaded(self, screens: list[ScreenItem]) -> None:
        self.project_label.setText(str(self.controller.project_dir))
        self.batch_overview_widget.set_screens(screens)
        self.statusBar().showMessage(f"Loaded {len(screens)} screens.")

    def _on_screen_changed(self, screen: ScreenItem, index: int, total: int) -> None:
        self.viewer_widget.set_image(screen.screenshot_path)
        overlay = screen.extraction_dir / "annotation_overlay.png"
        if overlay.exists(): self.viewer_widget.load_drawing(overlay)
        else: self.viewer_widget.clear_drawing()
            
        self.metadata_widget.set_screen(screen)
        self.route_label.setText(f"Route: {screen.route or '-'}")
        self.status_label.setText(f"Screen {index+1} of {total} | {screen.status.upper()}")
        self.controls_widget.set_navigation_state(index > 0, index < total - 1)
        self.batch_overview_widget.set_screens(self.controller.screens, current_index=index)
        self._refresh_hints(screen, index)

    def _on_recording_status_changed(self, is_rec: bool, is_paused: bool, duration: float) -> None:
        if is_rec and not self._recording_ui_timer.isActive():
            self._recording_ui_timer.start()
            self.transcript_live_widget.clear_transcript()
        elif not is_rec:
            self._recording_ui_timer.stop()
        self.controls_widget.set_recording_state(is_rec, is_paused, duration, self._recording_ui_phase)

    def _on_recording_timer_tick(self) -> None:
        self._recording_ui_phase = (self._recording_ui_phase + 1) % 4
        dur = self.controller.recorder.get_duration()
        self.controls_widget.set_recording_state(True, self.controller.recorder.is_paused(), dur, self._recording_ui_phase)

    def _on_pipeline_progress(self, step: int, total: int, msg: str) -> None:
        self.progress_widget.set_progress(step, total, msg)

    def _on_pipeline_finished(self, screen: ScreenItem) -> None:
        self.progress_widget.set_progress(9, 9, "Analysis complete.")
        self.controller.refresh_current_screen()

    def _on_error(self, msg: str) -> None:
        QMessageBox.warning(self, "Error", msg)

    def _on_viewport_mode_changed(self, mode: str) -> None:
        self.settings["viewport"]["mode"] = mode
        save_config(self.settings)
        if self.controller.project_dir: self.controller.load_project(self.controller.project_dir)

    def _combine_transcripts(self) -> None:
        res = self.controller.combine_transcripts()
        if res:
            count, path = res
            QMessageBox.information(self, "Success", f"Combined {count} transcripts into {path}")
        else: QMessageBox.warning(self, "Missing Data", "No transcripts found to combine.")

    def _refresh_hints(self, screen: ScreenItem, index: int) -> None:
        if index > 0:
            prev = self.controller.screens[index-1]
            try:
                _, ratio = self.controller.differ.compute_diff(prev.screenshot_path, screen.screenshot_path)
                self.comparison_widget.set_comparison(prev.name, screen.name, ratio)
            except: pass
        else: self.comparison_widget.set_comparison(None, screen.name, None)

    def toggle_fullscreen_mode(self) -> None:
        """
        Robust window state toggle.
        Uses setWindowState to avoid Wayland buffer mismatch errors during resize.
        """
        if self.isFullScreen():
            self.setWindowState(Qt.WindowState.WindowMaximized)
        else:
            self.setWindowState(Qt.WindowState.WindowFullScreen)

    def _apply_styles(self) -> None:
        self.setStyleSheet("""
            QMainWindow, QWidget { background: #f3f5f8; color: #1f2937; font-family: 'Segoe UI', sans-serif; font-size: 13px; }
            QLabel#sectionTitle { font-size: 14px; font-weight: 700; color: #111827; }
            QLabel#mutedText { font-weight: normal; color: #6b7280; font-size: 12px; }
            QLabel#routeTitle { font-size: 16px; font-weight: 800; color: #0f766e; background: #f0fdfa; border: 1px solid #99f6e4; border-radius: 8px; padding: 6px 16px; margin: 4px; }
            QLabel#statusBadge { background: #e0ecff; color: #1d4ed8; border: 1px solid #bfdbfe; border-radius: 10px; padding: 8px 12px; font-weight: 600; }
            
            QPushButton { border-radius: 10px; padding: 10px 18px; font-weight: 600; border: 1px solid transparent; transition: all 0.2s; }
            QPushButton#secondaryButton { background: white; border-color: #d1d5db; color: #374151; }
            QPushButton#secondaryButton:hover { background: #f9fafb; border-color: #9ca3af; }
            
            QPushButton#greenButton { background: #10b981; color: white; }
            QPushButton#greenButton:hover { background: #059669; }
            QPushButton#greenButton:disabled { background: #a7f3d0; color: #ecfdf5; }
            
            QPushButton#blueButton { background: #3b82f6; color: white; }
            QPushButton#blueButton:hover { background: #2563eb; }
            
            QPushButton#yellowButton { background: #f59e0b; color: white; }
            QPushButton#yellowButton:hover { background: #d97706; }
            
            QPushButton#dangerButton { background: #ef4444; color: white; }
            QPushButton#dangerButton:hover { background: #dc2626; }
            
            QPushButton#lightBlueButton { background: #e0f2fe; color: #0369a1; border: 1px solid #bae6fd; }
            QPushButton#lightBlueButton:hover { background: #bae6fd; }
            
            QPushButton#lightRedButton { background: #fee2e2; color: #b91c1c; border: 1px solid #fecaca; }
            QPushButton#lightRedButton:hover { background: #fecaca; }
            
            QStatusBar { background: white; border-top: 1px solid #e5e7eb; color: #6b7280; }
        """)

    def _bind_hotkeys(self) -> None:
        hotkeys = self.settings.get("hotkeys", {})
        b = [(hotkeys.get("next"), self._go_next), (hotkeys.get("back"), self._go_previous)]
        for seq, handler in b:
            if seq: QShortcut(QKeySequence(seq), self).activated.connect(handler)

    def _apply_tooltips(self) -> None:
        self.metadata_widget.setToolTip("Technical metadata and annotations")
        self.status_label.setToolTip("Shows current screen index and status")
        self.route_label.setToolTip("Current route information")
        self.viewer_widget.setToolTip("Main screen preview area")
    def _open_settings_dialog(self) -> None:
        d = SettingsDialog(self.settings, self, project_dir=self.controller.project_dir)
        if d.exec():
            self.settings = d.get_settings(); save_config(self.settings); self.controller.settings = self.settings
            if self.controller.project_dir: self.controller.load_project(self.controller.project_dir)

    def _open_preflight_dialog(self) -> None:
        if self.controller.project_dir:
            PreflightDialog(self.controller.project_dir, self.settings, self).exec()
        else:
            QMessageBox.information(self, "Preflight Check", "Please open a project first to run a preflight check.")
