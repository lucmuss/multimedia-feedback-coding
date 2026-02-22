# -*- coding: utf-8 -*-
"""Thumbnail overview of all screens."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from screenreview.models.screen_item import ScreenItem


STATUS_ICON = {
    "pending": "[]",
    "recording": "REC",
    "processing": "...",
    "done": "OK",
    "skipped": "SKIP",
}


class _BatchCard(QPushButton):
    def __init__(self, index: int, screen: ScreenItem, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.index = index
        self.screen = screen
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumSize(180, 140)
        self.setObjectName("batchCard")
        self._build_label()

    def _build_label(self) -> None:
        status = STATUS_ICON.get(self.screen.status, self.screen.status.upper())
        route = self.screen.route or self.screen.name
        self.setText(f"{status}  {self.index + 1}\n{route}\n{self.screen.viewport}")
        thumb = _load_icon(self.screen.screenshot_path)
        if thumb is not None:
            self.setIcon(thumb)
            self.setIconSize(thumb.availableSizes()[0] if thumb.availableSizes() else self.iconSize())


def _load_icon(path: Path) -> QIcon | None:
    if not path.exists():
        return None
    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        return None
    scaled = pixmap.scaled(84, 84, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    return QIcon(scaled)


class BatchOverviewWidget(QWidget):
    """Scrollable overview for quick navigation."""

    screen_selected = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._cards: list[_BatchCard] = []

        self.title_label = QLabel("Batch Overview")
        self.title_label.setObjectName("sectionTitle")

        self.grid_host = QWidget()
        self.grid = QGridLayout(self.grid_host)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(8)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setWidget(self.grid_host)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.title_label)
        layout.addWidget(self.scroll, 1)

    def set_screens(self, screens: list[ScreenItem], current_index: int = 0) -> None:
        """Rebuild thumbnail cards."""
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._cards.clear()

        columns = 2
        for index, screen in enumerate(screens):
            card = _BatchCard(index=index, screen=screen)
            card.clicked.connect(lambda checked=False, i=index: self.screen_selected.emit(i))
            self._cards.append(card)
            row = index // columns
            col = index % columns
            self.grid.addWidget(card, row, col)

        self.set_current_index(current_index)

    def set_current_index(self, index: int) -> None:
        """Highlight current card."""
        for card in self._cards:
            card.setChecked(card.index == index)

