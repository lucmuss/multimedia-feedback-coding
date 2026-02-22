# -*- coding: utf-8 -*-
"""Capture phase 1 GUI screenshots in offscreen mode."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QImage
from PyQt6.QtWidgets import QApplication

from screenreview.config import get_default_config
from screenreview.gui.main_window import MainWindow
from screenreview.gui.settings_dialog import SettingsDialog


def create_demo_project(base_dir: Path) -> Path:
    project_dir = base_dir / "demo-project"
    page_specs = [
        ("login_html", "/login.html"),
        ("dashboard_html", "/dashboard.html"),
        ("settings_html", "/settings.html"),
    ]
    for page_name, route in page_specs:
        viewport_dir = project_dir / page_name / "mobile"
        viewport_dir.mkdir(parents=True, exist_ok=True)

        meta = {
            "route": route,
            "slug": page_name,
            "url": f"http://127.0.0.1:8085{route}",
            "viewport": "mobile",
            "viewport_size": {"w": 390, "h": 844},
            "timestamp_utc": "2026-02-21T21:43:57Z",
            "git": {
                "branch": "main",
                "commit": "8904800cd7d591afb43873fb76cb1fd5272ac957",
            },
            "playwright": {"browser": "chromium", "test": route.lstrip("/")},
        }
        (viewport_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        (viewport_dir / "transcript.md").write_text(
            (
                "# Transcript (Voice -> Text)\n"
                f"Route: {route}\n"
                "Viewport: mobile\n\n"
                "## Notes\n"
                "- Demo content\n\n"
                "## Numbered refs (optional)\n"
                "1:\n2:\n3:\n"
            ),
            encoding="utf-8",
        )
        create_demo_image(viewport_dir / "screenshot.png", route)
    return project_dir


def create_demo_image(path: Path, label: str) -> None:
    image = QImage(390, 844, QImage.Format.Format_RGB32)
    color = {
        "/login.html": QColor("#daeafe"),
        "/dashboard.html": QColor("#dcfce7"),
        "/settings.html": QColor("#fee2e2"),
    }.get(label, QColor("#f5f5f5"))
    image.fill(color)
    image.save(str(path))


def save_widget(widget, target: Path) -> None:
    widget.repaint()
    QApplication.processEvents()
    pixmap = widget.grab()
    pixmap.save(str(target))


def main() -> int:
    output_dir = ROOT / "output" / "gui-screenshots"
    output_dir.mkdir(parents=True, exist_ok=True)
    demo_root = ROOT / "output"
    project_dir = create_demo_project(demo_root)

    app = QApplication(sys.argv)
    app.setApplicationName("multimedia-feedback-coding")

    settings = get_default_config()
    settings["viewport"]["mode"] = "mobile"

    main_window = MainWindow(settings=settings)
    main_window.load_project(project_dir)
    main_window.show()
    main_window.raise_()
    QApplication.processEvents()
    save_widget(main_window, output_dir / "00-overview.png")

    dialog = SettingsDialog(settings=settings, parent=main_window)
    dialog.show()
    QApplication.processEvents()
    save_widget(dialog, output_dir / "01-settings-overview.png")

    for index in range(dialog.tab_widget.count()):
        dialog.tab_widget.setCurrentIndex(index)
        QApplication.processEvents()
        tab_name = dialog.tab_widget.tabText(index).lower().replace(" ", "-").replace("&", "and")
        file_name = f"{index + 2:02d}-{tab_name}.png"
        save_widget(dialog, output_dir / file_name)

    dialog.close()
    main_window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
