# -*- coding: utf-8 -*-
"""Compact tile overview of all screens (no screenshots)."""

from __future__ import annotations

import os
from pathlib import Path
from PyQt6.QtCore import Qt, pyqtSignal, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from screenreview.models.screen_item import ScreenItem


# New very light beige-toned colors as requested by the user
STATUS_BG_COLOR = {
    "pending": "#fff9e6",    # Very light beige/yellow (Hellgelb)
    "done": "#f2faf2",       # Very light beige/green (Hellgrün)
    "error": "#fff2f2",      # Very light beige/red (Hellrot)
    "recording": "#fef2f2",  # Light red tint
    "processing": "#fffbeb", # Light yellow/beige
}

STATUS_COLOR = {
    "pending": "#92400e",    # Brownish/Orange
    "recording": "#dc2626",
    "processing": "#d97706",
    "done": "#166534",       # Dark green
    "error": "#b91c1c",      # Red
    "skipped": "#9ca3af",
}

STATUS_ABBREV = {
    "pending": "·",
    "recording": "●",
    "processing": "…",
    "done": "✓",
    "error": "⚠",
    "skipped": "–",
}


class _TileButton(QPushButton):
    """Compact tile showing only the screen name and status — no screenshot."""

    def __init__(self, index: int, screen: ScreenItem, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.index = index
        self.screen = screen
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("batchTile")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(22)
        self._refresh_label()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            # Open file explorer in the screen's extraction directory
            folder = str(self.screen.extraction_dir)
            if os.name == 'nt':
                os.startfile(folder)
            else:
                QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
        else:
            super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        """Open file explorer in the screen's extraction directory on double-click."""
        folder = str(self.screen.extraction_dir)
        if os.name == 'nt':
            os.startfile(folder)
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
        super().mouseDoubleClickEvent(event)

    def _refresh_label(self) -> None:
        # Determine status based on file existence and error state
        status = self.screen.status
        if self.screen.error:
            status = "error"
        else:
            # Check if transcript file exists for this specific screen/viewport
            try:
                if self.screen.transcript_path.exists():
                    status = "done"
                elif status == "done": # If status says done but file missing, reset to pending
                    status = "pending"
            except Exception:
                pass

        abbrev = STATUS_ABBREV.get(status, "?")
        name = self.screen.route or self.screen.name
        # Truncate long names
        display = name if len(name) <= 18 else name[:16] + "…"
        self.setText(f"{abbrev} {self.index + 1}: {display}")
        
        color = STATUS_COLOR.get(status, "#6b7280")
        bg_color = STATUS_BG_COLOR.get(status, "white")
        
        self.setStyleSheet(
            f"""
            QPushButton[objectName="batchTile"] {{
                background: {bg_color};
                border: 1px solid #d0d7e2;
                border-radius: 3px;
                padding: 1px 4px;
                font-size: 10px;
                text-align: left;
                color: {color};
            }}
            QPushButton[objectName="batchTile"]:checked {{
                border: 1px solid #2563eb;
                background: #eef4ff;
                color: #1d4ed8;
                font-weight: 600;
            }}
            QPushButton[objectName="batchTile"]:hover {{
                border-color: #93c5fd;
                background: #f8fbff;
            }}
            """
        )


class BatchOverviewWidget(QWidget):
    """Compact scrollable tile list for quick navigation. No screenshots — names only."""

    screen_selected = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tiles: list[_TileButton] = []

        self.title_label = QLabel("Batch Overview")
        self.title_label.setObjectName("sectionTitle")

        self.grid_host = QWidget()
        self.grid = QGridLayout(self.grid_host)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(3)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setWidget(self.grid_host)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self.title_label)
        layout.addWidget(self.scroll, 1)

    def set_screens(self, screens: list[ScreenItem], current_index: int = 0) -> None:
        """Rebuild compact tiles (no screenshots)."""
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._tiles.clear()

        columns = 2
        for index, screen in enumerate(screens):
            tile = _TileButton(index=index, screen=screen)
            tile.clicked.connect(lambda checked=False, i=index: self.screen_selected.emit(i))
            self._tiles.append(tile)
            row = index // columns
            col = index % columns
            self.grid.addWidget(tile, row, col)

        self.set_current_index(current_index)

    def set_current_index(self, index: int) -> None:
        """Highlight the active tile and scroll it into view."""
        for tile in self._tiles:
            tile.setChecked(tile.index == index)
            if tile.index == index:
                self.scroll.ensureWidgetVisible(tile)
