# -*- coding: utf-8 -*-
"""Widget for before/after comparison summary."""

from __future__ import annotations

from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class ComparisonWidget(QWidget):
    """Show basic diff information between two screenshots."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.title_label = QLabel("Comparison")
        self.title_label.setObjectName("sectionTitle")
        self.before_label = QLabel("Before: -")
        self.after_label = QLabel("After: -")
        self.diff_label = QLabel("Change: 0.00%")
        for label in (self.before_label, self.after_label, self.diff_label):
            label.setObjectName("mutedText")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self.title_label)
        layout.addWidget(self.before_label)
        layout.addWidget(self.after_label)
        layout.addWidget(self.diff_label)
        layout.addStretch(1)

    def set_comparison(self, before_name: str | None, after_name: str | None, diff_ratio: float | None) -> None:
        self.before_label.setText(f"Before: {before_name or '-'}")
        self.after_label.setText(f"After: {after_name or '-'}")
        if diff_ratio is None:
            self.diff_label.setText("Change: -")
        else:
            self.diff_label.setText(f"Change: {diff_ratio * 100:.2f}%")

