# -*- coding: utf-8 -*-
"""Application entry point."""

from __future__ import annotations

import sys
from pathlib import Path
import logging

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QMessageBox

from screenreview.config import load_config
from screenreview.core.precheck import analyze_missing_screen_files, format_missing_file_report
from screenreview.gui.main_window import MainWindow
from screenreview.utils.logger import setup_session_logging


def main() -> int:
    """Start the GUI application."""
    session_log_path = setup_session_logging(Path.cwd(), "multimedia-feedback-coding")
    logger = logging.getLogger(__name__)
    app = QApplication(sys.argv)
    if session_log_path is not None:
        logger.info("Session log file: %s", session_log_path)
    settings = load_config()
    startup_project_dir: Path | None = None
    
    # Check for command-line argument first
    if len(sys.argv) > 1:
        candidate = Path(sys.argv[1])
        if candidate.exists():
            startup_project_dir = candidate
    
    # Fall back to default_project_dir from settings if no command-line argument
    if startup_project_dir is None:
        default_dir = settings.get("default_project_dir")
        if default_dir:
            candidate = Path(default_dir)
            if candidate.exists():
                startup_project_dir = candidate
                logger.info("Auto-loading default project dir: %s", startup_project_dir)

    if startup_project_dir is not None:
        viewport_mode = str(settings.get("viewport", {}).get("mode", "mobile"))
        report = analyze_missing_screen_files(startup_project_dir, viewport_mode=viewport_mode)
        if int(report.get("missing_count", 0)) > 0:
            QMessageBox.warning(
                None,
                "Pre-Start File Report",
                format_missing_file_report(report),
            )

    window = MainWindow(settings=settings)
    if startup_project_dir is not None:
        window.load_project(startup_project_dir, show_file_report=False)
    window.showFullScreen()
    window.raise_()
    window.activateWindow()
    QTimer.singleShot(50, window.raise_)
    QTimer.singleShot(50, window.activateWindow)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
