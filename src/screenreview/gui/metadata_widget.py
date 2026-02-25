# -*- coding: utf-8 -*-
"""Metadata panel for the selected screen."""

from __future__ import annotations

from PyQt6.QtWidgets import QFormLayout, QLabel, QVBoxLayout, QWidget

from screenreview.models.screen_item import ScreenItem


from PyQt6.QtWidgets import QFormLayout, QLabel, QVBoxLayout, QWidget, QHBoxLayout, QFrame

class MetadataWidget(QWidget):
    """Show key metadata from meta.json in a two-column layout."""

    LEFT_FIELDS = (
        ("route", "Route"),
        ("viewport", "Viewport"),
        ("size", "Size"),
        ("browser", "Browser"),
    )
    RIGHT_FIELDS = (
        ("branch", "Branch"),
        ("commit", "Commit"),
        ("timestamp", "Timestamp"),
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.title_label = QLabel("Metadata")
        self.title_label.setObjectName("sectionTitle")

        self._value_labels: dict[str, QLabel] = {}
        
        # Container for the two columns
        columns_container = QWidget()
        columns_layout = QHBoxLayout(columns_container)
        columns_layout.setContentsMargins(0, 0, 0, 0)
        columns_layout.setSpacing(12)

        # Left column
        left_form = QFormLayout()
        left_form.setSpacing(4)
        for key, label_text in self.LEFT_FIELDS:
            value_label = QLabel("-")
            value_label.setObjectName("metaValue")
            self._value_labels[key] = value_label
            left_form.addRow(f"{label_text}:", value_label)
        
        # Vertical Separator
        line = QFrame()
        line.setFrameShape(QFrame.Shape.VLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet("color: #d1d9e6;")

        # Right column
        right_form = QFormLayout()
        right_form.setSpacing(4)
        for key, label_text in self.RIGHT_FIELDS:
            value_label = QLabel("-")
            value_label.setObjectName("metaValue")
            self._value_labels[key] = value_label
            right_form.addRow(f"{label_text}:", value_label)

        # Wrappers to ensure equal width
        left_wrapper = QWidget()
        left_wrapper_layout = QVBoxLayout(left_wrapper)
        left_wrapper_layout.setContentsMargins(0, 0, 0, 0)
        left_wrapper_layout.addLayout(left_form)

        right_wrapper = QWidget()
        right_wrapper_layout = QVBoxLayout(right_wrapper)
        right_wrapper_layout.setContentsMargins(0, 0, 0, 0)
        right_wrapper_layout.addLayout(right_form)

        columns_layout.addWidget(left_wrapper, 1)
        columns_layout.addWidget(line)
        columns_layout.addWidget(right_wrapper, 1)
        
        # Force equal width
        columns_layout.setStretch(0, 1)
        columns_layout.setStretch(2, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.title_label)
        layout.addWidget(columns_container)

    def set_screen(self, screen: ScreenItem | None) -> None:
        """Populate metadata from the current screen."""
        if screen is None:
            for label in self._value_labels.values():
                label.setText("-")
            return

        size = screen.viewport_size or {}
        size_text = f"{size.get('w', '?')}x{size.get('h', '?')}"
        commit_text = screen.git_commit[:12] if screen.git_commit else "-"

        values = {
            "route": screen.route or "-",
            "viewport": screen.viewport or "-",
            "size": size_text,
            "browser": screen.browser or "-",
            "branch": screen.git_branch or "-",
            "commit": commit_text,
            "timestamp": screen.timestamp_utc or "-",
        }
        for key, value in values.items():
            self._value_labels[key].setText(str(value))

