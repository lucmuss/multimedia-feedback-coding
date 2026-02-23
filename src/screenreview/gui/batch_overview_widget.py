# -*- coding: utf-8 -*-
"""Compact tile overview of all screens (no screenshots)."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
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


STATUS_COLOR = {
    "pending": "#6b7280",
    "recording": "#dc2626",
    "processing": "#d97706",
    "done": "#059669",
    "skipped": "#9ca3af",
}

STATUS_ABBREV = {
    "pending": "·",
    "recording": "●",
    "processing": "…",
    "done": "✓",
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

    def _refresh_label(self) -> None:
        abbrev = STATUS_ABBREV.get(self.screen.status, "?")
        name = self.screen.route or self.screen.name
        # Truncate long names
        display = name if len(name) <= 18 else name[:16] + "…"
        self.setText(f"{abbrev} {self.index + 1}: {display}")
        color = STATUS_COLOR.get(self.screen.status, "#6b7280")
        self.setStyleSheet(
            f"""
            QPushButton[objectName="batchTile"] {{
                background: white;
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

