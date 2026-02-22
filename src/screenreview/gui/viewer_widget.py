# -*- coding: utf-8 -*-
"""Widget for showing the current screenshot."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QSizePolicy
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget


class ViewerWidget(QWidget):
    """Display a screenshot image with a framed placeholder."""

    MIN_DISPLAY_WIDTH = 500

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._image_path: Path | None = None
        self._scale_percent = 100

        self.title_label = QLabel("Screenshot")
        self.title_label.setObjectName("sectionTitle")
        self.scale_combo = QComboBox()
        self.scale_combo.addItems(["10%", "20%", "30%", "40%", "50%", "75%", "100%"])
        self.scale_combo.setCurrentText("100%")
        self.scale_combo.setToolTip("Scale screenshot width relative to the viewer area.")
        self.scale_combo.currentTextChanged.connect(self._on_scale_changed)
        self.scale_label = QLabel("Scale")
        self.scale_label.setObjectName("mutedText")
        self.image_label = QLabel("No screenshot loaded")
        self.image_label.setObjectName("viewerSurface")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Keep minimum size small; readability is handled by scaling + scrollbars.
        self.image_label.setMinimumSize(120, 120)
        self.image_label.setScaledContents(False)
        self.image_label.setContentsMargins(8, 8, 8, 8)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setMinimumWidth(240)
        self.scroll_area.setMinimumHeight(260)
        self.scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setWidget(self.image_label)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(8)
        title_row.addWidget(self.title_label)
        title_row.addStretch(1)
        title_row.addWidget(self.scale_label)
        title_row.addWidget(self.scale_combo)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addLayout(title_row)
        layout.addWidget(self.scroll_area, 1)

    def set_image(self, path: Path | None) -> None:
        """Load and display an image from disk."""
        self._image_path = path
        if path is None or not path.exists():
            self.image_label.setText("No screenshot loaded")
            self.image_label.setPixmap(QPixmap())
            self.image_label.adjustSize()
            return

        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self.image_label.setText("Failed to load screenshot")
            self.image_label.setPixmap(QPixmap())
            self.image_label.adjustSize()
            return

        self._set_scaled_pixmap(pixmap)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        if self._image_path and self._image_path.exists():
            pixmap = QPixmap(str(self._image_path))
            if not pixmap.isNull():
                self._set_scaled_pixmap(pixmap)

    def _on_scale_changed(self, text: str) -> None:
        raw = text.strip().rstrip("%")
        try:
            value = int(raw)
        except ValueError:
            value = 100
        self._scale_percent = max(10, min(100, value))
        if self._image_path and self._image_path.exists():
            pixmap = QPixmap(str(self._image_path))
            if not pixmap.isNull():
                self._set_scaled_pixmap(pixmap)

    def _set_scaled_pixmap(self, pixmap: QPixmap) -> None:
        target_size = self.scroll_area.viewport().size()
        target_width = max(1, target_size.width() - 16)
        target_height = max(1, target_size.height() - 16)
        scaled_target_width = int(target_width * (self._scale_percent / 100.0))
        display_width = max(self.MIN_DISPLAY_WIDTH, scaled_target_width)

        # Keep screenshots readable by scaling to width. Scrollbars handle overflow.
        if display_width > 0:
            scaled = pixmap.scaledToWidth(display_width, Qt.TransformationMode.SmoothTransformation)
        else:
            scaled = pixmap.scaled(
                max(1, self.MIN_DISPLAY_WIDTH),
                max(1, target_height),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        self.image_label.setPixmap(scaled)
        self.image_label.resize(scaled.size())
        self.image_label.setText("")
