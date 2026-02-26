# -*- coding: utf-8 -*-
"""Main window for phase 3."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QObject, QThread, QTimer, Qt, QUrl, pyqtSignal
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
)

from screenreview.config import save_config
from screenreview.constants import APP_NAME, APP_VERSION
from screenreview.core.folder_scanner import scan_project
from screenreview.core.navigator import Navigator
from screenreview.core.precheck import analyze_missing_screen_files, format_missing_file_report
from screenreview.core.queue_manager import QueueManager
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
from screenreview.models.extraction_result import ExtractionResult
from screenreview.models.screen_item import ScreenItem
from screenreview.pipeline.differ import Differ
from screenreview.pipeline.exporter import Exporter
from screenreview.pipeline.recorder import Recorder
from screenreview.pipeline.transcriber import Transcriber
from screenreview.utils.cost_calculator import CostCalculator

logger = logging.getLogger(__name__)

class _TranscriptionWorker(QObject):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, transcriber: Transcriber, audio_path: Path, provider: str, language: str) -> None:
        super().__init__()
        self.transcriber = transcriber
        self.audio_path = audio_path
        self.provider = provider
        self.language = language

    def run(self) -> None:
        try:
            logger.info("Sending STT request: %s %s %s", self.provider, self.language, self.audio_path)
            result = self.transcriber.transcribe(self.audio_path, provider=self.provider, language=self.language)
            segments = result.get("segments", [])
            if not segments:
                segments = [{"start": 0.0, "end": 1.0, "text": "(No API speech results)"}]
            self.finished.emit(segments)
        except Exception as e:
            logger.exception("STT API failed")
            self.error.emit(str(e))
logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Phase 3 GUI: scan folders, record feedback, and show analysis hints."""

    def __init__(self, settings: dict[str, Any], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.project_dir: Path | None = None
        self.screens: list[ScreenItem] = []
        self.navigator: Navigator | None = None
        self.recorder = Recorder()
        
        openai_key = str(self.settings.get("api_keys", {}).get("openai", ""))
        from screenreview.integrations.openai_client import OpenAIClient
        self.transcriber = Transcriber(openai_client=OpenAIClient(api_key=openai_key))
        self.exporter = Exporter(transcriber=self.transcriber)
        self.differ = Differ()
        self.queue_manager = QueueManager(max_workers=2)
        self.cost_tracker = CostCalculator()
        self._live_segments: list[dict[str, Any]] = []
        self._last_file_report: dict[str, Any] | None = None
        self._recording_ui_phase = 0
        self._recording_ui_timer = QTimer(self)
        self._recording_ui_timer.setInterval(500)
        self._recording_ui_timer.timeout.connect(self._update_recording_feedback)

        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.resize(1320, 860)

        self._build_actions()
        self._build_ui()
        self._apply_tooltips()
        self._apply_styles()
        self._bind_hotkeys()
        self._refresh_ui()

    def _build_actions(self) -> None:
        self.open_project_action = QAction("Open Project", self)
        self.open_project_action.triggered.connect(self.choose_project_dir)
        self.settings_action = QAction("Settings", self)
        self.settings_action.triggered.connect(self.open_settings_dialog)
        self.preflight_action = QAction("Preflight Check", self)
        self.preflight_action.triggered.connect(self.open_preflight_dialog)

    def _build_ui(self) -> None:
        toolbar = self.addToolBar("Main")
        toolbar.setMovable(False)
        toolbar.addAction(self.open_project_action)
        toolbar.addAction(self.preflight_action)
        toolbar.addAction(self.settings_action)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(12)
        self.title_label = QLabel(APP_NAME)
        self.title_label.setObjectName("appTitle")
        self.project_label = QLabel("No project loaded")
        self.project_label.setObjectName("mutedText")
        self.batch_button = QPushButton("Batch Overview")
        self.batch_button.setObjectName("secondaryButton")
        self.batch_button.clicked.connect(self._focus_batch_panel)
        self.open_folder_button = QPushButton("Open Screen Folder")
        self.open_folder_button.setObjectName("secondaryButton")
        self.open_folder_button.clicked.connect(self.open_current_screen_folder)
        self.settings_button = QPushButton("Settings")
        self.settings_button.setObjectName("secondaryButton")
        self.settings_button.clicked.connect(self.open_settings_dialog)
        self.fullscreen_button = QPushButton("Exit Fullscreen")
        self.fullscreen_button.setObjectName("secondaryButton")
        self.fullscreen_button.clicked.connect(self.toggle_fullscreen_mode)
        self.preflight_button = QPushButton("Preflight Check")
        self.preflight_button.setObjectName("secondaryButton")
        self.preflight_button.clicked.connect(self.open_preflight_dialog)
        header_layout.addStretch(1)
        # project_label moved to path container in header_row

        self.viewer_widget = ViewerWidget()
        self.viewer_widget.viewport_changed.connect(self._on_viewport_changed)
        self.metadata_widget = MetadataWidget()
        self.smart_hint_widget = SmartHintWidget()
        self.comparison_widget = ComparisonWidget()
        self.cost_widget = CostWidget()
        self.setup_status_widget = QWidget()
        setup_layout = QVBoxLayout(self.setup_status_widget)
        setup_layout.setContentsMargins(10, 10, 10, 10)
        setup_layout.setSpacing(6)
        self.setup_status_widget.setObjectName("panelCard")
        setup_title = QLabel("Setup Status")
        setup_title.setObjectName("sectionTitle")
        # Setup Status in zwei Spalten
        setup_content = QWidget()
        setup_content_layout = QHBoxLayout(setup_content)
        setup_content_layout.setContentsMargins(0, 0, 0, 0)
        setup_content_layout.setSpacing(10)
        left_column = QVBoxLayout()
        left_column.setSpacing(4)
        left_column.addWidget(QLabel("Files"))
        left_column.addWidget(QLabel("Analysis"))
        left_column.addWidget(QLabel("Preflight"))
        right_column = QVBoxLayout()
        right_column.setSpacing(4)
        self.setup_files_label = QLabel("OK")
        self.setup_files_label.setObjectName("mutedText")
        self.setup_analysis_label = QLabel("OpenRouter")
        self.setup_analysis_label.setObjectName("mutedText")
        self.setup_preflight_label = QLabel("Check")
        self.setup_preflight_label.setObjectName("mutedText")
        right_column.addWidget(self.setup_files_label)
        right_column.addWidget(self.setup_analysis_label)
        right_column.addWidget(self.setup_preflight_label)
        setup_content_layout.addLayout(left_column)
        setup_content_layout.addLayout(right_column)
        setup_layout.addWidget(setup_title)
        setup_layout.addWidget(setup_content)
        self.batch_overview_widget = BatchOverviewWidget()
        self.batch_overview_widget.screen_selected.connect(self._go_to_screen)
        self.transcript_live_widget = TranscriptLiveWidget()
        self.progress_widget = ProgressWidget()

        self.status_label = QLabel("Screen 0 of 0")
        self.status_label.setObjectName("statusBadge")
        
        self.route_label = QLabel("-")
        self.route_label.setObjectName("routeTitle")
        self.route_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.path_label = QLabel("Path:")
        self.path_label.setObjectName("sectionTitle")
        self.path_label.setFixedWidth(50)

        # Header row for path and route info
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(10)
        
        path_container = QHBoxLayout()
        path_container.addWidget(self.path_label)
        path_container.addWidget(self.project_label)
        
        header_row.addLayout(path_container, 1)
        header_row.addWidget(self.route_label, 2, Qt.AlignmentFlag.AlignCenter)
        header_row.addStretch(1)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)
        left_layout.addLayout(header_row)
        left_layout.addWidget(self.viewer_widget, 1)
        left_layout.addWidget(self.transcript_live_widget, 0)

        # Comparison + Smart Selector side-by-side with separator
        comparison_row = QWidget()
        comparison_row_layout = QHBoxLayout(comparison_row)
        comparison_row_layout.setContentsMargins(0, 0, 0, 0)
        comparison_row_layout.setSpacing(8)
        comparison_row_layout.addWidget(self.comparison_widget, 1)
        
        comparison_line = QFrame()
        comparison_line.setFrameShape(QFrame.Shape.VLine)
        comparison_line.setFrameShadow(QFrame.Shadow.Sunken)
        comparison_line.setStyleSheet("color: #d1d9e6;")
        comparison_row_layout.addWidget(comparison_line)
        
        comparison_row_layout.addWidget(self.smart_hint_widget, 1)
        comparison_row_layout.setStretch(0, 1)
        comparison_row_layout.setStretch(2, 1)

        # Cost + Progress side-by-side with separator
        cost_progress_row = QWidget()
        cost_progress_layout = QHBoxLayout(cost_progress_row)
        cost_progress_layout.setContentsMargins(0, 0, 0, 0)
        cost_progress_layout.setSpacing(8)
        cost_progress_layout.addWidget(self.cost_widget, 1)
        
        cost_progress_line = QFrame()
        cost_progress_line.setFrameShape(QFrame.Shape.VLine)
        cost_progress_line.setFrameShadow(QFrame.Shadow.Sunken)
        cost_progress_line.setStyleSheet("color: #d1d9e6;")
        cost_progress_layout.addWidget(cost_progress_line)
        
        cost_progress_layout.addWidget(self.progress_widget, 1)
        cost_progress_layout.setStretch(0, 1)
        cost_progress_layout.setStretch(2, 1)

        right_panel = QWidget()
        right_panel.setMinimumWidth(260)
        right_panel.setMaximumWidth(400)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)
        right_layout.addWidget(self.metadata_widget, 0)
        right_layout.addWidget(cost_progress_row, 0)
        right_layout.addWidget(comparison_row, 0)
        right_layout.addWidget(self.status_label) # Moved status label here
        right_layout.addWidget(self.batch_overview_widget, 1)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter = splitter
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([1120, 260])

        self.controls_widget = ControlsWidget(hotkeys=self.settings.get("hotkeys", {}))
        self.controls_widget.back_requested.connect(self.go_previous)
        self.controls_widget.skip_requested.connect(self.go_skip)
        self.controls_widget.next_requested.connect(self.go_next)
        self.controls_widget.record_requested.connect(self.toggle_record)
        self.controls_widget.pause_requested.connect(self.toggle_pause)
        self.controls_widget.stop_requested.connect(self.stop_recording)

        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(14, 14, 14, 14)
        central_layout.setSpacing(12)
        central_layout.addWidget(header)
        central_layout.addWidget(splitter, 1)
        central_layout.addWidget(self.controls_widget)

        self.setCentralWidget(central)
        self.setStatusBar(QStatusBar())
        self._show_startup_status_message()

    def _apply_tooltips(self) -> None:
        self.viewer_widget.setToolTip(HelpSystem.get_tooltip("main_window", "viewer_widget"))
        self.metadata_widget.setToolTip(HelpSystem.get_tooltip("main_window", "metadata_widget"))
        self.batch_overview_widget.setToolTip(
            HelpSystem.get_tooltip("main_window", "batch_overview_widget")
        )
        self.transcript_live_widget.setToolTip(
            HelpSystem.get_tooltip("main_window", "transcript_live_widget")
        )
        self.progress_widget.setToolTip(HelpSystem.get_tooltip("main_window", "progress_widget"))
        self.setup_status_widget.setToolTip(HelpSystem.get_tooltip("main_window", "setup_status_widget"))
        self.batch_button.setToolTip(HelpSystem.get_tooltip("main_window", "batch_button"))
        self.preflight_button.setToolTip(HelpSystem.get_tooltip("main_window", "preflight_button"))
        self.settings_button.setToolTip(HelpSystem.get_tooltip("main_window", "settings_button"))
        self.fullscreen_button.setToolTip("Toggle fullscreen mode (F11). Press Esc to exit fullscreen.")
        self.open_folder_button.setToolTip(HelpSystem.get_tooltip("main_window", "open_folder_button"))
        self._refresh_status_tooltips(None)

    def _refresh_status_tooltips(self, screen: ScreenItem | None) -> None:
        status_tip = HelpSystem.get_tooltip("main_window", "status_label")
        route_tip = HelpSystem.get_tooltip("main_window", "route_label")
        if screen is None:
            self.status_label.setToolTip(status_tip)
            self.route_label.setToolTip(route_tip)
            return
        route_text = screen.route or "-"
        self.status_label.setToolTip(f"{status_tip}\nStatus: {screen.status}\nRoute: {route_text}")
        self.route_label.setToolTip(f"{route_tip}\nCurrent route: {route_text}")

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #f3f5f8;
                color: #1f2937;
                font-family: "Segoe UI", "Noto Sans", sans-serif;
                font-size: 12px;
            }
            QLabel#appTitle {
                font-size: 20px;
                font-weight: 700;
                color: #0f172a;
                letter-spacing: 0.3px;
            }
            QLabel#sectionTitle {
                font-size: 13px;
                font-weight: 700;
                color: #111827;
            }
            QLabel#routeTitle {
                font-size: 16px;
                font-weight: 800;
                color: #0f766e;
                background: #f0fdfa;
                border: 1px solid #99f6e4;
                border-radius: 6px;
                padding: 4px 12px;
            }
            QLabel#mutedText {
                color: #6b7280;
            }
            QLabel#statusBadge {
                background: #e0ecff;
                color: #1d4ed8;
                border: 1px solid #bfdbfe;
                border-radius: 8px;
                padding: 6px 10px;
                font-weight: 600;
            }
            QLabel#viewerSurface {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #ffffff, stop:1 #e9eef7);
                border: 1px solid #d1d9e6;
                border-radius: 12px;
                color: #64748b;
            }
            QPushButton#primaryButton {
                background: #0f766e;
                color: white;
                border: 1px solid #115e59;
                border-radius: 10px;
                padding: 8px 14px;
                font-weight: 700;
            }
            QPushButton#primaryButton:hover {
                background: #0d9488;
            }
            QPushButton#dangerButton {
                background: #dc2626;
                color: white;
                border: 1px solid #b91c1c;
                border-radius: 10px;
                padding: 8px 14px;
                font-weight: 700;
            }
            QPushButton#dangerButton:hover {
                background: #ef4444;
            }
            QPushButton#secondaryButton {
                background: white;
                border: 1px solid #d0d7e2;
                border-radius: 10px;
                padding: 8px 12px;
            }
            QWidget#panelCard {
                background: white;
                border: 1px solid #d0d7e2;
                border-radius: 10px;
            }
            QPushButton#secondaryButton:hover {
                border-color: #93c5fd;
                background: #f8fbff;
            }
            QPushButton#greenButton {
                background: #16a34a;
                color: white;
                border: 1px solid #15803d;
                border-radius: 10px;
                padding: 8px 14px;
                font-weight: 700;
            }
            QPushButton#greenButton:hover {
                background: #15803d;
            }
            QPushButton#yellowButton {
                background: #eab308;
                color: white;
                border: 1px solid #ca8a04;
                border-radius: 10px;
                padding: 8px 14px;
                font-weight: 700;
            }
            QPushButton#yellowButton:hover {
                background: #ca8a04;
            }
            QPushButton#blueButton {
                background: #2563eb;
                color: white;
                border: 1px solid #1d4ed8;
                border-radius: 10px;
                padding: 8px 14px;
                font-weight: 700;
            }
            QPushButton#blueButton:hover {
                background: #1d4ed8;
            }
            QPushButton#lightBlueButton {
                background: #0ea5e9;
                color: white;
                border: 1px solid #0284c7;
                border-radius: 10px;
                padding: 8px 14px;
                font-weight: 700;
            }
            QPushButton#lightBlueButton:hover {
                background: #0284c7;
            }
            QPushButton#lightRedButton {
                background: #f97316;
                color: white;
                border: 1px solid #ea580c;
                border-radius: 10px;
                padding: 8px 14px;
                font-weight: 700;
            }
            QPushButton#lightRedButton:hover {
                background: #ea580c;
            }
            QToolBar {
                background: #e9edf4;
                border: none;
                spacing: 6px;
                padding: 4px;
            }
            QTabWidget::pane {
                border: 1px solid #d1d9e6;
                background: white;
                border-radius: 8px;
            }
            QTabBar::tab {
                background: #e9edf4;
                border: 1px solid #d1d9e6;
                padding: 8px 12px;
                margin-right: 3px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }
            QTabBar::tab:selected {
                background: white;
                border-bottom-color: white;
                font-weight: 700;
            }
            QTextEdit#transcriptLive {
                background: white;
                border: 1px solid #d0d7e2;
                border-radius: 10px;
                padding: 8px;
            }
            """
        )

    def _bind_hotkeys(self) -> None:
        hotkeys = self.settings.get("hotkeys", {})
        bindings = [
            (hotkeys.get("next"), self.go_next),
            (hotkeys.get("skip"), self.go_skip),
            (hotkeys.get("back"), self.go_previous),
            (hotkeys.get("record"), self.toggle_record),
            (hotkeys.get("pause"), self.toggle_pause),
            (hotkeys.get("stop"), self.stop_recording),
        ]
        self._shortcuts: list[QShortcut] = []
        for sequence, handler in bindings:
            if not sequence:
                continue
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.activated.connect(handler)
            self._shortcuts.append(shortcut)
        fullscreen_shortcut = QShortcut(QKeySequence("F11"), self)
        fullscreen_shortcut.activated.connect(self.toggle_fullscreen_mode)
        self._shortcuts.append(fullscreen_shortcut)
        exit_fullscreen_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        exit_fullscreen_shortcut.activated.connect(self.exit_fullscreen_mode)
        self._shortcuts.append(exit_fullscreen_shortcut)

    def _update_fullscreen_button_text(self) -> None:
        self.fullscreen_button.setText("Exit Fullscreen" if self.isFullScreen() else "Fullscreen")

    def toggle_fullscreen_mode(self) -> None:
        if self.isFullScreen():
            self.showMaximized()
        else:
            self.showFullScreen()
        self.raise_()
        self.activateWindow()
        self._update_fullscreen_button_text()

    def exit_fullscreen_mode(self) -> None:
        if not self.isFullScreen():
            return
        self.showMaximized()
        self.raise_()
        self.activateWindow()
        self._update_fullscreen_button_text()

    def choose_project_dir(self) -> None:
        """Open folder picker and load a project directory."""
        selected = QFileDialog.getExistingDirectory(self, "Select Project Directory")
        if selected:
            self.load_project(Path(selected))

    def open_current_screen_folder(self) -> None:
        """Open the current screen's viewport folder (not .extraction)."""
        screen = self._current_screen_or_none()
        if screen is None:
            QMessageBox.information(self, APP_NAME, "No project folder is loaded yet.")
            return
        # Open the viewport folder (e.g., /mobile or /desktop), not the parent or .extraction
        target_dir = screen.screenshot_path.parent
        if not target_dir.exists():
            QMessageBox.warning(self, APP_NAME, f"Folder does not exist: {target_dir}")
            return
        
        # Windows-specific: use os.startfile for better compatibility
        import os
        import sys
        try:
            if sys.platform == "win32":
                # Windows: use os.startfile for explorer
                os.startfile(str(target_dir))
                logger.info("Opened folder via os.startfile: %s", target_dir)
            else:
                # macOS/Linux: use QDesktopServices
                opened = QDesktopServices.openUrl(QUrl.fromLocalFile(str(target_dir)))
                logger.info("Open current screen folder requested: %s (opened=%s)", target_dir, opened)
                if not opened:
                    QMessageBox.warning(self, APP_NAME, f"Could not open folder: {target_dir}")
        except Exception as e:
            logger.error("Failed to open folder: %s", e)
            QMessageBox.warning(self, APP_NAME, f"Could not open folder: {e}")

    def load_project(self, project_dir: Path, show_file_report: bool = True) -> None:
        """Scan a project directory and refresh the screen list."""
        logger.info("Loading project: %s (show_file_report=%s)", project_dir, show_file_report)
        viewport_mode = self.settings.get("viewport", {}).get("mode", "mobile")
        if show_file_report:
            report = analyze_missing_screen_files(project_dir, viewport_mode=str(viewport_mode))
            self._last_file_report = report
            if int(report.get("missing_count", 0)) > 0:
                QMessageBox.warning(
                    self,
                    "Project File Report",
                    format_missing_file_report(report),
                )
        else:
            self._last_file_report = analyze_missing_screen_files(project_dir, viewport_mode=str(viewport_mode))
        screens = scan_project(project_dir, viewport_mode=viewport_mode)
        self.project_dir = project_dir
        self.screens = screens
        self.navigator = Navigator(self.screens, enqueue_callback=self._queue_placeholder)

        self.project_label.setText(str(project_dir))
        if not screens:
            self.statusBar().showMessage(
                "No valid screens found for selected viewport. " + self._api_key_status_summary()
            )
        else:
            self.statusBar().showMessage(
                f"Loaded {len(screens)} screens ({viewport_mode}). "
                + self._api_key_status_summary()
            )

        self._refresh_ui()
        logger.info("Project loaded with %s screens (viewport=%s)", len(screens), viewport_mode)

    def open_settings_dialog(self) -> None:
        """Open the settings dialog and persist changes."""
        current_screen = self._current_screen_or_none()
        current_slug = current_screen.name if current_screen is not None else None
        dialog = SettingsDialog(self.settings, self, project_dir=self.project_dir)
        dialog.setWindowState(dialog.windowState() | Qt.WindowState.WindowMaximized)
        if dialog.exec():
            self.settings = dialog.get_settings()
            save_config(self.settings)
            
            openai_key = str(self.settings.get("api_keys", {}).get("openai", ""))
            self.transcriber.openai_client.api_key = openai_key
            
            self.controls_widget.setParent(None)
            self.controls_widget = ControlsWidget(hotkeys=self.settings.get("hotkeys", {}))
            self.controls_widget.back_requested.connect(self.go_previous)
            self.controls_widget.skip_requested.connect(self.go_skip)
            self.controls_widget.next_requested.connect(self.go_next)
            self.controls_widget.record_requested.connect(self.toggle_record)
            self.controls_widget.pause_requested.connect(self.toggle_pause)
            self.controls_widget.stop_requested.connect(self.stop_recording)
            self.centralWidget().layout().addWidget(self.controls_widget)  # type: ignore[union-attr]
            self._show_startup_status_message()
            if self.project_dir is not None:
                self.load_project(self.project_dir, show_file_report=False)
                if current_slug:
                    for index, screen in enumerate(self.screens):
                        if screen.name == current_slug:
                            self._go_to_screen(index)
                            break
            else:
                self._refresh_ui()

    def open_preflight_dialog(self) -> None:
        """Open a consolidated startup readiness dialog."""
        if self.project_dir is None:
            QMessageBox.information(self, APP_NAME, "Load a project folder before running preflight checks.")
            return
        dialog = PreflightDialog(self.project_dir, self.settings, self)
        dialog.exec()

    def go_next(self) -> None:
        """Move to next screen and mark current for processing."""
        logger.info("Next requested (recording_active=%s)", self.recorder.is_recording())
        if self.navigator is None:
            return
        was_recording = self.recorder.is_recording()
        if was_recording:
            self.stop_recording()
        if self.navigator is None:
            return
        previous_index = self.navigator.current_index()
        self.navigator.next()
        moved_to_next = self.navigator.current_index() != previous_index
        self._refresh_ui()
        if was_recording and moved_to_next:
            logger.info("Auto-start recording on next screen")
            self.toggle_record()
        elif was_recording and not moved_to_next:
            logger.info("Reached last screen after stopping current recording")
            self.statusBar().showMessage("Last screen reached. Recording was saved and no new recording started.")

    def go_skip(self) -> None:
        """Skip current screen."""
        logger.info("Skip requested (recording_active=%s)", self.recorder.is_recording())
        if self.recorder.is_recording():
            self.stop_recording()
        if self.navigator is None:
            return
        self.navigator.skip()
        self._refresh_ui()

    def go_previous(self) -> None:
        """Move to previous screen."""
        logger.info("Back requested (recording_active=%s)", self.recorder.is_recording())
        if self.recorder.is_recording():
            self.stop_recording()
        if self.navigator is None:
            return
        self.navigator.previous()
        self._refresh_ui()

    def _go_to_screen(self, index: int) -> None:
        if self.navigator is None:
            return
        try:
            self.navigator.go_to(index)
        except IndexError:
            return
        self._refresh_ui()

    def _on_viewport_changed(self, mode: str) -> None:
        self.settings["viewport"]["mode"] = mode
        save_config(self.settings)
        if self.project_dir is not None:
            self.load_project(self.project_dir, show_file_report=False)

    def _queue_placeholder(self, screen: ScreenItem) -> None:
        """Phase 4 placeholder queue integration (non-blocking background chain)."""
        self.progress_widget.set_progress(0, 9, f"Queued: {screen.name}")

        def _step(message: str):
            def _runner() -> dict[str, Any]:
                return {"message": message}

            return _runner

        self.queue_manager.add_task(
            screen.name,
            [
                ("save_recording", _step("save_recording")),
                ("extract_frames", _step("extract_frames")),
                ("smart_select", _step("smart_select")),
                ("detect_gestures", _step("detect_gestures")),
                ("run_ocr", _step("run_ocr")),
                ("transcribe_audio", _step("transcribe_audio")),
                ("detect_triggers", _step("detect_triggers")),
                ("analyze", _step("analyze")),
                ("export", _step("export")),
            ],
        )
        self.statusBar().showMessage(f"Queued for future processing: {screen.name} ({screen.viewport})")

    def toggle_record(self) -> None:
        """Start recording for the current screen, or stop if already recording."""
        logger.info("Record toggle requested (is_recording=%s)", self.recorder.is_recording())
        if self.recorder.is_recording():
            self.stop_recording()
            return

        screen = self._current_screen_or_none()
        if screen is None:
            QMessageBox.information(self, APP_NAME, "Load a project and select a screen first.")
            return

        # Check for existing recordings and handle overwrite setting
        overwrite = self.settings.get("recording", {}).get("overwrite_recordings", True)
        if overwrite and screen.extraction_dir.exists():
            logger.info("Overwriting existing recording data in %s", screen.extraction_dir)
            import shutil
            for item in screen.extraction_dir.iterdir():
                try:
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()
                except Exception as e:
                    logger.warning("Could not delete %s: %s", item, e)

        webcam = self.settings.get("webcam", {})
        self.recorder.set_output_dir(screen.extraction_dir)
        self.recorder.start(
            camera_index=int(webcam.get("camera_index", 0)),
            mic_index=int(webcam.get("microphone_index", 0)),
            resolution=str(webcam.get("resolution", "1080p")),
            custom_url=str(webcam.get("custom_url", "")),
        )
        logger.info(
            "Recording started for screen=%s camera_index=%s mic_index=%s resolution=%s backend=%s",
            screen.name,
            int(webcam.get("camera_index", 0)),
            int(webcam.get("microphone_index", 0)),
            str(webcam.get("resolution", "1080p")),
            self.recorder.get_backend_mode(),
        )
        for note in self.recorder.get_backend_notes()[:5]:
            logger.info("Recorder backend note: %s", note)
        screen.status = "recording"
        self._live_segments = []
        self.progress_widget.set_progress(0, 9, "Recording started")
        self.transcript_live_widget.clear_transcript()
        self.transcript_live_widget.append_segment(0.0, "Recording started", event_type="ref")
        self.statusBar().showMessage(f"Recording started for {screen.name}")
        if not self._recording_ui_timer.isActive():
            self._recording_ui_timer.start()
        self._refresh_ui()

    def toggle_pause(self) -> None:
        """Pause or resume recording."""
        logger.info(
            "Pause toggle requested (is_recording=%s is_paused=%s)",
            self.recorder.is_recording(),
            self.recorder.is_paused(),
        )
        if not self.recorder.is_recording():
            return
        if self.recorder.is_paused():
            self.recorder.resume()
            self.transcript_live_widget.append_segment(
                self.recorder.get_duration(),
                "Recording resumed",
            )
            self.statusBar().showMessage("Recording resumed")
        else:
            self.recorder.pause()
            self.transcript_live_widget.append_segment(
                self.recorder.get_duration(),
                "Recording paused",
            )
            self.statusBar().showMessage("Recording paused")
        self._refresh_ui()

    def stop_recording(self) -> None:
        """Stop recording, transcribe audio sequentially via API, and export transcript."""
        logger.info("Stop requested (is_recording=%s)", self.recorder.is_recording())
        if not self.recorder.is_recording():
            return
        screen = self._current_screen_or_none()
        if screen is None:
            return

        video_path, audio_path = self.recorder.stop()
        logger.info(
            "Recording saved video=%s audio=%s backend=%s",
            video_path,
            audio_path,
            self.recorder.get_backend_mode(),
        )
        for note in self.recorder.get_backend_notes()[:5]:
            logger.info("Recorder backend note: %s", note)
            
        screen.status = "processing"
        self._recording_ui_timer.stop()
        self.progress_widget.set_progress(5, 9, "Transcribing via API (OpenAI)...")
        self.statusBar().showMessage(f"Processing audio for {screen.name} via cloud API...")
        self.transcript_live_widget.append_segment(
            self.recorder.get_duration(), "Sending audio to API for transcription..."
        )
        self._refresh_ui()

        # Execute transcription in background to avoid freezing the window
        duration = max(1.0, self.recorder.get_duration())
        provider = str(self.settings.get("speech_to_text", {}).get("provider", "openai_4o_transcribe"))
        language = str(self.settings.get("speech_to_text", {}).get("language", "de"))

        self._transcribe_thread = QThread(self)
        self._transcribe_worker = _TranscriptionWorker(self.transcriber, audio_path, provider, language)
        self._transcribe_worker.moveToThread(self._transcribe_thread)
        self._transcribe_thread.started.connect(self._transcribe_worker.run)
        
        self._transcribe_worker.finished.connect(
            lambda segments, s=screen, v=video_path, a=audio_path, d=duration: 
            self._on_transcription_finished(s, v, a, d, segments)
        )
        self._transcribe_worker.error.connect(
            lambda err, s=screen, v=video_path, a=audio_path, d=duration: 
            self._on_transcription_finished(s, v, a, d, [{"start": 0.0, "end": d, "text": f"(API Error: {err})"}])
        )
        
        self._transcribe_worker.finished.connect(self._transcribe_thread.quit)
        self._transcribe_worker.error.connect(self._transcribe_thread.quit)
        self._transcribe_thread.finished.connect(self._transcribe_worker.deleteLater)
        self._transcribe_thread.finished.connect(self._transcribe_thread.deleteLater)
        self._transcribe_thread.start()

    def _on_transcription_finished(
        self, screen: ScreenItem, video_path: Path, audio_path: Path, duration: float, segments: list[dict[str, Any]]
    ) -> None:
        import json
        self._live_segments = segments
        trigger_events = self.transcriber.detect_trigger_words(
            self._live_segments,
            self.settings.get("trigger_words", {}),
        )

        # Ensure extraction directory structure exists
        from screenreview.utils.extraction_init import ExtractionInitializer
        ExtractionInitializer.ensure_structure(screen.extraction_dir)
        ExtractionInitializer.repair_structure(screen.extraction_dir)

        # Save intermediate: Audio Transcription
        transcript_path = screen.extraction_dir / "audio_transcription.json"
        transcript_path.write_text(json.dumps({
            "text": " ".join(str(seg.get("text", "")) for seg in self._live_segments).strip(),
            "segments": self._live_segments
        }, indent=2, ensure_ascii=False), encoding="utf-8")

        # Save intermediate: Trigger Events
        triggers_path = screen.extraction_dir / "detected_triggers.json"
        triggers_path.write_text(json.dumps(trigger_events, indent=2, ensure_ascii=False), encoding="utf-8")

        # STEP 1: Extract frames from video
        from screenreview.pipeline.frame_extractor import FrameExtractor
        frame_extractor = FrameExtractor(fps=1)
        frames_dir = screen.extraction_dir / "frames"
        all_frames = frame_extractor.extract_frames(video_path, frames_dir)
        logger.info("Frame extraction: %d frames extracted", len(all_frames))

        # STEP 2: Detect gestures
        from screenreview.pipeline.gesture_detector import GestureDetector
        import cv2
        gesture_detector = GestureDetector()
        gesture_positions = []
        gesture_regions = []
        for i, frame_path in enumerate(all_frames[:3]):  # Sample 3 frames for gesture detection
            try:
                frame = cv2.imread(str(frame_path))
                if frame is not None:
                    is_gesture, gx, gy = gesture_detector.detect_gesture_in_frame(frame)
                    if is_gesture and gx is not None and gy is not None:
                        gesture_positions.append({"x": gx, "y": gy})
                        gesture_regions.append({"x": gx, "y": gy, "frame_index": i})
            except Exception as e:
                logger.warning("Gesture detection failed for %s: %s", frame_path, e)
        logger.info("Gesture detection: %d gestures found", len(gesture_positions))

        # Save intermediate: Raw Gestures
        gestures_path = screen.extraction_dir / "gestures_raw.json"
        gestures_path.write_text(json.dumps(gesture_regions, indent=2, ensure_ascii=False), encoding="utf-8")

        # STEP 3: Run OCR
        ocr_results = []
        full_screenshot_ocr = []
        ocr_processor = None
        try:
            from screenreview.pipeline.ocr_processor import OcrProcessor
            ocr_processor = OcrProcessor()
            # Process main screenshot
            full_screenshot_ocr = ocr_processor.process(screen.screenshot_path)
            
            for frame_path in all_frames[:3]:  # Sample 3 frames for OCR
                try:
                    result = ocr_processor.process(frame_path)
                    ocr_results.append(result)
                except Exception as e:
                    logger.warning("OCR processing failed for %s: %s", frame_path, e)
            logger.info("OCR processing: %d frames processed", len(ocr_results))
        except Exception as e:
            logger.warning("OCR processing failed: %s - skipping OCR", e)
            ocr_results = []

        # STEP 4: Smart frame selection
        from screenreview.pipeline.smart_selector import SmartSelector
        smart_selector = SmartSelector()
        selected_frames = smart_selector.select_frames(all_frames, self.settings)
        logger.info("Smart selection: %d frames selected", len(selected_frames))

        # Save intermediate: Selected Frames
        selected_frames_path = screen.extraction_dir / "selected_frames.json"
        selected_frames_path.write_text(json.dumps([str(p) for p in selected_frames], indent=2, ensure_ascii=False), encoding="utf-8")

        # STEP 5: Create gesture events for annotation matching
        # Convert simple positions back to event format if needed
        gesture_events = []
        for i, pos in enumerate(gesture_positions):
            gesture_events.append({
                "timestamp": i * 1.0, # Placeholder timestamp if not tracked
                "screenshot_position": pos
            })

        # STEP 6: Generate annotations
        annotations = []
        if ocr_processor and gesture_events:
            annotations = ocr_processor.process_gesture_annotations(
                screen.extraction_dir.parent, # Viewport dir
                gesture_events,
                self._live_segments
            )

        extraction = ExtractionResult(
            screen=screen,
            video_path=video_path,
            audio_path=audio_path,
            all_frames=all_frames,
            selected_frames=selected_frames,
            gesture_positions=gesture_positions,
            gesture_regions=gesture_regions,
            ocr_results=full_screenshot_ocr, # Store full screenshot OCR for transcript
            transcript_text=" ".join(str(seg.get("text", "")) for seg in self._live_segments).strip(),
            transcript_segments=self._live_segments,
            trigger_events=trigger_events,
            annotations=annotations,
        )
        metadata = self._read_metadata_dict(screen)
        duration_minutes = max(0.01, duration / 60.0)
        provider = str(self.settings.get("speech_to_text", {}).get("provider", "gpt-4o-mini-transcribe"))
        self.cost_tracker.add(provider, duration_minutes, screen.name)
        # Note: Analysis models cost added here as mockup until phase 4 analyzer handles it
        self.cost_tracker.add("llama_32_vision", 6, screen.name)
        
        self.exporter.export(extraction, metadata=metadata, analysis_data={})
        logger.info("Export complete for screen=%s duration_seconds=%.2f", screen.name, duration)
        
        # Only update the active UI text widgets if the user is STILL on that exact screen.
        # Otherwise, they already hit Next and are recording the next screen.
        current_active = self._current_screen_or_none()
        if current_active is not None and current_active.name == screen.name:
            self.progress_widget.set_progress(9, 9, "Export complete")
            self.transcript_live_widget.clear_transcript()
            for seg in segments:
                seg_time = float(seg.get("start", 0.0))
                self.transcript_live_widget.append_segment(seg_time, str(seg.get("text", "")))
            self.transcript_live_widget.append_segment(duration, "Processing saved", event_type="ok")
            self.statusBar().showMessage(f"Recording & Transcript saved to {screen.extraction_dir}")

        screen.status = "pending"
        self._refresh_ui()

    def _update_recording_feedback(self) -> None:
        if not self.recorder.is_recording():
            self._recording_ui_timer.stop()
            self._recording_ui_phase = 0
            self._refresh_ui()
            return
        self._recording_ui_phase = (self._recording_ui_phase + 1) % 4
        elapsed = self.recorder.get_duration()
        mm = int(elapsed) // 60
        ss = int(elapsed) % 60
        state_text = "paused" if self.recorder.is_paused() else "recording"
        audio_level_pct = int(max(0.0, min(1.0, self.recorder.get_audio_level())) * 100)
        backend_mode = self.recorder.get_backend_mode()
        self.progress_widget.status_label.setText(
            f"Live capture {state_text}: {mm:02d}:{ss:02d} | audio {audio_level_pct}% | {backend_mode}"
        )
        self.controls_widget.set_recording_state(
            is_recording=True,
            is_paused=self.recorder.is_paused(),
            elapsed_seconds=elapsed,
            animation_phase=self._recording_ui_phase,
        )

    def _focus_batch_panel(self) -> None:
        """Scroll the right panel to show the batch overview widget and give it focus."""
        self.batch_overview_widget.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self.batch_overview_widget.scroll.verticalScrollBar().setValue(0)
        # Ensure the batch panel is visible by scrolling the right panel
        self.batch_overview_widget.show()
        self.batch_overview_widget.raise_()

    def _refresh_ui(self) -> None:
        self._update_fullscreen_button_text()
        screen = self._current_screen_or_none()
        self.viewer_widget.set_image(screen.screenshot_path if screen else None)
        self.metadata_widget.set_screen(screen)
        self.batch_overview_widget.set_screens(
            self.screens,
            current_index=self.navigator.current_index() if self.navigator else 0,
        )
        self._refresh_phase3_hints(screen)
        self._refresh_cost_widget(screen)
        self._refresh_setup_status_widget()

        total = len(self.screens)
        if screen and self.navigator:
            index = self.navigator.current_index()
            self.status_label.setText(
                f"Screen {index + 1} of {total} | Status: {screen.status.upper()}"
            )
            self.route_label.setText(f"Current route: {screen.route or '-'}")
            self.controls_widget.set_navigation_state(
                can_go_back=not self.navigator.is_first(),
                can_go_next=not self.navigator.is_last(),
            )
        else:
            self.status_label.setText("Screen 0 of 0")
            self.route_label.setText("Route: -")
            self.controls_widget.set_navigation_state(can_go_back=False, can_go_next=False)
        self.controls_widget.set_recording_state(
            is_recording=self.recorder.is_recording(),
            is_paused=self.recorder.is_paused(),
            elapsed_seconds=self.recorder.get_duration(),
            animation_phase=self._recording_ui_phase,
        )
        self._refresh_status_tooltips(screen)

    def _refresh_phase3_hints(self, screen: ScreenItem | None) -> None:
        if screen is not None and screen.extraction_dir.exists():
            # Try to get real stats from extraction directory
            frames_dir = screen.extraction_dir / "frames"
            selected_dir = screen.extraction_dir / "selected_frames"
            
            total_frames = 0
            if frames_dir.exists():
                total_frames = len(list(frames_dir.glob("*.png")))
            
            # If we don't have a separate selected_dir, we might look at gesture_annotations
            annotations_path = screen.extraction_dir / "gesture_annotations.json"
            selected_count = 0
            if annotations_path.exists():
                try:
                    import json
                    anns = json.loads(annotations_path.read_text(encoding="utf-8"))
                    selected_count = len(anns)
                except Exception:
                    selected_count = 0
            
            # Default fallback for mockup feel if no data yet
            if total_frames == 0:
                total_frames = 20
                selected_count = 6
            
            saved_euro = max(0.0, (total_frames - selected_count) * 0.002)
            self.smart_hint_widget.set_stats(total_frames, selected_count, saved_euro)
        else:
            self.smart_hint_widget.set_stats(0, 0, 0.0)

        if screen is None or self.navigator is None or self.navigator.is_first():
            self.comparison_widget.set_comparison(None, screen.name if screen else None, None)
            return

        try:
            prev_screen = self.screens[self.navigator.current_index() - 1]
            _, diff_ratio = self.differ.compute_diff(prev_screen.screenshot_path, screen.screenshot_path)
        except Exception:
            prev_screen = None
            diff_ratio = None

        self.comparison_widget.set_comparison(
            prev_screen.name if prev_screen else None,
            screen.name,
            diff_ratio,
        )

    def _refresh_cost_widget(self, screen: ScreenItem | None) -> None:
        budget_limit = float(self.settings.get("cost", {}).get("budget_limit_euro", 0.0))
        screen_cost = self.cost_tracker.get_screen_cost(screen.name) if screen else 0.0
        session_cost = self.cost_tracker.get_total()
        self.cost_widget.set_costs(screen_cost, session_cost, budget_limit)

    def _current_screen_or_none(self) -> ScreenItem | None:
        if self.navigator is None or not self.screens:
            return None
        try:
            return self.navigator.current()
        except IndexError:
            return None

    def _read_metadata_dict(self, screen: ScreenItem) -> dict[str, Any]:
        try:
            import json

            raw = json.loads(screen.metadata_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                return raw
        except Exception:
            pass
        return {
            "route": screen.route,
            "viewport": screen.viewport,
            "viewport_size": screen.viewport_size,
            "timestamp_utc": screen.timestamp_utc,
            "git": {"branch": screen.git_branch, "commit": screen.git_commit},
            "playwright": {"browser": screen.browser},
        }

    def _show_startup_status_message(self) -> None:
        self.statusBar().showMessage(
            "Ready. " + self._api_key_status_summary() + " Open Settings for live connection checks."
        )

    def _api_key_status_summary(self) -> str:
        api_keys = self.settings.get("api_keys", {})
        openai_loaded = bool(str(api_keys.get("openai", "")).strip())
        replicate_loaded = bool(str(api_keys.get("replicate", "")).strip())
        openrouter_loaded = bool(str(api_keys.get("openrouter", "")).strip())
        openai_text = "OpenAI key loaded." if openai_loaded else "OpenAI key missing."
        replicate_text = "Replicate key loaded." if replicate_loaded else "Replicate key missing."
        openrouter_text = "OpenRouter key loaded." if openrouter_loaded else "OpenRouter key missing."
        return f"{openai_text} {replicate_text} {openrouter_text}"

    def _refresh_setup_status_widget(self) -> None:
        file_text = "No project loaded"
        if self.project_dir is not None:
            report = self._last_file_report
            if report is None:
                report = analyze_missing_screen_files(
                    self.project_dir,
                    viewport_mode=str(self.settings.get("viewport", {}).get("mode", "mobile")),
                )
                self._last_file_report = report
            missing_count = int(report.get("missing_count", 0))
            file_text = "OK" if missing_count == 0 else f"{missing_count} missing"

        api_keys = self.settings.get("api_keys", {})
        openai_status = "configured" if str(api_keys.get("openai", "")).strip() else "missing"
        replicate_status = "configured" if str(api_keys.get("replicate", "")).strip() else "missing"
        openrouter_status = "configured" if str(api_keys.get("openrouter", "")).strip() else "missing"
        analysis_cfg = self.settings.get("analysis", {})
        provider = str(analysis_cfg.get("provider", "replicate"))
        model = str(analysis_cfg.get("model", "llama_32_vision"))
        self.setup_files_label.setText(file_text)
        self.setup_analysis_label.setText(provider)
        self.setup_preflight_label.setText("Check")
