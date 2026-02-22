# -*- coding: utf-8 -*-
"""Metadata panel for the selected screen."""

from __future__ import annotations

from PyQt6.QtWidgets import QFormLayout, QLabel, QVBoxLayout, QWidget

from screenreview.models.screen_item import ScreenItem


class MetadataWidget(QWidget):
    """Show key metadata from meta.json."""

    FIELD_ORDER = (
        ("route", "Route"),
        ("viewport", "Viewport"),
        ("size", "Size"),
        ("browser", "Browser"),
        ("branch", "Branch"),
        ("commit", "Commit"),
        ("timestamp", "Timestamp"),
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.title_label = QLabel("Metadata")
        self.title_label.setObjectName("sectionTitle")

        self._value_labels: dict[str, QLabel] = {}
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(6)
        for key, label_text in self.FIELD_ORDER:
            value_label = QLabel("-")
            value_label.setObjectName("metaValue")
            value_label.setWordWrap(True)
            self._value_labels[key] = value_label
            form.addRow(f"{label_text}:", value_label)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.title_label)
        layout.addLayout(form)
        layout.addStretch(1)

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

