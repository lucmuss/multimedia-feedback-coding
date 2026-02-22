# -*- coding: utf-8 -*-
"""Application entry point."""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication, QMessageBox

from screenreview.config import load_config
from screenreview.core.precheck import analyze_missing_screen_files, format_missing_file_report
from screenreview.gui.main_window import MainWindow


def main() -> int:
    """Start the GUI application."""
    app = QApplication(sys.argv)
    settings = load_config()
    startup_project_dir: Path | None = None
    if len(sys.argv) > 1:
        candidate = Path(sys.argv[1])
        if candidate.exists():
            startup_project_dir = candidate

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
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
