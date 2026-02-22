# -*- coding: utf-8 -*-
"""Widget for showing the current screenshot."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class ViewerWidget(QWidget):
    """Display a screenshot image with a framed placeholder."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._image_path: Path | None = None

        self.title_label = QLabel("Screenshot")
        self.title_label.setObjectName("sectionTitle")
        self.image_label = QLabel("No screenshot loaded")
        self.image_label.setObjectName("viewerSurface")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumSize(420, 320)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.title_label)
        layout.addWidget(self.image_label, 1)

    def set_image(self, path: Path | None) -> None:
        """Load and display an image from disk."""
        self._image_path = path
        if path is None or not path.exists():
            self.image_label.setText("No screenshot loaded")
            self.image_label.setPixmap(QPixmap())
            return

        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self.image_label.setText("Failed to load screenshot")
            self.image_label.setPixmap(QPixmap())
            return

        self._set_scaled_pixmap(pixmap)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        if self._image_path and self._image_path.exists():
            pixmap = QPixmap(str(self._image_path))
            if not pixmap.isNull():
                self._set_scaled_pixmap(pixmap)

    def _set_scaled_pixmap(self, pixmap: QPixmap) -> None:
        target_size = self.image_label.size()
        scaled = pixmap.scaled(
            max(1, target_size.width() - 12),
            max(1, target_size.height() - 12),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled)
        self.image_label.setText("")

